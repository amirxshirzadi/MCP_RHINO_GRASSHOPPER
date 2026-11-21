# -*- coding: utf-8 -*-
"""
Rhino MCP - serveur MCP (transport stdio) pour Claude Code.

Relaie chaque outil vers l'écouteur lancé dans Rhino (rhino/rhino_mcp_listener.py)
via une connexion TCP locale. Bibliothèque standard uniquement (Python 3.9+) :
il tourne avec le Python fourni par Rhino 8, sans rien installer.

Variables d'environnement : RHINO_MCP_HOST (127.0.0.1), RHINO_MCP_PORT (1999),
RHINO_MCP_TIMEOUT en secondes (120).
"""
import json
import os
import socket
import sys

HOST = os.environ.get("RHINO_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("RHINO_MCP_PORT", "1999"))
TIMEOUT = float(os.environ.get("RHINO_MCP_TIMEOUT", "120"))
DEFAULT_PROTOCOL = "2025-06-18"
SERVER_INFO = {"name": "rhino-grasshopper", "version": "0.1.0"}

ID_PROP = {"type": "string", "description": "Identifiant (InstanceGuid) de l'objet Grasshopper."}
PARAM_KEY = {"type": ["integer", "string"], "description": "Index (0, 1, ...) ou nom du paramètre."}

TOOLS = [
    {
        "name": "rhino_ping",
        "command": "ping",
        "description": "Vérifie que Rhino est joignable et renvoie la version de Rhino et le document ouvert.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "rhino_get_document_info",
        "command": "get_document_info",
        "description": "Infos sur le document Rhino actif : unités, tolérance, calques, nombre d'objets par type, vues.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "rhino_get_objects",
        "command": "get_objects",
        "description": "Liste les objets du document Rhino (id, type, nom, calque, boîte englobante), avec pagination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer": {"type": "string", "description": "Ne garder que ce calque (chemin complet)."},
                "selected_only": {"type": "boolean", "description": "Seulement les objets sélectionnés."},
                "limit": {"type": "integer", "default": 200},
                "offset": {"type": "integer", "default": 0},
            },
        },
    },
    {
        "name": "rhino_execute_python",
        "command": "execute_python",
        "description": (
            "Exécute du code Python 3 dans Rhino 8 (une seule étape d'annulation). Disponibles : Rhino (RhinoCommon), "
            "rs (rhinoscriptsyntax), sc (scriptcontext), System, doc (document actif), get_gh_doc() (document "
            "Grasshopper ; `import Grasshopper` pour l'API). Affecte la variable `result` pour renvoyer une valeur ; "
            "print() est aussi renvoyé. Outil polyvalent pour tout ce que les autres outils ne couvrent pas."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Code Python 3 à exécuter."}},
            "required": ["code"],
        },
    },
    {
        "name": "rhino_capture_view",
        "command": "capture_view",
        "description": "Capture une vue Rhino en image PNG (vue active par défaut) pour voir le résultat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "view": {"type": "string", "description": "Nom de la vue (Perspective, Top, ...)."},
                "width": {"type": "integer", "default": 900},
                "height": {"type": "integer", "default": 600},
            },
        },
    },
    {
        "name": "gh_get_canvas",
        "command": "gh_get_canvas",
        "description": (
            "Décrit le document Grasshopper ouvert (l'ouvre si besoin) : composants, entrées/sorties, connexions, "
            "valeurs des curseurs/panneaux/interrupteurs, erreurs et avertissements."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "gh_search_components",
        "command": "gh_search_components",
        "description": "Cherche des composants Grasshopper installés par nom, surnom, catégorie ou description.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texte à chercher (ex. 'circle', 'divide curve')."},
                "limit": {"type": "integer", "default": 30},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gh_add_component",
        "command": "gh_add_component",
        "description": (
            "Ajoute un composant sur le canevas Grasshopper, par nom exact (ex. 'Circle', 'Number Slider', 'Panel', "
            "'Boolean Toggle') ou par guid (voir gh_search_components). Renvoie son id et ses paramètres."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "guid": {"type": "string"},
                "x": {"type": "number", "default": 0},
                "y": {"type": "number", "default": 0},
                "nickname": {"type": "string"},
            },
        },
    },
    {
        "name": "gh_connect",
        "command": "gh_connect",
        "description": "Relie une sortie d'un objet Grasshopper à une entrée d'un autre (ou les déconnecte).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_id": ID_PROP,
                "source_output": PARAM_KEY,
                "target_id": ID_PROP,
                "target_input": PARAM_KEY,
                "disconnect": {"type": "boolean", "default": False},
            },
            "required": ["source_id", "target_id"],
        },
    },
    {
        "name": "gh_set_value",
        "command": "gh_set_value",
        "description": (
            "Règle la valeur d'un curseur (Number Slider : value, min, max, decimals), d'un panneau (texte) ou d'un "
            "interrupteur (Boolean Toggle : true/false)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": ID_PROP,
                "value": {"description": "Nouvelle valeur."},
                "min": {"type": "number"},
                "max": {"type": "number"},
                "decimals": {"type": "integer", "description": "0 = curseur entier."},
            },
            "required": ["id", "value"],
        },
    },
    {
        "name": "gh_get_output",
        "command": "gh_get_output",
        "description": "Lit les données calculées d'une sortie Grasshopper (arbre de données, sous forme de texte).",
        "inputSchema": {
            "type": "object",
            "properties": {"id": ID_PROP, "output": PARAM_KEY, "limit": {"type": "integer", "default": 200}},
            "required": ["id"],
        },
    },
    {
        "name": "gh_solve",
        "command": "gh_solve",
        "description": "Recalcule toute la définition Grasshopper et liste les composants en erreur ou en avertissement.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "gh_delete",
        "command": "gh_delete",
        "description": "Supprime des objets du canevas Grasshopper.",
        "inputSchema": {
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["ids"],
        },
    },
]
TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


