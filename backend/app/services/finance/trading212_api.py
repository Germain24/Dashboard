"""Client de l'API Trading 212 (v0) — source de vérité du compte Invest.

Remplace le parsing des Activity Statements PDF pour la valeur du compte, le
montant investi, les positions et les trades. Les relevés PDF/CSV restent le
repli automatique quand la clé n'est pas configurée (cf. `is_configured`), pour
ne pas casser le module sur une installation sans clé.

Authentification : **HTTP Basic `keyId:secret`**. Trading 212 délivre un couple
(API KEY ID, SECRET KEY) dans Settings > API (Beta) ; le secret n'est affiché
qu'à la création. Le header `Authorization: <clé>` seul — présent dans certains
exemples de la doc — renvoie 401 quel que soit l'environnement.

Limite connue : l'API n'expose **aucune série historique de valorisation**, ni
pour la valeur du compte ni pour le montant investi. `record_snapshot` persiste
donc un point par jour dans un journal local (`trading212_history.jsonl`), qui
constitue l'historique à partir de sa mise en service ; les points antérieurs
restent ceux extraits des relevés.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cadences tolérées par l'API (doc Trading 212). Dépassement -> 429, repris avec
# un backoff : mieux vaut attendre que perdre le point de la journée.
_MIN_INTERVAL = {
    "/api/v0/equity/account/cash": 2.0,
    "/api/v0/equity/portfolio": 5.0,
    "/api/v0/equity/metadata/instruments": 50.0,
}
_last_call: dict[str, float] = {}


class Trading212Error(RuntimeError):
    """Erreur d'appel à l'API (auth, quota, indisponibilité)."""


def is_configured() -> bool:
    """Vrai si le couple keyId/secret est renseigné."""
    return bool(settings.trading212_key_id and settings.trading212_secret)


def _auth_header() -> str:
    raw = f"{settings.trading212_key_id}:{settings.trading212_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _get(path: str, params: dict | None = None, *, timeout: float = 60.0,
         retries: int = 4):
    """GET authentifié. Rejoue les 429 avec un backoff, lève sinon."""
    if not is_configured():
        raise Trading212Error("clé Trading 212 absente (TRADING212_KEY_ID/SECRET)")

    wait = _MIN_INTERVAL.get(path, 0.0)
    if wait:
        elapsed = time.monotonic() - _last_call.get(path, 0.0)
        if elapsed < wait:
            time.sleep(wait - elapsed)

    url = settings.trading212_base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": _auth_header(),
        "Accept": "application/json",
        "User-Agent": "mission-control/1.0",
    })
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _last_call[path] = time.monotonic()
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:                       # quota : on patiente
                time.sleep(5 * (attempt + 1))
                continue
            if exc.code in (401, 403):
                raise Trading212Error(
                    f"authentification refusée ({exc.code}) — vérifier le couple "
                    f"keyId/secret et les permissions de la clé"
                ) from exc
            raise Trading212Error(f"{exc.code} sur {path}") from exc
        except Exception as exc:  # réseau
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise Trading212Error(f"échec {path}: {last}")


# ── Lectures unitaires ───────────────────────────────────────────────────────

def fetch_account_info() -> dict:
    """{id, currencyCode} du compte."""
    return _get("/api/v0/equity/account/info")


def fetch_cash() -> dict:
    """{free, total, invested, ppl, result, pieCash, blocked} en devise du compte.

    `total` = valeur du compte (positions + cash), `invested` = montant investi.
    """
    return _get("/api/v0/equity/account/cash")


def fetch_portfolio() -> list[dict]:
    """Positions ouvertes (ticker T212, quantité, prix moyen, prix courant, ppl)."""
    return _get("/api/v0/equity/portfolio")


def fetch_exchanges() -> list[dict]:
    return _get("/api/v0/equity/metadata/exchanges")


def fetch_instruments() -> list[dict]:
    """Catalogue complet des instruments négociables (~16 000). Coûteux : 1 appel/50 s."""
    return _get("/api/v0/equity/metadata/instruments", timeout=180)


def instruments_path() -> Path:
    return settings.imports_dir / "Finances" / "variables" / "trading212_instruments.json"


def exchanges_path() -> Path:
    return settings.imports_dir / "Finances" / "variables" / "trading212_exchanges.json"


def load_instruments(*, max_age_days: int = 7) -> list[dict]:
    """Catalogue en cache disque, rafraîchi au-delà de `max_age_days`.

    Le catalogue est volumineux et bridé à 1 appel/50 s : on ne le retélécharge
    pas à chaque usage. En cas d'échec réseau, le cache existant est conservé.
    """
    path = instruments_path()
    fresh = False
    if path.exists():
        age = dt.date.today() - dt.date.fromtimestamp(path.stat().st_mtime)
        fresh = age.days <= max_age_days
    if not fresh:
        try:
            data = fetch_instruments()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as exc:  # réseau/quota : on se rabat sur le cache
            logger.warning("[trading212] catalogue non rafraîchi (%s)", exc)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def load_exchanges(*, max_age_days: int = 30) -> list[dict]:
    """Places Trading 212 mises en cache pour résoudre les tickers sans ambiguïté."""
    path = exchanges_path()
    fresh = False
    if path.exists():
        age = dt.date.today() - dt.date.fromtimestamp(path.stat().st_mtime)
        fresh = age.days <= max_age_days
    if not fresh:
        try:
            data = fetch_exchanges()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as exc:
            logger.warning("[trading212] places non rafraîchies (%s)", exc)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def symbol_map() -> dict[str, str]:
    """Ticker interne Trading 212 (`SGLNl_EQ`) -> symbole Yahoo (`SGLN.L`).

    C'est la forme attendue par `portfolio_state` pour aller chercher un cours,
    et celle qu'utilisaient déjà les transactions importées des CSV. Repli sur
    le symbole court quand la place n'a pas d'équivalent Yahoo connu.
    """
    sched2ex = exchange_by_schedule()
    out: dict[str, str] = {}
    for inst in load_instruments():
        ticker = inst.get("ticker")
        if not ticker:
            continue
        out[ticker] = (yahoo_symbol(inst, sched2ex)
                       or inst.get("shortName") or ticker)
    return out


# Place de cotation Trading 212 -> suffixe Yahoo Finance ("" = marché US, sans
# suffixe). Les places US/OTC de Yahoo n'ont pas de suffixe ; Gettex est la
# plateforme de la Börse München, dont le suffixe Yahoo est `.MU`.
EXCHANGE_SUFFIX = {
    "NYSE": "", "NASDAQ": "", "OTC Markets": "",
    "Deutsche Börse Xetra": "DE", "Gettex": "MU",
    "London Stock Exchange": "L", "London Stock Exchange AIM": "L",
    "London Stock Exchange NON-ISA": "L",
    "SIX Swiss Exchange": "SW", "Toronto Stock Exchange": "TO",
    "Borsa Italiana": "MI", "Euronext Amsterdam": "AS",
    "Euronext Brussels": "BR", "Euronext Paris": "PA",
    "Euronext Lisbon": "LS", "Bolsa de Madrid": "MC",
    "Wiener Börse": "VI",
}


_SCHEDULE_CACHE: dict[int, str] | None = None


def exchange_by_schedule() -> dict[int, str]:
    """`workingScheduleId` d'un instrument -> nom de la place (mémoïsé)."""
    global _SCHEDULE_CACHE
    if _SCHEDULE_CACHE is not None:
        return _SCHEDULE_CACHE
    exchanges = load_exchanges()
    out: dict[int, str] = {}
    for ex in exchanges:
        for sched in ex.get("workingSchedules") or []:
            out[sched["id"]] = ex["name"]
    _SCHEDULE_CACHE = out
    return out


