"""Synchronisation en lecture seule de Kraken et des adresses MetaMask."""

from __future__ import annotations

import datetime as dt
import logging
import os
import threading
import time

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.core.timeutil import utcnow
from app.models.finance import Position, Transaction
from app.models.patrimoine import PatrimoineItem

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_last_refresh = 0.0


def _eur(amount: float, currency: str) -> float:
    if currency.upper() == "EUR":
        return float(amount)
    from app.services.finance.fx import convert
    return float(convert(float(amount), currency.upper(), "EUR", stale_ok=True) or 0)


def _upsert_position(
    session: Session, *, ticker: str, broker: str, quantity: float,
    price_eur: float, pmu: float | None = None,
) -> None:
    row = session.exec(
        select(Position).where(Position.ticker == ticker).where(Position.broker == broker)
    ).first()
    if quantity <= 1e-12:
        if row:
            session.delete(row)
        return
    if not row:
        row = Position(ticker=ticker, broker=broker, quantite=quantity, devise="EUR")
    row.quantite = quantity
    if pmu is not None and pmu >= 0:
        row.pmu = pmu
    row.devise = "EUR"
    row.updated_at = utcnow()
    session.add(row)
    from app.services.finance.prices import set_external_prices
    set_external_prices({ticker: price_eur})


def _ensure_asset(session: Session, label: str) -> None:
    if session.exec(select(PatrimoineItem).where(PatrimoineItem.label == label)).first():
        return
    session.add(PatrimoineItem(
        type="actif", label=label, valeur=0, devise="EUR", categorie="Investissement"
    ))


def _upsert_liability(session: Session, label: str, value_eur: float) -> None:
    row = session.exec(select(PatrimoineItem).where(PatrimoineItem.label == label)).first()
    if not row and value_eur <= 0.005:
        return
    if not row:
        row = PatrimoineItem(
            type="passif", label=label, valeur=0, devise="EUR", categorie="Crypto / DeFi"
        )
    row.type = "passif"
    row.valeur = round(max(0.0, value_eur), 2)
    row.devise = "EUR"
    row.updated_at = utcnow()
    session.add(row)


def _pair_index(pairs: dict[str, dict]) -> tuple[dict[str, tuple[str, str]], dict[str, dict]]:
    from app.services.finance.kraken_api import asset_symbol
    by_name: dict[str, dict] = {}
    decoded: dict[str, tuple[str, str]] = {}
    for key, info in pairs.items():
        base, quote = asset_symbol(info.get("base", "")), asset_symbol(info.get("quote", ""))
        decoded[key] = (base, quote)
        by_name[key] = info
        by_name[str(info.get("altname") or "")] = info
        by_name[str(info.get("wsname") or "").replace("/", "")] = info
    return decoded, by_name


def _kraken_prices(assets: list[str], pairs: dict[str, dict]) -> dict[str, float]:
    from app.services.finance import kraken_api
    from app.services.finance.kraken_api import asset_symbol
    prices: dict[str, float] = {"EUR": 1.0}
    for asset in assets:
        if asset in ("EUR",):
            continue
        if asset in ("USD", "CAD", "GBP", "JPY"):
            prices[asset] = _eur(1, asset)
            continue
        candidate = None
        quote = ""
        for key, info in pairs.items():
            if asset_symbol(info.get("base", "")) == asset:
                q = asset_symbol(info.get("quote", ""))
                if q == "EUR" or (q == "USD" and candidate is None):
                    candidate, quote = key, q
                    if q == "EUR":
                        break
        if not candidate:
            prices[asset] = 0.0
            continue
        tick = kraken_api.public("Ticker", pair=candidate)
        item = next(iter(tick.values()), {})
        last = float((item.get("c") or [0])[0] or 0)
        prices[asset] = last if quote == "EUR" else _eur(last, quote)
    return prices


def _import_kraken_trades(session: Session, pairs: dict[str, dict], prices: dict[str, float]) -> int:
    from app.services.finance import kraken_api
    from app.services.finance.kraken_api import asset_symbol
    _, names = _pair_index(pairs)
    existing_notes = {
        note for note in session.exec(select(Transaction.note).where(Transaction.broker == "Kraken"))
        if note
    }
    added = 0
    for txid, trade in kraken_api.closed_trades():
        note = f"Kraken trade {txid}"
        if note in existing_notes:
            continue
        info = names.get(str(trade.get("pair") or ""), {})
        base = asset_symbol(info.get("base", ""))
        quote = asset_symbol(info.get("quote", ""))
        quantity = float(trade.get("vol") or 0)
        if not base or quantity <= 0:
            continue
        quote_eur = 1.0 if quote == "EUR" else prices.get(quote) or _eur(1, quote)
        session.add(Transaction(
            date=dt.datetime.fromtimestamp(float(trade.get("time") or 0), tz=dt.timezone.utc).replace(tzinfo=None),
            ticker=base,
            broker="Kraken",
            type="achat" if trade.get("type") == "buy" else "vente",
            quantite=quantity,
            prix_unitaire=float(trade.get("price") or 0) * quote_eur,
            devise="EUR",
            frais=float(trade.get("fee") or 0) * quote_eur,
            note=note,
        ))
        added += 1
    return added


