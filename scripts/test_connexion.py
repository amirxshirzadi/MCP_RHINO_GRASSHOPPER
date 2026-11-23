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

    def call_raw(self, tool, arguments=None, timeout=180):
        return self.client.request("tools/call", {"name": tool, "arguments": arguments or {}}, timeout)

    def call(self, tool, arguments=None, timeout=180):
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
    parser.add_argument("--timeout", type=float, default=180, help="délai max par commande (s)")
    parser.add_argument("--sans-gh", action="store_true", help="ne pas tester Grasshopper")
    parser.add_argument("-k", dest="filtre", help="ne lancer que les tests dont le nom contient ce texte")
    args = parser.parse_args()
    try:  # console : encodage natif ; tube (Git Bash, outils) : UTF-8
        sys.stdout.reconfigure(errors="replace", **({} if sys.stdout.isatty() else {"encoding": "utf-8"}))
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
