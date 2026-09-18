import pandas as pd
import pytest


def test_ecb_history_converts_units_per_eur(monkeypatch, tmp_path):
    from app.services.finance import fx

    frame = pd.DataFrame(
        {
            "Date": ["2026-01-01", "2026-01-02"],
            "USD": [1.20, 1.10],
            "CHF": [0.96, 0.88],
        }
    )
    cache = tmp_path / "ecb.csv"
    frame.to_csv(cache, index=False)
    monkeypatch.setattr(fx, "_HISTORY_CACHE_FILE", cache)
    monkeypatch.setattr(fx, "_history_cache", None)

    chf_eur = fx.get_historical_rates("CHF", "EUR", refresh_after_days=9999)
    chf_usd = fx.get_historical_rates("CHF", "USD", refresh_after_days=9999)

    assert chf_eur.iloc[0] == pytest.approx(1 / 0.96)
    assert chf_usd.iloc[0] == pytest.approx(1.20 / 0.96)


def test_ecb_daily_seeds_all_available_spot_rates(monkeypatch, tmp_path):
    from app.services.finance import fx

    xml = b"""<?xml version='1.0'?>
    <Envelope><Cube><Cube time='2026-08-24'>
      <Cube currency='USD' rate='1.20'/>
      <Cube currency='CHF' rate='0.96'/>
    </Cube></Cube></Envelope>"""

    class Response:
        content = xml

        def raise_for_status(self):
            return None

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(fx, "_DISK_CACHE_FILE", tmp_path / "fx.json")
    fx.clear_cache()

    found = fx.refresh_rates_from_ecb({"CHF", "USD", "TWD"}, "EUR")

    assert found == {"CHF", "USD"}
    assert fx.get_rate("CHF", "EUR") == pytest.approx(1 / 0.96)
    assert fx.get_rate("USD", "EUR") == pytest.approx(1 / 1.20)
