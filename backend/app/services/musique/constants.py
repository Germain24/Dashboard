"""Playlists musicales : slug (identifiant) ↔ label (affichage) + description IA."""

# Ordre = ordre d'affichage. slug : ASCII, sans '/' ni espace ; stocké en base,
# utilisé dans les URLs et comme base des noms de fichiers d'export.
PLAYLISTS: dict[str, dict[str, str]] = {
    "cafe-petit-dej": {
        "label": "café pour le petit dep",
        "desc": "léger, doux, agréable au réveil / petit-déjeuner",
    },
    "coworking-travail-detente": {
        "label": "coworking/travail/detente",
        "desc": "rythmé mais non distrayant, fond de travail/concentration",
    },
    "soiree-francophone": {
        "label": "soirée ( francophone )",
        "desc": "festif, dansant, chansons francophones",
    },
    "soiree-internationale": {
        "label": "soirée ( internationale )",
        "desc": "festif, dansant, hits internationaux",
    },
    "amour-love-sex": {
        "label": "amour/love/sex",
        "desc": "romantique, sensuel, intime (type date)",
    },
    "chanson-francaise": {
        "label": "chanson francaise",
        "desc": "chanson française : variété et auteurs-compositeurs francophones",
    },
    "melancolie": {
        "label": "Mélancolie",
        "desc": "mélancolique, doux-amer, introspectif",
    },
    "sport-gym": {
        "label": "sport/gym",
        "desc": "entraînant, tempo élevé, motivation sportive",
    },
}

AMBIANCE_NAMES: list[str] = list(PLAYLISTS)
AMBIANCE_LABELS: dict[str, str] = {s: p["label"] for s, p in PLAYLISTS.items()}
AMBIANCES: dict[str, str] = {s: p["desc"] for s, p in PLAYLISTS.items()}
LABEL_TO_SLUG: dict[str, str] = {p["label"]: s for s, p in PLAYLISTS.items()}

AUDIO_EXTENSIONS = {".mp3", ".flac", ".dsf"}
