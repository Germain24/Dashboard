# Colonne Volume en euros — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La colonne `Volume` de la pipeline Buffett contient le volume échangé/jour **en euros** (nb actions × prix local × taux devise→EUR) au lieu du nombre brut d'actions.

**Architecture:** Conversion à l'ingestion (une seule source de vérité) dans `extract_metrics`/`_etf_result` via un nouveau module `currency.py` (détection de devise + conversion). `fx.get_rate` gagne un paramètre `force` pour le warm-up des paires au démarrage du run (le garde `_analysis_running` bloque sinon tout fetch pendant l'analyse). `liquidity.is_liquid` compare directement le Volume (déjà en €) au seuil. Dédup/DB/ToutBroker : aucun changement de code.

**Tech Stack:** Python 3.12, FastAPI, pytest (backend/, `uv run pytest`), yfinance.

**Spec:** `orchestration/a-faire/2026-07-15-volume-eur-design.md`

## Global Constraints

- La colonne/champ garde le nom `Volume` / `volume` partout (DB, ToutBroker.xlsx, dicts métriques) — seule l'unité change.
- `Prix` reste en devise locale (y compris pence) — hors périmètre.
- Taux introuvable → `Volume = 0.0` + message log ; jamais de valeur brute silencieuse.
- Pence : `info["currency"]` valant `"GBp"` (casse exacte) ou `"GBX"` (toute casse) → prix ÷ 100, devise GBP. Attention : `"GBp".upper() == "GBP"` — tester AVANT tout `.upper()`.
- Pas de migration des anciens runs en DB.
- Le dépôt contient beaucoup de modifications non commitées SANS rapport : `git add` UNIQUEMENT les fichiers listés dans la tâche, jamais `git add -A`.
- Tests backend : `cd backend && uv run pytest tests/test_finance/<fichier> -v` (Windows, chemins absolus si besoin : `C:\Users\germa\Documents\GitHub\mission-control\backend`).

---

### Task 1: Module `currency.py` — devise de cotation + volume en euros

**Files:**
- Create: `backend/app/services/finance/buffett/currency.py`
- Modify: `backend/app/services/finance/buffett/dedup.py:134-139` (table `_SUFFIX_CCY` remplacée par un import)
- Test: `backend/tests/test_finance/test_currency_volume.py`

**Interfaces:**
- Consumes: `app.services.finance.fx.get_rate(base, quote, ...) -> float` (existant).
- Produces: `SUFFIX_CCY: dict[str, str]` ; `infer_currency(ticker: str, info: dict | None) -> tuple[str, float]` (devise ISO, facteur prix — 0.01 pour les pence) ; `volume_eur(volume, prix, ticker: str = "", info: dict | None = None, *, rate_getter=None) -> float`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/test_finance/test_currency_volume.py` :

```python
"""Volume échangé/jour en euros : détection de devise + conversion (spec
orchestration/a-faire/2026-07-15-volume-eur-design.md)."""


def _fake_rate(base, quote, **kwargs):
    assert quote == "EUR"
    return {"USD": 0.9, "GBP": 1.15, "JPY": 0.006}.get(base, 0.0)


def test_infer_currency_prend_la_devise_yfinance_d_abord():
    from app.services.finance.buffett.currency import infer_currency
    assert infer_currency("AAPL", {"currency": "USD"}) == ("USD", 1.0)
    assert infer_currency("AIR.PA", {"currency": "EUR"}) == ("EUR", 1.0)


def test_infer_currency_pence_gbp_et_gbx():
    from app.services.finance.buffett.currency import infer_currency
    # "GBp" (casse yfinance exacte) = pence ; "GBP" = livres entières.
    assert infer_currency("HSBA.L", {"currency": "GBp"}) == ("GBP", 0.01)
    assert infer_currency("X.L", {"currency": "GBX"}) == ("GBP", 0.01)
    assert infer_currency("FUND.L", {"currency": "GBP"}) == ("GBP", 1.0)


