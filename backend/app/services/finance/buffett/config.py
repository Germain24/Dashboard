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
    ETF_REFERENCE_FILE: str = str(
        _IMPORTS_FIN / "variables" / "etf_reference.csv"
    )
    # Exports humains séparés. SQLite reste la source de vérité; les deux
    # classeurs ne mélangent plus les ratios d'actions avec les métadonnées ETF.
    BROKER_ACTIONS_FILE: str = str(
        _IMPORTS_FIN / "tableur" / "ToutBroker_Actions.xlsx"
    )
    BROKER_ETF_FILE: str = str(_IMPORTS_FIN / "tableur" / "ToutBroker_ETF.xlsx")
    # Alias de compatibilité pour les anciens scripts centrés sur les ETF.
    BROKER_FILE: str = BROKER_ETF_FILE

    # Limites analyse -- fenetre cible : MIN_AGE_YEARS <= age <= MAX_AGE_YEARS
    MIN_AGE_YEARS: int = 1   # < 1 an : pas de nouveau rapport annuel possible
    MAX_AGE_YEARS: int = 2   # > 2 ans : probablement deliste
    # Réglages pilotables par .env (cf. app.core.config.Settings).
    SCORE_THRESHOLD: float = settings.buffett_score_threshold
    SCORE_MIN_CONFIDENCE_PCT: float = 35.0
    MAX_REQUESTS_PER_MINUTE: int = settings.buffett_max_requests_per_minute
    YAHOO_REQUESTS_PER_HOUR: int = settings.buffett_yahoo_requests_per_hour
    RATE_LIMIT_MAX_PAUSE_SEC: float = settings.buffett_rate_limit_max_pause_sec

    # Filtres valorisation
    PER_MAX: float = settings.buffett_per_max
    PEG_MAX: float = settings.buffett_peg_max
    # Croissance retenue au dénominateur du PEG. La prévision d'analystes est
    # décotée (biais optimiste documenté) ; le plafond borne les CAGR aberrants.
    # Aucun PLANCHER : une croissance négative doit continuer d'exclure le titre.
    GROWTH_FORWARD_HAIRCUT: float = 0.85
    PEG_GROWTH_CAP: float = 0.25
    GROWTH_EXTREME: float = 0.50
    # Métrique de valorisation adaptée au secteur (P/FFO immobilier, PER
    # normalisé cyclique, PEG ajusté du dividende, P/B ÷ ROE). Passer à False
    # ramène tous les secteurs au couple PER/PEG, sans redéploiement.
    SECTOR_VALUATION_PROFILES_ENABLED: bool = True
    SECTOR_VALUATION_PROFILE_OVERRIDES: dict = {}
    # En dessous de cette couverture, le secteur retombe sur PER/PEG : une
    # médiane calculée sur 3 titres sur 25 rejetterait les 22 autres à tort.
    SECTOR_VALUATION_MIN_COVERAGE: float = 0.60
    NORMALIZED_EARNINGS_MIN_YEARS: int = 3
    NORMALIZED_EARNINGS_MAX_YEARS: int = 5
    DIVIDEND_YIELD_MAX_PCT: float = 15.0
    # Quantile retenu par secteur pour le signal d'achat. 0.50 = médiane
    # (historique) ; 0.40 ne garde que les 40 % les moins chers du secteur.
    BUY_SIGNAL_PERCENTILE: float = 0.40
    # Repli quand l'axe QUALITÉ (PEG) est indisponible : le titre est jugé sur le
    # seul axe VALORISATION, mais à un percentile plus SÉVÈRE — il doit être
    # nettement moins cher que la médiane de son secteur pour compenser le fait
    # que sa croissance n'est pas vérifiée.
    #
    # Sans ce repli, un PEG absent rejetait le titre sans appel. Mesuré sur
    # l'univers : 76 % des actions n'ont pas de PEG exploitable, et le manque est
    # très inégalement réparti — 92 % à Londres, 98 % à Munich, contre 50 % à
    # Varsovie. Le « signal Achat » devenait donc largement un signal de
    # DISPONIBILITÉ DE DONNÉES, amputant la diversification géographique de façon
    # systématique. Le repli ne dispense d'aucune autre règle : le titre doit
    # toujours avoir un PER positif et passer les plafonds sectoriels.
    #
    # 0.0 désactive le repli et restaure le rejet strict.
    BUY_SIGNAL_MISSING_QUALITY_PERCENTILE: float = 0.20
    TAUX_DEFAUT: float = settings.buffett_taux_defaut

    # Conservé pour la compatibilité des anciennes analyses. Le signal Achat
    # courant n'utilise plus de prime obligataire : aucun fetch FRED au run.
    TAUX_OBLIGATAIRES: dict = dict(STATIC_BOND_YIELDS)

    # Optimiseur
    SHARPE_TARGET_PERCENT: float = settings.buffett_sharpe_target_percent
    # Actions entières : pas de plancher global en pourcentage. La discrétisation
    # impose uniquement une unité achetable (au moins une action). Trading 212
    # conserve son plancher local de 1 % du pie ci-dessous.
    MIN_ALLOCATION_THRESHOLD: float = settings.buffett_min_allocation_threshold
    # Trading 212 travaille en points entiers dans un pie : une ligne active doit
    # représenter au moins 1 % du pie local, et non 1 % du portefeuille global.
    STARR_MIN_T212_PIE_PCT: float = 0.01
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
    # Crédit accordé quand le portefeuille est MOINS risqué que le benchmark.
    # Les termes de risque étaient strictement unilatéraux — `max(0, CVaR −
    # CVaR_bench)` — donc dépasser le risque de CW8 coûtait, mais descendre en
    # dessous ne rapportait rien : aucune incitation à réduire le risque, d'où des
    # portefeuilles agressifs. Le crédit rend le terme partiellement symétrique :
    #     terme = max(0, delta) − credit × max(0, −delta)
    # 0.0 reproduit EXACTEMENT l'ancien comportement (utile en test de
    # non-régression).
    #
    # ATTENTION à l'échelle : le crédit vaut `coefficient × écart de risque
    # ANNUALISÉ`, en points de %. Il est donc bien plus puissant qu'il n'y paraît.
    # Mesuré sur un actif à un quart du risque du benchmark, un coefficient de
    # 0,3 rapportait ~9,5 points — davantage que le score total d'un portefeuille
    # optimisé réel (~8 points) : de quoi faire passer un actif à faible rendement
    # de « clairement inférieur » à « équivalent », c'est-à-dire recréer la
    # pathologie de l'ETF monétaire à 96 % que la forme soustractive avait
    # corrigée. À 0,05 le crédit redevient un DÉPARTAGEUR (~1,5 point dans le même
    # cas) plutôt qu'un pilote de l'allocation.
    # Garde-fou : le portefeuille optimisé doit rester au-dessus du benchmark
    # nommé SGOV (cf. diagnostics `benchmarks`).
    STARR_RISK_REDUCTION_CREDIT: float = 0.05
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
    # Seuil conservé pour les diagnostics et la compatibilité des paramètres
    # historiques. Le malus de cardinalité est désactivé : la diversification
    # doit être arbitrée par STARR, les plafonds pays/région et le plafond par
    # position, pas par une taxe artificielle sur le nombre de lignes.
    STARR_MAX_LINES_PER_BROKER: int = 20
    STARR_CARD_BETA: float = 0.0
    # La Quality V3 reste un signal borné dans l'objectif, sans imposer une poche
    # actions : le meilleur portefeuille peut être 100 % ETF, 100 % actions ou mixte.
    STARR_DIRECT_ACTION_QUALITY_BONUS: float = 0.50
    # Pour les actions, aucune troncature de cardinalité n'est imposée par un
    # pourcentage : la discrétisation conserve seulement les lignes pour
    # lesquelles une action entière est achetable. Pour T212, la granularité
    # du pie limite naturellement à 100 lignes de 1 %.
    # Le score, lui, ne comporte plus de malus lié au nombre de lignes.
    # Arrêt du Differential Evolution : PAS de plafond de générations comme critère
    # normal — le DE s'arrête après le plateau chaud défini plus bas, jamais sur
    # la dispersion interne de scipy. STARR_DE_MAX_GENERATIONS n'est qu'un
    # garde-fou anti-boucle-infinie (paysage pathologique qui ne convergerait
    # jamais) ; s'il est atteint, c'est loggé comme une anomalie.
    # Relevé à 50 000 (au lieu de 2000) pour rester purement défensif : jamais le
    # critère d'arrêt normal en pratique.
    STARR_DE_MIN_GENERATIONS: int = 30
    STARR_DE_MAX_GENERATIONS: int = 50_000
    # Il n'existe VOLONTAIREMENT plus de « fenêtre de stagnation ». Une
    # génération qui n'améliore pas le score, c'est déjà de la stagnation : la
    # température monte dès celle-là, et d'autant plus vite qu'elle dure. Le
    # délai de carence qui existait ici (40 générations avant de réagir) était la
    # cause du défaut observé — il n'a pas été raccourci, il a été supprimé.
    # Cf. `next_temperature`.
    # Seuil d'amélioration : un plancher ABSOLU (pour les scores proches de 0) et
    # une part RELATIVE du score. Le relatif est l'essentiel — sans lui, les
    # miettes numériques d'un DE élitiste passaient pour des progrès et
    # refroidissaient la température à chaque génération.
    # Cf. `is_real_improvement`.
    STARR_DE_MIN_IMPROVEMENT: float = 1e-6
    STARR_DE_MIN_IMPROVEMENT_REL: float = 1e-3
    # ── Recuit adaptatif à l'intérieur de seeds indépendantes ────────────────
    # La température module l'amplitude dans un bassin. Une seed épuisée est
    # ensuite polie et remplacée ; seul le meilleur global traverse la frontière.
    #
    # Le DE étant ÉLITISTE, la température n'agit pas sur l'acceptation dans la
    # population mais ENTRE BASSINS : on distingue l'incumbent (livré, jamais
    # dégradé) de l'ancre (point de perturbation, qui peut dériver). C'est du
    # basin hopping — le DE est l'optimiseur local, la température le marcheur.
    # Une seed neuve commence en exploitation. La température maximale sert à
    # constater l'épuisement du bassin, puis déclenche un VRAI redémarrage
    # indépendant ; elle n'est plus le régime normal de départ.
    STARR_DE_T0: float = 0.25
    # Plancher volontairement haut : sous 0,25 le réchauffage multiplicatif met
    # trop longtemps à rouvrir le support alors que les changements de poids ne
    # modifient souvent même plus les quantités réellement achetables.
    STARR_DE_T_MIN: float = 0.25
    STARR_DE_T_MAX: float = 1.00
    # Le REFROIDISSEMENT reste proportionnel au gain, mais un nouveau meilleur
    # SIGNIFICATIF ramène aussi la température au plus à 0,65. Sans ce plafond,
    # un gain de 0,1 % à T=1 ne baissait T qu'à 0,999 : la recherche restait en
    # reconstruction large et n'affinait jamais le bassin qui venait de payer.
    #   gain de 1 %   -> T × 0,99
    #   gain de 50 %  -> T × 0,50
    #   gain ≥ 100 %  -> T au plancher
    # Un facteur unique (×0,90) s'appliquait auparavant à toute amélioration
    # jugée réelle : une miette de 0,1 % éteignait l'exploration autant qu'un
    # gain massif, sans rien avoir rapporté.
    #
    STARR_DE_IMPROVEMENT_T_MAX: float = 0.65
    # Montée LINÉAIRE et prévisible, en fraction de la plage [T_MIN, T_MAX] par
    # génération sans progrès. 0,5 % demande environ 200 générations pour aller
    # de 0,25 à 1, contre ~60 avec l'ancienne accélération exponentielle.
    STARR_DE_HEATING: float = 0.005
    # Seul refroidissement à taux fixe : celui qui suit une demande d'arrêt.
    # Après un arrêt il n'y a plus forcément de gain, et une décroissance
    # proportionnelle à un gain nul ne convergerait jamais — le run ne
    # s'arrêterait pas.
    STARR_DE_STOP_COOLING: float = 0.90
    # L'ampleur d'un réchauffage est commandée par la température : à T→0 une
    # poignée d'individus voit une seule ligne changer, à T=1 la secousse est
    # maximale. Cf. `reheat_quota` et `reheat_amplitude`. Les anciens plafonds
    # (25 % de la population, 6 lignes échangées, incumbent intouchable)
    # faisaient qu'une température au plafond ne déplaçait presque rien : le DE
    # reconvergeait aussitôt sur le même optimum — température brûlante,
    # portefeuille immobile.
    #
    # Mais une secousse ne doit pas être une DESTRUCTION. Remplacer 100 % de la
    # population ne laisse au DE qu'une génération de croisement avant que tout
    # soit jeté : il ne converge jamais, et un portefeuille tiré au hasard ne bat
    # jamais un optimum affiné. Une part est donc toujours préservée — elle
    # continue de converger pendant que le reste est renouvelé, et le DE croise
    # les deux.
    #
    # Calibré sur 400 générations (banc de 300 titres, population 120) :
    #     plafond   score    améliorations après T=1   supports distincts
    #       100 %   8,6502                         6                    4
    #        70 %   9,3936                        15                   12   <-
    #        50 %   9,3656                        14                   11
    #        25 %   9,0349                        25                   15
    # 70 % donne le meilleur score ET triple le renouvellement des tickers.
    # Descendre plus bas fait bouger davantage le portefeuille, mais coûte du
    # score : 25 % rend 15 supports distincts pour 9,03 contre 9,39.
    STARR_DE_MAX_REHEAT_SHARE: float = 0.70
    # Recherche en entonnoir : chaque instrument est sondé à plusieurs poids,
    # seuls les meilleurs bassins reçoivent un court amorçage contraint, puis la
    # contrainte est retirée et le bassin est optimisé librement avec un budget
    # fixe. Le 10 % n'est donc plus une destination artificielle.
    STARR_DE_FORCED_FLOOR: float = 0.10
    STARR_DE_PROBE_FLOORS: tuple[float, ...] = (0.01, 0.03, 0.05, 0.10)
    STARR_DE_FORCED_PROBE_BATCH_SIZE: int = 64
    STARR_DE_FORCED_PROBE_ELITES: int = 12
    STARR_DE_FUNNEL_CONSTRAINED_GENERATIONS: int = 8
    STARR_DE_FUNNEL_FREE_GENERATIONS: int = 30
    STARR_DE_FUNNEL_FREE_MIN_GENERATIONS: int = 10
    # Un bassin encore plus mauvais que le meilleur global de ce nombre de
    # points après la phase libre minimale est abandonné sans consommer le reste.
    STARR_DE_FUNNEL_PRUNE_MARGIN: float = 0.25
    # Recherche par grands voisinages (LNS) : remplace par defaut l'entonnoir
    # « un ticker force a la fois ». Les variantes melangent petites retouches,
    # destructions/reconstructions moyennes, refontes larges et redemarrages
    # globaux. Une archive de supports eloignes empeche toutes les campagnes de
    # repartir du seul incumbent.
    STARR_LNS_ENABLED: bool = True
    STARR_LNS_ARCHIVE_SIZE: int = 32
    STARR_LNS_ARCHIVE_MIN_DISTANCE: float = 0.30
    # Génération évolutive diversifiée à chaque génération principale : quatre
    # voisins locaux du meilleur global + 12 autres supports uniques, 8 enfants
    # par parent et 10 explorations entièrement aléatoires.
    STARR_EVOLUTION_PARENT_COUNT: int = 12
    STARR_EVOLUTION_CHILDREN_PER_PARENT: int = 8
    # Parmi les huit enfants de chaque lignée, deux corrigent explicitement le
    # secteur matériel le plus concentré géographiquement.
    STARR_EVOLUTION_GEOGRAPHY_CHILDREN: int = 2
    # Quota d'exploitation fine réservé au meilleur global. Ces quatre enfants
    # ne sont pas répétés pour chacune des douze lignées : le reste du budget
    # conserve ainsi toute son amplitude d'exploration.
    STARR_EVOLUTION_GLOBAL_LOCAL_CHILDREN: int = 4
    STARR_EVOLUTION_RANDOM_CANDIDATES: int = 10
    STARR_EVOLUTION_MIN_PARENT_DISTANCE: float = 0.10
    # Les douze lignées ne sont plus choisies uniquement par score : quatre
    # élites, quatre continuations familiales, deux nouveautés et deux immigrants
    # aléatoires. À chaud, davantage de candidats sont injectés dans le DE.
    STARR_EVOLUTION_SCORE_ELITES: int = 4
    STARR_EVOLUTION_LINEAGE_SURVIVORS: int = 4
    STARR_EVOLUTION_NOVELTY_SURVIVORS: int = 2
    STARR_EVOLUTION_RANDOM_SURVIVORS: int = 2
    STARR_EVOLUTION_HOT_INJECTION_COUNT: int = 64
    # Après ce nombre de générations sans gain, huit lignées sur douze sont
    # remplacées par de nouveaux bassins. Le meilleur global reste intact.
    STARR_EVOLUTION_RESET_STAGNATION: int = 50
    STARR_EVOLUTION_RESET_PARENT_COUNT: int = 8
    # L'optimisation tourne dans le thread de fond FastAPI. Une courte pause par
    # génération rend explicitement le GIL au serveur et évite que les routes
    # health/progress/SSE saturent la file de sockets Windows pendant des heures.
    # 5 ms ajoutent seulement 0,5 s toutes les 100 générations.
    STARR_COOPERATIVE_YIELD_SECONDS: float = 0.005
    # Compromis lors du remplissage : 0 = faible correlation uniquement,
    # 1 = score standalone uniquement. La combinaison reste ensuite jugee par
    # l'objectif complet (CVaR, benchmark, couts et contraintes).
    STARR_LNS_GUIDANCE_WEIGHT: float = 0.55
    # Après 20 générations consécutives à T=1 sans gain, les poids du support de
    # la seed sont polis, puis une population indépendante repart de zéro. Le
    # meilleur global reste archivé hors de cette nouvelle population.
    STARR_DE_HOT_CONVERGENCE_GENERATIONS: int = 20
    STARR_SEED_SUPPORT_POLISH_MAXITER: int = 350
    # Échelle de l'acceptation entre bassins, dans l'unité du score : des POINTS
    # de % annuels vs CW8 (typiquement 0 à 10). À T=1 une dégradation d'un demi-
    # point est acceptée ~37 % du temps ; à T=0,1 pratiquement jamais.
    STARR_DE_ACCEPT_SCALE: float = 0.50
    # Garde-fou du mode BORNÉ uniquement (continuous_until_stopped=False : tests
    # et appels programmatiques). En mode continu, seule la demande d'arrêt
    # termine le run. Compte les réinjections CONSÉCUTIVES sans progrès : depuis
    # qu'il y en a une par génération de stagnation (et non plus une par fenêtre
    # de 40), ce plafond se lit directement en générations — d'où 200 et non 12,
    # pour garder un garde-fou du même ordre de grandeur qu'avant.
    STARR_DE_MAX_REHEATS: int = 200
    # Mémoire anti-cyclage : signatures de SUPPORT (lignes ouvertes) déjà
    # visitées. Sans elle, le réchauffage refait indéfiniment le même trajet.
    STARR_DE_TABU_SIZE: int = 200
    STARR_DE_MAX_SEEDS: int = 1
    # Tolérance scipy conservée pour le calcul/affichage de `convergence`, mais
    # elle ne décide plus de l'arrêt : seul le plateau chaud le fait.
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
    # jusqu'à obtenir un portefeuille admissible. Le plafond évite une boucle
    # infinie si les données ou contraintes rendent cela impossible.
    STARR_DE_POSITIVE_INIT_BATCH_SIZE: int = 256
    STARR_DE_POSITIVE_INIT_MAX_BATCHES: int = 200
    # Screening ÉLITISTE des seeds froides : au lieu de repartir du premier
    # portefeuille aléatoire admissible venu, on en évalue beaucoup (les lots sont
    # vectorisés, c'est un produit BLAS) et on garde les meilleurs du LOT. Le seuil
    # d'acceptation est le pire élite courant — un quantile, jamais une fraction
    # d'un maximum qui n'existe pas (le score est un écart au benchmark, non borné).
    # La mémoire reste bornée : les tirages sont traités par lots. Le coût total
    # (~25 600 évaluations) vaut une cinquantaine de générations de DE — peu cher
    # pour un point de départ nettement meilleur, sur une seed qui en fera des
    # centaines.
    STARR_DE_ELITE_BATCHES: int = 100
    STARR_DE_ELITE_COUNT: int = 40
    # Ce qui piège le DE sur ce problème à support variable, c'est le
    # SUPPORT (les lignes ouvertes) — un bruit gaussien ne le change jamais. Le
    # remaniement de support n'a plus de bornes en dur ici : son amplitude suit
    # la température, de une ligne à la totalité du portefeuille.
    # Cf. `reheat_amplitude`.
    #
    # Le kick peut ouvrir jusqu'à la capacité économique du portefeuille afin
    # que l'objectif compare réellement les supports. La taille retenue reste
    # libre : aucun malus n'est appliqué au seul nombre de lignes.
    # Laissé à 1,0 et configurable pour les univers plus larges. Cf.
    # `kick_line_budget`.
    STARR_DE_KICK_LINES_FACTOR: float = 1.0
    # Ticker imposé comme individu de départ « 1 seule ligne » (ex. un ETF monde) ;
    # vide = ETF au meilleur score standalone, à défaut meilleur titre standalone.
    STARR_DE_SEED_TICKER: str = ""
    # Aucun plafond individuel par action par défaut : STARR peut retenir une
    # concentration élevée si elle maximise réellement le ratio STARR. La
    # diversification reste encouragée par les bonus pays/régions et contrôlée
    # par les plafonds géographiques/sectoriels.
    MAX_POSITION_PCT: float = 1.0
    # Plafond dur sur le capital TOTAL, pour tout compartiment de risque résolu :
    # secteurs Yahoo et catégories ETF manuelles (Or, Monde, Growth, etc.).
    MAX_SECTOR_PCT: float = 0.25
    # Surcharges par compartiment (clés canonisées via breakdown._canon_sector).
    # L'or satisfait le plancher défensif à moindre coût de risque et échappe au
    # plafond pays (« Sans pays ») : sans surcharge, l'optimiseur en charge
    # jusqu'au plafond commun de 25 %.
    MAX_SECTOR_PCT_OVERRIDES: dict = {"Or": 0.10}
    # Budget SOUPLE de contribution au risque baissier par secteur. Le poids
    # nominal peut donc monter jusqu'au plafond dur de 25 % si le secteur reste
    # peu contributeur au CVaR + semi-déviation du portefeuille.
    STARR_MAX_SECTOR_RISK_SHARE: float = 0.20
    STARR_SECTOR_RISK_PENALTY: float = 25.0
    # Budget souple renforcé pour la technologie. Les autres secteurs gardent
    # le seuil et le coefficient communs ci-dessus.
    STARR_MAX_SECTOR_RISK_SHARE_OVERRIDES: dict = {"Technologie": 0.10}
    STARR_SECTOR_RISK_PENALTY_OVERRIDES: dict = {"Technologie": 100.0}
    # Même budget souple, appliqué cette fois aux PAYS (look-through ETF_Pays).
    # Secteur et pays sont deux découpages COMPLETS et indépendants du même
    # portefeuille : chaque titre pèse 100 % dans son pays ET 100 % dans son
    # secteur. Il n'y a donc aucun risque à répartir entre les deux axes.
    # Piloter par le risque plutôt que par le seul poids évite de traiter à
    # l'identique 25 % d'obligations d'État et 25 % de technologie américaine.
    # Seuil d'ALERTE, plus contrainte : au-delà, le pays est signalé en orange
    # dans les diagnostics sans que l'allocation en soit déformée.
    STARR_MAX_COUNTRY_RISK_SHARE: float = 0.20
    # Réserve d'origine, TOUJOURS VALABLE, conservée telle quelle : cette part de
    # risque dépend d'estimations empilées (CVaR, semi-déviation, corrélations,
    # copule gaussienne) et elle est pro-cyclique — un marché calme récemment
    # obtient le plus gros budget, précisément avant de corriger. Le pipeline
    # contient déjà beaucoup de risque estimé ; un axe estimé de plus ajoute une
    # dépendance au modèle. Le coefficient avait donc été mis à 0 : CONTRAINDRE
    # sur ce qui est fiable (le poids, plafond dur à 30 %) et MESURER ce qui est
    # informatif (la contribution au risque).
    #
    # 2026-08-08 : réactivé à 5 (la valeur que le commentaire d'origine désignait
    # déjà comme calibrée), à la demande de l'utilisateur. Motif : à 0 le terme
    # était calculé et affiché dans les diagnostics tout en n'ayant aucun effet,
    # ce qui le faisait passer pour une contrainte active. Revenir à 0.0 reste le
    # bon geste si l'allocation devient visiblement pro-cyclique.
    STARR_COUNTRY_RISK_PENALTY: float = 5.0
    # Plafond pays activé : la faisabilité géographique reste une contrainte dure.
    # Un cœur World doit donc être combiné à des expositions complémentaires.
    COUNTRY_HARD_CAP_ENABLED: bool = True
    # Une contribution au risque faible ne suffit pas à rendre saine une
    # exposition nominale de 70 % à la même région. Ce plafond porte sur le
    # look-through géographique et reste compatible avec un cœur World.
    MAX_REGION_PCT: float = 0.50
    STARR_MAX_REGION_RISK_SHARE: float = 0.40
    STARR_REGION_RISK_PENALTY: float = 5.0
    # Repère visuel seulement dans la décomposition en actions ; il ne modifie
    # ni le score, ni la faisabilité, ni le poids autorisé d'un ETF.
    STARR_MAX_ECONOMIC_ACTION_PCT: float = 0.08
    # Bonus continu de diversification géographique DANS chaque secteur. Le
    # signal utilise log(nombre effectif de pays) et log(nombre de pays
    # significatifs), plutôt qu'un plafond externe ou l'inverse d'un écart-type.
    # Ces deux derniers explosent respectivement lorsque les poids sont égaux ou
    # lorsqu'un portefeuille ne contient qu'un seul pays. Le logarithme donne un
    # rendement décroissant sans rendre le bonus constant ni infini.
    STARR_SECTOR_COUNTRY_DIVERSIFICATION_BONUS: float = 0.65
    STARR_SECTOR_COUNTRY_SIGNIFICANT_PCT: float = 0.01
    STARR_SECTOR_COUNTRY_SIGNIFICANT_BONUS_WEIGHT: float = 0.25
    # Petit malus ciblé : 2 pays effectifs pour un secteur de 5-10 %, 3 au-delà.
    # Il complète le bonus continu sans transformer le nombre de lignes en cible.
    STARR_SECTOR_COUNTRY_DEFICIT_PENALTY: float = 10.0
    STARR_SECTOR_COUNTRY_MEDIUM_EXPOSURE: float = 0.05
    STARR_SECTOR_COUNTRY_LARGE_EXPOSURE: float = 0.10
    # Bonus géographique global : les deux égalités sont exponentielles
    # (écart-type faible = facteur proche de 1) et sont multipliées par le
    # nombre de pays significatifs. Il reste souple : STARR peut le sacrifier
    # si le gain de risque/rendement est supérieur.
    STARR_GEOGRAPHIC_DIVERSIFICATION_BONUS: float = 1.50
    STARR_GEOGRAPHIC_COUNTRY_STD_EXPONENT: float = 20.0
    STARR_GEOGRAPHIC_REGION_STD_EXPONENT: float = 20.0
    # Contraintes look-through (feuilles ETF_Defensif / ETF_Pays) :
    MIN_DEFENSIVE_PCT: float = 0.30    # min du portefeuille en défensif (look-through)
    # Plafond DUR par pays (look-through). C'est la seule contrainte géographique
    # qui engage : elle porte sur un fait vérifiable (le capital exposé) et non
    # sur une estimation, donc elle couvre aussi le risque que la CVaR ne voit
    # pas — politique, fiscal, monétaire, contrôle des capitaux.
    # 30 % et non 20 % : un ETF MSCI World étant à ~70 % américain, un plafond
    # trop bas interdit de fait tout cœur de portefeuille indiciel (la limite USA
    # serait atteinte dès ~28 % d'ETF monde). 30 % reste très en dessous du poids
    # des États-Unis dans l'indice mondial, sans rendre le portefeuille
    # inconstructible.
    MAX_COUNTRY_PCT: float = 0.30
    # Enrichissement pays avant les cours : Yahoo n'est interrogé que pour les
    # ETF absents du cache/ISIN. Le plafond évite qu'un catalogue exotique rende
    # la préparation plus longue que l'optimisation elle-même.
    ETF_COUNTRY_MAX_LIVE_FETCHES: int = 20
    ETF_HOLDINGS_MIN_COUNTRY_COVERAGE: float = 0.90
    # Seuil d'admission économique des ETF. Pour un synthétique, le collatéral
    # est refusé et aucun fonds physique n'est copié : seuls les constituants
    # officiels de l'indice exact sont admis. Sous ce seuil le fonds est remplacé.
    ETF_ECONOMIC_COMPOSITION_MIN_COVERAGE: float = 0.90
    # Enrichissement officiel limité aux ETF retenus par la présélection. Les
    # réponses sont mises en cache par ISIN/indice ; une absence de composition
    # économique suffisante retire le fonds et déclenche la recherche d'un
    # remplaçant.
    ETF_OFFICIAL_ENRICHMENT_ENABLED: bool = True
    ETF_OFFICIAL_INDEX_ENRICHMENT_ENABLED: bool = True
    # Shared across issuer/index searches and replacement waves, not per ETF.
    ETF_RESEARCH_SECONDS: float = 180.0
    ETF_RESEARCH_REQUESTS: int = 80
    ETF_RESEARCH_FUNDS: int = 24
    ETF_RESEARCH_INDICES: int = 12
    ETF_COMPOSITION_MAX_ROUNDS: int = 3
    # Les candidats de réserve sont vérifiés dans le même lot que les 100 ETF
    # cibles. Cela évite des dizaines de tours unitaires en fin de catalogue.
    ETF_COMPOSITION_BATCH_BUFFER_PER_BROKER: int = 50
    # Concurrence réseau bornée : quatre fonds au total, au plus deux pour un
    # même émetteur, afin d'accélérer sans déclencher ses protections anti-abus.
    ETF_ENRICHMENT_MAX_WORKERS: int = 4
    ETF_ENRICHMENT_MAX_WORKERS_PER_PROVIDER: int = 2
    # Les fichiers quotidiens vieillissent vite; les fichiers TOPIX officiels
    # sont mensuels et publiés avec décalage, d'où une fenêtre plus longue.
    ETF_INDEX_DAILY_MAX_AGE_DAYS: int = 7
    ETF_INDEX_MONTHLY_MAX_AGE_DAYS: int = 45
    ETF_INDEX_ISSUER_MAX_AGE_DAYS: int = 31
    ETF_COMPOSITION_MAX_AGE_DAYS: int = 365
    ETF_COMPOSITION_TRIGGER_WEIGHT: float = 0.001
    CONSTRAINT_PENALTY: float = 100.0  # raideur des pénalités (quadratiques ; ↑ = plus strict)
    # Cash oisif : le capital non investi ne rapporte rien. Sans malus, l'optimiseur
    # pouvait garder ~10 % en espèces (secteur saturé écrêté sans redistribution)
    # puisque le cash réduit aussi le risque. Malus quadratique k·(1−investi)²,
    # volontairement RAIDE (10 % de cash ≈ 5 points d'objectif) pour que rester
    # liquide ne soit jamais rentable.
    STARR_CASH_PENALTY: float = 500.0
    # Aucun minimum de lignes ni malus de concentration propre à un broker : le
    # risque économique est contrôlé sur le portefeuille GLOBAL. Ces constantes
    # restent à zéro pour la compatibilité des surcharges de configuration.
    STARR_MIN_LINES_PER_BROKER: int = 0
    STARR_LINE_SHORTFALL_PENALTY: float = 0.0
    STARR_BROKER_CONCENTRATION_PENALTY: float = 0.0
    # Passes de redéploiement du cash libéré par les plafonds. Peu de passes pour
    # les candidats du DE (coût × population), beaucoup pour la solution retenue.
    STARR_CASH_REDEPLOY_PASSES: int = 3
    STARR_CASH_REDEPLOY_PASSES_FINAL: int = 25
    N_MULTISTART: int = settings.buffett_n_multistart
    USE_BROKER_CONSTRAINTS: bool = True
    # Seuil de corrélation (rendements convertis EUR) au-delà duquel deux ETF sont
    # des « jumeaux d'indice » -> on retire le moins liquide. Décision utilisateur
    # 2026-07-13 : 0,95, et la règle ne s'applique QU'ENTRE ETF — une ACTION n'est
    # jamais retirée pour cause de corrélation (ni fusionnée avec un ETF) : deux
    # entreprises corrélées restent deux entreprises distinctes. Ajustable via
    # params.json.
    CORRELATION_DEDUP_THRESHOLD: float = 0.95
    # Présélection avant STARR : l'optimiseur peut comparer un support large ;
    # restreindre les candidats à 50 fermait trop tôt le champ
    # des possibles — la présélection écartait des fonds AVANT que l'optimiseur
    # ait pu juger leur apport en diversification secteur × pays. Porté à 100 le
    # 2026-08-10 (décision utilisateur) : le coût du DE croît avec le nombre de
    # candidats, mais la déduplication par corrélation (CORRELATION_DEDUP_THRESHOLD)
    # écarte déjà les jumeaux d'indice, donc les 50 candidats supplémentaires
    # apportent surtout de la variété réelle.
    ETF_MAX_CANDIDATES_PER_BROKER: int = 100
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
    # Nombre de titres au-delà duquel la copule de Vine est remplacée par une
    # copule GAUSSIENNE sur la matrice de corrélation (Spearman) COMPLÈTE.
    #
    # 0 = toujours la gaussienne. Ce n'est PAS un compromis vitesse/qualité :
    # `DVineCopula.simulate()` (vine_copula.py) se termine elle aussi par un
    # `multivariate_normal` + `norm.cdf`, donc par une gaussienne — mais nourrie
    # par `implied_correlation()`, qui ne lit QUE l'arbre 1 (`self.copulas[(1,
    # edge)]`) et ne remplit donc que les n-1 arêtes du chemin D-vine. À 135
    # titres cela renseigne 134 paires sur 9 045 : **98,5 % des corrélations
    # sont forcées à ZÉRO**. Pour un CVaR c'est l'erreur la plus coûteuse
    # possible — cette indépendance fictive fait paraître le portefeuille bien
    # plus diversifié qu'il n'est et SOUS-ESTIME les pertes extrêmes. Les
    # familles à queue épaisse (Clayton, Gumbel, BB7) sont en outre aplaties en
    # un simple rho via le tau de Kendall, et le facteur `correction` censé les
    # compenser n'est jamais appliqué : la dépendance de queue, seule raison
    # d'employer une vine, est perdue de toute façon.
    #
    # Le coût, lui, est bien réel : `_greedy_order` fait n²/2 taus de Kendall en
    # boucle Python, puis `fit` ajuste tous les arbres — dont seul le premier
    # sera lu. Mesuré : > 1 h à 135 titres sans une seule génération émise, et
    # ~1 h à 1250 titres (#bug rapporté : run figé à "seed 1, 0 générations").
    # La gaussienne pleine est vectorisée, ~100x plus rapide, ET plus juste.
    STARR_VINE_MAX_DIM: int = 0

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
