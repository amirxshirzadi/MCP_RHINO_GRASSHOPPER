# -*- coding: utf-8 -*-
"""Rhino : vues, captures d'écran, annotations, mises en page et PDF."""
import math
import os

import System
import System.Drawing
import Rhino
import Rhino.Geometry as G

from .registry import McpError, command
from .util import (Undo, attributes, created, doc, find_objects, to_plane, to_point, to_points, typed_list)

PROJECTIONS = {
    "top": "Top", "bottom": "Bottom", "left": "Left", "right": "Right", "front": "Front", "back": "Back",
    "perspective": "Perspective", "two_point_perspective": "TwoPointPerspective",
}


def _need(value, label, action):
    if value in (None, ""):
        raise McpError("%s : paramètre « %s » requis." % (action, label))
    return value


def find_view(d, view=None):
    v = d.Views.Find(view, False) if view else d.Views.ActiveView
    if v is None:
        names = ", ".join(x.ActiveViewport.Name for x in d.Views)
        raise McpError("Vue introuvable : %s. Vues disponibles : %s" % (view, names))
    return v


def _projection(name):
    key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    if key not in PROJECTIONS:
        raise McpError("Projection inconnue : %s (%s)." % (name, ", ".join(PROJECTIONS)))
    return getattr(Rhino.Display.DefinedViewportProjection, PROJECTIONS[key])


def _display_mode(name):
    modes = list(Rhino.Display.DisplayModeDescription.GetDisplayModes())
    wanted = str(name).strip().lower()
    for m in modes:
        if wanted in ((m.EnglishName or "").lower(), (m.LocalName or "").lower()):
            return m
    raise McpError("Mode d'affichage inconnu : %s. Modes : %s" % (name, ", ".join(m.EnglishName for m in modes)))


def _view_info(d, v):
    vp = v.ActiveViewport
    return {
        "name": vp.Name, "active": v.ActiveViewportID == d.Views.ActiveView.ActiveViewportID,
        "projection": "perspective" if vp.IsPerspectiveProjection else "parallel",
        "display_mode": vp.DisplayMode.EnglishName if vp.DisplayMode else None,
        "camera_location": [round(c, 4) for c in (vp.CameraLocation.X, vp.CameraLocation.Y, vp.CameraLocation.Z)],
        "camera_target": [round(c, 4) for c in (vp.CameraTarget.X, vp.CameraTarget.Y, vp.CameraTarget.Z)],
    }


def capture_png(view, width, height):
    bmp = view.CaptureToBitmap(System.Drawing.Size(int(width), int(height)))
    if bmp is None:
        raise McpError("La capture de la vue a échoué.")
    ms = System.IO.MemoryStream()
    try:
        bmp.Save(ms, System.Drawing.Imaging.ImageFormat.Png)
        return System.Convert.ToBase64String(ms.ToArray())
    finally:
        bmp.Dispose()
        ms.Dispose()


@command("rhino_capture_view", "capture_view")
def rhino_capture_view(width=900, height=600, view=None, display_mode=None, zoom_extents=False):
    d = doc()
    v = find_view(d, view)
    previous = None
    if display_mode:  # mode d'affichage le temps de la capture, puis retour au mode de l'utilisateur
        previous = v.ActiveViewport.DisplayMode
        v.ActiveViewport.DisplayMode = _display_mode(display_mode)
    if zoom_extents:
        v.ActiveViewport.ZoomExtents()
    try:
        v.Redraw()
        image = capture_png(v, width, height)
    finally:
        if previous is not None:
            v.ActiveViewport.DisplayMode = previous
            v.Redraw()
    return {"view": v.ActiveViewport.Name, "width": int(width), "height": int(height), "image_base64": image}


