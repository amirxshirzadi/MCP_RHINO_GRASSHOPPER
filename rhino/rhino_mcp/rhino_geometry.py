# -*- coding: utf-8 -*-
"""Rhino : création de géométrie et opérations géométriques."""
import math

import Rhino.Geometry as G
from Rhino.Geometry.Intersect import Intersection

from .registry import McpError, command
from .util import (Undo, add_geometry, attributes, created, enum_value, find_objects, to_plane, to_point, to_points,
                   to_vector, typed_list)

SHAPES = ("point", "line", "polyline", "curve", "circle", "arc", "ellipse", "rectangle", "polygon",
          "plane_surface", "sphere", "box", "cylinder", "cone", "torus", "mesh")
OPERATIONS = ("boolean_union", "boolean_difference", "boolean_intersection", "extrude", "loft", "revolve",
              "sweep1", "pipe", "offset", "join", "explode", "cap", "mesh", "intersect")
# Comme dans Rhino, ces opérations remplacent leurs objets d'origine (sauf delete_input=false).
REPLACES_INPUT = ("boolean_union", "boolean_difference", "boolean_intersection", "join", "explode", "cap")


def _need(value, label, kind):
    if value is None:
        raise McpError("%s : paramètre « %s » requis." % (kind, label))
    return value


def _unit(v):
    length = v.Length
    if length <= 0:
        raise McpError("Axe de longueur nulle.")
    return G.Vector3d(v.X / length, v.Y / length, v.Z / length)


