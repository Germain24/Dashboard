"""Classification utilisée par le plafond sectoriel de l'optimiseur."""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np

from .breakdown import _canon_sector, load_classification

_GENERIC_CATEGORIES = {
    "",
    "action",
    "actions",
    "diversifie",
    "etf",
    "fonds",
    "inconnu",
    "n/a",
    "nan",
    "none",
    "sectoriel",
    "unknown",
}

_CATEGORY_MODIFIERS = {
    "court terme",
    "couvert devise",
    "couvert (devise)",
    "esg",
    "inverse -1x",
    "levier x2",
    "moyen/long terme",
    "physique",
    "synthetique",
}

# Zones géographiques : ce sont des PAYS, pas des compartiments sectoriels. Un
# ETF « USA » ou « Zone euro » sans look-through sectoriel se voyait attribuer un
# pseudo-secteur à son nom, qui apparaissait ensuite dans la contribution au
# risque sectoriel et consommait un plafond de secteur. Son exposition
# géographique est déjà portée par la contrainte pays (look-through ETF_Pays).
_GEOGRAPHIC_LABELS = {
    "monde", "world", "global", "international", "acwi",
    "usa", "etats-unis", "etats unis", "united states", "amerique du nord",
    "north america", "amerique", "america", "amerique latine", "latam",
    "europe", "zone euro", "eurozone", "euro", "europe hors royaume-uni",
    "asie", "asia", "asie pacifique", "asia pacific", "pacifique", "pacific",
    "emergents", "marches emergents", "emerging", "emerging markets",
    "japon", "japan", "chine", "china", "inde", "india", "royaume-uni",
    "united kingdom", "allemagne", "germany", "france", "suisse",
    "switzerland", "italie", "italy", "espagne", "spain", "canada",
    "australie", "australia", "coree du sud", "south korea", "taiwan",
    "bresil", "brazil", "mexique", "mexico", "afrique du sud", "south africa",
    "pays-bas", "netherlands", "belgique", "belgium", "suede", "sweden",
    "norvege", "norway", "danemark", "denmark", "finlande", "finland",
    "irlande", "ireland", "portugal", "autriche", "austria", "pologne",
    "poland", "israel", "singapour", "singapore", "hong kong",
    "nouvelle-zelande", "new zealand", "arabie saoudite", "saudi arabia",
}


def is_geographic_label(value) -> bool:
    """Vrai si le libellé désigne une zone géographique et non un secteur."""
    return _normalized_category(value) in _GEOGRAPHIC_LABELS


EQUITY_SECTORS = {
    "Technologie",
    "Sante",
    "Finance",
    "Conso. discretionnaire",
    "Conso. de base",
    "Energie",
    "Industrie",
    "Materiaux",
    "Communication",
    "Services aux collectivites",
    "Immobilier",
}


def _normalized_category(value) -> str:
    import unicodedata

    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode()
        .casefold()
    )


def _usable_category(value) -> str | None:
    text = " ".join(str(value or "").strip().split())
    key = _normalized_category(text)
    if key in _GENERIC_CATEGORIES or key in _CATEGORY_MODIFIERS:
        return None
    # Un libellé géographique reste une catégorie VALIDE ici : il sert à juger
    # l'éligibilité d'un ETF (un ETF Monde doit rester investissable). Il est en
    # revanche écarté des compartiments SECTORIELS, cf. constrained_sector_labels
    # et sector_lookthrough.sector_matrix.
    canonical = _canon_sector(text)
    return None if _normalized_category(canonical) in _GENERIC_CATEGORIES else canonical


PRECIOUS_METALS_NAME = re.compile(
    r"\b(gold|bullion|precious\s+metals?|metaux\s+precieux|silver|platinum|palladium)\b",
    re.IGNORECASE,
)
# « Goldman » n'est pas de l'or : la limite de mot après « gold » l'exclut.
# « Argent » n'est PAS dans le motif : trop de faux positifs (Argentina, Banco
# Argentina...) pour un gain nul, les fonds argent se nommant « Silver ».


def is_precious_metals_fund(name: str) -> bool:
    """Le NOM d'un fonds l'identifie-t-il comme exposé aux métaux précieux ?

    Filet de sécurité sur la classification manuelle. Cas réel : « UBS Solactive
    Global **Pure Gold Miners** UCITS ETF » est renseigné dans ToutBroker en
    Actions / Diversifié / **Monde**. Il échappait donc au plafond « Or » (10 %)
    et tombait sous le plafond par défaut (25 %), si bien qu'il pouvait cohabiter
    avec un GDX correctement étiqueté sans qu'aucune contrainte ne lie les deux —
    10,5 % de mineurs d'or dans un portefeuille censé en plafonner 10.

    Les mineurs d'or sont des actions, mais leur risque suit le métal : c'est
    bien le compartiment « Or » qui doit les borner, comme le fait déjà GDX.
    """
    return bool(PRECIOUS_METALS_NAME.search(str(name or "")))


