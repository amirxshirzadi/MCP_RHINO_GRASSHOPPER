# -*- coding: utf-8 -*-
"""Grasshopper : composants (chercher, ajouter, modifier, supprimer, grouper) et fils."""
import System
import System.Drawing

from .gh_common import describe, find, gh_doc, params_of, pick, proxies, refresh
from .registry import McpError, command
from .util import impl


@command("gh_search_components")
def gh_search_components(query, limit=30):
    gh, _ = gh_doc()
    q = query.lower()
    hits = []
    for p in proxies(gh):
        d = p.Desc
        name, nick = d.Name or "", d.NickName or ""
        hay = " ".join([name, nick, d.Category or "", d.SubCategory or "", d.Description or ""]).lower()
        if q not in hay:
            continue
        score = 0 if name.lower() == q or nick.lower() == q else (1 if q in name.lower() else 2)
        hits.append((score, {
            "name": name, "nickname": nick, "category": d.Category, "subcategory": d.SubCategory,
            "guid": str(p.Guid), "description": (d.Description or "")[:200],
        }))
    hits.sort(key=lambda h: (h[0], h[1]["name"]))
    return [h[1] for h in hits[:limit]]


@command("gh_add_component")
def gh_add_component(name=None, guid=None, x=0, y=0, nickname=None):
    gh, gdoc = gh_doc()
    proxy = None
    if guid:
        proxy = gh.Instances.ComponentServer.EmitObjectProxy(System.Guid(str(guid)))
    elif name:
        n = name.lower()
        exact, by_nick = None, None
        for p in proxies(gh):
            if p.Desc.Name.lower() == n and exact is None:
                exact = p
            elif (p.Desc.NickName or "").lower() == n and by_nick is None:
                by_nick = p
        proxy = exact or by_nick
    else:
        raise McpError("Indique le nom (name) ou le guid du composant à ajouter.")
    if proxy is None:
        sugg = [h["name"] for h in gh_search_components(name or "", 8)]
        raise McpError("Composant '%s' introuvable. Suggestions : %s" % (name or guid, ", ".join(sugg)))
    obj = impl(impl(proxy).CreateInstance())
    obj.CreateAttributes()
    if nickname:
        obj.NickName = nickname
    obj.Attributes.Pivot = System.Drawing.PointF(float(x), float(y))
    gdoc.AddObject(obj, False)
    refresh(gh)
    return describe(obj)


@command("gh_connect")
def gh_connect(source_id, target_id, source_output=0, target_input=0, disconnect=False):
    gh, gdoc = gh_doc()
    src, tgt = find(gdoc, source_id), find(gdoc, target_id)
    sp = pick(params_of(src)[1], source_output)
    tp = pick(params_of(tgt)[0], target_input)
    if disconnect:
        tp.RemoveSource(sp)
    else:
        tp.AddSource(sp)
    tgt.ExpireSolution(True)
    refresh(gh)
    return describe(tgt)


@command("gh_delete")
def gh_delete(ids):
    gh, gdoc = gh_doc()
    removed = []
    for i in ids:
        o = find(gdoc, i)
        gdoc.RemoveObject(o, False)
        removed.append(str(i))
    gdoc.NewSolution(False)
    refresh(gh)
    return {"removed": removed}
