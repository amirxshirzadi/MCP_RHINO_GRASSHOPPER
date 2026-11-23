# -*- coding: utf-8 -*-
"""Rhino : calques (et états de calques), matériaux, blocs."""
import math

import System
import System.Drawing
import Rhino
import Rhino.Geometry as G

from .registry import McpError, command
from .util import (MAX_ITEMS, Undo, as_list, attributes, created, doc, find_material, find_objects, layer_index,
                   rgb, to_color, to_point, typed_list)


def _need(value, label, action):
    if value in (None, ""):
        raise McpError("%s : paramètre « %s » requis." % (action, label))
    return value


# --------------------------------------------------------------------------- #
# Calques
# --------------------------------------------------------------------------- #
def _layer(d, path):
    idx = d.Layers.FindByFullPath(str(path).strip(), -1)
    if idx < 0:
        raise McpError("Calque introuvable : %s" % path)
    return d.Layers[idx]


def _layer_info(d, layer):
    material = layer.RenderMaterial
    parent = d.Layers.FindId(layer.ParentLayerId) if layer.ParentLayerId != System.Guid.Empty else None
    return {
        "path": layer.FullPath, "name": layer.Name, "color": rgb(layer.Color), "visible": layer.IsVisible,
        "locked": layer.IsLocked, "current": layer.Index == d.Layers.CurrentLayerIndex,
        "objects": len(d.Objects.FindByLayer(layer) or []), "material": material.Name if material else None,
        "parent": parent.FullPath if parent else None,
    }


def _apply_layer(d, layer, color=None, visible=None, locked=None, material=None, new_name=None, parent=None):
    if new_name:
        layer.Name = new_name
    if parent is not None:
        layer.ParentLayerId = _layer(d, parent).Id if parent else System.Guid.Empty
    if color is not None:
        layer.Color = to_color(color)
    if visible is not None:
        layer.IsVisible = bool(visible)
    if locked is not None:
        layer.IsLocked = bool(locked)
    if material is not None:
        layer.RenderMaterial = find_material(d, material) if material else None
    layer.CommitChanges()


@command("rhino_layer")
def rhino_layer(action="list", path=None, new_name=None, color=None, visible=None, locked=None, parent=None,
                material=None, delete_objects=False, state=None):
    action = (action or "list").strip().lower()
    d = doc()
    if action == "list":
        layers = [_layer_info(d, layer) for layer in d.Layers if not layer.IsDeleted]
        return {"current": d.Layers.CurrentLayer.FullPath, "layers": layers[:MAX_ITEMS],
                "states": list(d.NamedLayerStates.Names)}
    if action in ("save_state", "restore_state", "delete_state"):
        name = _need(state, "state", action)
        if action == "save_state":
            d.NamedLayerStates.Save(name)
        elif d.NamedLayerStates.FindName(name) < 0:
            raise McpError("État de calques introuvable : %s" % name)
        elif action == "restore_state":
            d.NamedLayerStates.Restore(name, Rhino.DocObjects.Tables.RestoreLayerProperties.All)
        else:
            d.NamedLayerStates.Delete(name)
        d.Views.Redraw()
        return {"states": list(d.NamedLayerStates.Names)}
    with Undo("calque " + action) as d:
        if action == "create":
            idx = layer_index(d, _need(path, "path", action))
            _apply_layer(d, d.Layers[idx], color, visible, locked, material)
            return _layer_info(d, d.Layers[idx])
        if action == "update":
            layer = _layer(d, _need(path, "path", action))
            _apply_layer(d, layer, color, visible, locked, material, new_name, parent)
            return _layer_info(d, d.Layers[layer.Index])
        if action == "set_current":
            layer = _layer(d, _need(path, "path", action))
            d.Layers.SetCurrentLayerIndex(layer.Index, True)
            return {"current": layer.FullPath}
        if action == "delete":
            layer = _layer(d, _need(path, "path", action))
            if layer.Index == d.Layers.CurrentLayerIndex:
                others = [x for x in d.Layers if not x.IsDeleted and x.Index != layer.Index
                          and not x.FullPath.startswith(layer.FullPath + "::")]
                if not others:
                    raise McpError("Impossible de supprimer le seul calque du document.")
                d.Layers.SetCurrentLayerIndex(others[0].Index, True)
            objs = list(d.Objects.FindByLayer(layer) or [])
            if objs and not delete_objects:
                raise McpError("Le calque « %s » contient des objets : delete_objects=true pour les supprimer avec "
                               "lui, ou déplace-les d'abord (rhino_modify_objects)." % layer.FullPath)
            for o in objs:
                if o.IsLocked:
                    d.Objects.Unlock(o.Id, True)
                d.Objects.Delete(o.Id, True)
            if not d.Layers.Delete(layer.Index, True):
                raise McpError("Suppression du calque impossible (il a peut-être des sous-calques).")
            return {"deleted": path, "objects_deleted": len(objs)}
    raise McpError("Action inconnue : %s (list, create, update, delete, set_current, save_state, "
                   "restore_state, delete_state)." % action)


