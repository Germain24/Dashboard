# Mission Control — Améliorations vers une application de niveau professionnel

> Généré le 2026-07-02. Audit ancré sur l'état réel du code (Next.js 15 App Router +
> FastAPI/SQLModel, 29 segments de route, design system « Verre Clair » dans DESIGN.md).
> Complète `orchestration/AMELIORATIONS_200.txt` (vue item par item) par une vue
> thématique : **élever l'app existante**, sans reconstruction ni mock data sur les
> modules qui ont déjà de vraies données.
>
> Contraintes non négociables : pas d'IA conversationnelle ni d'aides vocales dans le
> dashboard ; l'arborescence est synchronisée avec graphify (l'utilisateur gère la sync) ;
> les données réelles (Desjardins, nutrition, Buffett, garde-robe) restent la source de
> vérité — les mock data ne servent qu'aux intégrations pas encore branchées.

Légende : [S] petit · [M] moyen · [L] gros — (\*) confort · (\*\*) valeur réelle · (\*\*\*) structurant

---

## 1. Fluidité de navigation — tuer l'effet « PowerPoint » (P0)

Constat : `src/app/template.tsx` remonte un `<div class="page-transition">` à chaque
navigation et rejoue un `fadeIn` CSS de 300 ms. Aucune animation de sortie, aucune
continuité entre pages : chaque navigation « clignote ». `motion` v12 est déjà dans
`package.json` mais n'est importé que dans 8 fichiers (deck, journal).

1.1 [M](\*\*\*) Remplacer le `fadeIn` du template par des transitions **directionnelles et
    continues** pilotées par `motion/react` : un `PageTransition` client qui anime
    opacité + translation Y légère (8–12 px) avec un spring doux, et n'anime **pas**
    lors des navigations intra-module (changement d'onglet, query params).
    ← FINIS ✓ (2026-07-02) PageTransition keyée module, opacité seule (contrainte fixed)
1.2 [M](\*\*\*) Étudier la **View Transitions API** (supportée par Next 15 via
    `experimental.viewTransition`) pour les éléments partagés : titre de module,
    stat-cards du hub → page détail. Fallback automatique = comportement actuel.
1.3 [S](\*\*) Étendre `.stagger` (limité à 6 enfants en CSS nth-child) par un vrai
    stagger déclaratif `motion` (`staggerChildren`) sur les grilles de cartes.
    ← FINIS ✓ (2026-07-03) 8 usages CSS migrés StaggerGroup/Item, bloc .stagger supprimé de globals.css
1.4 [S](\*\*) Harmoniser les courbes : une seule source de vérité pour les easings/springs
    (tokens `--ease-*` de globals.css ↔ constantes `motion` partagées dans `lib/motion.ts`).
    ← FINIS ✓ (2026-07-02) lib/motion/tokens.ts seule source ; MotionConfig reducedMotion global
1.5 [S](\*\*\*) Conserver strictement le respect de `prefers-reduced-motion` (déjà en
    place côté CSS) dans toutes les nouvelles animations (`useReducedMotion`).
1.6 [M](\*\*) Micro-interactions systématiques sur les primitives `components/ui/` :
    press-scale des boutons, élévation douce des cards au survol, apparition
    spring des dialogs, entrée/sortie des toasts sonner alignées sur les tokens.
    ← PARTIEL (2026-07-02) dialog spring+sortie, tabs pastille layoutId, StatCard count-up
    (boutons/cards avaient déjà press-scale et hover ; toasts sonner restants)
    ; header jamais masqué pendant chargement (Sante/Garderobe) (2026-07-03)
1.7 [S](\*\*) Navigation Dock/Sidebar : indicateur actif animé (layoutId partagé) au
    lieu d'un changement d'état sec.
    ← FINIS ✓ (2026-07-04) pastille motion layoutId sidebar-nav-pill (recette .nav-active),
    springs.soft ; le Dock n'a qu'un seul lien de nav (Accueil), rien à animer
1.8 [M](\*\*) Transitions de données : lorsqu'une requête TanStack revalide, animer les
    deltas de valeurs (compteurs, barres) plutôt que remplacer brutalement.

## 2. Design « quiet luxury » — combler l'écart avec Verre Clair (P1)

Constat : DESIGN.md définit déjà l'ambition exacte demandée (« old money almanac,
behind clear glass » : papier crème, encre marine, laiton). L'audit porte sur
l'application **inégale** de ce système à travers les 29 modules.

