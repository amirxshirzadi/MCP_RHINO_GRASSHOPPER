#! python3
# -*- coding: utf-8 -*-
"""
Rhino MCP - point d'entrée côté Rhino 8 (Python 3, compatible Rhino 8.12+).

Première fois, dans Rhino :
    _-RunPythonScript "C:\\chemin\\vers\\le\\dépôt\\rhino\\rhino_mcp_listener.py"
(ou glisser ce fichier dans la fenêtre de Rhino). Le script crée l'alias MCPStart :
ensuite, taper MCPStart suffit.

Le script écoute sur 127.0.0.1:1999 (connexions locales uniquement) et exécute
les commandes envoyées par le serveur MCP (server/rhino_mcp_server.py).
Relancer MCPStart recharge tout le code du paquet rhino_mcp/ et redémarre l'écouteur
(utile après une modification du code).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Le Python de Rhino garde les modules en mémoire d'un lancement à l'autre :
# on les oublie pour que MCPStart charge toujours la dernière version du code.
for _name in [m for m in sys.modules if m == "rhino_mcp" or m.startswith("rhino_mcp.")]:
    del sys.modules[_name]

import rhino_mcp.listener  # noqa: E402

rhino_mcp.listener.start(os.path.abspath(__file__))
