# -*- coding: utf-8 -*-
"""Rhino : document et fichiers (infos, nouveau, ouvrir, enregistrer, importer, exporter), annulation, plug-ins."""
import os

import Rhino
import Rhino.FileIO as F
import Rhino.Geometry as G

from . import VERSION
from .registry import McpError, command
from .util import MAX_ITEMS, Undo, doc, ensure_idle, find_objects, iter_objects, layer_path, object_summary, rgb

# Import/export SANS AUCUNE QUESTION. RhinoDoc.Export/ExportSelected/Import, et même WriteFile avec
# SuppressAllInput, attendent des réponses en ligne de commande pour STL, OBJ, DWG, STEP... et bloquent
# Rhino : on passe par les lecteurs/écrivains dédiés de RhinoCommon (vérifiés un par un sur Rhino 8.36).
WRITERS = {
    ".stl": ("FileStl", "FileStlWriteOptions"), ".obj": ("FileObj", "FileObjWriteOptions"),
    ".dwg": ("FileDwg", "FileDwgWriteOptions"), ".dxf": ("FileDwg", "FileDwgWriteOptions"),
    ".stp": ("FileStp", "FileStpWriteOptions"), ".step": ("FileStp", "FileStpWriteOptions"),
    ".igs": ("FileIgs", "FileIgsWriteOptions"), ".iges": ("FileIgs", "FileIgsWriteOptions"),
    ".fbx": ("FileFbx", "FileFbxWriteOptions"), ".3mf": ("File3mf", "File3mfWriteOptions"),
    ".glb": ("FileGltf", "FileGltfWriteOptions"), ".gltf": ("FileGltf", "FileGltfWriteOptions"),
    ".skp": ("FileSkp", "FileSkpWriteOptions"), ".ply": ("FilePly", "FilePlyWriteOptions"),
    ".sat": ("FileSat", "FileSatWriteOptions"), ".3ds": ("File3ds", "File3dsWriteOptions"),
    ".usd": ("FileUsd", "FileUsdWriteOptions"), ".usda": ("FileUsd", "FileUsdWriteOptions"),
    ".usdc": ("FileUsd", "FileUsdWriteOptions"), ".usdz": ("FileUsd", "FileUsdWriteOptions"),
}
READERS = {
    ".stl": ("FileStl", "FileStlReadOptions"), ".obj": ("FileObj", "FileObjReadOptions"),
    ".dwg": ("FileDwg", "FileDwgReadOptions"), ".dxf": ("FileDwg", "FileDwgReadOptions"),
    ".stp": ("FileStp", "FileStpReadOptions"), ".step": ("FileStp", "FileStpReadOptions"),
    ".fbx": ("FileFbx", "FileFbxReadOptions"), ".3ds": ("File3ds", "File3dsReadOptions"),
    ".ply": ("FilePly", "FilePlyReadOptions"), ".skp": ("FileSkp", "FileSkpReadOptions"),
}
BATCH_READ = (".3dm", ".igs", ".iges", ".3mf", ".glb", ".gltf")  # RhinoDoc.ReadFile en mode batch


def _write_options():
    o = F.FileWriteOptions()
    o.SuppressAllInput = True
    o.SuppressDialogBoxes = True
    o.UpdateDocumentPath = False
    return o


def _read_options():
    o = F.FileReadOptions()
    o.ImportMode = True
    o.BatchMode = True
    return o


def _format_options(name, base):
    """Options d'un format : certaines se construisent à partir des options générales (OBJ, PLY)."""
    cls = getattr(F, name)
    try:
        return cls()
    except TypeError:
        return cls(base())


def _succeeded(result):
    return result is True or str(result) in ("True", "Success")


@command("rhino_ping", "ping")
def rhino_ping():
    d = Rhino.RhinoDoc.ActiveDoc
    return {
        "rhino_version": str(Rhino.RhinoApp.Version),
        "listener_version": VERSION,
        "document": d.Name if d else None,
        "path": d.Path if d else None,
        "modified": bool(d.Modified) if d else None,
        "process_id": os.getpid(),
    }


