# #110 — Programme d'entraînement périodisé (mésocycle) avec progression auto

Statut : design validé · 2026-06-06 · module Entraînement (mission-control)

## Objectif

Ajouter au module Entraînement une **périodisation par mésocycle de prise de muscle**
avec progression automatique. Le schéma retenu (consensus hypertrophie / Renaissance
Periodization) : faire **monter le volume hebdomadaire (séries) de MEV vers MRV**
semaine après semaine, puis une **semaine de deload**. Réutilise les repères MEV 10 /
MRV 20 du #107 et le poids suggéré existant (`suggested_weight`).

## Décisions

- **Schéma** : volume montant + deload (pas de progression de charge linéaire, pas d'ondulatoire).
- **Avance** : automatique par date. L'utilisateur démarre un cycle ; la semaine courante se déduit du calendrier.
- **Overlay non destructif** : on ne réécrit jamais le `Programme`/`ProgrammeJour` stocké ; on calcule la cible de la semaine à la volée.
- **Sans migration** : store JSON local, comme `goals.py` / `revision.py`.
- **Longueur de cycle** : `accumulation_weeks` (défaut 4) semaines d'accumulation + 1 deload = 5 semaines.

## Architecture

Nouveau service pur + store : `backend/app/services/entrainement/mesocycle.py`.

### Données

`data/entrainement_mesocycle.json` :

```json
{ "start_date": "2026-06-01", "accumulation_weeks": 4, "active": true }
```

Absent / `active=false` → aucun cycle actif (l'UI affiche « démarrer un cycle »).

### Fonctions pures (testables, `today` injectable)

- `current_phase(start_date, accumulation_weeks, today) -> dict`
  - `semaines_ecoulees = (today_monday - start_monday).days // 7`
  - `cycle_len = accumulation_weeks + 1`
  - `semaine_cycle = semaines_ecoulees % cycle_len`  (0-indexé)
  - `cycle_num = semaines_ecoulees // cycle_len`
  - `phase = "deload" if semaine_cycle == accumulation_weeks else "accumulation"`
  - retourne `{ cycle_num, semaine_cycle (1-indexé pour l'UI), accumulation_weeks, phase }`
- `adjust_sets(base_sets_target, phase_info) -> int`
  - accumulation (semaine `w` 1-indexée) : `base + (w - 1)` (+1 série par semaine d'accumulation)
  - deload : `max(1, round(base / 2))`
  - garde-fou : jamais en dessous de 1 ; `base` None → None (slot sans cible de séries inchangé)

La **charge** reste pilotée par `suggested_weight` (inchangé). En deload, l'UI signale « charge allégée » sans modifier le calcul (choix V1 : le deload porte sur le volume, pas la charge).

### Store (helpers, mêmes conventions que goals.py)

- `mesocycle_file()` → `settings.data_dir / "entrainement_mesocycle.json"`
- `get_state(*, path=None) -> dict | None`
- `start_cycle(accumulation_weeks=4, *, path=None, today=None) -> dict` (écrit start_date = lundi de la semaine de `today`)
- `stop_cycle(*, path=None)`

## API (routes_entrainement.py)

- `GET /entrainement/mesocycle` → `MesocycleResponse` : `{ active, cycle_num, semaine_cycle, accumulation_weeks, phase, cycle_len }` (ou `{active:false}`).
- `POST /entrainement/mesocycle/start?accumulation_weeks=4` → état après démarrage.
- `POST /entrainement/mesocycle/stop` → `{active:false}`.
- **Enrichissement `/today`** : quand un cycle est actif, chaque `SlotToday` reçoit `sets_target_semaine` (= `adjust_sets(slot.sets_target, phase)`). `TodayResponse` reçoit `mesocycle` (l'état courant) pour que l'UI affiche le bandeau.

Schémas : `MesocycleResponse` ; champ `sets_target_semaine: Optional[int]` sur `SlotToday` ; champ `mesocycle: Optional[MesocycleResponse]` sur `TodayResponse`.

## Frontend

- `lib/entrainement.ts` : type `Mesocycle` + `entrainementApi.getMesocycle()/startMesocycle()/stopMesocycle()`.
- Bandeau « Mésocycle » dans `AujourdhuiTab` (emplacement principal ; `ProgrammeTab` = optionnel plus tard) : phase (« Accumulation S2/4 » ou « Deload »), barre de progression du cycle, bouton Démarrer / Arrêter.
- `SlotCard` : quand un cycle tourne, afficher la **cible de séries de la semaine** (`sets_target_semaine`) à la place de la cible de base, avec un indice deload (« charge allégée ») en phase deload.

## Tests (TDD)

- `test_mesocycle.py` :
  - `current_phase` : semaine 0 = accumulation S1 ; dernière semaine d'accumulation ; semaine deload ; passage au cycle suivant (cycle_num incrémenté, retour en accumulation S1) ; bords de semaine (ancrage lundi).
  - `adjust_sets` : ramp +1/sem en accumulation, deload ≈ moitié, garde-fou ≥ 1, base None → None.
  - store : start/get/stop via `tmp_path` (pas d'écriture dans le vrai data_dir).
- Test API léger : `GET /mesocycle` inactif par défaut ; `start` puis `GET` actif ; `/today` expose `sets_target_semaine` cohérent.

## Hors périmètre (YAGNI)

- Progression de charge linéaire et ondulatoire (DUP).
- Réécriture destructive du programme / job scheduler.
- Modèle multi-mésocycles persistant (historique de blocs).
- Périodisation de la charge en deload (V1 = volume seulement).
