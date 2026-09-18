"""Répare les noms d'indice transformés accidentellement en paragraphes PDF."""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.finance.buffett.etf_index_registry import (  # noqa: E402
    canonical_index_id,
    canonical_index_name,
    infer_index_from_fund_name,
    load_registry,
    save_registry,
)


def _clean_fund_attributes(value: str) -> str:
    value = canonical_index_name(value)
    value = re.sub(
        r"\s*[([]?\b(?:ACC(?:UMULATING)?|DIST(?:RIBUTING)?)\b[)\]]?\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+UCITS\s+ETF.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+SWAP(?:\s+II)?\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+II\s*$", "", value, flags=re.IGNORECASE)
    return canonical_index_name(value)


def main() -> None:
    registry = load_registry()
    funds = registry.get("funds", {})
    indices = registry.get("indices", {})
    repaired = 0
    rejected = 0

    for identity, fund in funds.items():
        previous_name = str(fund.get("index_name") or "")
        if len(previous_name) <= 180:
            continue
        previous_id = str(fund.get("index_id") or "")
        inferred = _clean_fund_attributes(
            infer_index_from_fund_name(fund.get("name") or "")
        )
        old_record = indices.get(previous_id, {})
        if previous_id and identity in (old_record.get("funds") or []):
            old_record["funds"] = [
                item for item in old_record.get("funds") or [] if item != identity
            ]
        fund["rejected_index_name"] = previous_name
        if inferred:
            index_id = canonical_index_id(inferred)
            fund["index_name"] = inferred
            fund["index_id"] = index_id
            fund["index_name_repaired"] = True
            record = indices.setdefault(index_id, {"name": inferred, "funds": []})
            record.setdefault("name", inferred)
            record.setdefault("funds", [])
            if identity not in record["funds"]:
                record["funds"].append(identity)
            repaired += 1
        else:
            fund["index_name"] = ""
            fund["index_id"] = ""
            fund["official_enrichment"] = {
                **(fund.get("official_enrichment") or {}),
                "status": "parse_error",
                "error": "nom d'indice rejeté: un paragraphe PDF avait été capturé",
            }
            rejected += 1

    registry["indices"] = {
        index_id: record
        for index_id, record in indices.items()
        if record.get("funds") or record.get("composition")
    }
    save_registry(registry)
    print({"repaired": repaired, "rejected": rejected})


if __name__ == "__main__":
    main()
