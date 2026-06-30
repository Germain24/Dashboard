"""Tests des fonctions pures de l'outil Excel <-> playlists."""
from scripts.playlists_excel import _parse_resultats, split_artists


def test_split_artists_slash_et_feat():
    assert split_artists("J Balvin/Bad Bunny", "QUE PRETENDES") == ("J Balvin", "Bad Bunny")
    assert split_artists("Daft Punk", "One More Time") == ("Daft Punk", "")
    assert split_artists("Kelly Rowland", "Motivation feat. Lil Wayne") == ("Kelly Rowland", "Lil Wayne")
    a, co = split_artists("David Guetta & Sia", "Titanium")
    assert a == "David Guetta" and co == "Sia"


def test_split_artists_dedup_et_vide():
    assert split_artists("", "") == ("", "")
    # featuring présent à la fois dans artiste et titre -> pas de doublon
    a, co = split_artists("A feat. B", "Chanson feat. B")
    assert a == "A" and co == "B"


def test_parse_resultats_garde_labels_valides():
    payload = {"resultats": [
        {"index": 1, "playlists": ["rock", "pop", "inconnu", "rock"]},
        {"index": 2, "playlists": []},
        {"index": 99, "playlists": ["rap"]},  # hors lot -> ignoré
    ]}
    res = _parse_resultats(payload, 2)
    assert res == [["rock", "pop"], []]


def test_parse_resultats_tristesse_remplace_melancolie():
    res = _parse_resultats({"resultats": [{"index": 1, "playlists": ["tristesse", "Mélancolie"]}]}, 1)
    assert res == [["tristesse"]]  # "Mélancolie" n'existe plus -> ignoré
