from app.services.musique.quality import purchase_status, quality_label, quality_tier


def test_quality_tier():
    assert quality_tier(".mp3", None, None) == "lossy"
    assert quality_tier(".flac", 16, 44100) == "cd"
    assert quality_tier(".flac", 24, 96000) == "hires"
    assert quality_tier(".flac", 16, 96000) == "hires"     # >48kHz -> hires
    assert quality_tier(".dsf", 1, 2822400) == "dsd"


def test_quality_label():
    assert quality_label(".mp3", 320, 44100, None) == "MP3 (320 kbps)"
    assert quality_label(".flac", 940, 44100, 16) == "FLAC CD (16 bit · 44,1 kHz)"
    assert quality_label(".flac", 2300, 96000, 24) == "Hi-Res (24 bit · 96 kHz)"
    assert quality_label(".dsf", None, 2822400, 1) == "DSD"
    assert quality_label(".mp3", None, None, None) == "MP3"   # bitrate inconnu


def test_purchase_status():
    assert purchase_status("cd", None) == "owned"
    assert purchase_status("hires", False) == "owned"
    assert purchase_status("lossy", True) == "to_buy"
    assert purchase_status("lossy", False) == "unavailable"
    assert purchase_status("lossy", None) == "unknown"