# --------------------------------------------------------------------------- #
# Vues
# --------------------------------------------------------------------------- #
@command("rhino_view")
def rhino_view(action="list", view=None, projection=None, display_mode=None, ids=None, zoom=None, name=None,
               camera_location=None, camera_target=None, lens=None, cplane=None, maximize=None):
    d = doc()
    action = (action or "list").strip().lower()
    if action == "list":
        return {
            "views": [_view_info(d, v) for v in d.Views.GetViewList(True, False)],
            "named_views": [d.NamedViews[i].Name for i in range(d.NamedViews.Count)],
            "display_modes": [m.EnglishName for m in Rhino.Display.DisplayModeDescription.GetDisplayModes()],
            "layouts": [p.PageName for p in d.Views.GetPageViews()],
        }
    v = find_view(d, view)
    vp = v.ActiveViewport
    if action == "set":
        d.Views.ActiveView = v
        if projection:
            vp.SetProjection(_projection(projection), vp.Name, True)
        if display_mode:
            vp.DisplayMode = _display_mode(display_mode)
        if camera_location is not None or camera_target is not None:
            target = to_point(camera_target, "camera_target") if camera_target is not None else vp.CameraTarget
            location = to_point(camera_location, "camera_location") if camera_location is not None else vp.CameraLocation
            vp.SetCameraLocations(target, location)
        if lens:
            vp.Camera35mmLensLength = float(lens)
        if cplane is not None:
            vp.SetConstructionPlane(to_plane(cplane))
        if maximize is not None:
            v.Maximized = bool(maximize)
    elif action == "zoom":
        if ids:
            bb = G.BoundingBox.Empty
            for o in find_objects(d, ids):
                bb = G.BoundingBox.Union(bb, o.Geometry.GetBoundingBox(True))
            vp.ZoomBoundingBox(bb)
        elif (zoom or "extents").lower() == "selected":
            vp.ZoomExtentsSelected()
        else:
            vp.ZoomExtents()
    elif action == "save_named":
        d.NamedViews.Add(_need(name, "name", action), vp.Id)
    elif action in ("restore_named", "delete_named"):
        index = d.NamedViews.FindByName(_need(name, "name", action))
        if index < 0:
            raise McpError("Vue nommée introuvable : %s" % name)
        if action == "restore_named":
            viewport_name = vp.Name
            d.NamedViews.Restore(index, vp)
            vp.Name = viewport_name  # Rhino renomme sinon la vue ; on garde un nom stable (« Perspective »...)
        else:
            d.NamedViews.Delete(index)
    else:
        raise McpError("Action inconnue : %s (list, set, zoom, save_named, restore_named, delete_named)." % action)
    v.Redraw()
    info = _view_info(d, v)
    info["named_views"] = [d.NamedViews[i].Name for i in range(d.NamedViews.Count)]
    return info


# --------------------------------------------------------------------------- #
# Annotations
# --------------------------------------------------------------------------- #
ANNOTATIONS = ("text", "dot", "dimension", "linear_dimension", "leader", "hatch")


@command("rhino_annotation")
def rhino_annotation(type, text=None, point=None, points=None, start=None, end=None, offset=None, height=None,
                     plane=None, ids=None, pattern="Solid", scale=1.0, rotation=0.0, layer=None, name=None,
                     color=None):
    kind = (type or "").strip().lower()
    if kind not in ANNOTATIONS:
        raise McpError("Type d'annotation inconnu : %s (%s)." % (type, ", ".join(ANNOTATIONS)))
    with Undo("annotation " + kind) as d:
        attrs = attributes(d, layer, name, color)
        new_ids = []
        if kind == "text":
            pl = to_plane(plane, origin=_need(point, "point", kind))
            te = G.TextEntity.Create(_need(text, "text", kind), pl, d.DimStyles.Current, False, 0.0,
                                     math.radians(float(rotation or 0)))
            if height:
                te.TextHeight = float(height)
            new_ids.append(d.Objects.AddText(te, attrs))
        elif kind == "dot":
            new_ids.append(d.Objects.AddTextDot(G.TextDot(_need(text, "text", kind),
                                                          to_point(_need(point, "point", kind))), attrs))
        elif kind in ("dimension", "linear_dimension"):
            p0, p1 = to_point(_need(start, "start", kind), "start"), to_point(_need(end, "end", kind), "end")
            pl = to_plane(plane, origin=start)
            if offset is not None:
                line_point = to_point(offset, "offset")
            else:  # ligne de cote décalée de 15 % de la longueur, perpendiculairement, dans le plan
                direction = G.Vector3d.CrossProduct(pl.ZAxis, p1 - p0)
                if direction.Length <= 0:
                    raise McpError("Cote : les deux points sont confondus ou alignés avec la normale du plan.")
                direction = direction * (1.0 / direction.Length)
                mid = G.Point3d((p0.X + p1.X) / 2, (p0.Y + p1.Y) / 2, (p0.Z + p1.Z) / 2)
                line_point = mid + direction * max(p0.DistanceTo(p1) * 0.15, d.ModelAbsoluteTolerance * 10)
            annotation_type = G.AnnotationType.Aligned if kind == "dimension" else G.AnnotationType.Rotated
            dim = G.LinearDimension.Create(annotation_type, d.DimStyles.Current, pl, pl.XAxis, p0, p1, line_point, 0.0)
            if dim is None:
                raise McpError("Cote impossible avec ces points.")
            new_ids.append(d.Objects.AddLinearDimension(dim, attrs))
        elif kind == "leader":
            pts = to_points(_need(points, "points", kind), "points", 2)
            pl = to_plane(plane, origin=points[0])
            pts2d = []
            for p in pts:
                ok, u, v = pl.ClosestParameter(p)
                pts2d.append(G.Point2d(u, v))
            new_ids.append(d.Objects.AddLeader(text or "", pl, typed_list(G.Point2d, pts2d), attrs))
        else:  # hatch
            curves = [o.Geometry for o in find_objects(d, _need(ids, "ids", kind))]
            hp = d.HatchPatterns.FindName(pattern or "Solid")
            if hp is None:
                names = ", ".join(d.HatchPatterns[i].Name for i in range(d.HatchPatterns.Count))
                raise McpError("Motif de hachure inconnu : %s. Motifs : %s" % (pattern, names))
            hatches = G.Hatch.Create(typed_list(G.Curve, curves), hp.Index, math.radians(float(rotation or 0)),
                                     float(scale or 1), d.ModelAbsoluteTolerance)
            if not hatches:
                raise McpError("Hachure impossible : les courbes doivent être fermées et planes.")
            new_ids += [d.Objects.AddHatch(h, attrs) for h in hatches]
        if any(i == System.Guid.Empty for i in new_ids):
            raise McpError("Rhino a refusé l'annotation (%s)." % kind)
        return created(d, new_ids)


