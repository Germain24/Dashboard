"""Disponibilité des actions par broker, lue depuis ToutBroker.xlsx.

Le fichier (par défaut ``data/imports/ToutBroker.xlsx``) contient une ligne par
action avec des colonnes de disponibilité par broker — ``Tradding 212``,
``Bourse Direct``, ``Bourse Direct 2``, ``IBKR`` — valant 1 (disponible) / 0
(indisponible). On fusionne ces colonnes dans le DataFrame passé à l'optimiseur
afin que celui-ci n'alloue une action que sur les brokers où elle est achetable.

Ticker inconnu dans le fichier → considéré disponible partout (comportement legacy).
"""

from __future__ import annotations

import os
import re

from .config import Config

# Classeurs mémoïsés : chemin -> ((mtime, taille), DataFrame). Un dictionnaire
# et non une entrée unique, car plusieurs fichiers sont lus en alternance au
# cours d'un même run — un cache mono-entrée se ferait évincer à chaque tour.
# Déclaré ici parce que `read_broker_excel`, tout en haut du fichier, s'en sert.
_EXCEL_CACHE: dict[str, tuple[tuple, object]] = {}
_BROKER_TABLE_CACHE = None


def _clean(v) -> str:
    return "".join(filter(str.isalnum, str(v).upper()))


def _alpha(v: str) -> str:
    return "".join(c for c in v if c.isalpha())


def _trailing_num(v: str) -> str:
    m = re.search(r"(\d+)$", v)
    return m.group(1) if m else ""


def _existing_candidates(configured: str, filename: str) -> list[str]:
    rel = os.path.join("data", "imports", "Finances", "tableur", filename)
    return [configured, rel, os.path.join("..", rel)]


def find_broker_files() -> list[str]:
    """Retourne les exports Actions/ETF, avec repli temporaire sur l'ancien mixte."""
    found: list[str] = []
    for configured, filename in (
        (Config.BROKER_ACTIONS_FILE, "ToutBroker_Actions.xlsx"),
        (Config.BROKER_ETF_FILE, "ToutBroker_ETF.xlsx"),
    ):
        for candidate in _existing_candidates(configured, filename):
            if candidate and os.path.exists(candidate):
                found.append(candidate)
                break
    if found:
        return found
    legacy = os.path.join("data", "imports", "Finances", "tableur", "ToutBroker.xlsx")
    candidates = [
        legacy,
        os.path.join("..", legacy),
    ]
    return [candidate for candidate in candidates if os.path.exists(candidate)][:1]


def find_broker_file() -> str | None:
    """Retourne le classeur ETF, qui porte les feuilles annexes d'indices."""
    files = find_broker_files()
    etf_name = os.path.basename(Config.BROKER_ETF_FILE).casefold()
    return next(
        (path for path in files if os.path.basename(path).casefold() == etf_name),
        files[0] if files else None,
    )


def read_broker_excel(path: str):
    """Lit ToutBroker.xlsx sans perdre les tickers homonymes d'un « manquant ».

    ``pd.read_excel`` traite par défaut « NA », « NULL », « N/A »… comme des
    valeurs manquantes : le ticker de Nano Labs (NASDAQ : ``NA``) devenait donc
    NaN et la ligne était vidée de son ticker à la première réécriture du
    fichier. On ne considère manquante que la cellule réellement vide, ce qui
    laisse les dtypes des autres colonnes inchangés.

    MÉMOÏSÉ sur (chemin, mtime, taille). Six appelants ouvrent ce classeur —
    disponibilités broker, classes d'actif, tickers ETF, look-through,
    répartitions — chacun pour son propre besoin. Profilé sur un run, il était
    relu CINQ fois pour 335 s : le premier poste de la préparation, avant même
    la simulation Monte-Carlo. La signature de fichier rend l'invalidation
    automatique : une réécriture est prise en compte d'elle-même, sans qu'aucun
    appelant ait à y penser.

    Une COPIE est rendue à chaque appel : plusieurs appelants renomment des
    colonnes ou filtrent des lignes en place, et se partager le même objet les
    ferait interférer.
    """
    import pandas as pd

    try:
        stat = os.stat(path)
        signature = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        signature = None
    if signature is not None:
        connu = _EXCEL_CACHE.get(str(path))
        if connu is not None and connu[0] == signature:
            return connu[1].copy()
    # ``ToutBroker.xlsx`` approche 260 000 lignes. openpyxl matérialise chaque
    # cellule Python et pouvait immobiliser le backend plusieurs minutes (et donc
    # faire expirer le proxy Next). Calamine lit le même classeur en Rust en une
    # trentaine de secondes sur la machine cible. Garder un repli explicite pour
    # les environnements de test/minimaux où l'extra ne serait pas installé.
    try:
        table = pd.read_excel(
            path,
            engine="calamine",
            keep_default_na=False,
            na_values=[""],
        )
    except (ImportError, ValueError):
        table = pd.read_excel(path, keep_default_na=False, na_values=[""])
    if signature is not None:
        _EXCEL_CACHE[str(path)] = (signature, table)
    return table.copy()


