# -*- coding: utf-8 -*-
"""Outils Rhino : document et fichiers."""
from .common import tool

TOOLS = [
    tool(
        "rhino_ping",
        "Vérifie que Rhino est joignable et renvoie la version de Rhino et le document ouvert.",
        read_only=True,
    ),
    tool(
        "rhino_get_document_info",
        "Infos sur le document Rhino actif : unités, tolérance, calques, nombre d'objets par type, vues.",
        read_only=True,
    ),
]
