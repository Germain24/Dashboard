# Enrichissement échelles — marques FR intermédiaires — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insérer les marques FR intermédiaires (curées, BonneGueule) juste après la marque d'entrée de chaque échelle pertinente de `Vetements.xlsx`, avec backup et re-sync.

**Architecture:** Une fonction pure `insert_after_entry` + une table curée `ENRICHMENT` (type → marques FR). Un script `main()` sauvegarde l'Excel, réécrit les échelles enrichies, imprime un diff. Le master est gitignoré → non committé ; on commite le script + la table + les tests. Après écriture, on re-sync le cache objectif.

**Tech Stack:** Python + openpyxl ; pytest.

## Global Constraints

- Backend via `uv run` depuis `backend/`.
- `data/imports/Vetements.xlsx` est **gitignoré** → sa modification n'est PAS committée ; on commite uniquement le script + les tests.
- Insertion : chaque marque FR va **juste après la marque d'entrée** (`echelle[0]`), dédupliquée (insensible casse/espaces) vs l'existant et entre elles ; ordre préservé. `insert_after_entry` n'ajoute jamais, ne retire jamais → `len(new) >= len(old)`.
- Sécurité : backup horodaté `Vetements.backup-<YYYYmmdd-HHMMSS>.xlsx` avant écriture ; idempotent (re-run ne duplique pas).
- La table `ENRICHMENT` = celle du spec (verbatim).
- Stager UNIQUEMENT les fichiers de chaque tâche (jamais `git add -A`/`.`).

---

## Task 1: Fonction pure `insert_after_entry` + table `ENRICHMENT`

**Files:**
- Create: `backend/scripts/enrich_bonnegueule.py`
- Test: `backend/tests/test_garderobe/test_enrich_bonnegueule.py`

