# -*- coding: utf-8 -*-
"""
Définitions des outils MCP (données pures, sans Rhino), un fichier par domaine.

Chaque outil correspond à une commande du même nom côté Rhino
(rhino/rhino_mcp/*.py, fonctions décorées par @command).
"""
from . import (
    grasshopper,
    rhino_document,
    rhino_geometry,
    rhino_objects,
    rhino_organisation,
    rhino_scripting,
    rhino_views,
)

DOMAINS = [
    ("Rhino : document et fichiers", rhino_document.TOOLS),
    ("Rhino : objets", rhino_objects.TOOLS),
    ("Rhino : géométrie", rhino_geometry.TOOLS),
    ("Rhino : calques, matériaux, blocs", rhino_organisation.TOOLS),
    ("Rhino : vues, annotations, mises en page", rhino_views.TOOLS),
    ("Rhino : scripts et commandes", rhino_scripting.TOOLS),
    ("Grasshopper", grasshopper.TOOLS),
]

TOOLS = [t for _, tools in DOMAINS for t in tools]
TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}

if len(TOOLS_BY_NAME) != len(TOOLS):
    raise RuntimeError("Nom d'outil en double dans server/tools.")
