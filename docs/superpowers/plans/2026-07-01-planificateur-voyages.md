# Planificateur de voyages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** À partir de la wishlist de lieux à visiter (`data/imports/Voyage.xlsx`) et de contraintes de dates/budget/départ-arrivée, proposer l'itinéraire qui maximise le nombre de lieux visités.

**Architecture:** Excel = master data (comme `Vetements.xlsx`), importé dans une table cache `lieu_voyage`. Prix/durées de vol récupérés en direct via l'API REST Duffel (httpx, pas de SDK — le SDK officiel `duffel-api` est explicitement non maintenu), mis en cache en DB. Le choix des lieux + leur ordre est résolu par un solveur OR-Tools CP-SAT (circuit optionnel), fonction pure séparée de tout I/O. Confirmation d'un voyage = écrit `Visité=True` dans l'Excel (backup horodaté) + DB en une seule opération.

**Tech Stack:** FastAPI, SQLModel, pandas/openpyxl (Excel), httpx (Duffel REST), OR-Tools CP-SAT (`ortools`, nouvelle dépendance), Next.js/TanStack Query.

## Global Constraints

- Spec source : `docs/superpowers/specs/2026-07-01-planificateur-voyages-design.md`
- Un seul voyage planifié par requête (pas de répartition multi-voyages).
- Candidats plafonnés à 25 par requête de planification (contrainte dure, 400 si dépassée).
- `DUFFEL_API_KEY` optionnelle dans `.env` — le module dégrade proprement (pas de plantage) si absente.
- Coût du séjour (hébergement + repas + activités + transport local) = un seul champ manuel `Coût/jour estimé` par lieu dans l'Excel (pas d'API pour cette partie — Duffel Stays est gated commercialement, pas d'alternative gratuite fiable trouvée).
- Prix/durée de vol = une seule requête Duffel par paire de lieux, à `date_debut` comme date de référence (pas de recalcul par position dans l'itinéraire).
- `Ordre` (colonne existante de `Voyage.xlsx`) n'est ni lu ni modifié par ce module.

---

### Task 1: Modèle `LieuVoyage` + `DuffelPriceCache`

**Files:**
- Create: `backend/app/models/voyage.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_voyage/__init__.py` (vide), `backend/tests/test_voyage/test_models.py`

**Interfaces:**
- Produces: `LieuVoyage` (champs : `id: int`, `nom: str`, `ville: str | None`, `pays: str | None`, `visite: bool`, `aeroport_iata: str | None`, `jours_min: int | None`, `jours_max: int | None`, `cout_jour_estime: float | None`) ; `DuffelPriceCache` (champs : `cache_key: str` (PK, `"{origine}|{destination}|{date}"`), `origine_iata: str`, `destination_iata: str`, `date_reference: str`, `prix: float`, `devise: str`, `duree_min: int`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_voyage/__init__.py
```
(fichier vide)

```python
# backend/tests/test_voyage/test_models.py
"""Modèles LieuVoyage + DuffelPriceCache."""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401 — enregistre toutes les tables
from app.models.voyage import DuffelPriceCache, LieuVoyage


def _mem_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_lieu_voyage_roundtrip():
    with _mem_session() as s:
        lv = LieuVoyage(
            nom="Table Mountain", ville="Le Cap", pays="Afrique du Sud", visite=False,
            aeroport_iata="CPT", jours_min=2, jours_max=4, cout_jour_estime=80.0,
        )
        s.add(lv)
        s.commit()
        s.refresh(lv)
        got = s.get(LieuVoyage, lv.id)
        assert got is not None
        assert got.nom == "Table Mountain"
        assert got.cout_jour_estime == 80.0


def test_lieu_voyage_defaults():
    with _mem_session() as s:
        lv = LieuVoyage(nom="K-2")
        s.add(lv)
        s.commit()
        s.refresh(lv)
        assert lv.visite is False
        assert lv.ville is None
        assert lv.aeroport_iata is None


def test_duffel_price_cache_roundtrip():
    with _mem_session() as s:
        s.add(DuffelPriceCache(
            cache_key="YUL|NRT|2026-09-01", origine_iata="YUL", destination_iata="NRT",
            date_reference="2026-09-01", prix=375.78, devise="USD", duree_min=863,
        ))
        s.commit()
        got = s.get(DuffelPriceCache, "YUL|NRT|2026-09-01")
        assert got is not None
        assert got.duree_min == 863
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`) : `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_models.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.models.voyage'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/models/voyage.py
"""Modèles Voyage — planificateur d'itinéraire (liste de lieux à visiter).

Tables :
  - `lieu_voyage`         : cache de la wishlist (master = data/imports/Voyage.xlsx)
  - `duffel_price_cache`  : cache des prix/durées de vol Duffel (paire aéroports + date)
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel


class LieuVoyage(SQLModel, table=True):
    """Cache d'un lieu de la wishlist voyage.

    Écrasé à chaque POST /voyage/sync, sauf `visite` qui est aussi écrit
    directement dans l'Excel par POST /voyage/confirmer (import_excel.py) —
    la synchro Excel->DB est un import destructif, donc l'Excel doit rester
    la source de vérité pour ce champ.
    """

    __tablename__ = "lieu_voyage"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    ville: Optional[str] = None
    pays: Optional[str] = None
    visite: bool = False
    aeroport_iata: Optional[str] = None
    jours_min: Optional[int] = None
    jours_max: Optional[int] = None
    cout_jour_estime: Optional[float] = None


class DuffelPriceCache(SQLModel, table=True):
    """Cache d'une offre de vol Duffel pour une paire aéroports + date de référence."""

    __tablename__ = "duffel_price_cache"

    cache_key: str = Field(primary_key=True)  # f"{origine_iata}|{destination_iata}|{date_reference}"
    origine_iata: str
    destination_iata: str
    date_reference: str  # "YYYY-MM-DD"
    prix: float
    devise: str
    duree_min: int
```

Ajouter au bas de `backend/app/models/__init__.py` :

```python
from app.models.voyage import DuffelPriceCache, LieuVoyage  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Créer la migration Alembic**

Run (depuis `backend/`) : `uv run alembic revision --autogenerate -m "add lieu_voyage and duffel_price_cache tables"` (équivalent à `make migrate-new m="add lieu_voyage and duffel_price_cache tables"` depuis la racine du repo)
Vérifier le fichier généré dans `backend/alembic/versions/` : il doit créer `lieu_voyage` et `duffel_price_cache` avec exactement les colonnes ci-dessus. Puis appliquer : `uv run alembic upgrade head`.

- [ ] **Step 6: Commit**

```bash
git add app/models/voyage.py app/models/__init__.py tests/test_voyage/ alembic/versions/
git commit -m "feat(voyage): modèles LieuVoyage + DuffelPriceCache"
```

---

### Task 2: Import Excel (`Voyage.xlsx` → cache DB)

**Files:**
- Create: `backend/app/services/voyage/__init__.py`, `backend/app/services/voyage/import_excel.py`
- Test: `backend/tests/test_voyage/test_import_excel.py`

**Interfaces:**
- Consumes: `LieuVoyage` (Task 1)
- Produces: `parse_voyage_xlsx(path: Path) -> list[dict]` (dicts avec les clés exactes des champs `LieuVoyage`, sans `id`) ; `sync_voyage(session: Session, path: Path) -> dict` (retourne `{"lieux": int, "incomplets": list[str]}`)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_voyage/test_import_excel.py
"""Import Voyage.xlsx -> cache lieu_voyage."""
from __future__ import annotations

import openpyxl
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.voyage import LieuVoyage
from app.services.voyage.import_excel import parse_voyage_xlsx, sync_voyage


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre",
               "Aéroport (IATA)", "Jours min", "Jours max", "Coût/jour estimé"])
    ws.append(["Table Mountain", "Le Cap", "Afrique du Sud", False, 1, "CPT", 2, 4, 80])
    ws.append(["K-2", "K-2", "Chine", False, 5, None, None, None, None])  # incomplet
    ws.append(["Robben Island", "Le Cap", "Afrique du Sud", True, None, "CPT", 1, 1, 60])  # déjà visité
    ws.append([None, None, None, None, None, None, None, None, None])  # ligne vide -> ignorée
    wb.save(path)


