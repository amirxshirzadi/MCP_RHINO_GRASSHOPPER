# MCP Rhino & Grasshopper

Serveur MCP (Model Context Protocol) gratuit qui donne à Claude Code un **accès complet à Rhino 8** (dès la 8.12)
**et à Grasshopper** ouverts sur l'ordinateur : 36 outils pour les fichiers, objets, géométrie, calques, matériaux,
blocs, vues, annotations, mises en page/PDF, commandes et Python dans Rhino ; définitions, composants, fils,
valeurs et cuisson dans Grasshopper. Aucune installation de Python, Node ou plugin compilé : tout repose sur le
Python 3 fourni avec Rhino 8.

## Fonctionnement

```
Claude Code ──stdio──> server/rhino_mcp_server.py ──TCP 127.0.0.1:1999──> rhino/rhino_mcp_listener.py (dans Rhino)
```

| Dossier | Rôle |
|---|---|
| [server/](server/) | Serveur MCP lancé **par Claude Code** ([.mcp.json](.mcp.json), avec le Python de Rhino). `rhino_mcp_server.py` gère le protocole ; [server/tools/](server/tools/) déclare les outils, un fichier par domaine. |
| [rhino/](rhino/) | Ce qui tourne **dans Rhino**. `rhino_mcp_listener.py` (commande `MCPStart`) charge le paquet [rhino_mcp/](rhino/rhino_mcp/) : écouteur (connexions locales uniquement), registre des commandes, un fichier par domaine (les mêmes que `server/tools/`). |
| [scripts/](scripts/) | `test_connexion.py` (test de bout en bout), `generer_doc_outils.py` (régénère la doc des outils). |
| [docs/OUTILS.md](docs/OUTILS.md) | Référence complète des 36 outils et de leurs paramètres. |
| [MODEL/](MODEL/) | Modèles Rhino et Grasshopper d'exemple. |

## Installation (une seule fois)

1. **Lancer l'écouteur dans Rhino 8** : glisser [rhino/rhino_mcp_listener.py](rhino/rhino_mcp_listener.py) dans la
   fenêtre de Rhino, ou taper :
   `_-RunPythonScript "<dossier du dépôt>\rhino\rhino_mcp_listener.py"`.
   La première fois, Rhino installe son Python 3 (environ une minute). La ligne de commande affiche
   `Rhino MCP : alias MCPStart créé` puis `Rhino MCP : prêt (v0.2.0), en écoute sur 127.0.0.1:1999.`
   Ensuite, taper **`MCPStart`** suffit : l'alias suit le dossier du dépôt, rien à saisir à la main.
2. **Démarrage automatique** : `Outils → Options → Général → Exécuter ces commandes à chaque ouverture de Rhino`,
   ajouter `MCPStart`.
3. **Claude Code** (VS Code) : ouvrir le dossier du dépôt, recharger la fenêtre (`Ctrl+Maj+P` → « Reload Window »)
   et accepter le serveur MCP **rhino**. La commande `/mcp` doit afficher `rhino · connected`.

## Outils (36)

Détail des paramètres : [docs/OUTILS.md](docs/OUTILS.md).

