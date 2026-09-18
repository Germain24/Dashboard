"""Façade publique du module buffett — point d'entrée pour le runner et le scoring."""

from .config import Config
from .runner import load_tickers, run_buffett_analysis
from .scoring import analyze_financials
from .scoring_pure import compute_moat_score, compute_buy_signal

__all__ = [
    "Config",
    "load_tickers",
    "run_buffett_analysis",
    "analyze_financials",
    "compute_moat_score",
    "compute_buy_signal",
]