def test_infer_currency_repli_suffixe_puis_usd():
    from app.services.finance.buffett.currency import infer_currency
    assert infer_currency("AIR.PA", {}) == ("EUR", 1.0)      # suffixe .PA
    assert infer_currency("7203.T", None) == ("JPY", 1.0)    # suffixe .T
    assert infer_currency("AAPL", None) == ("USD", 1.0)      # défaut


def test_volume_eur_identite_eur():
    from app.services.finance.buffett.currency import volume_eur
    assert volume_eur(1000, 10.0, "AIR.PA", {"currency": "EUR"},
                      rate_getter=_fake_rate) == 10_000.0


def test_volume_eur_conversion_usd():
    from app.services.finance.buffett.currency import volume_eur
    assert volume_eur(1000, 10.0, "AAPL", {"currency": "USD"},
                      rate_getter=_fake_rate) == 9_000.0


def test_volume_eur_pence():
    from app.services.finance.buffett.currency import volume_eur
    # 1000 actions x 250 pence = 2500 GBP x 1.15 = 2875 EUR
    assert volume_eur(1000, 250.0, "HSBA.L", {"currency": "GBp"},
                      rate_getter=_fake_rate) == 2_875.0


def test_volume_eur_taux_indisponible_donne_zero():
    from app.services.finance.buffett.currency import volume_eur
    assert volume_eur(1000, 10.0, "005930.KS", {"currency": "KRW"},
                      rate_getter=_fake_rate) == 0.0


def test_volume_eur_donnees_manquantes():
    from app.services.finance.buffett.currency import volume_eur
    assert volume_eur(None, 10.0, rate_getter=_fake_rate) == 0.0
    assert volume_eur(1000, None, rate_getter=_fake_rate) == 0.0
    assert volume_eur("n/a", 10.0, rate_getter=_fake_rate) == 0.0


def test_dedup_reutilise_la_table_suffixe():
    # La table vit dans currency.py ; dedup ne doit plus avoir sa copie.
    from app.services.finance.buffett import currency, dedup
    assert dedup._SUFFIX_CCY is currency.SUFFIX_CCY
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_finance/test_currency_volume.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.finance.buffett.currency'`

- [ ] **Step 3: Implémenter `currency.py`**

Créer `backend/app/services/finance/buffett/currency.py` :

```python
"""Devise de cotation et volume échangé/jour en euros.

La colonne ``Volume`` de la pipeline Buffett contient le volume échangé par
jour EN EUROS (= nb d'actions x prix local x taux devise->EUR), pas le nombre
brut d'actions : comparer des nombres d'actions entre bourses (dédup) ou les
confronter à un seuil en euros (liquidité) n'a aucun sens entre devises.
Spec : orchestration/a-faire/2026-07-15-volume-eur-design.md.
"""

from __future__ import annotations

from app.services.finance import fx

# Suffixe Yahoo -> devise de cotation (source unique, aussi utilisée par
# dedup._ticker_currency).
SUFFIX_CCY = {
    "L": "GBP", "PA": "EUR", "DE": "EUR", "AS": "EUR", "MI": "EUR", "MC": "EUR",
    "BR": "EUR", "LS": "EUR", "VI": "EUR", "HE": "EUR", "IR": "EUR",
    "HK": "HKD", "KS": "KRW", "KQ": "KRW", "T": "JPY", "TO": "CAD", "V": "CAD",
    "SW": "CHF", "ST": "SEK", "OL": "NOK", "CO": "DKK", "SI": "SGD", "AX": "AUD",
}


def infer_currency(ticker: str, info: dict | None) -> tuple[str, float]:
    """(devise ISO, facteur prix) d'un ticker.

    Le facteur prix vaut 0.01 pour les cotations en pence ('GBp' casse exacte
    yfinance, ou 'GBX') -- NE PAS upper() avant ce test : 'GBp'.upper() ==
    'GBP' (livres entières). Priorité : info['currency'], sinon suffixe du
    ticker (SUFFIX_CCY), sinon USD."""
    raw = str((info or {}).get("currency") or "").strip()
    if raw == "GBp" or raw.upper() == "GBX":
        return "GBP", 0.01
    cur = raw.upper()
    if not cur:
        suf = ticker.rsplit(".", 1)[1].upper() if "." in ticker else ""
        cur = SUFFIX_CCY.get(suf, "USD")
    return cur, 1.0


def volume_eur(volume, prix, ticker: str = "", info: dict | None = None,
               *, rate_getter=None) -> float:
    """Volume échangé/jour en euros ; 0.0 si donnée ou taux manquant (le titre
    sera alors traité comme illiquide -- jamais de valeur brute silencieuse)."""
    try:
        v, p = float(volume or 0), float(prix or 0)
    except (TypeError, ValueError):
        return 0.0
    if v <= 0 or p <= 0:
        return 0.0
    ccy, factor = infer_currency(ticker, info)
    if ccy == "EUR":
        return round(v * p * factor, 2)
    get = rate_getter or fx.get_rate
    rate = float(get(ccy, "EUR") or 0.0)
    if rate <= 0:
        print(f"[currency] taux {ccy}->EUR indisponible ({ticker or '?'}) -> Volume=0")
        return 0.0
    return round(v * p * factor * rate, 2)
```

