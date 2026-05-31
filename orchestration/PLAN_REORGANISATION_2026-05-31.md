# Project Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize mission-control into exactly 3 root folders (backend/, frontend/, orchestration/) with clean internal structure, move graphify results into orchestration, delete legacy_code, and create a proper activity/changelog log system.

**Architecture:** All project-tracking artifacts (graphify, CONV briefs, DONE reports, logs) live under `orchestration/`. The backend and frontend directories are unchanged structurally. `legacy_code/` is deleted (user confirmed copy exists elsewhere).

**Tech Stack:** PowerShell (Windows), git mv for tracked files, manual Write for new Markdown files.

---

## Current vs Target Structure

```
BEFORE                              AFTER
──────────────────────────────────────────────────────────
mission-control/                    mission-control/
├── backend/           (unchanged)  ├── backend/
├── frontend/          (unchanged)  ├── frontend/
├── data/              (unchanged)  ├── data/
├── graphify-out/      (MOVE)       ├── orchestration/
├── legacy_code/       (DELETE)     │   ├── PLAN.md             (stays)
├── orchestration/                  │   ├── CHANGELOG.md        (NEW)
│   ├── PLAN.md                     │   ├── graphify/           (MOVED from ../graphify-out/)
│   ├── CONV*_DONE.md (26 files)    │   ├── convs/
│   └── CONV*_brief.md              │   │   ├── done/           (MOVED: all *_DONE.md)
├── .env               (unchanged)  │   │   └── briefs/         (MOVED: all non-done CONVs)
├── .gitignore         (unchanged)  │   └── logs/
├── Makefile           (unchanged)  │       └── ACTIVITY.md     (NEW)
└── README.md          (unchanged)  ├── .env / .gitignore / Makefile / README.md
```

## Files Map

| Action | Source | Destination |
|--------|--------|-------------|
| MOVE   | `graphify-out/` (entire dir) | `orchestration/graphify/` |
| DELETE | `legacy_code/` (entire dir) | — |
| MOVE   | `orchestration/CONV1_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV2_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV3_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV4_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV5_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV6_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV7_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV_DESIGN_DONE.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV3_FOR_CONV1.md` | `orchestration/convs/done/` |
| MOVE   | `orchestration/CONV1_fondation.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV2_garderobe.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV3_sante_nutrition.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV4_finance.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV5_agenda.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV6_etudes.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV7_entrainement.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV_DESIGN.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV8_budget.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV9_cuisine.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV10_habitudes.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV11_livres.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV12_agent_ia.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV13_scheduler.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV14_auth_acces_distant.md` | `orchestration/convs/briefs/` |
| MOVE   | `orchestration/CONV15_tests_ci_doc.md` | `orchestration/convs/briefs/` |
| CREATE | — | `orchestration/CHANGELOG.md` |
| CREATE | — | `orchestration/logs/ACTIVITY.md` |
| UPDATE | `CLAUDE.md` (root) | fix graphify path |
| UPDATE | `orchestration/PLAN.md` | fix architecture diagram paths |

---

## Task 1: Create new directory structure

**Files:**
- Create: `orchestration/convs/done/` (directory)
- Create: `orchestration/convs/briefs/` (directory)
- Create: `orchestration/logs/` (directory)

- [ ] **Step 1: Create subdirectories**

```powershell
New-Item -ItemType Directory -Force "C:\Users\germa\Documents\GitHub\mission-control\orchestration\convs\done"
New-Item -ItemType Directory -Force "C:\Users\germa\Documents\GitHub\mission-control\orchestration\convs\briefs"
New-Item -ItemType Directory -Force "C:\Users\germa\Documents\GitHub\mission-control\orchestration\logs"
```

Expected: 3 directories created, no errors.

- [ ] **Step 2: Verify**

```powershell
Get-ChildItem "C:\Users\germa\Documents\GitHub\mission-control\orchestration" -Depth 1 | Select-Object FullName, PSIsContainer
```

Expected: `convs/`, `convs/done/`, `convs/briefs/`, `logs/` visible.

---

## Task 2: Move DONE reports to convs/done/

**Files:**
- Move: all `orchestration/*_DONE.md` and `CONV3_FOR_CONV1.md`
- Destination: `orchestration/convs/done/`

- [ ] **Step 1: Move via git mv (preserves history)**