@command("rhino_get_document_info", "get_document_info")
def rhino_get_document_info():
    d = doc()
    counts = {}
    total = 0
    for o in iter_objects(d):
        t = str(o.ObjectType)
        counts[t] = counts.get(t, 0) + 1
        total += 1
    layers = []
    for layer in d.Layers:
        if layer.IsDeleted:
            continue
        layers.append({
            "name": layer.FullPath,
            "visible": layer.IsVisible,
            "locked": layer.IsLocked,
            "color": rgb(layer.Color),
        })
    return {
        "name": d.Name,
        "path": d.Path,
        "modified": bool(d.Modified),
        "units": str(d.ModelUnitSystem),
        "tolerance": d.ModelAbsoluteTolerance,
        "angle_tolerance_degrees": d.ModelAngleToleranceDegrees,
        "object_count": total,
        "objects_by_type": counts,
        "selected_count": len(list(d.Objects.GetSelectedObjects(False, False))),
        "current_layer": d.Layers.CurrentLayer.FullPath,
        "layers": layers[:MAX_ITEMS],
        "views": [v.ActiveViewport.Name for v in d.Views.GetViewList(True, False)],
        "layouts": [p.PageName for p in d.Views.GetPageViews()],
        "named_views": [d.NamedViews[i].Name for i in range(d.NamedViews.Count)],
        "materials": [m.Name for m in d.RenderMaterials],
        "blocks": [idef.Name for idef in d.InstanceDefinitions if idef is not None and not idef.IsDeleted],
        "layer_states": list(d.NamedLayerStates.Names),
    }


# --------------------------------------------------------------------------- #
# Fichiers
# --------------------------------------------------------------------------- #
def _doc_status():
    d = doc()
    return {"document": d.Name, "path": d.Path, "modified": bool(d.Modified),
            "units": str(d.ModelUnitSystem), "object_count": len(list(iter_objects(d)))}


def _existing_file(path):
    if not path:
        raise McpError("Chemin de fichier requis (path).")
    path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
    if not os.path.isfile(path):
        raise McpError("Fichier introuvable : %s" % path)
    return path


