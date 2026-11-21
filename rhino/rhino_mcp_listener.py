#! python3
# -*- coding: utf-8 -*-
"""
Rhino MCP - écouteur côté Rhino 8 (Python 3, compatible Rhino 8.12+).

Lancer dans Rhino :
    _-RunPythonScript "C:\\chemin\\vers\\rhino\\rhino_mcp_listener.py"

Le script écoute sur 127.0.0.1:1999 (connexions locales uniquement) et exécute
les commandes envoyées par le serveur MCP (server/rhino_mcp_server.py).
Relancer le script redémarre l'écouteur (utile après une modification du code).

Tout s'exécute sur le fil principal de Rhino grâce à un minuteur Eto : pas de
thread Python en arrière-plan, donc pas de problème d'accès à RhinoCommon.
"""
import io
import json
import socket
import sys
import traceback

import clr

clr.AddReference("Eto")

import System  # noqa: E402
import System.Drawing  # noqa: E402
import Eto.Forms  # noqa: E402
import Rhino  # noqa: E402
import rhinoscriptsyntax as rs  # noqa: E402
import scriptcontext as sc  # noqa: E402

HOST = "127.0.0.1"
PORT = 1999
STICKY_KEY = "rhino_mcp_listener"
MAX_ITEMS = 500


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def _impl(o):
    """pythonnet 3 renvoie parfois une vue 'interface' : récupère l'objet réel."""
    return getattr(o, "__implementation__", o)


def _doc():
    doc = Rhino.RhinoDoc.ActiveDoc
    if doc is None:
        raise RuntimeError("Aucun document Rhino actif.")
    sc.doc = doc
    return doc


def _pt(p):
    return [round(p.X, 6), round(p.Y, 6), round(p.Z, 6)]


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        if isinstance(v, (list, tuple)):
            return [_jsonable(x) for x in v]
        if isinstance(v, dict):
            return {str(k): _jsonable(x) for k, x in v.items()}
        return str(v)


# --------------------------------------------------------------------------- #
# Commandes Rhino
# --------------------------------------------------------------------------- #
def cmd_ping():
    doc = Rhino.RhinoDoc.ActiveDoc
    return {
        "rhino_version": str(Rhino.RhinoApp.Version),
        "document": doc.Name if doc else None,
        "path": doc.Path if doc else None,
    }


def _enum_settings():
    s = Rhino.DocObjects.ObjectEnumeratorSettings()
    s.HiddenObjects = True
    s.LockedObjects = True
    return s


def cmd_get_document_info():
    doc = _doc()
    counts = {}
    total = 0
    for obj in doc.Objects.GetObjectList(_enum_settings()):
        t = str(obj.ObjectType)
        counts[t] = counts.get(t, 0) + 1
        total += 1
    layers = []
    for layer in doc.Layers:
        if layer.IsDeleted:
            continue
        layers.append({
            "name": layer.FullPath,
            "visible": layer.IsVisible,
            "locked": layer.IsLocked,
            "color": [layer.Color.R, layer.Color.G, layer.Color.B],
        })
    return {
        "name": doc.Name,
        "path": doc.Path,
        "units": str(doc.ModelUnitSystem),
        "tolerance": doc.ModelAbsoluteTolerance,
        "object_count": total,
        "objects_by_type": counts,
        "current_layer": doc.Layers.CurrentLayer.FullPath,
        "layers": layers[:MAX_ITEMS],
        "views": [v.ActiveViewport.Name for v in doc.Views],
    }


def cmd_get_objects(layer=None, selected_only=False, limit=200, offset=0):
    doc = _doc()
    out = []
    i = 0
    for obj in doc.Objects.GetObjectList(_enum_settings()):
        if selected_only and not obj.IsSelected(False):
            continue
        layer_name = doc.Layers[obj.Attributes.LayerIndex].FullPath
        if layer and layer_name.lower() != layer.lower():
            continue
        if i >= offset and len(out) < limit:
            bb = obj.Geometry.GetBoundingBox(True)
            out.append({
                "id": str(obj.Id),
                "type": str(obj.ObjectType),
                "name": obj.Attributes.Name,
                "layer": layer_name,
                "bbox_min": _pt(bb.Min),
                "bbox_max": _pt(bb.Max),
            })
        i += 1
    return {"total": i, "offset": offset, "objects": out}