def log(msg):
    sys.stderr.write("[rhino-mcp] %s\n" % msg)
    sys.stderr.flush()


def call_rhino(command, params):
    try:
        conn = socket.create_connection((HOST, PORT), timeout=5)
    except OSError:
        raise RuntimeError(
            "Rhino ne répond pas sur %s:%d. Ouvre Rhino 8 et lance l'écouteur : commande MCPStart "
            "(ou _-RunPythonScript sur rhino/rhino_mcp_listener.py)." % (HOST, PORT)
        )
    with conn:
        conn.settimeout(TIMEOUT)
        conn.sendall((json.dumps({"command": command, "params": params}) + "\n").encode("utf-8"))
        chunks = []
        while True:
            chunk = conn.recv(1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith(b"\n"):
                break
    return json.loads(b"".join(chunks).decode("utf-8"))


def text(s):
    return {"type": "text", "text": s}


def call_tool(name, args):
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return {"content": [text("Outil inconnu : %s" % name)], "isError": True}
    try:
        resp = call_rhino(tool["command"], args or {})
    except Exception as ex:
        return {"content": [text(str(ex))], "isError": True}
    if not resp.get("ok"):
        return {"content": [text("Erreur dans Rhino : %s\n\n%s" % (resp.get("error"), resp.get("traceback", "")))],
                "isError": True}
    result = resp.get("result")
    if name == "rhino_capture_view":
        return {"content": [
            {"type": "image", "data": result["image_base64"], "mimeType": "image/png"},
            text("Vue : %s" % result.get("view")),
        ]}
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
            "instructions": (
                "Pilote Rhino 8 et Grasshopper ouverts sur cet ordinateur. Commence par rhino_ping. "
                "Utilise rhino_capture_view pour vérifier visuellement un résultat."
            ),
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{k: v for k, v in t.items() if k != "command"} for t in TOOLS]}
    elif method == "tools/call":
        result = call_tool(params.get("name"), params.get("arguments"))
    else:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Méthode inconnue : %s" % method}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def send(obj):
    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def main():
    log("démarré, Rhino attendu sur %s:%d" % (HOST, PORT))
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
