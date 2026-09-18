from pathlib import Path

from scripts.import_jpx_tickers import merge_jpx_catalog


def test_merge_jpx_replaces_generated_tokyo_and_preserves_other_markets():
    current = (
        "ABC;Alpha;NYSE;Action\n"
        "1301.T;;;\n"
        "1301.T;Old name;Tokyo;Action\n"
        "9999.T;;;\n"
        "ABC;;;\n"
    ).encode()
    official = [
        ("1301.T", "KYOKUYO CO.,LTD.", "Tokyo Stock Exchange (Prime)", "Action"),
        ("1305.T", "iFreeETF TOPIX", "Tokyo Stock Exchange (ETFs/ ETNs)",
         "Tracker/ETF"),
    ]

    output, report = merge_jpx_catalog(current, official)
    text = output.decode()

    assert "ABC;Alpha;NYSE;Action" in text
    assert "1301.T;KYOKUYO CO.,LTD.;Tokyo Stock Exchange (Prime);Action" in text
    assert "1305.T;iFreeETF TOPIX;Tokyo Stock Exchange (ETFs/ ETNs);Tracker/ETF" in text
    assert "9999.T" not in text
    assert report["tokyo_generated_before"] == 2
    assert report["tokyo_official_after"] == 2
    assert report["tokyo_removed_not_listed"] == 1
    assert report["tokyo_added_official"] == 1
