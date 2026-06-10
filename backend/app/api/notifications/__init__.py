"""Routes Notifications — package par module (#515). URLs inchangées.

Ré-export direct (pas de routeur agrégateur) : la route ``GET ""`` (path vide)
n'est pas autorisée derrière un double include sans préfixe.
"""
from .routes import router  # noqa: F401
