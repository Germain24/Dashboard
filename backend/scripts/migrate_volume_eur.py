"""Migration one-shot : Volume en euros dans le cache et la DB (2026-07-15).

Contexte (#bug run 40) : le passage de la colonne Volume en euros convertit à
l'ingestion, mais le cache chaud (cache_status.json) et les runs déjà en base
gardaient des volumes en nb d'actions -> filtre de liquidité faussé (nb
d'actions comparés au seuil en euros).

Ce script :
1. Cache : convertit en € les entrées d'AVANT le cutover (démarrage du run 40,
   premier run sous le nouveau code) et pose le marqueur ``VolumeDevise`` sur
   toutes ; les entrées >= cutover sont déjà en € (fraîchement analysées).
   Les `.L` sont résolus via yfinance fast_info (GBp/pence vs GBP entier).
2. DB : convertit les lignes du run 39 (12 lignes, héritées de l'ancien code)
   et SUPPRIME le run 40 (interrompu, unités mélangées indémêlables ligne à
   ligne — décidé avec l'utilisateur le 2026-07-15).
3. Sauvegardes préalables : cache_status.json et instantané JSON des lignes DB
   modifiées, conservés sur le NAS.

Dry-run par défaut ; ``--apply`` pour exécuter.
    cd backend && uv run python scripts/migrate_volume_eur.py [--apply]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_storage import backup_bytes, backup_file  # noqa: E402
from app.services.finance import fx  # noqa: E402
from app.services.finance.buffett.currency import (  # noqa: E402
    SUFFIX_CCY,
    infer_currency,
)

CACHE_FILE = Path("data") / "cache_status.json"
DB_FILE = Path("..") / "data" / "mission-control.db"
RUN_TO_CONVERT = 39
RUN_TO_DELETE = 40


def _rates_for(currencies: set[str]) -> dict[str, float]:
    """Taux devise->EUR du jour (fetch live : aucune analyse ne tourne)."""
    rates = {"EUR": 1.0}
    for ccy in sorted(currencies - {"EUR"}):
        rates[ccy] = fx.get_rate(ccy, "EUR", force=True)
        if rates[ccy] <= 0:
            print(f"  !! taux {ccy}->EUR indisponible (les volumes {ccy} resteront à 0)")
    return rates


def _dot_l_currency(ticker: str, cache_yf: dict) -> tuple[str, float]:
    """Devise réelle d'une ligne LSE (.L) : GBp (pence) vs GBP vs USD."""
    if ticker in cache_yf:
        return cache_yf[ticker]
    cur, factor = "GBP", 0.01          # défaut : pence (majorité des lignes .L)
    try:
        import yfinance as yf

        from app.services.finance.yf_session import yf_session
        fi = yf.Ticker(ticker, session=yf_session()).fast_info
        try:
            raw = fi["currency"]
        except Exception:
            raw = getattr(fi, "currency", None)
        if raw:
            raw = str(raw).strip()
            if raw == "GBp" or raw.upper() == "GBX":
                cur, factor = "GBP", 0.01
            else:
                cur, factor = raw.upper(), 1.0
    except Exception:
        pass                            # défaut pence conservé
    cache_yf[ticker] = (cur, factor)
    return cur, factor


def _ticker_ccy(ticker: str, cache_yf: dict) -> tuple[str, float]:
    suf = ticker.rsplit(".", 1)[1].upper() if "." in ticker else ""
    if suf == "L":
        return _dot_l_currency(ticker, cache_yf)
    return infer_currency(ticker, None)


