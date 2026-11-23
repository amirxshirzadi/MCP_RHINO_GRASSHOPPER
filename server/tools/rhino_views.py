# -*- coding: utf-8 -*-
"""Outils Rhino : vues, captures, annotations et mises en page."""
from .common import COLOR, IDS, LAYER, NAME, PLANE, POINT, POINTS, enum, tool

PROJECTIONS = ["top", "bottom", "left", "right", "front", "back", "perspective", "two_point_perspective"]
DISPLAY = {"type": "string", "description": "Mode d'affichage : Wireframe, Shaded, Rendered, Ghosted, X-Ray, "
                                            "Technical, Artistic, Pen, Arctic, Raytraced..."}

TOOLS = [
    tool(
        "rhino_capture_view",
        (
            "Capture une vue Rhino en image PNG (vue active par défaut) pour voir le résultat. display_mode : mode "
            "d'affichage le temps de la capture (puis retour au mode de l'utilisateur) ; zoom_extents : cadrer tout."
        ),
        {
            "view": {"type": "string", "description": "Nom de la vue (Perspective, Top, ...)."},
            "width": {"type": "integer", "default": 900},
            "height": {"type": "integer", "default": 600},
            "display_mode": DISPLAY,
            "zoom_extents": {"type": "boolean", "default": False},
        },
        read_only=True,
    ),
    tool(
        "rhino_view",
        (
            "Vues Rhino. action : list (vues, vues nommées, modes d'affichage, mises en page) ; set (view ; "
            "projection, display_mode, camera_location / camera_target, lens en mm, cplane = plan de construction, "
            "maximize) ; zoom (ids = cadrer ces objets, sinon zoom = 'extents' ou 'selected') ; save_named / "
            "restore_named / delete_named (name). La vue active est utilisée si view n'est pas précisé."
        ),
        {
            "action": enum(["list", "set", "zoom", "save_named", "restore_named", "delete_named"], "Opération.",
                           default="list"),
            "view": {"type": "string"},
            "projection": enum(PROJECTIONS, "Projection standard."),
            "display_mode": DISPLAY,
            "ids": IDS,
            "zoom": enum(["extents", "selected"], "zoom : tout ou la sélection.", default="extents"),
            "name": {"type": "string", "description": "Nom de la vue nommée."},
            "camera_location": POINT,
            "camera_target": POINT,
            "lens": {"type": "number", "description": "Focale équivalente 35 mm (perspective)."},
            "cplane": PLANE,
            "maximize": {"type": "boolean"},
        },
    ),
    tool(
        "rhino_annotation",
        (
            "Annotations Rhino. type : text (text, point, height, rotation en degrés, plane), dot (text, point), "
            "dimension (cote alignée : start, end, offset = point de la ligne de cote, facultatif), "
            "linear_dimension (cote horizontale/verticale), leader (points, text), hatch (ids de courbes fermées "
            "planes, pattern 'Solid'/'Hatch1'/'Grid'..., scale, rotation). Options : layer, name, color."
        ),
        {
            "type": enum(["text", "dot", "dimension", "linear_dimension", "leader", "hatch"], "Annotation."),
            "text": {"type": "string"},
            "point": POINT, "points": POINTS, "start": POINT, "end": POINT, "offset": POINT,
            "height": {"type": "number", "description": "Hauteur du texte."},
            "plane": PLANE,
            "ids": IDS,
            "pattern": {"type": "string", "default": "Solid"},
            "scale": {"type": "number", "default": 1.0},
            "rotation": {"type": "number", "default": 0.0},
            "layer": LAYER, "name": NAME, "color": COLOR,
        },
        required=["type"],
    ),
    tool(
        "rhino_layout",
        (
            "Mises en page Rhino et PDF. action : list ; create (name, width/height de la feuille dans les unités de "
            "mise en page, 420 x 297 = A3 paysage en mm ; details = liste de fenêtres {projection, display_mode, "
            "rect [x0, y0, x1, y1], title}, une perspective pleine page par défaut) ; export_pdf (path ; layouts = "
            "noms des mises en page, toutes par défaut ; views = vues du modèle à ajouter ; dpi ; overwrite) ; "
            "delete (name)."
        ),
        {
            "action": enum(["list", "create", "export_pdf", "delete"], "Opération.", default="list"),
            "name": {"type": "string"},
            "width": {"type": "number", "default": 420},
            "height": {"type": "number", "default": 297},
            "details": {"type": "array", "items": {"type": "object"}},
            "path": {"type": "string"},
            "layouts": {"type": "array", "items": {"type": "string"}},
            "views": {"type": "array", "items": {"type": "string"}},
            "dpi": {"type": "integer", "default": 300},
            "overwrite": {"type": "boolean", "default": False},
        },
    ),
]