def refresh_kraken(session: Session) -> dict | None:
    from app.services.finance import kraken_api
    if not kraken_api.configured():
        return None
    balances = kraken_api.balances()
    pairs = kraken_api.asset_pairs()
    prices = _kraken_prices(list(balances), pairs)
    _import_kraken_trades(session, pairs, prices)

    # Prix de revient moyen issu des achats/ventes importés, sans inventer un
    # coût pour les crypto-actifs reçus par transfert.
    book: dict[str, dict[str, float]] = {}
    for tx in session.exec(select(Transaction).where(Transaction.broker == "Kraken").order_by(Transaction.date)):
        if tx.type not in ("achat", "vente"):
            continue
        b = book.setdefault(tx.ticker, {"q": 0.0, "cost": 0.0})
        if tx.type == "achat":
            b["q"] += tx.quantite
            b["cost"] += tx.quantite * tx.prix_unitaire + tx.frais
        elif b["q"] > 0:
            acb = b["cost"] / b["q"]
            sold = min(tx.quantite, b["q"])
            b["q"] -= sold
            b["cost"] -= sold * acb

    total = 0.0
    current_assets = {
        asset for asset in balances if asset not in ("EUR", "USD", "CAD", "GBP", "JPY")
    }
    for stale in session.exec(select(Position).where(Position.broker == "Kraken")).all():
        if stale.ticker not in current_assets:
            session.delete(stale)
    for asset, quantity in balances.items():
        price = prices.get(asset, 0.0)
        total += quantity * price
        if asset not in ("EUR", "USD", "CAD", "GBP", "JPY"):
            b = book.get(asset) or {}
            pmu = b.get("cost", 0) / b.get("q", 1) if b.get("q", 0) > 0 else None
            _upsert_position(session, ticker=asset, broker="Kraken", quantity=quantity,
                             price_eur=price, pmu=pmu)
    _ensure_asset(session, "Kraken")
    from app.services.finance.account_balances import set_balance
    set_balance("kraken", total, devise="EUR", source="Kraken API")
    return {"value_eur": round(total, 2), "assets": len(balances)}


def _blockscout(network: str, base_url: str, address: str) -> tuple[list[dict], float]:
    address_response = httpx.get(
        f"{base_url.rstrip('/')}/api/v2/addresses/{address}",
        timeout=15,
        follow_redirects=True,
    )
    address_response.raise_for_status()
    address_data = address_response.json()
    tokens_response = httpx.get(
        f"{base_url.rstrip('/')}/api/v2/addresses/{address}/token-balances",
        timeout=15,
        follow_redirects=True,
    )
    tokens_response.raise_for_status()
    tokens_data = tokens_response.json()
    usd_eur = _eur(1, "USD")
    if usd_eur <= 0:
        return {}
    symbol = "ETH" if network == "Ethereum" else "XDAI"
    native_q = float(address_data.get("coin_balance") or 0) / 1e18
    native_p = float(address_data.get("exchange_rate") or 0) * usd_eur
    holdings = [{"ticker": symbol, "quantity": native_q, "price": native_p}]
    for item in tokens_data if isinstance(tokens_data, list) else tokens_data.get("items", []):
        token = item.get("token") or {}
        if str(token.get("type") or "ERC-20").upper() not in ("ERC-20", "ERC20"):
            continue
        decimals = int(token.get("decimals") or 0)
        quantity = float(item.get("value") or 0) / (10 ** decimals if decimals else 1)
        ticker = str(token.get("symbol") or token.get("name") or "TOKEN").upper()
        # Les RealTokens immobiliers suivent ce préfixe. Ne pas utiliser le mot
        # « RealToken » dans le nom : REG et les aTokens RMM le contiennent aussi
        # et seraient sinon pris à tort pour des immeubles dépréciés à zéro.
        is_realt = ticker.startswith("REALTOKEN-")
        price = 0.0 if is_realt else float(token.get("exchange_rate") or 0) * usd_eur
        # Les explorateurs reçoivent beaucoup de faux airdrops « claim… ».
        # Sans cours vérifiable ils ne constituent ni une position ni une valeur.
        if quantity > 1e-12 and (price > 0 or is_realt):
            holdings.append({
                "ticker": ticker,
                "quantity": quantity,
                "price": price,
                "realt": is_realt,
                "contract": token.get("address_hash"),
            })
    return holdings, sum(x["quantity"] * x["price"] for x in holdings)


