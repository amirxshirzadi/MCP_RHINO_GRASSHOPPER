# -*- coding: utf-8 -*-
"""Rhino : objets du document (lister, détailler, sélectionner, modifier, transformer, supprimer)."""
import math

import System
import Rhino
import Rhino.Geometry as G

from .registry import McpError, command
from .util import (MAX_ITEMS, Undo, as_list, created, doc, filter_objects, find_material, find_objects,
                   geometry_summary, is_by_layer, layer_index, object_summary, pt, rgb, to_color, to_plane,
                   to_point, to_vector)


@command("rhino_get_objects", "get_objects")
def rhino_get_objects(layer=None, selected_only=False, type=None, name=None, include_hidden=True,
                      limit=200, offset=0):
    d = doc()
    out = []
    total = 0
    for o in filter_objects(d, layer, type, name, selected_only, include_hidden):
        if total >= offset and len(out) < limit:
            out.append(object_summary(o))
        total += 1
    return {"total": total, "offset": offset, "objects": out}


# --------------------------------------------------------------------------- #
# Détails
# --------------------------------------------------------------------------- #
def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def geometry_details(g):
    info = geometry_summary(g)
    if isinstance(g, G.Curve):
        info.update({"degree": g.Degree, "planar": _safe(g.IsPlanar), "start": pt(g.PointAtStart),
                     "end": pt(g.PointAtEnd)})
        ok, circle = _safe(g.TryGetCircle, (False, None))
        if ok:
            info["circle"] = {"center": pt(circle.Center), "radius": round(circle.Radius, 6)}
        ok, polyline = _safe(g.TryGetPolyline, (False, None))
        if ok:
            info["vertices"] = [pt(p) for p in list(polyline)[:MAX_ITEMS]]
        if g.IsClosed and info.get("planar"):
            amp = _safe(lambda: G.AreaMassProperties.Compute(g))
            if amp:
                info["area"] = round(amp.Area, 6)
    elif isinstance(g, (G.Brep, G.Extrusion, G.Surface, G.SubD)):
        brep = _safe(lambda: G.Brep.TryConvertBrep(g))
        if brep is not None:
            info.update({"faces": brep.Faces.Count, "edges": brep.Edges.Count, "solid": brep.IsSolid})
            amp = _safe(lambda: G.AreaMassProperties.Compute(brep))
            if amp:
                info["area"] = round(amp.Area, 6)
                info["centroid"] = pt(amp.Centroid)
            if brep.IsSolid:
                vmp = _safe(lambda: G.VolumeMassProperties.Compute(brep))
                if vmp:
                    info["volume"] = round(vmp.Volume, 6)
    elif isinstance(g, G.Mesh):
        info["closed"] = g.IsClosed
        amp = _safe(lambda: G.AreaMassProperties.Compute(g))
        if amp:
            info["area"] = round(amp.Area, 6)
        if g.IsClosed:
            vmp = _safe(lambda: G.VolumeMassProperties.Compute(g))
            if vmp:
                info["volume"] = round(vmp.Volume, 6)
    elif isinstance(g, G.TextEntity):
        info.update({"text": g.PlainText, "height": g.TextHeight, "origin": pt(g.Plane.Origin)})
    elif isinstance(g, G.TextDot):
        info.update({"text": g.Text, "point": pt(g.Point)})
    elif isinstance(g, G.Dimension):
        info.update({"value": _safe(lambda: g.NumericValue), "text": _safe(lambda: g.PlainText)})
    return info


def object_details(d, o):
    a = o.Attributes
    info = object_summary(o)
    material = _safe(lambda: o.RenderMaterial)
    user_text = {}
    strings = a.GetUserStrings()
    for key in strings.AllKeys:
        user_text[key] = a.GetUserString(key)
    groups = [d.Groups.GroupName(i) for i in (a.GetGroupList() or [])]
    info.update({
        "visible": o.Visible, "locked": o.IsLocked, "hidden": o.IsHidden, "selected": bool(o.IsSelected(False)),
        "color": rgb(a.ObjectColor), "color_source": str(a.ColorSource), "display_color": rgb(a.DrawColor(d)),
        "material": material.Name if material is not None else None, "material_source": str(a.MaterialSource),
        "user_text": user_text, "groups": groups, "geometry": geometry_details(o.Geometry),
    })
    if isinstance(o, Rhino.DocObjects.InstanceObject):
        info["block"] = o.InstanceDefinition.Name
        info["insertion_point"] = pt(o.InsertionPoint)
    return info


@command("rhino_get_object_details")
def rhino_get_object_details(ids):
    d = doc()
    return {"objects": [object_details(d, o) for o in find_objects(d, ids)]}


# --------------------------------------------------------------------------- #
# Sélection
# --------------------------------------------------------------------------- #
@command("rhino_select_objects")
def rhino_select_objects(action="select", ids=None, layer=None, type=None, name=None):
    d = doc()
    action = (action or "select").strip().lower()
    if action == "get":
        sel = list(d.Objects.GetSelectedObjects(False, False))
        return {"selected_count": len(sel), "objects": [object_summary(o) for o in sel[:MAX_ITEMS]]}
    if action == "clear":
        d.Objects.UnselectAll(True)
        d.Views.Redraw()
        return {"selected_count": 0}
    if action not in ("select", "unselect"):
        raise McpError("Action inconnue : %s (select, unselect, clear, get)." % action)
    if ids:
        targets = find_objects(d, ids)
    elif layer or type or name:
        targets = list(filter_objects(d, layer, type, name, include_hidden=False))
    else:
        raise McpError("Indique ids ou un filtre (layer, type, name).")
    changed = 0
    for o in targets:
        if action == "select":
            if o.Select(True):
                changed += 1
        else:
            o.Select(False)
            changed += 1
    d.Views.Redraw()
    sel = list(d.Objects.GetSelectedObjects(False, False))
    return {"changed": changed, "selected_count": len(sel), "selected": [str(o.Id) for o in sel[:MAX_ITEMS]]}


