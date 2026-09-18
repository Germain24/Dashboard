"""Filtre des ETF à effet de levier / inverse (exclus de l'optimisation)."""


def test_detects_known_leveraged_products():
    from app.services.finance.buffett.leverage_filter import is_leveraged_product
    assert is_leveraged_product("Amundi CAC 40 Daily (2x) Leveraged UCITS ETF Acc") is True
    assert is_leveraged_product("Amundi CAC 40 Daily (-1x) Inverse UCITS ETF Acc") is True
    assert is_leveraged_product("Amundi LevDax Daily (2x) leveraged UCITS ETF Acc") is True
    assert is_leveraged_product("Amundi MSCI USA Daily (2x) Leveraged UCITS ETF Acc") is True
    assert is_leveraged_product("ProShares UltraShort S&P500") is True
    assert is_leveraged_product("ProShares UltraPro QQQ") is True
    assert is_leveraged_product("FTSE 100 Short Daily UCITS ETF") is True
    assert is_leveraged_product("Direxion Daily S&P 500 Bear 3X Shares") is True
    assert is_leveraged_product("Leverage Shares -1x Apple ETC") is True
    assert is_leveraged_product("WisdomTree Palladium 1x Short") is True


def test_does_not_flag_false_positives():
    from app.services.finance.buffett.leverage_filter import is_leveraged_product
    # "lever" et "ultra" en sous-chaine ne doivent pas declencher un faux positif.
    assert is_leveraged_product("Unilever PLC") is False
    assert is_leveraged_product("Ultragenyx Pharmaceutical Inc.") is False
    assert is_leveraged_product("PGIM Short Duration High Yield Opportunities Fund") is False
    assert is_leveraged_product("BNP Paribas Easy S&P 500 UCITS ETF EUR C") is False
    assert is_leveraged_product("") is False
    assert is_leveraged_product(None) is False