def _bitcoin(address: str) -> tuple[list[dict], float]:
    base = settings.mempool_base_url.rstrip("/")
    response = httpx.get(f"{base}/address/{address}", timeout=15)
    response.raise_for_status()
    data = response.json()
    chain = data.get("chain_stats") or {}
    mempool = data.get("mempool_stats") or {}
    sats = (chain.get("funded_txo_sum", 0) - chain.get("spent_txo_sum", 0)
            + mempool.get("funded_txo_sum", 0) - mempool.get("spent_txo_sum", 0))
    quantity = float(sats) / 100_000_000
    price_response = httpx.get(f"{base}/v1/prices", timeout=15)
    price_response.raise_for_status()
    prices = price_response.json()
    price = float(prices.get("EUR") or 0)
    return [{"ticker": "BTC", "quantity": quantity, "price": price}], quantity * price


def _realt_cost_basis(address: str) -> dict[str, float]:
    """PMU USD par contrat, calculé par l'historique RealT/YAM/SwapCat/RMM."""
    url = settings.realt_performance_base_url.rstrip("/") + "/api/v1/realtokens-performance"
    response = httpx.get(url, params={"wallet": address}, timeout=120, follow_redirects=True)
    # Le service de performance ne publie pas toujours de données pour un
    # wallet. Dans ce cas les soldes restent valides ; seule la base de coût
    # RealT manque, ce qui doit être traité comme une donnée optionnelle.
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    by_token = response.json().get("performance", {}).get("by_token", {})
    usd_eur = _eur(1, "USD")
    return {
        str(contract).lower(): float(values.get("unrealized", {}).get("avg_cost_per_token") or 0) * usd_eur
        for contract, values in by_token.items()
    }


def _rmm_amount(raw, asset: str) -> float:
    value = float(raw or 0)
    if asset == "USDC":
        # Certaines réponses résumées sont déjà en unités, les événements sont
        # en 6 décimales. Les valeurs minuscules du résumé ne sont pas du wei.
        return value if abs(value) < 100_000 else value / 1_000_000
    return value / 1e18


def _rmm_positions(address: str) -> list[dict]:
    """Actifs fournis et dettes courantes RMM v2/v3, sans double-compter les flux."""
    result: list[dict] = []
    base = settings.rmm_analytics_base_url.rstrip("/")
    for version in ("v2", "v3"):
        response = httpx.get(
            f"{base}/api/rmm/{version}/{address}", timeout=60, follow_redirects=True
        )
        response.raise_for_status()
        rows = response.json().get("data", {}).get("results", [])
        if not rows:
            continue
        interests = rows[0].get("data", {}).get("interests", {})
        for asset, info in interests.items():
            if version == "v3":
                supply = _rmm_amount(info.get("supply", {}).get("summary", {}).get("currentSupply"), asset)
                debt = _rmm_amount(info.get("borrow", {}).get("summary", {}).get("currentDebt"), asset)
            else:
                supply_days = info.get("supply", {}).get("dailyDetails", [])
                debt_days = info.get("borrow", {}).get("dailyDetails", [])
                supply = _rmm_amount(supply_days[-1].get("supply"), asset) if supply_days else 0.0
                debt = _rmm_amount(debt_days[-1].get("debt"), asset) if debt_days else 0.0
            result.append({"version": version.upper(), "asset": asset, "supply": supply, "debt": debt})
    return result


