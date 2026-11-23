# -*- coding: utf-8 -*-
"""Rhino : vues, captures d'écran, annotations, mises en page et PDF."""
import System
import System.Drawing

from .registry import McpError, command
from .util import doc


def find_view(d, view=None):
    v = d.Views.Find(view, False) if view else d.Views.ActiveView
    if v is None:
        names = ", ".join(x.ActiveViewport.Name for x in d.Views)
        raise McpError("Vue introuvable : %s. Vues disponibles : %s" % (view, names))
    return v


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
def rhino_capture_view(width=900, height=600, view=None):
    d = doc()
    v = find_view(d, view)
    return {"view": v.ActiveViewport.Name, "width": int(width), "height": int(height),
            "image_base64": capture_png(v, width, height)}
