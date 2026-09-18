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
    # Sauvegardes séparées du dépôt pour ne pas remplir son dossier data.
    # Le job échoue explicitement si le NAS n'est pas monté, sans repli local.
    backup_dir: str = "Z:/BackUp/mission-control"

    # --- Localisation ---
    timezone: str = "America/Montreal"
    locale: str = "fr-CA"

    # --- CORS ---
    # Origines, méthodes et en-têtes explicites (pas de wildcard "*") — #191.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_headers: str = "Content-Type,Authorization,X-Requested-With"
    # En dev, le port du frontend Next peut glisser (3000 occupé -> 3001, 3002…).
    # On autorise donc tout localhost/127.0.0.1 sur n'importe quel port, ce qui
    # évite les preflight CORS 400 quand le port change. Mettre "" pour désactiver
    # (prod : l'origine reste contrôlée par cors_origins).
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

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
    # Dossier inventaire géré à la main (Vetements.xlsx + Pixelisé/ + Normal/),
    # lu par POST /garderobe/inventaire/sync et scripts/import_garderobe_inventaire.
    garderobe_inventaire_dir: str = r"C:\Users\germa\Desktop\Vetements"

    # --- Voyage ---
    # Recherche de vols datés. Vide = estimations locales clairement signalées.
    duffel_api_key: str = ""
    voyage_live_price_cache_hours: int = 12
    voyage_max_live_itineraries: int = 5

    # ── Réglages métier ajustables (override .env) ──────────────────────
    # Finance — score Buffett & valorisation
    # Score d'achat minimal des ACTIONS. Les ETF y échappent (score conventionnel
    # >= 200), tout comme les tickers forcés. Fixé à 85 le 2026-08-18 : sur la
    # run 57, le filtre complet score + valorisation + liquidité passe ainsi de
    # 15 à 49 actions, sans imposer de poche minimale au portefeuille final.
    buffett_score_threshold: float = 85.0       # Qualité Buffett V3 minimale
    buffett_per_max: float = 40.0               # PER maximal toléré
    buffett_peg_max: float = 1.0                # PEG maximal toléré
    buffett_taux_defaut: float = 0.04           # taux obligataire par défaut
    # Finance — optimiseur d'allocation
    buffett_sharpe_target_percent: float = 0.90
    # Actions entières : aucune part minimale en pourcentage. La contrainte
    # réelle est appliquée plus tard par la discrétisation : au moins 1 action
    # si le budget permet d'en acheter une. Trading 212 garde son propre
    # plancher local de 1 % du pie dans Config.STARR_MIN_T212_PIE_PCT.
    buffett_min_allocation_threshold: float = 0.0
    buffett_n_multistart: int = 5
    buffett_dedup_fuzzy_threshold: float = 0.80
    # Exclure de l'analyse les titres présents dans ToutBroker.xlsx dont TOUS les
    # brokers sont explicitement Faux (cellule vide ≠ Faux). Tout le reste est analysé.
    buffett_exclude_unavailable: bool = True
    # Compatibilité de configuration historique (désormais dépréciée).
    buffett_max_requests_per_minute: int = 2000
    # Quota réel Yahoo : 2 000 requêtes HTTP par heure, soit 1,8 s minimum
    # entre deux départs de requêtes, tous modules Finance confondus.
    buffett_yahoo_requests_per_hour: int = 2000
    buffett_rate_limit_max_pause_sec: float = 60.0
    # Une poignée de symboles Yahoo peuvent échouer éternellement tout en
    # émettant bien une requête. Borner les passes empêche un run figé à 99,9 %.
    buffett_max_transient_retry_passes: int = 3
    # Rotation d'IP : liste de proxys séparés par des virgules (ex.
    # "http://user:pass@host:port,http://host2:port"). La session yfinance en
    # choisit un au hasard à chaque (ré)ouverture — utile quand Yahoo bloque
    # l'IP. Vide = connexion directe (défaut). Pilotable via .env (YF_PROXIES).
    yf_proxies: str = ""
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

    # --- TMDB (Films & Séries) ---
    # Clé API TMDB pour enrichir la watchlist. Vide = mode manuel sans métadonnées.
    # Obtenir sur https://www.themoviedb.org/settings/api
    tmdb_api_key: str = ""

    # --- API Trading 212 (v0, compte Invest) ---
    # Authentification HTTP Basic `keyId:secret` (Settings > API (Beta) : le
    # secret n'est affiché qu'à la création). Le header `Authorization: <clé>`
    # de certains exemples de la doc renvoie 401 : il faut bien le couple.
    # Vides = les intégrations Trading 212 retombent sur les relevés PDF/CSV.
    trading212_key_id: str = ""
    trading212_secret: str = ""
    trading212_base_url: str = "https://live.trading212.com"

    # --- Kraken + portefeuilles MetaMask (lecture seule) ---
    # Les secrets Kraken restent exclusivement dans `.env`. La clé doit avoir
    # uniquement les droits de lecture (fonds, ledger et trades clôturés).
    kraken_api_key: str = ""
    kraken_api_secret: str = ""
    kraken_base_url: str = "https://api.kraken.com"
    metamask_ethereum_address: str = ""
    metamask_bitcoin_address: str = ""
    metamask_gnosis_address: str = ""
    ethereum_blockscout_url: str = "https://eth.blockscout.com"
    gnosis_blockscout_url: str = "https://gnosis.blockscout.com"
    mempool_base_url: str = "https://mempool.space/api"
    realt_performance_base_url: str = "https://performance.realtoken.community"
    rmm_analytics_base_url: str = "https://analytics.rmm.realtoken.community"
    external_accounts_refresh_seconds: int = 300

    # --- API DeepSeek (classement et découverte musicale) ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    musique_deepseek_model: str = "deepseek-chat"

    # --- Musique : bibliothèque Qobuz haute qualité + source MP3 basse qualité ---
    music_dir: str = "Z:/Musique/Qobuz"
    music_tele_dir: str = "Z:/Musique/Musique Tele"
    walkman_dir: str = "D:/MUSIC"
    # Budget — seuils d'alerte d'enveloppe (% du budget consommé)
    budget_envelope_warning_pct: float = 80.0
    budget_envelope_over_pct: float = 100.0

    # Scheduler — rétention pour la purge (#172)
    jobrun_retention_days: int = 30        # JobRun plus vieux supprimés
    notification_retention_days: int = 30  # notifications LUES plus vieilles supprimées
    # Notifications NON LUES : conservées bien plus longtemps (l'utilisateur ne
    # les a pas vues), mais plus indéfiniment -- sinon rien n'est jamais purgé et
    # la table croît sans fin (audit §3.E : 1 419 non lues, la plus ancienne du
    # 2026-06-17).
    notification_unread_retention_days: int = 90
    # 0 conserve tous les snapshots quotidiens sur le NAS ; une valeur positive
    # limite leur nombre si une rotation est souhaitée plus tard.
    backup_retention_count: int = 0

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