# --------------------------------------------------------------------------- #
# Création
# --------------------------------------------------------------------------- #
def _shape(kind, a):
    """Géométries (RhinoCommon) pour un type de forme ; `a` = dictionnaire des paramètres de l'outil."""
    need = lambda key: _need(a.get(key), key, kind)  # noqa: E731
    if kind == "point":
        return to_points(a["points"]) if a.get("points") else [to_point(need("point"))]
    if kind == "line":
        return [G.LineCurve(to_point(need("start"), "start"), to_point(need("end"), "end"))]
    if kind == "polyline":
        pts = to_points(need("points"), "points", 2)
        if a.get("closed") and pts[0].DistanceTo(pts[-1]) > 1e-9:
            pts.append(pts[0])
        return [G.PolylineCurve(typed_list(G.Point3d, pts))]
    if kind == "curve":
        pts = to_points(need("points"), "points", 2)
        degree = int(a.get("degree") or 3)
        if a.get("interpolate", True):
            if a.get("closed"):
                c = G.Curve.CreateInterpolatedCurve(typed_list(G.Point3d, pts), degree, G.CurveKnotStyle.ChordPeriodic)
            else:
                c = G.Curve.CreateInterpolatedCurve(typed_list(G.Point3d, pts), degree)
        else:
            c = G.NurbsCurve.Create(bool(a.get("closed")), min(degree, len(pts) - 1), typed_list(G.Point3d, pts))
        if c is None:
            raise McpError("curve : courbe impossible avec ces points.")
        return [c]
    if kind == "circle":
        return [G.ArcCurve(G.Circle(to_plane(a.get("plane"), origin=need("center")), float(need("radius"))))]
    if kind == "arc":
        if a.get("points"):
            p = to_points(a["points"], "points", 3)
            arc = G.Arc(p[0], p[1], p[2])
        else:
            circle = G.Circle(to_plane(a.get("plane"), origin=need("center")), float(need("radius")))
            arc = G.Arc(circle, G.Interval(math.radians(float(a.get("start_angle") or 0)),
                                           math.radians(float(need("end_angle")))))
        if not arc.IsValid:
            raise McpError("arc : arc invalide avec ces paramètres.")
        return [G.ArcCurve(arc)]
    if kind == "ellipse":
        pl = to_plane(a.get("plane"), origin=need("center"))
        return [G.Ellipse(pl, float(need("radius")), float(need("radius2"))).ToNurbsCurve()]
    if kind == "rectangle":
        if a.get("corner") is not None and a.get("corner2") is not None:
            p0, p1 = to_point(a["corner"], "corner"), to_point(a["corner2"], "corner2")
            rect = G.Rectangle3d(to_plane(a.get("plane"), origin=a["corner"]), p0, p1)
        else:
            pl = to_plane(a.get("plane"), origin=need("corner"))
            rect = G.Rectangle3d(pl, float(need("width")), float(need("height")))
        return [rect.ToNurbsCurve()]
    if kind == "polygon":
        circle = G.Circle(to_plane(a.get("plane"), origin=need("center")), float(need("radius")))
        return [G.PolylineCurve(G.Polyline.CreateInscribedPolygon(circle, int(need("sides"))))]
    if kind == "plane_surface":
        pl = to_plane(a.get("plane"), origin=need("corner"))
        return [G.PlaneSurface(pl, G.Interval(0, float(need("width"))), G.Interval(0, float(need("height"))))]
    if kind == "sphere":
        return [G.Sphere(to_point(need("center"), "center"), float(need("radius"))).ToBrep()]
    if kind == "box":
        if a.get("corner") is not None and a.get("corner2") is not None:
            pts = typed_list(G.Point3d, [to_point(a["corner"], "corner"), to_point(a["corner2"], "corner2")])
            return [G.Box(G.BoundingBox(pts)).ToBrep()]
        pl = to_plane(a.get("plane"), origin=need("corner"))
        box = G.Box(pl, G.Interval(0, float(need("width"))), G.Interval(0, float(need("depth"))),
                    G.Interval(0, float(need("height"))))
        return [box.ToBrep()]
    if kind in ("cylinder", "cone"):
        base = to_point(need("center"), "center")
        axis = _unit(to_vector(a["axis"], "axis")) if a.get("axis") is not None else G.Vector3d.ZAxis
        h, r, cap = float(need("height")), float(need("radius")), bool(a.get("cap", True))
        if kind == "cylinder":
            return [G.Cylinder(G.Circle(G.Plane(base, axis), r), h).ToBrep(cap, cap)]
        apex = base + axis * h  # Cone : sommet à l'origine du plan, base à `h` le long de son axe Z
        return [G.Cone(G.Plane(apex, G.Vector3d(-axis.X, -axis.Y, -axis.Z)), h, r).ToBrep(cap)]
    if kind == "torus":
        torus = G.Torus(to_plane(a.get("plane"), origin=need("center")), float(need("radius")), float(need("radius2")))
        return [G.Brep.CreateFromSurface(torus.ToNurbsSurface())]
    if kind == "mesh":
        m = G.Mesh()
        for v in need("vertices"):
            p = to_point(v, "vertex")
            m.Vertices.Add(p.X, p.Y, p.Z)
        for f in need("faces"):
            idx = [int(i) for i in f]
            if len(idx) == 3:
                m.Faces.AddFace(idx[0], idx[1], idx[2])
            elif len(idx) == 4:
                m.Faces.AddFace(idx[0], idx[1], idx[2], idx[3])
            else:
                raise McpError("mesh : chaque face doit avoir 3 ou 4 indices de sommets.")
        m.Normals.ComputeNormals()
        m.Compact()
        if not m.IsValid:
            raise McpError("mesh : maillage invalide (indices de sommets ?).")
        return [m]
    raise McpError("Type inconnu : %s. Types : %s." % (kind, ", ".join(SHAPES)))


