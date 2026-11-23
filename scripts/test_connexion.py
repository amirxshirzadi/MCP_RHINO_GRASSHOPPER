# -*- coding: utf-8 -*-
"""
Test de bout en bout du MCP Rhino & Grasshopper.

Lance le serveur MCP exactement comme Claude Code (stdio), puis appelle chaque
outil sur le Rhino ouvert (écouteur MCPStart actif) et vérifie les résultats.

    python scripts/test_connexion.py              # tous les tests
    python scripts/test_connexion.py --sans-gh    # sans Grasshopper
    python scripts/test_connexion.py -k calque    # seulement les tests dont le nom contient « calque »

Utilise de préférence le Python de Rhino (celui de .mcp.json) :
    & "$env:USERPROFILE\\.rhinocode\\py39-rh8\\python.exe" scripts\\test_connexion.py

Le test travaille dans un document Rhino et un document Grasshopper neufs :
enregistre ton travail avant de le lancer. Il nettoie derrière lui.
Code de sortie : 0 si tout passe, 1 si un test échoue, 2 si Rhino est injoignable.
"""
import argparse
import base64
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "server", "rhino_mcp_server.py")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------- #
# Client MCP minimal (stdio, JSON-RPC ligne par ligne)
# --------------------------------------------------------------------------- #
class McpClient(object):
    def __init__(self, port, timeout):
        env = dict(os.environ)
        env["RHINO_MCP_PORT"] = str(port)
        env["RHINO_MCP_TIMEOUT"] = str(timeout)
        self.proc = subprocess.Popen(
            [sys.executable, "-u", SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        self.messages = queue.Queue()
        self.stderr_tail = []
        self.next_id = 0
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        for raw in self.proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                self.messages.put(json.loads(line.decode("utf-8")))
            except ValueError:
                self.messages.put({"_invalid": line.decode("utf-8", "replace")})
        self.messages.put(None)

    def _read_stderr(self):
        for raw in self.proc.stderr:
            self.stderr_tail = (self.stderr_tail + [raw.decode("utf-8", "replace").rstrip()])[-20:]

    def _send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def request(self, method, params=None, timeout=180):
        self.next_id += 1
        msg_id = self.next_id
        self._send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise RuntimeError("pas de réponse du serveur MCP après %d s (%s)" % (timeout, method))
            try:
                msg = self.messages.get(timeout=remaining)
            except queue.Empty:
                continue
            if msg is None:
                raise RuntimeError("le serveur MCP s'est arrêté :\n" + "\n".join(self.stderr_tail))
            if "_invalid" in msg:
                raise RuntimeError("ligne non JSON sur stdout du serveur : %s" % msg["_invalid"])
            if msg.get("id") != msg_id:
                continue
            if "error" in msg:
                raise RuntimeError("erreur JSON-RPC : %s" % msg["error"])
            return msg["result"]

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(5)
        except Exception:
            self.proc.kill()


# --------------------------------------------------------------------------- #
# Petit cadre de test
# --------------------------------------------------------------------------- #
class TestFailure(Exception):
    pass


def check(condition, message):
    if not condition:
        raise TestFailure(message)


def result_text(result):
    return "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")


class Context(object):
    def __init__(self, client, args):
        self.client = client
        self.args = args
        self.tmp = tempfile.mkdtemp(prefix="rhino_mcp_test_")
        self.state = {}

    def call_raw(self, tool, arguments=None, timeout=None):
        # le serveur abandonne au bout de --timeout ; le client attend un peu plus pour recevoir son message
        wait = timeout or self.args.timeout + 30
        return self.client.request("tools/call", {"name": tool, "arguments": arguments or {}}, wait)

    def call(self, tool, arguments=None, timeout=None):
        """Appelle un outil, échoue s'il renvoie une erreur, renvoie le JSON décodé."""
        result = self.call_raw(tool, arguments, timeout)
        text = result_text(result)
        if result.get("isError"):
            raise TestFailure("%s a renvoyé une erreur :\n%s" % (tool, text[:1500]))
        try:
            return json.loads(text)
        except ValueError:
            return text

    def call_error(self, tool, arguments=None, contains=None):
        """Appelle un outil qui DOIT échouer proprement (isError) ; renvoie le texte de l'erreur."""
        result = self.call_raw(tool, arguments)
        text = result_text(result)
        check(result.get("isError"), "%s aurait dû renvoyer une erreur, a renvoyé :\n%s" % (tool, text[:500]))
        if contains:
            check(contains.lower() in text.lower(), "message d'erreur inattendu pour %s :\n%s" % (tool, text[:500]))
        return text

    def path(self, name):
        return os.path.join(self.tmp, name)


TESTS = []


def test(*tools, **options):
    """Déclare un test ; `tools` = outils couverts (rapport de couverture)."""
    def register(fn):
        TESTS.append({"name": fn.__name__, "tools": tools, "gh": options.get("gh", False), "fn": fn})
        return fn
    return register


# --------------------------------------------------------------------------- #
# Rhino
# --------------------------------------------------------------------------- #
@test("rhino_ping")
def rhino_ping(ctx):
    r = ctx.call("rhino_ping")
    check(str(r.get("rhino_version", "")).startswith("8."), "version de Rhino inattendue : %s" % r)


@test("rhino_get_document_info")
def rhino_document_info(ctx):
    r = ctx.call("rhino_get_document_info")
    for key in ("units", "tolerance", "layers", "views", "object_count"):
        check(key in r, "clé « %s » absente de rhino_get_document_info" % key)


def add_box(ctx, size=10, name=None):
    """Crée une boîte via rhino_execute_python (indépendant des outils de géométrie) ; renvoie son id."""
    code = (
        "import Rhino.Geometry as G\n"
        "bb = G.BoundingBox(G.Point3d(0, 0, 0), G.Point3d(%g, %g, %g))\n"
        "a = doc.CreateDefaultAttributes()\n"
        "a.Name = %r\n"
        "result = str(doc.Objects.AddBrep(G.Box(bb).ToBrep(), a))\n" % (size, size, size, name or "")
    )
    return ctx.call("rhino_execute_python", {"code": code})["result"]


@test("rhino_document")
def rhino_fichiers(ctx):
    box = add_box(ctx, name="boite_fichiers")
    path_3dm = ctx.path("essai.3dm")
    saved = ctx.call("rhino_document", {"action": "save_as", "path": path_3dm})
    check(os.path.isfile(path_3dm) and not saved["modified"] and saved["path"],
          "save_as n'a pas enregistré : %s" % saved)
    v7 = ctx.call("rhino_document", {"action": "save_as", "path": ctx.path("essai_v7.3dm"), "version": 7})
    with open(v7["saved_copy"], "rb") as fh:
        check(fh.read(32)[24:32].strip() == b"70", "save_as version 7 n'a pas écrit un fichier Rhino 7")
    check(v7["path"] == saved["path"], "après une copie en version 7, le document doit rester sur son fichier")
    for ext in ("stl", "obj", "dwg", "step"):  # formats qui posent des questions en ligne de commande
        path = ctx.path("boite." + ext)
        exp = ctx.call("rhino_document", {"action": "export", "path": path, "ids": [box]})
        check(os.path.getsize(path) > 0 and exp["objects"] == 1, "export %s inattendu : %s" % (ext, exp))
        imp = ctx.call("rhino_document", {"action": "import", "path": path})
        check(imp["imported"] >= 1, "import %s : aucun objet importé (%s)" % (ext, imp))
    whole = ctx.call("rhino_document", {"action": "export", "path": ctx.path("tout.fbx")})
    check(whole["objects"] == "document" and whole["size_bytes"] > 0, "export du document entier : %s" % whole)
    ctx.call_error("rhino_document", {"action": "export", "path": ctx.path("boite.stl")}, contains="existe déjà")
    ctx.call("rhino_document", {"action": "export", "path": ctx.path("boite.stl"), "overwrite": True})
    ctx.call_error("rhino_document", {"action": "export", "path": ctx.path("x.xyz")}, contains="non pris en charge")
    status = ctx.call("rhino_ping")
    check(status["path"] == saved["path"], "un export a changé le fichier du document : %s" % status)
    ctx.call_error("rhino_document", {"action": "new"}, contains="non enregistr")  # garde-fou
    ctx.call("rhino_document", {"action": "new", "discard_changes": True})
    opened = ctx.call("rhino_document", {"action": "open", "path": path_3dm})
    check(opened["object_count"] == 1 and opened["path"], "réouverture du .3dm inattendue : %s" % opened)
    ctx.call("rhino_document", {"action": "save"})
    ctx.call_error("rhino_document", {"action": "open", "path": ctx.path("absent.3dm")}, contains="introuvable")
    ctx.call("rhino_document", {"action": "new"})


@test("rhino_undo")
def rhino_annulation(ctx):
    box = add_box(ctx, name="boite_undo")
    ids = lambda: [o["id"] for o in ctx.call("rhino_get_objects", {"limit": 1000})["objects"]]
    undo = ctx.call("rhino_undo", {"action": "undo"})
    check(undo["steps_done"] == 1 and box not in ids(), "undo n'a pas retiré la boîte : %s" % undo)
    redo = ctx.call("rhino_undo", {"action": "redo"})
    check(redo["steps_done"] == 1 and box in ids(), "redo n'a pas rétabli la boîte : %s" % redo)


@test("rhino_run_command")
def rhino_commande(ctx):
    r = ctx.call("rhino_run_command", {"command": "_Sphere 0,0,0 5"})
    check(r["success"] and r["created_count"] == 1, "la commande Sphere n'a pas créé une sphère : %s" % r)
    ctx.call("rhino_execute_python", {"code": "doc.Objects.Delete(System.Guid('%s'), True)" % r["created"][0]["id"]})
    r = ctx.call("rhino_run_command", {"command": "_SelNone"})
    check(r["success"] and not r["selected"], "_SelNone a laissé une sélection : %s" % r)


@test("rhino_list_plugins")
def rhino_plugins(ctx):
    r = ctx.call("rhino_list_plugins", {"query": "grasshopper"})
    check(any("grasshopper" in p["name"].lower() for p in r["plugins"]), "Grasshopper absent des plug-ins : %s" % r)
    r = ctx.call("rhino_list_plugins", {"query": "sphere", "include_commands": True})
    check("Sphere" in r.get("commands", []), "commande Sphere absente : %s" % r.get("commands"))


def bbox_of(ctx, obj_id):
    o = ctx.call("rhino_get_object_details", {"ids": [obj_id]})["objects"][0]
    return o["bbox_min"], o["bbox_max"]


def near(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


@test("rhino_get_object_details", "rhino_modify_objects", "rhino_select_objects", "rhino_transform_objects",
      "rhino_delete_objects")
def rhino_objets(ctx):
    box = add_box(ctx, 10, name="boite_objets")
    geo = ctx.call("rhino_get_object_details", {"ids": [box]})["objects"][0]["geometry"]
    check(geo.get("solid") and abs(geo.get("volume", 0) - 1000) < 1e-6, "volume/solide inattendus : %s" % geo)

    ctx.call("rhino_modify_objects", {"ids": [box], "name": "cube", "layer": "Test MCP::Objets",
                                      "color": [255, 0, 0], "user_text": {"projet": "essai"}})
    det = ctx.call("rhino_get_object_details", {"ids": [box]})["objects"][0]
    check(det["name"] == "cube" and det["layer"] == "Test MCP::Objets" and det["color"] == [255, 0, 0]
          and det["user_text"].get("projet") == "essai", "modification d'attributs inattendue : %s" % det)
    found = ctx.call("rhino_get_objects", {"layer": "Test MCP::Objets", "type": "brep", "name": "cub"})
    check(found["total"] == 1, "filtres de rhino_get_objects : %s" % found)

    sel = ctx.call("rhino_select_objects", {"action": "select", "layer": "Test MCP::Objets"})
    check(sel["selected_count"] == 1, "sélection par calque : %s" % sel)
    check(ctx.call("rhino_select_objects", {"action": "get"})["selected_count"] == 1, "lecture de la sélection")
    check(ctx.call("rhino_select_objects", {"action": "clear"})["selected_count"] == 0, "désélection")

    ctx.call("rhino_transform_objects", {"ids": [box], "operation": "move", "vector": [100, 0, 0]})
    check(near(bbox_of(ctx, box)[0], [100, 0, 0]), "move : %s" % (bbox_of(ctx, box),))
    copy = ctx.call("rhino_transform_objects", {"ids": [box], "operation": "copy", "vector": [0, 50, 0]})
    arr = ctx.call("rhino_transform_objects", {"ids": [box], "operation": "array_linear", "count": 3,
                                               "vector": [20, 0, 0]})
    check(copy["count"] == 1 and arr["count"] == 2 and box not in arr["ids"], "copie/réseau : %s %s" % (copy, arr))
    polar = ctx.call("rhino_transform_objects", {"ids": [box], "operation": "array_polar", "count": 4,
                                                 "center": [0, 0, 0]})
    check(polar["count"] == 3, "réseau polaire : %s" % polar)
    ctx.call("rhino_transform_objects", {"ids": [box], "operation": "scale", "factor": 2})  # autour du centre
    lo, hi = bbox_of(ctx, box)
    check(near(lo, [95, -5, -5]) and near(hi, [115, 15, 15]), "scale x2 : %s" % ((lo, hi),))
    ctx.call("rhino_transform_objects", {"ids": [box], "operation": "rotate", "angle": 90, "center": [0, 0, 0]})
    lo, hi = bbox_of(ctx, box)
    check(near(lo, [-15, 95, -5]) and near(hi, [5, 115, 15]), "rotate 90° autour de l'origine : %s" % ((lo, hi),))
    ctx.call("rhino_transform_objects", {"ids": [box], "operation": "mirror", "plane": "zx", "center": [0, 0, 0]})
    lo, hi = bbox_of(ctx, box)
    check(hi[1] < -90, "mirror par le plan ZX : %s" % ((lo, hi),))

    ctx.call("rhino_modify_objects", {"ids": [box], "visible": False})
    check(ctx.call("rhino_get_object_details", {"ids": [box]})["objects"][0]["hidden"], "masquer")
    ctx.call("rhino_modify_objects", {"ids": [box], "visible": True, "locked": True})
    check(ctx.call("rhino_get_object_details", {"ids": [box]})["objects"][0]["locked"], "verrouiller")

    everything = [box] + copy["ids"] + arr["ids"] + polar["ids"]
    gone = ctx.call("rhino_delete_objects", {"ids": everything})
    check(len(gone["deleted"]) == len(everything) and not gone["failed"], "suppression (même verrouillé) : %s" % gone)
    ctx.call_error("rhino_get_object_details", {"ids": [box]}, contains="introuvable")
    ctx.call_error("rhino_transform_objects", {"ids": [box], "operation": "teleport"}, contains="introuvable")


def geometry(ctx, obj_id):
    return ctx.call("rhino_get_object_details", {"ids": [obj_id]})["objects"][0]["geometry"]


@test("rhino_create_geometry")
def rhino_creation(ctx):
    layer = "Test MCP::Création"
    shapes = [
        {"type": "point", "point": [1, 2, 3]},
        {"type": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
        {"type": "polyline", "points": [[0, 0, 0], [10, 0, 0], [10, 10, 0]], "closed": True},
        {"type": "curve", "points": [[0, 0, 0], [5, 5, 0], [10, 0, 0], [15, 5, 0]]},
        {"type": "circle", "center": [0, 0, 0], "radius": 5},
        {"type": "arc", "center": [0, 0, 0], "radius": 5, "start_angle": 0, "end_angle": 90},
        {"type": "arc", "points": [[0, 0, 0], [5, 5, 0], [10, 0, 0]]},
        {"type": "ellipse", "center": [0, 0, 0], "radius": 10, "radius2": 5},
        {"type": "rectangle", "corner": [0, 0, 0], "width": 20, "height": 10},
        {"type": "polygon", "center": [0, 0, 0], "radius": 10, "sides": 6},
        {"type": "plane_surface", "corner": [0, 0, 0], "width": 10, "height": 5},
        {"type": "sphere", "center": [0, 0, 0], "radius": 10},
        {"type": "box", "corner": [0, 0, 0], "width": 10, "depth": 10, "height": 10},
        {"type": "box", "corner": [5, 5, 5], "corner2": [15, 15, 15]},
        {"type": "cylinder", "center": [0, 0, 0], "radius": 2, "height": 10},
        {"type": "cone", "center": [0, 0, 0], "radius": 2, "height": 10},
        {"type": "torus", "center": [0, 0, 0], "radius": 10, "radius2": 2},
        {"type": "mesh", "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], "faces": [[0, 1, 2, 3]]},
    ]
    ids = {}
    for spec in shapes:
        r = ctx.call("rhino_create_geometry", dict(spec, layer=layer))
        check(r["count"] >= 1, "création %s : %s" % (spec["type"], r))
        ids.setdefault(spec["type"], r["ids"][0])
    check(abs(geometry(ctx, ids["circle"])["circle"]["radius"] - 5) < 1e-6, "rayon du cercle")
    check(abs(geometry(ctx, ids["rectangle"]).get("area", 0) - 200) < 1e-6, "aire du rectangle")
    check(abs(geometry(ctx, ids["sphere"])["volume"] - 4188.790205) < 1e-3, "volume de la sphère")
    check(abs(geometry(ctx, ids["cone"])["volume"] - 41.887902) < 1e-3, "volume du cône")
    ctx.call_error("rhino_create_geometry", {"type": "dodecaedre"}, contains="inconnu")
    ctx.call_error("rhino_create_geometry", {"type": "circle", "center": [0, 0, 0]}, contains="radius")
    everything = ctx.call("rhino_get_objects", {"layer": layer, "limit": 1000})["objects"]
    ctx.call("rhino_delete_objects", {"ids": [o["id"] for o in everything]})


@test("rhino_geometry_operation")
def rhino_operations(ctx):
    layer = "Test MCP::Opérations"
    new = lambda **spec: ctx.call("rhino_create_geometry", dict(spec, layer=layer))["ids"][0]  # noqa: E731
    op = lambda **args: ctx.call("rhino_geometry_operation", args)  # noqa: E731
    box = lambda c0, c1: new(type="box", corner=c0, corner2=c1)  # noqa: E731

    union = op(operation="boolean_union", ids=[box([0, 0, 0], [10, 10, 10]), box([5, 5, 5], [15, 15, 15])])
    check(union["count"] == 1 and abs(geometry(ctx, union["ids"][0])["volume"] - 1875) < 1e-6
          and len(union["deleted_input"]) == 2, "union : %s" % union)
    diff = op(operation="boolean_difference", ids=[box([0, 0, 0], [10, 10, 10])],
              other_ids=[box([5, 5, 5], [15, 15, 15])])
    check(abs(geometry(ctx, diff["ids"][0])["volume"] - 875) < 1e-6, "différence : %s" % diff)
    inter = op(operation="boolean_intersection", ids=[box([0, 0, 0], [10, 10, 10])],
               other_ids=[box([5, 5, 5], [15, 15, 15])])
    check(abs(geometry(ctx, inter["ids"][0])["volume"] - 125) < 1e-6, "intersection booléenne : %s" % inter)

    rect = new(type="rectangle", corner=[0, 0, 0], width=20, height=10)
    ext = op(operation="extrude", ids=[rect], height=5)
    check(abs(geometry(ctx, ext["ids"][0]).get("volume", 0) - 1000) < 1e-6, "extrusion fermée : %s" % ext)
    c1, c2 = new(type="circle", center=[0, 0, 0], radius=5), new(type="circle", center=[0, 0, 10], radius=3)
    check(op(operation="loft", ids=[c1, c2])["count"] == 1, "loft")
    line = new(type="line", start=[5, 0, 0], end=[5, 0, 10])
    check(op(operation="revolve", ids=[line], axis=[[0, 0, 0], [0, 0, 1]])["count"] == 1, "révolution")
    rail = new(type="line", start=[0, 0, 0], end=[0, 0, 20])
    profile = new(type="circle", center=[0, 0, 0], radius=2)
    check(op(operation="sweep1", ids=[profile], rail_id=rail)["count"] == 1, "balayage")
    pipe = op(operation="pipe", ids=[rail], radius=1)
    check(geometry(ctx, pipe["ids"][0]).get("solid"), "tuyau fermé : %s" % pipe)
    off = op(operation="offset", ids=[c1], distance=2)
    check(off["count"] >= 1, "décalage : %s" % off)
    a, b = new(type="line", start=[0, 0, 0], end=[10, 0, 0]), new(type="line", start=[10, 0, 0], end=[10, 10, 0])
    joined = op(operation="join", ids=[a, b])
    check(joined["count"] == 1 and abs(geometry(ctx, joined["ids"][0])["length"] - 20) < 1e-6, "join : %s" % joined)
    tri = new(type="polyline", points=[[0, 0, 0], [10, 0, 0], [10, 10, 0]], closed=True)
    check(op(operation="explode", ids=[tri])["count"] == 3, "explode d'un triangle")
    tube = new(type="cylinder", center=[50, 0, 0], radius=2, height=10, cap=False)
    check(geometry(ctx, op(operation="cap", ids=[tube])["ids"][0]).get("solid"), "cap")
    sphere = new(type="sphere", center=[0, 0, 50], radius=5)
    check(op(operation="mesh", ids=[sphere])["objects"][0]["type"] == "Mesh", "conversion en maillage")
    x1, x2 = new(type="line", start=[0, -5, 0], end=[0, 5, 0]), new(type="line", start=[-5, 0, 0], end=[5, 0, 0])
    cross = op(operation="intersect", ids=[x1], other_ids=[x2])
    check(cross["count"] == 1 and cross["objects"][0]["type"] == "Point", "intersection de courbes : %s" % cross)
    ctx.call_error("rhino_geometry_operation", {"operation": "boolean_union", "ids": [x1, x2]}, contains="surface")
    everything = ctx.call("rhino_get_objects", {"layer": layer, "limit": 1000})["objects"]
    ctx.call("rhino_delete_objects", {"ids": [o["id"] for o in everything]})


@test("rhino_execute_python", "rhino_get_objects")
def rhino_python_et_objets(ctx):
    code = (
        "import Rhino\n"
        "sid = doc.Objects.AddSphere(Rhino.Geometry.Sphere(Rhino.Geometry.Point3d(0, 0, 0), 5))\n"
        "print('sphere ok')\n"
        "result = str(sid)\n"
    )
    r = ctx.call("rhino_execute_python", {"code": code})
    check("sphere ok" in r.get("stdout", ""), "print() non renvoyé : %s" % r)
    sid = r["result"]
    objs = ctx.call("rhino_get_objects", {"limit": 1000})
    check(any(o["id"] == sid for o in objs["objects"]), "la sphère créée n'apparaît pas dans rhino_get_objects")
    ctx.call("rhino_execute_python", {"code": "doc.Objects.Delete(System.Guid('%s'), True)" % sid})
    err = ctx.call_error("rhino_execute_python", {"code": "1/0"})
    check("ZeroDivisionError" in err, "la trace Python n'est pas renvoyée : %s" % err[:300])


@test("rhino_capture_view")
def rhino_capture(ctx):
    result = ctx.call_raw("rhino_capture_view", {"width": 400, "height": 300})
    check(not result.get("isError"), "capture en erreur : %s" % result_text(result)[:500])
    images = [c for c in result["content"] if c.get("type") == "image"]
    check(images, "aucune image renvoyée")
    check(base64.b64decode(images[0]["data"])[:8] == PNG_SIGNATURE, "l'image n'est pas un PNG")


# --------------------------------------------------------------------------- #
# Grasshopper
# --------------------------------------------------------------------------- #
@test("gh_get_canvas", gh=True)
def gh_canevas(ctx):
    r = ctx.call("gh_get_canvas", timeout=300)  # 1er appel : Grasshopper se charge
    check("objects" in r, "gh_get_canvas ne décrit pas les objets : %s" % r)


@test("gh_search_components", gh=True)
def gh_recherche(ctx):
    hits = ctx.call("gh_search_components", {"query": "circle"})
    check(any(h["name"] == "Circle" for h in hits), "le composant Circle est introuvable")


@test("gh_add_component", "gh_set_value", "gh_connect", "gh_solve", "gh_get_output", "gh_delete", gh=True)
def gh_curseur_vers_cercle(ctx):
    slider = ctx.call("gh_add_component", {"name": "Number Slider", "x": 100, "y": 100})
    circle = ctx.call("gh_add_component", {"name": "Circle", "x": 350, "y": 100})
    ids = [slider["id"], circle["id"]]
    try:
        check("inputs" in circle, "« Circle » a donné un paramètre au lieu du composant Circle : %s" % circle)
        ctx.call("gh_set_value", {"id": slider["id"], "value": 5, "min": 0, "max": 10})
        ctx.call("gh_connect", {"source_id": slider["id"], "target_id": circle["id"], "target_input": "Radius"})
        solved = ctx.call("gh_solve")
        check(not [p for p in solved.get("problems", []) if p["id"] in ids], "erreurs Grasshopper : %s" % solved)
        out = ctx.call("gh_get_output", {"id": circle["id"]})
        check(out["total_items"] == 1, "1 cercle attendu, obtenu : %s" % out)
    finally:
        ctx.call("gh_delete", {"ids": ids})


# --------------------------------------------------------------------------- #
# Lancement
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Test de bout en bout du MCP Rhino & Grasshopper.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("RHINO_MCP_PORT", "1999")))
    parser.add_argument("--timeout", type=float, default=60,
                        help="délai max par commande dans Rhino (s) : un blocage devient un échec clair")
    parser.add_argument("--sans-gh", action="store_true", help="ne pas tester Grasshopper")
    parser.add_argument("-k", dest="filtre", help="ne lancer que les tests dont le nom contient ce texte")
    parser.add_argument("--abandonner-modifications", action="store_true",
                        help="autoriser le test à remplacer un document Rhino non enregistré")
    args = parser.parse_args()
    try:  # console : encodage natif ; tube (Git Bash, outils) : UTF-8 ; affichage ligne par ligne
        sys.stdout.reconfigure(errors="replace", line_buffering=True,
                               **({} if sys.stdout.isatty() else {"encoding": "utf-8"}))
    except AttributeError:
        pass

    client = McpClient(args.port, args.timeout)
    failures = 0
    try:
        init = client.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "test_connexion", "version": "1"},
        }, timeout=30)
        client.notify("notifications/initialized")
        tools = [t["name"] for t in client.request("tools/list", timeout=30)["tools"]]
        print("Serveur %s %s, protocole %s, %d outils." % (
            init["serverInfo"]["name"], init["serverInfo"]["version"], init["protocolVersion"], len(tools)))

        ping = client.request("tools/call", {"name": "rhino_ping", "arguments": {}}, timeout=30)
        if ping.get("isError"):
            print("Rhino injoignable :\n" + result_text(ping))
            return 2

        # Préparation : un document Rhino neuf (refusé si ton document a des modifications non enregistrées).
        prep = client.request("tools/call", {"name": "rhino_document", "arguments": {
            "action": "new", "discard_changes": args.abandonner_modifications}}, timeout=60)
        if prep.get("isError"):
            print("Préparation impossible : " + result_text(prep))
            print("Enregistre ton document Rhino (ou relance avec --abandonner-modifications), puis relance le test.")
            return 2

        ctx = Context(client, args)
        selected = [t for t in TESTS
                    if not (args.sans_gh and t["gh"]) and (not args.filtre or args.filtre in t["name"])]
        for t in selected:
            start = time.time()
            try:
                t["fn"](ctx)
                status, detail = "OK    ", ""
            except TestFailure as ex:
                status, detail, failures = "ÉCHEC ", str(ex), failures + 1
            except Exception as ex:  # erreur inattendue (protocole, délai...)
                status, detail, failures = "ERREUR", "%s: %s" % (type(ex).__name__, ex), failures + 1
            print("%s %-34s %6.2f s" % (status, t["name"], time.time() - start))
            if detail:
                print("       " + detail.replace("\n", "\n       "))

        if not args.filtre and not args.sans_gh:
            covered = set(tool for t in TESTS for tool in t["tools"])
            missing = [name for name in tools if name not in covered]
            if missing:
                failures += 1
                print("ÉCHEC  outils sans test : %s" % ", ".join(missing))
            unknown = sorted(covered - set(tools))
            if unknown:
                failures += 1
                print("ÉCHEC  outils testés mais absents du serveur : %s" % ", ".join(unknown))

        print("\n%s : %d test(s), %d en échec." % ("RÉUSSI" if not failures else "ÉCHEC", len(selected), failures))
        return 1 if failures else 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