def test_parse_voyage_xlsx(tmp_path):
    p = tmp_path / "Voyage.xlsx"
    _make_xlsx(p)
    rows = parse_voyage_xlsx(p)
    assert len(rows) == 3
    assert rows[0] == {
        "nom": "Table Mountain", "ville": "Le Cap", "pays": "Afrique du Sud", "visite": False,
        "aeroport_iata": "CPT", "jours_min": 2, "jours_max": 4, "cout_jour_estime": 80.0,
    }
    assert rows[1]["aeroport_iata"] is None
    assert rows[1]["jours_min"] is None
    assert rows[2]["visite"] is True


def test_sync_voyage_wipes_and_refills_and_flags_incomplete(tmp_path, session):
    p = tmp_path / "Voyage.xlsx"
    _make_xlsx(p)
    session.add(LieuVoyage(nom="Obsolète"))
    session.commit()

    result = sync_voyage(session, p)

    assert result["lieux"] == 3
    assert result["incomplets"] == ["K-2"]  # non visité + aéroport/jours manquants
    noms = {lv.nom for lv in session.exec(select(LieuVoyage)).all()}
    assert noms == {"Table Mountain", "K-2", "Robben Island"}  # ancien "Obsolète" effacé


def test_sync_voyage_does_not_flag_incomplete_if_already_visited(tmp_path, session):
    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre",
               "Aéroport (IATA)", "Jours min", "Jours max", "Coût/jour estimé"])
    ws.append(["Déjà fait", "Paris", "France", True, None, None, None, None, None])
    wb.save(p)

    result = sync_voyage(session, p)
    assert result["incomplets"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_import_excel.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.voyage'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/voyage/__init__.py
```
(fichier vide — package)

```python
# backend/app/services/voyage/import_excel.py
"""Import / sync de la wishlist voyage depuis Voyage.xlsx (master)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.voyage import LieuVoyage

_COLS = {
    "nom": "Lieux",
    "ville": "Ville (ou ville la plus proche)",
    "pays": "Pays",
    "visite": "Visité",
    "aeroport_iata": "Aéroport (IATA)",
    "jours_min": "Jours min",
    "jours_max": "Jours max",
    "cout_jour_estime": "Coût/jour estimé",
}


def _clean_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clean_int(v: Any) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    return int(float(v))


def _clean_float(v: Any) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    return float(v)


def parse_voyage_xlsx(path: Path) -> list[dict]:
    """Lit la feuille 0 par en-têtes de colonnes (cf. `_COLS`).

    Les lignes sans `Lieux` sont ignorées. Les colonnes manquantes du fichier
    (ex. avant l'ajout des nouvelles colonnes) donnent des valeurs `None`.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    header = rows[0] if rows else []
    col_idx = {name: header.index(label) for name, label in _COLS.items() if label in header}

    def _cell(row: tuple, name: str):
        i = col_idx.get(name)
        return row[i] if i is not None and i < len(row) else None

    out: list[dict] = []
    for row in rows[1:]:
        nom = _clean_str(_cell(row, "nom"))
        if not nom:
            continue
        out.append({
            "nom": nom,
            "ville": _clean_str(_cell(row, "ville")),
            "pays": _clean_str(_cell(row, "pays")),
            "visite": bool(_cell(row, "visite")),
            "aeroport_iata": _clean_str(_cell(row, "aeroport_iata")),
            "jours_min": _clean_int(_cell(row, "jours_min")),
            "jours_max": _clean_int(_cell(row, "jours_max")),
            "cout_jour_estime": _clean_float(_cell(row, "cout_jour_estime")),
        })
    return out


def sync_voyage(session: Session, path: Path) -> dict:
    """Écrase la table cache `lieu_voyage` avec le contenu de l'Excel.

    Retourne `{"lieux": n, "incomplets": [noms]}` — un lieu non visité sans
    aéroport IATA ou sans fourchette de jours n'est pas utilisable comme
    candidat de planification.
    """
    rows = parse_voyage_xlsx(path)
    for old in session.exec(select(LieuVoyage)).all():
        session.delete(old)
    incomplets: list[str] = []
    for r in rows:
        session.add(LieuVoyage(**r))
        if not r["visite"] and (
            not r["aeroport_iata"] or r["jours_min"] is None or r["jours_max"] is None
        ):
            incomplets.append(r["nom"])
    session.commit()
    return {"lieux": len(rows), "incomplets": incomplets}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_import_excel.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/voyage/__init__.py app/services/voyage/import_excel.py tests/test_voyage/test_import_excel.py
git commit -m "feat(voyage): import Excel Voyage.xlsx -> cache lieu_voyage"
```

---

### Task 3: Écriture Excel (confirmer un voyage → `Visité=True`)

**Files:**
- Modify: `backend/app/services/voyage/import_excel.py`
- Test: `backend/tests/test_voyage/test_import_excel.py` (ajouts)

**Interfaces:**
- Consumes: `LieuVoyage` (Task 1)
- Produces: `marquer_visites(session: Session, path: Path, noms: list[str]) -> Path` (retourne le chemin du backup créé)

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_voyage/test_import_excel.py` :

```python
def test_marquer_visites_writes_excel_and_db(tmp_path, session):
    from app.services.voyage.import_excel import marquer_visites

    p = tmp_path / "Voyage.xlsx"
    _make_xlsx(p)
    sync_voyage(session, p)  # peuple la DB depuis l'Excel initial

    backup = marquer_visites(session, p, ["Table Mountain"])

    assert backup.exists()
    assert backup.name.startswith("Voyage.backup-")

    # Excel mis à jour
    import openpyxl
    wb = openpyxl.load_workbook(p, data_only=True)
    ws = wb.active
    header = [c.value for c in ws[1]]
    col_lieux = header.index("Lieux") + 1
    col_visite = header.index("Visité") + 1
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, col_lieux).value == "Table Mountain")
    assert ws.cell(row, col_visite).value is True
    # les autres lignes ne sont pas touchées
    row_k2 = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, col_lieux).value == "K-2")
    assert ws.cell(row_k2, col_visite).value is False

    # DB mise à jour dans la même opération
    lv = session.exec(select(LieuVoyage).where(LieuVoyage.nom == "Table Mountain")).first()
    assert lv.visite is True


def test_marquer_visites_raises_if_columns_missing(tmp_path, session):
    from app.services.voyage.import_excel import marquer_visites

    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["Autre chose"])
    wb.save(p)

    with pytest.raises(ValueError):
        marquer_visites(session, p, ["X"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_import_excel.py -v`
Expected: FAIL avec `ImportError: cannot import name 'marquer_visites'`

- [ ] **Step 3: Write minimal implementation**

Ajouter à la fin de `backend/app/services/voyage/import_excel.py` :

```python
def marquer_visites(session: Session, path: Path, noms: list[str]) -> Path:
    """Marque `noms` comme visités : backup horodaté, écrit `Visité=True`
    dans l'Excel (ligne trouvée par correspondance exacte de `Lieux`), et
    met à jour le cache DB en une seule opération.

    Nécessaire car `sync_voyage` est un import destructif (écrase la table) :
    sans écriture Excel, la prochaine synchro effacerait `visite=True`.
    """
    import datetime as dt
    import shutil

    import openpyxl

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.backup-{ts}{path.suffix}")
    shutil.copy2(path, backup)

    wb = openpyxl.load_workbook(path)  # writable (pas read_only)
    ws = wb.worksheets[0]
    header = {cell.value: cell.column for cell in ws[1]}
    col_lieux = header.get(_COLS["nom"])
    col_visite = header.get(_COLS["visite"])
    if col_lieux is None or col_visite is None:
        raise ValueError(f"Colonnes '{_COLS['nom']}' ou '{_COLS['visite']}' introuvables dans {path}")

    remaining = set(noms)
    for row in range(2, ws.max_row + 1):
        cell_nom = ws.cell(row=row, column=col_lieux).value
        if cell_nom and str(cell_nom).strip() in remaining:
            ws.cell(row=row, column=col_visite, value=True)
            remaining.discard(str(cell_nom).strip())
    wb.save(path)

    for lv in session.exec(select(LieuVoyage).where(LieuVoyage.nom.in_(noms))).all():
        lv.visite = True
        session.add(lv)
    session.commit()
    return backup
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_import_excel.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/voyage/import_excel.py tests/test_voyage/test_import_excel.py
git commit -m "feat(voyage): écriture Visité=True dans Voyage.xlsx (backup + DB)"
```

---

### Task 4: Config Duffel + client Duffel (prix/durée de vol, avec cache)

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/services/voyage/duffel_client.py`
- Test: `backend/tests/test_voyage/test_duffel_client.py`

**Interfaces:**
- Consumes: `DuffelPriceCache` (Task 1), `settings.duffel_api_key`
- Produces: `fetch_offer(session: Session, origine_iata: str, destination_iata: str, date_reference: str, *, http_post=None) -> dict | None` (retourne `{"prix": float, "devise": str, "duree_min": int}` ou `None`)

**Format confirmé par appel réel à l'API Duffel (test du 2026-07-01, clé de test) :**
`POST https://api.duffel.com/air/offer_requests?return_offers=true`, headers `Authorization: Bearer <clé>`, `Duffel-Version: v2`, body `{"data": {"slices": [{"origin": IATA, "destination": IATA, "departure_date": "YYYY-MM-DD"}], "passengers": [{"type": "adult"}], "cabin_class": "economy"}}` → statut 201, `data.offers[].total_amount` (str décimal), `data.offers[].total_currency` (ex. `"USD"`), `data.offers[].slices[0].duration` (ISO 8601, ex. `"PT14H23M"`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_voyage/test_duffel_client.py
"""Client Duffel — prix/durée de vol avec cache DB."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.core.config import settings
from app.models.voyage import DuffelPriceCache
from app.services.voyage.duffel_client import fetch_offer


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


_OFFERS_PAYLOAD = {
    "data": {
        "offers": [
            {"total_amount": "500.00", "total_currency": "USD",
             "slices": [{"duration": "PT10H0M"}]},
            {"total_amount": "375.78", "total_currency": "USD",  # moins cher -> retenu
             "slices": [{"duration": "PT14H23M"}]},
        ]
    }
}


def test_fetch_offer_returns_cheapest_and_caches(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "duffel_test_fake")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(201, _OFFERS_PAYLOAD)

    result = fetch_offer(session, "YUL", "NRT", "2026-09-01", http_post=fake_post)

    assert result == {"prix": 375.78, "devise": "USD", "duree_min": 863}
    assert len(calls) == 1

    # deuxième appel : servi depuis le cache, pas de nouvel appel HTTP
    result2 = fetch_offer(session, "YUL", "NRT", "2026-09-01", http_post=fake_post)
    assert result2 == result
    assert len(calls) == 1

    cached = session.get(DuffelPriceCache, "YUL|NRT|2026-09-01")
    assert cached is not None
    assert cached.duree_min == 863


def test_fetch_offer_returns_none_without_api_key(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "")
    assert fetch_offer(session, "YUL", "NRT", "2026-09-01", http_post=lambda *a, **k: None) is None


def test_fetch_offer_returns_none_on_error_status(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "duffel_test_fake")
    result = fetch_offer(session, "YUL", "XXX", "2026-09-01",
                          http_post=lambda *a, **k: _FakeResponse(422, {"errors": []}))
    assert result is None


def test_fetch_offer_returns_none_when_no_offers(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "duffel_test_fake")
    result = fetch_offer(session, "YUL", "XXX", "2026-09-01",
                          http_post=lambda *a, **k: _FakeResponse(201, {"data": {"offers": []}}))
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_duffel_client.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.voyage.duffel_client'`

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/app/core/config.py`, juste après le bloc `# --- Garde-robe (CONV 2) ---` (ligne ~86, avant `# ── Réglages métier ajustables`) :

```python
    # --- Voyage (planificateur d'itinéraire) ---
    # Clé de test/prod Duffel (https://duffel.com) — recherche d'offres de vols.
    # Vide = module désactivé (fetch_offer renvoie toujours None).
    duffel_api_key: str = ""
```

```python
# backend/app/services/voyage/duffel_client.py
"""Client Duffel (REST direct, pas de SDK — le SDK officiel `duffel-api` sur
PyPI est explicitement non maintenu par Duffel) : prix/durée de vol le moins
cher entre deux aéroports à une date donnée, avec cache DB.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from sqlmodel import Session

from app.core.config import settings
from app.models.voyage import DuffelPriceCache

_OFFER_REQUESTS_URL = "https://api.duffel.com/air/offer_requests?return_offers=true"
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")


def _parse_iso_duration_min(duration: str) -> int:
    """« PT14H23M » -> 863 (minutes). Format ISO 8601 renvoyé par Duffel."""
    m = _DURATION_RE.fullmatch(duration)
    if not m:
        return 0
    heures = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    return heures * 60 + minutes


def _cache_key(origine: str, destination: str, date_reference: str) -> str:
    return f"{origine}|{destination}|{date_reference}"


def fetch_offer(
    session: Session,
    origine_iata: str,
    destination_iata: str,
    date_reference: str,
    *,
    http_post: Optional[Callable[..., Any]] = None,
) -> Optional[dict]:
    """Prix/durée de l'offre la moins chère entre deux aéroports à `date_reference`.

    Résultat mis en cache en DB (clé aéroports+date) : un second appel pour la
    même paire ne re-sollicite pas Duffel. `http_post` est injectable pour les
    tests (même signature que `httpx.post` : `(url, **kwargs) -> response` avec
    `response.status_code` et `response.json()`) ; en production, `httpx.post`.

    Retourne `None` si pas de clé API configurée, pas d'offre disponible, ou
    statut HTTP différent de 201 (jamais de levée d'exception réseau/API).
    """
    if not settings.duffel_api_key:
        return None

    key = _cache_key(origine_iata, destination_iata, date_reference)
    cached = session.get(DuffelPriceCache, key)
    if cached:
        return {"prix": cached.prix, "devise": cached.devise, "duree_min": cached.duree_min}

    poster = http_post
    if poster is None:
        import httpx
        poster = httpx.post

    resp = poster(
        _OFFER_REQUESTS_URL,
        headers={
            "Authorization": f"Bearer {settings.duffel_api_key}",
            "Duffel-Version": "v2",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "data": {
                "slices": [{"origin": origine_iata, "destination": destination_iata,
                             "departure_date": date_reference}],
                "passengers": [{"type": "adult"}],
                "cabin_class": "economy",
            }
        },
        timeout=30,
    )
    if resp.status_code != 201:
        return None
    offers = resp.json().get("data", {}).get("offers", [])
    if not offers:
        return None

    cheapest = min(offers, key=lambda o: float(o["total_amount"]))
    result = {
        "prix": float(cheapest["total_amount"]),
        "devise": cheapest["total_currency"],
        "duree_min": _parse_iso_duration_min(cheapest["slices"][0]["duration"]),
    }
    session.add(DuffelPriceCache(
        cache_key=key, origine_iata=origine_iata, destination_iata=destination_iata,
        date_reference=date_reference, **result,
    ))
    session.commit()
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_duffel_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py app/services/voyage/duffel_client.py tests/test_voyage/test_duffel_client.py
git commit -m "feat(voyage): client Duffel (prix/durée de vol) avec cache DB"
```

---

### Task 5: Solveur d'itinéraire (OR-Tools CP-SAT)

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/services/voyage/solver.py`
- Test: `backend/tests/test_voyage/test_solver.py`

**Interfaces:**
- Produces: `solve_itinerary(candidats: list[dict], trajets: dict[tuple[str, str], dict], budget_total: float, jours_disponibles: int, depart_id: str = "DEPART", arrivee_id: str = "ARRIVEE") -> list[dict] | None`. `candidats` : `[{"id": str, "jours_min": int, "jours_max": int, "cout_jour": float}, ...]`. `trajets` : `{(origine_id, destination_id): {"prix": float, "duree_min": int}}` pour **chaque paire ordonnée** parmi `{depart_id} ∪ {candidat["id"]} ∪ {arrivee_id}`. Retour : liste ordonnée (ordre du parcours) `[{"id": str, "jours": int}, ...]` (peut être vide — aucun candidat ne rentre mais le trajet direct depart→arrivee est possible), ou `None` si même le trajet direct dépasse budget/jours.

Algorithme vérifié manuellement avant écriture de ce plan (voir note ci-dessous) : circuit optionnel CP-SAT (`AddCircuit`) sur les nœuds `{depart} ∪ candidats ∪ {arrivee}`, chaque candidat a une boucle sur lui-même (non retenu) ou fait partie du chemin ; un arc virtuel `arrivee → depart` (coût/durée nuls) ferme le circuit pour satisfaire `AddCircuit` sans que ce soit un vrai trajet. Piège identifié pendant la vérification : la variable de durée d'un candidat doit être forcée à 0 s'il est écarté (sinon son `jours_min` grève le budget temps même non visité) — géré via une contrainte réifiée sur le literal de saut.

**Correction post-implémentation (Task 5 bloquée par son implémenteur, diagnostic confirmé) :** l'objectif initial (`maximiser Σ visite[i]` seul) ne contraint en rien la durée choisie pour un candidat retenu à l'intérieur de `[jours_min, jours_max]` — CP-SAT peut légitimement renvoyer n'importe quelle valeur de la fourchette, et ce choix s'est avéré non déterministe d'une machine à l'autre (vérifié : `jours_max` sur la machine de vérification initiale, `jours_min` sur la machine de l'implémenteur, avec un modèle pourtant identique). L'objectif est donc **lexicographique** : `maximiser (Σ visite[i]) × BIG − Σ jours_total`, avec `BIG = jours_disponibles + 1` (borne sûre qui garantit que l'objectif primaire domine toujours le secondaire). Effet : à nombre de lieux égal, minimise le total de jours utilisés — un lieu retenu sans autre contrainte reçoit `jours_min`, jamais plus, sauf si prolonger le séjour est nécessaire pour respecter une autre contrainte (ce qui n'arrive jamais ici puisque rester plus longtemps ne peut qu'augmenter le coût). Re-vérifié sur les 6 scénarios de test ci-dessous avant de débloquer l'implémenteur.

- [ ] **Step 1: Add the new dependency**

Dans `backend/pyproject.toml`, ajouter à la liste `dependencies` (après le bloc `# Util`) :

```toml
    # Voyage — solveur d'itinéraire (circuit optionnel / orienteering)
    "ortools>=9.15.0",
```

Run (depuis `backend/`) : `uv sync`
Expected : `ortools` installé sans erreur (confirmé fonctionnel en 9.15.6755 lors de la vérification de ce plan).

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_voyage/test_solver.py
"""Solveur d'itinéraire — circuit optionnel OR-Tools CP-SAT."""
from __future__ import annotations

import itertools

from app.services.voyage.solver import solve_itinerary


def _trajets_uniformes(points: list[str], prix: float, duree_min: int) -> dict:
    return {(a, b): {"prix": prix, "duree_min": duree_min} for a, b in itertools.permutations(points, 2)}


CANDIDATS_3 = [
    {"id": "X", "jours_min": 2, "jours_max": 4, "cout_jour": 100.0},
    {"id": "Y", "jours_min": 2, "jours_max": 3, "cout_jour": 100.0},
    {"id": "Z", "jours_min": 2, "jours_max": 3, "cout_jour": 100.0},
]
POINTS_3 = ["DEPART", "X", "Y", "Z", "ARRIVEE"]
TRAJETS_3 = _trajets_uniformes(POINTS_3, prix=200.0, duree_min=300)


def test_selects_max_candidates_within_tight_budget():
    """3 candidats coûtent exactement pile (budget=1400, jours=9 -> tous les 3
    tiennent tout juste à 10j/1400$ mais pas à 9j/1400$) : le solveur doit en
    retenir exactement 2, pas 3, pas 1."""
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=9)
    assert result is not None
    assert len(result) == 2
    assert all(r["jours"] == 2 for r in result)  # jours_min respecté (le minimum suffit ici)


def test_all_candidates_fit_when_budget_and_time_allow():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=10)
    assert result is not None
    assert len(result) == 3


def test_returns_empty_list_when_no_candidate_fits_but_direct_trip_does():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=250, jours_disponibles=1)
    assert result == []


def test_returns_none_when_even_direct_trip_is_infeasible():
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=50, jours_disponibles=0)
    assert result is None


