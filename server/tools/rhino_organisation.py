# -*- coding: utf-8 -*-
"""Outils Rhino : calques, matériaux et blocs."""
from .common import COLOR, IDS, LAYER, POINT, enum, tool

TOOLS = [
    tool(
        "rhino_layer",
        (
            "Calques Rhino. action : list (calques, objets par calque, matériau, calque courant, états), create "
            "(path 'Parent::Enfant' créé avec ses parents ; color, visible, locked, material), update (path ; "
            "new_name, parent ('' = racine), color, visible, locked, material), delete (refuse s'il contient des "
            "objets, sauf delete_objects=true), set_current, save_state / restore_state / delete_state (state = "
            "nom d'un état de calques)."
        ),
        {
            "action": enum(["list", "create", "update", "delete", "set_current", "save_state", "restore_state",
                            "delete_state"], "Opération.", default="list"),
            "path": {"type": "string", "description": "Chemin complet du calque (ex. 'Façade::Vitrage')."},
            "new_name": {"type": "string", "description": "update : nouveau nom (dernier niveau du chemin)."},
            "parent": {"type": "string", "description": "update : nouveau calque parent ('' = racine)."},
            "color": COLOR,
            "visible": {"type": "boolean"},
            "locked": {"type": "boolean"},
            "material": {"type": "string", "description": "Matériau du calque (nom, voir rhino_material ; '' = aucun)."},
            "delete_objects": {"type": "boolean", "default": False},
            "state": {"type": "string", "description": "Nom de l'état de calques."},
        },
    ),
    tool(
        "rhino_material",
        (
            "Matériaux de rendu (PBR) du document. action : list ; create (name, color, metallic 0-1, roughness "
            "0-1, opacity 0-1 ; replace=true remplace un matériau du même nom partout où il est utilisé ; ids / "
            "layers pour l'affecter tout de suite) ; assign (name à des objets ids et/ou des calques layers) ; "
            "delete."
        ),
        {
            "action": enum(["list", "create", "assign", "delete"], "Opération.", default="list"),
            "name": {"type": "string"},
            "color": COLOR,
            "metallic": {"type": "number", "default": 0.0},
            "roughness": {"type": "number", "default": 0.5},
            "opacity": {"type": "number", "default": 1.0, "description": "1 = opaque, 0.2 = verre."},
            "ids": IDS,
            "layers": {"type": "array", "items": {"type": "string"}, "description": "Calques (chemins complets)."},
            "replace": {"type": "boolean", "default": False},
        },
    ),
    tool(
        "rhino_block",
        (
            "Blocs Rhino. action : list (définitions, nombre d'instances) ; create (name, ids, base_point = coin "
            "minimal par défaut ; delete_input=true remplace les objets par une instance, comme la commande Block) ; "
            "insert (name, point, scale, rotation en degrés autour de Z, layer) ; explode (ids d'instances ; "
            "explode_nested) ; delete (name, supprime aussi ses instances)."
        ),
        {
            "action": enum(["list", "create", "insert", "explode", "delete"], "Opération.", default="list"),
            "name": {"type": "string"},
            "ids": IDS,
            "base_point": POINT,
            "description": {"type": "string"},
            "delete_input": {"type": "boolean", "default": True},
            "point": POINT,
            "scale": {"type": "number", "default": 1.0},
            "rotation": {"type": "number", "default": 0.0},
            "explode_nested": {"type": "boolean", "default": False},
            "layer": LAYER,
        },
    ),
]
