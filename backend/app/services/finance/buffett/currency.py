"""Devise de cotation et volume échangé/jour en euros.

La colonne ``Volume`` de la pipeline Buffett contient le volume échangé par
jour EN EUROS (= nb d'actions x prix local x taux devise->EUR), pas le nombre
brut d'actions : comparer des nombres d'actions entre bourses (dédup) ou les
confronter à un seuil en euros (liquidité) n'a aucun sens entre devises.
Spec : orchestration/a-faire/2026-07-15-volume-eur-design.md.
"""

from __future__ import annotations

from app.services.finance import fx

# Suffixe Yahoo -> devise de cotation (source unique, aussi utilisée par
# dedup._ticker_currency). Doit couvrir au moins toutes les bourses non-US de
# cache_manager.SUFFIX_MAP (source de vérité de l'univers) : test de
# couverture structurel dans test_currency_volume.py.
SUFFIX_CCY = {
    "L": "GBP", "PA": "EUR", "DE": "EUR", "F": "EUR", "AS": "EUR", "MI": "EUR",
    "MC": "EUR", "BR": "EUR", "LS": "EUR", "VI": "EUR", "HE": "EUR", "IR": "EUR",
    "HK": "HKD", "KS": "KRW", "KQ": "KRW", "T": "JPY", "TO": "CAD", "V": "CAD",
    "SW": "CHF", "ST": "SEK", "OL": "NOK", "CO": "DKK", "SI": "SGD",
    "SG": "EUR",  # .SG = Stuttgart (Yahoo), pas Singapour (.SI)
    "DU": "EUR",  # .DU = Düsseldorf (présent dans tickers.csv, absent de SUFFIX_MAP)
    "IL": "USD",  # .IL = London IOB (USD), pas Israel
    "AX": "AUD", "SS": "CNY", "SZ": "CNY", "NS": "INR", "BO": "INR", "TW": "TWD",
    "MX": "MXN", "SA": "BRL", "JO": "ZAR", "JK": "IDR", "IS": "TRY",
    "BK": "THB", "KL": "MYR",
}


def infer_currency(ticker: str, info: dict | None) -> tuple[str, float]:
    """(devise ISO, facteur prix) d'un ticker.

    Le facteur prix vaut 0.01 pour les cotations en pence ('GBp' casse exacte
    yfinance, ou 'GBX') -- NE PAS upper() avant ce test : 'GBp'.upper() ==
    'GBP' (livres entières). Priorité : info['currency'], sinon suffixe du
    ticker (SUFFIX_CCY), sinon USD."""
    raw = str((info or {}).get("currency") or "").strip()
    if raw == "GBp" or raw.upper() == "GBX":
        return "GBP", 0.01
    cur = raw.upper()
    if not cur:
        suf = ticker.rsplit(".", 1)[1].upper() if "." in ticker else ""
        cur = SUFFIX_CCY.get(suf, "USD")
    return cur, 1.0


def volume_eur(volume, prix, ticker: str = "", info: dict | None = None,
               *, rate_getter=None) -> float:
    """Volume échangé/jour en euros ; 0.0 si donnée ou taux manquant (le titre
    sera alors traité comme illiquide -- jamais de valeur brute silencieuse)."""
    try:
        v, p = float(volume or 0), float(prix or 0)
    except (TypeError, ValueError):
        return 0.0
    if v <= 0 or p <= 0:
        return 0.0
    ccy, factor = infer_currency(ticker, info)
    if ccy == "EUR":
        return round(v * p * factor, 2)
    get = rate_getter or fx.get_rate
    rate = float(get(ccy, "EUR") or 0.0)
    if rate <= 0:
        if ccy not in {*SUFFIX_CCY.values(), "USD"}:
            print(f"[currency] devise {ccy} NON préchauffée par warm_fx_cache "
                  f"({ticker or '?'}) -> ajouter à SUFFIX_CCY -> Volume=0")
        else:
            print(f"[currency] taux {ccy}->EUR indisponible ({ticker or '?'}) -> Volume=0")
        return 0.0
    return round(v * p * factor * rate, 2)


def ensure_volume_eur(metrics: dict, ticker: str = "") -> dict:
    """Metrics avec ``Volume`` garanti en euros (marqueur ``VolumeDevise``).

    Les métriques HISTORIQUES (cache_status.json et runs d'avant 2026-07-15)
    portent un Volume en nb d'actions ; celles produites depuis par
    extract_metrics/_etf_result portent ``VolumeDevise='EUR'``. Sans marqueur,
    convertit via Prix (devise locale) + suffixe du ticker. Idempotent, ne
    mute pas l'entrée. Limite connue : sans info['currency'], un titre `.L`
    coté en pence est traité comme GBP entier (volume surestimé x100) --
    corrigé au prochain rafraîchissement réel du ticker."""
    if metrics.get("VolumeDevise") == "EUR":
        return metrics
    out = dict(metrics)
    out["Volume"] = volume_eur(out.get("Volume"), out.get("Prix"), ticker, None)
    out["VolumeDevise"] = "EUR"
    return out


def warm_fx_cache(quote: str = "EUR", budget_s: float = 90.0) -> None:
    """Précharge les taux devise->quote au DÉMARRAGE du run Buffett : pendant
    l'analyse, fx.get_rate ne frappe plus le réseau (garde _analysis_running)
    et rendrait 0.0 pour toute paire jamais vue ce jour -> tous les volumes
    non-EUR seraient nuls et écartés comme illiquides.

    BORNÉ dans le temps (#bug POST /buffett/run « ne fait rien » : Yahoo
    throttlé rendait ce warm-up interminable, verrou d'analyse tenu, aucun
    log, aucun run visible) : budget global + timeout par paire ; au premier
    timeout on abandonne le reste (la session Yahoo est saturée, les paires
    suivantes pendraient pareil -- thread abandonné, même compromis que
    yf_session.download_with_timeout). Les paires manquantes retombent sur le
    dernier taux connu (cache disque rechargé ici) ou volume 0."""
    import concurrent.futures
    import time as _time

    fx.load_disk_cache()   # taux d'un run précédent (survit au redémarrage)
    currencies = sorted(({*SUFFIX_CCY.values()} | {"USD"}) - {quote.upper()})
    print(f"[currency] FX warm-up de {len(currencies)} paires -> {quote} "
          f"(budget {budget_s:.0f}s)...")
    t0 = _time.monotonic()
    ok: list[str] = []
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        for ccy in currencies:
            remaining = budget_s - (_time.monotonic() - t0)
            if remaining <= 0:
                break
            fut = ex.submit(fx.get_rate, ccy, quote, force=True)
            try:
                if fut.result(timeout=min(20.0, remaining)) > 0:
                    ok.append(ccy)
            except concurrent.futures.TimeoutError:
                break
            except Exception:
                pass
    finally:
        ex.shutdown(wait=False)
    fx.save_disk_cache()
    manquantes = sorted(set(currencies) - set(ok))
    print(f"[currency] FX warm-up : {len(ok)}/{len(currencies)} paires -> {quote} "
          f"en {_time.monotonic() - t0:.0f}s"
          + (f" (manquantes : {', '.join(manquantes)} -> dernier taux connu ou volume 0)"
             if manquantes else ""))