def test_defaults_to_shortest_stay_when_unconstrained():
    """Rien ne pousse vers une durée précise dans [jours_min, jours_max] hormis
    l'objectif secondaire (minimiser le total de jours à nombre de lieux égal)
    -> sans lui, CP-SAT peut légitimement choisir n'importe quelle valeur de la
    fourchette et le résultat devient non déterministe d'une machine à l'autre
    (constaté en le vérifiant sur deux machines différentes avant ce plan)."""
    candidats = [{"id": "X", "jours_min": 1, "jours_max": 3, "cout_jour": 10.0}]
    points = ["DEPART", "X", "ARRIVEE"]
    trajets = _trajets_uniformes(points, prix=10.0, duree_min=60)
    result = solve_itinerary(candidats, trajets, budget_total=1000, jours_disponibles=30)
    assert result is not None
    assert result[0]["jours"] == 1  # jours_min : rien ne justifie de rester plus longtemps


def test_departure_and_arrival_can_differ():
    """DEPART != ARRIVEE (pas de retour au point de départ) — vérifie que le
    solveur ne force pas un aller-retour."""
    result = solve_itinerary(CANDIDATS_3, TRAJETS_3, budget_total=1400, jours_disponibles=10,
                              depart_id="DEPART", arrivee_id="ARRIVEE")
    assert result is not None
    ids_visites = {r["id"] for r in result}
    assert "DEPART" not in ids_visites and "ARRIVEE" not in ids_visites
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_solver.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.voyage.solver'`

