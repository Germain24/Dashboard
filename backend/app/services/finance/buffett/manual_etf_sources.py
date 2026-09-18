"""Entrées Excel persistantes pour ajouter un ETF et router sa composition.

La feuille ne contient jamais les constituants. Elle décrit soit la source
officielle de l'indice, soit un tracker physique exact dont les positions
officielles servent de proxy économique contrôlé.
"""
from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

INPUT_SHEET = "ETF_Manuels"
STATUS_SHEET = "ETF_Manuels_Statut"
INPUT_COLUMNS = [
    "Actif", "ETF_ISIN", "ETF_Ticker", "Nom", "MIC",
    "BoursDirect2", "Trading212", "IBKR", "Indice",
    "Replication_declaree", "Mode_Composition", "URL_Composition",
    "Proxy_ISIN", "Proxy_Ticker", "Commentaire",
]
STATUS_COLUMNS = [
    "ETF_ISIN", "ETF_Ticker", "Indice_ID", "Replication_Verifiee",
    "Source_Utilisee", "URL_Resolue", "Proxy_ISIN", "Proxy_Ticker",
    "Nb_Constituants", "Couverture_Poids_pct",
    "Couverture_Secteur_Pays_pct", "Date_Composition", "Eligible", "Erreur",
]
_LAST_ERRORS: dict[str, str] = {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "nan", "none"} else text


def _true(value: Any) -> bool:
    return _text(value).casefold() in {"1", "1.0", "true", "vrai", "oui", "yes"}


def _workbook_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)
    from .config import Config
    return Path(Config.BROKER_ETF_FILE)