def cmd_execute_python(code):
    """Exécute du Python dans Rhino. Affecter `result` pour renvoyer une valeur."""
    doc = _doc()
    ns = {
        "__name__": "__rhino_mcp__",
        "Rhino": Rhino,
        "rs": rs,
        "sc": sc,
        "System": System,
        "doc": doc,
        "get_gh_doc": lambda: _gh_doc()[1],
        "result": None,
    }
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf
    undo = doc.BeginUndoRecord("MCP: script Python")
    error = None
    try:
        exec(compile(code, "<mcp>", "exec"), ns)
    except Exception:
        error = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        if undo:
            doc.EndUndoRecord(undo)
        doc.Views.Redraw()
    out = {"stdout": buf.getvalue()[-20000:], "result": _jsonable(ns.get("result"))}
    if error:
        out["error"] = error
    return out


def cmd_capture_view(width=900, height=600, view=None):
    doc = _doc()
    v = doc.Views.Find(view, False) if view else doc.Views.ActiveView
    if v is None:
        raise RuntimeError("Vue introuvable : %s" % view)
    bmp = v.CaptureToBitmap(System.Drawing.Size(int(width), int(height)))
    ms = System.IO.MemoryStream()
    bmp.Save(ms, System.Drawing.Imaging.ImageFormat.Png)
    data = System.Convert.ToBase64String(ms.ToArray())
    bmp.Dispose()
    ms.Dispose()
    return {"view": v.ActiveViewport.Name, "image_base64": data}


# --------------------------------------------------------------------------- #
# Grasshopper
# --------------------------------------------------------------------------- #
def _gh_doc(create=True):
    try:
        import Grasshopper
        canvas = Grasshopper.Instances.ActiveCanvas
    except Exception:
        canvas = None
    if canvas is None:
        Rhino.RhinoApp.RunScript("_Grasshopper", False)
        clr.AddReference("Grasshopper")
        import Grasshopper
        canvas = Grasshopper.Instances.ActiveCanvas
    if canvas is None:
        raise RuntimeError("Grasshopper n'est pas ouvert. Lance la commande Grasshopper dans Rhino puis réessaie.")
    gdoc = canvas.Document
    if gdoc is None:
        if not create:
            raise RuntimeError("Aucun document Grasshopper ouvert.")
        gdoc = Grasshopper.Kernel.GH_Document()
        Grasshopper.Instances.DocumentServer.AddDocument(gdoc)
        canvas.Document = gdoc
    return Grasshopper, _impl(gdoc)


def _gh_find(gdoc, obj_id):
    o = gdoc.FindObject(System.Guid(str(obj_id)), True)
    if o is None:
        raise RuntimeError("Objet Grasshopper introuvable : %s" % obj_id)
    return _impl(o)


def _gh_params(o):
    """(entrées, sorties) d'un composant ; un paramètre isolé est sa propre entrée/sortie."""
    if hasattr(o, "Params"):
        return [_impl(p) for p in o.Params.Input], [_impl(p) for p in o.Params.Output]
    if hasattr(o, "Sources"):
        return [o], [o]
    return [], []


def _gh_pick(params, key):
    if not params:
        raise RuntimeError("Cet objet n'a pas de paramètre de ce côté.")
    if key is None:
        return params[0]
    if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
        return params[int(key)]
    k = str(key).lower()
    for p in params:
        if p.Name.lower() == k or p.NickName.lower() == k:
            return p
    raise RuntimeError("Paramètre '%s' introuvable. Disponibles : %s"
                       % (key, ", ".join("%s (%s)" % (p.Name, p.NickName) for p in params)))


def _gh_owner_id(param):
    try:
        return str(_impl(param.Attributes.GetTopLevel.DocObject).InstanceGuid)
    except Exception:
        return None


def _gh_param_desc(p):
    return {
        "name": p.Name,
        "nickname": p.NickName,
        "type": p.TypeName,
        "sources": [{"id": _gh_owner_id(_impl(s)), "param": _impl(s).NickName} for s in p.Sources],
    }


