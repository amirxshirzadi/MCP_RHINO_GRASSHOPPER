# -*- coding: utf-8 -*-
"""Outils Rhino : document et fichiers."""
from .common import IDS, enum, tool

TOOLS = [
    tool(
        "rhino_ping",
        "Vérifie que Rhino est joignable et renvoie la version de Rhino, de l'écouteur et le document ouvert.",
        read_only=True,
    ),
    tool(
        "rhino_get_document_info",
        (
            "Infos sur le document Rhino actif : unités, tolérances, calques, nombre d'objets par type, vues, "
            "mises en page, vues nommées, matériaux, blocs, états de calques."
        ),
        read_only=True,
    ),
    tool(
        "rhino_document",
        (
            "Fichiers du document Rhino. action : new (document vide en mm, ou depuis un gabarit .3dm), "
            "open (ouvre un .3dm), save (enregistre), save_as (enregistre sous ; version = 7, 6... pour un "
            ".3dm plus ancien), import (importe dans le document actif : dwg, dxf, obj, stl, step, igs, fbx, "
            "skp, 3dm...), export (exporte tout le document, la sélection ou des objets précis ; le format suit "
            "l'extension du fichier). Par sécurité, new et open refusent si le document actif a des "
            "modifications non enregistrées, sauf avec discard_changes=true, et save_as/export refusent "
            "d'écraser un fichier existant, sauf avec overwrite=true (à confirmer avec l'utilisateur)."
        ),
        {
            "action": enum(["new", "open", "save", "save_as", "import", "export"], "Opération à effectuer."),
            "path": {"type": "string", "description": "Chemin du fichier (open, save_as, import, export)."},
            "template": {"type": "string", "description": "new : gabarit .3dm à utiliser."},
            "discard_changes": {
                "type": "boolean", "default": False,
                "description": "new/open : abandonner les modifications non enregistrées du document actif.",
            },
            "ids": dict(IDS, description="export : n'exporter que ces objets."),
            "selected_only": {"type": "boolean", "default": False, "description": "export : seulement la sélection."},
            "version": {"type": "integer", "description": "save/save_as : version du format .3dm (8, 7, 6...)."},
            "overwrite": {
                "type": "boolean", "default": False,
                "description": "save_as/export : remplacer le fichier s'il existe déjà.",
            },
        },
        required=["action"],
        destructive=True,
    ),
    tool(
        "rhino_undo",
        "Annule (undo) ou rétablit (redo) les dernières opérations dans Rhino.",
        {
            "action": enum(["undo", "redo"], "undo pour annuler, redo pour rétablir.", default="undo"),
            "steps": {"type": "integer", "default": 1, "description": "Nombre d'étapes."},
        },
    ),
    tool(
        "rhino_list_plugins",
        (
            "Liste les plug-ins Rhino installés (chargés ou non) et, avec include_commands, les noms des "
            "commandes Rhino disponibles (utile pour rhino_run_command)."
        ),
        {
            "query": {"type": "string", "description": "Filtre sur le nom (plug-ins et commandes)."},
            "loaded_only": {"type": "boolean", "default": False},
            "include_commands": {"type": "boolean", "default": False},
        },
        read_only=True,
    ),
]
