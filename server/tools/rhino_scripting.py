# -*- coding: utf-8 -*-
"""Outils Rhino : scripts Python et commandes Rhino (tout ce que les autres outils ne couvrent pas)."""
from .common import tool

TOOLS = [
    tool(
        "rhino_execute_python",
        (
            "Exécute du code Python 3 dans Rhino 8 (une seule étape d'annulation). Disponibles : Rhino (RhinoCommon), "
            "rs (rhinoscriptsyntax), sc (scriptcontext), System, doc (document actif), get_gh_doc() (document "
            "Grasshopper ; `import Grasshopper` pour l'API). Affecte la variable `result` pour renvoyer une valeur ; "
            "print() est aussi renvoyé. Outil polyvalent pour tout ce que les autres outils ne couvrent pas."
        ),
        {"code": {"type": "string", "description": "Code Python 3 à exécuter."}},
        required=["code"],
        destructive=True,
    ),
]
