import httpx

OPEN_LIBRARY_URL = "https://openlibrary.org/api/books"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
COVERS_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
COVERS_ID_URL = "https://covers.openlibrary.org/b/id/{cover_i}-L.jpg"

# Codes langue Open Library (ISO 639-2) -> libellés français.
LANG_LABELS = {
    "eng": "Anglais", "fre": "Français", "fra": "Français", "jpn": "Japonais",
    "spa": "Espagnol", "ger": "Allemand", "deu": "Allemand", "ita": "Italien",
    "por": "Portugais", "rus": "Russe", "chi": "Chinois", "zho": "Chinois",
    "kor": "Coréen", "ara": "Arabe", "dut": "Néerlandais", "nld": "Néerlandais",
    "lat": "Latin", "gre": "Grec", "heb": "Hébreu", "pol": "Polonais",
    "swe": "Suédois", "tur": "Turc",
}


def langue_label(codes) -> str:
    """Premier code langue Open Library traduit en libellé lisible (sinon "")."""
    if not codes:
        return ""
    code = (codes[0] or "").lower()
    return LANG_LABELS.get(code, code.capitalize())

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

def parse_search_response(data: dict, limit: int = 10) -> list[dict]:
    """Pur : extrait les résultats de recherche Open Library."""
    out = []
    for doc in data.get("docs", [])[:limit]:
        isbns = doc.get("isbn") or []
        cover_i = doc.get("cover_i")
        out.append({
            "titre": doc.get("title", ""),
            "auteur": ", ".join(doc.get("author_name", [])),
            "pages": doc.get("number_of_pages_median"),
            "isbn": isbns[0] if isbns else None,
            "annee": doc.get("first_publish_year"),
            "langue": langue_label(doc.get("language")),
            "couverture_url": COVERS_ID_URL.format(cover_i=cover_i) if cover_i else None,
        })
    return out


def search_books(query: str, limit: int = 10) -> list[dict]:
    """Recherche de livres par titre/auteur via Open Library (#143)."""
    if not query.strip():
        return []
    try:
        resp = httpx.get(
            OPEN_LIBRARY_SEARCH_URL,
            params={"q": query, "limit": limit, "fields": "title,author_name,number_of_pages_median,isbn,first_publish_year,language,cover_i"},
            timeout=5.0,
        )
        resp.raise_for_status()
        return parse_search_response(resp.json(), limit)
    except Exception:
        return []


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
