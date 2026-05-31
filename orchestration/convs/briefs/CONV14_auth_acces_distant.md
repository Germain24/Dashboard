# CONV 14 — Auth & accès distant

## Objectif

Permettre à Germain d'accéder à Mission Control (dashboard + agent) depuis
l'extérieur de son PC (téléphone, autre laptop) de manière sécurisée.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**. Pas obligé que CONV 12 soit faite,
mais le design doit prévoir l'agent IA derrière la même barrière d'auth.

## État cible

- Backend FastAPI tourne sur `:8000`, frontend Next.js sur `:3000`.
- Aucune exposition publique sans auth.

## Décisions à prendre

1. **Stratégie exposition** :
   - Option A : **Tailscale** (VPN privé, gratuit pour 1 user, zéro friction)
   - Option B : Cloudflare Tunnel (URL publique HTTPS, gratuit, + auth applicative)
   - Option C : Nginx + DDNS + Let's Encrypt (full DIY)
   - Reco : **Tailscale** — fait pour ça, pas d'URL publique exposée.
2. **Auth applicative** :
   - Si Tailscale, l'auth réseau suffit. Optionnel : ajouter un PIN UI.
   - Si Cloudflare/public, obligatoire : Cloudflare Access (OIDC) ou
     login custom NextAuth.js.
3. **Single-user ou multi-user** : reco single-user (toi seul).
4. **Secrets management** : `.env` versionné `.env.example` + vrai `.env`
   gitignored, ou passer à un secret manager (1Password CLI, age) ?
5. **Niveau de paranoïa** : tu veux du 2FA même en VPN privé ?

## Architecture selon décision

### Si Tailscale (reco)

- Installer Tailscale sur PC + iOS/Android
- L'app reste accessible via `http://<machine>.<tailnet>:3000` partout
- Côté code : presque rien à faire, juste écouter sur `0.0.0.0` au lieu de
  `127.0.0.1`
- Doc `docs/access.md` : installation + dépannage

### Si Cloudflare Tunnel

- Installer `cloudflared` daemon sur PC
- Configurer un tunnel vers `localhost:3000` et `localhost:8000`
- Activer Cloudflare Access avec règle "Email = germain..."
- Middleware FastAPI pour valider le JWT Cloudflare Access

### Si Nginx + DDNS

- Reverse proxy Nginx en frontal
- Certificat Let's Encrypt via certbot
- NextAuth.js côté front, dépendance backend pour valider session
- Le plus de boulot, pas reco

## Sécurité applicative complémentaire

Indépendamment de la stratégie réseau :

- Tous les endpoints `/api/*` derrière dépendance FastAPI `get_current_user`
- Rate limiting basique sur `/api/agent/chat` (l'agent coûte de l'argent)
- HTTPS partout en prod (Tailscale = HTTPS via MagicDNS optionnel)
- Variables d'env : chargées via `pydantic-settings`, fail au boot si manquantes

## Hors-scope

- Multi-tenancy
- Audit logs détaillés (V2)
- Single Sign-On (overkill single-user)

## Dépendances

- Prérequis : CONV 1.
- Bénéficiaire : usage mobile + partage potentiel.

## Suggestions techniques

- Tailscale → install Windows ~ 5 min, install iOS ~ 2 min. ROI immédiat.
- Si tu changes de PC ou veux héberger en remote (VPS), Cloudflare Tunnel
  devient plus pertinent.
- Test depuis le téléphone *avant* de considérer la CONV terminée.

## Critères de succès

- [ ] Accès depuis le téléphone fonctionne, même hors WiFi maison
- [ ] Aucune URL publique sans auth
- [ ] Tous les secrets en variables d'env, jamais commités
- [ ] `docs/access.md` clair pour reconfigurer si changement de PC
- [ ] Le PIN/2FA (si choisi) fonctionne

---

## Prompt d'amorce

```
Je veux configurer l'auth et l'accès distant pour Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV14_auth_acces_distant.md

Pose-moi les 5 questions de "Décisions à prendre".
```
