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

    # --- Robot / IA (CONV N) ---
    # Clé API Claude. Vide = module robot en lecture seule (chat désactivé,
    # dégradation propre). Voir https://console.anthropic.com.
    anthropic_api_key: str = ""
    robot_model: str = "claude-opus-4-8"        # modèle Claude par défaut (#161)
    robot_effort: str = "medium"                 # low | medium | high | max (#161)
    robot_max_tokens: int = 4096                  # plafond de tokens par réponse
    robot_system_prompt: str = ""                 # override optionnel du prompt système

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

    # Budget — seuils d'alerte d'enveloppe (% du budget consommé)
    budget_envelope_warning_pct: float = 80.0
    budget_envelope_over_pct: float = 100.0

    # Scheduler — rétention pour la purge (#172)
    jobrun_retention_days: int = 30        # JobRun plus vieux supprimés
    notification_retention_days: int = 30  # notifications LUES plus vieilles supprimées

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
