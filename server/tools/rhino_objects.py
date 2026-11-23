# -*- coding: utf-8 -*-
"""Outils Rhino : objets du document."""
from .common import COLOR, IDS, LAYER, LIMIT, PLANE, POINT, VECTOR, enum, tool

TYPE = {
    "type": "string",
    "description": (
        "Type d'objet : Point, Curve, Brep (polysurface/solide), Extrusion, Surface, Mesh, SubD, Annotation "
        "(texte, cote), TextDot, Hatch, InstanceReference (bloc)..."
    ),
}

TOOLS = [
    tool(
        "rhino_get_objects",
        "Liste les objets du document Rhino (id, type, nom, calque, boîte englobante), avec filtres et pagination.",
        {
            "layer": {"type": "string", "description": "Ne garder que ce calque (chemin complet)."},
            "type": TYPE,
            "name": {"type": "string", "description": "Ne garder que les objets dont le nom contient ce texte."},
            "selected_only": {"type": "boolean", "description": "Seulement les objets sélectionnés."},
            "include_hidden": {"type": "boolean", "default": True},
            "limit": LIMIT,
            "offset": {"type": "integer", "default": 0},
        },
        read_only=True,
    ),
    tool(
        "rhino_get_object_details",
        (
            "Détails d'objets Rhino : attributs (nom, calque, couleur, matériau, visibilité, verrouillage, "
            "textes utilisateur, groupes) et géométrie (longueur, aire, volume, centroïde, solide/fermé, "
            "points d'une polyligne, centre/rayon d'un cercle, texte d'une annotation, bloc...)."
        ),
        {"ids": IDS},
        required=["ids"],
        read_only=True,
    ),
    tool(
        "rhino_select_objects",
        (
            "Sélection dans Rhino. action : select / unselect (par ids, ou par filtre layer/type/name), "
            "clear (tout désélectionner), get (objets sélectionnés)."
        ),
        {
            "action": enum(["select", "unselect", "clear", "get"], "Opération.", default="select"),
            "ids": IDS,
            "layer": {"type": "string", "description": "Filtre : calque (chemin complet)."},
            "type": TYPE,
            "name": {"type": "string", "description": "Filtre : le nom contient ce texte."},
        },
    ),
    tool(
        "rhino_modify_objects",
        (
            "Modifie des objets Rhino : nom, calque (créé si besoin), couleur (ou 'by_layer'), matériau (nom d'un "
            "matériau du document, ou 'by_layer'), visible (afficher/masquer), locked (verrouiller), user_text "
            "(clé -> valeur ; valeur null pour supprimer). Une seule étape d'annulation."
        ),
        {
            "ids": IDS,
            "name": {"type": "string"},
            "layer": LAYER,
            "color": COLOR,
            "material": {"type": "string", "description": "Nom du matériau (voir rhino_material) ou 'by_layer'."},
            "visible": {"type": "boolean"},
            "locked": {"type": "boolean"},
            "user_text": {"type": "object", "description": "Textes utilisateur {clé: valeur}."},
        },
        required=["ids"],
    ),
    tool(
        "rhino_transform_objects",
        (
            "Transforme des objets Rhino (une seule étape d'annulation). operation : move (vector), copy (vector), "
            "rotate (angle en degrés, axis, center), scale (factor = nombre ou [sx, sy, sz], center), mirror "
            "(plane, 'yz' par défaut, passant par center), array_linear (count, vector entre deux copies), "
            "array_polar (count, center, axis, angle total en degrés = 360). center vaut par défaut le centre de la "
            "boîte englobante. copy=true garde les originaux. Renvoie les ids obtenus."
        ),
        {
            "ids": IDS,
            "operation": enum(["move", "copy", "rotate", "scale", "mirror", "array_linear", "array_polar"],
                              "Transformation."),
            "vector": VECTOR,
            "angle": {"type": "number", "description": "Angle en degrés (rotate, array_polar)."},
            "center": POINT,
            "axis": dict(VECTOR, description="Axe de rotation (Z par défaut)."),
            "factor": {"description": "Facteur d'échelle : nombre ou [sx, sy, sz]."},
            "plane": PLANE,
            "count": {"type": "integer", "description": "Nombre total d'éléments du réseau (original compris)."},
            "copy": {"type": "boolean", "default": False},
        },
        required=["ids", "operation"],
    ),
    tool(
        "rhino_delete_objects",
        "Supprime des objets Rhino (même verrouillés). Une seule étape d'annulation (rhino_undo pour revenir).",
        {"ids": IDS},
        required=["ids"],
        destructive=True,
    ),
]
