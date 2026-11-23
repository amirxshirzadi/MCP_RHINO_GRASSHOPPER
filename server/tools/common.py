# -*- coding: utf-8 -*-
"""Morceaux de schémas JSON réutilisés par les définitions d'outils."""

ID = {"type": "string", "description": "Identifiant (GUID) de l'objet."}
IDS = {"type": "array", "items": {"type": "string"}, "description": "Identifiants (GUID) des objets."}
GH_ID = {"type": "string", "description": "Identifiant (InstanceGuid) de l'objet Grasshopper."}
GH_IDS = {"type": "array", "items": {"type": "string"}, "description": "Identifiants (InstanceGuid) Grasshopper."}
PARAM_KEY = {"type": ["integer", "string"], "description": "Index (0, 1, ...) ou nom du paramètre."}
POINT = {
    "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3,
    "description": "Point [x, y, z] (z vaut 0 si omis).",
}
POINTS = {"type": "array", "items": POINT, "description": "Liste de points [[x, y, z], ...]."}
VECTOR = dict(POINT, description="Vecteur [x, y, z].")
PLANE = {
    "description": (
        "Plan : 'xy' (défaut), 'yz', 'zx', ou objet {\"origin\": [x,y,z], \"normal\": [x,y,z]} "
        "ou {\"origin\": [...], \"x_axis\": [...], \"y_axis\": [...]}."
    ),
}
COLOR = {
    "description": "Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque).",
}
LAYER = {"type": "string", "description": "Calque (chemin complet, ex. 'Façade::Vitrage') ; créé s'il n'existe pas."}
NAME = {"type": "string", "description": "Nom à donner à l'objet."}
LIMIT = {"type": "integer", "default": 200, "description": "Nombre maximal d'éléments renvoyés."}


def tool(name, description, properties=None, required=None, read_only=False, destructive=False, title=None):
    """Construit la définition MCP d'un outil."""
    schema = {"type": "object", "properties": properties or {}}
    if required:
        schema["required"] = list(required)
    annotations = {"readOnlyHint": bool(read_only)}
    if not read_only:
        annotations["destructiveHint"] = bool(destructive)
    if title:
        annotations["title"] = title
    return {"name": name, "description": description, "inputSchema": schema, "annotations": annotations}


def enum(values, description, default=None):
    prop = {"type": "string", "enum": list(values), "description": description}
    if default is not None:
        prop["default"] = default
    return prop