| Domaine | Outils |
|---|---|
| Document et fichiers | `rhino_ping`, `rhino_get_document_info`, `rhino_document` (nouveau, ouvrir, enregistrer, enregistrer sous, importer, exporter : 3dm, dwg, dxf, obj, stl, step, iges, fbx, 3mf, glTF, skp, ply, sat, usd, 3ds), `rhino_undo`, `rhino_list_plugins` |
| Objets | `rhino_get_objects`, `rhino_get_object_details`, `rhino_select_objects`, `rhino_modify_objects`, `rhino_transform_objects` (déplacer, copier, tourner, échelle, miroir, réseaux), `rhino_delete_objects` |
| Géométrie | `rhino_create_geometry` (points, lignes, courbes, cercles, arcs, rectangles, polygones, surfaces, sphère, boîte, cylindre, cône, tore, maillage), `rhino_geometry_operation` (booléens, extrusion, loft, révolution, balayage, tuyau, décalage, joindre, éclater, boucher, maillage, intersection) |
| Calques, matériaux, blocs | `rhino_layer` (+ états de calques), `rhino_material` (PBR), `rhino_block` |
| Vues et sorties | `rhino_view`, `rhino_capture_view`, `rhino_annotation` (texte, cotes, repères, hachures), `rhino_layout` (mises en page, PDF) |
| Tout le reste | `rhino_run_command` (n'importe quelle commande Rhino), `rhino_execute_python` (RhinoCommon et API Grasshopper complets) |
| Grasshopper | `gh_document`, `gh_get_canvas`, `gh_capture_canvas`, `gh_search_components`, `gh_add_component`, `gh_connect`, `gh_modify_objects`, `gh_delete`, `gh_group`, `gh_set_value`, `gh_reference_rhino_geometry`, `gh_get_output`, `gh_solve`, `gh_bake` |

Exemples de demandes à Claude : « crée une boîte de 10 x 20 x 5 sur un calque Murs en béton », « exporte la
sélection en DWG », « dans Grasshopper, une tour dont le nombre d'étages est piloté par un curseur, puis cuis-la
sur le calque Tour », « mets la vue perspective en mode Arctic et fais-en une planche A3 en PDF ».

## Sécurité et garde-fous

- L'écouteur n'accepte que les connexions locales (127.0.0.1) ; il exécute ce qu'on lui envoie, y compris du Python :
  n'ouvre pas ce port à d'autres machines.
- Chaque modification est **une étape d'annulation** : `Ctrl+Z` dans Rhino (ou `rhino_undo`) revient en arrière.
- Rien n'est perdu en silence : ouvrir/créer un document refuse s'il y a des modifications non enregistrées
  (sauf `discard_changes`), et `save_as`/`export` refusent d'écraser un fichier (sauf `overwrite`).
- Rien ne bloque Rhino : imports/exports sans aucune question, commandes en version « tiret ».

## Dépannage

| Message ou symptôme | Solution |
|---|---|
| `Rhino ne répond pas sur 127.0.0.1:1999` | Rhino fermé ou écouteur arrêté : taper `MCPStart` dans Rhino. |
| `Rhino n'a pas répondu en 120 s` | Une commande attend une réponse dans Rhino : appuyer sur **Échap** dans Rhino. |
| `port 1999 occupé` dans Rhino | Ancienne instance (après une réinitialisation de Python) : `MCPStart` la remplace automatiquement. |
| Plusieurs Rhino ouverts | Claude pilote le dernier Rhino où `MCPStart` a été lancé. |
| Grasshopper ne calcule rien | Éditeur Grasshopper fermé : les outils `gh_*` le rouvrent et réactivent la définition. |
| Code modifié | `MCPStart` recharge le code côté Rhino ; dans Claude Code, `/mcp` → reconnecter le serveur. |

Vérifier toute la chaîne (ouvre un document vide ; enregistre ton travail avant) :

```
& "$env:USERPROFILE\.rhinocode\py39-rh8\python.exe" scripts\test_connexion.py
```

## Travailler à plusieurs

- Dépôt d'origine : [tanguygralltg-dotcom/MCP_RHINO_GRASSHOPPER](https://github.com/tanguygralltg-dotcom/MCP_RHINO_GRASSHOPPER).
  Chacun peut travailler dans son **fork** (`origin` = le fork, `upstream` = le dépôt d'origine).
- Récupérer les nouveautés du dépôt d'origine : `git fetch upstream` puis `git merge upstream/main`.
- Proposer ses changements : une **Pull Request** du fork vers `main` du dépôt d'origine.
- Dans VS Code, chaque commit est envoyé automatiquement (réglages dans [.vscode/settings.json](.vscode/settings.json)).

## Ajouter un outil

1. Déclarer l'outil dans `server/tools/<domaine>.py` (fonction `tool(...)` : nom, description, paramètres).
2. Écrire la commande du même nom dans `rhino/rhino_mcp/<domaine>.py`, décorée par `@command("nom_de_l_outil")`.
   Règle : rien ne doit poser de question dans Rhino (API sans dialogue ou commande « tiret » complète).
3. Taper `MCPStart` dans Rhino (recharge le code) et reconnecter le serveur dans Claude Code (`/mcp`).
4. `python scripts/generer_doc_outils.py` pour mettre à jour [docs/OUTILS.md](docs/OUTILS.md).