@command("rhino_create_geometry")
def rhino_create_geometry(type, point=None, points=None, start=None, end=None, center=None, radius=None,
                          radius2=None, width=None, height=None, depth=None, corner=None, corner2=None, sides=None,
                          start_angle=None, end_angle=None, plane=None, axis=None, degree=3, closed=False,
                          interpolate=True, vertices=None, faces=None, cap=True, layer=None, name=None, color=None):
    kind = (type or "").strip().lower()
    params = dict(point=point, points=points, start=start, end=end, center=center, radius=radius, radius2=radius2,
                  width=width, height=height, depth=depth, corner=corner, corner2=corner2, sides=sides,
                  start_angle=start_angle, end_angle=end_angle, plane=plane, axis=axis, degree=degree,
                  closed=closed, interpolate=interpolate, vertices=vertices, faces=faces, cap=cap)
    with Undo("créer " + kind) as d:
        geometries = _shape(kind, params)
        attrs = attributes(d, layer, name, color)
        return created(d, [add_geometry(d, g, attrs) for g in geometries])


# --------------------------------------------------------------------------- #
# Opérations
# --------------------------------------------------------------------------- #
def _brep(o):
    b = G.Brep.TryConvertBrep(o.Geometry)
    if b is None:
        raise McpError("L'objet %s (%s) n'est pas une surface ou un solide." % (o.Id, o.ObjectType))
    return b


def _curve(o):
    if not isinstance(o.Geometry, G.Curve):
        raise McpError("L'objet %s (%s) n'est pas une courbe." % (o.Id, o.ObjectType))
    return o.Geometry


def _cap(breps, tol, cap):
    return [(b.CapPlanarHoles(tol) or b) if cap else b for b in breps]


def _intersect(a, b, tol):
    """Courbes et points d'intersection entre deux géométries (courbe, surface, solide)."""
    ga, gb = a.Geometry, b.Geometry
    out = []
    if isinstance(ga, G.Curve) and isinstance(gb, G.Curve):
        for ev in Intersection.CurveCurve(ga, gb, tol, tol) or []:
            out.append(ev.PointA if ev.IsPoint else ga.Trim(ev.OverlapA))
        return out
    if isinstance(gb, G.Curve):
        a, b, ga, gb = b, a, gb, ga
    if isinstance(ga, G.Curve):
        res = Intersection.CurveBrep(ga, _brep(b), tol)
    else:
        res = Intersection.BrepBrep(_brep(a), _brep(b), tol)
    for part in list(res)[1:]:  # (ok, courbes, points[, paramètres])
        for item in part or []:
            if isinstance(item, (G.Curve, G.Point3d)):
                out.append(item)
    return out


