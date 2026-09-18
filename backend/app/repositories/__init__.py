"""Couche repository par module.

Chaque module expose des classes ``*Repository`` (héritant de
:class:`app.core.repository.Repository`) qui encapsulent l'accès aux modèles
SQLModel. Les services consomment ces repositories pour rester découplés de la
persistance.
"""
