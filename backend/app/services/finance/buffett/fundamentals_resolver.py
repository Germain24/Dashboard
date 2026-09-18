"""Résolution cotation broker -> cotation Yahoo utilisée pour les fondamentaux."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FundamentalsLink:
    quote_symbol: str
    fundamentals_symbol: str
    identity_key: str


@dataclass(frozen=True, slots=True)
class InstrumentGroup:
    identity_key: str
    primary_symbol: str
    quote_symbols: tuple[str, ...]


def _text(value) -> str:
    try:
        import pandas as pd

        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip().upper()


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value) in {"1", "TRUE", "YES", "OUI", "VRAI"}


def build_fundamentals_links(table) -> dict[str, FundamentalsLink]:
    """Construit les liens à partir des colonnes du catalogue/ToutBroker.

    ``Fundamentals Symbol`` est autoritaire. Pour les anciens fichiers, un
    groupe ISIN possédant une unique ligne ``Primary Market`` est également
    résolu sans attendre une reconstruction complète.
    """
    if table is None or getattr(table, "empty", True):
        return {}
    from .broker_availability import _find_ticker_col

    ticker_col = _find_ticker_col(table.columns, "Ticker Yahoo Finance")
    if ticker_col is None:
        return {}
    columns = {
        str(column).strip().casefold(): column for column in table.columns
    }
    isin_col = columns.get("isin")
    primary_col = columns.get("primary market")
    fundamentals_col = columns.get("fundamentals symbol")

    # Sans ces colonnes, la résolution dégradait EN SILENCE : `primary` valait
    # False partout, aucun ISIN n'obtenait de cotation principale, chaque ticker
    # devenait son propre groupe et la propagation des fondamentaux vers les
    # cotations secondaires ne produisait RIEN — à chaque run, sans un mot. C'est
    # ce qui affamait Munich, Milan, Amsterdam et une grande partie de Londres.
    if primary_col is None or fundamentals_col is None:
        manquantes = [
            nom
            for nom, presente in (
                ("Primary Market", primary_col is not None),
                ("Fundamentals Symbol", fundamentals_col is not None),
            )
            if not presente
        ]
        print(
            f"    * ATTENTION : colonne(s) {', '.join(manquantes)} absente(s) du "
            "fichier broker. La cotation principale sera déduite du VOLUME "
            "(repli), au lieu de la donnée officielle."
        )

    volume_col = columns.get("volume")
    rows: list[tuple[str, str, bool, str]] = []
    volumes: dict[str, float] = {}
    for _, row in table.iterrows():
        ticker = _text(row.get(ticker_col))
        if not ticker:
            continue
        isin = _text(row.get(isin_col)) if isin_col is not None else ""
        primary = _truthy(row.get(primary_col)) if primary_col is not None else False
        explicit = (
            _text(row.get(fundamentals_col))
            if fundamentals_col is not None
            else ""
        )
        if volume_col is not None:
            try:
                value = float(row.get(volume_col) or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            volumes[ticker] = 0.0 if value != value else max(value, 0.0)
        rows.append((ticker, isin, primary, explicit))

    primary_by_isin: dict[str, str] = {}
    grouped: dict[str, list[tuple[str, bool]]] = {}
    for ticker, isin, primary, _ in rows:
        if isin:
            grouped.setdefault(isin, []).append((ticker, primary))
    for isin, candidates in grouped.items():
        primaries = sorted(ticker for ticker, primary in candidates if primary)
        if len(primaries) == 1:
            primary_by_isin[isin] = primaries[0]
            continue
        # Repli : la cotation la PLUS LIQUIDE du groupe ISIN. Un ISIN identifie
        # une seule et même société ; propager ses fondamentaux depuis sa ligne
        # la plus échangée est sûr, et infiniment préférable à ne rien propager.
        # S'applique aussi quand PLUSIEURS lignes se déclarent principales, cas
        # que l'ancienne condition `== 1` abandonnait purement et simplement.
        pool = primaries or sorted(ticker for ticker, _p in candidates)
        if len(pool) > 1:
            primary_by_isin[isin] = max(pool, key=lambda t: (volumes.get(t, 0.0), t))
        elif pool:
            primary_by_isin[isin] = pool[0]

    links: dict[str, FundamentalsLink] = {}
    for ticker, isin, _, explicit in rows:
        fundamental = explicit or primary_by_isin.get(isin, "") or ticker
        links[ticker] = FundamentalsLink(
            quote_symbol=ticker,
            fundamentals_symbol=fundamental,
            identity_key=isin or ticker,
        )
    return links


def load_fundamentals_links() -> dict[str, FundamentalsLink]:
    from .broker_availability import load_broker_table

    return build_fundamentals_links(load_broker_table())


def build_instrument_groups(
    tickers: list[str],
    links: dict[str, FundamentalsLink],
) -> list[InstrumentGroup]:
    """Regroupe l'univers par ISIN/cotation fondamentale, ordre déterministe.

    La cotation principale est ajoutée même si seul un ticker secondaire figure
    dans le fichier historique : elle devient l'unique tâche Yahoo, tandis que
    les symboles de ``quote_symbols`` restent les routes broker possibles.
    """
    grouped: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for raw_ticker in tickers:
        ticker = _text(raw_ticker)
        if not ticker:
            continue
        link = links.get(ticker)
        primary = _text(link.fundamentals_symbol) if link else ticker
        identity = _text(link.identity_key) if link else ticker
        key = (identity or ticker, primary or ticker)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        if ticker not in grouped[key]:
            grouped[key].append(ticker)
    return [
        InstrumentGroup(
            identity_key=identity,
            primary_symbol=primary,
            quote_symbols=tuple(quotes),
        )
        for identity, primary in order
        for quotes in (grouped[(identity, primary)],)
    ]
