# -*- coding: utf-8 -*-
"""Grasshopper : composants (chercher, ajouter, modifier, supprimer, grouper) et fils."""
import clr

import System
import System.Drawing

from .gh_common import describe, find, free_position, gh_doc, params_of, pick, proxies, refresh
from .registry import McpError, command
from .util import as_list, enum_value, impl, to_color


def _kind(gh, proxy):
    try:
        t = proxy.Type
        if clr.GetClrType(gh.Kernel.IGH_Component).IsAssignableFrom(t):
            return "component"
        if clr.GetClrType(gh.Kernel.IGH_Param).IsAssignableFrom(t):
            return "parameter"
    except Exception:
        pass
    return "special"


def _library(gh, proxy):
    try:
        info = gh.Instances.ComponentServer.FindAssembly(proxy.LibraryGuid)
        return info.Name if info is not None else None
    except Exception:
        return None


@command("gh_search_components")
def gh_search_components(query="", limit=30, category=None):
    gh, _ = gh_doc()
    q = (query or "").lower()
    cat = (category or "").lower()
    if not q and not cat:
        raise McpError("Indique un texte à chercher (query) ou une catégorie (category).")
    hits = []
    for p in proxies(gh):
        d = p.Desc
        name, nick = d.Name or "", d.NickName or ""
        if cat and cat not in (d.Category or "").lower():
            continue
        hay = " ".join([name, nick, d.Category or "", d.SubCategory or "", d.Description or ""]).lower()
        if q and q not in hay:
            continue
        score = 0 if q and (name.lower() == q or nick.lower() == q) else (1 if q and q in name.lower() else 2)
        hits.append((score, p))
    hits.sort(key=lambda h: (h[0], h[1].Desc.Name))
    out = []
    for _, p in hits[:limit]:
        d = p.Desc
        out.append({
            "name": d.Name, "nickname": d.NickName, "category": d.Category, "subcategory": d.SubCategory,
            "kind": _kind(gh, p), "library": _library(gh, p), "guid": str(p.Guid),
            "description": (d.Description or "")[:200],
        })
    return out


def _find_proxy(gh, name, guid):
    if guid:
        proxy = gh.Instances.ComponentServer.EmitObjectProxy(System.Guid(str(guid)))
        if proxy is None:
            raise McpError("Aucun composant avec le guid %s." % guid)
        return proxy
    n = name.strip().lower()
    exact = [p for p in proxies(gh) if (p.Desc.Name or "").lower() == n]
    if not exact:
        exact = [p for p in proxies(gh) if (p.Desc.NickName or "").lower() == n]
    if not exact:
        return None
    # Un même nom peut désigner un composant ET un paramètre (« Circle ») : on préfère le composant.
    components = [p for p in exact if _kind(gh, p) == "component"]
    return (components or exact)[0]


@command("gh_add_component")
def gh_add_component(name=None, guid=None, x=None, y=None, nickname=None, value=None, min=None, max=None,
                     decimals=None):
    gh, gdoc = gh_doc()
    if not name and not guid:
        raise McpError("Indique le nom (name) ou le guid du composant à ajouter.")
    proxy = _find_proxy(gh, name or "", guid)
    if proxy is None:
        sugg = [h["name"] for h in gh_search_components(name or "", 8)]
        raise McpError("Composant '%s' introuvable. Suggestions : %s" % (name or guid, ", ".join(sugg)))
    obj = impl(impl(proxy).CreateInstance())
    obj.CreateAttributes()
    if nickname:
        obj.NickName = nickname
    if x is None or y is None:
        fx, fy = free_position(gdoc)
        x = fx if x is None else x
        y = fy if y is None else y
    obj.Attributes.Pivot = System.Drawing.PointF(float(x), float(y))
    gdoc.AddObject(obj, False)
    if value is not None or min is not None or max is not None:
        from .gh_data import apply_value
        apply_value(gh, obj, value, min, max, decimals)
    refresh(gh)
    return describe(obj)


@command("gh_connect")
def gh_connect(source_id, target_id, source_output=0, target_input=0, disconnect=False, replace=False):
    gh, gdoc = gh_doc()
    src, tgt = find(gdoc, source_id), find(gdoc, target_id)
    sp = pick(params_of(src)[1], source_output)
    tp = pick(params_of(tgt)[0], target_input)
    if disconnect:
        tp.RemoveSource(sp)
    else:
        if replace:
            tp.RemoveAllSources()
        tp.AddSource(sp)
    tgt.ExpireSolution(True)
    refresh(gh)
    return describe(tgt)


