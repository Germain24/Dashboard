# Mission Control — Changelog

Historique chronologique de toutes les modifications majeures du projet.
Maintenu à chaque fin de conversation de développement.

---

## 2026-06-01 — CONV 8-15 : Implémentation complète + redesign

**Commits :** `dbb53e9` (backend) → `7e93592` (redesign) → `283a078` (CI)

**Backend (CONV 8-13) :**
- Module Budget : transactions, catégories, règles regex, enveloppes, import CSV Desjardins/RBC
- Module Habitudes : streaks, heatmap, 6 habitudes seedées, auto-cochage (Entraînement→Muscu/Course, Livres→Lecture)
- Module Livres : bibliothèque Kanban, notes Markdown, citations, sessions, ISBN via Open Library
- Module Cuisine : recettes, macros depuis aliments CONV3, meal plan glouton, shopping list → Budget
- Scheduler APScheduler : snapshot 22h, plan nutrition 6h30, backup minuit, météo
- Système de notifications (Notification, JobRun) avec widget frontend

**Frontend (redesign + nouvelles pages) :**
- Nouvelle sidebar Linear/Notion (240px fixe, groupée, active state)
- Pages : Budget (Mois/Transactions/Enveloppes), Habitudes (Checklist/Heatmap), Livres (Kanban), Cuisine (Recettes/Plan/Courses), Jobs
- CSS : `--sidebar` variable dark/light ajoutée

**Tests/CI :**
- 32 tests verts (fonctions pures, zéro mock DB)
- GitHub Actions CI : pytest + tsc --noEmit sur push/PR

---

## 2026-05-31 — Réorganisation structure projet

**Session :** Hors CONV numérotée
- Structure 3 dossiers racine établie : `backend/`, `frontend/`, `orchestration/`
- `graphify-out/` → `orchestration/graphify/`
- `legacy_code/` supprimé (sauvegardé ailleurs)
- `orchestration/convs/done/` — 9 rapports DONE
- `orchestration/convs/briefs/` — 16 briefs CONV
- `orchestration/logs/ACTIVITY.md` créé
- `CLAUDE.md` mis à jour (chemins graphify)
- `orchestration/PLAN.md` mis à jour (diagramme architecture)

---

## 2026-05-28 — CONV 4 : Module Finance

**Commit :** `81ed30c`
- Port complet du module Finance (suivi portefeuille, transactions CSV)
- Refactor `WarrenBuffetMensuel.py` → 13+ sous-modules < 200 lignes
- Tables : `buffett_run`, `buffett_run_result`, `snapshot_portefeuille`, `transaction`, `position`
- 40 tests verts (19 scoring pur Python + 21 API intégration)
- APScheduler stubbé (snapshot 22h, Buffett mensuel 3h 1er du mois)
- Ref : `orchestration/convs/done/CONV4_DONE.md`

---

## 2026-05-26 — CONV DESIGN : Design System

**Commits :** `cb87444`, `583a7cf`, `39d951e`, `59d158e`
- Design system complet : CSS variables, thème dark/light, densité compact
- 12 primitives UI dans `frontend/components/ui/`
- Migration de tous les modules existants vers le design system
- `frontend/DESIGN.md` = spec de référence contraignante pour toutes les CONV futures
- Ref : `orchestration/convs/done/CONV_DESIGN_DONE.md`

---

## 2026-05-26 — CONV 6 : Module Études

**Commit :** à faire (43 tests verts)
- Module Études from-scratch (aucun code Streamlit de référence)
- Tables : `cours`, `evaluation`, `session_etude`
- `Cours.note_finale` = source de vérité GPA
- Bridge Études → Agenda câblé (source/source_id)
- Ref : `orchestration/convs/done/CONV6_DONE.md`

---

## 2026-05-25 — CONV 5 : Module Agenda

**Commit :** `63fc207`
- Module Agenda avec récurrences virtuelles (non persistées, générées à la volée)
- Tables : `evenement` (étendu), `regle_recurrence`, `tache`
- Bridge inter-modules silencieux par défaut (try/except + fallback)
- Ref : `orchestration/convs/done/CONV5_DONE.md`

---

## 2026-05-20 — CONV 7 : Module Entraînement

**Commit inclus**
- Module Entraînement complet + import Garmin
- Tables : `seance`, `exercice`, `programme`, `programme_jour`, `set_serie`, `course_cardio`
- 148 tests verts
- Hook intensité Santé ↔ Entraînement (import in-process, pas HTTP)
- Ref : `orchestration/convs/done/CONV7_DONE.md`

---

## 2026-05-17 — CONV 3 : Module Santé / Nutrition

**Commit :** `ac38f21`
- Module Santé : mesures, plan nutrition, aliments, objectifs nutritionnels
- Tables : `mesure_sante`, `plan_nutrition`, `aliment`, `nutrition_goal`
- Ref : `orchestration/convs/done/CONV3_DONE.md`

---

## 2026-05-16 — CONV 2 : Module Garde-robe

**Commit :** à faire
- Module Garde-robe complet
- Tables : `vetement` (23 entrées), `tenue_history`
- Ref : `orchestration/convs/done/CONV2_DONE.md`

---

## 2026-05-14 — CONV 1 : Fondation

**Commit initial**
- Bootstrap monorepo FastAPI + Next.js + SQLite
- 17 tables créées, 4 098 lignes legacy importées
- `make dev` opérationnel, 11 pages routées
- Ref : `orchestration/convs/done/CONV1_DONE.md`

---

## Modules restants (non implémentés)

| # | Module | Brief |
|---|--------|-------|
| CONV 8 | Budget | `orchestration/convs/briefs/CONV8_budget.md` |
| CONV 9 | Cuisine | `orchestration/convs/briefs/CONV9_cuisine.md` |
| CONV 10 | Habitudes | `orchestration/convs/briefs/CONV10_habitudes.md` |
| CONV 11 | Livres | `orchestration/convs/briefs/CONV11_livres.md` |
| CONV 12 | Agent IA | `orchestration/convs/briefs/CONV12_agent_ia.md` |
| CONV 13 | Scheduler | `orchestration/convs/briefs/CONV13_scheduler.md` |
| CONV 14 | Auth / Tailscale | `orchestration/convs/briefs/CONV14_auth_acces_distant.md` |
| CONV 15 | Tests, CI, Docs | `orchestration/convs/briefs/CONV15_tests_ci_doc.md` |
