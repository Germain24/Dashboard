"""Service météo — OpenWeather (préféré) + Open-Meteo (fallback).

Décisions CONV 2 :
- Provider principal : OpenWeather (tier Free, clé dans `.env`).
- Fallback automatique : Open-Meteo si la clé manque, est invalide, ou échec.
- Cache in-memory 30 min (configurable via `GARDEROBE_WEATHER_CACHE_TTL`).
- Expose la série horaire **et** la moyenne 7h-23h utilisée pour le ciblage
  thermique du nouvel optimiseur (cf. `optimizer.py`).
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Modèles de données
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HourlyTemp:
    hour: int             # 0..23 (heure locale)
    temp: float           # °C
    apparent_temp: float  # °C ressenti

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WeatherData:
    temp: float
    feels: float
    temp_min: float
    temp_max: float
    humidity: float
    wind: float            # km/h
    precip: float          # mm sur la dernière heure
    desc: str
    icon: str
    source: str
    hourly: list[HourlyTemp] = field(default_factory=list)

    @property
    def mean_window_temp(self) -> float:
        """Moyenne du ressenti sur la fenêtre [hour_start, hour_end)."""
        h_start = settings.garderobe_hour_start
        h_end = settings.garderobe_hour_end
        window = [h for h in self.hourly if h_start <= h.hour < h_end]
        if not window:
            return (self.temp_min + self.temp_max) / 2
        return sum(h.apparent_temp for h in window) / len(window)

    @property
    def pluie(self) -> bool:
        d = self.desc.lower()
        return self.precip > 0.5 or any(
            w in d for w in ("rain", "pluie", "drizzle", "shower")
        )

    @property
    def snow(self) -> bool:
        d = self.desc.lower()
        return any(w in d for w in ("snow", "neige", "blizzard"))

    def to_dict(self) -> dict:
        return {
            "temp": self.temp,
            "feels": self.feels,
            "temp_min": self.temp_min,
            "temp_max": self.temp_max,
            "humidity": self.humidity,
            "wind": self.wind,
            "precip": self.precip,
            "desc": self.desc,
            "icon": self.icon,
            "source": self.source,
            "pluie": self.pluie,
            "snow": self.snow,
            "mean_window_temp": self.mean_window_temp,
            "hour_window": [
                settings.garderobe_hour_start,
                settings.garderobe_hour_end,
            ],
            "hourly": [h.to_dict() for h in self.hourly],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_OPEN_METEO_CODE_DESC = {
    0: "Ciel dégagé", 1: "Principalement clair", 2: "Partiellement nuageux", 3: "Couvert",
    45: "Brouillard", 48: "Brouillard givrant",
    51: "Bruine légère", 53: "Bruine", 55: "Bruine forte",
    61: "Pluie légère", 63: "Pluie", 65: "Pluie forte",
    71: "Neige légère", 73: "Neige", 75: "Neige forte",
    77: "Grésil",
    80: "Averses légères", 81: "Averses", 82: "Averses violentes",
    85: "Averses de neige", 86: "Fortes averses de neige",
    95: "Orage", 96: "Orage avec grêle", 99: "Orage violent avec grêle",
}


def _derive_icon(desc: str, precip: float) -> str:
    d = desc.lower()
    if any(w in d for w in ("snow", "neige", "blizzard")):
        return "🌨️"
    if precip > 0.5 or any(w in d for w in ("rain", "pluie", "drizzle", "shower", "averse")):
        return "🌧️"
    if any(w in d for w in ("sunny", "clear", "dégagé")):
        return "☀️"
    return "🌤️"


# ─────────────────────────────────────────────────────────────────────────────
# Providers
# ─────────────────────────────────────────────────────────────────────────────

class WeatherProvider(ABC):
    name: str

    @abstractmethod
    def fetch(self, lat: float, lon: float) -> WeatherData: ...


class OpenWeatherProvider(WeatherProvider):
    name = "openweather"
    BASE = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str, timezone: str = "America/Montreal"):
        self.api_key = api_key
        self.tz = ZoneInfo(timezone)

    def fetch(self, lat: float, lon: float) -> WeatherData:
        with httpx.Client(timeout=10.0) as client:
            cur_r = client.get(
                f"{self.BASE}/weather",
                params={
                    "lat": lat, "lon": lon,
                    "appid": self.api_key,
                    "units": "metric", "lang": "fr",
                },
            )
            cur_r.raise_for_status()
            cur = cur_r.json()

            fc_r = client.get(
                f"{self.BASE}/forecast",
                params={
                    "lat": lat, "lon": lon,
                    "appid": self.api_key,
                    "units": "metric", "lang": "fr",
                },
            )
            fc_r.raise_for_status()
            fc = fc_r.json()

        temp = float(cur["main"]["temp"])
        feels = float(cur["main"]["feels_like"])
        humidity = float(cur["main"]["humidity"])
        wind_ms = float(cur.get("wind", {}).get("speed", 0.0))
        wind = wind_ms * 3.6  # m/s → km/h
        precip = float(cur.get("rain", {}).get("1h", 0.0))
        desc = ""
        if cur.get("weather"):
            desc = cur["weather"][0].get("description", "")

        # Série horaire d'aujourd'hui (forecast step 3h → on garde les points)
        now_local = dt.datetime.now(self.tz)
        today = now_local.date()
        hourly: list[HourlyTemp] = []
        temp_min = temp
        temp_max = temp
        for entry in fc.get("list", []):
            ts = dt.datetime.fromtimestamp(entry["dt"], tz=dt.timezone.utc).astimezone(self.tz)
            if ts.date() != today:
                continue
            t = float(entry["main"]["temp"])
            ft = float(entry["main"].get("feels_like", t))
            hourly.append(HourlyTemp(hour=ts.hour, temp=t, apparent_temp=ft))
            temp_min = min(temp_min, t)
            temp_max = max(temp_max, t)

        # Si forecast vide pour aujourd'hui (rare, late evening), on tente demain
        if not hourly:
            tomorrow = today + dt.timedelta(days=1)
            for entry in fc.get("list", []):
                ts = dt.datetime.fromtimestamp(entry["dt"], tz=dt.timezone.utc).astimezone(self.tz)
                if ts.date() != tomorrow:
                    continue
                t = float(entry["main"]["temp"])
                ft = float(entry["main"].get("feels_like", t))
                hourly.append(HourlyTemp(hour=ts.hour, temp=t, apparent_temp=ft))

        hourly.sort(key=lambda h: h.hour)

        # Fallback temp_min/temp_max sur le current si forecast vide
        if temp_min == temp and temp_max == temp:
            temp_min = float(cur["main"].get("temp_min", temp))
            temp_max = float(cur["main"].get("temp_max", temp))

        return WeatherData(
            temp=temp,
            feels=feels,
            temp_min=temp_min,
            temp_max=temp_max,
            humidity=humidity,
            wind=wind,
            precip=precip,
            desc=desc,
            icon=_derive_icon(desc, precip),
            source=self.name,
            hourly=hourly,
        )


class OpenMeteoProvider(WeatherProvider):
    name = "open-meteo"
    URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timezone: str = "America/Montreal"):
        self.timezone = timezone
        self.tz = ZoneInfo(timezone)

    def fetch(self, lat: float, lon: float) -> WeatherData:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
            "hourly": "temperature_2m,apparent_temperature",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": self.timezone,
            "forecast_days": 1,
        }
        with httpx.Client(timeout=10.0) as client:
            r = client.get(self.URL, params=params)
            r.raise_for_status()
            data = r.json()

        cur = data["current"]
        daily = data["daily"]
        hourly_raw = data["hourly"]

        temp = float(cur["temperature_2m"])
        feels = float(cur["apparent_temperature"])
        humidity = float(cur["relative_humidity_2m"])
        wind = float(cur["wind_speed_10m"])
        precip = float(cur["precipitation"])
        wcode = int(cur.get("weather_code", 0))
        desc = _OPEN_METEO_CODE_DESC.get(wcode, f"code {wcode}")

        hourly: list[HourlyTemp] = []
        now_local = dt.datetime.now(self.tz)
        today = now_local.date()
        times = hourly_raw["time"]
        temps = hourly_raw["temperature_2m"]
        apparent = hourly_raw["apparent_temperature"]
        for i, t_str in enumerate(times):
            # Open-Meteo retourne les timestamps en heure locale quand on passe `timezone`
            t_dt = dt.datetime.fromisoformat(t_str).replace(tzinfo=self.tz)
            if t_dt.date() != today:
                continue
            hourly.append(
                HourlyTemp(
                    hour=t_dt.hour,
                    temp=float(temps[i]),
                    apparent_temp=float(apparent[i]),
                )
            )
        hourly.sort(key=lambda h: h.hour)

        return WeatherData(
            temp=temp,
            feels=feels,
            temp_min=float(daily["temperature_2m_min"][0]),
            temp_max=float(daily["temperature_2m_max"][0]),
            humidity=humidity,
            wind=wind,
            precip=precip,
            desc=desc,
            icon=_derive_icon(desc, precip),
            source=self.name,
            hourly=hourly,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cache + API publique
# ─────────────────────────────────────────────────────────────────────────────

_cache: dict[tuple[float, float], tuple[float, WeatherData]] = {}


def _select_primary_provider() -> WeatherProvider:
    if settings.openweather_api_key:
        return OpenWeatherProvider(settings.openweather_api_key, settings.timezone)
    return OpenMeteoProvider(settings.timezone)


def get_weather(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    *,
    force_refresh: bool = False,
) -> WeatherData:
    """Retourne la météo (cachée 30 min) pour les coordonnées données.

    Coordonnées par défaut = Montréal (depuis settings).
    """
    lat = lat if lat is not None else settings.garderobe_lat
    lon = lon if lon is not None else settings.garderobe_lon
    key = (round(lat, 4), round(lon, 4))
    now = time.time()

    if not force_refresh and key in _cache:
        ts, cached = _cache[key]
        if now - ts < settings.garderobe_weather_cache_ttl:
            return cached

    primary = _select_primary_provider()
    try:
        data = primary.fetch(lat, lon)
    except Exception as e:  # pragma: no cover - dépend du réseau
        logger.warning("Weather provider %s failed: %s — fallback Open-Meteo", primary.name, e)
        if isinstance(primary, OpenMeteoProvider):
            raise
        try:
            data = OpenMeteoProvider(settings.timezone).fetch(lat, lon)
        except Exception:
            raise

    _cache[key] = (now, data)
    return data


def clear_cache() -> None:
    """Utile pour les tests."""
    _cache.clear()
