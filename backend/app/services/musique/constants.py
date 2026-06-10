"""Ambiances musicales et leurs définitions (pour guider Ollama)."""

AMBIANCES: dict[str, str] = {
    "café": "léger, acoustique, agréable en fond",
    "loft": "chill/électro posé, ambiance appartement",
    "coworking": "rythmé mais non distrayant, pour travailler",
    "étude": "calme, instrumental, concentration",
    "repos": "très calme, détente, sieste",
    "énergie": "entraînant, motivant, tempo élevé",
    "soirée": "festif, dansant",
    "love": "chansons d'amour, romantiques (type date)",
}

AMBIANCE_NAMES = list(AMBIANCES)
AUDIO_EXTENSIONS = {".mp3", ".flac", ".dsf"}
