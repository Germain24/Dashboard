from app.services.livres.metadata import parse_open_library_response

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
