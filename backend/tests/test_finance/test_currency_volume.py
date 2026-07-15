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


def test_suffix_ccy_couvre_toutes_les_bourses_de_suffix_map():
    """Test de couverture structurel : cache_manager.SUFFIX_MAP est la source
    de vérité des bourses de l'univers Buffett. Si une bourse non-US y est
    ajoutée sans devise dans SUFFIX_CCY, warm_fx_cache() ne préchauffera
    jamais son taux -> Volume=0 silencieux pour tout ticker de cette bourse
    (voir orchestration/a-faire/2026-07-15-volume-eur-design.md, finding
    "SUFFIX_CCY couvre moins de bourses que SUFFIX_MAP").

    SUFFIX_MAP contient des suffixes non-bourse ou de bourses US/zone EUR déjà
    couvertes ; on exclut seulement les pays "United States" et "Inconnu"
    (aucun suffixe ne mappe vers eux dans la table) -- toute autre entrée doit
    avoir un suffixe équivalent (sans le point) dans SUFFIX_CCY.
    """
    from app.services.finance.buffett import currency
    from app.services.finance.buffett.cache_manager import SUFFIX_MAP

    manquants = []
    for suffix_avec_point, pays in SUFFIX_MAP.items():
        suf = suffix_avec_point.lstrip(".").upper()
        if suf not in currency.SUFFIX_CCY:
            manquants.append((suffix_avec_point, pays))
    assert not manquants, (
        f"Bourses de SUFFIX_MAP sans devise dans SUFFIX_CCY (Volume=0 "
        f"silencieux garanti) : {manquants}"
    )


def test_volume_eur_signale_devise_non_prechauffee(capsys):
    """Une devise absente de SUFFIX_CCY.values() (donc jamais préchauffée par
    warm_fx_cache) doit produire un message distinct d'un simple échec de
    fetch, pour qu'on puisse la repérer dans les logs et compléter la table."""
    from app.services.finance.buffett.currency import volume_eur

    def taux_toujours_absent(base, quote, **kwargs):
        return 0.0

    # "XXX" n'est la devise d'aucun suffixe de SUFFIX_CCY ni USD.
    assert volume_eur(1000, 10.0, "FOO.ZZ", {"currency": "XXX"},
                      rate_getter=taux_toujours_absent) == 0.0
    out = capsys.readouterr().out
    assert "XXX" in out
    assert "préchauffée" in out
    assert "indisponible" not in out


def test_volume_eur_devise_couverte_mais_taux_indisponible_message_different(capsys):
    """Contrôle négatif : une devise couverte (ex. KRW, déjà dans SUFFIX_CCY)
    dont le taux échoue au fetch reste un message 'taux indisponible' normal,
    pas le message 'non préchauffée'."""
    from app.services.finance.buffett.currency import volume_eur

    def taux_toujours_absent(base, quote, **kwargs):
        return 0.0

    assert volume_eur(1000, 10.0, "005930.KS", {"currency": "KRW"},
                      rate_getter=taux_toujours_absent) == 0.0
    out = capsys.readouterr().out
    assert "non préchauffée" not in out
    assert "indisponible" in out
