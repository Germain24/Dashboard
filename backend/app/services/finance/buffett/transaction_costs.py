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
        self.gbp_eur_rate = max(float(gbp_eur_rate or 1.0), 1e-9)

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
