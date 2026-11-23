# -*- coding: utf-8 -*-
"""Outils Rhino : scripts Python et commandes Rhino (tout ce que les autres outils ne couvrent pas)."""
from .common import tool

TOOLS = [
    tool(
        "rhino_execute_python",
        (
            "Exécute du code Python 3 dans Rhino 8 (une seule étape d'annulation). Disponibles : Rhino (RhinoCommon), "
            "rs (rhinoscriptsyntax), sc (scriptcontext), System, doc (document actif), get_gh_doc() (document "
            "Grasshopper ; `import Grasshopper` pour l'API). Affecte la variable `result` pour renvoyer une valeur ; "
            "print() est aussi renvoyé. Outil polyvalent pour tout ce que les autres outils ne couvrent pas."
        ),
        {"code": {"type": "string", "description": "Code Python 3 à exécuter."}},
        required=["code"],
        destructive=True,
    ),
    tool(
        "rhino_run_command",
        (
            "Lance n'importe quelle commande Rhino comme si elle était tapée (macro), par ex. "
            "'_-Make2D _Enter', '_SelAll', '_Undo', '_-Export \"C:\\\\dossier\\\\plan.dwg\" _Enter'. "
            "Utilise la version « tiret » des commandes (_-Commande) et les noms anglais préfixés de « _ » : "
            "les versions à boîte de dialogue bloqueraient Rhino jusqu'à ce que l'utilisateur la ferme. Pour agir "
            "sur des objets précis, sélectionne-les d'abord (rhino_select_objects). Renvoie les objets créés, la "
            "sélection et ce que la commande a écrit dans la ligne de commande."
        ),
        {
            "command": {"type": "string", "description": "Macro Rhino (ex. '_-Sphere 0,0,0 10')."},
            "echo": {"type": "boolean", "default": False, "description": "Afficher la macro dans la ligne de commande."},
        },
        required=["command"],
        destructive=True,
    ),
]