```powershell
cd "C:\Users\germa\Documents\GitHub\mission-control"
git mv orchestration/CONV1_DONE.md orchestration/convs/done/CONV1_DONE.md
git mv orchestration/CONV2_DONE.md orchestration/convs/done/CONV2_DONE.md
git mv orchestration/CONV3_DONE.md orchestration/convs/done/CONV3_DONE.md
git mv orchestration/CONV4_DONE.md orchestration/convs/done/CONV4_DONE.md
git mv orchestration/CONV5_DONE.md orchestration/convs/done/CONV5_DONE.md
git mv orchestration/CONV6_DONE.md orchestration/convs/done/CONV6_DONE.md
git mv orchestration/CONV7_DONE.md orchestration/convs/done/CONV7_DONE.md
git mv orchestration/CONV_DESIGN_DONE.md orchestration/convs/done/CONV_DESIGN_DONE.md
git mv orchestration/CONV3_FOR_CONV1.md orchestration/convs/done/CONV3_FOR_CONV1.md
```

- [ ] **Step 2: Verify**

```powershell
Get-ChildItem "C:\Users\germa\Documents\GitHub\mission-control\orchestration\convs\done"
```

Expected: 9 files listed.

---

## Task 3: Move conversation briefs to convs/briefs/

**Files:**
- Move: all non-DONE `orchestration/CONV*.md` files
- Destination: `orchestration/convs/briefs/`

- [ ] **Step 1: Move all briefs via git mv**

```powershell
cd "C:\Users\germa\Documents\GitHub\mission-control"
git mv orchestration/CONV1_fondation.md orchestration/convs/briefs/CONV1_fondation.md
git mv orchestration/CONV2_garderobe.md orchestration/convs/briefs/CONV2_garderobe.md
git mv orchestration/CONV3_sante_nutrition.md orchestration/convs/briefs/CONV3_sante_nutrition.md
git mv orchestration/CONV4_finance.md orchestration/convs/briefs/CONV4_finance.md
git mv orchestration/CONV5_agenda.md orchestration/convs/briefs/CONV5_agenda.md
git mv orchestration/CONV6_etudes.md orchestration/convs/briefs/CONV6_etudes.md
git mv orchestration/CONV7_entrainement.md orchestration/convs/briefs/CONV7_entrainement.md
git mv orchestration/CONV_DESIGN.md orchestration/convs/briefs/CONV_DESIGN.md
git mv orchestration/CONV8_budget.md orchestration/convs/briefs/CONV8_budget.md
git mv orchestration/CONV9_cuisine.md orchestration/convs/briefs/CONV9_cuisine.md
git mv orchestration/CONV10_habitudes.md orchestration/convs/briefs/CONV10_habitudes.md
git mv orchestration/CONV11_livres.md orchestration/convs/briefs/CONV11_livres.md
git mv orchestration/CONV12_agent_ia.md orchestration/convs/briefs/CONV12_agent_ia.md
git mv orchestration/CONV13_scheduler.md orchestration/convs/briefs/CONV13_scheduler.md
git mv orchestration/CONV14_auth_acces_distant.md orchestration/convs/briefs/CONV14_auth_acces_distant.md
git mv orchestration/CONV15_tests_ci_doc.md orchestration/convs/briefs/CONV15_tests_ci_doc.md
```

- [ ] **Step 2: Verify**

```powershell
Get-ChildItem "C:\Users\germa\Documents\GitHub\mission-control\orchestration\convs\briefs" | Measure-Object
```

Expected: Count = 16.

---

## Task 4: Move graphify-out/ into orchestration/graphify/

**Files:**
- Move: `graphify-out/` (entire directory) → `orchestration/graphify/`

- [ ] **Step 1: Move directory via PowerShell (git tracks content)**

```powershell
Move-Item "C:\Users\germa\Documents\GitHub\mission-control\graphify-out" "C:\Users\germa\Documents\GitHub\mission-control\orchestration\graphify"
```

- [ ] **Step 2: Stage the move in git**

```powershell
cd "C:\Users\germa\Documents\GitHub\mission-control"
git add -A orchestration/graphify
git rm -r --cached graphify-out 2>$null
```

- [ ] **Step 3: Verify**

```powershell
Test-Path "C:\Users\germa\Documents\GitHub\mission-control\orchestration\graphify\GRAPH_REPORT.md"
Test-Path "C:\Users\germa\Documents\GitHub\mission-control\graphify-out"
```

Expected: first = True, second = False.

---

## Task 5: Delete legacy_code/

**Note:** User confirmed the legacy code is saved elsewhere. This deletes the local copy.

- [ ] **Step 1: Remove from git tracking and disk**