def load_broker_table():
    """Charge le catalogue SQLite, avec le classeur comme bootstrap historique.

    La lecture elle-même est mémoïsée dans `read_broker_excel`.
    """
    global _BROKER_TABLE_CACHE
    if _BROKER_TABLE_CACHE is not None:
        return _BROKER_TABLE_CACHE.copy()
    try:
        from app.services.finance.catalog.repository import catalog_dataframe

        normalized = catalog_dataframe()
        if normalized is not None:
            # Le merge des ETF manuels est optionnel : un classeur corrompu ne doit
            # jamais jeter le catalogue SQLite déjà chargé. On l'isole donc ici.
            from .manual_etf_sources import merge_manual_etfs
            try:
                normalized = merge_manual_etfs(normalized)
            except Exception as exc:
                print(f"[broker_availability] ETF manuels ignorés: {exc}")
            _BROKER_TABLE_CACHE = normalized
            return normalized.copy()
    except Exception as exc:
        print(f"[broker_availability] Catalogue SQLite indisponible: {exc}")
    paths = find_broker_files()
    if not paths:
        return None
    try:
        import pandas as pd

        tables = [read_broker_excel(path) for path in paths]
        table = pd.concat(tables, ignore_index=True, sort=False)
        from .manual_etf_sources import merge_manual_etfs
        table = merge_manual_etfs(table)
        _BROKER_TABLE_CACHE = table
        return table.copy()
    except Exception as e:
        print(f"[broker_availability] Lecture {paths}: {e}")
        return None


def _secteur1_col(columns) -> str | None:
    """Trouve la colonne 'Secteur 1' (tolère espaces/casse)."""
    for c in columns:
        if str(c).strip().lower() == "secteur 1":
            return c
    return None


def _secteur2_col(columns) -> str | None:
    """Trouve la colonne 'Secteur 2' (tolère espaces/casse)."""
    for c in columns:
        if str(c).strip().lower() == "secteur 2":
            return c
    return None