2.1 [M](\*\*\*) Passe de conformité module par module : typographie display (Libre
    Caslon) réservée aux titres, palette restreinte (navy = seule voix interactive),
    espacements 4/8/16/24 — corriger les écarts hérités des différents chantiers.
    ← FINIS ✓ (2026-07-03) passe par lots de catégorie, garde conformity.test.ts (0 hex hors lib/design/colors.ts)
2.2 [M](\*\*) **Backgrounds structurés et sobres** : texture papier très subtile (grain
    SVG inline < 2 Ko, opacité ≤ 3 %), dégradé marin discret derrière le hub,
    variation par module via une teinte d'accent unique — jamais de gradients criards.
    ← FINIS ✓ (2026-07-03) grain SVG + lavis d'accent par module (--wash-module)
2.3 [S](\*\*) Verre translucide cohérent : un seul recipe `backdrop-blur` (chrome du
    Dock, dialogs, headers sticky) avec bordure et ombre unifiées.
    ← FINIS ✓ (2026-07-03) recettes .glass-card/.glass-veil/.glass-inset + garde CI
2.4 [M](\*\*) Mode sombre « minuit marine + laiton » : vérifier contraste AA et
    cohérence des 15 primitives ui/ dans les deux thèmes.
    ← FINIS ✓ (2026-07-03) contraste AA testé (contrast-tokens.test.ts, 2 thèmes)
2.5 [S](\*\*) États vides (`empty-state.tsx`) : illustration/typographie éditoriale au
    lieu de texte brut — un état vide premium est ce qui distingue une app finie.
    ← FINIS ✓ (2026-07-03) EmptyState serif italique + ornement laiton
2.6 [S](\*) Densité : hiérarchiser les pages très denses (finance, santé) avec des
    sections repliables et un rythme vertical constant.
    ← FINIS ✓ (2026-07-03) CollapsibleSection (ui/) sur finance + santé
2.7 [S](\*\*) Skeletons (`loading.tsx` par segment) calqués sur la géométrie réelle des
    pages pour éliminer les layout shifts au chargement.
    ← FINIS ✓ (2026-07-03) blocs composables + 6 loading.tsx sur mesure

## 3. Architecture & rangement — consolidation sans casse (P1/P3)

Constat : la séparation demandée existe déjà (`frontend/`, `backend/`, `data/`,
`docs/`, `orchestration/`, `tools/`). Les écarts sont des résidus, pas une refonte.

3.1 [S](\*\*) **Consolidation documentation** : réalisé autrement le 2026-07-02
    (choix user) — tous les specs/plans regroupés dans `orchestration/` classés par
    avancement (`a-faire/`, `en-cours/`, `finis/`), convention dans
    `orchestration/README.md` ; `docs/` supprimé. ← FINIS ✓ (2026-07-02)
    Résidu : `README.md`/`ARCHITECTURE.md`/`DESIGN.md`/`PRODUCT.md` restent à la
    racine ; ajouter des liens de renvoi vers `orchestration/README.md`.
3.2 [S](\*) Nettoyage racine : `pytest_out.txt`, `pytest_full.txt` → supprimés et
    gitignorés ; `entities.json`, `mempalace.yaml` → `orchestration/` si rien ne les
    référence à la racine (à vérifier avant déplacement).
3.3 [S](\*) Clarifier `src/mission_control/` (package Python quasi vide à la racine) :
    le documenter ou le retirer s'il n'est plus consommé.