@command("rhino_geometry_operation")
def rhino_geometry_operation(operation, ids, other_ids=None, rail_id=None, vector=None, height=None, distance=None,
                             radius=None, axis=None, angle=None, plane=None, cap=True, closed=False,
                             delete_input=None, layer=None, name=None, color=None):
    op = (operation or "").strip().lower()
    if op not in OPERATIONS:
        raise McpError("Opération inconnue : %s. Opérations : %s." % (operation, ", ".join(OPERATIONS)))
    with Undo(op) as d:
        tol = d.ModelAbsoluteTolerance
        objs = find_objects(d, ids)
        used = list(objs)
        results = []
        if op.startswith("boolean_"):
            first = typed_list(G.Brep, [_brep(o) for o in objs])
            if op == "boolean_union":
                if len(objs) < 2:
                    raise McpError("boolean_union : il faut au moins deux objets.")
                res = G.Brep.CreateBooleanUnion(first, tol)
            else:
                others = find_objects(d, _need(other_ids, "other_ids", op))
                used += others
                fn = G.Brep.CreateBooleanDifference if op == "boolean_difference" else G.Brep.CreateBooleanIntersection
                res = fn(first, typed_list(G.Brep, [_brep(o) for o in others]), tol)
            if not res:
                raise McpError("%s impossible (objets disjoints, non fermés ou mal orientés ?)." % op)
            results = list(res)
        elif op == "extrude":
            vec = to_vector(vector) if vector is not None else G.Vector3d(0, 0, float(_need(height, "height", op)))
            for o in objs:
                c = _curve(o)
                srf = G.Surface.CreateExtrusion(c, vec)
                if srf is None:
                    raise McpError("extrude : extrusion impossible pour %s." % o.Id)
                results += _cap([srf.ToBrep()], tol, cap and c.IsClosed)
        elif op == "loft":
            if len(objs) < 2:
                raise McpError("loft : il faut au moins deux courbes (dans l'ordre).")
            res = G.Brep.CreateFromLoft(typed_list(G.Curve, [_curve(o) for o in objs]), G.Point3d.Unset,
                                        G.Point3d.Unset, G.LoftType.Normal, bool(closed))
            results = _cap(list(res or []), tol, cap)
        elif op == "revolve":
            p = to_points(_need(axis, "axis ([[x,y,z], [x,y,z]])", op), "axis", 2)
            sweep = math.radians(float(angle if angle is not None else 360))
            for o in objs:
                results.append(G.RevSurface.Create(_curve(o), G.Line(p[0], p[1]), 0.0, sweep).ToBrep())
        elif op == "sweep1":
            rail_obj = find_objects(d, [_need(rail_id, "rail_id", op)])[0]
            used.append(rail_obj)
            res = G.Brep.CreateFromSweep(_curve(rail_obj), typed_list(G.Curve, [_curve(o) for o in objs]),
                                         bool(closed), tol)
            results = _cap(list(res or []), tol, cap)
        elif op == "pipe":
            mode = enum_value(G.PipeCapMode, "Flat" if cap else "None")
            for o in objs:
                results += list(G.Brep.CreatePipe(_curve(o), float(_need(radius, "radius", op)), False, mode, True,
                                                  tol, d.ModelAngleToleranceRadians) or [])
        elif op == "offset":
            pl = to_plane(plane)
            for o in objs:
                results += list(_curve(o).Offset(pl, float(_need(distance, "distance", op)), tol,
                                                 G.CurveOffsetCornerStyle.Sharp) or [])
        elif op == "join":
            curves = [o.Geometry for o in objs if isinstance(o.Geometry, G.Curve)]
            breps = [_brep(o) for o in objs if not isinstance(o.Geometry, G.Curve)]
            if curves:
                results += list(G.Curve.JoinCurves(typed_list(G.Curve, curves), tol) or [])
            if breps:
                results += list(G.Brep.JoinBreps(typed_list(G.Brep, breps), tol) or [])
        elif op == "explode":
            for o in objs:
                if isinstance(o.Geometry, G.Curve):
                    segments = o.Geometry.DuplicateSegments()
                    results += list(segments) if segments and len(segments) > 1 else [o.Geometry.DuplicateCurve()]
                else:
                    brep = _brep(o)
                    results += [brep.Faces[i].DuplicateFace(False) for i in range(brep.Faces.Count)]
        elif op == "cap":
            for o in objs:
                b = _brep(o).CapPlanarHoles(tol)
                if b is None:
                    raise McpError("cap : aucun trou plan à boucher sur %s." % o.Id)
                results.append(b)
        elif op == "mesh":
            for o in objs:
                mesh = G.Mesh()
                for part in G.Mesh.CreateFromBrep(_brep(o), G.MeshingParameters.Default) or []:
                    mesh.Append(part)
                results.append(mesh)
        elif op == "intersect":
            others = find_objects(d, _need(other_ids, "other_ids", op))
            for o in objs:
                for other in others:
                    results += _intersect(o, other, tol)
        if not results:
            raise McpError("%s n'a rien produit." % op)
        if layer or name or color is not None:
            attrs = attributes(d, layer, name, color)
        else:
            attrs = objs[0].Attributes.Duplicate()  # même calque/couleur que le premier objet
        ids = [add_geometry(d, g, attrs) for g in results]
        remove = delete_input if delete_input is not None else op in REPLACES_INPUT
        if remove:
            for o in used:
                d.Objects.Delete(o.Id, True)
        out = created(d, ids)
        out["deleted_input"] = [str(o.Id) for o in used] if remove else []
        return out