# --------------------------------------------------------------------------- #
# Modification des attributs
# --------------------------------------------------------------------------- #
@command("rhino_modify_objects")
def rhino_modify_objects(ids, name=None, layer=None, color=None, material=None, visible=None, locked=None,
                         user_text=None):
    with Undo("modifier des objets") as d:
        objs = find_objects(d, ids)
        render_material = None
        if material is not None and not is_by_layer(material):
            render_material = find_material(d, material)
        for o in objs:
            was_locked = o.IsLocked
            if was_locked:
                d.Objects.Unlock(o.Id, True)
            a = d.Objects.FindId(o.Id).Attributes.Duplicate()
            if name is not None:
                a.Name = name
            if layer:
                a.LayerIndex = layer_index(d, layer)
            if color is not None:
                if is_by_layer(color):
                    a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
                else:
                    a.ObjectColor = to_color(color)
                    a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            if material is not None and is_by_layer(material):
                a.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromLayer
            for key, value in (user_text or {}).items():
                if value is None:
                    a.DeleteUserString(str(key))
                else:
                    a.SetUserString(str(key), str(value))
            d.Objects.ModifyAttributes(o.Id, a, True)
            if render_material is not None:
                current = d.Objects.FindId(o.Id)
                current.RenderMaterial = render_material
                current.CommitChanges()
            if visible is not None:
                (d.Objects.Show if visible else d.Objects.Hide)(o.Id, True)
            if locked or (was_locked and locked is None):
                d.Objects.Lock(o.Id, True)
        return {"objects": [object_summary(d.Objects.FindId(o.Id)) for o in objs]}


# --------------------------------------------------------------------------- #
# Transformations
# --------------------------------------------------------------------------- #
def _union_bbox(objs):
    bb = G.BoundingBox.Empty
    for o in objs:
        bb = G.BoundingBox.Union(bb, o.Geometry.GetBoundingBox(True))
    return bb


def _require(value, label):
    if value is None:
        raise McpError("Paramètre requis pour cette opération : %s" % label)
    return value


@command("rhino_transform_objects")
def rhino_transform_objects(ids, operation, vector=None, angle=None, center=None, axis=None, factor=None,
                            plane=None, count=None, copy=False):
    op = (operation or "").strip().lower()
    with Undo(op or "transformer") as d:
        objs = find_objects(d, ids)
        c = to_point(center, "center") if center is not None else _union_bbox(objs).Center
        ax = to_vector(axis, "axis") if axis is not None else G.Vector3d.ZAxis
        xforms = []
        if op in ("move", "copy"):
            xforms = [G.Transform.Translation(to_vector(_require(vector, "vector")))]
            copy = copy or op == "copy"
        elif op == "rotate":
            xforms = [G.Transform.Rotation(math.radians(float(_require(angle, "angle"))), ax, c)]
        elif op == "scale":
            f = _require(factor, "factor")
            if isinstance(f, (list, tuple)):
                sx, sy, sz = [float(v) for v in (list(f) + [1, 1, 1])[:3]]
                xforms = [G.Transform.Scale(G.Plane(c, G.Vector3d.ZAxis), sx, sy, sz)]
            else:
                xforms = [G.Transform.Scale(c, float(f))]
        elif op == "mirror":
            pl = to_plane(plane if plane is not None else "yz", origin=center)
            xforms = [G.Transform.Mirror(pl.Origin, pl.ZAxis)]
        elif op == "array_linear":
            n = int(_require(count, "count"))
            step = to_vector(_require(vector, "vector"))
            xforms = [G.Transform.Translation(step * float(k)) for k in range(1, n)]
            copy = True
        elif op == "array_polar":
            n = int(_require(count, "count"))
            if center is None:
                raise McpError("array_polar : indique le centre de rotation (center).")
            total = float(angle) if angle is not None else 360.0
            step = total / n if abs(total) >= 360 else total / max(n - 1, 1)
            xforms = [G.Transform.Rotation(math.radians(step * k), ax, c) for k in range(1, n)]
            copy = True
        else:
            raise McpError("Opération inconnue : %s (move, copy, rotate, scale, mirror, array_linear, "
                           "array_polar)." % operation)
        result_ids = []
        for xf in xforms:
            for o in objs:
                new_id = d.Objects.Transform(o.Id, xf, not copy)
                if new_id == System.Guid.Empty:
                    raise McpError("Transformation refusée pour l'objet %s (verrouillé ?)." % o.Id)
                result_ids.append(new_id)
        result = created(d, result_ids)
        result["operation"] = op
        result["copies"] = bool(copy)
        return result


# --------------------------------------------------------------------------- #
# Suppression
# --------------------------------------------------------------------------- #
@command("rhino_delete_objects")
def rhino_delete_objects(ids):
    with Undo("supprimer") as d:
        deleted, failed = [], []
        for o in find_objects(d, as_list(ids)):
            if o.IsLocked:
                d.Objects.Unlock(o.Id, True)
            (deleted if d.Objects.Delete(o.Id, True) else failed).append(str(o.Id))
        return {"deleted": deleted, "failed": failed}