def _gh_messages(o):
    import Grasshopper
    msgs = {}
    if hasattr(o, "RuntimeMessages"):
        for name in ("Error", "Warning"):
            level = getattr(Grasshopper.Kernel.GH_RuntimeMessageLevel, name)
            lst = [str(m) for m in o.RuntimeMessages(level)]
            if lst:
                msgs[name.lower()] = lst
    return msgs


def _gh_describe(o):
    o = _impl(o)
    d = {
        "id": str(o.InstanceGuid),
        "name": o.Name,
        "nickname": o.NickName,
        "type": o.GetType().Name,
        "position": [round(o.Attributes.Pivot.X, 1), round(o.Attributes.Pivot.Y, 1)],
    }
    tname = o.GetType().Name
    if hasattr(o, "Params"):
        ins, outs = _gh_params(o)
        d["inputs"] = [_gh_param_desc(p) for p in ins]
        d["outputs"] = [_gh_param_desc(p) for p in outs]
    elif hasattr(o, "Sources"):
        d["sources"] = _gh_param_desc(o)["sources"]
    if tname == "GH_NumberSlider":
        d["value"] = System.Convert.ToDouble(o.CurrentValue)
        d["min"] = System.Convert.ToDouble(o.Slider.Minimum)
        d["max"] = System.Convert.ToDouble(o.Slider.Maximum)
    elif tname == "GH_Panel":
        d["value"] = o.UserText
    elif tname == "GH_BooleanToggle":
        d["value"] = bool(o.Value)
    msgs = _gh_messages(o)
    if msgs:
        d["messages"] = msgs
    return d


def cmd_gh_get_canvas():
    _, gdoc = _gh_doc()
    objs = [_gh_describe(o) for o in gdoc.Objects]
    return {"file": gdoc.FilePath, "object_count": len(objs), "objects": objs[:MAX_ITEMS]}


def _gh_proxies(gh):
    for proxy in gh.Instances.ComponentServer.ObjectProxies:
        p = _impl(proxy)
        if not p.Obsolete:
            yield p


def cmd_gh_search_components(query, limit=30):
    gh, _ = _gh_doc()
    q = query.lower()
    hits = []
    for p in _gh_proxies(gh):
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


def cmd_gh_add_component(name=None, guid=None, x=0, y=0, nickname=None):
    gh, gdoc = _gh_doc()
    proxy = None
    if guid:
        proxy = gh.Instances.ComponentServer.EmitObjectProxy(System.Guid(str(guid)))
    else:
        n = name.lower()
        exact, by_nick = None, None
        for p in _gh_proxies(gh):
            if p.Desc.Name.lower() == n and exact is None:
                exact = p
            elif (p.Desc.NickName or "").lower() == n and by_nick is None:
                by_nick = p
        proxy = exact or by_nick
    if proxy is None:
        sugg = [h["name"] for h in cmd_gh_search_components(name or "", 8)]
        raise RuntimeError("Composant '%s' introuvable. Suggestions : %s" % (name or guid, ", ".join(sugg)))
    obj = _impl(_impl(proxy).CreateInstance())
    obj.CreateAttributes()
    if nickname:
        obj.NickName = nickname
    obj.Attributes.Pivot = System.Drawing.PointF(float(x), float(y))
    gdoc.AddObject(obj, False)
    gh.Instances.ActiveCanvas.Refresh()
    return _gh_describe(obj)


def cmd_gh_connect(source_id, target_id, source_output=0, target_input=0, disconnect=False):
    gh, gdoc = _gh_doc()
    src, tgt = _gh_find(gdoc, source_id), _gh_find(gdoc, target_id)
    sp = _gh_pick(_gh_params(src)[1], source_output)
    tp = _gh_pick(_gh_params(tgt)[0], target_input)
    if disconnect:
        tp.RemoveSource(sp)
    else:
        tp.AddSource(sp)
    tgt.ExpireSolution(True)
    gh.Instances.ActiveCanvas.Refresh()
    return _gh_describe(tgt)


