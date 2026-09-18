# Colonne Volume en euros (pipeline Buffett) — design

**Date** : 2026-07-15 · **Statut** : approuvé (conversion à l'ingestion)

## Problème

La colonne `Volume` (yfinance : nombre d'actions échangées/jour) circule **brute**
dans toute la pipeline Buffett : scoring → DB (`BuffettResult.volume`) →
ToutBroker.xlsx → dédup cross-listings → filtre de liquidité. Deux biais réels :

- **Dédup** (`dedup.py`) : « garder le plus gros volume » compare des nombres
  d'actions entre bourses/devises — un listing Tokyo à 1M actions × 500 ¥ (~3 M€)
  bat un listing NYSE à 200k actions × 150 $ (~28 M€).
- **Liquidité** (`liquidity.py`) : `is_liquid = volume × prix_local ≥ MIN_VOLUME_EUR`
  compare un montant en devise locale à un seuil en euros — un titre japonais
  à ~600 €/jour réels passe le filtre « 100 000 € ».

## Décision

La colonne garde le nom **`Volume`** mais contient désormais le **volume échangé
par jour en euros** = `volume_actions × prix_local × taux(devise → EUR)`.
Conversion **à l'ingestion** (une seule source de vérité) ; DB, ToutBroker,
dédup et liquidité consomment la valeur convertie sans changement de schéma.

## Changements

1. **Ingestion** — `scoring.extract_metrics` et `runner._etf_result` produisent
   `Volume` en EUR. Devise = `info["currency"]` ; repli : suffixe du ticker via
   la table `_SUFFIX_CCY` (à déplacer/partager depuis `dedup.py`), défaut USD.
   Pence `GBp`/`GBX` : prix ÷ 100 puis GBP.
2. **Liquidité** — `daily_eur_volume`/`is_liquid` ne multiplient plus par le
   prix : `is_liquid(volume_eur, min_eur=None)`. Appelants adaptés :
   `runner.py` (~l.540) et `api/finance/buffett.py` (~l.454).
3. **Dédup / DB / ToutBroker** — zéro changement de code : mêmes colonnes,
   valeur désormais en euros ; les comparaisons deviennent équitables
   entre devises.
4. **FX** — réutilise `fx.get_rate` (cache quotidien). Warm-up des paires de
   `_SUFFIX_CCY` (+ USD) au démarrage du run, AVANT que le garde
   `_analysis_running` ne bloque les fetchs. Taux introuvable → `Volume = 0`
   + warning (titre traité illiquide) — jamais de valeur brute silencieuse.
5. **Anciens runs** — pas de migration : les valeurs historiques restent en
   nombre d'actions ; la prochaine analyse écrit des euros. Une **reprise** de
   run interrompu d'avant le changement mélange les unités : accepté, warning
   au log.

## Hors périmètre

- `Prix` reste en devise locale (y compris pence) — seul `Volume` change.
- Pas de renommage de colonne ni de champ DB.

## Tests

- `test_liquidity.py` : nouvelle signature (volume déjà en €).
- Nouveaux tests conversion : EUR (identité), USD, GBp (pence), devise
  inconnue → repli suffixe, taux indisponible → 0.
- `test_dedup.py` : inchangé (les volumes y sont déjà des scalaires abstraits).
