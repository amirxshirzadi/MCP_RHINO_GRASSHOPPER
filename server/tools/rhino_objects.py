# -*- coding: utf-8 -*-
"""Outils Rhino : objets du document."""
from .common import LIMIT, tool

TOOLS = [
    tool(
        "rhino_get_objects",
        "Liste les objets du document Rhino (id, type, nom, calque, boîte englobante), avec pagination.",
        {
            "layer": {"type": "string", "description": "Ne garder que ce calque (chemin complet)."},
            "selected_only": {"type": "boolean", "description": "Seulement les objets sélectionnés."},
            "limit": LIMIT,
            "offset": {"type": "integer", "default": 0},
        },
        read_only=True,
    ),
]