def load_manual_rows(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Charge uniquement les lignes actives; une feuille absente vaut vide."""
    import pandas as pd

    target = _workbook_path(path)
    if not target.exists():
        return []
    try:
        frame = pd.read_excel(
            target, sheet_name=INPUT_SHEET, engine="calamine",
            keep_default_na=False,
        )
    except Exception:
        # Un classeur corrompu (écriture interrompue -> CalamineError/BadZipFile),
        # une feuille absente ou tout autre échec de lecture ne doit jamais faire
        # planter le run : la source de vérité est SQLite. Les saisies manuelles
        # sont alors simplement ignorées le temps de régénérer le classeur.
        try:
            frame = pd.read_excel(
                target, sheet_name=INPUT_SHEET, keep_default_na=False,
            )
        except Exception:
            return []
    rows: list[dict[str, Any]] = []
    for _, raw in frame.iterrows():
        row = {column: raw.get(column, "") for column in INPUT_COLUMNS}
        if not _true(row["Actif"]):
            continue
        row["ETF_Ticker"] = _text(row["ETF_Ticker"]).upper()
        row["ETF_ISIN"] = _text(row["ETF_ISIN"]).upper()
        row["Proxy_Ticker"] = _text(row["Proxy_Ticker"]).upper()
        row["Proxy_ISIN"] = _text(row["Proxy_ISIN"]).upper()
        row["Mode_Composition"] = _text(row["Mode_Composition"]).upper()
        rows.append(row)
    return rows


def merge_manual_etfs(table, path: str | Path | None = None):
    """Superpose les ETF manuels au catalogue en mémoire, sans supprimer de ligne."""
    import pandas as pd
    from .etf_index_registry import valid_isin

    rows = load_manual_rows(path)
    if not rows:
        return table
    out = table.copy() if table is not None else pd.DataFrame()
    if "Ticker Yahoo Finance" not in out:
        out["Ticker Yahoo Finance"] = pd.Series(dtype=object)
    for row in rows:
        ticker = row["ETF_Ticker"]
        isin = valid_isin(row["ETF_ISIN"])
        if not ticker or not isin:
            _LAST_ERRORS[ticker or row["ETF_ISIN"] or "<ligne>"] = (
                "ETF_Ticker et ETF_ISIN valide sont obligatoires"
            )
            continue
        mask = out["Ticker Yahoo Finance"].astype(str).str.strip().str.upper().eq(ticker)
        existing = out.loc[mask]
        if not existing.empty:
            catalog_isin = _text(existing.iloc[0].get("ISIN")).upper()
            if catalog_isin and catalog_isin != isin:
                _LAST_ERRORS[ticker] = f"conflit ISIN catalogue={catalog_isin}, manuel={isin}"
                continue
            index = existing.index[0]
        else:
            if not _text(row["Nom"]) or not _text(row["MIC"]):
                _LAST_ERRORS[ticker] = "Nom et MIC sont obligatoires pour un nouvel ETF"
                continue
            index = len(out)
            out.loc[index, "Ticker Yahoo Finance"] = ticker
        values = {
            "ISIN": isin,
            "Nom": _text(row["Nom"]) or ticker,
            "Primary MIC": _text(row["MIC"]).upper() or None,
            "Type": "ETF", "Secteur": "ETF", "Secteur 1": "ETF",
            "Indice": _text(row["Indice"]),
            "Réplication": _text(row["Replication_declaree"]),
        }
        for column, value in values.items():
            if value not in {None, ""} or column in {"Type", "Secteur", "Secteur 1"}:
                out.loc[index, column] = value
        for broker in ("BoursDirect2", "Trading212", "IBKR"):
            raw = _text(row[broker])
            if raw:
                out.loc[index, broker] = _true(raw)
    return out


def routes_by_ticker(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    for row in load_manual_rows(path):
        ticker = row["ETF_Ticker"]
        if ticker:
            routes[ticker] = row
    return routes


def _validate_public_https_url(url: str) -> str:
    parsed = urlparse(_text(url))
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username:
        raise ValueError("URL HTTPS publique obligatoire")
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise ValueError("hôte local interdit")
    try:
        addresses = [item[4][0] for item in socket.getaddrinfo(hostname, 443)]
    except OSError as exc:
        raise ValueError(f"hôte non résolu: {exc}") from exc
    if not addresses:
        raise ValueError("hôte sans adresse publique")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            raise ValueError("adresse locale/privée interdite")
    return parsed.geturl()


def _get_public(client, url: str):
    current = _validate_public_https_url(url)
    for _ in range(6):
        response = client.get(current, follow_redirects=False)
        if response.status_code not in {301, 302, 303, 307, 308}:
            response.raise_for_status()
            length = int(response.headers.get("content-length") or 0)
            if length > 25 * 1024 * 1024 or len(response.content) > 25 * 1024 * 1024:
                raise ValueError("source supérieure à 25 Mio")
            return response, current
        location = response.headers.get("location")
        if not location:
            raise ValueError("redirection sans destination")
        current = _validate_public_https_url(urljoin(current, location))
    raise ValueError("trop de redirections")


def fetch_manual_holdings(url: str, *, client=None) -> tuple[list[dict], str]:
    """Télécharge un tableau direct ou découvre le tableau lié depuis une page."""
    import httpx
    from bs4 import BeautifulSoup
    from .official_index_enrichment import _read_table, holdings_from_weight_frame

    owns_client = client is None
    http = client or httpx.Client(timeout=35.0)
    try:
        response, resolved = _get_public(http, url)
        content_type = str(response.headers.get("content-type") or "").casefold()
        direct = resolved.casefold().endswith((".csv", ".xls", ".xlsx")) or any(
            marker in content_type for marker in ("csv", "spreadsheet", "excel")
        )
        if direct:
            holdings = holdings_from_weight_frame(_read_table(response, resolved))
            if not holdings:
                raise ValueError("tableau sans poids complets reconnus")
            return holdings, resolved
        soup = BeautifulSoup(response.text, "html.parser")
        candidates: list[tuple[int, str]] = []
        for link in soup.find_all("a", href=True):
            href = urljoin(resolved, str(link.get("href") or ""))
            if not href.casefold().split("?", 1)[0].endswith((".csv", ".xls", ".xlsx")):
                continue
            label = (link.get_text(" ", strip=True) + " " + href).casefold()
            score = sum(marker in label for marker in (
                "constituent", "component", "holding", "composition", "weight", "poids"
            ))
            candidates.append((score, href))
        if not candidates:
            raise ValueError("page sans lien CSV/XLSX de composition reconnu")
        candidates.sort(reverse=True)
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise ValueError("plusieurs fichiers de composition ambigus")
        download, final_url = _get_public(http, candidates[0][1])
        holdings = holdings_from_weight_frame(_read_table(download, final_url))
        if not holdings:
            raise ValueError("fichier lié sans poids complets reconnus")
        return holdings, final_url
    finally:
        if owns_client:
            http.close()


def prepare_manual_official_sources(
    tickers: list[str], metadata: dict[str, dict], *, client=None, budget=None,
) -> dict[str, dict[str, Any]]:
    """Matérialise les routes officielles actives dans le registre d'indices."""
    from .etf_research_budget import ResearchBudgetExceeded
    from .etf_index_registry import (
        cached_index_composition, canonical_index_id, load_registry,
        save_registry, store_index_composition,
    )

    routes = routes_by_ticker()
    for ticker in tickers:
        route = routes.get(ticker)
        if not route or route["Mode_Composition"] != "SOURCE_OFFICIELLE":
            continue
        index_name = _text(route.get("Indice")) or _text(metadata.get(ticker, {}).get("index_name"))
        index_id = canonical_index_id(index_name)
        try:
            if not index_id:
                raise ValueError("Indice obligatoire")
            requested_url = _text(route.get("URL_Composition"))
            registry_data = load_registry()
            stored = registry_data.get("indices", {}).get(index_id, {}).get("composition") or {}
            cached = cached_index_composition(index_id)
            if (
                cached
                and str(stored.get("source") or "")
                == "manual_official_index_constituents"
                and _text(stored.get("manual_route_url")) == requested_url
            ):
                route["_resolved_url"] = _text(cached.get("source_url"))
                _LAST_ERRORS.pop(ticker, None)
                continue
            if budget is not None:
                from .etf_research_budget import BudgetClient
                if not budget.claim("index", f"manual:{requested_url}"):
                    continue
                with httpx.Client(timeout=10.0) as bounded_client:
                    holdings, resolved = fetch_manual_holdings(
                        requested_url, client=BudgetClient(client or bounded_client, budget),
                    )
            else:
                holdings, resolved = fetch_manual_holdings(requested_url, client=client)
            store_index_composition(
                index_id, holdings,
                source="manual_official_index_constituents",
                index_name=index_name, source_url=resolved,
                provider=str(metadata.get(ticker, {}).get("provider") or ""),
                provider_index_id=str(
                    metadata.get(ticker, {}).get("provider_index_id") or index_id
                ),
            )
            registry_data = load_registry()
            registry_data["indices"][index_id]["composition"]["manual_route_url"] = requested_url
            save_registry(registry_data)
            route["_resolved_url"] = resolved
            _LAST_ERRORS.pop(ticker, None)
        except ResearchBudgetExceeded:
            route["_deferred"] = True
        except Exception as exc:
            route["_error"] = str(exc)
            _LAST_ERRORS[ticker] = str(exc)
    return routes


def manual_physical_proxy(
    ticker: str, target_meta: dict[str, Any], registry: dict,
    route: dict[str, Any] | None,
) -> dict | None:
    """Retourne uniquement le proxy physique explicitement demandé et exact."""
    if not route or route.get("Mode_Composition") != "PROXY_PHYSIQUE":
        return None
    from .etf_index_registry import (
        _composition_with_holdings, _registry_target,
        canonical_constituent_set_id, save_registry, valid_isin,
    )
    import datetime as dt

    proxy_isin = valid_isin(route.get("Proxy_ISIN"))
    proxy_ticker = _text(route.get("Proxy_Ticker")).upper()
    target_set = canonical_constituent_set_id(
        target_meta.get("index_name") or target_meta.get("index") or route.get("Indice")
    )
    try:
        if not proxy_isin or not proxy_ticker or not _text(route.get("URL_Composition")):
            raise ValueError("Proxy_ISIN, Proxy_Ticker et URL_Composition obligatoires")
        candidate = next((fund for fund in registry.get("funds", {}).values() if (
            str(fund.get("isin") or "").upper() == proxy_isin
            and proxy_ticker in {str(value).upper() for value in fund.get("tickers") or []}
        )), None)
        if not candidate:
            raise ValueError("proxy absent du registre ou identité ISIN/ticker incohérente")
        if str(candidate.get("replication") or "").casefold() != "physical":
            raise ValueError("le proxy déclaré n'est pas vérifié physique")
        proxy_set = canonical_constituent_set_id(candidate.get("index_name") or "")
        if not target_set or proxy_set != target_set:
            raise ValueError("le proxy ne suit pas exactement le même indice")
        composition = _composition_with_holdings(
            candidate.get("composition"), _registry_target(registry.get("_storage_path")),
        )
        try:
            updated = dt.date.fromisoformat(str(composition.get("updated_at") or "")[:10])
            fresh = (dt.date.today() - updated).days <= 31
        except ValueError:
            fresh = False
        if (
            str(composition.get("source") or "") != "issuer_fund_holdings"
            or not fresh
        ):
            holdings, resolved = fetch_manual_holdings(route.get("URL_Composition", ""))
            total = sum(max(float(item.get("weight") or 0.0), 0.0) for item in holdings)
            today = dt.date.today().isoformat()
            composition = {
                "holdings": holdings, "source": "issuer_fund_holdings",
                "source_url": resolved, "coverage": min(total, 1.0),
                "partial": total < 0.90, "as_of": today,
                "fetched_at": today, "updated_at": today,
            }
            candidate["composition"] = composition
            save_registry(registry, registry.get("_storage_path"))
        if str(composition.get("source") or "") != "issuer_fund_holdings":
            raise ValueError("positions officielles du proxy indisponibles")
        coverage = float(composition.get("coverage") or 0.0)
        if coverage < 0.90:
            raise ValueError("couverture du proxy inférieure à 90 %")
        _LAST_ERRORS.pop(ticker, None)
        return {
            **target_meta, **composition,
            "source": "manual_physical_tracker_proxy",
            "coverage": coverage,
            "proxy_ticker": proxy_ticker, "proxy_isin": proxy_isin,
            "proxy_source_url": _text(route.get("URL_Composition")),
            "index_status": "manual_physical_tracker_proxy",
            "index_source_url": _text(route.get("URL_Composition")),
        }
    except Exception as exc:
        _LAST_ERRORS[ticker] = str(exc)
        return {
            **target_meta, "holdings": [], "source": "manual_route_invalid",
            "index_status": "manual_route_invalid", "index_error": str(exc),
        }


def ensure_manual_sheets(path: str | Path | None = None) -> None:
    """Crée seulement les feuilles absentes; ne remplace jamais les saisies."""
    import pandas as pd
    target = _workbook_path(path)
    if not target.exists():
        return
    with pd.ExcelFile(target, engine="openpyxl") as workbook:
        sheet_names = list(workbook.sheet_names)
    missing = [name for name in (INPUT_SHEET, STATUS_SHEET) if name not in sheet_names]
    if not missing:
        return
    with pd.ExcelWriter(target, engine="openpyxl", mode="a") as writer:
        if INPUT_SHEET in missing:
            pd.DataFrame(columns=INPUT_COLUMNS).to_excel(writer, sheet_name=INPUT_SHEET, index=False)
        if STATUS_SHEET in missing:
            pd.DataFrame(columns=STATUS_COLUMNS).to_excel(writer, sheet_name=STATUS_SHEET, index=False)


def write_manual_status(
    qualities: dict[str, dict[str, Any]], compositions: dict[str, dict[str, Any]],
    path: str | Path | None = None,
) -> int:
    import pandas as pd
    target = _workbook_path(path)
    routes = routes_by_ticker(target)
    if not target.exists() or not routes:
        return 0
    rows = []
    for ticker, route in routes.items():
        quality = qualities.get(ticker, {})
        composition = compositions.get(ticker, {})
        rows.append({
            "ETF_ISIN": route.get("ETF_ISIN", ""), "ETF_Ticker": ticker,
            "Indice_ID": quality.get("index_id", ""),
            "Replication_Verifiee": quality.get("replication", ""),
            "Source_Utilisee": quality.get("source", composition.get("source", "")),
            "URL_Resolue": composition.get("index_source_url") or composition.get("source_url") or route.get("URL_Composition", ""),
            "Proxy_ISIN": quality.get("proxy_isin", route.get("Proxy_ISIN", "")),
            "Proxy_Ticker": quality.get("proxy_ticker", route.get("Proxy_Ticker", "")),
            "Nb_Constituants": len(composition.get("holdings") or []),
            "Couverture_Poids_pct": round(float(quality.get("coverage") or 0) * 100, 4),
            "Couverture_Secteur_Pays_pct": round(float(quality.get("joint_coverage") or 0) * 100, 4),
            "Date_Composition": quality.get("as_of", ""),
            "Eligible": bool(quality.get("eligible", False)),
            "Erreur": _LAST_ERRORS.get(ticker, "") or ("" if quality.get("eligible") else quality.get("reason", "non vérifié")),
        })
    with pd.ExcelWriter(target, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        pd.DataFrame(rows, columns=STATUS_COLUMNS).to_excel(writer, sheet_name=STATUS_SHEET, index=False)
    return len(rows)
