# Carte de l'itinéraire conseillé — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher le résultat de `POST /voyage/planifier` (l'itinéraire recommandé) sur une carte au-dessus de la liste ordonnée déjà existante dans l'onglet Planifier du module Voyage.

**Architecture:** Table statique locale IATA→coordonnées (CSV, dérivé d'OurAirports, aucun appel réseau au runtime), lookup fait côté backend qui enrichit la réponse `/voyage/planifier` avec `lat`/`lon` par point. Le frontend affiche ces coordonnées via un composant Leaflet dédié, chargé dynamiquement côté client uniquement (`next/dynamic`, `ssr: false`).

**Tech Stack:** FastAPI/Pydantic (backend), Next.js/React (frontend), `react-leaflet` + `leaflet` (nouvelle dépendance, tuiles OpenStreetMap, pas de clé API).

## Global Constraints

- Spec source : `docs/superpowers/specs/2026-07-02-voyage-carte-itineraire-design.md`
- Aucune requête réseau au runtime pour résoudre les coordonnées — lookup local uniquement, contre une table statique committée.
- Un code IATA absent de la table donne `lat`/`lon` à `None`, jamais d'exception (backend) ni de crash (frontend).
- La carte ne s'affiche que si TOUS les points affichés (départ, chaque étape retenue, arrivée) ont des coordonnées connues ; sinon repli textuel complet (« Carte indisponible pour cet itinéraire »), jamais de carte partielle avec des points manquants.
- La carte s'affiche au-dessus de la liste ordonnée `<ol>` déjà existante dans `PlanifierTab.tsx` ; la liste texte reste toujours affichée, indépendamment de la disponibilité de la carte.
- Ordre des points sur la carte : départ → étapes (ordre retenu par le solveur, déjà celui de `resultat.etapes`) → arrivée.
- Pas de clé API requise (tuiles OpenStreetMap, usage équitable).

---

### Task 1: Table locale IATA → coordonnées

**Files:**
- Create: `backend/app/services/voyage/airports.py`
- Create: `backend/app/services/voyage/data/airports_iata.csv` (généré par le script ci-dessous, pas écrit à la main)
- Create: `backend/scripts/build_airports_iata.py`
- Test: `backend/tests/test_voyage/test_airports.py`

**Interfaces:**
- Produces: `lookup_coords(iata: str, *, path: Path | None = None) -> tuple[float, float] | None` — `path` injectable pour les tests, défaut = `backend/app/services/voyage/data/airports_iata.csv`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_voyage/test_airports.py
"""Lookup IATA -> coordonnées (table statique locale, aucun appel réseau)."""
from __future__ import annotations

from app.services.voyage.airports import lookup_coords


def _make_csv(path):
    path.write_text(
        "iata,name,lat,lon\n"
        "YUL,Montreal-Trudeau Intl,45.4706,-73.7408\n"
        "CDG,Charles de Gaulle,49.0097,2.5479\n",
        encoding="utf-8",
    )


def test_lookup_coords_known_code(tmp_path):
    p = tmp_path / "airports.csv"
    _make_csv(p)
    assert lookup_coords("YUL", path=p) == (45.4706, -73.7408)


def test_lookup_coords_case_insensitive(tmp_path):
    p = tmp_path / "airports.csv"
    _make_csv(p)
    assert lookup_coords("cdg", path=p) == (49.0097, 2.5479)


def test_lookup_coords_unknown_code_returns_none(tmp_path):
    p = tmp_path / "airports.csv"
    _make_csv(p)
    assert lookup_coords("ZZZ", path=p) is None


def test_lookup_coords_caches_per_path(tmp_path):
    """Deux lookups sur le même path ne relisent pas le fichier deux fois."""
    p = tmp_path / "airports.csv"
    _make_csv(p)
    lookup_coords("YUL", path=p)
    p.write_text("iata,name,lat,lon\n", encoding="utf-8")  # vide le fichier
    # toujours servi depuis le cache, pas relu depuis le fichier maintenant vide
    assert lookup_coords("YUL", path=p) == (45.4706, -73.7408)
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`) : `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_airports.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.voyage.airports'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/voyage/airports.py
"""Lookup IATA -> (lat, lon) depuis une table statique locale.

Source : `data/airports_iata.csv` (colonnes iata,name,lat,lon), dérivé du
dataset public domain OurAirports (CC0), filtré aux entrées ayant un code
IATA renseigné. Généré une fois via `scripts/build_airports_iata.py`
(backend/) — pas régénéré automatiquement au runtime, aucun appel réseau
lors du lookup.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent / "data" / "airports_iata.csv"
_cache: dict[Path, dict[str, tuple[float, float]]] = {}


def _load(path: Path) -> dict[str, tuple[float, float]]:
    if path not in _cache:
        table: dict[str, tuple[float, float]] = {}
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                iata = (row.get("iata") or "").strip().upper()
                if iata:
                    table[iata] = (float(row["lat"]), float(row["lon"]))
        _cache[path] = table
    return _cache[path]


def lookup_coords(iata: str, *, path: Optional[Path] = None) -> Optional[tuple[float, float]]:
    """Renvoie `(lat, lon)` pour un code IATA, ou `None` si absent de la table."""
    table = _load(path or _DATA_PATH)
    return table.get(iata.strip().upper())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_airports.py -v`
Expected: 4 passed

- [ ] **Step 5: Write the one-time data-generation script**

```python
# backend/scripts/build_airports_iata.py
"""Génère `app/services/voyage/data/airports_iata.csv` depuis OurAirports
(dataset public domain, CC0) — filtré aux aéroports ayant un code IATA.

Script one-shot, pas couvert par les tests automatisés (appel réseau) : à
relancer manuellement si la table doit être rafraîchie.

Usage (depuis `backend/`) : `uv run python -m scripts.build_airports_iata`
"""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import httpx

_SOURCE_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
_OUT_PATH = Path(__file__).parent.parent / "app" / "services" / "voyage" / "data" / "airports_iata.csv"


def main() -> None:
    resp = httpx.get(_SOURCE_URL, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    reader = csv.DictReader(StringIO(resp.text))

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with _OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iata", "name", "lat", "lon"])
        for row in reader:
            iata = (row.get("iata_code") or "").strip().upper()
            lat, lon = row.get("latitude_deg"), row.get("longitude_deg")
            if not iata or not lat or not lon:
                continue
            writer.writerow([iata, row.get("name", ""), lat, lon])
            n += 1

    print(f"écrit {n} aéroports -> {_OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the script once to generate the real data file**

Run (depuis `backend/`) : `uv run python -m scripts.build_airports_iata`
Expected : un message `écrit N aéroports -> .../airports_iata.csv` avec N de l'ordre de plusieurs milliers (typiquement 8000-11000). Vérifier que le fichier existe et qu'il contient au moins les lignes `YUL,...` et `CDG,...` (ou équivalent) :

```bash
grep -c "^" app/services/voyage/data/airports_iata.csv
grep "^YUL," app/services/voyage/data/airports_iata.csv
```

Expected : un nombre de lignes cohérent avec le message affiché (N+1 pour l'en-tête), et une ligne `YUL,...` présente.

Si la requête réseau échoue (pas de connexion) : escalader plutôt que d'inventer des données — ce n'est pas une décision qu'un exécutant doit prendre seul.

- [ ] **Step 7: Commit**

```bash
git add app/services/voyage/airports.py app/services/voyage/data/airports_iata.csv scripts/build_airports_iata.py tests/test_voyage/test_airports.py
git commit -m "feat(voyage): table locale IATA -> coordonnées (carte itinéraire)"
```

---

### Task 2: Backend — enrichissement de la réponse `/voyage/planifier`

**Files:**
- Modify: `backend/app/api/voyage/schemas.py`
- Modify: `backend/app/api/voyage/routes.py`
- Test: `backend/tests/test_voyage/test_api.py`

**Interfaces:**
- Consumes: `lookup_coords(iata: str, *, path: Path | None = None) -> tuple[float, float] | None` (Task 1)
- Produces: `PointItineraire{iata: str, lat: float | None, lon: float | None}` ; `EtapeItineraire` gagne `lat`/`lon` ; `ItineraireOut` gagne `depart`/`arrivee: PointItineraire`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_voyage/test_api.py`, juste après `test_planifier_happy_path` :

```python
def test_planifier_includes_coordinates(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "EUR", "duree_min": 600},
    )
    monkeypatch.setattr(
        voyage_routes, "lookup_coords",
        lambda iata, **kwargs: {"YUL": (45.4706, -73.7408), "CPT": (-33.9648, 18.6017)}.get(iata),
    )

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["depart"] == {"iata": "YUL", "lat": 45.4706, "lon": -73.7408}
    assert data["arrivee"] == {"iata": "YUL", "lat": 45.4706, "lon": -73.7408}
    assert data["etapes"][0]["lat"] == -33.9648
    assert data["etapes"][0]["lon"] == 18.6017


def test_planifier_null_coordinates_when_iata_unknown(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "EUR", "duree_min": 600},
    )
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: None)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["depart"]["lat"] is None and data["depart"]["lon"] is None
    assert data["etapes"][0]["lat"] is None and data["etapes"][0]["lon"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`) : `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_api.py -v -k coordinates`
Expected: FAIL — `AttributeError: <module 'app.api.voyage.routes'> does not have the attribute 'lookup_coords'` (le monkeypatch échoue tant que la route ne l'importe pas), ou `KeyError`/`AssertionError` sur `data["depart"]` (le champ n'existe pas encore dans la réponse).

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/api/voyage/schemas.py`, insérer une nouvelle classe juste avant `class EtapeItineraire(BaseModel):` :

```python
class PointItineraire(BaseModel):
    iata: str
    lat: float | None
    lon: float | None
```

Puis modifier `EtapeItineraire` pour ajouter les deux champs :

```python
class EtapeItineraire(BaseModel):
    lieu_id: int
    nom: str
    jours: int
    date_arrivee: dt.date
    date_depart: dt.date
    lat: float | None
    lon: float | None
```

Et `ItineraireOut` pour ajouter `depart`/`arrivee` :

```python
class ItineraireOut(BaseModel):
    etapes: list[EtapeItineraire]
    cout_total: float
    cout_transport: float
    cout_sejour: float
    depart: PointItineraire
    arrivee: PointItineraire
```

Dans `backend/app/api/voyage/routes.py`, modifier l'import des schémas (ligne 16-19) pour ajouter `PointItineraire` :

```python
from app.api.voyage.schemas import (
    ConfirmerRequest, EtapeItineraire, ItineraireOut, LieuVoyageOut,
    PlanifierRequest, PointItineraire, SyncVoyageOut,
)
```

Ajouter l'import du lookup, en tête du bloc d'imports `app.services.voyage.*` (ordre alphabétique par nom de module — `airports` vient avant `duffel_client`), juste avant la ligne `from app.services.voyage.duffel_client import fetch_offer` (ligne 24) :

```python
from app.services.voyage.airports import lookup_coords
from app.services.voyage.duffel_client import fetch_offer
from app.services.voyage.import_excel import marquer_visites, sync_voyage
from app.services.voyage.solver import solve_itinerary
```

Dans `post_planifier`, juste après la ligne `arrivee_iata = req.arrivee_iata or req.depart_iata` (ligne 106), ajouter :

```python
    arrivee_iata = req.arrivee_iata or req.depart_iata
    depart_lat, depart_lon = lookup_coords(req.depart_iata) or (None, None)
    arrivee_lat, arrivee_lon = lookup_coords(arrivee_iata) or (None, None)
```

Dans la boucle qui construit `etapes` (ligne 151-163), ajouter le lookup et passer `lat`/`lon` au constructeur :

```python
    for i, etape in enumerate(resultat):
        lieu = by_id[etape["id"]]
        prev_id = trajet_ids[i]
        travel_days = math.ceil(trajets[(prev_id, etape["id"])]["duree_min"] / 1440)
        current_date += dt.timedelta(days=travel_days)
        date_arrivee = current_date
        current_date += dt.timedelta(days=etape["jours"])
        date_depart = current_date
        lat, lon = lookup_coords(lieu.aeroport_iata) or (None, None)
        etapes.append(EtapeItineraire(
            lieu_id=lieu.id, nom=lieu.nom, jours=etape["jours"],
            date_arrivee=date_arrivee, date_depart=date_depart,
            lat=lat, lon=lon,
        ))
        cout_sejour += (lieu.cout_jour_estime or 0.0) * etape["jours"]
```

Et modifier le `return` final (ligne 167-170) pour inclure `depart`/`arrivee` :

```python
    return ItineraireOut(
        etapes=etapes, cout_total=cout_transport + cout_sejour,
        cout_transport=cout_transport, cout_sejour=cout_sejour,
        depart=PointItineraire(iata=req.depart_iata, lat=depart_lat, lon=depart_lon),
        arrivee=PointItineraire(iata=arrivee_iata, lat=arrivee_lat, lon=arrivee_lon),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_voyage/test_api.py -v`
Expected: tous les tests du fichier passent (les tests existants ne vérifient pas l'égalité stricte du JSON complet, donc les nouveaux champs ne les cassent pas — vérifié : seul `test_post_sync` compare `r.json() ==` en entier, et il ne touche pas `/planifier`).

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: tous les tests passent (aucune régression sur les autres modules)

- [ ] **Step 6: Commit**

```bash
git add app/api/voyage/schemas.py app/api/voyage/routes.py tests/test_voyage/test_api.py
git commit -m "feat(voyage): enrichit /planifier avec les coordonnées (départ/étapes/arrivée)"
```

---

### Task 3: Frontend — composant carte + intégration

**Files:**
- Modify: `frontend/lib/voyage.ts`
- Create: `frontend/components/voyage/ItineraryMap.tsx`
- Modify: `frontend/components/voyage/PlanifierTab.tsx`
- Test: `frontend/__tests__/components/itinerary-map.test.tsx`

**Interfaces:**
- Consumes: `Itineraire` (type étendu, ce fichier)
- Produces: `itineraryPoints(itineraire: Itineraire) -> Point[] | null` (fonction pure, exportée pour les tests) ; `ItineraryMap({ itineraire }: { itineraire: Itineraire }) -> JSX.Element`

- [ ] **Step 1: Add the new dependencies**

Run (depuis `frontend/`) :
```bash
npm install leaflet react-leaflet
npm install -D @types/leaflet
```
Expected : installation réussie (le repo utilise déjà `legacy-peer-deps=true` dans `.npmrc`, donc pas de conflit peer-deps bloquant avec React 19).

- [ ] **Step 2: Extend the TypeScript types**

Dans `frontend/lib/voyage.ts`, ajouter un nouveau type juste avant `export type EtapeItineraire`, et étendre `EtapeItineraire`/`Itineraire` :

```ts
export type PointItineraire = {
  iata: string;
  lat: number | null;
  lon: number | null;
};

export type EtapeItineraire = {
  lieu_id: number;
  nom: string;
  jours: number;
  date_arrivee: string;
  date_depart: string;
  lat: number | null;
  lon: number | null;
};

export type Itineraire = {
  etapes: EtapeItineraire[];
  cout_total: number;
  cout_transport: number;
  cout_sejour: number;
  depart: PointItineraire;
  arrivee: PointItineraire;
};
```

(Remplace les définitions existantes de `EtapeItineraire` et `Itineraire` dans ce fichier — mêmes noms, champs supplémentaires.)

- [ ] **Step 3: Write the failing test**

```tsx
// frontend/__tests__/components/itinerary-map.test.tsx
import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ItineraryMap, itineraryPoints } from "@/components/voyage/ItineraryMap";
import type { Itineraire } from "@/lib/voyage";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Marker: ({ children }: { children: ReactNode }) => <div data-testid="marker">{children}</div>,
  Polyline: () => null,
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("leaflet", () => ({
  default: { Icon: { Default: { prototype: {}, mergeOptions: vi.fn() } } },
}));

const ITINERAIRE_COMPLET: Itineraire = {
  etapes: [
    {
      lieu_id: 1, nom: "Table Mountain", jours: 2,
      date_arrivee: "2026-09-02", date_depart: "2026-09-04",
      lat: -33.96, lon: 18.6,
    },
  ],
  cout_total: 1160, cout_transport: 1000, cout_sejour: 160,
  depart: { iata: "YUL", lat: 45.47, lon: -73.74 },
  arrivee: { iata: "YUL", lat: 45.47, lon: -73.74 },
};

const ITINERAIRE_SANS_COORD: Itineraire = {
  ...ITINERAIRE_COMPLET,
  etapes: [{ ...ITINERAIRE_COMPLET.etapes[0], lat: null, lon: null }],
};

describe("itineraryPoints", () => {
  it("construit départ + étapes + arrivée dans l'ordre", () => {
    const points = itineraryPoints(ITINERAIRE_COMPLET);
    expect(points).toHaveLength(3);
    expect(points?.[0].label).toContain("Départ");
    expect(points?.[1].label).toBe("Table Mountain");
    expect(points?.[2].label).toContain("Arrivée");
  });

  it("renvoie null si une étape n'a pas de coordonnées", () => {
    expect(itineraryPoints(ITINERAIRE_SANS_COORD)).toBeNull();
  });
});

describe("ItineraryMap", () => {
  it("affiche un marqueur par point", () => {
    render(<ItineraryMap itineraire={ITINERAIRE_COMPLET} />);
    expect(screen.getAllByTestId("marker")).toHaveLength(3);
  });

  it("affiche un repli si les coordonnées manquent", () => {
    render(<ItineraryMap itineraire={ITINERAIRE_SANS_COORD} />);
    expect(screen.getByText(/indisponible/)).toBeInTheDocument();
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run (depuis `frontend/`) : `npm test -- itinerary-map`
Expected: FAIL — `Cannot find module '@/components/voyage/ItineraryMap'`

- [ ] **Step 5: Write minimal implementation**

```tsx
// frontend/components/voyage/ItineraryMap.tsx
"use client";

import type { ReactNode } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Itineraire } from "@/lib/voyage";

// Le bundler ne préserve pas les chemins d'assets relatifs que Leaflet
// utilise par défaut pour ses icônes de marqueur ; sans ce correctif les
// marqueurs s'affichent avec une image cassée.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

type Point = { lat: number; lon: number; label: string; detail?: ReactNode };

/** Départ -> étapes (ordre du solveur) -> arrivée. `null` si un point du
 * parcours n'a pas de coordonnées connues (jamais de carte partielle). */
export function itineraryPoints(itineraire: Itineraire): Point[] | null {
  const { depart, arrivee, etapes } = itineraire;
  if (depart.lat == null || depart.lon == null) return null;
  if (arrivee.lat == null || arrivee.lon == null) return null;

  const points: Point[] = [{ lat: depart.lat, lon: depart.lon, label: `Départ (${depart.iata})` }];
  for (const e of etapes) {
    if (e.lat == null || e.lon == null) return null;
    points.push({ lat: e.lat, lon: e.lon, label: e.nom, detail: `${e.date_arrivee} → ${e.date_depart}` });
  }
  points.push({ lat: arrivee.lat, lon: arrivee.lon, label: `Arrivée (${arrivee.iata})` });
  return points;
}

export function ItineraryMap({ itineraire }: { itineraire: Itineraire }) {
  const points = itineraryPoints(itineraire);

  if (!points) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-3 text-sm text-[var(--muted-foreground)]">
        Carte indisponible pour cet itinéraire.
      </div>
    );
  }

  const positions: [number, number][] = points.map((p) => [p.lat, p.lon]);

  return (
    <MapContainer
      center={positions[0]}
      zoom={3}
      bounds={positions}
      scrollWheelZoom={false}
      className="h-64 w-full rounded-lg"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Polyline positions={positions} />
      {points.map((p, i) => (
        <Marker key={i} position={[p.lat, p.lon]}>
          <Popup>
            {p.label}
            {p.detail && <div>{p.detail}</div>}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npm test -- itinerary-map`
Expected: 4 passed

- [ ] **Step 7: Integrate into `PlanifierTab.tsx`**

Ajouter l'import `dynamic` de Next.js et le chargement dynamique du composant, juste après les imports existants (ligne 6) :

```tsx
import { notifySuccess } from "@/lib/toast";
import dynamic from "next/dynamic";

const ItineraryMap = dynamic(
  () => import("./ItineraryMap").then((m) => m.ItineraryMap),
  { ssr: false },
);
```

Insérer `<ItineraryMap>` juste avant le `<ol>` existant, à l'intérieur du bloc `{resultat && (...)}` (juste après la `<div className="text-sm font-semibold">...</div>` du résumé, ligne 82) :

```tsx
          <div className="text-sm font-semibold">
            {resultat.etapes.length} lieu(x) retenu(s) · {resultat.cout_total.toFixed(0)} €
            (transport {resultat.cout_transport.toFixed(0)} € + séjour {resultat.cout_sejour.toFixed(0)} €)
          </div>
          <ItineraryMap itineraire={resultat} />
          <ol className="list-decimal space-y-1 pl-5 text-sm">
```

- [ ] **Step 8: Vérifier le typecheck**

Run (depuis `frontend/`) : `npx tsc --noEmit`
Expected : aucune erreur de type

- [ ] **Step 9: Run the full frontend test suite to check for regressions**

Run: `npm test -- --run`
Expected: tous les fichiers de test passent (aucune régression sur les autres modules)

- [ ] **Step 10: Commit**

```bash
git add lib/voyage.ts components/voyage/ItineraryMap.tsx components/voyage/PlanifierTab.tsx __tests__/components/itinerary-map.test.tsx package.json package-lock.json
git commit -m "feat(voyage): carte Leaflet de l'itinéraire conseillé"
```

---

## Décomposition (rappel)

1. Table locale IATA → coordonnées (CSV généré depuis OurAirports + loader) + tests
2. Backend : enrichissement `lat`/`lon` dans la réponse `/voyage/planifier` (schémas + route) + tests
3. Frontend : types étendus + composant `ItineraryMap` (Leaflet) + intégration dans `PlanifierTab` + tests

Chaque tâche produit un livrable testable indépendamment ; les tâches 1-2 (backend) sont vérifiables via l'API/Swagger avant même que la tâche 3 (frontend) n'existe.
