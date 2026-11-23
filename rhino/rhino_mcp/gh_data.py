# -*- coding: utf-8 -*-
"""Grasshopper : valeurs (curseurs, panneaux, entrées), géométrie référencée, sorties, calcul et cuisson."""
import System

from .gh_common import describe, find, gh_doc, messages, params_of, pick, refresh
from .registry import McpError, command
from .util import impl


@command("gh_set_value")
def gh_set_value(id, value, min=None, max=None, decimals=None):
    gh, gdoc = gh_doc()
    o = find(gdoc, id)
    tname = o.GetType().Name
    if tname == "GH_NumberSlider":
        if decimals is not None:
            acc = gh.GUI.Base.GH_SliderAccuracy
            o.Slider.Type = acc.Integer if int(decimals) == 0 else acc.Float
            o.Slider.DecimalPlaces = int(decimals)
        if min is not None:
            o.Slider.Minimum = System.Decimal(float(min))
        if max is not None:
            o.Slider.Maximum = System.Decimal(float(max))
        o.SetSliderValue(System.Decimal(float(value)))
    elif tname == "GH_Panel":
        o.UserText = str(value)
    elif tname == "GH_BooleanToggle":
        o.Value = bool(value)
    else:
        raise McpError("gh_set_value gère les curseurs (Number Slider), panneaux (Panel) et interrupteurs "
                       "(Boolean Toggle). Pour '%s', utilise rhino_execute_python." % tname)
    o.ExpireSolution(True)
    refresh(gh)
    return describe(o)


@command("gh_get_output")
def gh_get_output(id, output=0, limit=200):
    _, gdoc = gh_doc()
    o = find(gdoc, id)
    p = pick(params_of(o)[1], output)
    data = p.VolatileData
    branches, count = [], 0
    for path in data.Paths:
        items = []
        for item in data.get_Branch(path):
            if count >= limit:
                break
            items.append(str(item))
            count += 1
        branches.append({"path": str(path), "items": items})
        if count >= limit:
            break
    return {"param": p.NickName, "total_items": data.DataCount, "branches": branches}


@command("gh_solve")
def gh_solve():
    gh, gdoc = gh_doc()
    gdoc.NewSolution(True)
    refresh(gh)
    problems = []
    for o in gdoc.Objects:
        o = impl(o)
        m = messages(o)
        if m:
            problems.append({"id": str(o.InstanceGuid), "name": o.NickName, "messages": m})
    return {"objects": gdoc.ObjectCount, "problems": problems}
