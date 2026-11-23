# -*- coding: utf-8 -*-
"""Grasshopper : valeurs (curseurs, panneaux, entrées), géométrie référencée, sorties, calcul et cuisson."""
import System
import Rhino
import Rhino.Geometry as G

from .gh_common import describe, find, gh_doc, messages, params_of, pick, refresh
from .registry import McpError, command
from .util import (MAX_ITEMS, Undo, as_list, attributes, created, doc, find_object, geometry_summary, impl,
                   jsonable, to_color, to_guid, to_plane, to_point, to_vector)


# --------------------------------------------------------------------------- #
# Valeurs
# --------------------------------------------------------------------------- #
def _convert(param_type, value):
    """Valeur JSON -> valeur .NET selon le type du paramètre (Grasshopper convertit le reste)."""
    if param_type in ("Param_Point",):
        return to_point(value)
    if param_type in ("Param_Vector",):
        return to_vector(value)
    if param_type in ("Param_Colour",):
        return to_color(value)
    if param_type in ("Param_Plane",):
        return to_plane(value)
    return value


def set_persistent(param, value):
    """Valeur(s) saisie(s) directement dans une entrée ou un paramètre (comme « Set Number »...)."""
    param = impl(param)
    if not hasattr(param, "PersistentData"):
        raise McpError("Le paramètre « %s » n'accepte pas de valeur saisie." % param.NickName)
    ptype = param.GetType().Name
    single_point = ptype in ("Param_Point", "Param_Vector") and isinstance(value, (list, tuple)) and \
        value and not isinstance(value[0], (list, tuple, dict))
    values = [value] if single_point or not isinstance(value, (list, tuple)) else list(value)
    param.PersistentData.Clear()
    param.SetPersistentData(System.Array[System.Object]([_convert(ptype, v) for v in values]))
    param.ExpireSolution(True)


def apply_value(gh, o, value, min=None, max=None, decimals=None):
    o = impl(o)
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
        if value is not None:
            o.SetSliderValue(System.Decimal(float(value)))
    elif tname == "GH_Panel":
        o.UserText = "" if value is None else str(value)
    elif tname == "GH_BooleanToggle":
        o.Value = bool(value)
    elif tname == "GH_ValueList":
        items = list(o.ListItems)
        if isinstance(value, int) and not isinstance(value, bool):
            index = value
        else:
            wanted = str(value).strip().lower()
            index = next((i for i, it in enumerate(items)
                          if wanted in ((it.Name or "").lower(), (it.Expression or "").lower())), -1)
        if not 0 <= index < len(items):
            raise McpError("Élément introuvable dans la liste : %s. Éléments : %s"
                           % (value, ", ".join(it.Name for it in items)))
        o.SelectItem(index)
    elif tname == "GH_ColourSwatch":
        o.SwatchColour = to_color(value)
    elif hasattr(o, "PersistentData"):
        set_persistent(o, value)
        return
    else:
        raise McpError("gh_set_value gère curseurs, panneaux, interrupteurs, listes de valeurs, nuanciers et "
                       "paramètres ; pour une entrée de composant, indique input. Objet : '%s'." % tname)
    o.ExpireSolution(True)


@command("gh_set_value")
def gh_set_value(id, value=None, min=None, max=None, decimals=None, input=None):
    gh, gdoc = gh_doc()
    o = find(gdoc, id)
    if input is not None:
        p = pick(params_of(o)[0], input)
        if p.SourceCount:
            raise McpError("L'entrée « %s » est reliée à %d fil(s) : la valeur saisie serait ignorée. Déconnecte-la "
                           "d'abord (gh_connect disconnect=true)." % (p.NickName, p.SourceCount))
        set_persistent(p, value)
    else:
        apply_value(gh, o, value, min, max, decimals)
    refresh(gh)
    return describe(o)


@command("gh_reference_rhino_geometry")
def gh_reference_rhino_geometry(id, rhino_ids, input=None):
    """Relie des objets Rhino à un paramètre (comme « Set one/multiple Curve(s) ») : ils restent liés au modèle."""
    gh, gdoc = gh_doc()
    o = find(gdoc, id)
    p = pick(params_of(o)[0], input) if hasattr(o, "Params") else o
    d = doc()
    goos = []
    for rid in as_list(rhino_ids):
        find_object(d, rid)
        goo = gh.Kernel.GH_Convert.ObjRefToGeometry(Rhino.DocObjects.ObjRef(d, to_guid(rid)))
        if goo is None:
            raise McpError("L'objet Rhino %s ne peut pas être référencé dans Grasshopper." % rid)
        goos.append(goo)
    if not goos:
        raise McpError("Indique au moins un objet Rhino (rhino_ids).")
    set_persistent(p, goos)
    refresh(gh)
    return describe(o)


# --------------------------------------------------------------------------- #
# Lecture et calcul
# --------------------------------------------------------------------------- #
def _goo_value(goo):
    if goo is None:
        return None
    value = goo.ScriptVariable() if hasattr(goo, "ScriptVariable") else goo
    if isinstance(value, G.GeometryBase):
        return geometry_summary(value)
    if isinstance(value, (bool, int, float, str, System.Guid, G.Point3d, G.Vector3d, G.Line, G.Plane, G.Circle,
                          G.Interval, System.Drawing.Color)):
        return jsonable(value)
    return str(goo)


@command("gh_get_output")
def gh_get_output(id, output=None, side="output", limit=200):
    _, gdoc = gh_doc()
    o = find(gdoc, id)
    ins, outs = params_of(o)
    p = pick(ins if (side or "output").lower() == "input" else outs, output)
    data = p.VolatileData
    branches, count = [], 0
    for path in data.Paths:
        items = []
        for item in data.get_Branch(path):
            if count >= limit:
                break
            items.append(_goo_value(item))
            count += 1
        branches.append({"path": str(path), "items": items})
        if count >= limit:
            break
    return {"param": p.NickName, "type": p.TypeName, "total_items": data.DataCount, "branches": branches}


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


# --------------------------------------------------------------------------- #
# Cuisson (bake) vers Rhino
# --------------------------------------------------------------------------- #
def _bake_goo(gh, d, goo, attrs):
    if isinstance(goo, gh.Kernel.IGH_BakeAwareData):
        try:
            res = goo.BakeGeometry(d, attrs)
        except TypeError:
            res = gh.Kernel.IGH_BakeAwareData(goo).BakeGeometry(d, attrs)
        if isinstance(res, tuple) and res[0] and res[1] != System.Guid.Empty:
            return res[1]
    geometry = gh.Kernel.GH_Convert.ToGeometryBase(goo)
    if geometry is not None:
        gid = d.Objects.Add(geometry, attrs)
        if gid != System.Guid.Empty:
            return gid
    return None


@command("gh_bake")
def gh_bake(id, output=None, layer=None, name=None, color=None):
    gh, gdoc = gh_doc(create=False)
    o = find(gdoc, id)
    outs = params_of(o)[1]
    targets = [pick(outs, output)] if output is not None else outs
    with Undo("cuire Grasshopper") as d:
        attrs = attributes(d, layer, name, color)
        ids = []
        for p in targets:
            for goo in p.VolatileData.AllData(True):
                gid = _bake_goo(gh, d, goo, attrs)
                if gid is not None:
                    ids.append(gid)
                if len(ids) >= 10 * MAX_ITEMS:
                    break
        if not ids:
            raise McpError("Rien à cuire : la sortie ne contient pas de géométrie (lance gh_solve, vérifie les "
                           "erreurs du composant).")
        return created(d, ids)