MAPPINGS = {"none": "None", "flatten": "Flatten", "graft": "Graft"}


@command("gh_modify_objects")
def gh_modify_objects(ids, nickname=None, x=None, y=None, enabled=None, preview=None, params=None):
    gh, gdoc = gh_doc()
    objs = [find(gdoc, i) for i in as_list(ids)]
    for o in objs:
        if nickname is not None:
            o.NickName = nickname
        if x is not None or y is not None:
            pivot = o.Attributes.Pivot
            o.Attributes.Pivot = System.Drawing.PointF(float(pivot.X if x is None else x),
                                                       float(pivot.Y if y is None else y))
            o.Attributes.ExpireLayout()
        if enabled is not None:
            if not hasattr(o, "Locked"):
                raise McpError("%s ne peut pas être activé/désactivé." % o.NickName)
            o.Locked = not enabled
        if preview is not None:
            if not hasattr(o, "Hidden"):
                raise McpError("%s n'a pas d'aperçu dans Rhino." % o.NickName)
            o.Hidden = not preview
        for spec in params or []:
            ins, outs = params_of(o)
            p = pick(outs if spec.get("side") == "output" else ins, spec.get("param"))
            if spec.get("mapping") is not None:
                key = str(spec["mapping"]).lower()
                if key not in MAPPINGS:
                    raise McpError("mapping inconnu : %s (none, flatten, graft)." % spec["mapping"])
                p.DataMapping = enum_value(gh.Kernel.GH_DataMapping, MAPPINGS[key])
            if spec.get("reverse") is not None:
                p.Reverse = bool(spec["reverse"])
            if spec.get("simplify") is not None:
                p.Simplify = bool(spec["simplify"])
        o.ExpireSolution(False)
    gdoc.NewSolution(False)
    refresh(gh)
    return {"objects": [describe(o) for o in objs]}


@command("gh_delete")
def gh_delete(ids):
    gh, gdoc = gh_doc()
    removed = []
    for i in as_list(ids):
        o = find(gdoc, i)
        gdoc.RemoveObject(o, False)
        removed.append(str(i))
    gdoc.NewSolution(False)
    refresh(gh)
    return {"removed": removed}


@command("gh_group")
def gh_group(action="group", ids=None, name=None, color=None, text=None, x=None, y=None, size=None,
             group_id=None):
    gh, gdoc = gh_doc()
    action = (action or "group").strip().lower()
    if action == "group":
        members = [find(gdoc, i) for i in as_list(ids)]
        if not members:
            raise McpError("group : indique les objets à grouper (ids).")
        group = gh.Kernel.Special.GH_Group()
        group.CreateAttributes()
        group.NickName = name or "Groupe"
        if color is not None:
            c = to_color(color)
            group.Colour = System.Drawing.Color.FromArgb(c.A if c.A < 255 else 150, c.R, c.G, c.B)
        for o in members:
            group.AddObject(o.InstanceGuid)
        gdoc.AddObject(group, False)
        refresh(gh)
        return describe(group)
    if action == "ungroup":
        group = find(gdoc, group_id or (as_list(ids)[0] if ids else None))
        if group.GetType().Name != "GH_Group":
            raise McpError("%s n'est pas un groupe." % group.NickName)
        gdoc.RemoveObject(group, False)
        refresh(gh)
        return {"ungrouped": str(group.InstanceGuid)}
    if action == "note":
        if not text:
            raise McpError("note : indique le texte (text).")
        note = gh.Kernel.Special.GH_Scribble()
        note.CreateAttributes()
        note.Text = text
        if size:
            note.Font = System.Drawing.Font(note.Font.FontFamily, float(size))
        if x is None or y is None:
            fx, fy = free_position(gdoc)
            x = fx if x is None else x
            y = fy if y is None else y
        note.Attributes.Pivot = System.Drawing.PointF(float(x), float(y))
        gdoc.AddObject(note, False)
        refresh(gh)
        return describe(note)
    raise McpError("Action inconnue : %s (group, ungroup, note)." % action)
