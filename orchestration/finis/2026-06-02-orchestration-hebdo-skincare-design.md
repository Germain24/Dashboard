# Design — Orchestration hebdomadaire + module Skincare

> Date : 2026-06-02
> Statut : validé (brainstorming), en attente de relecture avant plan d'implémentation
> Branche de travail prévue : à créer depuis `main`

## 1. Objectif

Relier les modules de Mission Control pour qu'**une seule génération planifie la semaine entière**, au lieu de générer chaque domaine indépendamment. Le système place automatiquement, autour de contraintes fixes, l'ensemble des activités optimisables.

### Contraintes FIXES (non négociables)
- **Horaires de cours** : identiques, changent seulement par semestre → modèle hebdomadaire avec fenêtre de validité.
- **Horaires de travail** : flux iCal Agendrix (`.ics`).
- **Coût des études** (sortie budget) et **revenus du travail** (entrée budget).

### Optimisable autour des contraintes fixes
Repas (cuisine + macros + budget), skincare, entraînement/sport, sessions d'étude, habitudes — et le **sommeil** (durée garantie chaque nuit).

### Décisions de cadrage (validées)
- Le plan est **appliqué automatiquement** (events agenda, plan repas, routine skincare, sessions d'étude, habitudes), mais **éditable** : tout item déplacé/supprimé devient `locked` et est respecté aux régénérations.
- Périmètre v1 : **les 4 domaines** (repas, skincare, sport, étude+habitudes).
- Priorité en cas de tension : **études/deadlines d'abord**, puis le reste.
- Horizon : **hebdomadaire** (réserve le sommeil, répartit les tâches hebdo, équilibre la charge).
- Approche : **solveur d'optimisation CP-SAT (OR-Tools)**, structuré de façon modulaire.

## 2. Architecture

```
   Sources FIXES                        WeeklyContext (7 jours)
   - ScheduleTemplate (cours)   ──┐
   - ExternalCalendarFeed .ics  ──┤──▶  blocs fixes → free_slots (existe déjà)
     (Agendrix)                    │     budget restant, macros cibles,
                                   │     deadlines/charge étude, stock+freq skincare
                                   ▼
   Domaines = CONTRIBUTORS : etudes | repas | sport | skincare | habitudes | sommeil
        chacun : contribute(context) -> CandidateTask[]
                                   │
                                   ▼
   SOLVEUR CP-SAT (hebdomadaire) : maximise Σ utilité
        s.c. no-overlap/jour, fenêtres, budget, cardinalité+espacement hebdo,
             sommeil garanti, obligatoires (deadlines) forcés, anti-surcharge
                                   │
                                   ▼
   WeeklyPlan + DailyPlanItems  → application : events agenda, plan repas,
                                   routine skincare, sessions étude, habitudes
```

Le contexte est **hebdomadaire** (`WeeklyContext`) et contient, par jour, les blocs fixes, créneaux libres, budget, macros, deadlines et l'état skincare ; chaque contributor le reçoit en entier pour décider de la répartition sur la semaine.

**Principe d'isolation** : les domaines ne connaissent pas le solveur (ils déclarent des `CandidateTask` : durée, fenêtres valides, coût, utilité, priorité, fréquence, obligatoire/optionnel) ; le solveur ne connaît pas les domaines (il manipule des tâches abstraites et renvoie des placements). Chaque côté est testable seul.

## 3. Modèle de données

### Module Skincare (nouveau)
- **`SkincareProduct`** : `nom`, `type` (nettoyant/sérum/hydratant/SPF/exfoliant/masque/rétinoïde…), `moment` (AM | PM | les_deux), `ordre` (position dans la routine), `frequence` (quotidien | n_par_semaine | jours_precis), contraintes de placement (`apres_douche`, `soir_seulement`, `pas_avant_soleil`), `duree_min`, `stock_qte` + `unite`, `date_ouverture`, `date_peremption`, `cout`, `actif`.
- **`SkincareLog`** : `date`, `moment`, produits appliqués, `note`.
- La routine AM/PM = ensemble ordonné des produits actifs du moment (pas de table dédiée).
- Rachat (stock bas / péremption) → dépense prévue → **lien Budget**.

### Contraintes fixes
- **`ScheduleTemplate`** (cours) : `type`, `label`, `weekday`, `heure_debut`, `heure_fin`, `valid_from`, `valid_to` (semestre). Décision : table dédiée (séparation claire) plutôt que la récurrence agenda.
- **`ExternalCalendarFeed`** (travail) : `type`, `url` (.ics Agendrix), `actif`, `last_sync`, cache du dernier contenu. Réutilise `app/services/agenda/ical_adapter.py` pour le parsing.

### Orchestration
- **`WeeklyPlan`** : `week_start` (unique), `status` (generated|applied|edited), `generated_at`, `solver_meta` (json : score, faisabilité, conflits), `notes`.
- **`DailyPlanItem`** : `weekly_plan_id`, `date`, `domain` (etudes|repas|sport|skincare|habitudes|sommeil), `titre`, `debut`, `fin`, `duree_min`, `cout`, `utilite`, `ref_type` + `ref_id` (vers l'objet créé dans le module), `source` (generated|manual), `locked` (bool), `status` (planned|done|skipped).

### Interface partagée (dataclass, pas une table)
- **`CandidateTask`** : `domain`, `titre`, `duree_min`, fenêtres horaires valides, `cout`, `utilite`, `priorite`, `frequence_key` (dédup/cardinalité hebdo), `obligatoire` (bool), dépendances/précédences.

## 4. Solveur (CP-SAT / OR-Tools)

- **Discrétisation** : créneaux de 15 min, 7 jours. Les blocs fixes (cours + shifts Agendrix) marquent les créneaux indisponibles par jour.
- **Variables** : par `CandidateTask`, un intervalle optionnel (présence booléenne + début) contraint aux fenêtres valides et aux créneaux libres.
- **Contraintes** :
  - `NoOverlap` par jour (la journée = ressource unique).
  - Fenêtres par tâche : skincare PM = soir ; SPF = matin ; « après douche » = précédence ; « pas avant soleil » = avant blocs extérieurs.
  - **Budget** : Σ coût des tâches retenues ≤ enveloppe (linéaire).
  - **Cardinalité + espacement hebdo** : une fréquence « n×/sem » = n placements sur 7 jours, espacés (ex. exfoliant ≥2 jours).
  - **Sommeil** : tâche obligatoire par nuit, durée min configurable, fenêtre nocturne adaptée au shift du lendemain (Agendrix).
  - **Priorité études** : tâches proches d'une deadline = obligatoires + forte utilité.
- **Objectif** : maximiser Σ(utilité × présence) − pénalités (fragmentation, tardiveté, surcharge journalière).
- **Faisabilité** : tâches optionnelles à faible utilité abandonnées naturellement ; obligatoire infaisable → conflit signalé (Notification), pas d'échec silencieux.
- **Perf** : ~672 créneaux (7×96) × ~20-30 tâches → résolution attendue <1-2 s.

## 5. Orchestration, application, idempotence

- **Job hebdomadaire** `weekly_generation` (ex. lundi 5h), via `run_job` → `JobRun` + `Notification`.
- **Étapes** : construire le contexte (blocs fixes + `free_slots` + budget + macros + deadlines + skincare dû) → `contribute()` par domaine → `solve()` → persister `WeeklyPlan` + items → **appliquer** (créer events/plan repas/routine/sessions/habitudes, stocker `ref_type`+`ref_id`).
- **Idempotence** : re-générer une semaine supprime les items `generated && !locked` (+ refs), garde les items `locked`, et re-résout autour d'eux (items verrouillés = blocs fixes du nouveau solve).
- **Édition / override** : déplacer/supprimer un item en UI → `locked=manual`, respecté à la régénération. Réconcilie « appliqué automatiquement » + « je peux ajuster ».
- **Re-solve partiel** en cours de semaine (changement de shift Agendrix, imprévu) : re-résout *aujourd'hui → fin de semaine*, garde passé + `locked`.
- **Robustesse** : chaque contributor en try/except (un domaine en échec ne tue pas le plan, log + notif) ; échec fetch Agendrix → dernier .ics en cache + flag `solver_meta` ; infaisabilité obligatoire → Notification.

### API
- `GET /weekly/current`, `POST /weekly/regenerate`, `POST /weekly/resolve-from/{date}`
- `PATCH /daily/items/{id}` (déplacer | lock | done | skip)
- CRUD Skincare (`/skincare/products`, `/skincare/log`)
- `ScheduleTemplate` (cours) et config du flux Agendrix.

### Frontend
- Vue « Ma semaine » : timeline 7 jours du plan, items éditables (drag/lock/done), bouton régénérer.
- Module Skincare : produits, routines AM/PM, stock/péremption, fréquence.

## 6. Tests

- **Solveur** (pur, sans DB) : no-overlap, fenêtres, sommeil garanti, cardinalité/espacement, budget, obligatoires forcés, infaisabilité signalée.
- **Contributors** : `DailyContext` factice → bonnes `CandidateTask` (fréquence, coût, fenêtres).
- **Adaptateur Agendrix** : parse un `.ics` d'exemple → shifts ; builder de contexte sur DB mémoire.
- **Orchestrateur** (intégration, DB mémoire) : `WeeklyPlan` + items + refs ; re-génération idempotente préserve les `locked`.
- **Skincare** : CRUD + logique fréquence/stock.

## 7. Découpage incrémental (chaque étape livrable seule)

1. **Module Skincare** (modèles, CRUD, routes, UI) — autonome, valeur immédiate, fournit les données au solveur.
2. **Entrées fixes** : `ScheduleTemplate` (cours) + adaptateur Agendrix `.ics` (réutilise `ical_adapter`) + builder `WeeklyContext` (`free_slots` existe).
3. **Solveur CP-SAT** + interface `CandidateTask` — pur, testé isolément.
4. **Contributors** par domaine : études → repas → sport → skincare → habitudes → sommeil.
5. **Orchestrateur** + persistance + application + idempotence + job hebdo + re-solve partiel.
6. **Frontend** « Ma semaine » + régénérer/éditer.

## 8. Dépendances / risques

- Backend : ajouter `ortools` (solveur) ; parseur iCal (réutiliser l'existant ou `icalendar`).
- Flux Agendrix : URL privée à token UUID — stockée en config, fetch serveur + cache, données gardées en local.
- Dégradation propre : un contributor produit moins/pas de tâches si son module manque de données (ex. pas d'objectif macro → pas de repas imposé).
- Le fuseau Agendrix (America/New_York) ≈ Montréal — à normaliser explicitement à la lecture du `.ics`.

## 9. Lien avec AMELIORATIONS_200.txt

Ce chantier fait avancer/subsume : #72 (plan repas ↔ macros), #89 (focus étude ↔ agenda), #120 (budget ↔ cuisine), #129 (recettes selon macros), #136 (rappels habitudes), #159 (récap quotidien), partiellement #66/#68 (hydratation/sommeil) — plus le nouveau module Skincare.
