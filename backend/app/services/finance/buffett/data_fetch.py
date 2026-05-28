"""Téléchargement et persistance locale des données yfinance par ticker."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import Config


def fetch_data(symbol: str, rate_limiter=None) -> Optional[dict]:
    """Télécharge income / balance / cashflow / info depuis yfinance."""
    try:
        import yfinance as yf
        if rate_limiter:
            rate_limiter.wait_for_slot()
        t = yf.Ticker(symbol)
        return {
            "income": t.financials.transpose(),
            "balance": t.balance_sheet.transpose(),
            "cashflow": t.cashflow.transpose(),
            "info": t.info,
        }
    except Exception as e:
        print(f"[data_fetch] Erreur {symbol}: {e}")
        return None


def load_local_data(ticker: str) -> Optional[dict]:
    """Charge les données financières depuis le cache local (Excel par ticker)."""
    file_path = Config.output_dir() / f"{ticker.replace(':', '_')}.xlsx"
    if not file_path.exists():
        return None
    try:
        import pandas as pd
        xl = pd.ExcelFile(file_path)
        sheets = [s for s in ["income", "balance", "cashflow"] if s in xl.sheet_names]
        data = pd.read_excel(file_path, sheet_name=sheets, index_col=0)
        for k in data:
            data[k].index = pd.to_datetime(data[k].index)
        if "info" in xl.sheet_names:
            info_df = pd.read_excel(file_path, sheet_name="info")
            if not info_df.empty:
                data["info"] = info_df.iloc[0].to_dict()
        return data
    except Exception as e:
        print(f"[data_fetch] Erreur lecture locale {ticker}: {e}")
        return None


def save_local_data(ticker: str, data: dict) -> bool:
    """Sauvegarde les données dans un Excel local par ticker."""
    if not data:
        return False
    import pandas as pd
    has_real = any(
        isinstance(v, pd.DataFrame) and not v.empty
        for v in data.values()
        if v is not None
    )
    if not has_real:
        return False
    file_path = Config.output_dir() / f"{ticker.replace(':', '_')}.xlsx"
    try:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            for key, df in data.items():
                if key == "info" and isinstance(df, dict) and df:
                    pd.DataFrame([df]).to_excel(writer, sheet_name="info", index=False)
                elif isinstance(df, pd.DataFrame) and not df.empty:
                    df.to_excel(writer, sheet_name=key)
        return True
    except Exception as e:
        print(f"[data_fetch] Erreur sauvegarde {ticker}: {e}")
        return False


def merge_data(old_data: Optional[dict], new_data: Optional[dict]) -> Optional[dict]:
    """Fusionne ancien cache local + nouvelles données yfinance."""
    if not old_data:
        return new_data
    if not new_data:
        return old_data
    import pandas as pd
    merged: dict = {}
    for key in ["income", "balance", "cashflow"]:
        old = old_data.get(key, pd.DataFrame())
        new = new_data.get(key, pd.DataFrame())
        if old is None:
            old = pd.DataFrame()
        if new is None:
            new = pd.DataFrame()
        if not old.empty and not new.empty:
            combined = pd.concat([old, new])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            merged[key] = combined
        elif not new.empty:
            merged[key] = new
        else:
            merged[key] = old
    merged["info"] = new_data.get("info") or old_data.get("info", {})
    return merged
