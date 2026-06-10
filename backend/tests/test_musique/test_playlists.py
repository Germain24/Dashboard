from app.services.musique.playlists import reco_bibliotheque, to_m3u


def test_to_m3u_relative_paths():
    tracks = [
        {"path": "A/Alb/01.flac", "artist": "A", "title": "T1", "duree_sec": 200},
        {"path": "B/Alb/02.mp3", "artist": "B", "title": "T2", "duree_sec": None},
    ]
    m = to_m3u(tracks)
    lines = m.splitlines()
    assert lines[0] == "#EXTM3U"
    assert "#EXTINF:200,A - T1" in lines
    assert "A/Alb/01.flac" in lines
    assert "#EXTINF:-1,B - T2" in lines  # durée inconnue -> -1


def test_reco_scores_by_shared_artist_or_genre():
    tracks_in = [{"id": 1, "artist": "X", "genre": "jazz"}]
    tracks_out = [
        {"id": 2, "artist": "X", "genre": "rock"},   # même artiste -> score 1
        {"id": 3, "artist": "Z", "genre": "jazz"},   # même genre -> score 1
        {"id": 4, "artist": "Q", "genre": "metal"},  # rien -> exclu
    ]
    reco = reco_bibliotheque(tracks_in, tracks_out)
    ids = [t["id"] for t in reco]
    assert set(ids) == {2, 3} and 4 not in ids
