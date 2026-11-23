# -*- coding: utf-8 -*-
"""Outils Rhino : vues, captures, annotations et mises en page."""
from .common import tool

TOOLS = [
    tool(
        "rhino_capture_view",
        "Capture une vue Rhino en image PNG (vue active par défaut) pour voir le résultat.",
        {
            "view": {"type": "string", "description": "Nom de la vue (Perspective, Top, ...)."},
            "width": {"type": "integer", "default": 900},
            "height": {"type": "integer", "default": 600},
        },
        read_only=True,
    ),
]