def _same_path(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _target_file(path, overwrite, default_ext=None):
    """Chemin de destination : crée le dossier, refuse d'écraser un fichier existant sans overwrite."""
    if not path:
        raise McpError("Chemin de fichier requis (path).")
    path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
    if default_ext and not os.path.splitext(path)[1]:
        path += default_ext
    if os.path.exists(path) and not overwrite and not _same_path(path, doc().Path):
        raise McpError("Le fichier %s existe déjà : relance avec overwrite=true pour le remplacer." % path)
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    return path


def _guard_unsaved(discard_changes):
    """Jamais de perte silencieuse : refuse si le document actif a des modifications non enregistrées."""
    d = Rhino.RhinoDoc.ActiveDoc
    if d is None or not d.Modified:
        return
    if not discard_changes:
        raise McpError("Le document actif « %s » a des modifications non enregistrées. Enregistre-le "
                       "(action save ou save_as) ou relance avec discard_changes=true pour les abandonner."
                       % (d.Name or "Sans titre"))
    d.Modified = False


def _new(template, discard_changes):
    ensure_idle()
    if template:
        template = _existing_file(template)
    _guard_unsaved(discard_changes)
    macro = '_-New "%s"' % template if template else "_-New _None"
    if not Rhino.RhinoApp.RunScript(macro, False):
        raise McpError("La création du document a échoué.")
    return _doc_status()


def _open(path, discard_changes):
    ensure_idle()
    path = _existing_file(path)
    if not path.lower().endswith(".3dm"):
        raise McpError("open n'ouvre que les fichiers .3dm. Pour un autre format (dwg, obj, step...), "
                       "crée un document (action new) puis importe-le (action import).")
    _guard_unsaved(discard_changes)
    opened = Rhino.RhinoDoc.Open(path)
    d = opened[0] if isinstance(opened, tuple) else opened
    if d is None:
        raise McpError("Impossible d'ouvrir %s" % path)
    return _doc_status()


def _save(path, version, overwrite):
    ensure_idle()
    d = doc()
    if not path and not version:
        if not d.Path:
            raise McpError("Le document n'a jamais été enregistré : indique un chemin (action save_as).")
        if not d.Save():
            raise McpError("Échec de l'enregistrement de %s." % d.Path)
        return _doc_status()
    # Enregistrer sous : la commande -SaveAs (RhinoDoc.SaveAs n'écrit qu'une copie, sans changer de fichier).
    path = _target_file(path or d.Path, overwrite, ".3dm")
    if not path.lower().endswith(".3dm"):
        raise McpError("save_as enregistre en .3dm ; pour un autre format, utilise l'action export.")
    previous = os.path.getmtime(path) if os.path.exists(path) else None
    option = "_Version=%d " % int(version) if version else ""
    Rhino.RhinoApp.RunScript('_-SaveAs %s"%s"' % (option, path), False)
    written = os.path.isfile(path) and os.path.getmtime(path) != previous
    status = _doc_status()
    if version and int(version) < Rhino.RhinoApp.ExeVersion:
        # Ancienne version : Rhino écrit une copie et le document reste lié à son fichier actuel.
        if not written:
            raise McpError("Échec de l'enregistrement en version %s sous %s." % (version, path))
        status["saved_copy"] = path
        status["copy_version"] = int(version)
        return status
    if not written or not _same_path(status["path"], path) or status["modified"]:
        raise McpError("Échec de l'enregistrement sous %s." % path)
    return status


def _import(path):
    ensure_idle()
    path = _existing_file(path)
    ext = os.path.splitext(path)[1].lower()
    if ext not in READERS and ext not in BATCH_READ:
        raise McpError("Import sans question non pris en charge pour %s. Formats : %s. Sinon : rhino_run_command "
                       "avec '_-Import \"chemin\"' et les options du format." % (ext, ", ".join(_import_formats())))
    with Undo("import") as d:
        before = set(o.Id for o in iter_objects(d))
        if ext in READERS:
            cls, opt = READERS[ext]
            ok = _succeeded(getattr(F, cls).Read(path, d, _format_options(opt, _read_options)))
        else:
            ok = Rhino.RhinoDoc.ReadFile(path, _read_options())
        new = [o for o in iter_objects(d) if o.Id not in before]
    if not ok:
        raise McpError("Import impossible : %s (fichier invalide ?)." % path)
    return {"path": path, "imported": len(new), "objects": [object_summary(o) for o in new[:MAX_ITEMS]]}


def _import_formats():
    return sorted(set(READERS) | set(BATCH_READ))


def _copy_into(src, dst, o, xform):
    """Copie un objet (blocs éclatés) dans un document sans fenêtre, en recréant son calque."""
    a = o.Attributes.Duplicate()
    a.RemoveFromAllGroups()
    a.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromLayer
    path = layer_path(src, o.Attributes.LayerIndex)
    if path:
        idx = dst.Layers.FindByFullPath(path, -1)
        if idx < 0:
            idx = dst.Layers.AddPath(path, src.Layers[o.Attributes.LayerIndex].Color)
        a.LayerIndex = idx
    if isinstance(o, Rhino.DocObjects.InstanceObject):
        for sub in o.InstanceDefinition.GetObjects():
            _copy_into(src, dst, sub, xform * o.InstanceXform)
        return
    g = o.Geometry.Duplicate()
    if not xform.IsIdentity:
        g.Transform(xform)
    dst.Objects.Add(g, a)


def _write_doc(d, path, ext):
    if ext == ".3dm":
        return d.WriteFile(path, _write_options())
    cls, opt = WRITERS[ext]
    return _succeeded(getattr(F, cls).Write(path, d, _format_options(opt, _write_options)))


def _export(path, ids, selected_only, overwrite):
    ensure_idle()
    d = doc()
    path = _target_file(path, overwrite)
    ext = os.path.splitext(path)[1].lower()
    if ext != ".3dm" and ext not in WRITERS:
        raise McpError("Export sans question non pris en charge pour « %s ». Formats : %s. Pour le PDF : "
                       "rhino_layout. Sinon : rhino_run_command avec '_-Export \"chemin\"' et les options du format."
                       % (ext or "sans extension", ", ".join(sorted(set(WRITERS) | {".3dm"}))))
    if ids:
        objs = find_objects(d, ids)
    elif selected_only:
        objs = list(d.Objects.GetSelectedObjects(False, False))
        if not objs:
            raise McpError("Aucun objet sélectionné à exporter.")
    else:
        objs = None
    if objs is None:  # tout le document
        ok = _write_doc(d, path, ext)
    else:  # une partie : copie dans un document sans fenêtre, écrit, puis jeté
        if ext == ".skp":
            raise McpError("SketchUp (.skp) : seul l'export du document entier est possible (sans ids ni sélection).")
        tmp = Rhino.RhinoDoc.CreateHeadless(None)
        try:
            tmp.ModelUnitSystem = d.ModelUnitSystem
            tmp.ModelAbsoluteTolerance = d.ModelAbsoluteTolerance
            for o in objs:
                _copy_into(d, tmp, o, G.Transform.Identity)
            ok = _write_doc(tmp, path, ext)
        finally:
            tmp.Dispose()
    if not ok or not os.path.isfile(path):
        raise McpError("Export impossible vers %s." % path)
    return {"path": path, "size_bytes": os.path.getsize(path), "objects": len(objs) if objs else "document"}


@command("rhino_document")
def rhino_document(action, path=None, template=None, discard_changes=False, ids=None, selected_only=False,
                   version=None, overwrite=False):
    action = (action or "").strip().lower()
    if action == "new":
        return _new(template, discard_changes)
    if action == "open":
        return _open(path, discard_changes)
    if action == "save":
        return _save(path, version, overwrite)
    if action == "save_as":
        if not path:
            raise McpError("save_as : indique le chemin (path).")
        return _save(path, version, overwrite)
    if action == "import":
        return _import(path)
    if action == "export":
        return _export(path, ids, selected_only, overwrite)
    raise McpError("Action inconnue : %s (new, open, save, save_as, import, export)." % action)


# --------------------------------------------------------------------------- #
# Annulation et plug-ins
# --------------------------------------------------------------------------- #
@command("rhino_undo")
def rhino_undo(action="undo", steps=1):
    """Passe par les commandes _Undo/_Redo (comme Ctrl+Z / Ctrl+Y) : RhinoDoc.Redo ne rétablit pas
    ce que RhinoDoc.Undo a annulé. Les étapes réellement effectuées sont comptées par l'évènement UndoRedo."""
    ensure_idle()
    d = doc()
    action = (action or "undo").strip().lower()
    if action not in ("undo", "redo"):
        raise McpError("Action inconnue : %s (undo ou redo)." % action)
    done = {"steps": 0}

    def on_undo_redo(sender, e):
        if (e.IsEndUndo if action == "undo" else e.IsEndRedo):
            done["steps"] += 1

    Rhino.Commands.Command.UndoRedo += on_undo_redo
    try:
        for _ in range(max(1, min(int(steps), 100))):
            before = done["steps"]
            Rhino.RhinoApp.RunScript("_Undo" if action == "undo" else "_Redo", False)
            if done["steps"] == before:  # plus rien à annuler / rétablir
                break
    finally:
        Rhino.Commands.Command.UndoRedo -= on_undo_redo
    d.Views.Redraw()
    return {"action": action, "steps_done": done["steps"]}


@command("rhino_list_plugins")
def rhino_list_plugins(query=None, loaded_only=False, include_commands=False):
    q = (query or "").lower()
    plugins = []
    for kv in Rhino.PlugIns.PlugIn.GetInstalledPlugIns():
        plugin_id, name = kv.Key, kv.Value
        if q and q not in (name or "").lower():
            continue
        exists = Rhino.PlugIns.PlugIn.PlugInExists(plugin_id)
        loaded = bool(exists[1]) if isinstance(exists, tuple) else None
        if loaded_only and not loaded:
            continue
        plugins.append({"name": name, "id": str(plugin_id), "loaded": loaded})
    result = {"plugins": sorted(plugins, key=lambda p: (p["name"] or "").lower())}
    if include_commands:
        names = [n for n in Rhino.Commands.Command.GetCommandNames(True, True) if not q or q in n.lower()]
        result["commands"] = sorted(names)[:MAX_ITEMS]
        result["command_count"] = len(names)
    return result
