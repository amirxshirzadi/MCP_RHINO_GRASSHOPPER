# -*- coding: utf-8 -*-
"""Outils Grasshopper : définition, composants, fils, données, calcul."""
from .common import GH_ID, GH_IDS, PARAM_KEY, tool

TOOLS = [
    tool(
        "gh_get_canvas",
        (
            "Décrit le document Grasshopper ouvert (l'ouvre si besoin) : composants, entrées/sorties, connexions, "
            "valeurs des curseurs/panneaux/interrupteurs, erreurs et avertissements."
        ),
        read_only=True,
    ),
    tool(
        "gh_search_components",
        "Cherche des composants Grasshopper installés par nom, surnom, catégorie ou description.",
        {
            "query": {"type": "string", "description": "Texte à chercher (ex. 'circle', 'divide curve')."},
            "limit": {"type": "integer", "default": 30},
        },
        required=["query"],
        read_only=True,
    ),
    tool(
        "gh_add_component",
        (
            "Ajoute un composant sur le canevas Grasshopper, par nom exact (ex. 'Circle', 'Number Slider', 'Panel', "
            "'Boolean Toggle') ou par guid (voir gh_search_components). Renvoie son id et ses paramètres."
        ),
        {
            "name": {"type": "string"},
            "guid": {"type": "string"},
            "x": {"type": "number", "default": 0},
            "y": {"type": "number", "default": 0},
            "nickname": {"type": "string"},
        },
    ),
    tool(
        "gh_connect",
        "Relie une sortie d'un objet Grasshopper à une entrée d'un autre (ou les déconnecte).",
        {
            "source_id": GH_ID,
            "source_output": PARAM_KEY,
            "target_id": GH_ID,
            "target_input": PARAM_KEY,
            "disconnect": {"type": "boolean", "default": False},
        },
        required=["source_id", "target_id"],
    ),
    tool(
        "gh_set_value",
        (
            "Règle la valeur d'un curseur (Number Slider : value, min, max, decimals), d'un panneau (texte) ou d'un "
            "interrupteur (Boolean Toggle : true/false)."
        ),
        {
            "id": GH_ID,
            "value": {"description": "Nouvelle valeur."},
            "min": {"type": "number"},
            "max": {"type": "number"},
            "decimals": {"type": "integer", "description": "0 = curseur entier."},
        },
        required=["id", "value"],
    ),
    tool(
        "gh_get_output",
        "Lit les données calculées d'une sortie Grasshopper (arbre de données, sous forme de texte).",
        {"id": GH_ID, "output": PARAM_KEY, "limit": {"type": "integer", "default": 200}},
        required=["id"],
        read_only=True,
    ),
    tool(
        "gh_solve",
        "Recalcule toute la définition Grasshopper et liste les composants en erreur ou en avertissement.",
    ),
    tool(
        "gh_delete",
        "Supprime des objets du canevas Grasshopper.",
        {"ids": GH_IDS},
        required=["ids"],
        destructive=True,
    ),
]