# --------------------------------------------------------------------------- #
# Matériaux (PBR)
# --------------------------------------------------------------------------- #
def _new_material(d, name, color, metallic, roughness, opacity):
    col = to_color(color) if color is not None else System.Drawing.Color.FromArgb(255, 200, 200, 200)
    m = Rhino.DocObjects.Material()
    m.Name = name
    m.DiffuseColor = col
    if opacity < 1.0:
        m.Transparency = 1.0 - opacity
    m.ToPhysicallyBased()
    pbr = m.PhysicallyBased
    pbr.BaseColor = Rhino.Display.Color4f(col)
    pbr.Metallic = float(metallic)
    pbr.Roughness = float(roughness)
    if opacity < 1.0:
        pbr.Opacity = float(opacity)
    rm = Rhino.Render.RenderMaterial.FromMaterial(m, d)
    rm.Name = name
    d.RenderMaterials.Add(rm)
    return find_material(d, name)


def _assign(d, rm, ids=None, layers=None):
    count = 0
    for o in (find_objects(d, ids) if ids else []):
        current = d.Objects.FindId(o.Id)
        current.RenderMaterial = rm
        current.CommitChanges()
        count += 1
    for path in as_list(layers):
        layer = _layer(d, path)
        layer.RenderMaterial = rm
        layer.CommitChanges()
        count += 1
    return count


def _users(d, rm):
    objs = [o for o in d.Objects if o.RenderMaterial is not None and o.RenderMaterial.Id == rm.Id]
    layers = [x for x in d.Layers if not x.IsDeleted and x.RenderMaterial is not None and x.RenderMaterial.Id == rm.Id]
    return objs, layers


@command("rhino_material")
def rhino_material(action="list", name=None, color=None, metallic=0.0, roughness=0.5, opacity=1.0, ids=None,
                   layers=None, replace=False):
    action = (action or "list").strip().lower()
    d = doc()
    if action == "list":
        return {"materials": [{"name": m.Name, "id": str(m.Id), "type": m.TypeName} for m in d.RenderMaterials]}
    with Undo("matériau " + action) as d:
        if action == "create":
            name = _need(name, "name", action)
            existing = None
            try:
                existing = find_material(d, name)
            except McpError:
                pass
            if existing is not None and not replace:
                raise McpError("Le matériau « %s » existe déjà : replace=true pour le remplacer, ou assign." % name)
            rm = _new_material(d, name + (" (nouveau)" if existing else ""), color, metallic, roughness, opacity)
            reassigned = 0
            if existing is not None:  # remplacer : réaffecter tout ce qui l'utilisait, puis prendre son nom
                objs, used_layers = _users(d, existing)
                reassigned = _assign(d, rm, [o.Id for o in objs], [x.FullPath for x in used_layers])
                d.RenderMaterials.Remove(existing)
                rm.BeginChange(Rhino.Render.RenderContent.ChangeContexts.Program)
                rm.Name = name
                rm.EndChange()
            assigned = _assign(d, rm, ids, layers)
            return {"name": rm.Name, "id": str(rm.Id), "assigned": assigned, "replaced": existing is not None,
                    "reassigned": reassigned}
        if action == "assign":
            if not ids and not layers:
                raise McpError("assign : indique ids (objets) et/ou layers (calques).")
            return {"name": name, "assigned": _assign(d, find_material(d, _need(name, "name", action)), ids, layers)}
        if action == "delete":
            rm = find_material(d, _need(name, "name", action))
            if not d.RenderMaterials.Remove(rm):
                raise McpError("Suppression du matériau impossible : %s" % name)
            return {"deleted": name}
    raise McpError("Action inconnue : %s (list, create, assign, delete)." % action)


