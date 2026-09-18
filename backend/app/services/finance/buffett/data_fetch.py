"""Téléchargement et persistance locale des données yfinance par ticker."""

from __future__ import annotations

import json
import os
import tempfile

from .config import Config


def is_remote_rate_limit_error(error: BaseException) -> bool:
    """Détecte les variantes yfinance/curl du HTTP 429."""
    message = str(error).casefold()
    return (
        "too many requests" in message
        or "rate limited" in message
        or "rate limit" in message
        or "http error 429" in message
    )


def _wait_for_remote_recovery(rate_limiter) -> None:
    if rate_limiter is not None:
        rate_limiter.wait_for_remote_recovery()


def _record_success(rate_limiter) -> None:
    if rate_limiter is not None:
        rate_limiter.record_remote_success()


def _record_failure(error: BaseException, rate_limiter) -> bool:
    """Retourne True pour un 429, sans pause globale supplémentaire."""
    if not is_remote_rate_limit_error(error):
        return False
    if rate_limiter is not None:
        rate_limiter.record_remote_rate_limit()
    print("[data_fetch] Yahoo rate-limit: ticker différé, cadence 1,8s conservée")
    return True


def _rotate_session_safe() -> None:
    """Force une session curl_cffi neuve pour le thread courant (nouvelle IP si
    un pool de proxys est configuré). Yahoo bloque transitoirement une session
    (401 "Invalid Crumb", "User is unable to access this feature", quoteSummary
    None -> "argument of type 'NoneType' is not iterable") : changer de session
    débloque souvent immédiatement, sans attendre le prochain run."""
    try:
        from app.services.finance.yf_session import rotate_session
        rotate_session()
    except Exception:
        pass


def fetch_data(symbol: str, rate_limiter=None) -> dict | None:
    """Télécharge income / balance / cashflow / info depuis yfinance.

    Un échec rend immédiatement la main au runner. Celui-ci place le ticker
    dans sa file de reprise et le retente après la première passe complète.
    On tourne tout de même la session ici afin que cette reprise utilise une
    session neuve, sans doubler immédiatement un appel Yahoo potentiellement
    bloquant.
    """
    try:
        import yfinance as yf

        from app.services.finance.yf_session import yf_session
        _wait_for_remote_recovery(rate_limiter)
        t = yf.Ticker(symbol, session=yf_session())
        # Demander d'abord quoteSummary/.info : les symboles invalides et les
        # sessions Yahoo rejetées (401 crumb) échouent alors avant les trois
        # téléchargements de comptes, au lieu de gaspiller plusieurs appels
        # pour finalement jeter tout le résultat.
        info = t.info
        result = {
            "income": t.financials.transpose(),
            "balance": t.balance_sheet.transpose(),
            "cashflow": t.cashflow.transpose(),
            "info": info,
        }
        _record_success(rate_limiter)
        return result
    except Exception as e:
        print(f"[data_fetch] Erreur {symbol} -> reprise différée en fin de passe: {e}")
        _record_failure(e, rate_limiter)
        # Le prochain essai, après le backoff éventuel, doit repartir avec un
        # cookie/crumb neuf. Une seule rotation par sonde, jamais par ticker
        # sauté pendant que le circuit est ouvert.
        _rotate_session_safe()
    return None


def fetch_info_only(symbol: str, rate_limiter=None) -> dict | None:
    """Télécharge UNIQUEMENT `.info` (pas financials/balance/cashflow).

    Un ETF n'a pas de comptes annuels : son Score est figé par convention
    (200, cf. runner._etf_result) et ne dépend jamais de income/balance/
    cashflow -- seul `.info` sert à peupler Nom/Pays/Prix/Volume. Utilisé pour
    un ETF connu (`_check_is_etf`) sans cache ni fichier local exploitable :
    évite 3 des 4 appels yfinance de `fetch_data()` (financials/balance/
    cashflow sont inutiles et téléchargés en pure perte pour un ETF).

    Même politique que `fetch_data` : un échec est renvoyé au runner et repris
    en fin de passe avec une session neuve.
    """
    try:
        import yfinance as yf

        from app.services.finance.yf_session import yf_session
        _wait_for_remote_recovery(rate_limiter)
        t = yf.Ticker(symbol, session=yf_session())
        result = {"info": t.info}
        _record_success(rate_limiter)
        return result
    except Exception as e:
        print(f"[data_fetch] Erreur info {symbol} -> reprise différée en fin de passe: {e}")
        _record_failure(e, rate_limiter)
        _rotate_session_safe()
    return None


