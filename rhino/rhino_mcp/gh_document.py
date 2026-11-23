# -*- coding: utf-8 -*-
"""Grasshopper : documents (définitions .gh), description et capture du canevas."""
from .gh_common import describe, gh_doc
from .registry import command
from .util import MAX_ITEMS


@command("gh_get_canvas")
def gh_get_canvas():
    _, gdoc = gh_doc()
    objs = [describe(o) for o in gdoc.Objects]
    return {"file": gdoc.FilePath, "object_count": len(objs), "objects": objs[:MAX_ITEMS]}