- [ ] **Step 4: Write minimal implementation**

```python
# backend/app/services/voyage/solver.py
"""Solveur d'itinéraire — circuit optionnel (OR-Tools CP-SAT).

Modélise le choix des lieux à visiter + leur ordre comme un TSP à sélection
de nœuds (proche d'un « Orienteering Problem ») : chaque candidat a une
boucle sur lui-même (non retenu) ou fait partie du chemin
depart -> ... -> arrivee. Un arc virtuel arrivee -> depart (coût/durée nuls)
ferme le circuit pour satisfaire la contrainte `AddCircuit` de CP-SAT — ce
n'est pas un vrai trajet, juste un artifice de modélisation.

Objectif lexicographique : (1) maximiser le nombre de lieux retenus, sous
contrainte de jours disponibles et de budget total (transport + coût/jour ×
durée du séjour) ; (2) à nombre égal, minimiser le total de jours utilisés
(un lieu retenu reçoit sa durée minimale, sauf si en rester justifié par
ailleurs — ce qui ne se produit jamais dans ce modèle).
"""
from __future__ import annotations

import math
from typing import Optional

from ortools.sat.python import cp_model


def solve_itinerary(
    candidats: list[dict],
    trajets: dict[tuple[str, str], dict],
    budget_total: float,
    jours_disponibles: int,
    depart_id: str = "DEPART",
    arrivee_id: str = "ARRIVEE",
) -> Optional[list[dict]]:
    """Choisit un sous-ensemble ordonné de `candidats` maximisant leur nombre.

    `candidats` : [{"id": str, "jours_min": int, "jours_max": int, "cout_jour": float}, ...]
    `trajets` : prix/durée pour CHAQUE paire ordonnée (i, j) parmi
    {depart_id} ∪ {candidat["id"] pour chaque candidat} ∪ {arrivee_id}, i != j.

    Retourne les lieux retenus dans l'ordre du parcours, avec la durée de
    séjour assignée : [{"id": str, "jours": int}, ...]. Liste vide si aucun
    candidat ne rentre mais que depart->arrivee direct est faisable. `None`
    si même le trajet direct dépasse le budget ou les jours disponibles.
    """
    ids = [depart_id] + [c["id"] for c in candidats] + [arrivee_id]
    n = len(ids)
    idx = {v: i for i, v in enumerate(ids)}
    depart_idx, arrivee_idx = 0, n - 1

    model = cp_model.CpModel()

    duree_days: dict[int, cp_model.IntVar] = {}
    skip_lit: dict[int, cp_model.IntVar] = {}
    for c in candidats:
        i = idx[c["id"]]
        duree_days[i] = model.NewIntVar(0, c["jours_max"], f"duree_{i}")
        skip_lit[i] = model.NewBoolVar(f"skip_{i}")
        # 0 jour si écarté (sinon jours_min grève le budget temps même non visité)
        model.Add(duree_days[i] == 0).OnlyEnforceIf(skip_lit[i])
        model.Add(duree_days[i] >= c["jours_min"]).OnlyEnforceIf(skip_lit[i].Not())

    arcs: list[tuple[int, int, cp_model.IntVar]] = []
    arc_lit: dict[tuple[int, int], cp_model.IntVar] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                if i in skip_lit:
                    arcs.append((i, i, skip_lit[i]))
                continue
            if j == depart_idx and i != arrivee_idx:
                continue  # seule arrivee peut revenir vers depart (ferme le circuit)
            if i == arrivee_idx and j != depart_idx:
                continue  # arrivee ne repart que vers depart
            lit = model.NewBoolVar(f"arc_{i}_{j}")
            arc_lit[(i, j)] = lit
            arcs.append((i, j, lit))

    model.AddCircuit(arcs)
    model.Add(arc_lit[(arrivee_idx, depart_idx)] == 1)  # arc virtuel, toujours emprunté

    total_days = list(duree_days.values())
    total_cost = []
    for (i, j), lit in arc_lit.items():
        if (i, j) == (arrivee_idx, depart_idx):
            continue  # arc virtuel : pas un vrai trajet, ne consomme rien
        t = trajets[(ids[i], ids[j])]
        travel_days = math.ceil(t["duree_min"] / 1440)
        if travel_days:
            total_days.append(cp_model.LinearExpr.Term(lit, travel_days))
        total_cost.append(cp_model.LinearExpr.Term(lit, round(t["prix"])))
    for c in candidats:
        i = idx[c["id"]]
        total_cost.append(cp_model.LinearExpr.Term(duree_days[i], round(c["cout_jour"])))

    model.Add(cp_model.LinearExpr.Sum(total_days) <= jours_disponibles)
    model.Add(cp_model.LinearExpr.Sum(total_cost) <= round(budget_total))

    # Objectif lexicographique : (1) maximiser le nombre de lieux visités,
    # (2) à égalité, minimiser le total de jours utilisés. Sans (2), la durée
    # d'un candidat retenu dans [jours_min, jours_max] n'est contrainte par
    # rien d'autre et CP-SAT peut renvoyer n'importe quelle valeur de la
    # fourchette — constaté non déterministe d'une machine à l'autre avec
    # l'objectif (1) seul. BIG doit dominer strictement le terme secondaire,
    # qui est borné par jours_disponibles via la contrainte ci-dessus.
    BIG = jours_disponibles + 1
    n_visites = sum(1 - skip_lit[idx[c["id"]]] for c in candidats)
    model.Maximize(n_visites * BIG - cp_model.LinearExpr.Sum(total_days))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # reconstruit l'ordre du parcours en suivant les arcs retenus depuis depart
    ordre: list[str] = []
    current = depart_idx
    while current != arrivee_idx:
        nxt = next(j for (i, j), lit in arc_lit.items() if i == current and solver.Value(lit) == 1)
        if nxt != arrivee_idx:
            ordre.append(ids[nxt])
        current = nxt

    return [{"id": nom_id, "jours": solver.Value(duree_days[idx[nom_id]])} for nom_id in ordre]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_solver.py -v`
