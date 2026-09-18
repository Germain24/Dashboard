import type { Weather } from "@/lib/garderobe";

export function WeatherBanner({ weather, meanTemp }: { weather: Weather; meanTemp: number }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 flex items-center gap-4">
      <div className="text-4xl">{weather.icon}</div>
      <div className="flex-1">
        <div className="text-base font-semibold">
          Montréal — {weather.temp.toFixed(1)}°C{" "}
          <span className="text-sm text-[var(--muted-foreground)]">
            (ressenti {weather.feels.toFixed(1)}°C)
          </span>
        </div>
        <div className="text-xs text-[var(--muted-foreground)] capitalize">
          {weather.desc} · Hum. {weather.humidity}% · Vent {weather.wind.toFixed(0)} km/h
        </div>
        <div className="mt-1 text-xs text-[var(--muted-foreground)]">
          Source : {weather.source} · Moyenne {weather.hour_window[0]}h–{weather.hour_window[1]}h :{" "}
          <span className="font-medium text-[var(--foreground)]">
            {meanTemp.toFixed(1)}°C
          </span>
          {weather.pluie ? " · 🌧 Pluie" : ""}
          {weather.snow ? " · ❄️ Neige" : ""}
        </div>
      </div>
    </div>
  );
}