def cmd_gh_set_value(id, value, min=None, max=None, decimals=None):
    gh, gdoc = _gh_doc()
    o = _gh_find(gdoc, id)
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
        raise RuntimeError("gh_set_value gère les curseurs (Number Slider), panneaux (Panel) et interrupteurs "
                           "(Boolean Toggle). Pour '%s', utilise rhino_execute_python." % tname)
    o.ExpireSolution(True)
    gh.Instances.ActiveCanvas.Refresh()
    return _gh_describe(o)


def cmd_gh_get_output(id, output=0, limit=200):
    _, gdoc = _gh_doc()
    o = _gh_find(gdoc, id)
    p = _gh_pick(_gh_params(o)[1], output)
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


def cmd_gh_solve():
    gh, gdoc = _gh_doc()
    gdoc.NewSolution(True)
    gh.Instances.ActiveCanvas.Refresh()
    problems = []
    for o in gdoc.Objects:
        o = _impl(o)
        m = _gh_messages(o)
        if m:
            problems.append({"id": str(o.InstanceGuid), "name": o.NickName, "messages": m})
    return {"objects": gdoc.ObjectCount, "problems": problems}


def cmd_gh_delete(ids):
    gh, gdoc = _gh_doc()
    removed = []
    for i in ids:
        o = _gh_find(gdoc, i)
        gdoc.RemoveObject(o, False)
        removed.append(str(i))
    gdoc.NewSolution(False)
    gh.Instances.ActiveCanvas.Refresh()
    return {"removed": removed}


COMMANDS = {
    "ping": cmd_ping,
    "get_document_info": cmd_get_document_info,
    "get_objects": cmd_get_objects,
    "execute_python": cmd_execute_python,
    "capture_view": cmd_capture_view,
    "gh_get_canvas": cmd_gh_get_canvas,
    "gh_search_components": cmd_gh_search_components,
    "gh_add_component": cmd_gh_add_component,
    "gh_connect": cmd_gh_connect,
    "gh_set_value": cmd_gh_set_value,
    "gh_get_output": cmd_gh_get_output,
    "gh_solve": cmd_gh_solve,
    "gh_delete": cmd_gh_delete,
}


def dispatch(command, params):
    fn = COMMANDS.get(command)
    if fn is None:
        raise RuntimeError("Commande inconnue : %s" % command)
    return fn(**params)


# --------------------------------------------------------------------------- #
# Écouteur TCP piloté par un minuteur du fil principal
# --------------------------------------------------------------------------- #
class Listener(object):
    def __init__(self, port):
        self.port = port
        self.busy = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((HOST, port))
        self.sock.listen(5)
        self.sock.setblocking(False)
        self.timer = Eto.Forms.UITimer()
        self.timer.Interval = 0.05
        self.timer.Elapsed += self._on_tick
        self.timer.Start()

    def stop(self):
        try:
            self.timer.Stop()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    def _on_tick(self, sender, e):
        if self.busy:
            return
        self.busy = True
        try:
            for _ in range(10):
                try:
                    conn, _addr = self.sock.accept()
                except OSError:
                    break
                self._serve(conn)
        except Exception:
            Rhino.RhinoApp.WriteLine("Rhino MCP : " + traceback.format_exc())
        finally:
            self.busy = False

    def _serve(self, conn):
        try:
            conn.setblocking(True)
            conn.settimeout(10)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            try:
                req = json.loads(buf.decode("utf-8"))
                result = dispatch(req.get("command"), req.get("params") or {})
                resp = {"ok": True, "result": result}
            except Exception as ex:
                resp = {"ok": False, "error": "%s: %s" % (type(ex).__name__, ex),
                        "traceback": traceback.format_exc()}
            conn.sendall((json.dumps(resp, default=str) + "\n").encode("utf-8"))
        finally:
            conn.close()


def start(port=PORT):
    old = sc.sticky.get(STICKY_KEY)
    if old is not None:
        try:
            old.stop()
        except Exception:
            pass
        sc.sticky.pop(STICKY_KEY, None)
    try:
        sc.sticky[STICKY_KEY] = Listener(port)
    except OSError as ex:
        Rhino.RhinoApp.WriteLine("Rhino MCP : impossible d'écouter sur le port %d (%s)." % (port, ex))
        return
    Rhino.RhinoApp.WriteLine("Rhino MCP : prêt, en écoute sur %s:%d." % (HOST, port))


start()