**Interfaces:**
- Consumes: rien.
- Produces: `insert_after_entry(echelle: list[str], brands: list[str]) -> list[str]` ; `ENRICHMENT: dict[str, list[str]]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garderobe/test_enrich_bonnegueule.py
"""Enrichissement des échelles — fonction pure + table."""
from __future__ import annotations

from scripts.enrich_bonnegueule import ENRICHMENT, insert_after_entry


def test_insert_apres_entree_ordre_preserve():
    assert insert_after_entry(
        ["Uniqlo", "Beams Plus", "Auralee"], ["Asphalte", "Loom"]
    ) == ["Uniqlo", "Asphalte", "Loom", "Beams Plus", "Auralee"]


def test_dedup_vs_existant_insensible_casse():
    # "asphalte" déjà présent (casse différente) -> non ré-inséré
    assert insert_after_entry(
        ["Uniqlo", "Asphalte", "Auralee"], ["asphalte", "Loom"]
    ) == ["Uniqlo", "Loom", "Asphalte", "Auralee"]


def test_dedup_entre_nouvelles():
    assert insert_after_entry(["Uniqlo"], ["Loom", "loom", "Asphalte"]) == [
        "Uniqlo",
        "Loom",
        "Asphalte",
    ]


def test_echelle_vide_et_un_element():
    assert insert_after_entry([], ["A", "B", "a"]) == ["A", "B"]
    assert insert_after_entry(["Uniqlo"], ["Asphalte"]) == ["Uniqlo", "Asphalte"]


def test_jamais_de_retrait_len_croit():
    old = ["Uniqlo", "Beams Plus"]
    new = insert_after_entry(old, ["Asphalte"])
    assert len(new) >= len(old)
    assert set(old).issubset(set(new))


def test_table_enrichment_coherente():
    assert "T-shirts" in ENRICHMENT
    assert ENRICHMENT["Chemises"] == ["Asphalte", "Officine Générale", "De Bonne Facture"]
    # toutes les valeurs sont des listes non vides de chaînes
    for t, brands in ENRICHMENT.items():
        assert isinstance(t, str) and t
        assert brands and all(isinstance(b, str) and b for b in brands)
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`): `uv run pytest tests/test_garderobe/test_enrich_bonnegueule.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.enrich_bonnegueule'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/scripts/enrich_bonnegueule.py
"""Enrichit les échelles de Vetements.xlsx avec des marques FR intermédiaires.

Curation informée BonneGueule : les listes actuelles sont déjà riches (japonais/
anglo + luxe) mais sans marque FR mid-tier. On insère ces marques juste après la
marque d'entrée. Master gitignoré : la modif est locale (backup + re-sync).

Usage (depuis backend/) :
    uv run python -m scripts.enrich_bonnegueule
"""
from __future__ import annotations


def _norm(s: str | None) -> str:
    return " ".join(str(s or "").strip().casefold().split())


def insert_after_entry(echelle: list[str], brands: list[str]) -> list[str]:
    """Insère `brands` juste après `echelle[0]`, dédupliquées (casse/espaces).

    N'ajoute que des marques absentes de `echelle` et non dupliquées entre elles ;
    ordre préservé. Ne retire jamais → len(résultat) >= len(echelle).
    """
    def _dedup(items: list[str], already: set[str]) -> list[str]:
        out: list[str] = []
        seen = set(already)
        for b in items:
            k = _norm(b)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(b)
        return out

    if not echelle:
        return _dedup(brands, set())
    new = _dedup(brands, {_norm(x) for x in echelle})
    return [echelle[0]] + new + echelle[1:]


# Type objectif -> marques FR intermédiaires à insérer (cf. spec).
ENRICHMENT: dict[str, list[str]] = {
    # Hauts
    "T-shirts": ["Loom", "Asphalte", "Le Minor"],
    "Polos": ["Asphalte", "Le Minor"],
    "Chemises": ["Asphalte", "Officine Générale", "De Bonne Facture"],
    "Débardeurs": ["Le Minor", "Saint James"],
    "Pulls": ["Officine Générale", "De Bonne Facture", "Maison Montagut"],
    "Sweats": ["Asphalte", "Maison Labiche"],
    "Gilets": ["Officine Générale", "De Bonne Facture"],
    "Overshirts": ["Asphalte", "De Bonne Facture"],
    # Bas
    "Jeans": ["Asphalte", "1083", "Ateliers de Nîmes"],
    "Pantalons chino": ["Asphalte", "Officine Générale", "De Bonne Facture"],
    "Pantalons habillés": ["Officine Générale", "De Fursac", "Husbands"],
    "Shorts": ["Asphalte"],
    "Pantalons en velours": ["Officine Générale", "De Bonne Facture"],
    # Vestes / manteaux
    "Vestes légères": ["Officine Générale", "De Bonne Facture", "Harmony"],
    "Blazers": ["Officine Générale", "De Fursac", "Husbands"],
    "Manteaux": ["Officine Générale", "Harmony", "Éditions M.R"],
    # Costume
    "Vestes de costume": ["De Fursac", "Husbands", "Samson"],
    "Pantalons de costume": ["De Fursac", "Husbands"],
    "Gilets de costume": ["De Fursac", "Husbands"],
    "Smokings": ["De Fursac", "Husbands"],
    # Sous-vêtements
    "Boxers": ["Le Slip Français"],
    "Slips": ["Le Slip Français"],
    "Maillots de corps": ["Le Slip Français"],
    "Chaussettes": ["Bleuforêt", "Labonal", "Royalties"],
    # Chaussures
    "Bottines": ["Jules & Jenn", "Anthology Paris"],
    "Chaussures de ville": ["Bexley", "Jacques & Déclercq", "Markowski"],
    # Accessoires
    "Ceintures": ["JOSEPH BONNIE", "Bleu de Chauffe"],
    "Cravates": ["Le Colonel Moutarde", "Cinabre"],
    "Nœuds papillon": ["Le Colonel Moutarde", "Cinabre"],
    "Foulards": ["Cinabre"],
    "Lunettes de soleil": ["Jimmy Fairly", "Ateliers Loden"],
    "Sacs à dos": ["Bleu de Chauffe", "Bonastre", "Côme"],
    "Sacs de voyage": ["Bleu de Chauffe", "Bonastre"],
    "Portefeuilles": ["Bleu de Chauffe", "JOSEPH BONNIE"],
    # Technique
    "Maillots techniques": ["Circle Sportswear"],
    "Shorts techniques": ["Circle Sportswear"],
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_garderobe/test_enrich_bonnegueule.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/enrich_bonnegueule.py backend/tests/test_garderobe/test_enrich_bonnegueule.py
git commit -m "feat(garderobe): fonction pure + table d'enrichissement marques FR (BonneGueule)"
```

---

## Task 2: Script `main()` (backup + écriture Excel) + run réel

**Files:**
- Modify: `backend/scripts/enrich_bonnegueule.py` (ajoute `main()` + `__main__`)

**Interfaces:**
- Consumes: `insert_after_entry`, `ENRICHMENT` (Task 1), `settings.imports_dir`.
- Produces: `main() -> dict` (`{"enriched": int, "backup": str, "not_found": list[str]}`), écrit le master (backup avant).

- [ ] **Step 1: Add the implementation**

Append to `backend/scripts/enrich_bonnegueule.py`:

