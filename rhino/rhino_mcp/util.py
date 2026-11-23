# -*- coding: utf-8 -*-
"""Utilitaires partagés : document actif, conversions JSON <-> RhinoCommon, attributs, annulation."""
import itertools
import math

import System
import System.Collections.Generic
import System.Drawing
import Rhino
import Rhino.Geometry as G
import scriptcontext as sc

from .registry import McpError

MAX_ITEMS = 500


# --------------------------------------------------------------------------- #
# Document et objets
# --------------------------------------------------------------------------- #
def doc():
    d = Rhino.RhinoDoc.ActiveDoc
    if d is None:
        raise McpError("Aucun document Rhino actif.")
    sc.doc = d
    return d


def ensure_idle():
    """Refuse de modifier le document pendant qu'une commande Rhino est en cours (dessin, sélection...)."""
    if Rhino.Commands.Command.InCommand():
        raise McpError("Une commande Rhino est en cours : termine-la ou annule-la (Échap), puis réessaie.")


def close_dangling_undo_records(d):
    """Un script a pu laisser un enregistrement d'annulation ouvert : le refermer, sinon Ctrl+Z ne marche plus."""
    if d is None or Rhino.Commands.Command.InCommand():
        return
    for _ in range(10):
        if not d.UndoRecordingIsActive:
            break
        d.EndUndoRecord(d.CurrentUndoRecordSerialNumber)


def impl(o):
    """pythonnet 3 renvoie parfois une vue « interface » : récupère l'objet réel."""
    return getattr(o, "__implementation__", o)


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def to_guid(value):
    try:
        return System.Guid(str(value).strip())
    except Exception:
        raise McpError("Identifiant invalide : %s" % value)


def find_object(d, obj_id):
    o = d.Objects.FindId(to_guid(obj_id))
    if o is None or o.IsDeleted:
        raise McpError("Objet Rhino introuvable : %s" % obj_id)
    return o


def find_objects(d, ids):
    ids = as_list(ids)
    if not ids:
        raise McpError("Aucun identifiant fourni (ids).")
    return [find_object(d, i) for i in ids]


def iter_objects(d, include_hidden=True, include_locked=True):
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.HiddenObjects = bool(include_hidden)
    settings.LockedObjects = bool(include_locked)
    return d.Objects.GetObjectList(settings)


def layer_path(d, index):
    if 0 <= index < d.Layers.Count:
        return d.Layers[index].FullPath
    return None


TYPE_ALIASES = {
    "polysurface": "brep", "solid": "brep", "text": "annotation", "dimension": "annotation",
    "block": "instancereference", "instance": "instancereference", "dot": "textdot",
}


def filter_objects(d, layer=None, type=None, name=None, selected_only=False, include_hidden=True):
    """Objets du document filtrés par calque (chemin exact), type, nom (contient) et sélection."""
    want = str(type).strip().lower() if type else None
    want = TYPE_ALIASES.get(want, want)
    for o in iter_objects(d, include_hidden):
        if selected_only and not o.IsSelected(False):
            continue
        if want and str(o.ObjectType).lower() != want:
            continue
        if layer and (layer_path(d, o.Attributes.LayerIndex) or "").lower() != layer.strip().lower():
            continue
        if name and name.lower() not in (o.Attributes.Name or "").lower():
            continue
        yield o


# --------------------------------------------------------------------------- #
# Entrées JSON -> RhinoCommon
# --------------------------------------------------------------------------- #
def to_point(value, label="point"):
    if isinstance(value, dict):
        value = [value.get("x", 0), value.get("y", 0), value.get("z", 0)]
    try:
        vals = [float(v) for v in value]
    except Exception:
        raise McpError("%s invalide : %r (attendu [x, y, z])" % (label, value))
    if len(vals) == 2:
        vals.append(0.0)
    if len(vals) != 3:
        raise McpError("%s invalide : %r (attendu [x, y, z])" % (label, value))
    return G.Point3d(vals[0], vals[1], vals[2])


def to_vector(value, label="vecteur"):
    p = to_point(value, label)
    return G.Vector3d(p.X, p.Y, p.Z)


def to_points(values, label="points", minimum=1):
    pts = [to_point(v, label) for v in as_list(values)]
    if len(pts) < minimum:
        raise McpError("Il faut au moins %d point(s) pour %s." % (minimum, label))
    return pts


