# -*- coding: utf-8 -*-
"""Grasshopper : documents (définitions .gh), description et capture du canevas."""
import os

import System
import System.Collections.Generic
import System.Drawing

from .gh_common import describe, gh_doc, gh_module, refresh
from .registry import McpError, command
from .util import MAX_ITEMS, as_list, impl


def _documents(gh):
    return [impl(d) for d in gh.Instances.DocumentServer]


def _doc_info(gh, gdoc):
    active = gh.Instances.ActiveCanvas.Document
    return {
        "name": gdoc.DisplayName, "path": gdoc.FilePath if gdoc.IsFilePathDefined else None,
        "modified": bool(gdoc.IsModified), "objects": gdoc.ObjectCount,
        "active": active is not None and impl(active).DocumentID == gdoc.DocumentID,
    }


def _same_path(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _activate(gh, gdoc):
    gh.Instances.ActiveCanvas.Document = gdoc
    if not gdoc.Enabled:
        gdoc.Enabled = True
    gdoc.NewSolution(False)
    refresh(gh)


@command("gh_document")
def gh_document(action="list", path=None, name=None, discard_changes=False, overwrite=False):
    gh = gh_module()
    action = (action or "list").strip().lower()
    server = gh.Instances.DocumentServer
    if action == "list":
        return {"documents": [_doc_info(gh, d) for d in _documents(gh)],
                "solver_enabled": bool(gh.Kernel.GH_Document.EnableSolutions)}
    if action == "new":
        gdoc = gh.Kernel.GH_Document()
        server.AddDocument(gdoc)
        _activate(gh, gdoc)
        return _doc_info(gh, gdoc)
    if action == "open":
        if not path:
            raise McpError("open : indique le chemin du fichier .gh/.ghx (path).")
        path = os.path.abspath(os.path.expandvars(path))
        if not os.path.isfile(path):
            raise McpError("Fichier introuvable : %s" % path)
        for d in _documents(gh):
            if d.IsFilePathDefined and _same_path(d.FilePath, path):
                _activate(gh, d)
                info = _doc_info(gh, d)
                info["already_open"] = True
                return info
        gdoc = server.AddDocument(path, True)
        if gdoc is None:
            raise McpError("Impossible d'ouvrir %s (fichier Grasshopper invalide ?)." % path)
        _activate(gh, impl(gdoc))
        return _doc_info(gh, impl(gdoc))
    if action in ("save", "save_as"):
        _, gdoc = gh_doc(create=False)
        target = path or (gdoc.FilePath if gdoc.IsFilePathDefined else None)
        if not target:
            raise McpError("Ce document n'a jamais été enregistré : utilise save_as avec un chemin (path).")
        target = os.path.abspath(os.path.expandvars(target))
        if not os.path.splitext(target)[1]:
            target += ".gh"
        if os.path.exists(target) and not overwrite and not _same_path(target, gdoc.FilePath):
            raise McpError("Le fichier %s existe déjà : relance avec overwrite=true pour le remplacer." % target)
        if os.path.dirname(target) and not os.path.isdir(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))
        if not gh.Kernel.GH_DocumentIO(gdoc).SaveQuiet(target):
            raise McpError("Échec de l'enregistrement de %s" % target)
        gdoc.FilePath = target
        gdoc.IsModified = False
        return _doc_info(gh, gdoc)
    if action == "close":
        _, gdoc = gh_doc(create=False)
        if gdoc.IsModified and not discard_changes:
            raise McpError("La définition « %s » a des modifications non enregistrées : enregistre-la (save/save_as) "
                           "ou relance avec discard_changes=true." % gdoc.DisplayName)
        closed = gdoc.DisplayName
        server.RemoveDocument(gdoc)
        remaining = _documents(gh)
        gh.Instances.ActiveCanvas.Document = remaining[0] if remaining else None
        refresh(gh)
        return {"closed": closed, "documents": [_doc_info(gh, d) for d in remaining]}
    if action == "activate":
        wanted = (name or path or "").strip().lower()
        for d in _documents(gh):
            if wanted in (d.DisplayName.lower(), (d.FilePath or "").lower()) or \
                    (path and d.IsFilePathDefined and _same_path(d.FilePath, path)):
                _activate(gh, d)
                return _doc_info(gh, d)
        raise McpError("Définition introuvable : %s. Ouvertes : %s"
                       % (name or path, ", ".join(d.DisplayName for d in _documents(gh))))
    if action in ("enable_solver", "disable_solver"):
        gh.Kernel.GH_Document.EnableSolutions = action == "enable_solver"
        if action == "enable_solver":
            _, gdoc = gh_doc()
            gdoc.NewSolution(False)
        refresh(gh)
        return {"solver_enabled": bool(gh.Kernel.GH_Document.EnableSolutions)}
    raise McpError("Action inconnue : %s (list, new, open, save, save_as, close, activate, enable_solver, "
                   "disable_solver)." % action)


@command("gh_get_canvas")
def gh_get_canvas(ids=None):
    gh, gdoc = gh_doc()
    wanted = set(str(i).strip().lower() for i in as_list(ids))
    objs = [describe(o) for o in gdoc.Objects if not wanted or str(o.InstanceGuid).lower() in wanted]
    return {
        "file": gdoc.FilePath, "name": gdoc.DisplayName, "modified": bool(gdoc.IsModified),
        "solver_enabled": bool(gh.Kernel.GH_Document.EnableSolutions),
        "object_count": len(objs), "objects": objs[:MAX_ITEMS],
    }


@command("gh_capture_canvas")
def gh_capture_canvas(width=1200, height=800, zoom_to_fit=True):
    """Image PNG du canevas, rendue dans une vue à part : la vue de l'utilisateur ne bouge pas."""
    gh, gdoc = gh_doc(create=False)
    canvas = gh.Instances.ActiveCanvas
    viewport = gh.GUI.Canvas.GH_Viewport(canvas.Viewport)
    viewport.Width = int(width)
    viewport.Height = int(height)
    if zoom_to_fit and gdoc.ObjectCount:
        attrs = System.Collections.Generic.List[gh.Kernel.IGH_Attributes]()
        for o in gdoc.Objects:
            attrs.Add(o.Attributes)
        viewport.Focus(attrs)
    bmp = canvas.GenerateHiResImageTile(viewport, System.Drawing.Color.White)
    if bmp is None:
        raise McpError("La capture du canevas Grasshopper a échoué.")
    ms = System.IO.MemoryStream()
    try:
        bmp.Save(ms, System.Drawing.Imaging.ImageFormat.Png)
        data = System.Convert.ToBase64String(ms.ToArray())
    finally:
        bmp.Dispose()
        ms.Dispose()
    return {"document": gdoc.DisplayName, "objects": gdoc.ObjectCount, "width": int(width), "height": int(height),
            "image_base64": data}
