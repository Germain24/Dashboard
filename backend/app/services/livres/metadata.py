import httpx

OPEN_LIBRARY_URL = "https://openlibrary.org/api/books"
COVERS_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"

def parse_open_library_response(data: dict, isbn: str) -> dict | None:
    key = f"ISBN:{isbn}"
    if key not in data:
        return None
    book = data[key]
    authors = book.get("authors", [])
    return {
        "titre": book.get("title", ""),
        "auteur": ", ".join(a["name"] for a in authors),
        "pages": book.get("number_of_pages"),
        "couverture_url": COVERS_URL.format(isbn=isbn),
    }

def lookup_isbn(isbn: str) -> dict | None:
    try:
        resp = httpx.get(
            OPEN_LIBRARY_URL,
            params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            timeout=5.0
        )
        resp.raise_for_status()
        return parse_open_library_response(resp.json(), isbn)
    except Exception:
        return None