def typed_list(cls, items):
    lst = System.Collections.Generic.List[cls]()
    for item in items:
        lst.Add(item)
    return lst


_PLANES = {
    "xy": lambda: G.Plane.WorldXY, "yz": lambda: G.Plane.WorldYZ,
    "zx": lambda: G.Plane.WorldZX, "xz": lambda: G.Plane.WorldZX,
}


def to_plane(value=None, origin=None, label="plan"):
    """None/'xy'/'yz'/'zx', {"origin", "normal"} ou {"origin", "x_axis", "y_axis"} ; origin remplace l'origine."""
    if value is None or value == "":
        pl = G.Plane.WorldXY
    elif isinstance(value, str):
        key = value.strip().lower()
        if key not in _PLANES:
            raise McpError("%s inconnu : %s (attendu 'xy', 'yz', 'zx' ou {origin, normal})." % (label, value))
        pl = _PLANES[key]()
    elif isinstance(value, dict):
        o = to_point(value.get("origin", [0, 0, 0]), "origin")
        if value.get("x_axis") is not None and value.get("y_axis") is not None:
            pl = G.Plane(o, to_vector(value["x_axis"], "x_axis"), to_vector(value["y_axis"], "y_axis"))
        else:
            pl = G.Plane(o, to_vector(value.get("normal", [0, 0, 1]), "normal"))
    else:
        raise McpError("%s invalide : %r" % (label, value))
    if origin is not None:
        pl.Origin = to_point(origin, "origine")
    if not pl.IsValid:
        raise McpError("%s invalide : %r" % (label, value))
    return pl


def is_by_layer(value):
    return isinstance(value, str) and value.strip().lower().replace("-", "_") in ("by_layer", "bylayer", "layer")


def to_color(value):
    """[r, g, b], [r, g, b, a], '#RRGGBB(AA)' ou nom de couleur (anglais)."""
    if isinstance(value, System.Drawing.Color):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("#") and len(s) in (7, 9):
            try:
                r, g, b = int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)
                a = int(s[7:9], 16) if len(s) == 9 else 255
                return System.Drawing.Color.FromArgb(a, r, g, b)
            except ValueError:
                pass
        c = System.Drawing.Color.FromName(s)
        if c.IsKnownColor:
            return c
        raise McpError("Couleur inconnue : %s (attendu [r, g, b], '#RRGGBB' ou un nom comme 'red')." % value)
    try:
        vals = [max(0, min(255, int(round(float(v))))) for v in value]
    except Exception:
        raise McpError("Couleur invalide : %r" % (value,))
    if len(vals) == 3:
        return System.Drawing.Color.FromArgb(255, vals[0], vals[1], vals[2])
    if len(vals) == 4:
        return System.Drawing.Color.FromArgb(vals[3], vals[0], vals[1], vals[2])
    raise McpError("Couleur invalide : %r" % (value,))


# --------------------------------------------------------------------------- #
# RhinoCommon -> JSON
# --------------------------------------------------------------------------- #
def pt(p):
    return [round(p.X, 6), round(p.Y, 6), round(p.Z, 6)]


def rgb(c):
    return [int(c.R), int(c.G), int(c.B)]


def bbox(bb):
    return {"min": pt(bb.Min), "max": pt(bb.Max)} if bb.IsValid else None


def object_summary(o):
    d = o.Document or Rhino.RhinoDoc.ActiveDoc
    bb = o.Geometry.GetBoundingBox(True) if o.Geometry is not None else G.BoundingBox.Empty
    return {
        "id": str(o.Id),
        "type": str(o.ObjectType),
        "name": o.Attributes.Name,
        "layer": layer_path(d, o.Attributes.LayerIndex),
        "bbox_min": pt(bb.Min) if bb.IsValid else None,
        "bbox_max": pt(bb.Max) if bb.IsValid else None,
    }


def geometry_summary(g):
    info = {"type": g.GetType().Name}
    bb = g.GetBoundingBox(True)
    if bb.IsValid:
        info["bbox"] = bbox(bb)
    if isinstance(g, G.Point):
        info["location"] = pt(g.Location)
    elif isinstance(g, G.Curve):
        info["length"] = round(g.GetLength(), 6)
        info["closed"] = g.IsClosed
    elif isinstance(g, G.Brep):
        info["faces"] = g.Faces.Count
        info["solid"] = g.IsSolid
    elif isinstance(g, G.Mesh):
        info["vertices"] = g.Vertices.Count
        info["faces"] = g.Faces.Count
    return info