# --------------------------------------------------------------------------- #
# Blocs
# --------------------------------------------------------------------------- #
def _block(d, name):
    idef = d.InstanceDefinitions.Find(_need(name, "name", "bloc"))
    if idef is None or idef.IsDeleted:
        raise McpError("Bloc introuvable : %s" % name)
    return idef


@command("rhino_block")
def rhino_block(action="list", name=None, ids=None, base_point=None, description=None, delete_input=True,
                point=None, scale=1.0, rotation=0.0, explode_nested=False, layer=None):
    action = (action or "list").strip().lower()
    d = doc()
    if action == "list":
        blocks = []
        for idef in d.InstanceDefinitions:
            if idef is None or idef.IsDeleted or (idef.Name or "").startswith("*"):  # « * » = interne à Rhino
                continue
            blocks.append({"name": idef.Name, "description": idef.Description, "objects": idef.ObjectCount,
                           "instances": len(idef.GetReferences(0) or [])})
        return {"blocks": blocks}
    with Undo("bloc " + action) as d:
        if action == "create":
            name = _need(name, "name", action)
            if d.InstanceDefinitions.Find(name) is not None:
                raise McpError("Un bloc « %s » existe déjà." % name)
            objs = find_objects(d, _need(ids, "ids", action))
            if base_point is not None:
                base = to_point(base_point, "base_point")
            else:
                bb = G.BoundingBox.Empty
                for o in objs:
                    bb = G.BoundingBox.Union(bb, o.Geometry.GetBoundingBox(True))
                base = bb.Min
            index = d.InstanceDefinitions.Add(
                name, description or "", base,
                typed_list(G.GeometryBase, [o.Geometry.Duplicate() for o in objs]),
                typed_list(Rhino.DocObjects.ObjectAttributes, [o.Attributes.Duplicate() for o in objs]))
            if index < 0:
                raise McpError("Création du bloc impossible.")
            instance = None
            if delete_input:  # comme la commande Block : les objets deviennent une instance du bloc
                for o in objs:
                    d.Objects.Delete(o.Id, True)
                instance = d.Objects.AddInstanceObject(index, G.Transform.Translation(G.Vector3d(base)))
            return {"name": name, "objects": len(objs), "base_point": [base.X, base.Y, base.Z],
                    "instance_id": str(instance) if instance else None}
        if action == "insert":
            idef = _block(d, name)
            p = to_point(point, "point") if point is not None else G.Point3d.Origin
            xform = (G.Transform.Translation(G.Vector3d(p))
                     * G.Transform.Rotation(math.radians(float(rotation or 0)), G.Vector3d.ZAxis, G.Point3d.Origin)
                     * G.Transform.Scale(G.Point3d.Origin, float(scale or 1)))
            gid = d.Objects.AddInstanceObject(idef.Index, xform, attributes(d, layer))
            return created(d, [gid])
        if action == "explode":
            pieces = []
            for o in find_objects(d, _need(ids, "ids", action)):
                if not isinstance(o, Rhino.DocObjects.InstanceObject):
                    raise McpError("%s n'est pas une instance de bloc." % o.Id)
                pieces += list(d.Objects.AddExplodedInstancePieces(o, bool(explode_nested), True) or [])
            return created(d, pieces)
        if action == "delete":
            idef = _block(d, name)
            if not d.InstanceDefinitions.Delete(idef.Index, True, True):
                raise McpError("Suppression du bloc impossible : %s" % name)
            return {"deleted": name}
    raise McpError("Action inconnue : %s (list, create, insert, explode, delete)." % action)
