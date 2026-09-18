from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import Workbook

from scripts.import_garde_manger import import_workbook


def _write_workbook(path: Path, rows: list[list[str]], *, brand_header: str = "Martque") -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inventaire"
    sheet.append(["Produit", brand_header, "Quantité"])
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_import_is_dry_run_by_default_and_preserves_source(tmp_path: Path):
    source = tmp_path / "Garde Mange.xlsx"
    _write_workbook(source, [["Graine de chia", "Kirkland Signature", "1,36 Kg"]])
    original_bytes = source.read_bytes()
    pantry = tmp_path / "cuisine_pantry.json"
    manifest = tmp_path / "cuisine_pantry_imports.json"

    result = import_workbook(source, pantry, manifest)

    assert result["applied"] is False
    assert result["added"] == 1
    assert not pantry.exists()
    assert not manifest.exists()
    assert source.read_bytes() == original_bytes


def test_import_preserves_existing_items_metadata_and_is_idempotent(tmp_path: Path):
    source = tmp_path / "Garde Mange.xlsx"
    _write_workbook(source, [
        ["Graine de chia", "Kirkland Signature", "1,36 Kg"],
        ["Pre-Workout Anabolix Freaked", "Anabolix", "375g"],
        ["Multi Vitamin and mineral advanced", "Fusion", "90 tablets"],
        ["Sauce tomate", "Heinz", "540mL"],
    ])
    pantry = tmp_path / "cuisine_pantry.json"
    manifest = tmp_path / "cuisine_pantry_imports.json"
    pantry.write_text(json.dumps([{"id": 7, "ingredient": "Pain", "quantite": 1, "unite": "unité"}]))

    first = import_workbook(source, pantry, manifest, apply=True)
    items = json.loads(pantry.read_text(encoding="utf-8"))
    assert first["added"] == 4
    assert len(items) == 5
    assert items[0]["ingredient"] == "Pain"  # existing pantry data remains untouched
    assert items[1]["id"] == 8

    chia = items[1]
    assert chia["ingredient"] == "Graines de chia"
    assert chia["source_produit"] == "Graine de chia"
    assert chia["marque"] == "Kirkland Signature"
    assert chia["quantite"] == 1.36
    assert chia["unite"] == "kg"
    assert chia["quantite_source"] == "1,36 Kg"
    assert chia["ciqual_code"] == "15047"
    assert chia["ciqual_nom"] == "Chia, graine, séchée"
    assert chia["type_aliment"] == "aliment"
    assert chia["nutrition_label"]["serving_size"] == "15 g"
    assert any(value["nutrient"] == "Calcium" for value in chia["nutrition_label"]["values"])

    supplement = items[2]
    assert supplement["ingredient"] == "Pre-Workout Anabolix Freaked"
    assert supplement["rayon"] == "Compléments"
    assert supplement["type_aliment"] == "supplement"
    assert supplement["optimizer_excluded"] is True

    multivitamin = items[3]
    assert multivitamin["source_url"] == "https://naturalfoodbarn.com/product/multi-vitamin-mineral-advanced-90-tabs/"
    assert multivitamin["type_aliment"] == "supplement"

    unmatched = items[4]
    assert unmatched["ingredient"] == "Sauce tomate"
    assert unmatched["source_produit"] == "Sauce tomate"
    assert unmatched["type_aliment"] == "non_mappe"
    assert unmatched["unite"] == "mL"

    second = import_workbook(source, pantry, manifest, apply=True)
    assert second["already_imported"] is True
    assert second["added"] == 0
    assert len(json.loads(pantry.read_text(encoding="utf-8"))) == 5


def test_same_workbook_can_enrich_existing_row_with_verified_label(tmp_path: Path):
    source = tmp_path / "Garde Mange.xlsx"
    _write_workbook(source, [["Avoine", "Quaker", "10.26Kg"]])
    pantry = tmp_path / "cuisine_pantry.json"
    manifest = tmp_path / "cuisine_pantry_imports.json"
    import_workbook(source, pantry, manifest, apply=True)

    items = json.loads(pantry.read_text(encoding="utf-8"))
    items[0].pop("nutrition_label")
    pantry.write_text(json.dumps(items), encoding="utf-8")
    result = import_workbook(source, pantry, manifest, apply=True)

    assert result["updated"] == 1
    enriched = json.loads(pantry.read_text(encoding="utf-8"))[0]
    assert enriched["source_import_key"] == items[0]["source_import_key"]
    assert enriched["nutrition_label"]["source_label"].startswith("Quaker")


def test_changed_workbook_only_adds_new_rows(tmp_path: Path):
    source = tmp_path / "Garde Mange.xlsx"
    _write_workbook(source, [["Avoine", "Quaker", "10.26Kg"]])
    pantry = tmp_path / "cuisine_pantry.json"
    manifest = tmp_path / "cuisine_pantry_imports.json"
    import_workbook(source, pantry, manifest, apply=True)

    _write_workbook(source, [
        ["Avoine", "Quaker", "10.26Kg"],
        ["Vinaigre balsamique", "Liv 99", "250mL"],
    ], brand_header="Marque")
    result = import_workbook(source, pantry, manifest, apply=True)
    items = json.loads(pantry.read_text(encoding="utf-8"))

    assert result["added"] == 1
    assert result["skipped"] == 1
    assert len(items) == 2
    assert items[0]["ingredient"] == "Flocons d'avoine"
    assert items[0]["ciqual_code"] == "9311"
    vinegar = items[1]
    assert vinegar["ingredient"] == "Vinaigre balsamique"
    assert vinegar["ciqual_code"] == "11091"
    assert vinegar["type_aliment"] == "non_mappe"


def test_curated_ciqual_codes_and_optimizer_names_exist_in_catalog():
    repo_root = Path(__file__).resolve().parents[3]
    ciqual_path = repo_root / "data" / "imports" / "Sante" / "ciqual" / "ciqual_normalise.csv"
    catalog_path = repo_root / "data" / "imports" / "Sante" / "tableur" / "aliments.csv"
    with ciqual_path.open(encoding="utf-8-sig", newline="") as handle:
        ciqual = {row["CiqualCode"]: row["CiqualNom"] for row in csv.DictReader(handle, delimiter=";")}
    with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
        optimizer_names = next(csv.reader(handle, delimiter=";"))[1:]

    from scripts.import_garde_manger import _MATCHES

    for match in _MATCHES.values():
        assert ciqual[match["ciqual_code"]] == match["ciqual_nom"]
        if "ingredient" in match:
            assert match["ingredient"] in optimizer_names