```python
def _echelle_from_row(ws, row: int) -> list[str]:
    """Marques d'une ligne (colonnes C.. = 3..), non vides."""
    out: list[str] = []
    for col in range(3, ws.max_column + 1):
        v = ws.cell(row=row, column=col).value
        if v is not None and str(v).strip():
            out.append(str(v).strip())
    return out


def main() -> dict:
    import datetime as dt
    import shutil

    import openpyxl

    from app.core.config import settings

    path = settings.imports_dir / "Vetements.xlsx"
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"Vetements.backup-{ts}.xlsx")
    shutil.copy2(path, backup)

    wb = openpyxl.load_workbook(path)  # writable (pas read_only)
    ws = wb.worksheets[0]

    found_types: set[str] = set()
    enriched = 0
    for row in range(2, ws.max_row + 1):
        nom_cell = ws.cell(row=row, column=1).value
        if not nom_cell or not str(nom_cell).strip():
            continue
        nom = str(nom_cell).strip()
        found_types.add(nom)
        if nom not in ENRICHMENT:
            continue
        old = _echelle_from_row(ws, row)
        new = insert_after_entry(old, ENRICHMENT[nom])
        if new == old:
            continue
        # insert_after_entry n'ajoute que -> len(new) >= len(old), pas de nettoyage
        for i, brand in enumerate(new):
            ws.cell(row=row, column=3 + i, value=brand)
        enriched += 1
        print(f"{nom}: +{len(new) - len(old)}  {old} -> {new}")

    not_found = sorted(t for t in ENRICHMENT if t not in found_types)
    wb.save(path)
    print(f"types enrichis: {enriched} / {len(ENRICHMENT)} ; backup: {backup.name} ; non trouvés: {not_found}")
    return {"enriched": enriched, "backup": str(backup), "not_found": not_found}


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the enrichment once (backup + write)**

Run: `uv run python -m scripts.enrich_bonnegueule`
Expected: un diff par type enrichi (`Chemises: +3  [...] -> [...]`), puis une ligne finale `types enrichis: 33 / 34 ; backup: Vetements.backup-<ts>.xlsx ; non trouvés: [...]`. **`not_found` DOIT être `[]`** (tous les types de la table existent dans l'Excel) — s'il est non vide, un nom de type ne matche pas (accent/casse) : STOP et corriger la clé dans `ENRICHMENT` avant de continuer.

(Note : le compte « 33/34 » n'est qu'un exemple ; la valeur attendue = `len(ENRICHMENT)` types tous enrichis, `not_found == []`.)

- [ ] **Step 3: Verify the write + backup**

Run:
```bash
uv run python -c "
import openpyxl
from app.core.config import settings
p = settings.imports_dir / 'Vetements.xlsx'
wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
ws = wb.worksheets[0]
for row in ws.iter_rows(values_only=True):
    if row[0] and str(row[0]).strip() == 'Chemises':
        print('Chemises:', [c for c in row[2:] if c])
"
```
Expected: la ligne Chemises contient désormais `Asphalte`, `Officine Générale`, `De Bonne Facture` juste après `Uniqlo`. Vérifier aussi qu'un fichier `Vetements.backup-<ts>.xlsx` existe dans `data/imports/`.

- [ ] **Step 4: Idempotence check**

Run: `uv run python -m scripts.enrich_bonnegueule`
Expected: `types enrichis: 0 / <N>` (les marques sont déjà présentes → aucune ré-insertion) ; un nouveau backup est créé (normal).

- [ ] **Step 5: Re-sync the objectif cache**

Run:
```bash
uv run python -c "
from sqlmodel import Session
from app.core.db import engine
from app.core.config import settings
from app.services.garderobe.objectif_import import sync_objectif
with Session(engine) as s:
    n = sync_objectif(s, settings.imports_dir / 'Vetements.xlsx')
    print('types re-synced:', n)
"
```
Expected: `types re-synced: 55` (le cache reflète les nouvelles échelles ; les positions 0→100 se recalculent au prochain GET).

- [ ] **Step 6: Regression + commit**

Run: `uv run pytest tests/test_garderobe/test_enrich_bonnegueule.py -q`
Expected: PASS.

```bash
git add backend/scripts/enrich_bonnegueule.py
git commit -m "feat(garderobe): script d'enrichissement (backup + écriture Excel + diff)"
```

(Le master `Vetements.xlsx` et les backups sont gitignorés → non committés ; seul le script l'est.)

---

## Self-Review

**1. Spec coverage**
- `insert_after_entry` (après entrée, dédup casse/espaces, jamais de retrait) → Task 1 + tests. ✓
- Table `ENRICHMENT` = spec verbatim (~34 types) → Task 1. ✓
- Script `main()` : backup horodaté, écriture, diff, idempotent → Task 2 (Steps 1-2, 4). ✓
- Master gitignoré non committé → Global Constraints + Task 2 Step 6 note. ✓
- Re-sync du cache après écriture → Task 2 Step 5. ✓
- Vérification (Chemises enrichie, backup présent) → Task 2 Step 3. ✓
- Types non enrichis laissés tels quels → seuls les types ∈ ENRICHMENT sont modifiés. ✓

**2. Placeholder scan** : aucun TODO/placeholder ; code complet à chaque step. (Le « 33/34 » est explicitement noté comme exemple, la vraie attente = `not_found == []`.)

**3. Type consistency** :
- `insert_after_entry(echelle, brands) -> list[str]` : même signature Task 1 (def) et Task 2 (appel dans `main`). ✓
- `ENRICHMENT: dict[str,list[str]]` : défini Task 1, consommé Task 2. ✓
- `_echelle_from_row(ws, row)` renvoie `list[str]` → passé à `insert_after_entry`. ✓
- `main()` écrit col `3 + i` (C=3 en openpyxl 1-based) ; lecture `_echelle_from_row` lit col 3.. → symétrique. ✓