def resolve_risk_categories(
    yahoo_sectors: dict[str, str],
    *,
    broker_table=None,
) -> tuple[dict[str, str], dict]:
    """Résout la catégorie de risque AVANT le téléchargement des historiques.

    Priorité : secteur Yahoo exploitable ; pour un ETF, Secteur 4 puis Secteur 5,
    Secteur 3 et Secteur 2 ; pour une action sans secteur Yahoo, Secteur 1 puis
    les autres colonnes manuelles. Les simples modificateurs (ESG, physique,
    synthétique, couverture de devise, levier...) ne créent jamais un compartiment.

    Dernier mot au NOM du fonds pour les métaux précieux : la classification
    manuelle a des trous, et un ETF de mineurs d'or classé « Monde » échappait au
    plafond qui le vise (cf. ``is_precious_metals_fund``).
    """
    from .broker_availability import (
        _find_ticker_col,
        load_broker_table,
        merge_broker_columns,
    )

    table = broker_table if broker_table is not None else load_broker_table()
    requested = {
        str(ticker).strip().upper(): str(sector or "")
        for ticker, sector in yahoo_sectors.items()
        if str(ticker).strip()
    }
    rows: dict[str, dict[str, str]] = {}
    if table is not None and not getattr(table, "empty", True):
        # Les résultats du run utilisent souvent le ticker principal Yahoo,
        # tandis que les secteurs PEA sont portés par une cotation secondaire
        # Bourse Direct du même ``Fundamentals Symbol``. Lire uniquement la ligne
        # exacte du ticker principal classait alors l'ETF « inconnu » et le
        # supprimait. Réutiliser la même propagation que les disponibilités
        # broker rend aussi les métadonnées de la cotation exécutable visibles.
        import pandas as pd

        requested_table = merge_broker_columns(
            pd.DataFrame({"Ticker Yahoo Finance": list(requested)}),
            broker_table=table,
        )
        ticker_col = _find_ticker_col(
            requested_table.columns,
            "Ticker Yahoo Finance",
        )
        columns = {
            str(column).strip().casefold(): column
            for column in requested_table.columns
        }
        if ticker_col is not None:
            for _, row in requested_table.iterrows():
                ticker = str(row.get(ticker_col) or "").strip().upper()
                if ticker and ticker in requested:
                    rows[ticker] = {
                        name: str(row.get(column) or "").strip()
                        for name, column in columns.items()
                        if name.startswith("secteur")
                    }
                    # Le nom du fonds sert de filet quand les colonnes manuelles
                    # se trompent de compartiment (cf. is_precious_metals_fund).
                    if "nom" in columns:
                        rows[ticker]["_nom"] = str(row.get(columns["nom"]) or "").strip()

    resolved: dict[str, str] = {}
    sources: dict[str, int] = {}
    excluded: list[str] = []
    metal_overrides: list[tuple[str, str]] = []
    for ticker, yahoo_sector in requested.items():
        metadata = rows.get(ticker, {})
        category = _usable_category(yahoo_sector)
        source = "yahoo"
        if category is None:
            is_etf = _normalized_category(metadata.get("secteur 1")) == "etf"
            order = (
                ("secteur 4", "secteur 5", "secteur 3", "secteur 2")
                if is_etf
                else ("secteur 1", "secteur 4", "secteur 5", "secteur 3", "secteur 2")
            )
            for column in order:
                category = _usable_category(metadata.get(column))
                if category is not None:
                    source = column.replace(" ", "_")
                    break
        # Filet métaux précieux : le nom prime sur une classification manuelle
        # qui rangerait un fonds d'or ailleurs. Ne s'applique QUE dans ce sens —
        # jamais pour retirer un titre de « Or ».
        if is_precious_metals_fund(metadata.get("_nom", "")) and category != "Or":
            metal_overrides.append((ticker, category or "(aucune)"))
            category = "Or"
            source = "nom_metaux_precieux"
        if category is None:
            excluded.append(ticker)
            continue
        resolved[ticker] = category
        sources[source] = sources.get(source, 0) + 1

    if metal_overrides:
        details = ", ".join(f"{t} ({was})" for t, was in metal_overrides[:10])
        print(
            f"    * {len(metal_overrides)} fonds reclasses en 'Or' d'apres leur nom "
            f"(classification manuelle divergente) : {details}"
            f"{'...' if len(metal_overrides) > 10 else ''}"
        )

    return resolved, {
        "method": "yahoo_then_manual_sector_4_5",
        "requested": len(requested),
        "classified": len(resolved),
        "excluded": len(excluded),
        "excluded_tickers": excluded,
        "sources": sources,
        "precious_metals_overrides": [t for t, _ in metal_overrides],
    }


