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
>
> **Découpé le 2026-07-04** par avancement (fichiers trop chargés) :
> - §1 (navigation, P0) + §2 (design Verre Clair, P1) + §4 (performance, P1) sont
>   100% terminés → `orchestration/finis/2026-07-04-improvements-p0-p1-navigation-design-perf.md`
> - §3 (rangement, ci-dessous) reste ici : encore un mélange fait/en attente.
> - §5 (enrichir les modules) + §6 (qualité & DX) n'ont pas commencé (P2) →
>   `orchestration/a-faire/ameliorations-p2-modules-qualite.md`

Légende : [S] petit · [M] moyen · [L] gros — (\*) confort · (\*\*) valeur réelle · (\*\*\*) structurant

---

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

---

## Ordre d'exécution proposé (historique)

| Phase | Contenu | Statut |
|-------|---------|--------|
| **P0** | §1 transitions & micro-interactions (1.1 → 1.8) | ✅ Terminé — `finis/2026-07-04-improvements-p0-p1-navigation-design-perf.md` |
| **P1** | §2 conformité Verre Clair + backgrounds, §4 perfs, 3.1–3.3 rangement docs | ✅ §2+§4 terminés (même fichier finis/) ; 3.1 fait, 3.2/3.3 restants ci-dessus |
| **P2** | §5 enrichissements modules, §6 qualité | Pas commencé — `a-faire/ameliorations-p2-modules-qualite.md` |
| **P3** | 3.4 unification `frontend/src/` | Pas commencé, risqué et invasif : seul, en dernier, commit dédié |

Chaque item suit le workflow existant : TDD, un commit par item, marquage daté une
fois terminé.
