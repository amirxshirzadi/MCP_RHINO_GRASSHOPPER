# -*- coding: utf-8 -*-
"""Rhino : exécution de Python et de commandes Rhino (tout ce que les autres outils ne couvrent pas)."""
import io
import sys
import traceback

import System
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

from .registry import McpError, command
from .util import MAX_ITEMS, close_dangling_undo_records, ensure_idle, iter_objects, jsonable, object_summary


def _get_gh_doc():
    from .gh_common import gh_doc
    return gh_doc()[1]


@command("rhino_execute_python", "execute_python")
def rhino_execute_python(code):
    """Exécute du Python dans Rhino. Affecter `result` pour renvoyer une valeur.
    Fonctionne aussi sans document actif (doc vaut alors None), par ex. pour en créer un."""
    ensure_idle()
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
            close_dangling_undo_records(Rhino.RhinoDoc.ActiveDoc)
        except Exception:
            pass
        active = Rhino.RhinoDoc.ActiveDoc
        if active is not None:
            active.Views.Redraw()
    out = {"stdout": buf.getvalue()[-20000:], "result": jsonable(ns.get("result"))}
    if error:
        out["error"] = error
    return out


@command("rhino_run_command")
def rhino_run_command(command, echo=False):
    """Lance une commande Rhino (macro) et renvoie les objets créés et la sortie de la ligne de commande."""
    ensure_idle()
    if not (command or "").strip():
        raise McpError("Commande vide.")
    d = Rhino.RhinoDoc.ActiveDoc
    before = set(o.Id for o in iter_objects(d)) if d is not None else set()
    history = Rhino.RhinoApp.CommandHistoryWindowText or ""
    ok = Rhino.RhinoApp.RunScript(command, bool(echo))
    after = Rhino.RhinoApp.CommandHistoryWindowText or ""
    output = after[len(history):] if after.startswith(history) else after[-3000:]
    d = Rhino.RhinoDoc.ActiveDoc
    if d is None:
        return {"success": bool(ok), "output": output.strip()[-4000:], "created": [], "selected": []}
    created = [o for o in iter_objects(d) if o.Id not in before]
    selected = [str(o.Id) for o in d.Objects.GetSelectedObjects(False, False)]
    d.Views.Redraw()
    return {
        "success": bool(ok),
        "output": output.strip()[-4000:],
        "created": [object_summary(o) for o in created[:MAX_ITEMS]],
        "created_count": len(created),
        "selected": selected[:MAX_ITEMS],
    }