def _normalize_asset_class(secteur2, secteur1) -> str | None:
    """Classe d'actif depuis 'Secteur 2'. None = inconnue.

    Obligations et Monétaire sont FUSIONNÉS en `taux` (décision utilisateur
    2026-07-21) : le monétaire ne comptait qu'un titre, et son comportement est
    celui d'un produit de taux.

    La comparaison se fait sur un PRÉFIXE désaccentué et jamais sur la chaîne
    complète : le tableur contient du mojibake (`Mati?res premi?res`,
    `Mon?taire`) qui ferait silencieusement tomber ces classes dans `actions`.
    """
    import unicodedata

    norm = (
        unicodedata.normalize("NFKD", str(secteur2).strip())
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    if norm in ("", "nan", "none"):
        # Un titre vif sans Secteur 2 est une action ; un ETF sans Secteur 2 a une
        # classe réellement inconnue -> repli sur la médiane globale.
        return None if str(secteur1).strip().upper() == "ETF" else "actions"
    if norm.startswith("oblig") or norm.startswith("mon"):
        return "taux"
    if norm.startswith("mati"):
        return "matieres_premieres"
    return "actions"


def _compute_asset_classes(df, ticker_col: str) -> dict[str, str]:
    if df is None or getattr(df, "empty", True):
        return {}
    tcol = _find_ticker_col(df.columns, ticker_col)
    s2col = _secteur2_col(df.columns)
    s1col = _secteur1_col(df.columns)
    if tcol is None or s2col is None:
        return {}
    s1_values = df[s1col] if s1col is not None else ["" for _ in range(len(df))]
    out: dict[str, str] = {}
    for t, s2, s1 in zip(df[tcol], df[s2col], s1_values, strict=True):
        tt = _norm_ticker(t)
        if not tt:
            continue
        klass = _normalize_asset_class(s2, s1)
        if klass is not None:
            out[tt] = klass
    return out


def load_asset_classes(df=None, ticker_col: str = "Ticker Yahoo Finance") -> dict[str, str]:
    """Classe d'actif par ticker depuis ToutBroker.xlsx ('Secteur 2').

    Source AUTORITAIRE, comme `load_etf_tickers` l'est pour la classification ETF.
    Sert au prior de rendement de l'optimiseur : chaque titre est tiré vers la
    médiane de SA classe et non vers celle de tout l'univers, qui offrait ~9 points
    de rendement fictif aux obligations. `df` explicite = pas de cache (tests).
    """
    global _ASSET_CLASS_CACHE
    if df is not None:
        return _compute_asset_classes(df, ticker_col)
    if _ASSET_CLASS_CACHE is None:
        _ASSET_CLASS_CACHE = _compute_asset_classes(load_broker_table(), ticker_col)
    return _ASSET_CLASS_CACHE


def _norm_ticker(v) -> str:
    s = str(v).strip().upper()
    return "" if s in ("", "NAN", "NONE") else s


def _compute_etf_tickers(df, ticker_col: str) -> set[str]:
    if df is None or getattr(df, "empty", True):
        return set()
    tcol = _find_ticker_col(df.columns, ticker_col)
    scol = _secteur1_col(df.columns)
    if tcol is None or scol is None:
        return set()
    out: set[str] = set()
    for t, s in zip(df[tcol], df[scol], strict=True):
        if str(s).strip().upper() == "ETF":
            tt = _norm_ticker(t)
            if tt:
                out.add(tt)
    return out


_ETF_CACHE: set[str] | None = None
_UNIVERSE_CACHE: set[str] | None = None
_ASSET_CLASS_CACHE: dict[str, str] | None = None
_INSTRUMENT_NAME_CACHE: dict[str, str] | None = None


def load_instrument_names(df=None, ticker_col: str = "Ticker Yahoo Finance") -> dict[str, str]:
    """Nom de catalogue stable, utilisé lorsque Yahoo ne renvoie que le ticker."""
    global _INSTRUMENT_NAME_CACHE
    if df is None and _INSTRUMENT_NAME_CACHE is not None:
        return _INSTRUMENT_NAME_CACHE
    frame = load_broker_table() if df is None else df
    if frame is None or getattr(frame, "empty", True):
        return {}
    tcol = _find_ticker_col(frame.columns, ticker_col)
    ncol = next(
        (column for column in frame.columns if str(column).strip().casefold() in {"nom", "name"}),
        None,
    )
    if tcol is None or ncol is None:
        return {}
    names = {
        _norm_ticker(ticker): str(name).strip()
        for ticker, name in zip(frame[tcol], frame[ncol], strict=True)
        if _norm_ticker(ticker)
        and str(name).strip().casefold() not in {"", "nan", "none"}
    }
    if df is None:
        _INSTRUMENT_NAME_CACHE = names
    return names


def reset_etf_cache() -> None:
    """Invalide les caches ETF/univers/classes (à appeler après modif de ToutBroker.xlsx)."""
    global _ETF_CACHE, _UNIVERSE_CACHE, _ASSET_CLASS_CACHE, _INSTRUMENT_NAME_CACHE, _BROKER_TABLE_CACHE
    _ETF_CACHE = None
    _UNIVERSE_CACHE = None
    _ASSET_CLASS_CACHE = None
    _INSTRUMENT_NAME_CACHE = None
    _BROKER_TABLE_CACHE = None
    _EXCEL_CACHE.clear()


def load_etf_tickers(df=None, ticker_col: str = "Ticker Yahoo Finance") -> set[str]:
    """Tickers (MAJ) dont 'Secteur 1' == 'ETF' dans ToutBroker.xlsx.

    Source autoritaire de la classification ETF (MOAT non applicable). ``df`` explicite =
    pas de cache (tests) ; sinon résultat mémoïsé (relire l'Excel à chaque ticker
    serait prohibitif). Utiliser ``reset_etf_cache()`` après une écriture du fichier.
    """
    global _ETF_CACHE
    if df is not None:
        return _compute_etf_tickers(df, ticker_col)
    if _ETF_CACHE is None:
        _ETF_CACHE = _compute_etf_tickers(load_broker_table(), ticker_col)
    return _ETF_CACHE


def _compute_universe(df, ticker_col: str) -> set[str]:
    if df is None or getattr(df, "empty", True):
        return set()
    tcol = _find_ticker_col(df.columns, ticker_col)
    if tcol is None:
        return set()
    return {tt for t in df[tcol] if (tt := _norm_ticker(t))}


def load_broker_universe(df=None, ticker_col: str = "Ticker Yahoo Finance") -> set[str]:
    """Tous les tickers (MAJ) présents dans ToutBroker.xlsx (univers curé)."""
    global _UNIVERSE_CACHE
    if df is not None:
        return _compute_universe(df, ticker_col)
    if _UNIVERSE_CACHE is None:
        _UNIVERSE_CACHE = _compute_universe(load_broker_table(), ticker_col)
    return _UNIVERSE_CACHE


def _cell_state(v) -> bool | None:
    """Interprète une cellule de disponibilité broker : True / False / None (vide).

    None = cellule vide / valeur inattendue → « inconnu » (ne compte pas comme Faux).
    """
    try:
        import pandas as pd

        if v is None or pd.isna(v):
            return None
    except (TypeError, ValueError):
        if v is None:
            return None
    s = str(v).strip().lower()
    if s == "" or s == "nan":
        return None
    if s in ("1", "1.0", "true", "vrai", "oui", "yes", "x", "v"):
        return True
    if s in ("0", "0.0", "false", "faux", "non", "no"):
        return False
    return None  # valeur non reconnue → prudence : analyser


def broker_excluded_tickers(ticker_col: str = "Ticker Yahoo Finance") -> set[str]:
    """Tickers (MAJ) à IGNORER : présents dans ToutBroker.xlsx ET dont TOUTES les
    colonnes broker sont explicitement Faux. Une cellule vide ne compte pas comme
    Faux (la ligne reste analysée). Tout le reste (absent du fichier, au moins un
    broker Vrai, ou au moins une cellule vide) est analysé.

    Vide si le fichier est introuvable / sans colonne ticker / sans colonne broker
    reconnue → l'appelant n'exclut alors rien (analyse tout, garde-fou).
    """
    df = load_broker_table()
    if df is None:
        return set()
    tcol = _find_ticker_col(df.columns, ticker_col)
    if tcol is None:
        return set()
    broker_cols: list = []
    for broker in Config.BUDGET_BROKERS:
        c = _match_broker_column(broker, df.columns)
        if c is not None and c not in broker_cols:
            broker_cols.append(c)
    if not broker_cols:
        return set()

    # ``iterrows`` sur les quelque 258 000 cotations immobilisait la phase de
    # préparation plusieurs minutes avant chaque run. La conversion reste
    # strictement identique à ``_cell_state`` mais s'effectue colonne par
    # colonne, puis le masque est calculé par pandas.
    states = df[broker_cols].map(_cell_state)
    all_explicitly_false = states.eq(False).all(axis=1)  # noqa: E712
    tickers = df.loc[all_explicitly_false, tcol].map(_norm_ticker)
    return {ticker for ticker in tickers if ticker}


def broker_investable_tickers(
    active_brokers: list[str] | tuple[str, ...] | set[str],
    df=None,
    ticker_col: str = "Ticker Yahoo Finance",
) -> set[str]:
    """Union stricte des titres explicitement disponibles chez les brokers actifs.

    Un broker est actif lorsque son budget est strictement positif. Une ligne
    absente du catalogue, une cellule vide ou une valeur inconnue ne prouvent
    pas que le titre est achetable et sont donc exclues du run. Cette fonction
    est volontairement plus stricte que :func:`broker_excluded_tickers`, gardée
    pour les anciens appels qui distinguent encore ``Faux`` de ``inconnu``.
    """
    frame = load_broker_table() if df is None else df
    if frame is None or getattr(frame, "empty", True):
        return set()
    tcol = _find_ticker_col(frame.columns, ticker_col)
    if tcol is None:
        return set()
    broker_cols = [
        column
        for broker in active_brokers
        if (column := _match_broker_column(str(broker), frame.columns)) is not None
    ]
    broker_cols = list(dict.fromkeys(broker_cols))
    if not broker_cols:
        return set()
    states = frame[broker_cols].map(_cell_state)
    explicitly_available = states.eq(True).any(axis=1)  # noqa: E712
    tickers = frame.loc[explicitly_available, tcol].map(_norm_ticker)
    return {ticker for ticker in tickers if ticker}


def _find_ticker_col(columns, ticker_col: str) -> str | None:
    if ticker_col in columns:
        return ticker_col
    for c in columns:
        if "ticker" in str(c).lower():
            return c
    return None


def _match_broker_column(broker_name: str, columns) -> str | None:
    """Associe un broker de Config (ex: 'Trading212') à sa colonne dans ToutBroker
    (ex: 'Tradding 212'), tolérant l'orthographe et les espaces.
    """
    cb, cb_num = _clean(broker_name), _trailing_num(broker_name)
    cb_alpha = _alpha(cb)
    best = None
    for c in columns:
        cc = _clean(c)
        if cb == cc:
            return c  # correspondance exacte
        cc_num, cc_alpha = _trailing_num(cc), _alpha(cc)
        if cc_num != cb_num:
            continue
        # même numéro de fin + préfixes alpha qui se ressemblent (4 premiers car.)
        if cb_alpha[:4] and cb_alpha[:4] == cc_alpha[:4]:
            best = c
    return best


# Attribut BuffettRunResult -> colonne ToutBroker.xlsx. Seules les colonnes
# déjà présentes dans le fichier sont écrites (on n'invente pas de colonnes).
_RESULT_TO_BROKER_COL = {
    "chance_moat": "Chance MOAT",
    "achat": "Achat",
    "nom": "Nom",
    "pays": "Pays",
    "secteur": "Secteur",
    "prix": "Prix",
    "eps": "EPS",
    "per": "PER",
    "croissance": "Croissance",
    "peg": "PEG",
    "volume": "Volume",
}


def _save_main_sheet(df, path: str) -> None:
    """Écrit ``df`` dans la 1re feuille de ToutBroker en PRÉSERVANT les autres
    feuilles (``ETF_Defensif``, ``ETF_Pays``…). Sans autres feuilles -> écriture simple.
    """
    import pandas as pd

    main, has_others = None, False
    try:
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True)
        main = wb.sheetnames[0]
        has_others = len(wb.sheetnames) > 1
        wb.close()
    except Exception:
        pass
    if has_others and main:
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
            df.to_excel(w, sheet_name=main, index=False)
    else:
        df.to_excel(path, index=False)


