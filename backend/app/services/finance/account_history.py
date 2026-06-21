"""Historique de la valeur des comptes, reconstruit depuis les relevés.

Pour l'évolution du patrimoine PAR COMPTE dans le temps (histogramme empilé), on
lit la valeur de clôture de chaque relevé mensuel :
- Trading212 : « Account value » de chaque Activity Statement (PDF).
- Desjardins (compte chèque) : dernier solde du CSV AccèsD (col 13), CAD→EUR.
- Banque Populaire : « SOLDE CREDITEUR AU … * » de chaque Extrait de compte (PDF).
- Wise : non géré pour l'instant (XLSX multi-devises) → repli valeur courante.

Les points par compte sont reportés (carry-forward) entre deux relevés et valent
0 avant le premier relevé connu. Les parseurs et `build_monthly_series` sont purs
(testables) ; le scan des dossiers est mis en cache (signature = liste de fichiers).
"""

from __future__ import annotations

import calendar
import csv
import datetime as dt
import io
import json
import logging
import re
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def _releve_dir() -> Path:
    return settings.imports_dir / "Finances" / "Releve"


def _cache_path() -> Path:
    return settings.imports_dir / "Finances" / "account_history.json"


# ── Parseurs (purs) ───────────────────────────────────────────────────────────

def parse_bp_closing(text: str) -> tuple[dt.date, float] | None:
    """Solde créditeur de CLÔTURE d'un extrait Banque Populaire (la ligne avec *)."""
    best = None
    for line in text.splitlines():
        if "SOLDE CREDITEUR AU" in line and "*" in line:
            dm = re.search(r"AU (\d{2})/(\d{2})/(\d{4})", line)
            am = re.search(r"(-?[\d \xa0]+,\d{2})\s*€", line)
            if dm and am:
                d = dt.date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
                v = float(am.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
                best = (d, v)
    return best


_ACCESD_DATE = re.compile(r"\d{4}/\d{2}/\d{2}$")


_EN_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
_WP_PERIOD = re.compile(
    r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})\s*-\s*(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
_WP_CLOSING = re.compile(r"Closing Balance\s*\+?\s*\$?\s*([\d,]+\.\d{2})")


def parse_westpac_statement(text: str) -> tuple[dt.date, float] | None:
    """Date de fin de période + Closing Balance (AUD) d'un relevé Westpac Choice."""
    pm = _WP_PERIOD.search(text)
    cm = _WP_CLOSING.search(text)
    if not pm or not cm or pm.group(5) not in _EN_MONTHS:
        return None
    try:
        end = dt.date(int(pm.group(6)), _EN_MONTHS[pm.group(5)], int(pm.group(4)))
    except ValueError:
        return None
    return end, float(cm.group(1).replace(",", ""))


def parse_desjardins_csv_solde(content: str) -> tuple[dt.date, float] | None:
    """Dernier solde (col 13) d'un export CSV AccèsD Desjardins (compte chèque)."""
    rows: list[tuple[dt.date, float]] = []
    for r in csv.reader(io.StringIO(content)):
        if len(r) >= 14 and _ACCESD_DATE.match(r[3].strip()):
            try:
                d = dt.datetime.strptime(r[3].strip(), "%Y/%m/%d").date()
                solde = float(r[13].replace(",", "").strip())
            except ValueError:
                continue
            rows.append((d, solde))
    return max(rows, key=lambda x: x[0]) if rows else None


def parse_desjardins_csv_all(content: str) -> list[tuple[dt.date, float]]:
    """Tous les soldes (col 13) d'un CSV AccèsD, un point par jour (solde de fin
    de journée = dernière ligne du jour). Trié croissant."""
    by_date: dict[dt.date, float] = {}
    for r in csv.reader(io.StringIO(content)):
        if len(r) >= 14 and _ACCESD_DATE.match(r[3].strip()):
            try:
                d = dt.datetime.strptime(r[3].strip(), "%Y/%m/%d").date()
                by_date[d] = float(r[13].replace(",", "").strip())
            except ValueError:
                continue
    return sorted(by_date.items())


def aggregate_wise(
    per_currency: dict[str, list[tuple[dt.date, float]]],
    fx,
) -> list[tuple[dt.date, float]]:
    """Solde Wise total (EUR) à chaque date, somme des devises (report par devise).

    `per_currency` : {devise: [(date, solde_dans_la_devise), …] triés croissant}.
    `fx(montant, devise) -> EUR`. Retourne [(date, total_eur)] aux dates distinctes.
    """
    all_dates = sorted({d for pts in per_currency.values() for d, _ in pts})
    out: list[tuple[dt.date, float]] = []
    for day in all_dates:
        total = 0.0
        for dev, pts in per_currency.items():
            bal = 0.0
            for d, v in pts:
                if d <= day:
                    bal = v
                else:
                    break
            total += fx(bal, dev)
        out.append((day, round(total, 2)))
    return out


# ── Construction de la série mensuelle empilée (pur) ──────────────────────────

def _month_end(y: int, m: int) -> dt.date:
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def _month_ends(start: dt.date, end: dt.date) -> list[dt.date]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(_month_end(y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _span_start(points_by_account: dict, manual: list) -> dt.date | None:
    candidates = [p[0] for pts in points_by_account.values() for p in pts]
    candidates += [c for _, _, c in manual]
    return min(candidates) if candidates else None


def _fill(
    points_by_account: dict[str, list[tuple[dt.date, float]]],
    manual: list[tuple[str, float, dt.date]],
    dates: list[dt.date],
) -> dict:
    """Remplit la série empilée aux dates données : report du dernier point connu
    par compte (relevés), 0 avant ; valeur courante dès création pour `manual`."""
    comptes = list(points_by_account.keys()) + [lbl for lbl, _, _ in manual]
    series: dict[str, list[float]] = {c: [] for c in comptes}
    total: list[float] = []
    for bucket in dates:
        s = 0.0
        for label, pts in points_by_account.items():
            v = 0.0
            for d, val in pts:
                if d <= bucket:
                    v = val
                else:
                    break
            series[label].append(round(v, 2))
            s += v
        for label, val, created in manual:
            v = val if created <= bucket else 0.0
            series[label].append(round(v, 2))
            s += v
        total.append(round(s, 2))
    return {
        "dates": [d.isoformat() for d in dates],
        "comptes": comptes, "series": series, "total": total,
    }


def build_monthly_series(points_by_account, manual, today: dt.date | None = None) -> dict:
    """Série MENSUELLE empilée (fin de mois) — cf. `build_daily_series` pour le détail."""
    start = _span_start(points_by_account, manual)
    if start is None:
        return {"dates": [], "comptes": [], "series": {}, "total": []}
    return _fill(points_by_account, manual, _month_ends(start, today or dt.date.today()))


def build_daily_series(points_by_account, manual, today: dt.date | None = None) -> dict:
    """Série QUOTIDIENNE empilée (valeur brute) par compte, du plus ancien point
    à `today`. Les comptes à points épars (relevés mensuels) forment des marches ;
    Desjardins/Wise (points quotidiens) montrent la vraie variation."""
    today = today or dt.date.today()
    start = _span_start(points_by_account, manual)
    if start is None:
        return {"dates": [], "comptes": [], "series": {}, "total": []}
    dates = [start + dt.timedelta(days=k) for k in range((today - start).days + 1)]
    return _fill(points_by_account, manual, dates)


def _wise_points() -> list[tuple[dt.date, float]]:
    """Solde Wise total (EUR) dans le temps, sommé sur toutes les devises.

    Chaque XLSX = une devise, colonne « Solde actuel » (solde courant après chaque
    opération). On prend le solde de fin de journée par devise, converti en EUR au
    taux courant (approx historique), puis sommé."""
    base = _releve_dir() / "Wise"
    if not base.exists():
        return []
    import pandas as pd
    from app.services.finance.patrimoine import to_eur

    per: dict[str, list[tuple[dt.date, float]]] = {}
    for f in sorted(base.glob("*.xlsx")):
        try:
            m = re.search(r"_([A-Z]{3})_", f.name)
            df = pd.read_excel(f, sheet_name="All transactions").dropna(subset=["Solde actuel"])
            if df.empty:
                continue
            sort_col = "Date et heure" if "Date et heure" in df.columns else "Date"
            df = df.sort_values(sort_col)
            df["_d"] = pd.to_datetime(df["Date"]).dt.date
            ser = df.groupby("_d")["Solde actuel"].last()
            dev = (m.group(1) if m else None) or str(df["Devise"].iloc[0])
            per[dev] = sorted((d, float(v)) for d, v in ser.items())
        except Exception:
            continue
    if not per:
        return []
    return aggregate_wise(per, lambda amt, d: to_eur(amt, d))


def _westpac_points() -> list[tuple[dt.date, float]]:
    """Solde de clôture (AUD→EUR) de chaque relevé Westpac Choice."""
    base = _releve_dir() / "Westpac"
    if not base.exists():
        return []
    from app.services.budget.desjardins_pdf import extract_pdf_text
    from app.services.finance.patrimoine import to_eur
    pts: list[tuple[dt.date, float]] = []
    for pdf in sorted(base.glob("*.pdf")):
        try:
            r = parse_westpac_statement(extract_pdf_text(pdf.read_bytes()))
            if r:
                pts.append((r[0], round(to_eur(r[1], "AUD"), 2)))
        except Exception:
            pass
    return sorted(set(pts))


# ── Scan des dossiers (impur, mis en cache) ───────────────────────────────────

def account_history_points(*, force: bool = False) -> dict[str, list[tuple[dt.date, float]]]:
    """{compte: [(date, valeur_eur), …]} reconstruit depuis les relevés.

    Mis en cache (signature = liste des fichiers de relevés) car le parsing PDF
    est coûteux. Best-effort : un dossier/relevé illisible est simplement ignoré.
    """
    base = _releve_dir()

    def _glob(sub: str, pattern: str) -> list[Path]:
        d = base / sub
        return sorted(d.rglob(pattern)) if d.exists() else []

    t212 = _glob("Tradding212", "Activity-Statement-*.pdf")
    desj = _glob("Desjardins/Debit", "*.csv")
    bp = _glob("Banque populaire", "*.pdf")
    wise = _glob("Wise", "*.xlsx")
    westpac = _glob("Westpac", "*.pdf")
    sig = [p.name for p in (*t212, *desj, *bp, *wise, *westpac)]

    cache = _cache_path()
    if not force and cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("sig") == sig:
                return {
                    k: [(dt.date.fromisoformat(d), v) for d, v in pts]
                    for k, pts in data["points"].items()
                }
        except Exception:
            pass

    from app.services.budget.desjardins_pdf import extract_pdf_text
    from app.services.finance.patrimoine import to_eur
    from app.services.finance.trading212 import parse_trading212_statement

    out: dict[str, list[tuple[dt.date, float]]] = {}

    pts: list[tuple[dt.date, float]] = []
    for pdf in t212:
        try:
            p = parse_trading212_statement(extract_pdf_text(pdf.read_bytes()))
            if p["account_value"] and p["date"]:
                pts.append((dt.date.fromisoformat(p["date"]), round(float(p["account_value"]), 2)))
        except Exception:
            pass
    if pts:
        out["Trading 212"] = sorted(set(pts))

    pts = []
    for f in desj:
        try:
            for d, solde in parse_desjardins_csv_all(f.read_text(encoding="utf-8-sig")):
                pts.append((d, round(to_eur(solde, "CAD"), 2)))   # daily (1 pt/jour)
        except Exception:
            pass
    if pts:
        out["Desjardins"] = sorted(set(pts))

    pts = []
    for pdf in bp:
        try:
            r = parse_bp_closing(extract_pdf_text(pdf.read_bytes()))
            if r:
                pts.append((r[0], round(r[1], 2)))
        except Exception:
            pass
    if pts:
        out["Banque Populaire"] = sorted(set(pts))

    wpts = _wise_points()
    if wpts:
        out["Wise"] = wpts

    wsp = _westpac_points()
    if wsp:
        out["Westpac"] = wsp

    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({
            "sig": sig,
            "points": {k: [[d.isoformat(), v] for d, v in pts] for k, pts in out.items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    return out
