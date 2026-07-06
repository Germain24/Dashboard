# Marge de crédit — feuille de route d'optimisation (design)

Date : 2026-07-05
Statut : à faire

## Contexte

L'utilisateur est arrivé au Canada en septembre 2025, avec un emploi à ~40 000 CAD/an depuis cette date. Il détient une seule carte de crédit (Desjardins, limite 700 CAD, ouverte septembre 2025). Objectif : maximiser la **marge de crédit totale disponible, toutes institutions confondues**, à l'horizon du 2026-10 (~2 ans 3 mois, date cible par défaut 2028-09-01, calée sur son anniversaire d'arrivée + 3 ans).

Pas d'accès réaliste à une vraie API de bureau de crédit (Equifax/TransUnion) ni d'agrégateur bancaire pour un particulier — confirmé avec l'utilisateur. Toutes les données (comptes, limites, pointage) sont saisies manuellement.

## Objectif du module

Une nouvelle page "Marge de crédit" qui, à partir de l'état réel saisi par l'utilisateur (comptes actuels, historique de pointage, profil), génère :
1. Une feuille de route chronologique d'actions recommandées ("demander augmentation chez X", "ouvrir un compte/carte chez Y") jusqu'à la date cible.
2. Une projection de la marge de crédit totale cumulée dans le temps.

Le moteur est un **advisor basé sur des règles + projection temporelle** (pas un solveur d'optimisation combinatoire, pas de simulation Monte-Carlo des probabilités d'approbation — jugé disproportionné vu l'incertitude réelle des politiques bancaires).

## Modèle de données (backend, SQLModel, même DB que `PatrimoineItem`)

### `CreditProfile` (ligne unique)
- `revenu_annuel: float`
- `date_arrivee_canada: date`
- `date_cible: date` (défaut 2028-09-01, éditable)
- `nom: str | None`

### `CreditAccount`
- `id`, `institution: str`, `produit: str` (ex. "Carte Mastercard", "Marge personnelle", "Carte garantie")
- `limite_actuelle: float`
- `date_ouverture: date`
- `derniere_augmentation: date | None`
- `statut: Literal["actif", "ferme"]`
- `notes: str | None`

### `CreditScoreEntry`
- `id`, `date: date`, `score: int`, `source: str` (ex. "Credit Karma", "Borrowell")

Toutes ces entités sont gérées via CRUD simple (ajout/édition/suppression) depuis l'UI — pas d'import automatique.

## Catalogue de règles ("playbook")

`backend/app/services/finance/credit/catalog.py` : liste statique de produits candidats par institution, avec pour chacun :
- `limite_depart_estimee` (fonction grossière du revenu, fourchette min/max)
- `anciennete_min_avant_1ere_hausse` (mois, ex. 6-12)
- `cooldown_entre_hausses` (mois)
- `score_min_requis` (None si produit "newcomer"/carte garantie sans exigence de pointage)
- `necessite_historique_canada` (bool)
- `type: Literal["carte_standard", "carte_garantie", "programme_newcomer", "marge_personnelle"]`

Catalogue de départ : grandes banques canadiennes (RBC, TD, Scotiabank — incl. programme StartRight, BMO, CIBC, Banque Nationale, Desjardins, Tangerine) + options credit-builder/cartes garanties (ex. Home Trust Secured, Refresh Financial). Valeurs = estimations heuristiques, clairement indiquées comme telles dans l'UI, et surchargeables sans redéploiement via `data/imports/Finances/variables/credit_catalog.json` (même convention que `params.json` du Buffett — cf. `backend/app/services/finance/buffett/config.py`).

## Moteur (`planner.py`)

Fonction pure :
```python
def build_plan(accounts, score_history, profile, catalog, today) -> Plan
```

Simule mois par mois de `today` à `profile.date_cible` :
- Un compte existant devient éligible à une demande d'augmentation après `anciennete_min_avant_1ere_hausse` (ou `cooldown_entre_hausses` depuis la dernière augmentation), si le pointage courant ≥ seuil du produit (si applicable).
- Un nouveau produit du catalogue devient candidat à l'ouverture si ses critères d'éligibilité (score, revenu, ancienneté au Canada) sont satisfaits à cette date.
- Contrainte anti-inquiries : au plus 1 nouvelle demande d'ouverture tous les N mois (paramètre configurable, défaut 3-4 mois) pour éviter d'empiler les enquêtes de crédit dures.
- Les actions candidates sont ordonnées par date de faisabilité puis par gain de limite estimé décroissant.
- Sortie : liste d'actions datées (type, institution/produit, delta de limite estimé, condition/justification) + série mensuelle de marge totale cumulée projetée.

Le pointage utilisé à une date donnée = dernière entrée de `CreditScoreEntry` connue à cette date (pas d'extrapolation/prédiction de la progression du score — on reste sur la dernière valeur saisie par l'utilisateur tant qu'il n'en ajoute pas de nouvelle).

Aucune persistance du plan calculé : recalculé à chaque requête `GET /plan` à partir de l'état courant. Pas de statut "fait/rejeté/reporté" sur les recommandations — l'utilisateur reflète la réalité en mettant à jour ses comptes/scores, et le plan se recalcule en conséquence.

## API (`backend/app/api/finance/credit.py`)

- CRUD `CreditProfile` (get/update, singleton)
- CRUD `CreditAccount` (list/create/update/delete)
- CRUD `CreditScoreEntry` (list/create/delete)
- `GET /plan` → feuille de route + projection (calcul synchrone à la volée, pas de BackgroundTask)

## Frontend

Nouveau module dans `frontend/lib/modules.ts` :
```ts
{
  slug: "credit",
  label: "Marge de crédit",
  description: "Feuille de route pour maximiser la marge de crédit totale.",
  icon: CreditCard,
  group: "Finances & Ingénierie",
  ready: true,
}
```

`frontend/src/app/credit/page.tsx` (`ModuleHeader` + `ErrorBoundary` + `CreditTab`), `frontend/components/finance/CreditTab.tsx` avec sections :
1. **Profil** — revenu, date d'arrivée, date cible (édition inline).
2. **Mes comptes** — table éditable (institution, produit, limite, date ouverture, statut).
3. **Historique de pointage** — liste + ajout (date, score, source).
4. **Feuille de route** — liste chronologique des actions recommandées, avec la justification (ancienneté suffisante, score requis atteint, etc.), clairement étiquetée comme estimation heuristique.
5. **Graphique** — marge totale cumulée projetée jusqu'à la date cible (courbe), avec repère sur la marge actuelle et sur le total projeté à la date cible.

## Tests

- `planner.py` : tests unitaires purs (pas de DB) sur des scénarios fixes — respect des cooldowns, filtrage par éligibilité, non-dépassement de la contrainte anti-inquiries, cas où le catalogue est vide, cas où l'utilisateur n'a aucune entrée de score.
- API : tests CRUD standards + test d'intégration `GET /plan` avec un jeu de données fixe.

## Hors scope

- Toute intégration API bancaire réelle (Plaid/Flinks) ou bureau de crédit (Equifax/TransUnion).
- Simulation probabiliste des taux d'approbation.
- Suivi automatique du statut des demandes (l'utilisateur met à jour manuellement).
