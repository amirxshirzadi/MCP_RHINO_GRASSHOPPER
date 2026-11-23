# -*- coding: utf-8 -*-
"""Registre des commandes : chaque outil MCP correspond à une fonction décorée par @command."""
import inspect

COMMANDS = {}


class McpError(Exception):
    """Erreur attendue (paramètre invalide, objet introuvable...) : renvoyée sans trace Python."""


def command(*names):
    """Enregistre la fonction sous un ou plusieurs noms (nom de l'outil MCP, puis anciens noms éventuels)."""
    def register(fn):
        for name in names:
            if name in COMMANDS:
                raise RuntimeError("Commande en double : %s" % name)
            COMMANDS[name] = fn
        return fn
    return register


def dispatch(name, params):
    fn = COMMANDS.get(name)
    if fn is None:
        raise McpError("Commande inconnue : %s. L'écouteur est peut-être plus ancien que le serveur : "
                       "relance MCPStart dans Rhino." % name)
    if not isinstance(params, dict):
        raise McpError("Les paramètres doivent être un objet JSON.")
    params = {k: v for k, v in params.items() if v is not None}
    try:
        inspect.signature(fn).bind(**params)
    except TypeError as ex:
        raise McpError("Paramètres invalides pour %s : %s" % (name, ex))
    return fn(**params)


@command("list_commands")
def list_commands():
    """Noms de toutes les commandes connues (sert au test de cohérence serveur/écouteur)."""
    return sorted(COMMANDS)
