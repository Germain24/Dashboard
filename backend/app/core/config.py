"""Configuration centralisée (Pydantic Settings).

Toutes les variables d'environnement passent par ici. Charge `.env` à la racine
du repo en dev, mais les variables d'environnement réelles prévalent toujours.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du repo : mission-control/  (backend/ -> .. -> root)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Paramètres applicatifs lus depuis l'environnement (et `.env`)."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "mission-control"
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_log_level: str = "INFO"
    # Format des logs : "text" (défaut, lisible) ou "json" (agrégation/observabilité).
    log_format: str = "text"

    # Préfixe de version de l'API. Les routes principales sont exposées sous
    # ce préfixe ; un montage racine (non documenté) est conservé pour la
    # rétro-compatibilité durant la transition.
    api_v1_prefix: str = "/api/v1"

    # --- DB ---
    # URL SQLite par défaut. Le chemin est résolu par rapport au backend/.
    database_url: str = Field(default="sqlite:///../data/mission-control.db")

    # --- Localisation ---
    timezone: str = "America/Montreal"
    locale: str = "fr-CA"

    # --- CORS ---
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Google Calendar (Agenda #83, OAuth) ---
    # Identifiants OAuth « installed app ». Obtenus via la console Google Cloud,
    # le refresh_token via scripts/google_oauth_setup.py. Vides = intégration
    # désactivée (le module agenda fonctionne sans).
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_calendar_id: str = "primary"

    # --- Garde-robe (CONV 2) ---
    openweather_api_key: str = ""
    garderobe_lat: float = 45.5017
    garderobe_lon: float = -73.5673
    garderobe_hour_start: int = 7
    garderobe_hour_end: int = 23
    garderobe_weather_cache_ttl: int = 1800

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    @property
    def data_dir(self) -> Path:
        return REPO_ROOT / "data"

    @property
    def imports_dir(self) -> Path:
        return self.data_dir / "imports"


settings = Settings()