def update_broker_file_scores(
    rows, path: str | None = None, ticker_col: str = "Ticker Yahoo Finance"
) -> int:
    """Écrit les scores/indicateurs de l'analyse dans ToutBroker.xlsx (upsert par ticker).

    ``rows`` : itérable d'objets type ``BuffettRunResult`` (attributs ``ticker``,
    ``chance_moat``, ``achat``, ``nom``, ``pays``, ``secteur``, ``prix``, ``eps``,
    ``per``, ``croissance``, ``peg``, ``volume``).

    - Ticker déjà présent -> met à jour ses cellules (Chance MOAT, Achat, indicateurs).
    - Ticker absent -> ajoute une nouvelle ligne.
    - Les autres colonnes (disponibilité broker incluse) sont **préservées**.

    Retourne le nombre de tickers traités. Sans fichier -> 0 (aucune écriture).
    """
    from app.services.finance.catalog.repository import (
        append_analysis_results,
        normalized_catalog_is_active,
    )

    if path is None and normalized_catalog_is_active():
        return append_analysis_results(rows)
    path = path or find_broker_file()
    if not path:
        return 0
    try:
        import pandas as pd

        df = read_broker_excel(path)
        tcol = _find_ticker_col(df.columns, ticker_col) or ticker_col
        if tcol not in df.columns:
            return 0

        # Colonnes du fichier qu'on sait remplir.
        writable = {attr: col for attr, col in _RESULT_TO_BROKER_COL.items() if col in df.columns}

        # Excel relit souvent les colonnes "entières" (8.0, 12.0…) en int64 ;
        # passer en object évite un rejet de dtype lors de l'écriture d'un float.
        for col in set(writable.values()):
            df[col] = df[col].astype(object)

        # Index ticker (nettoyé) -> position de ligne (première occurrence).
        index: dict[str, int] = {}
        for i, k in df[tcol].astype(str).str.strip().items():
            index.setdefault(k.upper(), i)

        # Les quelques identités vérifiées manuellement sont autoritaires sur
        # les anciennes cellules vides/erronées. On les écrit pendant l'export
        # de scores déjà prévu, afin de ne pas reconstruire une seconde fois le
        # très gros classeur uniquement pour une cellule ISIN.
        if "ISIN" in df.columns:
            from .etf_reference import load_etf_reference

            for ticker, reference in load_etf_reference()["by_ticker"].items():
                position = index.get(ticker.upper())
                if position is None or not reference:
                    continue
                df.at[position, "ISIN"] = reference["isin"]
                if "Secteur 1" in df.columns:
                    df.at[position, "Secteur 1"] = "ETF"

        new_rows: list[dict] = []
        n = 0
        for r in rows:
            tk = str(getattr(r, "ticker", "") or "").strip()
            if not tk:
                continue
            payload = {}
            for attr, col in writable.items():
                val = getattr(r, attr, None)
                if attr == "achat":
                    val = bool(val)
                elif (
                    attr == "chance_moat"
                    and str(getattr(r, "secteur", "") or "").strip().upper() == "ETF"
                ):
                    val = None
                payload[col] = val
            key = tk.upper()
            if key in index:
                for col, val in payload.items():
                    df.at[index[key], col] = val
            else:
                row = {tcol: tk}
                row.update(payload)
                new_rows.append(row)
            n += 1

        if new_rows:
            df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

        _save_main_sheet(df, path)
        return n
    except Exception as e:
        print(f"[broker_availability] Écriture scores ToutBroker: {e}")
        return 0