def yahoo_symbol(instrument: dict, sched2ex: dict[int, str] | None = None) -> str | None:
    """Symbole Yahoo d'un instrument Trading 212 (`SUp_EQ` -> `SU.PA`).

    None si la place n'a pas d'équivalent Yahoo connu — mieux vaut ne rien
    proposer qu'un symbole inventé qui polluerait le catalogue.
    """
    short = (instrument.get("shortName") or "").strip().upper()
    if not short:
        return None
    place = (sched2ex or {}).get(instrument.get("workingScheduleId"))
    if place is None:
        return None
    suffix = EXCHANGE_SUFFIX.get(place)
    if suffix is None:
        return None
    return f"{short}.{suffix}" if suffix else short


def _next_page_target(path: str, nxt: str) -> str:
    """Résout un `nextPagePath` en chemin appelable.

    Selon l'endpoint, Trading 212 renvoie soit un chemin absolu
    (`/api/v0/equity/history/orders?...`), soit une query string à recoller sur
    le chemin courant — avec ou sans `?` initial (`limit=50&cursor=...`).
    """
    base = path.split("?", 1)[0]
    if nxt.startswith("?"):
        return base + nxt
    if nxt.startswith("/"):
        return nxt
    if "=" in nxt.split("/", 1)[0]:          # query string nue
        return base + "?" + nxt
    return "/" + nxt


