# -*- coding: utf-8 -*-
"""Grasshopper : accès au document et descriptions communes aux commandes gh_*."""
import clr

import System
import Rhino

from .registry import McpError
from .util import impl


def gh_module(load=True):
    """Module Grasshopper, en ouvrant (ou réaffichant) Grasshopper si besoin."""
    try:
        import Grasshopper
        if Grasshopper.Instances.ActiveCanvas is not None:
            editor = Grasshopper.Instances.DocumentEditor
            if load and editor is not None and not editor.Visible:
                # Éditeur fermé : Grasshopper coupe alors le calcul du document. On le réaffiche.
                Rhino.RhinoApp.RunScript("_Grasshopper", False)
            return Grasshopper
    except Exception:
        pass
    if not load:
        raise McpError("Grasshopper n'est pas ouvert.")
    Rhino.RhinoApp.RunScript("_Grasshopper", False)
    clr.AddReference("Grasshopper")
    import Grasshopper
    if Grasshopper.Instances.ActiveCanvas is None:
        raise McpError("Grasshopper n'est pas ouvert. Lance la commande Grasshopper dans Rhino puis réessaie.")
    return Grasshopper


def gh_doc(create=True):
    """(module Grasshopper, document actif) ; crée un document vide si aucun n'est ouvert."""
    gh = gh_module()
    canvas = gh.Instances.ActiveCanvas
    gdoc = canvas.Document
    if gdoc is None:
        if not create:
            raise McpError("Aucun document Grasshopper ouvert.")
        gdoc = gh.Kernel.GH_Document()
        gh.Instances.DocumentServer.AddDocument(gdoc)
        canvas.Document = gdoc
    gdoc = impl(gdoc)
    if not gdoc.Enabled:  # document désactivé (éditeur fermé) : rien ne serait calculé
        gdoc.Enabled = True
    return gh, gdoc


def refresh(gh):
    canvas = gh.Instances.ActiveCanvas
    if canvas is not None:
        canvas.Refresh()


def find(gdoc, obj_id):
    try:
        guid = System.Guid(str(obj_id).strip())
    except Exception:
        raise McpError("Identifiant Grasshopper invalide : %s" % obj_id)
    o = gdoc.FindObject(guid, True)
    if o is None:
        raise McpError("Objet Grasshopper introuvable : %s" % obj_id)
    return impl(o)


def params_of(o):
    """(entrées, sorties) d'un composant ; un paramètre isolé est sa propre entrée/sortie."""
    if hasattr(o, "Params"):
        return [impl(p) for p in o.Params.Input], [impl(p) for p in o.Params.Output]
    if hasattr(o, "Sources"):
        return [o], [o]
    return [], []


def pick(params, key):
    if not params:
        raise McpError("Cet objet n'a pas de paramètre de ce côté.")
    if key is None:
        return params[0]
    if isinstance(key, int) or (isinstance(key, str) and key.strip().isdigit()):
        index = int(key)
        if not 0 <= index < len(params):
            raise McpError("Index de paramètre hors limites : %s (0 à %d)." % (key, len(params) - 1))
        return params[index]
    k = str(key).strip().lower()
    for p in params:
        if p.Name.lower() == k or p.NickName.lower() == k:
            return p
    raise McpError("Paramètre '%s' introuvable. Disponibles : %s"
                   % (key, ", ".join("%s (%s)" % (p.Name, p.NickName) for p in params)))


def owner_id(param):
    try:
        return str(impl(param.Attributes.GetTopLevel.DocObject).InstanceGuid)
    except Exception:
        return None


def param_desc(p):
    return {
        "name": p.Name,
        "nickname": p.NickName,
        "type": p.TypeName,
        "sources": [{"id": owner_id(impl(s)), "param": impl(s).NickName} for s in p.Sources],
    }


def messages(o):
    import Grasshopper
    msgs = {}
    if hasattr(o, "RuntimeMessages"):
        for level_name in ("Error", "Warning"):
            level = getattr(Grasshopper.Kernel.GH_RuntimeMessageLevel, level_name)
            lst = [str(m) for m in o.RuntimeMessages(level)]
            if lst:
                msgs[level_name.lower()] = lst
    return msgs


def describe(o):
    o = impl(o)
    d = {
        "id": str(o.InstanceGuid),
        "name": o.Name,
        "nickname": o.NickName,
        "type": o.GetType().Name,
        "position": [round(o.Attributes.Pivot.X, 1), round(o.Attributes.Pivot.Y, 1)],
    }
    tname = o.GetType().Name
    if hasattr(o, "Params"):
        ins, outs = params_of(o)
        d["inputs"] = [param_desc(p) for p in ins]
        d["outputs"] = [param_desc(p) for p in outs]
    elif hasattr(o, "Sources"):
        d["sources"] = param_desc(o)["sources"]
    if tname == "GH_NumberSlider":
        d["value"] = System.Convert.ToDouble(o.CurrentValue)
        d["min"] = System.Convert.ToDouble(o.Slider.Minimum)
        d["max"] = System.Convert.ToDouble(o.Slider.Maximum)
    elif tname == "GH_Panel":
        d["value"] = o.UserText
    elif tname == "GH_BooleanToggle":
        d["value"] = bool(o.Value)
    msgs = messages(o)
    if msgs:
        d["messages"] = msgs
    return d


def proxies(gh):
    for proxy in gh.Instances.ComponentServer.ObjectProxies:
        p = impl(proxy)
        if not p.Obsolete:
            yield p
