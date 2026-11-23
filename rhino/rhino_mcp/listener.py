# -*- coding: utf-8 -*-
"""
Écouteur TCP local (127.0.0.1 uniquement) du MCP, côté Rhino.

Tout s'exécute sur le fil principal de Rhino grâce à un minuteur Eto : pas de thread
Python en arrière-plan, donc pas de problème d'accès à RhinoCommon.

Protocole : une requête par connexion, une ligne JSON {"command", "params"} terminée
par « \\n » ; réponse {"ok": true, "result"} ou {"ok": false, "error", "traceback"}.
"""
import json
import os
import socket
import traceback

import clr

clr.AddReference("Eto")

import Eto.Forms  # noqa: E402
import Rhino  # noqa: E402
import scriptcontext as sc  # noqa: E402

from . import VERSION  # noqa: E402
from .registry import McpError, dispatch  # noqa: E402
from .util import jsonable  # noqa: E402

# Importer les modules de commandes suffit à les enregistrer.
from . import (  # noqa: E402,F401
    gh_components,
    gh_data,
    gh_document,
    rhino_document,
    rhino_geometry,
    rhino_objects,
    rhino_organisation,
    rhino_scripting,
    rhino_views,
)

HOST = "127.0.0.1"
PORT = int(os.environ.get("RHINO_MCP_PORT", "1999"))
STICKY_KEY = "rhino_mcp_listener"
RETRY_KEY = STICKY_KEY + "_retry"
ALIAS = "MCPStart"


def log(message):
    Rhino.RhinoApp.WriteLine("Rhino MCP : " + message)


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
        if self.busy:  # une commande en cours peut relancer la boucle d'événements
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
            log(traceback.format_exc())
        finally:
            self.busy = False

    def _serve(self, conn):
        shutdown = False
        try:
            conn.setblocking(True)
            conn.settimeout(10)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            if not buf.strip():
                return
            try:
                req = json.loads(buf.decode("utf-8"))
                if req.get("command") == "shutdown":
                    shutdown = True
                    resp = {"ok": True, "result": "arrêt"}
                else:
                    result = dispatch(req.get("command"), req.get("params") or {})
                    resp = {"ok": True, "result": jsonable(result)}
            except McpError as ex:
                resp = {"ok": False, "error": str(ex)}
            except Exception as ex:
                resp = {"ok": False, "error": "%s: %s" % (type(ex).__name__, ex),
                        "traceback": traceback.format_exc()}
            conn.sendall((json.dumps(resp, default=str) + "\n").encode("utf-8"))
        finally:
            conn.close()
        if shutdown:
            self.stop()
            log("ancien écouteur arrêté.")


# --------------------------------------------------------------------------- #
# Démarrage
# --------------------------------------------------------------------------- #
def _norm(path):
    return path.replace("/", "\\").lower()


def register_alias(script_path):
    """Crée (ou corrige) l'alias MCPStart vers ce script : aucun chemin à saisir à la main."""
    if not script_path:
        return
    try:
        aliases = Rhino.ApplicationSettings.CommandAliasList
        macro = '_-RunPythonScript "%s"' % script_path
        if aliases.IsAlias(ALIAS):
            if _norm(script_path) in _norm(aliases.GetMacro(ALIAS) or ""):
                return
            aliases.SetMacro(ALIAS, macro)
            log("alias %s mis à jour vers %s" % (ALIAS, script_path))
        else:
            aliases.Add(ALIAS, macro)
            log("alias %s créé : tape %s pour relancer l'écouteur." % (ALIAS, ALIAS))
    except Exception as ex:
        log("impossible de créer l'alias %s (%s)." % (ALIAS, ex))


def _start_listener(port):
    sc.sticky[STICKY_KEY] = Listener(port)
    log("prêt (v%s), en écoute sur %s:%d." % (VERSION, HOST, port))


def _retry_after_shutdown(port):
    """Port occupé (ancienne instance, p. ex. après une réinitialisation de Python) : on lui demande
    de s'arrêter, puis on réessaie depuis un minuteur pour la laisser répondre.
    Idée et code d'origine : branche Bulle-de-test (tanguygralltg-dotcom)."""
    try:
        s = socket.create_connection((HOST, port), timeout=2)
        s.sendall(b'{"command": "shutdown"}\n')
        s.close()
    except OSError:
        pass
    state = {"tries": 0}
    timer = Eto.Forms.UITimer()
    timer.Interval = 0.5

    def tick(sender, e):
        state["tries"] += 1
        try:
            _start_listener(port)
            timer.Stop()
        except OSError as ex:
            if state["tries"] >= 20:
                timer.Stop()
                log("le port %d reste occupé (%s). Redémarre Rhino puis relance %s." % (port, ex, ALIAS))

    timer.Elapsed += tick
    sc.sticky[RETRY_KEY] = timer
    timer.Start()
    log("port %d occupé, arrêt de l'ancienne instance en cours..." % port)


def start(script_path=None, port=PORT):
    register_alias(script_path)
    old = sc.sticky.pop(STICKY_KEY, None)
    if old is not None:
        try:
            old.stop()
        except Exception:
            pass
    old_retry = sc.sticky.pop(RETRY_KEY, None)
    if old_retry is not None:
        try:
            old_retry.Stop()
        except Exception:
            pass
    try:
        _start_listener(port)
    except OSError:
        _retry_after_shutdown(port)
