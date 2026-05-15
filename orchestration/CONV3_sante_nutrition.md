# CONV 3 — Module Santé / Nutrition

## Objectif

Porter le module `sante/` (505 lignes) vers la nouvelle stack, **et étoffer**
pour soutenir l'objectif de prise de muscle : tracking de composition corporelle,
liaison avec le module Entraînement (CONV 7) pour ajustement dynamique des
macros selon la charge de séance.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**. Idéalement faite après CONV 7
pour exploiter le module Entraînement, mais peut aussi se faire avant avec
un placeholder.

## Code de référence

- `mon_espace/sante/logic.py` — 505 lignes : `calculate_daily_targets`,
  `optimize_nutrition` (scipy), `calculate_plan_totals`
- `mon_espace/sante/aliments.csv` — déjà importé en CONV 1
- `mon_espace/sante/sante.json` — déjà importé en CONV 1
- `mon_espace/Dashboard.py` lignes 935-1190 — UI Streamlit

## Décisions à prendre

1. **Objectif explicite** : poids cible ? Échéance ? Surplus calorique vise
   actuellement +500 kcal sport / +10 % repos — ces valeurs correspondent
   toujours à ton objectif prise de muscle ?
2. **Composition corporelle** : tu vas tracker quoi ? Poids, tour de taille,
   photos, % masse grasse (impédance / pli) ? À quelle fréquence ?
3. **Lien Entraînement** : on attend CONV 7 ou on prévoit le hook (champ
   `intensite_seance: low/medium/high/none`) saisi manuellement en attendant ?
4. **Budget nutrition** : on intègre dès maintenant un coût mensuel max, ou
   on attend le module Budget (CONV 8) ?
5. **Affichage** : conserver tout le détail micronutriments dans l'UI principal,
   ou expand-on-demand par défaut ?

## Fonctionnalités à porter + ajouter

### Backend

- `calculate_daily_targets(weight, date, history, training_intensity)` —
  porter + ajouter le paramètre intensité
- `optimize_nutrition(targets, budget_max=None)` — porter + ajouter contrainte
  budget optionnelle
- `calculate_plan_totals` — porter
- **Nouveau** : `BodyComposition` model + endpoints (mesures pondérées par
  jour, calcul tendance 7j / 30j)
- **Nouveau** : projection "Au rythme actuel, tu atteins X kg le Y" via
  régression linéaire sur les 30 derniers jours

### Endpoints

```
GET    /api/sante/mesures           # historique poids + composition
POST   /api/sante/mesures           # nouvelle mesure
GET    /api/sante/aliments          # catalogue
GET    /api/sante/targets/today     # objectifs du jour
POST   /api/sante/plan/generate     # optimiser plan du jour
GET    /api/sante/plan/today        # plan courant
PATCH  /api/sante/plan/today        # modifier (ajouter/retirer aliment)
GET    /api/sante/projection        # projection poids cible
```

### Frontend (`frontend/app/sante/`)

- Vue jour : objectifs + plan + totaux + barres de progression macros
- Vue tendance : graphique poids 90 jours avec ligne de tendance + projection
- Onglet composition : entrée poids + tour de taille + (optionnel) photos
- Détail micronutriments dans un drawer/dialog

## Hors-scope

- Reconnaissance d'aliments par photo
- Connexion Apple Health / Google Fit (V2)
- Modification de la base aliments par UI (édition CSV manuelle pour l'instant)

## Dépendances

- Prérequis : CONV 1.
- Idéal : CONV 7 (Entraînement) avant, pour avoir l'intensité réelle.

## Suggestions techniques

- Garder l'optimiseur scipy tel quel — il marche bien.
- Cacher les `daily_targets` 24h pour éviter de re-calculer à chaque requête.
- Pour la projection : `scipy.stats.linregress` sur les 30 derniers points.

## Critères de succès

- [ ] Historique poids importé et visible
- [ ] Saisie poids du jour → re-calcule + génère plan
- [ ] Plan optimisé respecte macros + budget si défini
- [ ] Projection de poids cible avec date estimée
- [ ] Tendance poids 7j et 30j affichées correctement

---

## Prompt d'amorce

```
Je veux porter et étoffer le module Santé/Nutrition de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV3_sante_nutrition.md
3. Logique de référence : C:\Users\germa\Documents\GitHub\openclaw\mon_espace\sante\logic.py

Pose-moi les 5 questions de "Décisions à prendre" avant d'attaquer.
```