Expected: 6 passed (le solveur CP-SAT est déterministe sur ces cas mais peut prendre quelques secondes — normal, `max_time_in_seconds=10` est un plafond, pas une durée systématique)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock app/services/voyage/solver.py tests/test_voyage/test_solver.py
git commit -m "feat(voyage): solveur d'itinéraire OR-Tools (circuit optionnel)"
```

---

### Task 6: API — sync, candidats, planifier, confirmer

**Files:**
- Create: `backend/app/api/voyage/__init__.py`, `backend/app/api/voyage/schemas.py`, `backend/app/api/voyage/routes.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/test_voyage/test_api.py`

**Interfaces:**
- Consumes: `sync_voyage`, `marquer_visites` (Task 2/3), `fetch_offer` (Task 4), `solve_itinerary` (Task 5), `LieuVoyage` (Task 1)
- Produces : routes `POST /voyage/sync`, `GET /voyage/lieux`, `POST /voyage/planifier`, `POST /voyage/confirmer`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_voyage/test_api.py
"""API Voyage : sync, lieux, planifier, confirmer."""
from __future__ import annotations

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.api.voyage import routes as voyage_routes
from app.core.config import settings
from app.core.db import get_session
from app.main import create_app
from app.models.voyage import LieuVoyage


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_post_sync(client, monkeypatch, tmp_path):
    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre",
               "Aéroport (IATA)", "Jours min", "Jours max", "Coût/jour estimé"])
    ws.append(["Table Mountain", "Le Cap", "Afrique du Sud", False, 1, "CPT", 2, 4, 80])
    wb.save(p)
    monkeypatch.setattr(voyage_routes, "_voyage_xlsx_path", lambda: p)

    r = client.post("/voyage/sync")
    assert r.status_code == 200
    assert r.json() == {"lieux": 1, "incomplets": []}


def test_post_sync_missing_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(voyage_routes, "_voyage_xlsx_path", lambda: tmp_path / "absent.xlsx")
    r = client.post("/voyage/sync")
    assert r.status_code == 404


def test_get_lieux(client, session):
    session.add(LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=4,
                            cout_jour_estime=80.0))
    session.add(LieuVoyage(nom="K-2"))  # incomplet
    session.commit()

    r = client.get("/voyage/lieux")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    par_nom = {d["nom"]: d for d in data}
    assert par_nom["Table Mountain"]["complet"] is True
    assert par_nom["K-2"]["complet"] is False


def test_planifier_rejects_more_than_25_candidats(client, session):
    ids = []
    for i in range(26):
        lv = LieuVoyage(nom=f"L{i}", aeroport_iata="XXX", jours_min=1, jours_max=1, cout_jour_estime=10.0)
        session.add(lv)
        session.commit()
        session.refresh(lv)
        ids.append(lv.id)

    r = client.post("/voyage/planifier", json={
        "candidats": ids, "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 400


def test_planifier_rejects_incomplete_lieu(client, session):
    lv = LieuVoyage(nom="Incomplet")  # pas d'aéroport/jours
    session.add(lv)
    session.commit()
    session.refresh(lv)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 400
    assert "Incomplet" in r.json()["detail"]


def test_planifier_happy_path(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "USD", "duree_min": 600},
    )

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["etapes"]) == 1
    assert data["etapes"][0]["lieu_id"] == lv.id
    assert data["etapes"][0]["jours"] == 2
    assert data["cout_transport"] == 1000.0  # aller + retour à 500 chacun
    assert data["cout_sejour"] == 160.0  # 2 jours x 80
    assert data["cout_total"] == 1160.0


def test_planifier_returns_409_when_infeasible(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "USD", "duree_min": 600},
    )

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-01", "budget_total": 10,
    })
    assert r.status_code == 409


def test_planifier_returns_502_when_duffel_unavailable(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(voyage_routes, "fetch_offer", lambda *a, **k: None)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 502


def test_confirmer_marks_visite(client, session, monkeypatch, tmp_path):
    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre"])
    ws.append(["Table Mountain", "Le Cap", "Afrique du Sud", False, None])
    wb.save(p)
    monkeypatch.setattr(voyage_routes, "_voyage_xlsx_path", lambda: p)

    lv = LieuVoyage(nom="Table Mountain", visite=False)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    r = client.post("/voyage/confirmer", json={"lieu_ids": [lv.id]})
    assert r.status_code == 200
    assert session.get(LieuVoyage, lv.id).visite is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_api.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.api.voyage'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/api/voyage/schemas.py
"""Schémas Pydantic — module Voyage."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class LieuVoyageOut(BaseModel):
    id: int
    nom: str
    ville: str | None
    pays: str | None
    visite: bool
    aeroport_iata: str | None
    jours_min: int | None
    jours_max: int | None
    cout_jour_estime: float | None
    complet: bool


class SyncVoyageOut(BaseModel):
    lieux: int
    incomplets: list[str]


class PlanifierRequest(BaseModel):
    candidats: list[int]
    depart_iata: str
    arrivee_iata: str
    date_debut: dt.date
    date_fin: dt.date
    budget_total: float


class EtapeItineraire(BaseModel):
    lieu_id: int
    nom: str
    jours: int
    date_arrivee: dt.date
    date_depart: dt.date


class ItineraireOut(BaseModel):
    etapes: list[EtapeItineraire]
    cout_total: float
    cout_transport: float
    cout_sejour: float


class ConfirmerRequest(BaseModel):
    lieu_ids: list[int]
```

