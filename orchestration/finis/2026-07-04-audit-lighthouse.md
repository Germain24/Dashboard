# Audit Lighthouse — LCP / INP / CLS (2026-07-04)

Item 4.6 d'`orchestration/en-cours/improvements.md`. `docs/` n'existe plus
(cf. item 3.1, consolidation dans `orchestration/`) : ce rapport vit ici.

## Méthode

- Build de **production** réel (`next build && next start`, pas `next dev`)
  + backend FastAPI local, conditions représentatives d'un déploiement.
- Outil : `frontend/scripts/lighthouse-audit.mjs` (`lighthouse` + `chrome-launcher`
  + `puppeteer-core`, ajoutés en devDependencies). Réutilisable :
  `node scripts/lighthouse-audit.mjs [baseUrl]`.
- 2 routes : `/` (hub, la plus visitée) et `/finance` (page dense, cf. item 2.6).
- 2 profils : **mobile** (émulation Lighthouse par défaut : Moto G-like,
  CPU×4, réseau lent — sert de proxy Android) et **desktop** (`desktopConfig`,
  pas de throttling).
- LCP/CLS/TBT viennent d'un run **navigation** classique. Lighthouse ne calcule
  l'INP qu'en mode **timespan** (`interaction-to-next-paint` a
  `supportedModes: ['timespan']` dans le code de Lighthouse) : le script
  ouvre donc un timespan, déclenche une vraie interaction (tiroir de nav sur
  mobile, ThemeToggle sur desktop — Sidebar/Dock sont `hidden` sous `md:`),
  puis lit l'INP du flow.
- 3 exécutions par route/profil ; valeurs ci-dessous = médiane.

## Résultats (médiane de 3 runs)

| Route      | Profil  | LCP      | CLS  | TBT (proxy interactivité) | INP    |
|------------|---------|----------|------|---------------------------|--------|
| `/`        | mobile  | 4468 ms  | 0    | 1463 ms                   | n/a¹   |
| `/`        | desktop | 990 ms   | 0    | 109 ms                    | 141 ms |
| `/finance` | mobile  | 4626 ms  | 0    | 1357 ms                   | 441 ms |
| `/finance` | desktop | 1024 ms  | 0.1  | 67 ms                     | 237 ms |

Seuils Core Web Vitals : LCP bon <2,5 s / à améliorer <4 s / mauvais ≥4 s ·
CLS bon <0,1 / mauvais ≥0,25 · INP bon <200 ms / à améliorer <500 ms / mauvais ≥500 ms.

¹ INP non capturé sur `/` mobile dans les 3 runs (reproductible) : l'ouverture
du tiroir `MobileNav` ne produit pas d'événement que la métrique
`Responsiveness` de Lighthouse détecte comme interaction scorable. Limite de
l'outil en mode lab, pas une mesure de "0 ms" — à ignorer, pas à interpréter
comme bon.

## Lecture

- **Desktop : bon sur toute la ligne.** LCP <1,1 s, TBT <140 ms, INP ≤237 ms
  sur les deux routes. Aucune action requise.
- **Mobile : LCP et TBT en zone "mauvaise" de façon constante**, y compris sur
  le hub (page la plus simple). Le throttling CPU×4/réseau lent de
  l'émulation mobile amplifie mécaniquement l'écart, mais un TBT >1,3 s même
  sur le hub pointe vers un coût d'hydratation client important — cohérent
  avec l'architecture largement `'use client'` du dashboard (Sidebar, Dock,
  QueryProvider, MotionProvider, etc. s'hydratent tous dès le premier rendu).
- `/finance` desktop a un CLS de 0,1 (limite de la zone "bon"), stable sur
  les 3 runs — probablement un shift lié au chargement asynchrone d'une
  section (StatCard count-up, CollapsibleSection). Mineur, à surveiller si
  `/finance` gagne encore en densité.

## Pistes (hors scope de cet audit, à qualifier séparément si prioritaire)

- Le TBT mobile élevé suggère de revisiter le poids d'hydratation initial du
  shell (`MainShell`/`Sidebar`/`Dock`/`QueryProvider`) — au-delà de ce que
  4.1/4.2/4.5 (déjà traités) couvrent, ce serait un chantier dédié (React
  Server Components pour des blocs non interactifs, ou différer l'hydratation
  de widgets secondaires du Dock).
- Pas de budget de taille par route automatisé en CI (cf. note de clôture de
  l'item 4.2) : cet audit Lighthouse est manuel/à la demande, pas un garde-fou
  continu.
