# Frontend Mission Control

Le frontend est une application Next.js 15 (App Router), TypeScript et
Tailwind. La documentation générale du projet se trouve dans le
[`README.md`](../README.md) à la racine.

## Développement

Depuis la racine du dépôt :

```bash
make dev
```

Ou uniquement le frontend :

```bash
npm run dev --prefix frontend
```

Le serveur écoute sur <http://localhost:3000>. Les appels API passent par le
proxy Next.js ; le préfixe canonique du backend est `/api/v1`.

## Vérifications

```bash
npm test --prefix frontend
npx tsc --noEmit --project frontend/tsconfig.json
npm run build --prefix frontend
```