# --------------------------------------------------------------------------- #
# Mises en page et PDF
# --------------------------------------------------------------------------- #
def _page(d, name):
    for p in d.Views.GetPageViews():
        if p.PageName.lower() == str(name).strip().lower():
            return p
    raise McpError("Mise en page introuvable : %s. Disponibles : %s"
                   % (name, ", ".join(p.PageName for p in d.Views.GetPageViews()) or "aucune"))


def _page_info(p):
    return {"name": p.PageName, "width": p.PageWidth, "height": p.PageHeight,
            "details": [dv.Viewport.Name for dv in p.GetDetailViews()]}


@command("rhino_layout")
def rhino_layout(action="list", name=None, width=420.0, height=297.0, details=None, path=None, layouts=None,
                 views=None, dpi=300, overwrite=False):
    d = doc()
    action = (action or "list").strip().lower()
    if action == "list":
        return {"layouts": [_page_info(p) for p in d.Views.GetPageViews()]}
    if action == "create":
        page = d.Views.AddPageView(_need(name, "name", action), float(width), float(height))
        if page is None:
            raise McpError("Création de la mise en page impossible.")
        specs = details or [{"projection": "perspective"}]
        margin = 10.0
        cell = (float(width) - margin * (len(specs) + 1)) / len(specs)
        for i, spec in enumerate(specs):
            rect = spec.get("rect") or [margin + i * (cell + margin), margin,
                                        margin + i * (cell + margin) + cell, float(height) - margin]
            projection = spec.get("projection", "perspective")
            detail = page.AddDetailView(spec.get("title") or projection, G.Point2d(rect[0], rect[1]),
                                        G.Point2d(rect[2], rect[3]), _projection(projection))
            if detail is None:
                raise McpError("Création de la fenêtre de détail %d impossible." % (i + 1))
            if spec.get("display_mode"):
                detail.Viewport.DisplayMode = _display_mode(spec["display_mode"])
            detail.Viewport.ZoomExtents()
            detail.CommitViewportChanges()
        page.SetPageAsActive()
        d.Views.ActiveView = page
        d.Views.Redraw()
        return _page_info(page)
    if action == "export_pdf":
        target = os.path.abspath(os.path.expandvars(_need(path, "path", action)))
        if not target.lower().endswith(".pdf"):
            target += ".pdf"
        if os.path.exists(target) and not overwrite:
            raise McpError("Le fichier %s existe déjà : relance avec overwrite=true pour le remplacer." % target)
        if not os.path.isdir(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))
        pdf = Rhino.FileIO.FilePdf.Create()
        pages = 0
        page_names = layouts if layouts is not None else [p.PageName for p in d.Views.GetPageViews()]
        for page_name in page_names:
            pdf.AddPage(Rhino.Display.ViewCaptureSettings(_page(d, page_name), float(dpi)))
            pages += 1
        for view_name in views or []:  # vues du modèle, en A4 paysage
            settings = Rhino.Display.ViewCaptureSettings(find_view(d, view_name), System.Drawing.Size(1754, 1240),
                                                         float(dpi))
            pdf.AddPage(settings)
            pages += 1
        if not pages:
            raise McpError("Aucune page : crée une mise en page (action create) ou indique des vues (views).")
        pdf.Write(target)
        return {"path": target, "pages": pages, "size_bytes": os.path.getsize(target)}
    if action == "delete":
        _page(d, _need(name, "name", action)).Close()
        return {"deleted": name}
    raise McpError("Action inconnue : %s (list, create, export_pdf, delete)." % action)