def constrained_sector_labels(
    tickers: Iterable[str],
    *,
    is_etf: Iterable[bool] | None = None,
    fallback_sectors: dict[str, str] | None = None,
) -> list[str | None]:
    """Retourne le compartiment plafonné de chaque instrument.

    Les catégories résolues en amont couvrent les secteurs Yahoo et les classes
    ETF manuelles. ``None`` signifie que l'instrument aurait dû être exclu avant
    le téléchargement de ses cours.
    """
    normalized = [str(ticker).strip().upper() for ticker in tickers]
    flags = list(is_etf) if is_etf is not None else [False] * len(normalized)
    _, classified = load_classification()
    fallback = {
        str(ticker).strip().upper(): _canon_sector(sector)
        for ticker, sector in (fallback_sectors or {}).items()
    }
    labels: list[str | None] = []
    for ticker, _etf in zip(normalized, flags, strict=True):
        # La catégorie résolue en amont est prioritaire. Elle peut être un secteur
        # Yahoo ou un compartiment manuel légitime (Or, Monde, Growth...).
        category = _usable_category(fallback.get(ticker))
        if category is None:
            category = _usable_category(classified.get(ticker))
        # Une zone géographique n'ouvre pas de compartiment sectoriel : sinon un
        # ETF « USA » consommerait un plafond de secteur à lui seul et pèserait
        # dans la contribution au risque sectoriel sous un nom de pays. Sa
        # concentration géographique relève du plafond pays.
        if category is not None and is_geographic_label(category):
            category = None
        labels.append(category)
    return labels


class SectorCaps:
    """Plafond de capital par compartiment de risque : défaut + surcharges.

    Les clés des surcharges sont canonisées à la construction, sinon un ETF
    étiqueté « Métaux précieux » échapperait au plafond défini pour « Or ».
    """

    __slots__ = ("default", "_overrides")

    def __init__(self, default: float, overrides=None) -> None:
        self.default = float(default)
        self._overrides: dict[str, float] = {}
        for label, cap in (overrides or {}).items():
            key = _normalized_category(_canon_sector(str(label)))
            if not key:
                continue
            try:
                self._overrides[key] = float(cap)
            except (TypeError, ValueError):
                continue

    @classmethod
    def from_config(cls) -> SectorCaps:
        """Lit ``Config`` À L'APPEL : plusieurs tests monkeypatchent MAX_SECTOR_PCT."""
        from .config import Config

        return cls(
            float(Config.MAX_SECTOR_PCT),
            dict(getattr(Config, "MAX_SECTOR_PCT_OVERRIDES", None) or {}),
        )

    def for_label(self, label) -> float:
        if not self._overrides:
            return self.default
        return self._overrides.get(
            _normalized_category(_canon_sector(str(label or ""))), self.default
        )

    def as_array(self, names: Iterable[str]) -> np.ndarray:
        return np.array([self.for_label(name) for name in names], dtype=float)

    def is_uniform(self) -> bool:
        return not self._overrides or all(
            abs(cap - self.default) <= 1e-12 for cap in self._overrides.values()
        )

    def max(self) -> float:
        return max([self.default, *self._overrides.values()])

    def min(self) -> float:
        return min([self.default, *self._overrides.values()])

    def as_dict(self) -> dict[str, float]:
        return dict(self._overrides)


def as_sector_caps(value) -> SectorCaps:
    """Accepte un ``float`` (rétro-compatible) ou un ``SectorCaps`` déjà construit."""
    if isinstance(value, SectorCaps):
        return value
    if isinstance(value, dict):
        from .config import Config

        return SectorCaps(float(Config.MAX_SECTOR_PCT), value)
    return SectorCaps(float(value))


def sector_exposures(
    weights,
    labels: list[str | None],
) -> dict[str, float]:
    exposures: dict[str, float] = {}
    for weight, label in zip(weights, labels, strict=True):
        if label:
            exposures[label] = exposures.get(label, 0.0) + max(float(weight), 0.0)
    return dict(sorted(exposures.items()))


UNASSIGNED_SECTOR = "Secteur non renseigné"