def migrate(apply: bool) -> None:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== Migration Volume->EUR ({mode}) ===")

    # ---------- 1. Cache ----------
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()
    cur.execute("SELECT created_at FROM buffett_run WHERE id=?", (RUN_TO_DELETE,))
    row = cur.fetchone()
    if row is None:
        # run 40 déjà supprimé (re-exécution) : cutover = maintenant, plus
        # aucune entrée "déjà en euros" à préserver n'est postérieure.
        cutover_utc = dt.datetime.now(dt.timezone.utc)
    else:
        cutover_utc = dt.datetime.fromisoformat(row[0]).replace(tzinfo=dt.timezone.utc)
    cutover_local = cutover_utc.astimezone().replace(tzinfo=None)
    print(f"Cutover (heure locale, = démarrage run {RUN_TO_DELETE}) : {cutover_local}")

    to_convert, to_mark, skipped = [], [], 0
    yf_ccy_cache: dict = {}
    for ticker, info in cache.items():
        metrics = (info or {}).get("metrics") or {}
        if not metrics or metrics.get("VolumeDevise") == "EUR":
            skipped += 1
            continue
        try:
            last = dt.datetime.fromisoformat(str(info.get("last_update")))
        except (TypeError, ValueError):
            last = dt.datetime.min
        if last >= cutover_local:
            to_mark.append(ticker)      # déjà en euros (analysé sous le nouveau code)
        else:
            to_convert.append(ticker)
    n_dot_l = sum(1 for t in to_convert if t.upper().endswith(".L"))
    print(f"Cache : {len(to_convert)} entrées à convertir (dont {n_dot_l} .L), "
          f"{len(to_mark)} à marquer seulement, {skipped} déjà OK/sans métriques")

    if apply:
        bak = backup_file(
            CACHE_FILE,
            category="maintenance/migrate_volume_eur",
            filename=f"{CACHE_FILE.stem}.json.bak-{ts}",
        )
        print(f"Sauvegarde cache -> {bak}")
        # Résolution des devises (les ~.L font un appel yfinance throttlé chacun)
        currencies = {_ticker_ccy(t, yf_ccy_cache)[0] for t in to_convert}
        rates = _rates_for(currencies)
        converted = zeroed = 0
        for ticker in to_convert:
            metrics = cache[ticker]["metrics"]
            ccy, factor = _ticker_ccy(ticker, yf_ccy_cache)
            try:
                v = float(metrics.get("Volume") or 0)
                p = float(metrics.get("Prix") or 0)
            except (TypeError, ValueError):
                v = p = 0.0
            rate = rates.get(ccy, 0.0)
            new = round(v * p * factor * rate, 2) if v > 0 and p > 0 and rate > 0 else 0.0
            if new == 0.0 and v > 0:
                zeroed += 1
            metrics["Volume"] = new
            metrics["VolumeDevise"] = "EUR"
            converted += 1
        for ticker in to_mark:
            cache[ticker]["metrics"]["VolumeDevise"] = "EUR"
        CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        print(f"Cache converti : {converted} entrées ({zeroed} à 0 : prix/taux manquant), "
              f"{len(to_mark)} marquées")

    # ---------- 2. DB ----------
    cur.execute("SELECT COUNT(*) FROM buffett_run_result WHERE run_id=?", (RUN_TO_CONVERT,))
    n39 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM buffett_run_result WHERE run_id=?", (RUN_TO_DELETE,))
    n40 = cur.fetchone()[0]
    print(f"DB : {n39} lignes du run {RUN_TO_CONVERT} à convertir ; "
          f"{n40} lignes + le run {RUN_TO_DELETE} à supprimer")

    if apply:
        cur.execute("SELECT * FROM buffett_run_result WHERE run_id IN (?, ?)",
                    (RUN_TO_CONVERT, RUN_TO_DELETE))
        result_columns = [column[0] for column in cur.description]
        result_rows = cur.fetchall()
        cur.execute("SELECT * FROM buffett_run WHERE id=?", (RUN_TO_DELETE,))
        run_columns = [column[0] for column in cur.description]
        run_rows = cur.fetchall()
        db_backup = backup_bytes(
            json.dumps(
                {
                    "buffett_run_result": {
                        "columns": result_columns,
                        "rows": result_rows,
                    },
                    "buffett_run": {"columns": run_columns, "rows": run_rows},
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            category="maintenance/migrate-volume-eur",
            filename=f"buffett-db-before-migration-{ts}.json",
        )
        print(f"Sauvegarde DB -> {db_backup}")
        cur.execute("SELECT id, ticker, volume, prix FROM buffett_run_result WHERE run_id=?",
                    (RUN_TO_CONVERT,))
        rows = cur.fetchall()
        rates = _rates_for({_ticker_ccy(t, yf_ccy_cache)[0] for _, t, _, _ in rows})
        for rid, ticker, volume, prix in rows:
            ccy, factor = _ticker_ccy(ticker, yf_ccy_cache)
            rate = rates.get(ccy, 0.0)
            v, p = float(volume or 0), float(prix or 0)
            new = round(v * p * factor * rate, 2) if v > 0 and p > 0 and rate > 0 else 0.0
            cur.execute("UPDATE buffett_run_result SET volume=? WHERE id=?", (new, rid))
        cur.execute("DELETE FROM buffett_run_result WHERE run_id=?", (RUN_TO_DELETE,))
        cur.execute("DELETE FROM buffett_run WHERE id=?", (RUN_TO_DELETE,))
        db.commit()
        print(f"DB : run {RUN_TO_CONVERT} converti ({len(rows)} lignes), "
              f"run {RUN_TO_DELETE} supprimé ({n40} lignes)")
    db.close()
    print("=== Terminé ===")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="exécute (défaut : dry-run)")
    migrate(ap.parse_args().apply)
