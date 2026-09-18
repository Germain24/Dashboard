# Design — Finance « tout automatique » piloté par les transactions (+ taxes)

> Date : 2026-06-03
> Statut : validé (brainstorming), en attente de relecture avant plan
> Branche prévue : `feat/finance-auto`

## 1. Objectif

L'utilisateur ne saisit que ses **mouvements** (ajout de cash, achats, ventes, dividendes,
frais). Tout le reste — **allocation actuelle, cash, plus-value latente et réalisée,
dividendes, taxes estimées** — est **dérivé automatiquement** des transactions, sans
étape manuelle (plus de « rebuild » à déclencher).

### Décisions de cadrage (validées)
- **Source de vérité unique** : la table `Transaction`.
- **Cash** : nouveaux types de transaction `depot` / `retrait` (et `frais`). Pas de
  nouveau champ : convention `ticker="CASH"`, `prix_unitaire`=montant, `quantite`=1.
- **Taxes** : **taux effectif configurable** — `taux_plus_value_pct` et
  `taux_dividende_pct` (pas de règle juridictionnelle figée).
- **Coût** : coût moyen pondéré (ACB) — cohérent avec le `pmu` existant et le régime
  canadien.
- **Cash négatif** : autorisé mais affiché en négatif (pas de blocage).
- **Approche** : C — fonction de dérivation unique + cache invalidé à l'écriture.

## 2. Modèle de données

- **`Transaction`** : inchangé (le champ `type` est une chaîne libre). Types gérés :
  `achat`, `vente`, `dividende`, `depot`, `retrait`, `frais`.
  - Mouvements cash (`depot`/`retrait`/`frais`) : `ticker="CASH"`, `prix_unitaire`=montant,
    `quantite`=1, `broker` renseigné.
- **`FinanceSettings`** (nouvelle table mono-ligne) : `id`, `taux_plus_value_pct` (float,
  défaut 25), `taux_dividende_pct` (float, défaut 15), `devise_affichage` (str, défaut "EUR"),
  `updated_at`. Migration Alembic + seed d'une ligne par défaut.
- **`Position`** : conservée comme **cache dérivé** (reconstruite par la dérivation ou
  calculée à la volée), plus comme source.

## 3. Fonction de dérivation (cœur, pure)

`compute_portfolio_state(transactions, prix, taxe) -> dict` — sans DB ni réseau.

Parcours chronologique, agrégation par `(ticker, broker)` :
- `achat` : `qte += q` ; `cout += q*pu + frais` ; `cash[broker] -= q*pu + frais`
- `vente` : `acb = cout/qte` ; `realise += (pu - acb)*q` ; `cout -= acb*q` ; `qte -= q` ;
  `cash[broker] += q*pu - frais`
- `dividende` : `cash[broker] += montant` ; `dividendes += montant`
- `depot` : `cash[broker] += montant`
- `retrait` : `cash[broker] -= montant`
- `frais` (seul) : `cash[broker] -= montant`

Sorties (`PortfolioState`) :
- `positions` : liste `{ticker, broker, quantite, acb, prix, valeur, pl_latent, pl_pct, poids_pct}`
  (qte > 0, valorisée au cours `prix`).
- `cash_par_broker` : `{broker: montant}` ; `cash_total`.
- `investi_net` : Σ(`depot`) − Σ(`retrait`).
- `valeur_totale` : Σ valeur positions + `cash_total`.
- `pl_realise` : Σ des ventes ; `pl_latent_total` : Σ des positions.
- `dividendes_total`.
- `allocation` : poids % de chaque position **et du cash** sur `valeur_totale`.
- `taxes` : `{ base_pv: max(0, pl_realise), impot_pv, base_div: dividendes_total,
  impot_div, total }` selon les taux configurés.

## 4. Invalidation + endpoints

- **Cache** de l'état (TTLCache `app/core/cache.py`) **invalidé** dans le service
  transactions à chaque `create` / `update` / `delete`. Lecture = état caché.
- Endpoints :
  - `GET /finance/state` — état dérivé complet.
  - `GET /finance/cash` — cash par broker + total.
  - `GET /finance/tax` — détail des taxes estimées.
  - `GET /finance/settings` / `PATCH /finance/settings` — taux de taxe + devise.
  - `POST /finance/transactions` (existant) : accepte aussi `depot`/`retrait`/`frais`.
  - `get_positions` repointé sur l'état dérivé (cohérence).

## 5. Frontend

- **Formulaire transactions** : types `dépôt`, `retrait`, `frais` en plus de achat/vente/dividende
  (pour cash : un seul champ « montant »).
- **Cash** : affichage par broker + total (CompositionTab / SuiviTab).
- **Allocation** : inclut le cash.
- **P&L** : réalisé vs latent.
- **Taxes** : mini-section (réalisé, impôt PV estimé, impôt dividendes estimé, total) +
  édition des taux (`/finance/settings`).

## 6. Tests

- **`compute_portfolio_state`** (pur) : ACB après plusieurs achats ; plus-value réalisée
  sur vente partielle/totale ; cash après dépôt/achat/vente/dividende/frais ; allocation
  cash inclus ; taxes selon taux ; portefeuille vide.
- **Intégration** : POST transactions (dépôt, achat, vente) → `GET /finance/state` reflète
  positions/cash/réalisé/taxes ; invalidation du cache après écriture.
- **Settings** : PATCH taux → `/finance/tax` recalcule.

## 7. Découpage (phases livrables)

1. `compute_portfolio_state` (pur) + tests.
2. Types cash (`depot`/`retrait`/`frais`) + `GET /finance/state` + `GET /finance/cash` +
   invalidation du cache à l'écriture.
3. `FinanceSettings` (modèle + migration + seed) + `GET|PATCH /finance/settings` +
   `GET /finance/tax`.
4. Frontend : types de transaction cash, affichage cash, P&L réalisé/latent, section taxes.

## 8. Risques / notes

- L'estimation de taxe est **indicative** (taux effectif), pas un calcul fiscal officiel —
  à afficher comme tel.
- Les frais peuvent être inclus dans une ligne achat/vente (`frais`) ou en transaction
  `frais` autonome ; la dérivation gère les deux.
- `investi` actuel vient des snapshots/Excel ; avec les dépôts, `investi_net` devient
  dérivé. On garde la rétro-compatibilité (snapshots inchangés).