def with_unassigned_sector(sector_matrix):
    """Complète la matrice des secteurs par la part NON ATTRIBUÉE de chaque ligne.

    Une ligne de ``sector_matrix`` somme à 1 quand la composition sectorielle est
    connue, et à 0 sinon — cas de la quasi-totalité des ETF, dont l'étiquette est
    géographique (« Monde », « USA ») et pour lesquels on refuse délibérément
    d'inventer un pseudo-secteur portant un nom de pays.

    Sans cette colonne, la ligne nulle disparaissait de TOUS les termes du bonus
    de diversification : le poids de l'ETF s'évaporait du calcul et il n'obtenait
    rien, alors que ses PAYS étaient parfaitement connus. Mesuré, un ETF réparti
    sur deux pays marquait 0,0 au lieu de 0,5 — l'instrument le plus diversifié
    du portefeuille traité comme le moins diversifié.

    Rien n'est inventé ici : on ne prête aucun secteur à cette part, on cesse
    seulement de la faire disparaître. La règle « une donnée absente reste
    explicitement inconnue et n'hérite jamais de la moyenne des autres » est donc
    respectée — seule la ventilation sectorielle manque, pas les pays.

    La matrice reçue n'est jamais modifiée : elle alimente AUSSI les contraintes
    de risque sectoriel (plafonds par secteur), où ce compartiment n'a rien à
    faire. Le résidu doit rester cantonné au bonus.
    """
    matrix = np.asarray(sector_matrix, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("sector_matrix doit être une matrice [tickers x secteurs]")
    residue = np.maximum(1.0 - matrix.sum(axis=1), 0.0)
    return np.column_stack([matrix, residue])


def sector_country_exposures(
    weights,
    labels: list[str | None],
    country_matrix,
    countries: Iterable[str],
    *,
    sector_matrix=None,
    sector_names: Iterable[str] | None = None,
    joint_matrix=None,
) -> dict[str, dict[str, float]]:
    """Croise les secteurs contraints avec les expositions pays look-through.

    ``country_matrix[i, j]`` est la fraction du ticker ``i`` exposée au pays
    ``j``. Les ETF/instruments dont ``labels[i]`` vaut ``None`` restent hors de
    cette matrice : sans look-through sectoriel de leurs constituants, leur
    attribuer un secteur économique serait trompeur.
    """
    w = np.maximum(np.asarray(weights, dtype=float).reshape(-1), 0.0)
    matrix = np.asarray(country_matrix, dtype=float)
    country_names = [str(country) for country in countries]
    if matrix.size == 0:
        return {}
    if matrix.ndim != 2 or matrix.shape != (len(w), len(country_names)):
        raise ValueError("country_matrix doit avoir la forme [tickers x pays]")
    if len(labels) != len(w):
        raise ValueError("labels et weights doivent avoir la même longueur")

    if joint_matrix is not None:
        joint = np.asarray(joint_matrix, dtype=float)
        names = [str(value) for value in (sector_names or [])]
        if joint.shape != (len(w), len(names), len(country_names)):
            raise ValueError("joint_matrix doit avoir la forme [tickers x secteurs x pays]")
        result: dict[str, dict[str, float]] = {}
        for index, sector in enumerate(names):
            values = joint[:, index, :].T @ w
            by_country = {
                country: float(value)
                for country, value in zip(country_names, values, strict=True)
                if float(value) > 1e-12
            }
            if by_country:
                result[sector] = dict(sorted(by_country.items()))
        return result

    if sector_matrix is not None:
        sectors_matrix = np.asarray(sector_matrix, dtype=float)
        names = [str(value) for value in (sector_names or [])]
        if sectors_matrix.shape != (len(w), len(names)):
            raise ValueError("sector_matrix et sector_names sont incompatibles")
        # La part sans ventilation sectorielle est montrée sous son propre nom
        # plutôt que passée sous silence : c'est elle qui domine chez les ETF.
        sectors_matrix = with_unassigned_sector(sectors_matrix)
        names = [*names, UNASSIGNED_SECTOR]
        result: dict[str, dict[str, float]] = {}
        for index, sector in enumerate(names):
            values = matrix.T @ (w * sectors_matrix[:, index])
            by_country = {
                country: float(value)
                for country, value in zip(country_names, values, strict=True)
                if float(value) > 1e-12
            }
            if by_country:
                result[sector] = dict(sorted(by_country.items()))
        return result

    result = {}
    for sector in sorted({label for label in labels if label}):
        rows = np.asarray([label == sector for label in labels], dtype=bool)
        values = matrix[rows].T @ w[rows]
        by_country = {
            country: float(value)
            for country, value in zip(country_names, values, strict=True)
            if float(value) > 1e-12
        }
        if by_country:
            result[str(sector)] = dict(sorted(by_country.items()))
    return result


def sector_country_diversification_score(
    weights,
    labels: list[str | None],
    country_matrix,
    *,
    sector_matrix=None,
    joint_matrix=None,
    country_names: Iterable[str] | None = None,
    significant_exposure: float = 0.01,
    significant_weight: float = 0.25,
) -> float:
    """Score continu de diversité pays à l'intérieur de chaque secteur.

    Chaque contribution combine ``log(N_effectif)`` et un petit complément
    ``0,25 × log(N_significatifs)``. ``N_effectif`` mesure à la fois le nombre
    de pays et l'égalité de leurs poids ; un pays est significatif au-delà de
    1 % de l'exposition totale. Le logarithme fournit un rendement décroissant
    et évite tout plafond externe ou division instable par un écart-type.
    """
    w = np.maximum(np.asarray(weights, dtype=float).reshape(-1), 0.0)
    matrix = np.asarray(country_matrix, dtype=float)
    if matrix.size == 0:
        return 0.0
    if matrix.ndim != 2 or matrix.shape[0] != len(w):
        raise ValueError("country_matrix doit avoir une ligne par ticker")
    if len(labels) != len(w):
        raise ValueError("labels et weights doivent avoir la même longueur")

    score = 0.0
    if joint_matrix is not None:
        joint = np.asarray(joint_matrix, dtype=float)
        if joint.ndim != 3 or joint.shape[0] != len(w) or joint.shape[2] != matrix.shape[1]:
            raise ValueError("joint_matrix incompatible avec weights/country_matrix")
        names = [str(value) for value in (country_names or range(matrix.shape[1]))]
        unknown = np.asarray([
            name.casefold() in {"inconnu", "unknown", "autres", "other"}
            for name in names
        ], dtype=bool)
        for index in range(joint.shape[1]):
            buckets = joint[:, index, :].T @ w
            exposure = float(np.sum(buckets))
            if exposure <= 1e-12:
                continue
            score += float(
                country_diversification_score_from_buckets(
                    buckets,
                    unknown,
                    significant_exposure=significant_exposure,
                    significant_weight=significant_weight,
                )[0]
            )
        return float(score)

    if sector_matrix is not None:
        sectors_matrix = np.asarray(sector_matrix, dtype=float)
        if sectors_matrix.ndim != 2 or sectors_matrix.shape[0] != len(w):
            raise ValueError("sector_matrix doit avoir une ligne par ticker")
        # Sans ce complément, tout poids dont le secteur est inconnu — donc la
        # quasi-totalité des ETF — sortait purement et simplement de la somme.
        sectors_matrix = with_unassigned_sector(sectors_matrix)
        for index in range(sectors_matrix.shape[1]):
            buckets = matrix.T @ (w * sectors_matrix[:, index])
            exposure = float(np.sum(buckets))
            if exposure <= 1e-12:
                continue
            score += float(
                country_diversification_score_from_buckets(
                    buckets,
                    np.zeros(matrix.shape[1], dtype=bool),
                    significant_exposure=significant_exposure,
                    significant_weight=significant_weight,
                )[0]
            )
        return float(score)
    for sector in {label for label in labels if label}:
        rows = np.asarray([label == sector for label in labels], dtype=bool)
        buckets = matrix[rows].T @ w[rows]
        exposure = float(np.sum(buckets))
        if exposure <= 1e-12:
            continue
        score += float(
            country_diversification_score_from_buckets(
                buckets,
                np.zeros(matrix.shape[1], dtype=bool),
                significant_exposure=significant_exposure,
                significant_weight=significant_weight,
            )[0]
        )
    return float(score)


def country_diversification_score_from_buckets(
    buckets,
    unknown_mask,
    *,
    significant_exposure: float = 0.01,
    significant_weight: float = 0.25,
) -> np.ndarray:
    """Calcule le score pays pour des paniers ``pays × portefeuilles``.

    ``buckets`` contient des expositions absolues, pas des parts normalisées.
    Les pays inconnus sont exclus du nombre effectif et leur poids réduit la
    couverture connue. Le résultat est vectorisé afin d'être utilisable dans
    la boucle de population de l'optimiseur.
    """
    values = np.maximum(np.asarray(buckets, dtype=float), 0.0)
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2:
        raise ValueError("buckets doit être un tableau pays × portefeuilles")
    unknown = np.asarray(unknown_mask, dtype=bool).reshape(-1)
    if unknown.size != values.shape[0]:
        raise ValueError("unknown_mask doit avoir une ligne par pays")

    exposure = values.sum(axis=0)
    known_values = values[~unknown]
    known_exposure = known_values.sum(axis=0) if known_values.size else np.zeros_like(exposure)
    valid = (exposure > 1e-12) & (known_exposure > 1e-12)
    out = np.zeros(values.shape[1], dtype=float)
    if not valid.any():
        return out

    shares = known_values[:, valid] / known_exposure[valid]
    hhi = np.sum(shares * shares, axis=0)
    effective = 1.0 / np.maximum(hhi, 1e-12)
    significant = np.sum(
        known_values[:, valid] >= max(float(significant_exposure), 0.0),
        axis=0,
    )
    coverage = known_exposure[valid] / exposure[valid]
    value = (
        np.log(np.maximum(effective, 1.0))
        + max(float(significant_weight), 0.0)
        * np.log(np.maximum(significant, 1.0))
    )
    out[valid] = exposure[valid] * coverage * np.maximum(value, 0.0)
    return out


def geographic_diversification_factors(
    country_buckets,
    region_buckets,
    *,
    country_names: Iterable[str] | None = None,
    region_names: Iterable[str] | None = None,
    significant_exposure: float = 0.01,
    country_std_exponent: float = 20.0,
    region_std_exponent: float = 20.0,
) -> dict[str, np.ndarray]:
    """Calcule les trois facteurs du bonus géographique global.

    ``country_buckets`` et ``region_buckets`` sont des tableaux
    ``compartiment × portefeuille`` contenant des expositions absolues. Le
    bonus combine les égalités exponentielles pays/régions et le nombre de
    pays significatifs. Les seaux inconnus ne peuvent pas être récompensés.
    """
    country = _geographic_axis_factors(
        country_buckets,
        country_names,
        significant_exposure=significant_exposure,
        std_exponent=country_std_exponent,
    )
    region = _geographic_axis_factors(
        region_buckets,
        region_names,
        significant_exposure=significant_exposure,
        std_exponent=region_std_exponent,
    )
    count_bonus = np.log1p(country["count"])
    return {
        "combined": country["equality"] * region["equality"] * count_bonus,
        "country_equality": country["equality"],
        "region_equality": region["equality"],
        "country_count_bonus": count_bonus,
        "country_std": country["std"],
        "region_std": region["std"],
        "country_coverage": country["coverage"],
        "region_coverage": region["coverage"],
        "country_count": country["count"],
    }


def _geographic_axis_factors(
    buckets,
    names: Iterable[str] | None,
    *,
    significant_exposure: float,
    std_exponent: float,
) -> dict[str, np.ndarray]:
    values = np.maximum(np.asarray(buckets, dtype=float), 0.0)
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2:
        raise ValueError("buckets doit être un tableau compartiment × portefeuille")
    labels = [str(value) for value in (names or range(values.shape[0]))]
    if len(labels) != values.shape[0]:
        raise ValueError("names doit avoir une entrée par compartiment")
    unknown = np.asarray([
        name.casefold() in {"inconnu", "unknown", "autres", "other"}
        for name in labels
    ], dtype=bool)
    known = values[~unknown]
    total = values.sum(axis=0)
    known_total = known.sum(axis=0) if known.size else np.zeros(values.shape[1])
    coverage = known_total / np.maximum(total, 1e-12)
    shares = known / np.maximum(known_total, 1e-12)
    active = known >= max(float(significant_exposure), 0.0)
    count = active.sum(axis=0).astype(float)
    mean = np.divide((shares * active).sum(axis=0), np.maximum(count, 1.0))
    variance = np.divide(
        (((shares - mean[None, :]) ** 2) * active).sum(axis=0),
        np.maximum(count, 1.0),
    )
    std = np.sqrt(np.maximum(variance, 0.0))
    valid = (known_total > 1e-12) & (count > 0)
    equality = np.exp(-max(float(std_exponent), 0.0) * std) * coverage
    equality = np.where(valid, equality, 0.0)
    return {
        "equality": equality,
        "std": np.where(valid, std, 0.0),
        "coverage": np.where(valid, coverage, 0.0),
        "count": np.where(valid, count, 0.0),
    }


def sector_country_diversification_components(
    weights,
    country_matrix,
    sector_matrix,
    *,
    joint_matrix=None,
    country_names: Iterable[str] | None = None,
    significant_exposure: float = 0.01,
    significant_weight: float = 0.25,
) -> np.ndarray:
    """Contribution de chaque secteur au score pays, puis du résidu inconnu.

    La version scalaire ne permettait pas de neutraliser uniquement le secteur
    qui dépassait son budget de risque : l'optimiseur supprimait alors le bonus
    de *tout* le portefeuille. Cette forme détaillée conserve la même somme,
    mais rend possible un filtrage secteur par secteur.
    """
    w = np.maximum(np.asarray(weights, dtype=float).reshape(-1), 0.0)
    countries = np.asarray(country_matrix, dtype=float)
    if joint_matrix is not None:
        joint = np.asarray(joint_matrix, dtype=float)
        if joint.ndim != 3 or joint.shape[0] != len(w) or joint.shape[2] != countries.shape[1]:
            raise ValueError("joint_matrix incompatible avec weights/country_matrix")
        names = [str(value) for value in (country_names or range(countries.shape[1]))]
        unknown = np.asarray([
            name.casefold() in {"inconnu", "unknown", "autres", "other"}
            for name in names
        ], dtype=bool)
        out = np.zeros(joint.shape[1], dtype=float)
        for index in range(joint.shape[1]):
            buckets = joint[:, index, :].T @ w
            exposure = float(np.sum(buckets))
            if exposure <= 1e-12:
                continue
            out[index] = float(
                country_diversification_score_from_buckets(
                    buckets,
                    unknown,
                    significant_exposure=significant_exposure,
                    significant_weight=significant_weight,
                )[0]
            )
        return out

    sectors = with_unassigned_sector(np.asarray(sector_matrix, dtype=float))
    if countries.ndim != 2 or countries.shape[0] != len(w):
        raise ValueError("country_matrix doit avoir une ligne par ticker")
    if sectors.ndim != 2 or sectors.shape[0] != len(w):
        raise ValueError("sector_matrix doit avoir une ligne par ticker")
    out = np.zeros(sectors.shape[1], dtype=float)
    for index in range(sectors.shape[1]):
        buckets = countries.T @ (w * sectors[:, index])
        exposure = float(np.sum(buckets))
        if exposure <= 1e-12:
            continue
        out[index] = float(
            country_diversification_score_from_buckets(
                buckets,
                np.zeros(countries.shape[1], dtype=bool),
                significant_exposure=significant_exposure,
                significant_weight=significant_weight,
            )[0]
        )
    return out


def sector_country_deficit_penalty(
    weights,
    country_matrix,
    sector_matrix,
    *,
    coefficient: float,
    medium_exposure: float = 0.05,
    large_exposure: float = 0.10,
    joint_matrix=None,
    country_names: Iterable[str] | None = None,
) -> float:
    """Petit malus quand un secteur matériel manque de pays *effectifs*.

    Entre ``medium_exposure`` et ``large_exposure``, la cible vaut deux pays
    équilibrés ; au-dessus, trois. Les secteurs plus petits et la colonne de
    secteur non renseigné ne sont jamais contraints. Le déficit est normalisé,
    quadratique et pondéré par l'exposition : une micro-poche ne peut donc pas
    piloter l'allocation entière.
    """
    k = max(float(coefficient), 0.0)
    if k <= 0:
        return 0.0
    w = np.maximum(np.asarray(weights, dtype=float).reshape(-1), 0.0)
    countries = np.asarray(country_matrix, dtype=float)
    sectors = np.asarray(sector_matrix, dtype=float)
    if countries.ndim != 2 or countries.shape[0] != len(w):
        raise ValueError("country_matrix doit avoir une ligne par ticker")
    if sectors.ndim != 2 or sectors.shape[0] != len(w):
        raise ValueError("sector_matrix doit avoir une ligne par ticker")
    medium = max(float(medium_exposure), 0.0)
    large = max(float(large_exposure), medium)
    penalty = 0.0
    joint = None if joint_matrix is None else np.asarray(joint_matrix, dtype=float)
    if joint is not None and (
        joint.ndim != 3
        or joint.shape != (len(w), sectors.shape[1], countries.shape[1])
    ):
        raise ValueError("joint_matrix incompatible avec les matrices secteur/pays")
    names = [str(value) for value in (country_names or range(countries.shape[1]))]
    unknown = np.asarray([
        name.casefold() in {"inconnu", "unknown", "autres", "other"}
        for name in names
    ], dtype=bool)
    for index in range(sectors.shape[1]):
        buckets = (
            joint[:, index, :].T @ w
            if joint is not None
            else countries.T @ (w * sectors[:, index])
        )
        exposure = float(np.sum(buckets))
        target = 3.0 if exposure >= large else (2.0 if exposure >= medium else 0.0)
        if target <= 0 or exposure <= 1e-12:
            continue
        shares = buckets / exposure
        hhi = float(np.sum(shares[~unknown] ** 2) + np.sum(shares[unknown]))
        effective = 1.0 / max(hhi, 1e-12)
        deficit = max(target - effective, 0.0) / target
        penalty += exposure * deficit * deficit
    return float(k * penalty)


def sector_downside_risk_from_context(
    simulated_returns,
    labels: list[str | None],
    context: dict,
    *,
    downside_weight: float = 1.0,
    sector_matrix=None,
    sector_names: Iterable[str] | None = None,
) -> dict:
    """Attribue le CVaR et la semi-déviation aux secteurs, par candidat.

    ``context`` provient de ``benchmark_relative_batch_details`` et contient les
    poids normalisés, les indices exacts des scénarios de queue et les pertes de
    portefeuille. Les contributions suivent l'attribution d'Euler : elles
    incorporent donc la volatilité du secteur ET ses corrélations avec le reste
    du portefeuille. Les actifs sans secteur restent dans le risque total mais
    ne sont attribués à aucun secteur économique.
    """
    sim = np.asarray(simulated_returns, dtype=float)
    weights = np.asarray(context["weights"], dtype=float)
    tail_indices = np.asarray(context["tail_indices"], dtype=int)
    downside = np.asarray(context["downside"], dtype=float)
    dd_daily = np.asarray(context["downside_deviation_daily"], dtype=float)
    cvar_daily = np.asarray(context["cvar_daily"], dtype=float)
    if weights.ndim != 2 or sim.ndim != 2 or sim.shape[1] != weights.shape[0]:
        raise ValueError("simulated_returns et weights ont des formes incompatibles")
    if len(labels) != weights.shape[0]:
        raise ValueError("labels doit avoir une entrée par ticker")

    matrix = None if sector_matrix is None else np.asarray(sector_matrix, dtype=float)
    if matrix is not None:
        sectors = [str(value) for value in (sector_names or [])]
        if matrix.shape != (weights.shape[0], len(sectors)):
            raise ValueError("sector_matrix et sector_names sont incompatibles")
    else:
        sectors = sorted({str(label) for label in labels if label})
    n_candidates = weights.shape[1]
    cvar_by_sector = np.zeros((len(sectors), n_candidates), dtype=float)
    downside_by_sector = np.zeros_like(cvar_by_sector)
    for sector_index, sector in enumerate(sectors):
        if matrix is None:
            rows = np.asarray([label == sector for label in labels], dtype=bool)
            sector_returns = sim[:, rows] @ weights[rows]
        else:
            sector_returns = sim @ (weights * matrix[:, sector_index, None])
        sector_tail = np.take_along_axis(sector_returns, tail_indices, axis=0)
        cvar_by_sector[sector_index] = -sector_tail.mean(axis=0, dtype=np.float64)
        numerator = np.mean(downside * sector_returns, axis=0, dtype=np.float64)
        downside_by_sector[sector_index] = np.divide(
            numerator,
            dd_daily,
            out=np.zeros_like(numerator, dtype=float),
            where=dd_daily > 1e-12,
        )

    composite = cvar_by_sector + max(float(downside_weight), 0.0) * downside_by_sector
    total = cvar_daily + max(float(downside_weight), 0.0) * dd_daily
    shares = np.divide(
        composite,
        total[None, :],
        out=np.zeros_like(composite),
        where=total[None, :] > 1e-12,
    )
    return {
        "sectors": sectors,
        "cvar_contributions": cvar_by_sector,
        "downside_contributions": downside_by_sector,
        "composite_contributions": composite,
        "risk_shares": shares,
        "total_composite_risk": total,
    }


def sector_downside_risk_penalty(
    risk_details: dict,
    *,
    max_risk_share: float | np.ndarray,
    coefficient: float | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Pénalité quadratique et masque de dépassement du budget de risque."""
    shares = np.asarray(risk_details["risk_shares"], dtype=float)
    n_candidates = shares.shape[1] if shares.ndim == 2 else 0
    if shares.size == 0:
        return np.zeros(n_candidates, dtype=float), np.zeros(n_candidates, dtype=bool)
    caps = np.asarray(max_risk_share, dtype=float)
    coefficients = np.asarray(coefficient, dtype=float)
    if caps.ndim == 0:
        caps = np.full(shares.shape[0], max(float(caps), 0.0))
    if coefficients.ndim == 0:
        coefficients = np.full(shares.shape[0], max(float(coefficients), 0.0))
    if caps.shape != (shares.shape[0],) or coefficients.shape != (shares.shape[0],):
        raise ValueError("budgets/coefficient de risque incompatibles avec les secteurs")
    excess = np.maximum(shares - np.maximum(caps, 0.0)[:, None], 0.0)
    return (
        np.sum(np.maximum(coefficients, 0.0)[:, None] * excess * excess, axis=0),
        np.any(excess > 1e-12, axis=0),
    )
