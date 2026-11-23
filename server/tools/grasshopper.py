# -*- coding: utf-8 -*-
"""Outils Grasshopper : définition, composants, fils, données, calcul et cuisson vers Rhino."""
from .common import COLOR, GH_ID, GH_IDS, IDS, LAYER, NAME, PARAM_KEY, enum, tool

TOOLS = [
    # ----------------------------------------------------------------- définition
    tool(
        "gh_document",
        (
            "Définitions Grasshopper. action : list (définitions ouvertes, active, solveur), new, open (path .gh/.ghx ; "
            "réactive si déjà ouverte), save, save_as (path ; overwrite), close (refuse si non enregistrée, sauf "
            "discard_changes=true), activate (name ou path), enable_solver / disable_solver (calcul automatique)."
        ),
        {
            "action": enum(["list", "new", "open", "save", "save_as", "close", "activate", "enable_solver",
                            "disable_solver"], "Opération.", default="list"),
            "path": {"type": "string"},
            "name": {"type": "string", "description": "activate : nom affiché de la définition."},
            "discard_changes": {"type": "boolean", "default": False},
            "overwrite": {"type": "boolean", "default": False},
        },
    ),
    tool(
        "gh_get_canvas",
        (
            "Décrit la définition Grasshopper active (ouvre Grasshopper si besoin) : composants, entrées/sorties, "
            "connexions, valeurs (curseurs, panneaux, interrupteurs, listes, couleurs), groupes, notes, activé/aperçu, "
            "erreurs et avertissements. ids : ne décrire que ces objets."
        ),
        {"ids": GH_IDS},
        read_only=True,
    ),
    tool(
        "gh_capture_canvas",
        "Image PNG du canevas Grasshopper (cadré sur toute la définition), sans déplacer la vue de l'utilisateur.",
        {
            "width": {"type": "integer", "default": 1200},
            "height": {"type": "integer", "default": 800},
            "zoom_to_fit": {"type": "boolean", "default": True},
        },
        read_only=True,
    ),
    # ----------------------------------------------------------------- composants
    tool(
        "gh_search_components",
        (
            "Cherche les composants Grasshopper installés (plug-ins compris) par nom, surnom, catégorie ou "
            "description ; renvoie nom, catégorie, kind (component/parameter), bibliothèque et guid."
        ),
        {
            "query": {"type": "string", "description": "Texte à chercher (ex. 'circle', 'divide curve')."},
            "category": {"type": "string", "description": "Ne garder qu'une catégorie (ex. 'Curve', 'Maths')."},
            "limit": {"type": "integer", "default": 30},
        },
        read_only=True,
    ),
    tool(
        "gh_add_component",
        (
            "Ajoute un objet sur le canevas : par nom exact (ex. 'Circle', 'Number Slider', 'Panel', 'Boolean "
            "Toggle', 'Value List', 'Colour Swatch' ; si un nom désigne aussi un paramètre, le composant est choisi) "
            "ou par guid (gh_search_components). Placé automatiquement à droite si x/y sont omis. value/min/max/"
            "decimals règlent tout de suite un curseur, un panneau, etc. Renvoie son id et ses paramètres."
        ),
        {
            "name": {"type": "string"},
            "guid": {"type": "string"},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "nickname": {"type": "string"},
            "value": {"description": "Valeur initiale (curseur, panneau, interrupteur...)."},
            "min": {"type": "number"},
            "max": {"type": "number"},
            "decimals": {"type": "integer"},
        },
    ),
    tool(
        "gh_connect",
        (
            "Relie une sortie d'un objet Grasshopper à une entrée d'un autre (replace=true remplace les fils "
            "existants de cette entrée), ou les déconnecte (disconnect=true)."
        ),
        {
            "source_id": GH_ID,
            "source_output": PARAM_KEY,
            "target_id": GH_ID,
            "target_input": PARAM_KEY,
            "disconnect": {"type": "boolean", "default": False},
            "replace": {"type": "boolean", "default": False},
        },
        required=["source_id", "target_id"],
    ),
    tool(
        "gh_modify_objects",
        (
            "Modifie des objets Grasshopper : nickname, position (x, y), enabled (activer/désactiver), preview "
            "(aperçu dans Rhino), params = liste de {param (nom ou index), side 'input'/'output', mapping "
            "'none'/'flatten'/'graft', reverse, simplify}."
        ),
        {
            "ids": GH_IDS,
            "nickname": {"type": "string"},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "enabled": {"type": "boolean"},
            "preview": {"type": "boolean"},
            "params": {"type": "array", "items": {"type": "object"}},
        },
        required=["ids"],
    ),
    tool(
        "gh_delete",
        "Supprime des objets du canevas Grasshopper.",
        {"ids": GH_IDS},
        required=["ids"],
        destructive=True,
    ),
    tool(
        "gh_group",
        (
            "Organisation du canevas. action : group (ids, name, color) ; ungroup (group_id) ; note (texte libre "
            "sur le canevas : text, x, y, size)."
        ),
        {
            "action": enum(["group", "ungroup", "note"], "Opération.", default="group"),
            "ids": GH_IDS,
            "name": {"type": "string"},
            "color": COLOR,
            "text": {"type": "string"},
            "x": {"type": "number"},
            "y": {"type": "number"},
            "size": {"type": "number", "description": "Taille du texte de la note."},
            "group_id": GH_ID,
        },
    ),
    # ----------------------------------------------------------------- données
    tool(
        "gh_set_value",
        (
            "Règle une valeur Grasshopper : curseur (Number Slider : value, min, max, decimals ; 0 = entier), "
            "panneau (texte), interrupteur (true/false), liste de valeurs (nom ou index de l'élément), nuancier "
            "(couleur), paramètre isolé (Number, Point [x,y,z], Text...), ou entrée d'un composant (input = nom/index "
            "de l'entrée ; valeur ou liste de valeurs, l'entrée ne doit pas être reliée)."
        ),
        {
            "id": GH_ID,
            "value": {"description": "Nouvelle valeur (ou liste de valeurs)."},
            "input": PARAM_KEY,
            "min": {"type": "number"},
            "max": {"type": "number"},
            "decimals": {"type": "integer", "description": "0 = curseur entier."},
        },
        required=["id", "value"],
    ),
    tool(
        "gh_reference_rhino_geometry",
        (
            "Envoie des objets Rhino (rhino_ids) dans un paramètre Grasshopper (Curve, Brep, Point, Geometry...) ou "
            "dans l'entrée input d'un composant, comme « Set one/multiple ... » : ils restent liés au modèle Rhino."
        ),
        {"id": GH_ID, "rhino_ids": IDS, "input": PARAM_KEY},
        required=["id", "rhino_ids"],
    ),
    tool(
        "gh_get_output",
        (
            "Lit les données d'une sortie (ou, avec side='input', d'une entrée) Grasshopper : arbre de données avec "
            "nombres, textes, points, et résumés de géométrie (type, boîte, longueur...)."
        ),
        {
            "id": GH_ID,
            "output": PARAM_KEY,
            "side": enum(["output", "input"], "Côté du composant.", default="output"),
            "limit": {"type": "integer", "default": 200},
        },
        required=["id"],
        read_only=True,
    ),
    tool(
        "gh_solve",
        "Recalcule toute la définition Grasshopper et liste les composants en erreur ou en avertissement.",
    ),
    tool(
        "gh_bake",
        (
            "Cuit (bake) la géométrie d'un composant ou paramètre Grasshopper dans Rhino : toutes ses sorties, ou "
            "seulement output ; sur le calque layer (créé si besoin), avec name et color. Une étape d'annulation ; "
            "renvoie les ids Rhino."
        ),
        {"id": GH_ID, "output": PARAM_KEY, "layer": LAYER, "name": NAME, "color": COLOR},
        required=["id"],
    ),
]