```powershell
cd "C:\Users\germa\Documents\GitHub\mission-control"
git rm -r --cached legacy_code
Remove-Item -Recurse -Force "C:\Users\germa\Documents\GitHub\mission-control\legacy_code"
```

- [ ] **Step 2: Verify deletion**

```powershell
Test-Path "C:\Users\germa\Documents\GitHub\mission-control\legacy_code"
```

Expected: False.

---

## Task 6: Update CLAUDE.md to fix graphify path

**Files:**
- Modify: `C:\Users\germa\CLAUDE.md` — update path `graphify-out/` → `orchestration/graphify/`

- [ ] **Step 1: Read current CLAUDE.md**

Use Read tool on `C:\Users\germa\CLAUDE.md`.

- [ ] **Step 2: Update graphify references**

Replace every occurrence of `graphify-out/` with `orchestration/graphify/` using Edit tool.

Also update the CLAUDE.md inside the project root if it mentions `graphify-out/`:

```powershell
Select-String -Path "C:\Users\germa\Documents\GitHub\mission-control\CLAUDE.md" -Pattern "graphify-out"
```

Fix any matches found.

- [ ] **Step 3: Verify**

```powershell
Select-String -Path "C:\Users\germa\CLAUDE.md" -Pattern "graphify-out"
Select-String -Path "C:\Users\germa\Documents\GitHub\mission-control\CLAUDE.md" -Pattern "graphify-out"
```

Expected: 0 matches in both files.

---

## Task 7: Update PLAN.md architecture diagram

**Files:**
- Modify: `orchestration/PLAN.md` — update the architecture tree to show new paths

- [ ] **Step 1: Replace old architecture block**

In `orchestration/PLAN.md`, find and update the architecture section to reflect:
- `orchestration/` containing `convs/done/`, `convs/briefs/`, `logs/`, `graphify/`
- No `graphify-out/` or `legacy_code/` at root

- [ ] **Step 2: Verify no stale paths remain**

```powershell
Select-String -Path "C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md" -Pattern "graphify-out|legacy_code"
```

Expected: 0 matches.

---

## Task 8: Create CHANGELOG.md

**Files:**
- Create: `orchestration/CHANGELOG.md`

- [ ] **Step 1: Write the file**

Create `orchestration/CHANGELOG.md` with a timeline of all completed work extracted from the PLAN.md phase tables and DONE files:

```markdown
# Mission Control — Changelog

Historique chronologique de toutes les modifications majeures du projet.
Maintenu manuellement à chaque fin de conversation de développement.

---

## 2026-05-28 — CONV 4 : Module Finance
**Commit :** `81ed30c`
- Port complet du module Finance (suivi portefeuille, transactions CSV)
- Refactor WarrenBuffetMensuel.py → 13+ sous-modules < 200 lignes
- Tables : `buffett_run`, `buffett_run_result`, `snapshot_portefeuille`, `transaction`, `position`
- 40 tests verts (19 scoring pur Python + 21 API intégration)
- APScheduler stubbé (snapshot 22h, Buffett mensuel 3h 1er du mois)

## 2026-05-26 — CONV DESIGN : Design System
**Commits :** `cb87444`, `583a7cf`, `39d951e`, `59d158e`
- Design system complet : CSS variables, thème dark/light, densité compact
- 12 primitives UI dans `frontend/components/ui/`
- Migration de tous les modules existants vers le design system
- `frontend/DESIGN.md` = spec de référence contraignante

## 2026-05-26 — CONV 6 : Module Études
- Module Études from-scratch (pas de code Streamlit de référence)
- Tables : `cours`, `evaluation`, `session_etude`
- 43 tests verts

## 2026-05-25 — CONV 5 : Module Agenda
**Commit :** `63fc207`
- Module Agenda avec récurrences virtuelles (non persistées)
- Tables : `evenement` (étendu), `regle_recurrence`, `tache`
- Bridge Études → Agenda câblé (source/source_id)

## 2026-05-20 — CONV 7 : Module Entraînement
- Module Entraînement + import Garmin
- Tables : `seance`, `exercice`, `programme`, `programme_jour`, `set_serie`, `course_cardio`
- 148 tests verts
- Hook intensité Santé ↔ Entraînement

## 2026-05-17 — CONV 3 : Module Santé / Nutrition
**Commit :** `ac38f21`
- Module Santé : mesures, plan nutrition, aliments, objectifs
- Tables : `mesure_sante`, `plan_nutrition`, `aliment`, `nutrition_goal`

## 2026-05-16 — CONV 2 : Module Garde-robe
- Module Garde-robe complet
- Tables : `vetement` (23 entrées), `tenue_history`

## 2026-05-14 — CONV 1 : Fondation
- Bootstrap monorepo FastAPI + Next.js + SQLite
- 17 tables créées, 4 098 lignes legacy importées
- `make dev` opérationnel, 11 pages routées

---

## Modules restants (pas encore implémentés)

| # | Module | CONV |
|---|--------|------|
| 8 | Budget | CONV 8 |
| 9 | Cuisine | CONV 9 |
| 10 | Habitudes | CONV 10 |
| 11 | Livres | CONV 11 |
| 12 | Agent IA | CONV 12 |
| 13 | Scheduler | CONV 13 |
| 14 | Auth / Tailscale | CONV 14 |
| 15 | Tests, CI, Docs | CONV 15 |
```