```python
# backend/app/api/voyage/routes.py
"""Routes Voyage : sync Excel, candidats, planification, confirmation.

Master = data/imports/Voyage.xlsx. POST /sync l'importe dans lieu_voyage ;
POST /planifier calcule l'itinéraire optimal (Duffel + OR-Tools) ;
POST /confirmer écrit Visité=True dans l'Excel + DB.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.voyage.schemas import (
    ConfirmerRequest, EtapeItineraire, ItineraireOut, LieuVoyageOut,
    PlanifierRequest, SyncVoyageOut,
)
from app.core.config import settings
from app.core.db import get_session
from app.models.voyage import LieuVoyage
from app.services.voyage.duffel_client import fetch_offer
from app.services.voyage.import_excel import marquer_visites, sync_voyage
from app.services.voyage.solver import solve_itinerary

router = APIRouter(tags=["voyage"])

MAX_CANDIDATS = 25


def _voyage_xlsx_path() -> Path:
    return settings.imports_dir / "Voyage.xlsx"


def _est_complet(lv: LieuVoyage) -> bool:
    return bool(lv.aeroport_iata) and lv.jours_min is not None and lv.jours_max is not None


@router.get("/ping")
def ping() -> dict:
    return {"module": "voyage", "ready": True}


@router.post("/sync", response_model=SyncVoyageOut)
def post_sync(session: Session = Depends(get_session)) -> SyncVoyageOut:
    path = _voyage_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    result = sync_voyage(session, path)
    return SyncVoyageOut(**result)


@router.get("/lieux", response_model=list[LieuVoyageOut])
def get_lieux(session: Session = Depends(get_session)) -> list[LieuVoyageOut]:
    lieux = session.exec(select(LieuVoyage).order_by(LieuVoyage.nom)).all()
    return [
        LieuVoyageOut(
            id=lv.id, nom=lv.nom, ville=lv.ville, pays=lv.pays, visite=lv.visite,
            aeroport_iata=lv.aeroport_iata, jours_min=lv.jours_min, jours_max=lv.jours_max,
            cout_jour_estime=lv.cout_jour_estime, complet=_est_complet(lv),
        )
        for lv in lieux
    ]


@router.post("/planifier", response_model=ItineraireOut)
def post_planifier(req: PlanifierRequest, session: Session = Depends(get_session)) -> ItineraireOut:
    if len(req.candidats) > MAX_CANDIDATS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"{MAX_CANDIDATS} lieux candidats maximum par requête")

    lieux = session.exec(select(LieuVoyage).where(LieuVoyage.id.in_(req.candidats))).all()
    if len(lieux) != len(set(req.candidats)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Un ou plusieurs lieux candidats introuvables")

    incomplets = [lv.nom for lv in lieux if not _est_complet(lv)]
    if incomplets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"Lieux incomplets (aéroport/jours manquants) : {', '.join(incomplets)}")

    date_ref = req.date_debut.isoformat()
    by_id = {str(lv.id): lv for lv in lieux}
    points = (
        [("DEPART", req.depart_iata)]
        + [(str(lv.id), lv.aeroport_iata) for lv in lieux]
        + [("ARRIVEE", req.arrivee_iata)]
    )

    trajets: dict[tuple[str, str], dict] = {}
    for a_id, a_iata in points:
        for b_id, b_iata in points:
            if a_id == b_id:
                continue
            offer = fetch_offer(session, a_iata, b_iata, date_ref)
            if offer is None:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    f"Impossible d'obtenir un prix de vol {a_iata} -> {b_iata}",
                )
            trajets[(a_id, b_id)] = {"prix": offer["prix"], "duree_min": offer["duree_min"]}

    candidats_solver = [
        {"id": str(lv.id), "jours_min": lv.jours_min, "jours_max": lv.jours_max,
         "cout_jour": lv.cout_jour_estime or 0.0}
        for lv in lieux
    ]
    jours_disponibles = (req.date_fin - req.date_debut).days
    resultat = solve_itinerary(candidats_solver, trajets, req.budget_total, jours_disponibles)
    if resultat is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aucun itinéraire ne respecte le budget/temps disponibles, même le trajet direct",
        )

    etapes: list[EtapeItineraire] = []
    cout_sejour = 0.0
    current_date = req.date_debut
    trajet_ids = ["DEPART"] + [e["id"] for e in resultat] + ["ARRIVEE"]
    for i, etape in enumerate(resultat):
        lieu = by_id[etape["id"]]
        prev_id = trajet_ids[i]
        travel_days = math.ceil(trajets[(prev_id, etape["id"])]["duree_min"] / 1440)
        current_date += dt.timedelta(days=travel_days)
        date_arrivee = current_date
        current_date += dt.timedelta(days=etape["jours"])
        date_depart = current_date
        etapes.append(EtapeItineraire(
            lieu_id=lieu.id, nom=lieu.nom, jours=etape["jours"],
            date_arrivee=date_arrivee, date_depart=date_depart,
        ))
        cout_sejour += (lieu.cout_jour_estime or 0.0) * etape["jours"]

    cout_transport = sum(trajets[(a, b)]["prix"] for a, b in zip(trajet_ids, trajet_ids[1:]))

    return ItineraireOut(
        etapes=etapes, cout_total=cout_transport + cout_sejour,
        cout_transport=cout_transport, cout_sejour=cout_sejour,
    )


@router.post("/confirmer")
def post_confirmer(req: ConfirmerRequest, session: Session = Depends(get_session)) -> dict:
    lieux = session.exec(select(LieuVoyage).where(LieuVoyage.id.in_(req.lieu_ids))).all()
    noms = [lv.nom for lv in lieux]
    path = _voyage_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    marquer_visites(session, path, noms)
    return {"visites": len(noms)}
```

