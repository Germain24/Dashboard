# Marge de crédit — simplification du moteur (design)

Date : 2026-07-06
Statut : à faire
Remplace : `orchestration/finis/2026-07-05-marge-credit-design.md` (moteur catalogue/institutions, jugé peu réaliste à l'usage — cf. retour utilisateur du 2026-07-06)

## Contexte

La première version du module "Marge de crédit" (catalogue statique de produits bancaires canadiens + règles d'éligibilité par ancienneté/revenu) produisait des recommandations jugées irréalistes par l'utilisateur : montants de départ inventés, banques suggérées sans rapport avec sa situation réelle (il n'a qu'un compte Desjardins, 700 CAD de marge, depuis septembre 2025). L'utilisateur préfère un modèle où **lui-même** définit les règles de progression (à quel score demander quoi, pour combien), plutôt qu'un catalogue figé.

Point clé confirmé par l'utilisateur : les actions futures (hausse de limite ou nouvelle carte) sont déclenchées par des **seuils de cote de crédit**, pas par le temps écoulé — et chaque action fait temporairement baisser le score (enquête de crédit / nouveau compte).

## Objectif

Remplacer le moteur catalogue/institutions par un modèle plus simple :
1. L'utilisateur garde le suivi de ses comptes réels (institution, produit, limite, statut) — la marge actuelle = somme des comptes actifs.
2. L'utilisateur garde l'historique réel de son score de crédit (déjà existant).
3. L'utilisateur définit lui-même une liste ordonnée de règles "à partir du score X, fais l'action Y (hausse ou nouvelle carte), montant estimé Z".
4. Le système déduit automatiquement le rythme de progression du score à partir de l'historique réel (pente entre 2 points ou plus), simule mois par mois l'évolution du score et de la marge totale jusqu'à la date cible, en appliquant les règles dès que le score projeté franchit leur seuil, et en faisant baisser le score de 10 points à chaque action déclenchée.
5. Deux graphiques : cote de crédit dans le temps, marge de crédit dans le temps — chacun avec les points réels et la portion projetée.

## Ce qui est supprimé

- `backend/app/services/finance/credit/catalog.py` (et son test `test_credit_catalog.py`) — catalogue de banques canadiennes, plus utilisé.
- Les champs `CreditProfile.revenu_annuel` et `CreditProfile.date_arrivee_canada` — n'ont plus d'usage dans le nouveau moteur (l'éligibilité n'est plus basée sur le revenu ni l'ancienneté au Canada).
- L'ancien `planner.py` (logique de correspondance catalogue/comptes, cooldowns d'ancienneté, anti-inquiry par calendrier) — remplacé par le nouveau moteur ci-dessous.
- `RoadmapSection` et `ProfileForm` (champs revenu/arrivée) dans `CreditTab.tsx` — remplacés par les nouvelles sections décrites plus bas.

## Ce qui reste inchangé

- `CreditAccount` (institution, produit, limite_actuelle, date_ouverture, derniere_augmentation, statut, notes) — table et CRUD inchangés.
- `CreditScoreEntry` (date, score, source) — table et CRUD inchangés, c'est la source de vérité pour la pente de progression du score.
- `CreditProfile.date_cible` — conservé (horizon de simulation).

## Nouveau modèle de données

### `CreditActionRule` (nouvelle table)
- `id`, `seuil_score: int` (score à partir duquel l'action devient déclenchable)
- `type: Literal["hausse", "nouvelle_carte"]`
- `montant_estime: float` (delta de marge appliqué quand la règle se déclenche)

CRUD simple (liste/ajout/suppression), triée par `seuil_score` croissant à l'affichage et dans le moteur — pas besoin d'un champ d'ordre séparé, le tri par seuil suffit à définir la séquence.

### `CreditProfile` (simplifié)
- `id`, `date_cible: date`, `nom: str | None` — `revenu_annuel` et `date_arrivee_canada` retirés (migration de suppression de colonnes).

## Nouveau moteur (`planner.py`, réécrit)

Constante : `SCORE_IMPACT_PAR_ACTION = 10` (points perdus après chaque hausse ou nouvelle carte déclenchée).

```python
def build_plan(accounts, score_history, rules, date_cible, today) -> dict
```

1. `marge_actuelle` = somme des `limite_actuelle` des comptes `statut == "actif"`.
2. Si `score_history` contient moins de 2 points : pas de projection possible. Retourne seulement les séries réelles (score_history tel quel, un seul point de marge = `marge_actuelle` à aujourd'hui), `projection_possible: false`, `actions: []`.
3. Sinon : pente mensuelle = `(dernier_score - premier_score) / mois_entre(première_date, dernière_date)` (régression sur 2 points extrêmes — simple et suffisant, pas de régression linéaire multi-points pour l'instant).
4. Simulation mois par mois de `today` à `date_cible` :
   - `score += pente` à chaque mois.
   - Tant qu'il existe une règle non consommée avec `seuil_score <= score` (dans l'ordre croissant des seuils) : consommer la règle (`marge += montant_estime`, `score -= SCORE_IMPACT_PAR_ACTION`), enregistrer une action `{date, type, seuil_score, montant_estime}`.
   - Enregistrer le point `{date, score, marge_totale}` de la série projetée.
5. Retourne :
   - `historique_score`: les points réels de `CreditScoreEntry` (date, score)
   - `historique_marge`: un seul point réel `{date: today, marge_totale: marge_actuelle}` (pas d'historique de marge saisi séparément — la marge réelle actuelle vient des comptes)
   - `projection_score`: série projetée `{date, score}` (vide si `projection_possible` est faux)
   - `projection_marge`: série projetée `{date, marge_totale}` (idem)
   - `actions`: liste des actions déclenchées dans la simulation, datées
   - `projection_possible: bool`

Pas de persistance : recalculé à chaque `GET /finance/credit/plan`, comme avant.

## API (`backend/app/api/finance/credit.py`, ajustée)

- CRUD `CreditActionRule` : `GET/POST /credit/rules`, `DELETE /credit/rules/{id}` (pas de PATCH — une règle mal définie se supprime et se recrée, plus simple).
- `CreditProfilePatch` perd `revenu_annuel`/`date_arrivee_canada`.
- `GET /credit/plan` retourne la nouvelle forme de réponse ci-dessus (remplace l'ancienne `marge_actuelle`/`marge_projetee_a_date_cible`/`actions`/`projection`).
- Les routes `accounts`/`scores` sont inchangées.

## Frontend

`CreditTab.tsx` réorganisé :
1. **Profil** : uniquement la date cible (le formulaire revenu/arrivée disparaît).
2. **Mes comptes** — inchangé.
3. **Historique de pointage** — inchangé.
4. **Règles de seuils** (nouveau) : liste éditable (seuil de score, type, montant estimé) + formulaire d'ajout, triée par seuil croissant à l'affichage.
5. **Graphique cote de crédit** : historique réel (points de `CreditScoreEntry`) + portion projetée en pointillé ou couleur distincte (même idiome SVG inline que l'existant) ; si `projection_possible` est faux, afficher seulement les points réels avec un message "ajoute au moins 2 points de score pour voir la projection".
6. **Graphique marge de crédit** : point réel actuel + portion projetée, même traitement.
7. **Prochaines actions prévues** : liste compacte des actions de la simulation (date, type, seuil, montant), sous les graphiques.

## Migration

Une migration Alembic supplémentaire : `create_table CreditActionRule` + `drop_column revenu_annuel`/`drop_column date_arrivee_canada` sur `credit_profile` (SQLite nécessite `batch_alter_table` pour un drop de colonne — cf. convention Alembic déjà utilisée ailleurs dans ce repo si un précédent existe, sinon batch mode standard).

## Tests

- `planner.py` (nouveau) : tests purs sur le nouveau `build_plan` — pente à 2 points, déclenchement de règle unique, déclenchement de plusieurs règles le même mois (croissance rapide), aucune règle définie, moins de 2 points de score (pas de projection), comptes fermés exclus de `marge_actuelle`.
- `service.py`/API : CRUD des règles, `compute_plan` reflète les champs simplifiés de `CreditProfile`.
- Suppression des tests de l'ancien catalogue (`test_credit_catalog.py`) et des tests du planner v1 devenus obsolètes (remplacés par les nouveaux).

## Hors scope

- Toute API de bureau de crédit réelle (déjà exclu dans la v1, toujours exclu).
- Régression multi-points sophistiquée pour la pente du score (2 points extrêmes suffisent pour l'instant).
- Limite du nombre de hausses par compte avant d'exiger une nouvelle carte — c'est à l'utilisateur de construire sa liste de règles en conséquence, le moteur ne l'impose pas.