---

## Task 9: Create logs/ACTIVITY.md

**Files:**
- Create: `orchestration/logs/ACTIVITY.md`

- [ ] **Step 1: Write the file**

Create `orchestration/logs/ACTIVITY.md` as the running log of Claude's actions:

```markdown
# Mission Control — Journal d'activité Claude

Log chronologique de toutes les modifications effectuées par Claude Code.
Chaque entrée = une session avec date, fichiers touchés, et résultat.

Format :
```
## YYYY-MM-DD — [Description courte]
**Session :** [CONV N ou type d'action]
**Fichiers modifiés :** liste
**Résultat :** [succès / partiel / erreur]
**Notes :** [décisions importantes, workarounds]
```

---

## 2026-05-31 — Réorganisation complète du projet

**Session :** Reorganisation (hors CONV numérotée)
**Fichiers modifiés :**
- `orchestration/convs/done/` — création + déplacement de 9 fichiers DONE
- `orchestration/convs/briefs/` — création + déplacement de 16 briefs CONV
- `orchestration/graphify/` — déplacement depuis `graphify-out/`
- `legacy_code/` — suppression (code sauvegardé ailleurs par Germain)
- `orchestration/CHANGELOG.md` — création
- `orchestration/logs/ACTIVITY.md` — création (ce fichier)
- `CLAUDE.md` — mise à jour chemin graphify
- `orchestration/PLAN.md` — mise à jour diagramme architecture

**Résultat :** Succès — structure 3 dossiers racine établie
**Notes :** legacy_code supprimé sur demande explicite de Germain (copie externe confirmée).
```

---

## Task 10: Commit the reorganization

- [ ] **Step 1: Stage all changes**

```powershell
cd "C:\Users\germa\Documents\GitHub\mission-control"
git add -A
git status
```

Expected: All moves/deletes/creates staged, no surprises.

- [ ] **Step 2: Commit**

```powershell
git commit -m "$(cat <<'EOF'
chore: reorganize project structure — 3 root folders

- orchestration/convs/done/   ← 9 DONE reports
- orchestration/convs/briefs/ ← 16 CONV briefs
- orchestration/graphify/     ← moved from graphify-out/
- orchestration/CHANGELOG.md  ← new feature timeline
- orchestration/logs/ACTIVITY.md ← new Claude action log
- legacy_code/ deleted (saved externally)
- CLAUDE.md paths updated

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Verify final structure**

```powershell
Get-ChildItem "C:\Users\germa\Documents\GitHub\mission-control" -Depth 0 | Select-Object Name
Get-ChildItem "C:\Users\germa\Documents\GitHub\mission-control\orchestration" -Depth 1 | Select-Object FullName
```

Expected root: only `backend/`, `frontend/`, `data/`, `orchestration/`, `.claude/`, and root files.
Expected orchestration: `PLAN.md`, `CHANGELOG.md`, `convs/`, `convs/done/`, `convs/briefs/`, `logs/`, `graphify/`.

---

## Self-Review

**Spec coverage:**
- ✅ 3 dossiers racine : backend, frontend, orchestration
- ✅ Tout ce qui touche au suivi projet (graphify, CONV, logs) dans orchestration
- ✅ legacy_code supprimé
- ✅ Traces de toutes les modifications (CHANGELOG + ACTIVITY)
- ✅ Paths CLAUDE.md mis à jour pour graphify
- ✅ PLAN.md mis à jour pour refléter la nouvelle structure

**Placeholders:** Aucun — tous les chemins et commandes sont exacts.

**Type consistency:** Pas de code, pas de types — seulement des paths et commandes shell.

**Gaps:** Aucun gap identifié. Le `settings.local.json` à la racine est un fichier Claude Code — ne pas déplacer.
