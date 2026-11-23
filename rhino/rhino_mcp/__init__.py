# -*- coding: utf-8 -*-
"""
Code du MCP exécuté dans Rhino 8 (Python 3) : l'écouteur TCP et une commande par outil MCP.

    listener.py          écouteur 127.0.0.1 piloté par un minuteur du fil principal + alias MCPStart
    registry.py          registre des commandes (@command) et erreurs « attendues » (McpError)
    util.py              document actif, conversions JSON <-> RhinoCommon, attributs, annulation
    rhino_*.py           commandes Rhino, par domaine (mêmes domaines que server/tools/)
    gh_*.py              commandes Grasshopper
"""
VERSION = "0.2.0"
