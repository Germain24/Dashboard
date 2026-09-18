"""Génère les exports Actions et ETF séparés depuis le catalogue SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.finance.buffett.config import Config  # noqa: E402
from app.services.finance.catalog.repository import catalog_dataframe  # noqa: E402
from scripts.migrate_toutbroker_catalog import fix_text  # noqa: E402
from app.services.finance.buffett.leverage_filter import is_leveraged_product  # noqa: E402
from app.services.finance.buffett.manual_etf_sources import (  # noqa: E402
    INPUT_SHEET,
    STATUS_SHEET,
)


def clean_extra_sheet(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in frame.select_dtypes(include=["object", "string"]).columns:
        frame[column] = frame[column].map(fix_text)
    if name == "ETF_Secteurs" and "realestate" in frame.columns:
        if "Immobilier" not in frame.columns:
            frame["Immobilier"] = 0.0
        frame["Immobilier"] = pd.to_numeric(frame["Immobilier"], errors="coerce").fillna(
            0
        ) + pd.to_numeric(frame["realestate"], errors="coerce").fillna(0)
        frame = frame.drop(columns="realestate")
        if "Couverture_pct" in frame.columns:
            frame["Couverture_pct"] = frame["Couverture_pct"].replace(0, None)
    if name == "Indices_Constituants":
        identity_columns = [
            column
            for column in ("Indice_ID", "Indice", "Identifiant_Fournisseur")
            if column in frame.columns
        ]
        for column in identity_columns:
            frame[column] = frame[column].replace({"TOPIX-INDEX": "TOPIX"})
        index_col = (
            "Indice_ID"
            if "Indice_ID" in frame.columns
            else ("Indice" if "Indice" in frame.columns else None)
        )
        constituent_columns = [column for column in ("Ticker", "ISIN") if column in frame.columns]
        if index_col is not None and constituent_columns:
            frame = frame.drop_duplicates(subset=[index_col, *constituent_columns], keep="first")
        else:
            frame = frame.drop_duplicates()
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--actions-output", type=Path, default=Path(Config.BROKER_ACTIONS_FILE),
    )
    parser.add_argument(
        "--etf-output", type=Path, default=Path(Config.BROKER_ETF_FILE),
    )
    parser.add_argument("--extras-from", type=Path)
    parser.add_argument("--extras-only", action="store_true")
    parser.add_argument("--etf-only", action="store_true")
    args = parser.parse_args()
    extras: dict[str, pd.DataFrame] = {}
    # Ces deux feuilles appartiennent à l'utilisateur et à son audit. Un export
    # complet du catalogue doit les préserver même sans ``--extras-from``.
    if args.etf_output.exists():
        current = pd.ExcelFile(args.etf_output, engine="calamine")
        for sheet in (INPUT_SHEET, STATUS_SHEET):
            if sheet in current.sheet_names:
                extras[sheet] = pd.read_excel(
                    args.etf_output, sheet_name=sheet, engine="calamine",
                    keep_default_na=False,
                )
    source = args.extras_from
    if source and source.exists():
        workbook = pd.ExcelFile(source, engine="calamine")
        for sheet in workbook.sheet_names[1:]:
            extras[sheet] = clean_extra_sheet(
                sheet, pd.read_excel(source, sheet_name=sheet, engine="calamine")
            )
    if args.extras_only:
        if not args.etf_output.exists():
            raise SystemExit("L'export ETF cible n'existe pas")
        with pd.ExcelWriter(
            args.etf_output, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as writer:
            for name, extra in extras.items():
                extra.to_excel(writer, sheet_name=name[:31], index=False)
        print(f"Feuilles ETF annexes régénérées: {args.etf_output}")
        return
    frame = catalog_dataframe()
    if frame is None:
        raise SystemExit("Le catalogue SQLite est vide; exécuter d'abord la migration")
    # Le fichier est un export : MOAT n'a aucune valeur sentinelle pour les ETF.
    frame.loc[frame["Secteur 1"].eq("ETF"), "Chance MOAT"] = None
    sector = frame["Secteur 1"].astype(str).str.strip().str.upper()
    etfs = frame.loc[sector.eq("ETF")].copy()
    actions = frame.loc[~sector.eq("ETF")].copy()
    forbidden = etfs["Nom"].map(is_leveraged_product)
    excluded_products = int(forbidden.sum())
    etfs = etfs.loc[~forbidden].copy()
    args.actions_output.parent.mkdir(parents=True, exist_ok=True)
    args.etf_output.parent.mkdir(parents=True, exist_ok=True)
    if not args.etf_only:
        with pd.ExcelWriter(args.actions_output, engine="openpyxl") as writer:
            actions.to_excel(writer, sheet_name="Actions", index=False)
    with pd.ExcelWriter(args.etf_output, engine="openpyxl") as writer:
        etfs.to_excel(writer, sheet_name="ETF", index=False)
        for name, extra in extras.items():
            extra.to_excel(writer, sheet_name=name[:31], index=False)
    print(
        f"Exports générés: {args.actions_output} ({len(actions):,} actions); "
        f"{args.etf_output} ({len(etfs):,} ETF; "
        f"{excluded_products:,} inverses/à levier exclus)"
    )


if __name__ == "__main__":
    main()