def refresh_metamask(session: Session) -> dict | None:
    networks: list[tuple[str, list[dict], float]] = []
    errors: list[str] = []
    if settings.metamask_ethereum_address:
        try:
            h, v = _blockscout("Ethereum", settings.ethereum_blockscout_url, settings.metamask_ethereum_address)
            networks.append(("Ethereum", h, v))
        except Exception as exc:
            errors.append(f"Ethereum:{type(exc).__name__}")
    if settings.metamask_gnosis_address:
        try:
            h, v = _blockscout("Gnosis", settings.gnosis_blockscout_url, settings.metamask_gnosis_address)
            networks.append(("Gnosis", h, v))
        except Exception as exc:
            errors.append(f"Gnosis:{type(exc).__name__}")
    if settings.metamask_bitcoin_address:
        try:
            h, v = _bitcoin(settings.metamask_bitcoin_address)
            networks.append(("Bitcoin", h, v))
        except Exception as exc:
            errors.append(f"Bitcoin:{type(exc).__name__}")
    if not networks and not errors:
        return None
    realt_costs: dict[str, float] = {}
    if settings.metamask_gnosis_address:
        try:
            realt_costs = _realt_cost_basis(settings.metamask_gnosis_address)
        except Exception as exc:
            errors.append(f"RealT:{type(exc).__name__}")
    total = 0.0
    for network, holdings, value in networks:
        total += value
        broker = f"MetaMask · {network}"
        current = {h["ticker"] for h in holdings}
        for stale in session.exec(select(Position).where(Position.broker == broker)).all():
            if stale.ticker not in current:
                session.delete(stale)
        for h in holdings:
            # Le PMU existant (saisi/importé) est conservé. Pour RealT, cours=0
            # donc toute base de coût enregistrée devient une perte latente totale.
            contract = str(h.get("contract") or "").lower()
            pmu = realt_costs.get(contract) if h.get("realt") else None
            _upsert_position(session, ticker=h["ticker"], broker=broker,
                             quantity=h["quantity"], price_eur=h["price"], pmu=pmu)

    rmm_supply_eur = 0.0
    rmm_debt_eur = 0.0
    if settings.metamask_gnosis_address:
        try:
            rmm_rows = _rmm_positions(settings.metamask_gnosis_address)
            active_keys = set()
            for row in rmm_rows:
                asset = row["asset"]
                unit_eur = _eur(1, "USD") if asset in ("WXDAI", "USDC") else 0.0
                broker = f"MetaMask · RMM {row['version']}"
                ticker = f"RMM-{row['version']}-{asset}"
                if row["supply"] > 1e-12:
                    active_keys.add((ticker, broker))
                    _upsert_position(
                        session, ticker=ticker, broker=broker,
                        quantity=row["supply"], price_eur=unit_eur, pmu=unit_eur,
                    )
                    rmm_supply_eur += row["supply"] * unit_eur
                debt_eur = row["debt"] * unit_eur
                rmm_debt_eur += debt_eur
                _upsert_liability(session, f"RMM dette {row['version']} {asset}", debt_eur)
            for stale in session.exec(select(Position).where(Position.broker.startswith("MetaMask · RMM"))).all():
                if (stale.ticker, stale.broker) not in active_keys:
                    session.delete(stale)
        except Exception as exc:
            errors.append(f"RMM:{type(exc).__name__}")
    total += rmm_supply_eur
    _ensure_asset(session, "MetaMask")
    from app.services.finance.account_balances import set_balance
    set_balance("metamask", total, devise="EUR", source="Blockscout + mempool.space")
    return {
        "value_eur": round(total, 2),
        "networks": len(networks),
        "realt_cost_basis_eur": round(sum(
            h["quantity"] * realt_costs.get(str(h.get("contract") or "").lower(), 0)
            for _, holdings, _ in networks for h in holdings if h.get("realt")
        ), 2),
        "rmm_supply_eur": round(rmm_supply_eur, 2),
        "rmm_debt_eur": round(rmm_debt_eur, 2),
        "errors": errors,
    }


def refresh_external_accounts(session: Session, *, force: bool = False) -> dict:
    """Rafraîchit au plus toutes les 5 minutes, sans bloquer le dashboard."""
    global _last_refresh
    if not force and "PYTEST_CURRENT_TEST" in os.environ:
        return {"status": "disabled_in_tests"}
    now = time.monotonic()
    ttl = max(30, int(settings.external_accounts_refresh_seconds))
    if not force and now - _last_refresh < ttl:
        return {"status": "cached"}
    if not _lock.acquire(blocking=False):
        return {"status": "already_running"}
    result: dict = {"status": "ok"}
    try:
        for name, callback in (("kraken", refresh_kraken), ("metamask", refresh_metamask)):
            try:
                result[name] = callback(session)
            except Exception as exc:
                logger.warning("[%s] synchronisation ignorée: %s", name, exc)
                result[name] = {"error": type(exc).__name__}
        session.commit()
        from app.services.finance.portfolio_state import invalidate_state
        invalidate_state()
        _last_refresh = now
        return result
    finally:
        _lock.release()
