# -*- coding: utf-8 -*-
"""
Rhino MCP - serveur MCP (transport stdio) pour Claude Code.

Relaie chaque outil vers l'écouteur lancé dans Rhino (rhino/rhino_mcp_listener.py)
via une connexion TCP locale. Bibliothèque standard uniquement (Python 3.9+) :
il tourne avec le Python fourni par Rhino 8, sans rien installer.

Ce fichier ne gère que le protocole MCP ; les outils sont déclarés dans server/tools/
(un fichier par domaine) et implémentés côté Rhino dans rhino/rhino_mcp/.

Variables d'environnement : RHINO_MCP_HOST (127.0.0.1), RHINO_MCP_PORT (1999),
RHINO_MCP_TIMEOUT en secondes (120).
"""
import json
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import TOOLS, TOOLS_BY_NAME  # noqa: E402

HOST = os.environ.get("RHINO_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("RHINO_MCP_PORT", "1999"))
TIMEOUT = float(os.environ.get("RHINO_MCP_TIMEOUT", "120"))
DEFAULT_PROTOCOL = "2025-06-18"
SERVER_INFO = {"name": "rhino-grasshopper", "version": "0.2.0"}
INSTRUCTIONS = (
    "Pilote Rhino 8 et Grasshopper ouverts sur cet ordinateur (accès complet). Commence par rhino_ping.\n"
    "- Préfère les outils dédiés : rhino_document (fichiers), rhino_get_objects / rhino_get_object_details, "
    "rhino_create_geometry et rhino_geometry_operation (géométrie), rhino_transform_objects, rhino_modify_objects, "
    "rhino_layer / rhino_material / rhino_block, rhino_view / rhino_annotation / rhino_layout (PDF). Grasshopper : "
    "gh_add_component, gh_connect, gh_set_value, gh_solve, gh_get_output, gh_bake ; gh_get_canvas pour comprendre "
    "une définition existante.\n"
    "- Vérifie visuellement avec rhino_capture_view et gh_capture_canvas.\n"
    "- Pour tout le reste : rhino_run_command (commande Rhino en version « tiret », macro complète) ou "
    "rhino_execute_python (RhinoCommon et API Grasshopper complets).\n"
    "- Chaque modification est une étape d'annulation (rhino_undo). Ne remplace jamais un document non enregistré "
    "(discard_changes) ni un fichier existant (overwrite) sans l'accord explicite de l'utilisateur."
)


class RhinoError(Exception):
    """Rhino injoignable ou réponse inexploitable : message destiné à l'utilisateur."""


def log(msg):
    sys.stderr.write("[rhino-mcp] %s\n" % msg)
    sys.stderr.flush()


def call_rhino(command, params):
    """Envoie une commande à l'écouteur de Rhino et renvoie sa réponse JSON."""
    try:
        conn = socket.create_connection((HOST, PORT), timeout=5)
    except OSError:
        raise RhinoError(
            "Rhino ne répond pas sur %s:%d. Ouvre Rhino 8 et lance l'écouteur : commande MCPStart "
            "(ou _-RunPythonScript sur rhino/rhino_mcp_listener.py)." % (HOST, PORT)
        )
    chunks = []
    with conn:
        conn.settimeout(TIMEOUT)
        try:
            conn.sendall((json.dumps({"command": command, "params": params}) + "\n").encode("utf-8"))
            while True:
                chunk = conn.recv(1 << 20)
                if not chunk:
                    break
                chunks.append(chunk)
                if chunk.endswith(b"\n"):
                    break
        except socket.timeout:
            raise RhinoError(
                "Rhino n'a pas répondu en %d s (commande « %s »). Une boîte de dialogue attend peut-être "
                "une réponse dans Rhino, ou l'opération est très longue (augmente RHINO_MCP_TIMEOUT)."
                % (TIMEOUT, command)
            )
        except OSError as ex:
            raise RhinoError("Connexion à Rhino interrompue pendant « %s » : %s" % (command, ex))
    data = b"".join(chunks)
    if not data.strip():
        raise RhinoError(
            "Rhino a fermé la connexion sans répondre (commande « %s »). L'écouteur vient peut-être "
            "d'être relancé : réessaie." % command
        )
    try:
        return json.loads(data.decode("utf-8"))
    except ValueError:
        raise RhinoError("Réponse illisible de Rhino pour « %s »." % command)


def text(s):
    return {"type": "text", "text": s}


def error_result(message):
    return {"content": [text(message)], "isError": True}


def call_tool(name, args):
    if name not in TOOLS_BY_NAME:
        return error_result("Outil inconnu : %s" % name)
    try:
        resp = call_rhino(name, args or {})
    except RhinoError as ex:
        return error_result(str(ex))
    if not resp.get("ok"):
        message = "Erreur dans Rhino : %s" % resp.get("error")
        if resp.get("traceback"):
            message += "\n\n" + resp["traceback"]
        return error_result(message)
    result = resp.get("result")
    if isinstance(result, dict) and result.get("image_base64"):
        # Capture d'écran : l'image elle-même, puis les autres informations en texte.
        image = {"type": "image", "data": result["image_base64"], "mimeType": "image/png"}
        rest = {k: v for k, v in result.items() if k != "image_base64"}
        return {"content": [image, text(json.dumps(rest, ensure_ascii=False))]}
    is_error = isinstance(result, dict) and bool(result.get("error"))
    return {"content": [text(json.dumps(result, ensure_ascii=False, indent=1))], "isError": is_error}


def handle(msg):
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    if msg_id is None:  # notification : pas de réponse
        return None
    if method == "initialize":
        result = {
            "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(params.get("name"), params.get("arguments"))
    else:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Méthode inconnue : %s" % method}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def send(obj):
    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def main():
    log("démarré (%d outils), Rhino attendu sur %s:%d" % (len(TOOLS), HOST, PORT))
    for raw in sys.stdin.buffer:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode("utf-8"))
        except ValueError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalide"}})
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            try:
                resp = handle(m)
            except Exception as ex:
                resp = {"jsonrpc": "2.0", "id": m.get("id"), "error": {"code": -32603, "message": str(ex)}}
            if resp is not None:
                send(resp)


if __name__ == "__main__":
    main()