def load_local_data(
    ticker: str,
    *,
    identity_key: str | None = None,
    fundamentals_symbol: str | None = None,
) -> dict | None:
    """Charge SQLite; migre paresseusement l'ancien Excel en cas de cache miss."""
    from .fundamentals_cache import FundamentalsCache
    cache = FundamentalsCache()
    cached = cache.load(
        ticker,
        identity_key=identity_key,
        metadata_symbol=fundamentals_symbol,
    )
    if cached:
        return cached
    file_path = Config.output_dir() / f"{ticker.replace(':', '_')}.xlsx"
    if not file_path.exists():
        return None
    try:
        import pandas as pd
        xl = pd.ExcelFile(file_path)
        sheets = [s for s in ["income", "balance", "cashflow"] if s in xl.sheet_names]
        # Un ETF persisté via le fetch allégé ".info seul" (cf. fetch_info_only)
        # n'a AUCUNE de ces 3 feuilles -- pd.read_excel(sheet_name=[]) lève
        # "Sheet name is an empty list" si on l'appelle quand meme.
        data = pd.read_excel(file_path, sheet_name=sheets, index_col=0) if sheets else {}
        for k in data:
            data[k].index = pd.to_datetime(data[k].index)
        if "info" in xl.sheet_names:
            info_df = pd.read_excel(file_path, sheet_name="info")
            if not info_df.empty:
                data["info"] = info_df.iloc[0].to_dict()
        if data:
            cache.save(ticker, data, identity_key=identity_key)
        return data
    except Exception as e:
        print(f"[data_fetch] Erreur lecture locale {ticker}: {e}")
        return None


def save_local_data(
    ticker: str,
    data: dict,
    *,
    identity_key: str | None = None,
) -> bool:
    """Sauvegarde les données dans le cache SQLite partagé.

    "Exploitable" = au moins un DataFrame financier non-vide OU un `.info`
    non-vide. Un vrai ETF yfinance a income/balance/cashflow VIDES (ce n'est
    pas une entreprise) -- sans le `or info non-vide`, un ETF ne serait
    JAMAIS persisté localement, empêchant le court-circuit "fichier local"
    (cf. runner._analyze_one, étape 2) de jouer son rôle pour les ETF.
    """
    if not data:
        return False
    import pandas as pd
    has_real = any(
        isinstance(v, pd.DataFrame) and not v.empty
        for v in data.values()
        if v is not None
    ) or bool(data.get("info"))
    if not has_real:
        return False
    try:
        from .fundamentals_cache import FundamentalsCache
        FundamentalsCache().save(ticker, data, identity_key=identity_key)
        return True
    except Exception as e:
        print(f"[data_fetch] Erreur sauvegarde {ticker}: {e}")
        return False


def save_excel_mirror(ticker: str, data: dict) -> bool:
    """Écrit une copie de secours Excel complète des fondamentaux.

    SQLite reste le cache de travail rapide. Ce miroir n'est appelé par le
    runner qu'après une vraie réponse Yahoo : un simple recalcul de score ne
    réécrit donc pas les milliers de classeurs existants. L'écriture passe par
    un fichier temporaire dans le même dossier puis ``os.replace`` afin qu'une
    interruption ne laisse jamais un classeur à moitié écrit.
    """
    if not data:
        return False
    try:
        import pandas as pd

        output_dir = Config.output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{ticker.replace(':', '_')}.xlsx"
        temporary: str | None = None
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            prefix=f".{target.stem}-",
            dir=output_dir,
            delete=False,
        ) as handle:
            temporary = handle.name

        with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
            wrote_sheet = False
            for key in ("income", "balance", "cashflow"):
                frame = data.get(key)
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    frame.sort_index().to_excel(writer, sheet_name=key)
                    wrote_sheet = True

            info = data.get("info") if isinstance(data.get("info"), dict) else {}
            if info:
                # Excel n'accepte pas directement les listes/dictionnaires.
                serializable = {
                    key: (
                        json.dumps(value, ensure_ascii=False, default=str)
                        if isinstance(value, (dict, list, tuple, set))
                        else value
                    )
                    for key, value in info.items()
                }
                pd.DataFrame([serializable]).to_excel(
                    writer, sheet_name="info", index=False
                )
                wrote_sheet = True

            if not wrote_sheet:
                return False

        os.replace(temporary, target)
        return True
    except Exception as error:
        print(f"[data_fetch] Erreur miroir Excel {ticker}: {error}")
        return False
    finally:
        if "temporary" in locals() and temporary and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass


def merge_data(old_data: dict | None, new_data: dict | None) -> dict | None:
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
