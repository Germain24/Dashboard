"""Configuration Buffett — paramètres chargés depuis params.json + valeurs par défaut."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.core.config import settings
from app.services.finance.buffett.bond_yields import STATIC_BOND_YIELDS


class Config:
    # Chemins. Les fichiers FOURNIS par l'utilisateur sont rangés sous
    # data/imports/<Catégorie>/<Type>/ (cf. #6). Les fichiers de cache/runtime
    # restent sous data/ (non fournis par l'utilisateur).
    _IMPORTS_FIN = settings.imports_dir / "Finances"
    DATA_DIR: str = str(settings.data_dir)
    FOLDER_PATH: str = os.path.join("data", "financials_by_company")  # cache runtime
    CACHE_FILE: str = os.path.join("data", "cache_status.json")        # cache runtime
    # Fichiers d'entrée (Finances) — rangés data/imports/Finances/<type>/
    TICKERS_CSV: str = str(_IMPORTS_FIN / "variables" / "tickers.csv")
    PARAMS_FILE: str = str(_IMPORTS_FIN / "variables" / "params.json")
    # Disponibilite par broker + scores + Poids (colonnes Tradding 212, Bourse
    # Direct, Bourse Direct 2, IBKR... + Chance MOAT). find_broker_file teste
    # plusieurs emplacements au chargement.
    BROKER_FILE: str = str(_IMPORTS_FIN / "tableur" / "ToutBroker.xlsx")

    # Limites analyse -- fenetre cible : MIN_AGE_YEARS <= age <= MAX_AGE_YEARS
    MIN_AGE_YEARS: int = 1   # < 1 an : pas de nouveau rapport annuel possible
    MAX_AGE_YEARS: int = 2   # > 2 ans : probablement deliste
    # Réglages pilotables par .env (cf. app.core.config.Settings).
    SCORE_THRESHOLD: float = settings.buffett_score_threshold
    MAX_REQUESTS_PER_HOUR: int = settings.buffett_max_requests_per_hour
    REQUESTS_PER_TICKER: int = settings.buffett_requests_per_ticker
    # Pause max (s) quand le quota horaire est atteint (borne anti-attente longue).
    RATE_LIMIT_MAX_PAUSE_SEC: float = settings.buffett_rate_limit_max_pause_sec

    # Filtres valorisation
    PER_MAX: float = settings.buffett_per_max
    PEG_MAX: float = settings.buffett_peg_max
    TAUX_DEFAUT: float = settings.buffett_taux_defaut

    # Valeurs de repli ; rafraîchies en direct au lancement du run (cf.
    # bond_yields.get_bond_yields appelé dans runner.run_buffett_analysis).
    TAUX_OBLIGATAIRES: dict = dict(STATIC_BOND_YIELDS)

    # Optimiseur
    SHARPE_TARGET_PERCENT: float = settings.buffett_sharpe_target_percent
    MIN_ALLOCATION_THRESHOLD: float = settings.buffett_min_allocation_threshold
    # Liquidité : volume minimum échangé/jour (€) pour qu'un titre soit éligible à
    # l'allocation (volume actions × prix). Surchargage possible via params.json.
    # 100k : assez bas pour les ETF obligataires d'État (volume d'écran faible mais
    # très liquides), assez haut pour écarter les micro-actions illiquides.
    MIN_VOLUME_EUR: float = 100_000.0
    # STARR (objectif d'optimisation centré sur les grosses chutes) :
    STARR_ALPHA: float = 0.05          # niveau CVaR (5 % des pires cas)
    STARR_N_SIM: int = 20_000          # scénarios Monte-Carlo (copule de Vine)
    # Scénarios utilisés PENDANT la recherche DE (sous-échantillon des STARR_N_SIM,
    # en float32) : suffisant pour comparer des candidats entre eux. Le score final
    # est recalculé sur les STARR_N_SIM scénarios complets en float64.
    STARR_N_SIM_SEARCH: int = 8_000
    STARR_DOWNSIDE_WEIGHT: float = 1.0  # λ : poids de la variance baissière (Sortino)
    # Trois régimes historiques sont simulés séparément puis concaténés.
    # La fenêtre 3 ans reste centrale ; 1 an capte le régime récent et 5 ans
    # apporte les épisodes plus anciens. Une fenêtre n'est utilisée que si au
    # moins 90 % de ses séances sont disponibles, puis les poids sont renormalisés.
    STARR_REGIME_WINDOWS: list = [
        {"label": "1y", "days": 252, "weight": 0.25},
        {"label": "3y", "days": 756, "weight": 0.50},
        {"label": "5y", "days": 1260, "weight": 0.25},
    ]
    STARR_REGIME_MIN_COVERAGE: float = 0.90
    # Le rendement espéré (numérateur STARR) reste volontairement centré
    # sur 3 ans ; l'estimation 1 an serait beaucoup trop volatile.
    STARR_MEAN_WINDOW_DAYS: int = 756
    # Malus exponentiel au-delà du plafond de positions : pousse l'optimiseur à
    # regrouper les ETF redondants (même indice) et limiter les micro-lignes, sans
    # supprimer d'ETF (respecte la dispo broker). penalty = exp(β·(n_lignes−max))−1.
    # Le plafond est exprimé PAR BROKER actif : max = STARR_MAX_LINES_PER_BROKER × n
    # (ex. 20/broker → 40 lignes à 2 brokers, 60 à 3 quand IBKR sera ajouté).
    STARR_MAX_LINES_PER_BROKER: int = 20
    STARR_CARD_BETA: float = 0.15
    # Arrêt du Differential Evolution : PAS de plafond de générations comme critère
    # normal — le DE s'arrête quand sa population converge (écart-type des scores
    # <= tol, cf. DifferentialEvolutionSolver.converged()), avec un minimum de
    # générations pour éviter une convergence prématurée (population encore peu
    # diversifiée après quelques générations seulement). STARR_DE_MAX_GENERATIONS
    # n'est qu'un garde-fou anti-boucle-infinie (paysage pathologique qui ne
    # convergerait jamais) ; s'il est atteint, c'est loggé comme une anomalie.
    # Relevé à 50 000 (au lieu de 2000) pour rester purement défensif : jamais le
    # critère d'arrêt normal en pratique.
    STARR_DE_MIN_GENERATIONS: int = 30
    STARR_DE_MAX_GENERATIONS: int = 50_000
    # Un seed qui n'améliore plus réellement le score est abandonné au lieu de
    # consommer des milliers de générations identiques. Plusieurs seeds bornés
    # gardent l'exploration reproductible sans boucle infinie.
    STARR_DE_STAGNATION_GENERATIONS: int = 250
    STARR_DE_MIN_IMPROVEMENT: float = 1e-6
    STARR_DE_MAX_SEEDS: int = 1
    # Tolérance de convergence (écart-type des scores de la population / |moyenne|
    # <= tol). Choix délibéré de garder 1e-6 (précision maximale) malgré le coût :
    # sur un cas de test à 29 titres, la convergence naturelle demande ~730
    # générations (~144s/seed).
    STARR_DE_TOL: float = 1e-6
    # Budget d'itérations du polish local gradient-free (Nelder-Mead) en fin de DE.
    STARR_DE_POLISH_MAXITER: int = 300
    # Taille TOTALE de la population DE (init custom passée au solver). Sans init
    # custom, scipy multiplierait popsize par le nombre de dimensions : à 1250
    # titres cela faisait 15 000 individus évalués PAR GÉNÉRATION. La population
    # peut dépasser ce nombre si la couverture de l'univers l'exige (chaque titre
    # doit apparaître dans au moins un individu, cf. build_init_population).
    STARR_DE_POPSIZE: int = 515
    # Avant de lancer le DE, évalue des lots de portefeuilles 100 % aléatoires
    # jusqu'à obtenir un objectif pénalisé strictement positif. Le plafond évite
    # une boucle infinie si les données ou contraintes rendent cela impossible.
    STARR_DE_POSITIVE_INIT_BATCH_SIZE: int = 256
    STARR_DE_POSITIVE_INIT_MAX_BATCHES: int = 200
    # Ticker imposé comme individu de départ « 1 seule ligne » (ex. un ETF monde) ;
    # vide = ETF au meilleur score standalone, à défaut meilleur titre standalone.
    STARR_DE_SEED_TICKER: str = ""
    # Plafond de poids par ACTION (filet anti « tout sur un titre »). Les ETF en sont
    # EXEMPTÉS : un ETF est déjà diversifié, donc un gros poids n'est pas un risque de
    # concentration sur un sous-jacent unique.
    MAX_POSITION_PCT: float = 0.15
    # Contraintes look-through (feuilles ETF_Defensif / ETF_Pays) :
    MIN_DEFENSIVE_PCT: float = 0.30    # min du portefeuille en défensif (look-through)
    MAX_COUNTRY_PCT: float = 0.25      # max par pays (look-through ; métaux exemptés)
    CONSTRAINT_PENALTY: float = 100.0  # raideur des pénalités (quadratiques ; ↑ = plus strict)
    N_MULTISTART: int = settings.buffett_n_multistart
    USE_BROKER_CONSTRAINTS: bool = True
    # Seuil de corrélation (rendements convertis EUR) au-delà duquel deux ETF sont
    # des « jumeaux d'indice » -> on retire le moins liquide. Décision utilisateur
    # 2026-07-13 : 0,95, et la règle ne s'applique QU'ENTRE ETF — une ACTION n'est
    # jamais retirée pour cause de corrélation (ni fusionnée avec un ETF) : deux
    # entreprises corrélées restent deux entreprises distinctes. Ajustable via
    # params.json.
    CORRELATION_DEDUP_THRESHOLD: float = 0.95
    # Présélection avant STARR : l'optimiseur final conserve 20 lignes maximum
    # par broker, donc 50 ETF candidats apportent assez de choix sans laisser des
    # centaines de fonds redondants exploser le coût du DE.
    ETF_MAX_CANDIDATES_PER_BROKER: int = 50
    ETF_SELECTION_CORRELATION_DAYS: int = 756
    # Régularisation des corrélations vers la corrélation moyenne : stabilise les
    # valeurs extrêmes, particulièrement quand le nombre de titres est élevé.
    STARR_CORRELATION_SHRINKAGE: float = 0.15
    # Le signal de rendement historique est ramené vers la moyenne transversale.
    # 0,25 = 25 % de moyenne propre au titre, 75 % de prior commun.
    STARR_MEAN_SIGNAL_WEIGHT: float = 0.25
    # Scénarios de stress ajoutés au mélange historique sans augmenter N_SIM.
    STARR_STRESS_WEIGHT: float = 0.10
    STARR_STRESS_VOL_MULTIPLIER: float = 2.0
    STARR_STRESS_EQUITY_CORRELATION: float = 0.85
    # Benchmark de reference : le score mesure l'ecart A CE TITRE. Il n'appartient
    # PAS a l'univers d'optimisation (select_etfs_per_broker l'ecarte) : ses
    # rendements sont injectes par le runner. Cf. la spec du 2026-07-21.
    STARR_BENCHMARK_TICKER: str = "CW8.PA"
    REBALANCES_PER_YEAR: int = 4
    TRANSACTION_COSTS_ENABLED: bool = True
    # Frais brokers applicables aux ordres de rebalancement (tarifs BD au
    # 06-01-2026 ; Trading 212 communiqué par l'utilisateur).
    TRADING212_FX_FEE_RATE: float = 0.0015
    BOURSE_DIRECT_FX_FEE_RATE: float = 0.0008
    BOURSE_DIRECT_FOREIGN_CUSTODY_RATE: float = 0.00036
    FRENCH_TRANSACTION_TAX_RATE: float = 0.004
    # La TTF ne concerne qu'une liste légale d'actions françaises, jamais tous
    # les titres `.PA`. À renseigner via params.json ou colonne `TTF` du tableur.
    FRENCH_TTF_TICKERS: list = []
    # Historique de cours minimal (jours de bourse) pour entrer dans l'optimisation.
    # Sans ce filtre, un seul fonds récent (lancé il y a quelques semaines) tronque
    # la fenêtre COMMUNE de rendements de tout l'univers (le dropna aligne tout le
    # monde sur le plus jeune) -> corrélations et STARR calculés sur quelques
    # semaines au lieu de 5 ans (#bug rapporté : ETF assurance fusionné avec
    # l'action Adobe à corr 0,96, EEM absorbé par EWY...).
    STARR_MIN_HISTORY_DAYS: int = 756
    BUDGET_BROKERS: dict = {
        "Trading212": 733.70,
        "BoursDirect": 0.0,
        "BoursDirect2": 24472.0,
    }

    # Copule
    VINE_TRUNC_HIGH: float = 20.0
    VINE_FAMILY: str = "auto"
    # Au-delà de ce nombre de titres, la copule de Vine est remplacée par une
    # copule GAUSSIENNE sur la matrice de corrélation (Spearman) complète :
    # l'ajustement Vine est O(n²) taus de Kendall en boucle Python (~1 h à
    # 1250 titres, silencieux) alors que sa simulate() ne retenait de toute
    # façon qu'une matrice de corrélation CREUSE (les n-1 arêtes du chemin
    # D-vine) passée dans une gaussienne -- la gaussienne pleine est à la fois
    # ~100x plus rapide et plus riche en dépendances (#bug rapporté : run figé
    # à "seed 1, 0 générations").
    STARR_VINE_MAX_DIM: int = 150

    # Deduplication
    DEDUP_FUZZY_THRESHOLD: float = settings.buffett_dedup_fuzzy_threshold

    # Tickers forces (ex: ETF)
    FORCED_BUY_TICKERS: list = []

    @classmethod
    def load_params(cls) -> None:
        """Surcharge les valeurs depuis params.json s'il existe."""
        if not os.path.exists(cls.PARAMS_FILE):
            return
        try:
            with open(cls.PARAMS_FILE, encoding="utf-8") as f:
                params = json.load(f)
            for k, v in params.items():
                if hasattr(cls, k):
                    setattr(cls, k, v)
        except Exception as e:
            print(f"[Config] Erreur chargement {cls.PARAMS_FILE}: {e}")

    @classmethod
    def output_dir(cls) -> Path:
        return Path(cls.FOLDER_PATH)

    @classmethod
    def ensure_dirs(cls) -> None:
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.FOLDER_PATH, exist_ok=True)
