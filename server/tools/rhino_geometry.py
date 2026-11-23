# -*- coding: utf-8 -*-
"""Outils Rhino : création et opérations géométriques."""
from .common import COLOR, IDS, LAYER, NAME, PLANE, POINT, POINTS, VECTOR, enum, tool

SHAPES = ["point", "line", "polyline", "curve", "circle", "arc", "ellipse", "rectangle", "polygon",
          "plane_surface", "sphere", "box", "cylinder", "cone", "torus", "mesh"]
OPERATIONS = ["boolean_union", "boolean_difference", "boolean_intersection", "extrude", "loft", "revolve",
              "sweep1", "pipe", "offset", "join", "explode", "cap", "mesh", "intersect"]
NUMBER = {"type": "number"}

TOOLS = [
    tool(
        "rhino_create_geometry",
        (
            "Crée de la géométrie dans Rhino (unités du document). Paramètres selon le type :\n"
            "- point : point (ou points)\n- line : start, end\n- polyline : points, closed\n"
            "- curve : points, degree (3), interpolate (true = passe par les points, false = points de contrôle), "
            "closed\n- circle : center, radius, plane\n- arc : center, radius, start_angle, end_angle (degrés), "
            "plane — ou points (3 points)\n- ellipse : center, radius (x), radius2 (y), plane\n"
            "- rectangle : corner, width, height, plane — ou corner + corner2\n- polygon : center, radius, sides, "
            "plane\n- plane_surface : corner, width, height, plane\n- sphere : center, radius\n"
            "- box : corner, width (x), depth (y), height (z), plane — ou corner + corner2 (diagonale)\n"
            "- cylinder / cone : center (base), radius, height, axis (Z par défaut), cap\n"
            "- torus : center, radius (grand), radius2 (petit), plane\n"
            "- mesh : vertices [[x,y,z]...], faces [[i,j,k] ou [i,j,k,l]...]\n"
            "Options communes : layer, name, color. Une seule étape d'annulation ; renvoie les ids créés."
        ),
        {
            "type": enum(SHAPES, "Forme à créer."),
            "point": POINT, "points": POINTS, "start": POINT, "end": POINT, "center": POINT,
            "corner": POINT, "corner2": POINT,
            "radius": NUMBER, "radius2": NUMBER, "width": NUMBER, "height": NUMBER, "depth": NUMBER,
            "sides": {"type": "integer"}, "start_angle": NUMBER, "end_angle": NUMBER,
            "plane": PLANE, "axis": VECTOR,
            "degree": {"type": "integer", "default": 3}, "closed": {"type": "boolean", "default": False},
            "interpolate": {"type": "boolean", "default": True}, "cap": {"type": "boolean", "default": True},
            "vertices": POINTS, "faces": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
            "layer": LAYER, "name": NAME, "color": COLOR,
        },
        required=["type"],
    ),
    tool(
        "rhino_geometry_operation",
        (
            "Opérations géométriques sur des objets Rhino (ids) :\n"
            "- boolean_union (ids), boolean_difference (ids moins other_ids), boolean_intersection (ids et "
            "other_ids) : solides fermés\n"
            "- extrude : courbes, vector (ou height le long de Z), cap\n- loft : courbes dans l'ordre, closed, cap\n"
            "- revolve : courbes, axis [[x,y,z], [x,y,z]], angle (360 par défaut)\n"
            "- sweep1 : profils (ids) le long de rail_id, cap\n- pipe : courbes, radius, cap\n"
            "- offset : courbes, distance (signe = côté), plane\n- join : courbes ou surfaces\n"
            "- explode : courbes (segments) ou polysurfaces (faces)\n- cap : boucher les trous plans\n"
            "- mesh : convertir surfaces/solides en maillage\n- intersect : ids avec other_ids (courbes/points)\n"
            "delete_input : supprimer les objets d'origine (par défaut oui pour booléens, join, explode, cap ; "
            "non sinon). Résultat sur le calque du premier objet, sauf layer/name/color. Une étape d'annulation."
        ),
        {
            "operation": enum(OPERATIONS, "Opération."),
            "ids": IDS,
            "other_ids": dict(IDS, description="Second groupe d'objets (booléens, intersect)."),
            "rail_id": {"type": "string", "description": "sweep1 : courbe rail."},
            "vector": VECTOR, "height": NUMBER, "distance": NUMBER, "radius": NUMBER,
            "axis": dict(POINTS, description="revolve : axe [[x,y,z], [x,y,z]]."),
            "angle": NUMBER, "plane": PLANE,
            "cap": {"type": "boolean", "default": True}, "closed": {"type": "boolean", "default": False},
            "delete_input": {"type": "boolean"},
            "layer": LAYER, "name": NAME, "color": COLOR,
        },
        required=["operation", "ids"],
    ),
]
