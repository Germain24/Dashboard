"""Ajoute les colonnes de l'optimiseur Voyage v2 sans écraser les données.

Une sauvegarde horodatée est créée à côté du fichier avant toute écriture.
Le script est idempotent.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.backup_storage import backup_file
from app.services.voyage.import_excel import _infer_progression

NEW_COLUMNS = (
    "Progression",
    "Priorité",
    "Coût activité",
    "Transport local",
    "Mois disponibles",
    "Coût hébergement/jour",
    "Coût nourriture/jour",
    "Statut",
    "Raison indisponible",
)


def main() -> None:
    path = settings.imports_dir / "Voyage.xlsx"
    workbook = openpyxl.load_workbook(path)
    sheet = workbook.worksheets[0]
    headers = {cell.value: cell.column for cell in sheet[1] if cell.value}
    missing = [column for column in NEW_COLUMNS if column not in headers]
    if not missing:
        workbook.close()
        print("Voyage.xlsx est déjà au format v2.")
        return

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_file(
        path,
        category="maintenance/upgrade_voyage_xlsx",
        filename=f"Voyage.metadata-backup-{timestamp}.xlsx",
    )
    for column in missing:
        sheet.cell(row=1, column=sheet.max_column + 1, value=column)

    headers = {cell.value: cell.column for cell in sheet[1] if cell.value}
    for row in range(2, sheet.max_row + 1):
        name = sheet.cell(row, headers["Lieux"]).value
        order = sheet.cell(row, headers["Ordre"]).value
        if not name:
            continue
        if not sheet.cell(row, headers["Priorité"]).value:
            sheet.cell(row, headers["Priorité"], value=3)
        if order and not sheet.cell(row, headers["Progression"]).value:
            sheet.cell(
                row, headers["Progression"],
                value=_infer_progression(str(name), int(order)),
            )
        if not sheet.cell(row, headers["Statut"]).value:
            sheet.cell(row, headers["Statut"], value="possible")

        country = str(sheet.cell(row, headers["Pays"]).value or "").casefold()
        if country in {"corée du nord", "coree du nord"}:
            sheet.cell(row, headers["Statut"], value="impossible")
            sheet.cell(
                row, headers["Raison indisponible"],
                value=(
                    "Évitez tout voyage — frontières largement fermées, risque de détention "
                    "arbitraire (Conseils aux voyageurs du Canada, 2026-07-08)"
                ),
            )

    workbook.save(path)
    print(f"Colonnes ajoutées: {', '.join(missing)}")
    print(f"Sauvegarde: {backup}")


if __name__ == "__main__":
    main()