def _iter_paged(path: str, limit: int = 50, max_pages: int = 200):
    """Parcourt un endpoint paginé (`items` + `nextPagePath`)."""
    payload = _get(path, {"limit": limit})
    pages = 0
    while payload and pages < max_pages:
        for item in payload.get("items") or []:
            yield item
        nxt = payload.get("nextPagePath")
        if not nxt:
            return
        pages += 1
        time.sleep(1.0)                              # 6 requêtes/min tolérées
        payload = _get(_next_page_target(path, nxt))


def iter_orders(limit: int = 50):
    """Historique des ordres exécutés, du plus récent au plus ancien."""
    return _iter_paged("/api/v0/equity/history/orders", limit)


def iter_dividends(limit: int = 50):
    return _iter_paged("/api/v0/history/dividends", limit)


def iter_transactions(limit: int = 50):
    """Mouvements de trésorerie (dépôts, retraits, intérêts)."""
    return _iter_paged("/api/v0/history/transactions", limit)


# ── Conversion vers le modèle Transaction ────────────────────────────────────

BROKER = "Trading212"


def _parse_dt(value: str) -> dt.datetime:
    """ISO-8601 Trading 212 (`...Z` ou `...+03:00`) -> datetime naïf UTC.

    Les dates déjà en base sont naïves et exprimées en UTC : on aligne dessus,
    sinon les comparaisons de doublons échouent sur le fuseau.
    """
    raw = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(raw)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return parsed


def _fees_eur(fill: dict) -> float:
    """Frais/taxes prélevés sur une exécution (conversion de devise, taxes)."""
    taxes = ((fill.get("walletImpact") or {}).get("taxes")) or []
    return round(sum(abs(float(t.get("quantity") or 0)) for t in taxes), 8)


def order_to_transaction(item: dict, symbols: dict[str, str]) -> dict | None:
    """Ordre exécuté (API) -> dict Transaction, ou None si non exécuté.

    `filledValue` inclut les frais pour un achat et les déduit pour une vente,
    exactement comme la colonne `Total` des exports CSV : on isole donc les
    frais avant de dériver le prix unitaire brut, sans quoi ils seraient
    comptés deux fois.
    """
    order, fill = item.get("order") or {}, item.get("fill") or {}
    if not fill.get("id") or not order.get("side"):
        return None
    qty = float(fill.get("quantity") or 0)
    if qty <= 0:
        return None
    type_ = "achat" if str(order["side"]).upper() == "BUY" else "vente"
    total = abs(float(order.get("filledValue") or
                      (fill.get("walletImpact") or {}).get("netValue") or 0))
    frais = _fees_eur(fill)
    brut = total - frais if type_ == "achat" else total + frais
    t212_ticker = order.get("ticker") or ""
    return {
        "date": _parse_dt(fill.get("filledAt") or order["createdAt"]),
        "ticker": symbols.get(t212_ticker, t212_ticker),
        "broker": BROKER,
        "type": type_,
        "quantite": qty,
        "prix_unitaire": round(brut / qty, 8),
        "devise": "EUR",
        "frais": frais,
        "montant_brut": None,
        "retenue_source": 0.0,
        "note": f"T212 EOF{fill['id']}",
    }


_CASH_TYPES = {"DEPOSIT": "depot", "WITHDRAWAL": "retrait",
               "INTEREST_ON_FREE_CASH": "interet"}


def cash_to_transaction(item: dict) -> dict | None:
    """Mouvement de trésorerie (API) -> dict Transaction."""
    type_ = _CASH_TYPES.get(str(item.get("type") or "").upper())
    if not type_:
        return None
    montant = abs(float(item.get("amount") or 0))
    return {
        "date": _parse_dt(item["dateTime"]),
        "ticker": "CASH",
        "broker": BROKER,
        "type": type_,
        "quantite": 1.0,
        "prix_unitaire": montant,
        "devise": str(item.get("currency") or "EUR"),
        "frais": 0.0,
        "montant_brut": montant if type_ == "interet" else None,
        "retenue_source": 0.0,
        "note": f"T212 {item['reference']}" if item.get("reference") else None,
    }