Dans `backend/app/services/finance/buffett/dedup.py`, remplacer le bloc lignes 134-139 :

```python
_SUFFIX_CCY = {
    "L": "GBP", "PA": "EUR", "DE": "EUR", "AS": "EUR", "MI": "EUR", "MC": "EUR",
    "BR": "EUR", "LS": "EUR", "VI": "EUR", "HE": "EUR", "IR": "EUR",
    "HK": "HKD", "KS": "KRW", "KQ": "KRW", "T": "JPY", "TO": "CAD", "V": "CAD",
    "SW": "CHF", "ST": "SEK", "OL": "NOK", "CO": "DKK", "SI": "SGD", "AX": "AUD",
}
```

par :

```python
from .currency import SUFFIX_CCY as _SUFFIX_CCY  # source unique (currency.py)
```

(laisser cet import à cet emplacement, pas en tête de fichier : le module dedup
importe déjà paresseusement, et ça évite tout risque d'import circulaire.)

- [ ] **Step 4: Vérifier que les tests passent**

Run: `cd backend && uv run pytest tests/test_finance/test_currency_volume.py tests/test_finance/test_dedup.py -v`
Expected: PASS (tous, y compris test_dedup inchangé)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/buffett/currency.py backend/app/services/finance/buffett/dedup.py backend/tests/test_finance/test_currency_volume.py
git commit -m "feat(buffett): module currency (devise + volume en euros, pence gere)"
```

---

### Task 2: `fx.get_rate(force=)` + warm-up des paires au démarrage du run

**Files:**
- Modify: `backend/app/services/finance/fx.py:50-73` (signature + garde)
- Modify: `backend/app/services/finance/buffett/currency.py` (ajout `warm_fx_cache`)
- Modify: `backend/app/services/finance/scheduler_stub.py:109-111` (appel warm-up)
- Test: `backend/tests/test_finance/test_fx.py` (ajout), `backend/tests/test_finance/test_currency_volume.py` (ajout)

**Interfaces:**
- Consumes: `fx.get_rate`, `fx._analysis_running`, `currency.SUFFIX_CCY` (Task 1).
- Produces: `fx.get_rate(base, quote, *, fetcher=None, today=None, force=False)` — `force=True` ignore le garde `_analysis_running` ET le cache négatif (pas le cache du jour) ; `currency.warm_fx_cache(quote: str = "EUR") -> None`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_finance/test_fx.py` :

```python
def test_get_rate_force_contourne_le_garde_analyse(monkeypatch):
    """Pendant une analyse, get_rate ne fetch jamais (garde _analysis_running)
    -> le warm-up doit pouvoir forcer le fetch, sinon toute paire jamais vue
    ce jour vaudrait 0 pendant tout le run."""
    from app.services.finance import fx
    fx.clear_cache()
    monkeypatch.setattr(fx, "_analysis_running", lambda: True)
    calls = []

    def fetch(base, quote):
        calls.append((base, quote))
        return 1.25

    assert fx.get_rate("USD", "EUR", fetcher=fetch) == 0.0      # garde actif
    assert calls == []
    assert fx.get_rate("USD", "EUR", fetcher=fetch, force=True) == 1.25
    assert calls == [("USD", "EUR")]
    # Le taux forcé est en cache : l'appel normal suivant le voit.
    assert fx.get_rate("USD", "EUR", fetcher=fetch) == 1.25
    assert calls == [("USD", "EUR")]
    fx.clear_cache()
```

Ajouter à `backend/tests/test_finance/test_currency_volume.py` :

```python
def test_warm_fx_cache_precharge_toutes_les_devises(monkeypatch):
    from app.services.finance import fx
    from app.services.finance.buffett import currency

    fetched = []

    def fake_get_rate(base, quote, **kwargs):
        assert kwargs.get("force") is True and quote == "EUR"
        fetched.append(base)
        return 1.0

    monkeypatch.setattr(fx, "get_rate", fake_get_rate)
    currency.warm_fx_cache()
    attendu = sorted(({*currency.SUFFIX_CCY.values()} | {"USD"}) - {"EUR"})
    assert sorted(fetched) == attendu
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_finance/test_fx.py tests/test_finance/test_currency_volume.py -v`
Expected: FAIL — `TypeError: get_rate() got an unexpected keyword argument 'force'` et `AttributeError: ... no attribute 'warm_fx_cache'`

- [ ] **Step 3: Implémenter**

Dans `backend/app/services/finance/fx.py`, modifier la signature et le garde de `get_rate` :

```python
def get_rate(
    base: str,
    quote: str,
    *,
    fetcher: Callable[[str, str], float | None] | None = None,
    today: dt.date | None = None,
    force: bool = False,
) -> float:
    """Taux du jour pour 1 ``base`` en ``quote`` (cache quotidien). 1.0 si
    base==quote. ``force=True`` (warm-up au démarrage d'un run Buffett) passe
    outre le garde _analysis_running et le cache négatif -- pas le cache du
    jour."""
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return 1.0
    today = today or dt.date.today()
    fetch = fetcher or _default_fetch
    key = (base, quote)

    now = _now()
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] == today:
            return entry[1]
        if not force and (
            _analysis_running() or now - _failed.get(key, float("-inf")) < NEG_RETRY_S
        ):
            # Analyse en cours OU echec recent -> dernier taux connu sans
            # re-frapper yfinance
            return _cache[key][1] if key in _cache else 0.0
```

(le reste de la fonction est inchangé.)

Ajouter à la fin de `backend/app/services/finance/buffett/currency.py` :

```python
def warm_fx_cache(quote: str = "EUR") -> None:
    """Précharge les taux devise->quote au DÉMARRAGE du run Buffett : pendant
    l'analyse, fx.get_rate ne frappe plus le réseau (garde _analysis_running)
    et rendrait 0.0 pour toute paire jamais vue ce jour -> tous les volumes
    non-EUR seraient nuls et écartés comme illiquides."""
    currencies = sorted(({*SUFFIX_CCY.values()} | {"USD"}) - {quote.upper()})
    ok = [c for c in currencies if fx.get_rate(c, quote, force=True) > 0]
    manquantes = sorted(set(currencies) - set(ok))
    print(f"[currency] FX warm-up : {len(ok)}/{len(currencies)} paires -> {quote}"
          + (f" (manquantes : {', '.join(manquantes)})" if manquantes else ""))
```

Dans `backend/app/services/finance/scheduler_stub.py`, juste après `Config.load_params()` (ligne 109) :

```python
        Config.load_params()
        # Taux devise->EUR requis par la colonne Volume (en euros) : a
        # precharger AVANT le scoring, le garde _analysis_running bloque
        # ensuite tout fetch FX pendant l'analyse.
        from app.services.finance.buffett.currency import warm_fx_cache
        warm_fx_cache()
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `cd backend && uv run pytest tests/test_finance/test_fx.py tests/test_finance/test_currency_volume.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/fx.py backend/app/services/finance/buffett/currency.py backend/app/services/finance/scheduler_stub.py backend/tests/test_finance/test_fx.py backend/tests/test_finance/test_currency_volume.py
git commit -m "feat(finance): warm-up FX force au demarrage du run (volumes en euros)"
```

---

### Task 3: Ingestion — `extract_metrics` et `_etf_result` produisent un Volume en euros

**Files:**
- Modify: `backend/app/services/finance/buffett/scoring.py:52-58`
- Modify: `backend/app/services/finance/buffett/runner.py:126-138`
- Test: `backend/tests/test_finance/test_volume_eur_ingestion.py`

**Interfaces:**
- Consumes: `currency.volume_eur(volume, prix, ticker, info)` (Task 1).
- Produces: dicts métriques dont `"Volume"` est en euros (float) — consommés par reporting (DB), broker_availability (ToutBroker.xlsx), dedup, liquidity SANS changement de code.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/test_finance/test_volume_eur_ingestion.py` :

```python
"""La colonne Volume produite par le scoring/ETF est en euros (spec
orchestration/a-faire/2026-07-15-volume-eur-design.md), pas en nb d'actions."""


def _rates(monkeypatch, table):
    from app.services.finance import fx
    monkeypatch.setattr(fx, "get_rate", lambda b, q, **k: table.get(b, 0.0))


def test_extract_metrics_volume_en_euros_usd(monkeypatch):
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett.scoring import extract_metrics
    m = extract_metrics("AAPL", {
        "currentPrice": 100.0, "volume": 1_000, "currency": "USD",
        "sector": "Technology", "country": "United States",
    })
    assert m["Volume"] == 90_000.0        # 1000 x 100 $ x 0.9
    assert m["Prix"] == 100.0             # prix inchangé (devise locale)


def test_extract_metrics_volume_eur_sans_conversion(monkeypatch):
    _rates(monkeypatch, {})               # aucun taux dispo : EUR n'en a pas besoin
    from app.services.finance.buffett.scoring import extract_metrics
    m = extract_metrics("AIR.PA", {"currentPrice": 150.0, "volume": 200,
                                   "currency": "EUR"})
    assert m["Volume"] == 30_000.0


def test_extract_metrics_taux_indispo_volume_zero(monkeypatch):
    _rates(monkeypatch, {})
    from app.services.finance.buffett.scoring import extract_metrics
    m = extract_metrics("7203.T", {"currentPrice": 2_000.0, "volume": 5_000,
                                   "currency": "JPY"})
    assert m["Volume"] == 0.0


def test_etf_result_volume_en_euros(monkeypatch):
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett.runner import _etf_result
    score, metrics = _etf_result("SPY", {"info": {
        "longName": "SPDR S&P 500", "quoteType": "ETF",
        "regularMarketPrice": 500.0, "volume": 10_000, "currency": "USD",
    }})
    assert score == 200.0
    assert metrics["Volume"] == 4_500_000.0   # 10000 x 500 $ x 0.9
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_finance/test_volume_eur_ingestion.py -v`
Expected: FAIL — les `Volume` valent le nombre brut d'actions (1_000, 200, 5_000, 10_000)

- [ ] **Step 3: Implémenter**

Dans `backend/app/services/finance/buffett/scoring.py`, remplacer le retour de `extract_metrics` (lignes 52-58) :

```python
    prix = info.get("currentPrice", info.get("regularMarketPrice", 0))
    from .currency import volume_eur
    return {
        "Nom": ln or sn or symbol, "Pays": pays,
        "Prix": prix,
        "EPS": info.get("trailingEps", 0), "PER": info.get("trailingPE", 0),
        # Volume échangé/jour EN EUROS (nb actions x prix local x FX), pas le
        # nombre brut d'actions -- cf. currency.volume_eur.
        "Volume": volume_eur(
            info.get("volume", info.get("regularMarketVolume", 0)), prix, symbol, info,
        ),
        "Secteur": secteur, "QuoteType": qt,
    }
```

Dans `backend/app/services/finance/buffett/runner.py`, remplacer `_etf_result` (lignes 126-138) :

```python
def _etf_result(ticker: str, data: dict) -> tuple[float, dict]:
    """Construit le resultat Score=200 pour un ETF."""
    from .currency import volume_eur
    info = data.get("info", {})
    prix = info.get("currentPrice", info.get("regularMarketPrice", 0))
    metrics = {
        "Nom": info.get("longName", info.get("shortName", ticker)),
        "Pays": info.get("country", infer_country(ticker)),
        "Secteur": "ETF",
        "QuoteType": info.get("quoteType", "ETF"),
        "Achat": True,
        "Prix": prix,
        # En euros (cf. currency.volume_eur), comme extract_metrics.
        "Volume": volume_eur(info.get("volume", 0), prix, ticker, info),
    }
    return 200.0, metrics
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `cd backend && uv run pytest tests/test_finance/test_volume_eur_ingestion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/buffett/scoring.py backend/app/services/finance/buffett/runner.py backend/tests/test_finance/test_volume_eur_ingestion.py
git commit -m "feat(buffett): colonne Volume en euros a l'ingestion (scoring + ETF)"
```

---

### Task 4: Liquidité — `is_liquid` compare le Volume (déjà en €) au seuil

**Files:**
- Modify: `backend/app/services/finance/buffett/liquidity.py` (tout le module)
- Modify: `backend/app/services/finance/buffett/runner.py:540`
- Modify: `backend/app/api/finance/buffett.py:454`
- Test: `backend/tests/test_finance/test_liquidity.py` (réécrit)

**Interfaces:**
- Consumes: `Volume` en euros (Task 3) ; `BuffettResult.volume` (DB, euros après le prochain run).
- Produces: `daily_eur_volume(volume_eur) -> float` ; `is_liquid(volume_eur, min_eur: float | None = None) -> bool` — le paramètre `prix` DISPARAÎT des deux fonctions.

- [ ] **Step 1: Réécrire les tests (ils échouent)**

Remplacer le contenu de `backend/tests/test_finance/test_liquidity.py` :

```python
"""Filtre de liquidité : le Volume est DÉJÀ en euros (cf. currency.volume_eur),
is_liquid le compare directement au seuil -- plus de multiplication par le prix
(l'ancienne formule volume x prix_local comparait des yens/wons au seuil en €)."""


def test_daily_eur_volume_passthrough_et_donnees_manquantes():
    from app.services.finance.buffett.liquidity import daily_eur_volume
    assert daily_eur_volume(5_117.5) == 5_117.5
    assert daily_eur_volume(None) == 0.0
    assert daily_eur_volume("n/a") == 0.0


def test_is_liquid_seuil_explicite():
    from app.services.finance.buffett.liquidity import is_liquid
    assert is_liquid(5_117.5, min_eur=1_000_000) is False    # REIT athenien
    assert is_liquid(6_682_265.0, min_eur=1_000_000) is True # OR.PA
    assert is_liquid(1_000_000.0, min_eur=1_000_000) is True # egalite


def test_is_liquid_seuil_par_defaut_config():
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.liquidity import is_liquid
    assert Config.MIN_VOLUME_EUR == 100_000
    assert is_liquid(10_000.0) is False
    assert is_liquid(10_000_000.0) is True
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_finance/test_liquidity.py -v`
Expected: FAIL — `daily_eur_volume() missing 1 required positional argument: 'prix'`

- [ ] **Step 3: Implémenter**

Remplacer le contenu de `backend/app/services/finance/buffett/liquidity.py` :

```python
"""Filtre de liquidité pour l'éligibilité à l'optimisation.

On évite d'allouer un titre trop peu liquide (ex. REIT athénien BLEKEDROS.AT à
~5 000 €/jour) : il fausse l'optimiseur (variance faible/artefactuelle → Sharpe
gonflé → sur-pondération) et serait difficile à acheter/revendre. La colonne
``Volume`` est DÉJÀ le volume échangé en €/jour (cf. currency.volume_eur) : on
la compare directement au seuil ``Config.MIN_VOLUME_EUR``.
"""

from __future__ import annotations

from .config import Config


def daily_eur_volume(volume_eur) -> float:
    """Volume échangé par jour en € (0 si donnée manquante/invalide)."""
    try:
        return float(volume_eur or 0)
    except (TypeError, ValueError):
        return 0.0


def is_liquid(volume_eur, min_eur: float | None = None) -> bool:
    """Vrai si le volume €/jour atteint le seuil (défaut ``Config.MIN_VOLUME_EUR``)."""
    threshold = Config.MIN_VOLUME_EUR if min_eur is None else min_eur
    return daily_eur_volume(volume_eur) >= float(threshold)
```

Dans `backend/app/services/finance/buffett/runner.py` ligne 540, remplacer :

```python
            or is_liquid(v[1].get("Volume"), v[1].get("Prix"))
```

par :

```python
            or is_liquid(v[1].get("Volume"))
```

Dans `backend/app/api/finance/buffett.py` ligne 454, remplacer :

```python
            if not is_forced and not is_liquid(r.volume, r.prix):
```

par :

```python
            # r.volume est en euros depuis le passage de la colonne Volume en €
            # (runs anterieurs : nb d'actions brut, pas de migration -- spec).
            if not is_forced and not is_liquid(r.volume):
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `cd backend && uv run pytest tests/test_finance/test_liquidity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/buffett/liquidity.py backend/app/services/finance/buffett/runner.py backend/app/api/finance/buffett.py backend/tests/test_finance/test_liquidity.py
git commit -m "feat(buffett): is_liquid compare le Volume deja en euros (plus de x prix)"
```

---

### Task 5: Warning reprise de run + suite finance complète

**Files:**
- Modify: `backend/app/services/finance/scheduler_stub.py` (branche « reprise » du run, autour des lignes 117-130)
- Test: suite existante (aucun nouveau fichier)

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: rien de nouveau — garde-fou de log + validation d'ensemble.

- [ ] **Step 1: Ajouter le warning de reprise**

Dans `backend/app/services/finance/scheduler_stub.py`, dans la branche où un run existant (`existing`) est repris (juste après sa détection, vers la ligne 120-130 — chercher `existing = session.exec(`), ajouter :

```python
        if existing is not None:
            logger.warning(
                "Reprise du run %s : les tickers deja analyses avant le passage "
                "de la colonne Volume en euros gardent un volume en nb d'actions "
                "(unites melangees sur CE run uniquement, pas de migration).",
                existing.id,
            )
```

(adapter le nom de variable au code réel de la branche ; ne PAS logger pour un run neuf.)

- [ ] **Step 2: Lancer la suite finance complète**

Run: `cd backend && uv run pytest tests/test_finance/ -v`
Expected: PASS — si un test échoue parce qu'il supposait un Volume brut multiplié par un prix, l'adapter à la nouvelle sémantique (Volume déjà en €) plutôt que de réintroduire `prix` dans liquidity.

- [ ] **Step 3: Vérification manuelle rapide (backend vivant)**

Run: `curl -s http://127.0.0.1:8000/finance/buffett/progress`
Expected: réponse JSON (le serveur --reload a rechargé sans erreur d'import).

- [ ] **Step 4: Commit + déplacer la spec/plan dans en-cours → finis**

```bash
git add backend/app/services/finance/scheduler_stub.py
git commit -m "feat(buffett): warning reprise de run avec unites de Volume melangees"
git mv orchestration/a-faire/2026-07-15-volume-eur-design.md orchestration/finis/
git mv orchestration/a-faire/2026-07-15-volume-eur-plan.md orchestration/finis/
git commit -m "docs(orchestration): spec+plan volume EUR livres"
```
