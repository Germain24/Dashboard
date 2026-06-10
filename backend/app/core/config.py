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
    # Origines, méthodes et en-têtes explicites (pas de wildcard "*") — #191.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_headers: str = "Content-Type,Authorization,X-Requested-With"

    # --- Google Calendar (Agenda #83, OAuth) ---
    # Identifiants OAuth « installed app ». Obtenus via la console Google Cloud,
    # le refresh_token via scripts/google_oauth_setup.py. Vides = intégration
    # désactivée (le module agenda fonctionne sans).
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_calendar_id: str = "primary"

    # --- Calendriers iCal externes (Agenda) ---
    # URLs .ics à re-synchroniser automatiquement (ex. Agendrix). Plusieurs URLs
    # séparées par des virgules. Vide = synchro auto désactivée.
    ical_sync_urls: str = ""

    @property
    def ical_sync_url_list(self) -> list[str]:
        return [u.strip() for u in self.ical_sync_urls.split(",") if u.strip()]

    # --- Garde-robe (CONV 2) ---
    openweather_api_key: str = ""
    garderobe_lat: float = 45.5017
    garderobe_lon: float = -73.5673
    garderobe_hour_start: int = 7
    garderobe_hour_end: int = 23
    garderobe_weather_cache_ttl: int = 1800

    # ── Réglages métier ajustables (override .env) ──────────────────────
    # Finance — score Buffett & valorisation
    buffett_score_threshold: float = 80.0       # score d'achat minimal
    buffett_per_max: float = 40.0               # PER maximal toléré
    buffett_peg_max: float = 1.0                # PEG maximal toléré
    buffett_taux_defaut: float = 0.04           # taux obligataire par défaut
    # Finance — optimiseur d'allocation
    buffett_sharpe_target_percent: float = 0.90
    buffett_min_allocation_threshold: float = 0.01
    buffett_n_multistart: int = 5
    buffett_dedup_fuzzy_threshold: float = 0.80
    # Exclure de l'analyse les titres présents dans ToutBroker.xlsx dont TOUS les
    # brokers sont explicitement Faux (cellule vide ≠ Faux). Tout le reste est analysé.
    buffett_exclude_unavailable: bool = True
    # Plafond de requêtes yfinance par heure (anti-ban) + requêtes par ticker.
    buffett_max_requests_per_hour: int = 2000
    buffett_requests_per_ticker: int = 4
    # Finance — alertes
    finance_rebalance_alert_pct: float = 5.0    # écart de poids déclenchant l'alerte
    finance_snapshot_drop_alert_pct: float = 5.0  # chute quotidienne alertée

    # Santé — optimisation nutritionnelle
    sante_maintenance_kcal_per_kg: float = 32.0  # maintenance = poids × ce facteur
    sante_surplus_kcal_sport: float = 500.0      # surplus calorique un jour de sport
    sante_rest_factor: float = 1.1               # facteur jours de repos

    # Entraînement — repères de volume (séries/sem par muscle) + mésocycle
    entrainement_sets_mev: int = 10              # Minimum Effective Volume
    entrainement_sets_mrv: int = 20              # Maximum Recoverable Volume
    entrainement_mesocycle_accumulation_weeks: int = 4

    # --- Musique (module playlists par ambiance) ---
    music_dir: str = "C:/Users/germa/Music"
    musique_ollama_host: str = "http://localhost:11434"
    musique_ollama_model: str = "qwen2.5-coder:1.5b"
    musique_ollama_autostart: bool = True  # démarrer `ollama serve` au boot si absent

    # Budget — seuils d'alerte d'enveloppe (% du budget consommé)
    budget_envelope_warning_pct: float = 80.0
    budget_envelope_over_pct: float = 100.0

    # Scheduler — rétention pour la purge (#172)
    jobrun_retention_days: int = 30        # JobRun plus vieux supprimés
    notification_retention_days: int = 30  # notifications LUES plus vieilles supprimées
    backup_retention_count: int = 14       # nombre de backups DB conservés (#176)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_methods_list(self) -> list[str]:
        return [m.strip() for m in self.cors_methods.split(",") if m.strip()]

    @property
    def cors_headers_list(self) -> list[str]:
        return [h.strip() for h in self.cors_headers.split(",") if h.strip()]

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
