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