```python
# backend/app/api/voyage/__init__.py
"""Routes Voyage — package (cf. pattern app/api/garderobe)."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["voyage"])
router.include_router(routes.router)
```

Modifier `backend/app/api/__init__.py` : ajouter l'import (ordre alphabétique, après `travail_router`) et l'`include_router` :

```python
from app.api.voyage import router as voyage_router
```

```python
api_router.include_router(voyage_router, prefix="/voyage")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_api.py -v`
Expected: 9 passed

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: tous les tests passent (aucune régression sur les autres modules)

- [ ] **Step 6: Commit**

```bash
git add app/api/voyage/ app/api/__init__.py tests/test_voyage/test_api.py
git commit -m "feat(voyage): API sync/lieux/planifier/confirmer"
```

---

### Task 7: Frontend — types + client API + queries

**Files:**
- Create: `frontend/lib/voyage.ts`, `frontend/lib/queries/voyage.ts`
- Test: `frontend/__tests__/queries/voyage.test.tsx`

**Interfaces:**
- Consumes: `api` (`frontend/lib/api.ts`)
- Produces: `voyageApi.{listLieux, sync, planifier, confirmer}`, `useLieuxVoyage`, `useSyncVoyage`, `usePlanifier`, `useConfirmerVoyage`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/__tests__/queries/voyage.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { voyageApi } from "@/lib/voyage";
import { useLieuxVoyage } from "@/lib/queries/voyage";

