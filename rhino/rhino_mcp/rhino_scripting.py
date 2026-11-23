# -*- coding: utf-8 -*-
"""Rhino : exécution de Python et de commandes Rhino (tout ce que les autres outils ne couvrent pas)."""
import io
import sys
import traceback

import System
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

from .registry import command
from .util import jsonable


def _get_gh_doc():
    from .gh_common import gh_doc
    return gh_doc()[1]


@command("rhino_execute_python", "execute_python")
def rhino_execute_python(code):
    """Exécute du Python dans Rhino. Affecter `result` pour renvoyer une valeur.
    Fonctionne aussi sans document actif (doc vaut alors None), par ex. pour en créer un."""
    d = Rhino.RhinoDoc.ActiveDoc
    if d is not None:
        sc.doc = d
    ns = {
        "__name__": "__rhino_mcp__",
        "Rhino": Rhino,
        "rs": rs,
        "sc": sc,
        "System": System,
        "doc": d,
        "get_gh_doc": _get_gh_doc,
        "result": None,
    }
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf
    undo = d.BeginUndoRecord("MCP : script Python") if d is not None else 0
    error = None
    try:
        exec(compile(code, "<mcp>", "exec"), ns)
    except Exception:
        error = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        # le script a pu fermer ou remplacer le document (Nouveau, Ouvrir...)
        try:
            if undo:
                d.EndUndoRecord(undo)
        except Exception:
            pass
        active = Rhino.RhinoDoc.ActiveDoc
        if active is not None:
            active.Views.Redraw()
    out = {"stdout": buf.getvalue()[-20000:], "result": jsonable(ns.get("result"))}
    if error:
        out["error"] = error
    return out
