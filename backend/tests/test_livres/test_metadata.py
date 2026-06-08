from app.services.livres.metadata import parse_open_library_response, parse_search_response

def test_parse_valid():
    raw = {"ISBN:9780735224292": {
        "title": "Atomic Habits",
        "authors": [{"name": "James Clear"}],
        "number_of_pages": 320,
    }}
    result = parse_open_library_response(raw, "9780735224292")
    assert result["titre"] == "Atomic Habits"
    assert result["auteur"] == "James Clear"
    assert result["pages"] == 320

def test_parse_not_found():
    assert parse_open_library_response({}, "0000000000000") is None


# ── recherche (#143) ─────────────────────────────────────────────────────────

def test_parse_search_extracts_fields():
    raw = {"docs": [{
        "title": "Sapiens",
        "author_name": ["Yuval Noah Harari"],
        "number_of_pages_median": 443,
        "isbn": ["9780062316097", "0062316095"],
        "first_publish_year": 2011,
        "cover_i": 8739161,
    }]}
    res = parse_search_response(raw)
    assert len(res) == 1
    assert res[0]["titre"] == "Sapiens"
    assert res[0]["auteur"] == "Yuval Noah Harari"
    assert res[0]["pages"] == 443
    assert res[0]["isbn"] == "9780062316097"
    assert res[0]["annee"] == 2011
    assert "8739161" in res[0]["couverture_url"]


def test_parse_search_handles_missing_fields():
    res = parse_search_response({"docs": [{"title": "Inconnu"}]})
    assert res[0]["titre"] == "Inconnu"
    assert res[0]["auteur"] == ""
    assert res[0]["isbn"] is None
    assert res[0]["couverture_url"] is None


def test_parse_search_respects_limit():
    raw = {"docs": [{"title": f"L{i}"} for i in range(20)]}
    assert len(parse_search_response(raw, limit=5)) == 5


def test_parse_search_empty():
    assert parse_search_response({}) == []
