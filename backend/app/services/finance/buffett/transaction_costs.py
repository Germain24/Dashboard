"""Frais de rebalancement par broker, place de cotation et devise.

Barème Bourse Direct/PEA : conditions applicables au 6 janvier 2026 fournies par
l'utilisateur. Trading 212 : courtage/garde gratuits, FX 0,15 %, plus taxes locales.
"""

from __future__ import annotations

import re

import numpy as np

from .config import Config
from .currency import SUFFIX_CCY

_EURONEXT_DOMESTIC = {"PA", "AS", "BR"}
_EU_EEA_SUFFIXES = {
    "PA", "AS", "BR", "LS", "DE", "F", "MC", "MI", "VI", "HE", "IR",
    "ST", "OL", "CO",
}


def _clean(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _is_trading212(broker: str) -> bool:
    cleaned = _clean(broker)
    return "TRADING212" in cleaned or "TRADDING212" in cleaned or cleaned == "T212"


def _is_bourse_direct(broker: str) -> bool:
    cleaned = _clean(broker)
    return "BOURSEDIRECT" in cleaned or "BOURSDIRECT" in cleaned


def _suffix(ticker: str) -> str:
    return ticker.rsplit(".", 1)[1].upper() if "." in ticker else ""


def _currency(ticker: str) -> str:
    return SUFFIX_CCY.get(_suffix(ticker), "USD")


def ttf_tickers_from_dataframe(df, ticker_col: str = "Ticker Yahoo Finance") -> set[str]:
    """Liste TTF explicite depuis Config et, si présente, colonne `TTF` du tableur."""
    out = {str(t).strip().upper() for t in Config.FRENCH_TTF_TICKERS}
    if df is None or getattr(df, "empty", True):
        return out
    ttf_col = next(
        (c for c in df.columns if str(c).strip().upper() in {"TTF", "TAXE TTF"}),
        None,
    )
    if ttf_col is None:
        return out
    for _, row in df.iterrows():
        value = row.get(ttf_col)
        # Contrairement aux colonnes d'accès broker, une cellule fiscale vide
        # signifie « statut inconnu/non renseigné », jamais « taxable ».
        marked = (
            isinstance(value, (bool, np.bool_)) and bool(value)
        ) or str(value).strip().upper() in {"VRAI", "TRUE", "OUI", "YES", "1", "1.0"}
        if marked:
            ticker = str(row.get(ticker_col, "") or "").strip().upper()
            if ticker:
                out.add(ticker)
    return out


def first_year_cost_summary(
    trade_cost_eur: float,
    annual_custody_eur: float,
    total_capital_eur: float,
) -> dict[str, float]:
    """Résumé commun objectif/UI : transition unique + garde annuelle."""
    trade = max(float(trade_cost_eur or 0.0), 0.0)
    custody = max(float(annual_custody_eur or 0.0), 0.0)
    total_capital = max(float(total_capital_eur or 0.0), 1e-9)
    first_year = trade + custody
    return {
        "next_rebalance_cost_eur": trade,
        "next_rebalance_cost_pct": trade / total_capital,
        "first_year_cost_eur": first_year,
        "first_year_cost_pct": first_year / total_capital,
    }


def next_rebalance_costs_by_broker(diagnostics: dict | None) -> dict[str, float]:
    """Extrait la reserve de tresorerie immediate des diagnostics optimiseur.

    Seuls les frais de transaction du prochain rebalancement sont reserves avant
    les achats. Les droits de garde annuels restent un cout de performance et ne
    diminuent pas artificiellement le montant de l'ordre initial.
    """
    transaction_costs = (diagnostics or {}).get("transaction_costs") or {}
    reserves: dict[str, float] = {}
    for item in transaction_costs.get("brokers") or []:
        broker = str(item.get("broker") or "").strip()
        if not broker:
            continue
        value = max(float(item.get("trade_cost_eur", 0.0) or 0.0), 0.0)
        if np.isfinite(value):
            reserves[broker] = value
    return reserves


def estimate_rebalance_costs_by_broker(
    tickers: list[str],
    target_weights,
    active_brokers: list[str],
    total_capital_eur: float,
    *,
    current_broker_holdings: dict[str, dict[str, float]] | None = None,
    is_etf_tickers: set[str] | None = None,
    ttf_tickers: set[str] | None = None,
    execution_routes: dict[tuple[str, str], str] | None = None,
    gbp_eur_rate: float = 1.0,
) -> dict[str, float]:
    """Estime les frais de la cible continue, séparés par broker.

    Cette fonction est utilisée avant que ``optimize_portfolio_de`` ait produit
    ses diagnostics. Elle permet donc à la discrétisation de réserver les mêmes
    frais que ceux utilisés pour scorer le portefeuille exécutable, au lieu de
    scorer une cible sans réserve puis d'en retirer les frais uniquement à la
    toute fin.

    ``target_weights`` et les positions courantes sont des fractions du capital
    total. Les routes secondaires sont prises en compte lorsqu'elles sont
    connues ; sans route, le ticker analytique est utilisé.
    """
    brokers = list(active_brokers)
    if not bool(Config.TRANSACTION_COSTS_ENABLED):
        return {broker: 0.0 for broker in brokers}

    weights = np.asarray(target_weights, dtype=float)
    if weights.ndim == 1:
        if len(brokers) <= 0 or weights.size % len(brokers) != 0:
            raise ValueError("target_weights incompatible avec active_brokers")
        weights = weights.reshape(len(tickers), len(brokers))
    if weights.shape != (len(tickers), len(brokers)):
        raise ValueError(
            "target_weights doit avoir la forme "
            f"({len(tickers)}, {len(brokers)}), reçu {weights.shape}"
        )

    total = max(float(total_capital_eur or 0.0), 1e-9)
    normalized_tickers = [str(ticker).strip().upper() for ticker in tickers]
    etfs = {str(ticker).strip().upper() for ticker in (is_etf_tickers or set())}
    ttf = {str(ticker).strip().upper() for ticker in (ttf_tickers or set())}
    routes = execution_routes or {}
    holdings = current_broker_holdings or {}
    reserves: dict[str, float] = {}

    for broker_index, broker in enumerate(brokers):
        broker_holdings = holdings.get(broker) or {}
        current = np.asarray(
            [
                max(
                    float(
                        broker_holdings.get(ticker, 0.0)
                        or broker_holdings.get(ticker.upper(), 0.0)
                        or 0.0
                    ),
                    0.0,
                )
                for ticker in normalized_tickers
            ],
            dtype=float,
        )
        routed_tickers = [
            str(routes.get((ticker, broker), ticker) or ticker).strip().upper()
            for ticker in normalized_tickers
        ]
        model = TransactionCostModel(
            routed_tickers,
            [ticker in etfs for ticker in normalized_tickers],
            {
                ticker
                for source, ticker in zip(normalized_tickers, routed_tickers)
                if source in ttf or ticker in ttf
            },
            gbp_eur_rate=gbp_eur_rate,
        )
        signed_orders = (weights[:, broker_index] - current) * total
        cost = float(model.trade_costs_eur(broker, signed_orders)[0])
        reserves[broker] = max(cost, 0.0) if np.isfinite(cost) else 0.0
    return reserves


class TransactionCostModel:
    """Modèle vectorisé des commissions, FX, taxes et garde étrangère."""

    def __init__(
        self,
        tickers: list[str],
        is_etf,
        ttf_tickers: set[str] | None = None,
        gbp_eur_rate: float = 1.0,
    ) -> None:
        self.tickers = [str(t).upper() for t in tickers]
        self.is_etf = np.asarray(is_etf, dtype=bool)
        self.suffixes = np.array([_suffix(ticker) for ticker in self.tickers], dtype=object)
        self.currencies = np.array([_currency(ticker) for ticker in self.tickers], dtype=object)
        ttf = {str(t).upper() for t in (ttf_tickers or set())}
        self.ttf_mask = np.array(
            [ticker in ttf and not self.is_etf[i] for i, ticker in enumerate(self.tickers)],
            dtype=bool,
        )
        parsed_gbp_rate = float(gbp_eur_rate or 1.0)
        self.gbp_eur_rate = (
            max(parsed_gbp_rate, 1e-9)
            if np.isfinite(parsed_gbp_rate)
            else 1.0
        )

    def trade_costs_eur(self, broker: str, signed_amounts_eur) -> np.ndarray:
        """Coût total en EUR par candidat ; positif=achat, négatif=vente."""
        signed = np.asarray(signed_amounts_eur, dtype=float)
        if signed.ndim == 1:
            signed = signed[:, None]
        amount = np.abs(signed)
        buy = signed > 1e-9
        sell = signed < -1e-9
        costs = np.zeros_like(amount)

        if _is_bourse_direct(broker):
            domestic = np.isin(self.suffixes, list(_EURONEXT_DOMESTIC))[:, None]
            a = amount
            domestic_fee = np.select(
                [a <= 198.0, a <= 500.0, a <= 1000.0, a <= 2000.0, a <= 4400.0],
                [0.005 * a, 0.99, 1.90, 2.90, 3.80],
                default=0.0009 * a,
            )
            costs += np.where(domestic & (amount > 1e-9), domestic_fee, 0.0)

            ny = (self.suffixes == "")[:, None]
            ny_fee = np.where(amount <= 10_000.0, 8.50, 0.0009 * amount)
            costs += np.where(ny & (amount > 1e-9), ny_fee, 0.0)

            london_frankfurt = np.isin(self.suffixes, ["L", "DE", "F"])[:, None]
            lf_fee = np.maximum(0.0015 * amount, 15.0)
            costs += np.where(london_frankfurt & (amount > 1e-9), lf_fee, 0.0)

            madrid_swiss_portugal = np.isin(self.suffixes, ["MC", "SW", "LS"])[:, None]
            msp_fee = np.maximum(0.0020 * amount, 18.0)
            costs += np.where(madrid_swiss_portugal & (amount > 1e-9), msp_fee, 0.0)

            known = domestic | ny | london_frankfurt | madrid_swiss_portugal
            other_fee = np.maximum(0.0048 * amount, 41.90)
            costs += np.where(~known & (amount > 1e-9), other_fee, 0.0)

            # Plafond PEA en ligne à 0,5 % uniquement UE/EEE.
            eu_eea = np.isin(self.suffixes, list(_EU_EEA_SUFFIXES))[:, None]
            costs = np.where(eu_eea, np.minimum(costs, 0.005 * amount), costs)
            non_eur = (self.currencies != "EUR")[:, None]
            costs += np.where(
                non_eur,
                amount * float(Config.BOURSE_DIRECT_FX_FEE_RATE),
                0.0,
            )
        elif _is_trading212(broker):
            non_eur = (self.currencies != "EUR")[:, None]
            costs += np.where(
                non_eur,
                amount * float(Config.TRADING212_FX_FEE_RATE),
                0.0,
            )

        # Taxes gouvernementales communes aux brokers.
        costs += np.where(
            buy & self.ttf_mask[:, None],
            amount * float(Config.FRENCH_TRANSACTION_TAX_RATE),
            0.0,
        )
        uk_stamp = (self.suffixes == "L")[:, None] & (~self.is_etf)[:, None]
        costs += np.where(buy & uk_stamp, amount * 0.005, 0.0)
        # Panel on Takeovers and Mergers : £1,50 à l'achat comme à la vente
        # d'actions britanniques lorsque l'ordre dépasse £10 000.
        ptm = uk_stamp & (amount > 10_000.0 * self.gbp_eur_rate)
        costs += np.where(ptm & (buy | sell), 1.5 * self.gbp_eur_rate, 0.0)
        # FINRA est par action et ne peut être estimée sans quantité d'ordre ; la
        # SEC est actuellement à 0 %. Ces montants sont donc documentés mais omis.
        return costs.sum(axis=0)

    def annual_holding_cost(self, broker: str, broker_weights) -> np.ndarray:
        """Droits de garde annuels, en fraction du portefeuille total."""
        weights = np.asarray(broker_weights, dtype=float)
        if weights.ndim == 1:
            weights = weights[:, None]
        if not _is_bourse_direct(broker):
            return np.zeros(weights.shape[1], dtype=float)
        foreign = ~np.isin(self.suffixes, list(_EURONEXT_DOMESTIC))
        return (
            float(Config.BOURSE_DIRECT_FOREIGN_CUSTODY_RATE)
            * weights[foreign].sum(axis=0)
        )
