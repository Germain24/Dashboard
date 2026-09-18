from app.services.finance.buffett.world_scenarios import identify_world_tickers, is_broad_msci_world


def test_broad_world_excludes_acwi_and_thematic_indices():
    assert is_broad_msci_world("Amundi PEA Monde", "MSCI World")
    assert not is_broad_msci_world("ACWI", "MSCI ACWI")
    assert not is_broad_msci_world("Water", "MSCI World Water")


def test_identify_world_tickers_uses_economic_index_metadata():
    assert identify_world_tickers(
        ["WPEA.PA", "AWAT.PA"],
        {
            "WPEA.PA": {"Nom": "iShares PEA Monde", "Indice": "MSCI World"},
            "AWAT.PA": {"Nom": "Amundi Eau", "Indice": "MSCI World Water"},
        },
    ) == {"WPEA.PA"}