def jsonable(v, depth=0):
    """Convertit (récursivement) une valeur Python/.NET/RhinoCommon en données JSON lisibles."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if depth > 8:
        return str(v)
    if isinstance(v, dict):
        return {str(k): jsonable(x, depth + 1) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [jsonable(x, depth + 1) for x in list(v)[:MAX_ITEMS]]
    if isinstance(v, System.Guid):
        return str(v)
    if isinstance(v, (G.Point3d, G.Vector3d, G.Point3f, G.Vector3f)):
        return pt(v)
    if isinstance(v, (G.Point2d, G.Vector2d, G.Point2f)):
        return [round(v.X, 6), round(v.Y, 6)]
    if isinstance(v, G.BoundingBox):
        return bbox(v)
    if isinstance(v, G.Interval):
        return [v.T0, v.T1]
    if isinstance(v, G.Line):
        return {"from": pt(v.From), "to": pt(v.To)}
    if isinstance(v, G.Plane):
        return {"origin": pt(v.Origin), "x_axis": pt(v.XAxis), "y_axis": pt(v.YAxis), "normal": pt(v.ZAxis)}
    if isinstance(v, G.Circle):
        return {"center": pt(v.Center), "radius": v.Radius, "normal": pt(v.Normal)}
    if isinstance(v, System.Drawing.Color):
        return rgb(v)
    if isinstance(v, System.Enum):
        return str(v)
    if isinstance(v, System.Decimal):
        return float(System.Convert.ToDouble(v))
    if isinstance(v, System.DateTime):
        return v.ToString("o")
    if isinstance(v, G.GeometryBase):
        return geometry_summary(v)
    if isinstance(v, Rhino.DocObjects.RhinoObject):
        return object_summary(v)
    if isinstance(v, System.Collections.IDictionary):
        return {str(k): jsonable(v[k], depth + 1) for k in itertools.islice(v.Keys, MAX_ITEMS)}
    if isinstance(v, System.Collections.IEnumerable):
        return [jsonable(x, depth + 1) for x in itertools.islice(v, MAX_ITEMS)]
    return str(v)


# --------------------------------------------------------------------------- #
# Création d'objets
# --------------------------------------------------------------------------- #
def layer_index(d, path, create=True):
    path = (path or "").strip()
    if not path:
        raise McpError("Nom de calque vide.")
    idx = d.Layers.FindByFullPath(path, -1)
    if idx < 0:
        if not create:
            raise McpError("Calque introuvable : %s" % path)
        idx = d.Layers.AddPath(path)
        if idx < 0:
            raise McpError("Impossible de créer le calque : %s" % path)
    return idx


def attributes(d, layer=None, name=None, color=None):
    a = d.CreateDefaultAttributes()
    if layer:
        a.LayerIndex = layer_index(d, layer)
    if name:
        a.Name = name
    if color is not None and not is_by_layer(color):
        a.ObjectColor = to_color(color)
        a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
    return a


def add_geometry(d, geometry, attrs):
    if isinstance(geometry, G.Point3d):
        gid = d.Objects.AddPoint(geometry, attrs)
    else:
        gid = d.Objects.Add(geometry, attrs)
    if gid == System.Guid.Empty:
        raise McpError("Rhino a refusé la géométrie (%s) : elle est sans doute invalide." % type(geometry).__name__)
    return gid


def created(d, ids):
    """Résultat standard d'une création : identifiants + résumé des objets."""
    objs = [d.Objects.FindId(i) for i in ids]
    return {
        "count": len(ids),
        "ids": [str(i) for i in ids],
        "objects": [object_summary(o) for o in objs[:MAX_ITEMS] if o is not None],
    }


class Undo(object):
    """`with Undo("libellé") as d:` regroupe les modifications en une seule étape d'annulation."""

    def __init__(self, label):
        self.label = label
        self.doc = None
        self.record = 0

    def __enter__(self):
        ensure_idle()
        self.doc = doc()
        self.record = self.doc.BeginUndoRecord("MCP : " + self.label)
        return self.doc

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.record:
                self.doc.EndUndoRecord(self.record)
        finally:
            self.doc.Views.Redraw()
        return False
