# -*- coding: utf-8 -*-
"""Rhino : objets du document (lister, détailler, sélectionner, modifier, transformer, supprimer)."""
from .registry import command
from .util import doc, filter_objects, object_summary


@command("rhino_get_objects", "get_objects")
def rhino_get_objects(layer=None, selected_only=False, type=None, name=None, include_hidden=True,
                      limit=200, offset=0):
    d = doc()
    out = []
    total = 0
    for o in filter_objects(d, layer, type, name, selected_only, include_hidden):
        if total >= offset and len(out) < limit:
            out.append(object_summary(o))
        total += 1
    return {"total": total, "offset": offset, "objects": out}