vi.mock("@/lib/voyage", () => ({
  voyageApi: {
    listLieux: vi.fn(),
    sync: vi.fn(),
    planifier: vi.fn(),
    confirmer: vi.fn(),
  },
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useLieuxVoyage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("charge la liste des lieux", async () => {
    vi.mocked(voyageApi.listLieux).mockResolvedValue([
      { id: 1, nom: "Table Mountain", ville: "Le Cap", pays: "Afrique du Sud", visite: false,
        aeroport_iata: "CPT", jours_min: 2, jours_max: 4, cout_jour_estime: 80, complet: true },
    ]);

    const { result } = renderHook(() => useLieuxVoyage(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].nom).toBe("Table Mountain");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `frontend/`) : `npm test -- voyage`
Expected: FAIL — `Cannot find module '@/lib/voyage'`

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/lib/voyage.ts
/**
 * Client API + types pour le module Voyage (planificateur d'itinéraire).
 * Endpoints sous /voyage/* (cf. backend/app/api/voyage/routes.py).
 */
import { api } from "./api";

export type LieuVoyage = {
  id: number;
  nom: string;
  ville: string | null;
  pays: string | null;
  visite: boolean;
  aeroport_iata: string | null;
  jours_min: number | null;
  jours_max: number | null;
  cout_jour_estime: number | null;
  complet: boolean;
};

export type SyncVoyageResult = { lieux: number; incomplets: string[] };

export type PlanifierRequest = {
  candidats: number[];
  depart_iata: string;
  arrivee_iata: string;
  date_debut: string; // "YYYY-MM-DD"
  date_fin: string;
  budget_total: number;
};

export type EtapeItineraire = {
  lieu_id: number;
  nom: string;
  jours: number;
  date_arrivee: string;
  date_depart: string;
};

export type Itineraire = {
  etapes: EtapeItineraire[];
  cout_total: number;
  cout_transport: number;
  cout_sejour: number;
};

export const voyageApi = {
  listLieux: () => api<LieuVoyage[]>(`/voyage/lieux`),

  sync: () => api<SyncVoyageResult>(`/voyage/sync`, { method: "POST" }),

  planifier: (req: PlanifierRequest) =>
    api<Itineraire>(`/voyage/planifier`, { method: "POST", body: JSON.stringify(req) }),

  confirmer: (lieuIds: number[]) =>
    api<{ visites: number }>(`/voyage/confirmer`, {
      method: "POST",
      body: JSON.stringify({ lieu_ids: lieuIds }),
    }),
};
```

```ts
// frontend/lib/queries/voyage.ts
"use client";

/** Couche TanStack Query du module Voyage — modèle : lib/queries/garderobe.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { voyageApi, type PlanifierRequest } from "@/lib/voyage";

export const voyageKeys = {
  all: ["voyage"] as const,
  lieux: () => [...voyageKeys.all, "lieux"] as const,
};

export function useLieuxVoyage() {
  return useQuery({ queryKey: voyageKeys.lieux(), queryFn: voyageApi.listLieux });
}

export function useSyncVoyage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: voyageApi.sync,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: voyageKeys.all }),
  });
}

export function usePlanifier() {
  return useMutation({ mutationFn: (req: PlanifierRequest) => voyageApi.planifier(req) });
}

export function useConfirmerVoyage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lieuIds: number[]) => voyageApi.confirmer(lieuIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: voyageKeys.all }),
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- voyage`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add lib/voyage.ts lib/queries/voyage.ts __tests__/queries/voyage.test.tsx
git commit -m "feat(voyage): client API + queries TanStack (frontend)"
```

---

### Task 8: Frontend — page et composants (liste, formulaire, résultat)

**Files:**
- Create: `frontend/src/app/voyage/page.tsx`, `frontend/components/voyage/Voyage.tsx`, `frontend/components/voyage/LieuxTab.tsx`, `frontend/components/voyage/PlanifierTab.tsx`
- Modify: `frontend/lib/modules.ts`

**Interfaces:**
- Consumes: `useLieuxVoyage`, `useSyncVoyage`, `usePlanifier`, `useConfirmerVoyage` (Task 7)

- [ ] **Step 1: Enregistrer le module dans la navigation**

Dans `frontend/lib/modules.ts`, ajouter l'import d'icône `Plane` (import lucide-react existant, ajouter `Plane` à la liste d'imports en haut du fichier) et une entrée dans `MODULES`, dans le groupe `"Style & Horizons"` juste après `garderobe` :

```ts
  {
    slug: "voyage",
    label: "Voyage",
    description: "Wishlist de lieux à visiter, planification d'itinéraire.",
    icon: Plane,
    group: "Style & Horizons",
    ready: true,
  },
```

- [ ] **Step 2: Écrire les composants**

```tsx
// frontend/components/voyage/LieuxTab.tsx
"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { useLieuxVoyage, useSyncVoyage } from "@/lib/queries/voyage";

export function LieuxTab({ selected, onToggle }: {
  selected: Set<number>;
  onToggle: (id: number) => void;
}) {
  const lieuxQ = useLieuxVoyage();
  const syncMut = useSyncVoyage();

  if (lieuxQ.isLoading) {
    return <div className="p-2 text-[var(--muted-foreground)]">Chargement…</div>;
  }
  if (lieuxQ.isError || !lieuxQ.data) {
    return <div className="p-2 text-[var(--destructive)]">⚠ Impossible de charger la liste.</div>;
  }

  const aVisiter = lieuxQ.data.filter((l) => !l.visite);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-[var(--muted-foreground)]">
          {aVisiter.length} lieux à visiter · {selected.size} sélectionné(s) pour la planification
        </div>
        <button
          onClick={() => syncMut.mutate()}
          disabled={syncMut.isPending}
          className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${syncMut.isPending ? "animate-spin" : ""}`} />
          Re-synchroniser l'Excel
        </button>
      </div>
      {syncMut.data && syncMut.data.incomplets.length > 0 && (
        <div className="rounded-lg border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
          ⚠ {syncMut.data.incomplets.length} lieu(x) incomplet(s) (aéroport ou jours manquants) :{" "}
          {syncMut.data.incomplets.join(", ")}
        </div>
      )}
      <div className="space-y-1">
        {aVisiter.map((l) => (
          <label
            key={l.id}
            className={`flex items-center gap-3 rounded-lg border border-[var(--border)] p-2 text-sm ${
              l.complet ? "cursor-pointer hover:bg-[var(--muted)]" : "opacity-50"
            }`}
          >
            <input
              type="checkbox"
              disabled={!l.complet}
              checked={selected.has(l.id)}
              onChange={() => onToggle(l.id)}
            />
            <span className="flex-1">{l.nom}</span>
            <span className="text-[var(--muted-foreground)]">{l.ville ?? l.pays ?? ""}</span>
            {!l.complet && <span className="text-xs text-[var(--destructive)]">incomplet</span>}
          </label>
        ))}
      </div>
    </div>
  );
}
```

```tsx
// frontend/components/voyage/PlanifierTab.tsx
"use client";

import { useState } from "react";
import { usePlanifier, useConfirmerVoyage } from "@/lib/queries/voyage";
import type { Itineraire } from "@/lib/voyage";

export function PlanifierTab({ candidats }: { candidats: number[] }) {
  const [departIata, setDepartIata] = useState("YUL");
  const [arriveeIata, setArriveeIata] = useState("YUL");
  const [dateDebut, setDateDebut] = useState("");
  const [dateFin, setDateFin] = useState("");
  const [budget, setBudget] = useState(3000);
  const [resultat, setResultat] = useState<Itineraire | null>(null);

  const planifierMut = usePlanifier();
  const confirmerMut = useConfirmerVoyage();

  const soumettre = () => {
    if (candidats.length === 0 || !dateDebut || !dateFin) return;
    planifierMut.mutate(
      {
        candidats, depart_iata: departIata, arrivee_iata: arriveeIata,
        date_debut: dateDebut, date_fin: dateFin, budget_total: budget,
      },
      { onSuccess: setResultat },
    );
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <label className="text-sm">
          Départ (IATA)
          <input value={departIata} onChange={(e) => setDepartIata(e.target.value.toUpperCase())}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Arrivée (IATA)
          <input value={arriveeIata} onChange={(e) => setArriveeIata(e.target.value.toUpperCase())}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Budget total (€)
          <input type="number" value={budget} onChange={(e) => setBudget(Number(e.target.value))}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Date de début
          <input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Date de fin
          <input type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
      </div>
      <button
        onClick={soumettre}
        disabled={planifierMut.isPending || candidats.length === 0}
        className="rounded bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
      >
        {planifierMut.isPending ? "Calcul en cours…" : "Planifier"}
      </button>
      {planifierMut.isError && (
        <div className="text-sm text-[var(--destructive)]">
          {(planifierMut.error as Error)?.message ?? "Erreur de planification"}
        </div>
      )}
      {resultat && (
        <div className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="text-sm font-semibold">
            {resultat.etapes.length} lieu(x) retenu(s) · {resultat.cout_total.toFixed(0)} €
            (transport {resultat.cout_transport.toFixed(0)} € + séjour {resultat.cout_sejour.toFixed(0)} €)
          </div>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {resultat.etapes.map((e) => (
              <li key={e.lieu_id}>
                {e.nom} — {e.jours} jour(s), du {e.date_arrivee} au {e.date_depart}
              </li>
            ))}
          </ol>
          <button
            onClick={() => confirmerMut.mutate(resultat.etapes.map((e) => e.lieu_id))}
            disabled={confirmerMut.isPending}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
          >
            {confirmerMut.isPending ? "Confirmation…" : "Confirmer ce voyage"}
          </button>
        </div>
      )}
    </div>
  );
}
```

```tsx
// frontend/components/voyage/Voyage.tsx
"use client";

import { useState } from "react";
import { LieuxTab } from "./LieuxTab";
import { PlanifierTab } from "./PlanifierTab";

export function Voyage() {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 25) next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Voyage</h1>
      <LieuxTab selected={selected} onToggle={toggle} />
      <PlanifierTab candidats={[...selected]} />
    </div>
  );
}
```

```tsx
// frontend/src/app/voyage/page.tsx
import { Voyage } from "@/components/voyage/Voyage";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function VoyagePage() {
  return (
    <ErrorBoundary label="Voyage">
      <Voyage />
    </ErrorBoundary>
  );
}
```

- [ ] **Step 3: Vérifier le typecheck et le build**

Run (depuis `frontend/`) : `npx tsc --noEmit`
Expected : aucune erreur de type

Run : `npm run build`
Expected : build réussi

- [ ] **Step 4: Commit**

```bash
git add src/app/voyage/ components/voyage/ lib/modules.ts
git commit -m "feat(voyage): page et composants (liste, formulaire, résultat)"
```

---

## Décomposition (rappel)

1. Modèles (`LieuVoyage`, `DuffelPriceCache`) + migration
2. Import Excel (parse + sync + détection incomplets)
3. Écriture Excel (confirmer → `Visité=True`, backup)
4. Config + client Duffel (prix/durée de vol, cache)
5. Solveur OR-Tools (circuit optionnel)
6. API (sync, lieux, planifier, confirmer)
7. Frontend — types + queries
8. Frontend — page et composants

Chaque tâche produit un livrable testable indépendamment ; les tâches 1-6 (backend) sont fonctionnelles et testables via l'API/Swagger avant même que le frontend (7-8) n'existe.