3.4 [L](\*\*) *(P3, risqué)* Unifier le frontend sous `frontend/src/` (`components/` et
    `lib/` vivent aujourd'hui hors de `src/`). Gros renommage → à faire seul dans un
    commit dédié, avec mise à jour des tsconfig paths, puis sync graphify par
    l'utilisateur. Ne pas mélanger avec du travail UI.
3.5 [S](\*\*) La logique métier est déjà isolée côté backend (api/services/repositories) ;
    côté front, poursuivre la règle : **aucun calcul métier dans les composants**,
    tout dans `lib/` ou dérivé de l'API (déjà largement respecté, à auditer par module).

## 4. Performance (P1)

4.1 [S](\*\*) Import dynamique (`next/dynamic`, `ssr: false`) pour Leaflet et les
    composants lourds du deck — vérifier qu'aucun n'atterrit dans le bundle commun.
4.2 [S](\*\*) `@next/bundle-analyzer` en script `analyze` + budget de taille par route ;
    traquer les barrels `index.ts` qui importent tout un module.
4.3 [S](\*\*) Fonts via `next/font` (Libre Caslon Text, Public Sans, JetBrains Mono)
    si ce n'est pas déjà le cas — zéro FOUT, zéro requête externe.
4.4 [S](\*) Images (pixel art garde-robe, couvertures livres) : `next/image` +
    dimensions explicites partout.
4.5 [M](\*\*) Prefetch ciblé : conserver le prefetch des liens visibles, précharger les
    requêtes TanStack du module au survol du Dock (`queryClient.prefetchQuery`).
4.6 [S](\*) Audit Lighthouse (desktop + Android) documenté dans `docs/` avec les
    3 métriques suivies : LCP, INP, CLS.

## 5. Modules « automatisation de vie » — enrichir l'existant (P2)

> Tous les modules demandés existent déjà avec de vraies données. Les mock data ne
> sont introduites **que** pour les intégrations non branchées, sous forme de
> fixtures de test + adaptateurs prêts à recevoir le vrai flux.

### 5.1 Dashboard quantitatif & Finance
- [M](\*\*\*) Métriques quantitatives calculées sur le ledger réel : Sharpe, Sortino,
  volatilité annualisée, max drawdown, exposition par secteur (le TWR et le HHI
  existent déjà dans `services/finance/`).
- [M](\*\*) Adaptateur d'ingestion **OpenBB** : interface `MarketDataProvider` avec
  implémentation yfinance actuelle + implémentation OpenBB derrière un flag ;
  fixtures mock pour les tests uniquement.
- [S](\*) Volumes quotidiens et mini-sparklines sur les positions du portefeuille.

### 5.2 Performance & Physiologie
- [S](\*\*) Le tracker macros dérive déjà ses cibles de l'optimiseur nutrition
  (profil réel ~57 kg) — vérifier que la liste d'épicerie consomme bien
  `calculate_daily_targets` (dette connue : cibles encore codées en dur).
- [M](\*\*) Ingestion d'exports **Strava/GPX/TCX** : parseur + table `SeanceImportee`,
  fixtures d'exemple calibrées (57 kg) pour les tests ; l'UI entraînement existante
  affiche les séances importées à côté du mésocycle.
- [S](\*) Corrélations simples score/sommeil/nutrition sur la page `/score` existante.

### 5.3 Knowledge & Library
- [M](\*\*) Enrichir `livres/` : statuts (en cours/terminé/pile à lire), progression,
  notes de lecture ; support séries/mangas (tomes) à côté des essais.
- [S](\*) Si la base est vide au premier lancement : seed d'exemple optionnel
  (Housel, Lynch, une série manga) clairement marqué « exemple », jamais mélangé
  aux vraies entrées.

### 5.4 Logistique & Planification
- [S](\*\*) Voyage : la carte Leaflet vient d'être livrée — checklist par voyage et
  budget par étape comme prochains incréments.
- [M](\*\*) Garde-robe : conseils d'achat combinatoires + enrichissement BonneGueule
  livrés (plans dans `orchestration/finis/`). ← FINIS ✓ (2026-07-01)
  Module garde-robe complet, plus rien en attente.
- [S](\*) Objectifs long-terme : jalons datés + lien vers les modules concernés
  (un objectif « épargne X $ » pointe vers patrimoine).

## 6. Qualité & DX (P2)

6.1 [S](\*\*) CI : passer le lint d'advisory à bloquant, règle par règle (la dette est
    déjà suivie séparément).
6.2 [S](\*\*) Étendre les snapshots visuels Playwright aux états animés stabilisés
    (attendre la fin des transitions avant capture).
6.3 [S](\*) `gen:types` vérifié en CI (diff vide entre OpenAPI et `lib/types.ts`).
6.4 [S](\*) Un `docs/CONTRIBUTING.md` court : conventions commits, TDD, workflow
    AMELIORATIONS, sync graphify.

---

## Ordre d'exécution proposé

| Phase | Contenu | Pourquoi d'abord |
|-------|---------|------------------|
| **P0** | §1 transitions & micro-interactions (1.1 → 1.8) | C'est le reproche principal (« effet PowerPoint ») ; impact perçu maximal, risque faible |
| **P1** | §2 conformité Verre Clair + backgrounds, §4 perfs, 3.1–3.3 rangement docs | Rendu « premium » cohérent une fois la navigation fluide |
| **P2** | §5 enrichissements modules, §6 qualité | Valeur métier, s'appuie sur les fondations polies |
| **P3** | 3.4 unification `frontend/src/` | Risqué et invasif : seul, en dernier, commit dédié |

Chaque item suit le workflow existant : TDD, un commit par item, marquage daté une
fois terminé.
