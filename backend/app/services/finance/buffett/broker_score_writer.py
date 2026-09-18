"""Entrée du sous-processus d'export des scores vers ToutBroker.xlsx."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: broker_score_writer PAYLOAD_JSON WORKBOOK", file=sys.stderr)
        return 2
    from .broker_availability import update_broker_file_scores

    with open(sys.argv[1], encoding="utf-8") as stream:
        rows = [SimpleNamespace(**item) for item in json.load(stream)]
    print(update_broker_file_scores(rows, path=sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