def dividend_to_transaction(item: dict, symbols: dict[str, str]) -> dict | None:
    """Dividende (API) -> dict Transaction (montant net crédité, en EUR)."""
    montant = abs(float(item.get("amountInEuro") or item.get("amount") or 0))
    if not montant:
        return None
    t212_ticker = item.get("ticker") or ""
    return {
        "date": _parse_dt(item["paidOn"]),
        "ticker": symbols.get(t212_ticker, t212_ticker) or "CASH",
        "broker": BROKER,
        "type": "dividende",
        "quantite": 1.0,
        "prix_unitaire": round(montant, 8),
        "devise": "EUR",
        "frais": 0.0,
        "montant_brut": round(montant, 8),
        "retenue_source": 0.0,
        "note": f"T212 {item['reference']}" if item.get("reference") else None,
    }


def _signature(tx: dict) -> tuple:
    """Clé de repli quand la note ne peut pas dédoublonner.

    Les dividendes importés depuis les anciens CSV n'ont pas de note et la
    `reference` de l'API leur est étrangère ; leur montant diffère de surcroît
    (le CSV stocke le BRUT fiscal, l'API le NET crédité), donc seul le couple
    (type, horodatage) coïncide — l'heure de paiement est à la seconde près et
    deux dividendes du même titre ne tombent jamais sur la même seconde. Pour
    les autres types, le montant est inclus : deux intérêts d'un même jour
    peuvent partager l'horodatage sans être le même mouvement.
    """
    if tx["type"] == "dividende":
        return (tx["type"], tx["date"])
    return (tx["type"], tx["date"], round(float(tx["prix_unitaire"]), 2))


def import_history(session, *, broker: str = BROKER) -> dict:
    """Importe ordres, mouvements de trésorerie et dividendes depuis l'API.

    Idempotent : dédoublonnage par note (`T212 EOF<fill id>` pour les trades,
    `T212 <reference>` pour la trésorerie — mêmes identifiants que les exports
    CSV historiques) et, à défaut, par signature. Best-effort : une erreur
    d'API laisse la base intacte.
    """
    from app.models.finance import Transaction
    from sqlmodel import select

    from app.services.finance.transactions import create_transaction

    try:
        symbols = symbol_map()
        existing = session.exec(
            select(Transaction).where(Transaction.broker == broker)
        ).all()
        notes = {t.note for t in existing if t.note}
        signatures = {_signature({"type": t.type, "date": t.date,
                                  "prix_unitaire": t.prix_unitaire})
                      for t in existing}

        candidates: list[dict] = []
        for item in iter_orders():
            tx = order_to_transaction(item, symbols)
            if tx:
                candidates.append(tx)
        for item in iter_transactions():
            tx = cash_to_transaction(item)
            if tx:
                candidates.append(tx)
        for item in iter_dividends():
            tx = dividend_to_transaction(item, symbols)
            if tx:
                candidates.append(tx)

        imported = skipped = 0
        for tx in candidates:
            if (tx.get("note") and tx["note"] in notes) or _signature(tx) in signatures:
                skipped += 1
                continue
            create_transaction(session, tx)
            if tx.get("note"):
                notes.add(tx["note"])
            signatures.add(_signature(tx))
            imported += 1
        return {"imported": imported, "skipped": skipped,
                "parsed": len(candidates)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[trading212] import API ignoré (%s)", exc)
        return {"imported": 0, "skipped": 0, "parsed": 0}


# ── Snapshot quotidien (l'API ne fournit pas d'historique) ───────────────────

def history_path() -> Path:
    return settings.imports_dir / "Finances" / "trading212_history.jsonl"


def load_history() -> list[dict]:
    """Points {date, total, invested, ppl, free} déjà enregistrés, triés."""
    path = history_path()
    if not path.exists():
        return []
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("date"):
            out[rec["date"]] = rec       # dernier point du jour = celui retenu
    return [out[k] for k in sorted(out)]


def record_snapshot(cash: dict | None = None, *, today: dt.date | None = None) -> dict:
    """Ajoute (ou remplace) le point du jour dans le journal d'historique.

    Un seul point par jour : un rafraîchissement répété le même jour écrase le
    précédent à la lecture (`load_history` dédoublonne par date).
    """
    data = cash if cash is not None else fetch_cash()
    rec = {
        "date": (today or dt.date.today()).isoformat(),
        "total": round(float(data.get("total") or 0.0), 2),
        "invested": round(float(data.get("invested") or 0.0), 2),
        "ppl": round(float(data.get("ppl") or 0.0), 2),
        "free": round(float(data.get("free") or 0.0), 2),
        "devise": "EUR",
    }
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