def update_broker_file_scores_isolated(rows, path: str | None = None) -> int:
    """Écrit les scores dans un sous-processus afin de ne pas bloquer l'API.

    La reconstruction d'un classeur de plus de 250 000 lignes monopolise le
    GIL d'openpyxl/pandas pendant plusieurs minutes. Le thread APScheduler qui
    exécute la pipeline est distinct, mais l'event loop Uvicorn ne pouvait plus
    répondre : Next affichait alors ``socket hang up``. Le sous-processus garde
    exactement le même format et l'appel reste synchrone pour éviter toute
    course avec les lectures/écritures suivantes du classeur.
    """
    from app.services.finance.catalog.repository import (
        append_analysis_results,
        normalized_catalog_is_active,
    )

    if path is None and normalized_catalog_is_active():
        return append_analysis_results(rows)

    import json
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    path = path or find_broker_file()
    if not path:
        return 0
    attrs = tuple(_RESULT_TO_BROKER_COL)
    payload = [
        {attr: getattr(row, attr, None) for attr in attrs}
        | {"ticker": str(getattr(row, "ticker", "") or "")}
        for row in rows
    ]
    cache_dir = Path(Config.DATA_DIR) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="broker-scores-",
            dir=cache_dir,
            delete=False,
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False, default=str)
            payload_path = Path(stream.name)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.services.finance.buffett.broker_score_writer",
                str(payload_path),
                str(path),
            ],
            cwd=Path(__file__).resolve().parents[4],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.returncode != 0:
            print(
                f"[broker_availability] Sous-processus scores en erreur: {completed.stderr.strip()}"
            )
            return 0
        try:
            return int(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return 0
    except Exception as exc:
        print(f"[broker_availability] Sous-processus scores impossible: {exc}")
        return 0
    finally:
        if payload_path is not None:
            try:
                payload_path.unlink(missing_ok=True)
            except OSError:
                pass


def aggregate_weights(alloc: list[dict]) -> dict[str, float]:
    """Pur : somme du « Poids total (%) » par ticker depuis une allocation.

    ``alloc`` est la sortie de ``discretize_allocation`` (une ligne par couple
    ticker/broker). Le poids d'une action = somme de ses lignes.
    """
    out: dict[str, float] = {}
    for row in alloc or []:
        tk = str(row.get("Ticker", "") or "").strip()
        if not tk:
            continue
        out[tk] = out.get(tk, 0.0) + float(row.get("Poids total (%)", 0) or 0)
    return {t: round(p, 4) for t, p in out.items()}


def current_target_weights(df, ticker_col: str = "Ticker Yahoo Finance") -> dict[str, float]:
    """Lit la dernière cible persistée dans ``Poids`` et la convertit en fractions."""
    if df is None or getattr(df, "empty", True) or "Poids" not in df.columns:
        return {}
    weights: dict[str, float] = {}
    for _, row in df.iterrows():
        ticker = str(row.get(ticker_col, "") or "").strip()
        if not ticker:
            continue
        try:
            fraction = max(float(row.get("Poids", 0) or 0), 0.0) / 100.0
        except (TypeError, ValueError):
            fraction = 0.0
        if fraction > 0:
            weights[ticker] = weights.get(ticker, 0.0) + fraction
    return weights


def update_broker_file_weights(
    alloc: list[dict],
    path: str | None = None,
    ticker_col: str = "Ticker Yahoo Finance",
    weight_col: str = "Poids",
) -> int:
    """Écrit le pourcentage d'investissement par action dans la colonne ``Poids``.

    Agrège l'allocation par ticker (somme des poids par broker), remet toute la
    colonne ``Poids`` à 0, puis inscrit le poids de chaque action allouée.
    Crée la colonne si elle n'existe pas. Retourne le nombre de tickers écrits.
    """
    weights = aggregate_weights(alloc)
    from app.services.finance.catalog.repository import (
        normalized_catalog_is_active,
        update_target_weights,
    )

    if path is None and normalized_catalog_is_active():
        return update_target_weights(weights)
    path = path or find_broker_file()
    if not path:
        return 0
    try:
        df = read_broker_excel(path)
        tcol = _find_ticker_col(df.columns, ticker_col) or ticker_col
        if tcol not in df.columns:
            return 0

        if weight_col not in df.columns:
            df[weight_col] = 0.0
        df[weight_col] = 0.0  # reset (les non-alloués passent à 0, pas de valeur obsolète)

        index: dict[str, int] = {}
        for i, k in df[tcol].astype(str).str.strip().items():
            index.setdefault(k, i)

        n = 0
        for tk, pct in weights.items():
            if tk in index:
                df.at[index[tk], weight_col] = pct
                n += 1
        _save_main_sheet(df, path)
        return n
    except Exception as e:
        print(f"[broker_availability] Écriture Poids ToutBroker: {e}")
        return 0


def merge_broker_columns(
    df_m,
    ticker_col: str = "Ticker Yahoo Finance",
    *,
    broker_table=None,
):
    """Ajoute à ``df_m`` une colonne de disponibilité par broker de Config.BUDGET_BROKERS,
    renommée exactement comme la clé Config pour que l'optimiseur la retrouve.

    Sans fichier ToutBroker.xlsx, ``df_m`` est renvoyé inchangé (tout disponible).
    """
    tbl = broker_table if broker_table is not None else load_broker_table()
    if tbl is None or getattr(tbl, "empty", True):
        return df_m
    try:
        tcol = _find_ticker_col(tbl.columns, ticker_col)
        if tcol is None:
            return df_m
        sub = tbl.copy()
        # Restreindre immédiatement le très gros catalogue aux tickers demandés
        # et à leurs cotations secondaires. L'ancienne version construisait un
        # index et 257 000 Series pandas à chaque fusion, même pour quelques
        # centaines de candidats, ce qui gelait l'état live plusieurs minutes.
        keys = [str(k).strip() for k in df_m[ticker_col].tolist()]
        requested = {
            key.upper() for key in keys if key and key.lower() not in {"nan", "none", "<na>"}
        }
        # Conversion explicite par élément, pour la même raison que `keys`
        # ci-dessous : `astype(str)` laisse passer les valeurs manquantes.
        sub[tcol] = [str(v).strip() for v in sub[tcol].tolist()]
        # Le tableur contient une ligne au ticker VIDE. Elle n'apporte rien et
        # brouille l'appariement des cotations : on l'écarte explicitement.
        blanks = sub[tcol].isin(["", "nan", "NaN", "None", "<NA>"])
        if bool(blanks.any()):
            print(
                f"    * {int(blanks.sum())} ligne(s) sans ticker ignorée(s) dans le fichier broker."
            )
            sub = sub[~blanks]
        fundamentals_col = next(
            (c for c in sub.columns if str(c).strip().casefold() == "fundamentals symbol"),
            None,
        )
        ticker_keys = sub[tcol].astype(str).str.strip().str.upper()
        if fundamentals_col is not None:
            primary_keys = sub[fundamentals_col].fillna("").astype(str).str.strip().str.upper()
            primary_keys = primary_keys.where(primary_keys.ne(""), ticker_keys)
        else:
            primary_keys = ticker_keys
        sub = sub[ticker_keys.isin(requested) | primary_keys.isin(requested)].copy()
        sub = sub.drop_duplicates(subset=[tcol], keep="last")
        lookup = sub.set_index(tcol)
        candidates_by_primary: dict[str, list] = {}
        for _, candidate in sub.iterrows():
            quote = str(candidate.get(tcol) or "").strip()
            primary = (
                str(candidate.get(fundamentals_col) or "").strip()
                if fundamentals_col is not None
                else ""
            ) or quote
            candidates_by_primary.setdefault(primary.upper(), []).append(candidate)

        out = df_m.copy()
        # `astype(str)` NE suffit PAS : les pandas récents préservent les valeurs
        # manquantes au lieu de les convertir en "nan", si bien qu'un flottant NaN
        # survivait jusqu'au `key.upper()` et faisait tomber toute la fusion —
        # exception avalée, disponibilité broker jamais appliquée, portefeuille
        # inachetable. La conversion explicite par élément est insensible à cela.
        execution_routes: list[dict[str, str]] = [dict() for _ in keys]

        def _blank(value) -> bool:
            try:
                import pandas as pd

                return bool(pd.isna(value)) or str(value).strip() == ""
            except (TypeError, ValueError):
                return value is None or str(value).strip() == ""

        def _metadata_value(key: str, column):
            if key in lookup.index:
                value = lookup.at[key, column]
                if not _blank(value):
                    return value
            candidates = candidates_by_primary.get(key.upper(), [])
            for candidate in candidates:
                value = candidate.get(column, None)
                if not _blank(value):
                    return value
            return None

        for broker in Config.BUDGET_BROKERS:
            col = _match_broker_column(broker, tbl.columns)
            if not col:
                continue
            states: list[bool | None] = []
            for index, key in enumerate(keys):
                candidates = candidates_by_primary.get(key.upper())
                if not candidates:
                    row = lookup.loc[key] if key in lookup.index else None
                    candidates = [row] if row is not None else []
                available = [row for row in candidates if _cell_state(row.get(col, None)) is True]
                all_states = [_cell_state(row.get(col, None)) for row in candidates]
                states.append(
                    True
                    if available
                    else False
                    if all_states and all(state is False for state in all_states)
                    else None
                )
                if available:
                    primary_available = [
                        row
                        for row in available
                        if str(row.get(tcol) or "").strip().upper() == key.upper()
                    ]

                    def _volume(row) -> float:
                        try:
                            value = float(row.get("Volume") or 0)
                            return value if value == value else 0.0
                        except (TypeError, ValueError):
                            return 0.0

                    selected = (
                        primary_available[0] if primary_available else max(available, key=_volume)
                    )
                    execution_routes[index][broker] = str(selected.get(tcol) or key).strip()
            out[broker] = states
        out["Execution Routes"] = execution_routes
        # Colonne ISIN (dédup ETF par identité exacte), si présente dans ToutBroker.
        isin_col = next((c for c in tbl.columns if str(c).strip().upper() == "ISIN"), None)
        if isin_col is not None:
            out["ISIN"] = [_metadata_value(k, isin_col) for k in keys]
        # Métadonnées utilisées par la présélection diversifiée des ETF et par
        # la pénalité de turnover. Elles restent informatives et ne sont jamais
        # interprétées comme des colonnes broker par `_get_broker_col`.
        for metadata_col in (
            "Nom",
            "Secteur 1",
            "Secteur 2",
            "Secteur 3",
            "Secteur 4",
            "Secteur 5",
            "Poids",
            "TTF",
            "Type",
            "Primary Market",
            "Primary MIC",
            "Fundamentals Symbol",
            "Encours",
            "AUM",
            "Fund Size",
            "Total Assets",
        ):
            source = next(
                (c for c in tbl.columns if str(c).strip().lower() == metadata_col.lower()),
                None,
            )
            if source is not None:
                out[metadata_col] = [_metadata_value(k, source) for k in keys]
        return out
    except Exception as e:
        # NE PLUS AVALER. Renvoyer `df_m` sans colonne de disponibilité revenait
        # à déclarer TOUS les titres achetables chez TOUS les brokers : le run
        # produisait alors un portefeuille inachetable — actions américaines,
        # canadiennes et coréennes allouées sur un PEA — sans autre trace qu'une
        # ligne de log noyée. Une disponibilité broker incalculable est une
        # erreur bloquante, pas un détail.
        import traceback

        traceback.print_exc()
        raise RuntimeError(
            "Disponibilité broker incalculable : sans elle, l'optimiseur "
            "considérerait tous les titres disponibles chez tous les brokers et "
            f"produirait un portefeuille inachetable. Cause : {e}"
        ) from e
