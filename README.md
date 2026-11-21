# MCP Rhino & Grasshopper

Serveur MCP (Model Context Protocol) gratuit qui permet à Claude Code de piloter **Rhino 8** (dès la 8.12)
et **Grasshopper** ouverts sur l'ordinateur. Aucune installation de Python, Node ou plugin compilé :
tout repose sur le Python 3 fourni avec Rhino 8.

## Fonctionnement

```
Claude Code ──stdio──> server/rhino_mcp_server.py ──TCP 127.0.0.1:1999──> rhino/rhino_mcp_listener.py (dans Rhino)
```

- [rhino/rhino_mcp_listener.py](rhino/rhino_mcp_listener.py) : script lancé **dans Rhino**, qui écoute les commandes
  (connexions locales uniquement) et les exécute avec RhinoCommon et l'API Grasshopper.
- [server/rhino_mcp_server.py](server/rhino_mcp_server.py) : serveur MCP lancé **par Claude Code**
  (configuré dans [.mcp.json](.mcp.json)), qui relaie les outils vers Rhino.

## Outils disponibles

| Rhino | Grasshopper |
|---|---|
| `rhino_ping`, `rhino_get_document_info`, `rhino_get_objects`, `rhino_capture_view`, `rhino_execute_python` (code Python libre, accès complet à RhinoCommon et Grasshopper) | `gh_get_canvas`, `gh_search_components`, `gh_add_component`, `gh_connect`, `gh_set_value`, `gh_get_output`, `gh_solve`, `gh_delete` |

## Installation (une seule fois)

1. **Créer la commande `MCPStart` dans Rhino** : `Outils → Options → Alias`, clic sur **Nouveau** :
   - Alias : `MCPStart`
   - Macro de commande : `_-RunPythonScript "C:\Users\tangu\Documents\Github\MCP_RHINO GRASSHOPPER\rhino\rhino_mcp_listener.py"`
2. Dans Rhino, tape `MCPStart`. La première fois, Rhino installe son Python 3 (cela peut prendre une minute).
   La ligne de commande affiche : `Rhino MCP : prêt, en écoute sur 127.0.0.1:1999.`
3. Dans VS Code, recharge la fenêtre (`Ctrl+Maj+P` → « Reload Window ») et accepte le serveur MCP **rhino**
   quand Claude Code le propose.

Pour démarrer automatiquement à chaque ouverture de Rhino : `Outils → Options → Général →
Exécuter ces commandes à chaque ouverture de Rhino`, ajouter `MCPStart`.

## Utilisation

Rhino ouvert et `MCPStart` lancé, il suffit de demander à Claude, par exemple :
« crée une sphère de rayon 10 à l'origine » ou « dans Grasshopper, crée un cercle piloté par un curseur ».

## Valider et publier une modification

Rien n'est envoyé sur GitHub sans validation. Après avoir relu une modification, dans VS Code :

1. Ouvre l'onglet **Contrôle de code source** (Ctrl+Maj+G).
2. Écris le message du commit.
3. Clique sur **Commit**.

Toutes les modifications en cours sont enregistrées (commit) puis envoyées (push) automatiquement sur GitHub
(réglages dans [.vscode/settings.json](.vscode/settings.json)).
