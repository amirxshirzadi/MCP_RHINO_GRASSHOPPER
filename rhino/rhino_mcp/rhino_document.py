# -*- coding: utf-8 -*-
"""Rhino : document et fichiers."""
import os

import Rhino

from . import VERSION
from .registry import command
from .util import MAX_ITEMS, doc, iter_objects, rgb


@command("rhino_ping", "ping")
def rhino_ping():
    d = Rhino.RhinoDoc.ActiveDoc
    return {
        "rhino_version": str(Rhino.RhinoApp.Version),
        "listener_version": VERSION,
        "document": d.Name if d else None,
        "path": d.Path if d else None,
        "modified": bool(d.Modified) if d else None,
        "process_id": os.getpid(),
    }


@command("rhino_get_document_info", "get_document_info")
def rhino_get_document_info():
    d = doc()
    counts = {}
    total = 0
    for o in iter_objects(d):
        t = str(o.ObjectType)
        counts[t] = counts.get(t, 0) + 1
        total += 1
    layers = []
    for layer in d.Layers:
        if layer.IsDeleted:
            continue
        layers.append({
            "name": layer.FullPath,
            "visible": layer.IsVisible,
            "locked": layer.IsLocked,
            "color": rgb(layer.Color),
        })
    return {
        "name": d.Name,
        "path": d.Path,
        "modified": bool(d.Modified),
        "units": str(d.ModelUnitSystem),
        "tolerance": d.ModelAbsoluteTolerance,
        "angle_tolerance_degrees": d.ModelAngleToleranceDegrees,
        "object_count": total,
        "objects_by_type": counts,
        "current_layer": d.Layers.CurrentLayer.FullPath,
        "layers": layers[:MAX_ITEMS],
        "views": [v.ActiveViewport.Name for v in d.Views.GetViewList(True, False)],
        "layouts": [p.PageName for p in d.Views.GetPageViews()],
        "named_views": [d.NamedViews[i].Name for i in range(d.NamedViews.Count)],
    }
