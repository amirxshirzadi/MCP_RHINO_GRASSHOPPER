# Outils du MCP Rhino & Grasshopper

Généré par `scripts/generer_doc_outils.py` à partir de `server/tools/` : ne pas modifier à la main.

**36 outils** :

- Rhino : document et fichiers : `rhino_ping`, `rhino_get_document_info`, `rhino_document`, `rhino_undo`, `rhino_list_plugins`
- Rhino : objets : `rhino_get_objects`, `rhino_get_object_details`, `rhino_select_objects`, `rhino_modify_objects`, `rhino_transform_objects`, `rhino_delete_objects`
- Rhino : géométrie : `rhino_create_geometry`, `rhino_geometry_operation`
- Rhino : calques, matériaux, blocs : `rhino_layer`, `rhino_material`, `rhino_block`
- Rhino : vues, annotations, mises en page : `rhino_capture_view`, `rhino_view`, `rhino_annotation`, `rhino_layout`
- Rhino : scripts et commandes : `rhino_execute_python`, `rhino_run_command`
- Grasshopper : `gh_document`, `gh_get_canvas`, `gh_capture_canvas`, `gh_search_components`, `gh_add_component`, `gh_connect`, `gh_modify_objects`, `gh_delete`, `gh_group`, `gh_set_value`, `gh_reference_rhino_geometry`, `gh_get_output`, `gh_solve`, `gh_bake`

## Rhino : document et fichiers

### `rhino_ping`

Vérifie que Rhino est joignable et renvoie la version de Rhino, de l'écouteur et le document ouvert.

### `rhino_get_document_info`

Infos sur le document Rhino actif : unités, tolérances, calques, nombre d'objets par type, vues, mises en page, vues nommées, matériaux, blocs, états de calques.

### `rhino_document`

Fichiers du document Rhino. action : new (document vide en mm, ou depuis un gabarit .3dm), open (ouvre un .3dm), save (enregistre), save_as (enregistre sous ; version = 7, 6... pour un .3dm plus ancien), import (importe dans le document actif : dwg, dxf, obj, stl, step, igs, fbx, skp, 3dm...), export (exporte tout le document, la sélection ou des objets précis ; le format suit l'extension du fichier). Par sécurité, new et open refusent si le document actif a des modifications non enregistrées, sauf avec discard_changes=true, et save_as/export refusent d'écraser un fichier existant, sauf avec overwrite=true (à confirmer avec l'utilisateur).

| Paramètre | Type | Description |
|---|---|---|
| `action` **requis** | `new` / `open` / `save` / `save_as` / `import` / `export` | Opération à effectuer. |
| `path` | string | Chemin du fichier (open, save_as, import, export). |
| `template` | string | new : gabarit .3dm à utiliser. |
| `discard_changes` | boolean | new/open : abandonner les modifications non enregistrées du document actif. (défaut : `False`) |
| `ids` | liste de string | export : n'exporter que ces objets. |
| `selected_only` | boolean | export : seulement la sélection. (défaut : `False`) |
| `version` | integer | save/save_as : version du format .3dm (8, 7, 6...). |
| `overwrite` | boolean | save_as/export : remplacer le fichier s'il existe déjà. (défaut : `False`) |

### `rhino_undo`

Annule (undo) ou rétablit (redo) les dernières opérations dans Rhino.

| Paramètre | Type | Description |
|---|---|---|
| `action` | `undo` / `redo` | undo pour annuler, redo pour rétablir. (défaut : `undo`) |
| `steps` | integer | Nombre d'étapes. (défaut : `1`) |

### `rhino_list_plugins`

Liste les plug-ins Rhino installés (chargés ou non) et, avec include_commands, les noms des commandes Rhino disponibles (utile pour rhino_run_command).

| Paramètre | Type | Description |
|---|---|---|
| `query` | string | Filtre sur le nom (plug-ins et commandes). |
| `loaded_only` | boolean |  (défaut : `False`) |
| `include_commands` | boolean |  (défaut : `False`) |

## Rhino : objets

### `rhino_get_objects`

Liste les objets du document Rhino (id, type, nom, calque, boîte englobante), avec filtres et pagination.

| Paramètre | Type | Description |
|---|---|---|
| `layer` | string | Ne garder que ce calque (chemin complet). |
| `type` | string | Type d'objet : Point, Curve, Brep (polysurface/solide), Extrusion, Surface, Mesh, SubD, Annotation (texte, cote), TextDot, Hatch, InstanceReference (bloc)... |
| `name` | string | Ne garder que les objets dont le nom contient ce texte. |
| `selected_only` | boolean | Seulement les objets sélectionnés. |
| `include_hidden` | boolean |  (défaut : `True`) |
| `limit` | integer | Nombre maximal d'éléments renvoyés. (défaut : `200`) |
| `offset` | integer |  (défaut : `0`) |

### `rhino_get_object_details`

Détails d'objets Rhino : attributs (nom, calque, couleur, matériau, visibilité, verrouillage, textes utilisateur, groupes) et géométrie (longueur, aire, volume, centroïde, solide/fermé, points d'une polyligne, centre/rayon d'un cercle, texte d'une annotation, bloc...).

| Paramètre | Type | Description |
|---|---|---|
| `ids` **requis** | liste de string | Identifiants (GUID) des objets. |

### `rhino_select_objects`

Sélection dans Rhino. action : select / unselect (par ids, ou par filtre layer/type/name), clear (tout désélectionner), get (objets sélectionnés).

| Paramètre | Type | Description |
|---|---|---|
| `action` | `select` / `unselect` / `clear` / `get` | Opération. (défaut : `select`) |
| `ids` | liste de string | Identifiants (GUID) des objets. |
| `layer` | string | Filtre : calque (chemin complet). |
| `type` | string | Type d'objet : Point, Curve, Brep (polysurface/solide), Extrusion, Surface, Mesh, SubD, Annotation (texte, cote), TextDot, Hatch, InstanceReference (bloc)... |
| `name` | string | Filtre : le nom contient ce texte. |

### `rhino_modify_objects`

Modifie des objets Rhino : nom, calque (créé si besoin), couleur (ou 'by_layer'), matériau (nom d'un matériau du document, ou 'by_layer'), visible (afficher/masquer), locked (verrouiller), user_text (clé -> valeur ; valeur null pour supprimer). Une seule étape d'annulation.

| Paramètre | Type | Description |
|---|---|---|
| `ids` **requis** | liste de string | Identifiants (GUID) des objets. |
| `name` | string |  |
| `layer` | string | Calque (chemin complet, ex. 'Façade::Vitrage') ; créé s'il n'existe pas. |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |
| `material` | string | Nom du matériau (voir rhino_material) ou 'by_layer'. |
| `visible` | boolean |  |
| `locked` | boolean |  |
| `user_text` | object | Textes utilisateur {clé: valeur}. |

### `rhino_transform_objects`

Transforme des objets Rhino (une seule étape d'annulation). operation : move (vector), copy (vector), rotate (angle en degrés, axis, center), scale (factor = nombre ou [sx, sy, sz], center), mirror (plane, 'yz' par défaut, passant par center), array_linear (count, vector entre deux copies), array_polar (count, center, axis, angle total en degrés = 360). center vaut par défaut le centre de la boîte englobante. copy=true garde les originaux. Renvoie les ids obtenus.

| Paramètre | Type | Description |
|---|---|---|
| `ids` **requis** | liste de string | Identifiants (GUID) des objets. |
| `operation` **requis** | `move` / `copy` / `rotate` / `scale` / `mirror` / `array_linear` / `array_polar` | Transformation. |
| `vector` | liste de number | Vecteur [x, y, z]. |
| `angle` | number | Angle en degrés (rotate, array_polar). |
| `center` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `axis` | liste de number | Axe de rotation (Z par défaut). |
| `factor` | valeur | Facteur d'échelle : nombre ou [sx, sy, sz]. |
| `plane` | valeur | Plan : 'xy' (défaut), 'yz', 'zx', ou objet {"origin": [x,y,z], "normal": [x,y,z]} ou {"origin": [...], "x_axis": [...], "y_axis": [...]}. |
| `count` | integer | Nombre total d'éléments du réseau (original compris). |
| `copy` | boolean |  (défaut : `False`) |

### `rhino_delete_objects`

Supprime des objets Rhino (même verrouillés). Une seule étape d'annulation (rhino_undo pour revenir).

| Paramètre | Type | Description |
|---|---|---|
| `ids` **requis** | liste de string | Identifiants (GUID) des objets. |

## Rhino : géométrie

### `rhino_create_geometry`

Crée de la géométrie dans Rhino (unités du document). Paramètres selon le type :
- point : point (ou points)
- line : start, end
- polyline : points, closed
- curve : points, degree (3), interpolate (true = passe par les points, false = points de contrôle), closed
- circle : center, radius, plane
- arc : center, radius, start_angle, end_angle (degrés), plane — ou points (3 points)
- ellipse : center, radius (x), radius2 (y), plane
- rectangle : corner, width, height, plane — ou corner + corner2
- polygon : center, radius, sides, plane
- plane_surface : corner, width, height, plane
- sphere : center, radius
- box : corner, width (x), depth (y), height (z), plane — ou corner + corner2 (diagonale)
- cylinder / cone : center (base), radius, height, axis (Z par défaut), cap
- torus : center, radius (grand), radius2 (petit), plane
- mesh : vertices [[x,y,z]...], faces [[i,j,k] ou [i,j,k,l]...]
Options communes : layer, name, color. Une seule étape d'annulation ; renvoie les ids créés.

| Paramètre | Type | Description |
|---|---|---|
| `type` **requis** | `point` / `line` / `polyline` / `curve` / `circle` / `arc` / `ellipse` / `rectangle` / `polygon` / `plane_surface` / `sphere` / `box` / `cylinder` / `cone` / `torus` / `mesh` | Forme à créer. |
| `point` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `points` | liste de array | Liste de points [[x, y, z], ...]. |
| `start` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `end` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `center` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `corner` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `corner2` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `radius` | number |  |
| `radius2` | number |  |
| `width` | number |  |
| `height` | number |  |
| `depth` | number |  |
| `sides` | integer |  |
| `start_angle` | number |  |
| `end_angle` | number |  |
| `plane` | valeur | Plan : 'xy' (défaut), 'yz', 'zx', ou objet {"origin": [x,y,z], "normal": [x,y,z]} ou {"origin": [...], "x_axis": [...], "y_axis": [...]}. |
| `axis` | liste de number | Vecteur [x, y, z]. |
| `degree` | integer |  (défaut : `3`) |
| `closed` | boolean |  (défaut : `False`) |
| `interpolate` | boolean |  (défaut : `True`) |
| `cap` | boolean |  (défaut : `True`) |
| `vertices` | liste de array | Liste de points [[x, y, z], ...]. |
| `faces` | liste de array |  |
| `layer` | string | Calque (chemin complet, ex. 'Façade::Vitrage') ; créé s'il n'existe pas. |
| `name` | string | Nom à donner à l'objet. |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |

### `rhino_geometry_operation`

Opérations géométriques sur des objets Rhino (ids) :
- boolean_union (ids), boolean_difference (ids moins other_ids), boolean_intersection (ids et other_ids) : solides fermés
- extrude : courbes, vector (ou height le long de Z), cap
- loft : courbes dans l'ordre, closed, cap
- revolve : courbes, axis [[x,y,z], [x,y,z]], angle (360 par défaut)
- sweep1 : profils (ids) le long de rail_id, cap
- pipe : courbes, radius, cap
- offset : courbes, distance (signe = côté), plane
- join : courbes ou surfaces
- explode : courbes (segments) ou polysurfaces (faces)
- cap : boucher les trous plans
- mesh : convertir surfaces/solides en maillage
- intersect : ids avec other_ids (courbes/points)
delete_input : supprimer les objets d'origine (par défaut oui pour booléens, join, explode, cap ; non sinon). Résultat sur le calque du premier objet, sauf layer/name/color. Une étape d'annulation.

| Paramètre | Type | Description |
|---|---|---|
| `operation` **requis** | `boolean_union` / `boolean_difference` / `boolean_intersection` / `extrude` / `loft` / `revolve` / `sweep1` / `pipe` / `offset` / `join` / `explode` / `cap` / `mesh` / `intersect` | Opération. |
| `ids` **requis** | liste de string | Identifiants (GUID) des objets. |
| `other_ids` | liste de string | Second groupe d'objets (booléens, intersect). |
| `rail_id` | string | sweep1 : courbe rail. |
| `vector` | liste de number | Vecteur [x, y, z]. |
| `height` | number |  |
| `distance` | number |  |
| `radius` | number |  |
| `axis` | liste de array | revolve : axe [[x,y,z], [x,y,z]]. |
| `angle` | number |  |
| `plane` | valeur | Plan : 'xy' (défaut), 'yz', 'zx', ou objet {"origin": [x,y,z], "normal": [x,y,z]} ou {"origin": [...], "x_axis": [...], "y_axis": [...]}. |
| `cap` | boolean |  (défaut : `True`) |
| `closed` | boolean |  (défaut : `False`) |
| `delete_input` | boolean |  |
| `layer` | string | Calque (chemin complet, ex. 'Façade::Vitrage') ; créé s'il n'existe pas. |
| `name` | string | Nom à donner à l'objet. |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |

## Rhino : calques, matériaux, blocs

### `rhino_layer`

Calques Rhino. action : list (calques, objets par calque, matériau, calque courant, états), create (path 'Parent::Enfant' créé avec ses parents ; color, visible, locked, material), update (path ; new_name, parent ('' = racine), color, visible, locked, material), delete (refuse s'il contient des objets, sauf delete_objects=true), set_current, save_state / restore_state / delete_state (state = nom d'un état de calques).

| Paramètre | Type | Description |
|---|---|---|
| `action` | `list` / `create` / `update` / `delete` / `set_current` / `save_state` / `restore_state` / `delete_state` | Opération. (défaut : `list`) |
| `path` | string | Chemin complet du calque (ex. 'Façade::Vitrage'). |
| `new_name` | string | update : nouveau nom (dernier niveau du chemin). |
| `parent` | string | update : nouveau calque parent ('' = racine). |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |
| `visible` | boolean |  |
| `locked` | boolean |  |
| `material` | string | Matériau du calque (nom, voir rhino_material ; '' = aucun). |
| `delete_objects` | boolean |  (défaut : `False`) |
| `state` | string | Nom de l'état de calques. |

### `rhino_material`

Matériaux de rendu (PBR) du document. action : list ; create (name, color, metallic 0-1, roughness 0-1, opacity 0-1 ; replace=true remplace un matériau du même nom partout où il est utilisé ; ids / layers pour l'affecter tout de suite) ; assign (name à des objets ids et/ou des calques layers) ; delete.

| Paramètre | Type | Description |
|---|---|---|
| `action` | `list` / `create` / `assign` / `delete` | Opération. (défaut : `list`) |
| `name` | string |  |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |
| `metallic` | number |  (défaut : `0.0`) |
| `roughness` | number |  (défaut : `0.5`) |
| `opacity` | number | 1 = opaque, 0.2 = verre. (défaut : `1.0`) |
| `ids` | liste de string | Identifiants (GUID) des objets. |
| `layers` | liste de string | Calques (chemins complets). |
| `replace` | boolean |  (défaut : `False`) |

### `rhino_block`

Blocs Rhino. action : list (définitions, nombre d'instances) ; create (name, ids, base_point = coin minimal par défaut ; delete_input=true remplace les objets par une instance, comme la commande Block) ; insert (name, point, scale, rotation en degrés autour de Z, layer) ; explode (ids d'instances ; explode_nested) ; delete (name, supprime aussi ses instances).

| Paramètre | Type | Description |
|---|---|---|
| `action` | `list` / `create` / `insert` / `explode` / `delete` | Opération. (défaut : `list`) |
| `name` | string |  |
| `ids` | liste de string | Identifiants (GUID) des objets. |
| `base_point` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `description` | string |  |
| `delete_input` | boolean |  (défaut : `True`) |
| `point` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `scale` | number |  (défaut : `1.0`) |
| `rotation` | number |  (défaut : `0.0`) |
| `explode_nested` | boolean |  (défaut : `False`) |
| `layer` | string | Calque (chemin complet, ex. 'Façade::Vitrage') ; créé s'il n'existe pas. |

## Rhino : vues, annotations, mises en page

### `rhino_capture_view`

Capture une vue Rhino en image PNG (vue active par défaut) pour voir le résultat. display_mode : mode d'affichage le temps de la capture (puis retour au mode de l'utilisateur) ; zoom_extents : cadrer tout.

| Paramètre | Type | Description |
|---|---|---|
| `view` | string | Nom de la vue (Perspective, Top, ...). |
| `width` | integer |  (défaut : `900`) |
| `height` | integer |  (défaut : `600`) |
| `display_mode` | string | Mode d'affichage : Wireframe, Shaded, Rendered, Ghosted, X-Ray, Technical, Artistic, Pen, Arctic, Raytraced... |
| `zoom_extents` | boolean |  (défaut : `False`) |

### `rhino_view`

Vues Rhino. action : list (vues, vues nommées, modes d'affichage, mises en page) ; set (view ; projection, display_mode, camera_location / camera_target, lens en mm, cplane = plan de construction, maximize) ; zoom (ids = cadrer ces objets, sinon zoom = 'extents' ou 'selected') ; save_named / restore_named / delete_named (name). La vue active est utilisée si view n'est pas précisé.

| Paramètre | Type | Description |
|---|---|---|
| `action` | `list` / `set` / `zoom` / `save_named` / `restore_named` / `delete_named` | Opération. (défaut : `list`) |
| `view` | string |  |
| `projection` | `top` / `bottom` / `left` / `right` / `front` / `back` / `perspective` / `two_point_perspective` | Projection standard. |
| `display_mode` | string | Mode d'affichage : Wireframe, Shaded, Rendered, Ghosted, X-Ray, Technical, Artistic, Pen, Arctic, Raytraced... |
| `ids` | liste de string | Identifiants (GUID) des objets. |
| `zoom` | `extents` / `selected` | zoom : tout ou la sélection. (défaut : `extents`) |
| `name` | string | Nom de la vue nommée. |
| `camera_location` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `camera_target` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `lens` | number | Focale équivalente 35 mm (perspective). |
| `cplane` | valeur | Plan : 'xy' (défaut), 'yz', 'zx', ou objet {"origin": [x,y,z], "normal": [x,y,z]} ou {"origin": [...], "x_axis": [...], "y_axis": [...]}. |
| `maximize` | boolean |  |

### `rhino_annotation`

Annotations Rhino. type : text (text, point, height, rotation en degrés, plane), dot (text, point), dimension (cote alignée : start, end, offset = point de la ligne de cote, facultatif), linear_dimension (cote horizontale/verticale), leader (points, text), hatch (ids de courbes fermées planes, pattern 'Solid'/'Hatch1'/'Grid'..., scale, rotation). Options : layer, name, color.

| Paramètre | Type | Description |
|---|---|---|
| `type` **requis** | `text` / `dot` / `dimension` / `linear_dimension` / `leader` / `hatch` | Annotation. |
| `text` | string |  |
| `point` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `points` | liste de array | Liste de points [[x, y, z], ...]. |
| `start` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `end` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `offset` | liste de number | Point [x, y, z] (z vaut 0 si omis). |
| `height` | number | Hauteur du texte. |
| `plane` | valeur | Plan : 'xy' (défaut), 'yz', 'zx', ou objet {"origin": [x,y,z], "normal": [x,y,z]} ou {"origin": [...], "x_axis": [...], "y_axis": [...]}. |
| `ids` | liste de string | Identifiants (GUID) des objets. |
| `pattern` | string |  (défaut : `Solid`) |
| `scale` | number |  (défaut : `1.0`) |
| `rotation` | number |  (défaut : `0.0`) |
| `layer` | string | Calque (chemin complet, ex. 'Façade::Vitrage') ; créé s'il n'existe pas. |
| `name` | string | Nom à donner à l'objet. |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |

### `rhino_layout`

Mises en page Rhino et PDF. action : list ; create (name, width/height de la feuille dans les unités de mise en page, 420 x 297 = A3 paysage en mm ; details = liste de fenêtres {projection, display_mode, rect [x0, y0, x1, y1], title}, une perspective pleine page par défaut) ; export_pdf (path ; layouts = noms des mises en page, toutes par défaut ; views = vues du modèle à ajouter ; dpi ; overwrite) ; delete (name).

| Paramètre | Type | Description |
|---|---|---|
| `action` | `list` / `create` / `export_pdf` / `delete` | Opération. (défaut : `list`) |
| `name` | string |  |
| `width` | number |  (défaut : `420`) |
| `height` | number |  (défaut : `297`) |
| `details` | liste de object |  |
| `path` | string |  |
| `layouts` | liste de string |  |
| `views` | liste de string |  |
| `dpi` | integer |  (défaut : `300`) |
| `overwrite` | boolean |  (défaut : `False`) |

## Rhino : scripts et commandes

### `rhino_execute_python`

Exécute du code Python 3 dans Rhino 8 (une seule étape d'annulation). Disponibles : Rhino (RhinoCommon), rs (rhinoscriptsyntax), sc (scriptcontext), System, doc (document actif), get_gh_doc() (document Grasshopper ; `import Grasshopper` pour l'API). Affecte la variable `result` pour renvoyer une valeur ; print() est aussi renvoyé. Outil polyvalent pour tout ce que les autres outils ne couvrent pas.

| Paramètre | Type | Description |
|---|---|---|
| `code` **requis** | string | Code Python 3 à exécuter. |

### `rhino_run_command`

Lance n'importe quelle commande Rhino comme si elle était tapée (macro), par ex. '_-Make2D _Enter', '_SelAll', '_Undo', '_-Export "C:\\dossier\\plan.dwg" _Enter'. Utilise la version « tiret » des commandes (_-Commande) et les noms anglais préfixés de « _ » : les versions à boîte de dialogue bloqueraient Rhino jusqu'à ce que l'utilisateur la ferme. Pour agir sur des objets précis, sélectionne-les d'abord (rhino_select_objects). Renvoie les objets créés, la sélection et ce que la commande a écrit dans la ligne de commande.

| Paramètre | Type | Description |
|---|---|---|
| `command` **requis** | string | Macro Rhino (ex. '_-Sphere 0,0,0 10'). |
| `echo` | boolean | Afficher la macro dans la ligne de commande. (défaut : `False`) |

## Grasshopper

### `gh_document`

Définitions Grasshopper. action : list (définitions ouvertes, active, solveur), new, open (path .gh/.ghx ; réactive si déjà ouverte), save, save_as (path ; overwrite), close (refuse si non enregistrée, sauf discard_changes=true), activate (name ou path), enable_solver / disable_solver (calcul automatique).

| Paramètre | Type | Description |
|---|---|---|
| `action` | `list` / `new` / `open` / `save` / `save_as` / `close` / `activate` / `enable_solver` / `disable_solver` | Opération. (défaut : `list`) |
| `path` | string |  |
| `name` | string | activate : nom affiché de la définition. |
| `discard_changes` | boolean |  (défaut : `False`) |
| `overwrite` | boolean |  (défaut : `False`) |

### `gh_get_canvas`

Décrit la définition Grasshopper active (ouvre Grasshopper si besoin) : composants, entrées/sorties, connexions, valeurs (curseurs, panneaux, interrupteurs, listes, couleurs), groupes, notes, activé/aperçu, erreurs et avertissements. ids : ne décrire que ces objets.

| Paramètre | Type | Description |
|---|---|---|
| `ids` | liste de string | Identifiants (InstanceGuid) Grasshopper. |

### `gh_capture_canvas`

Image PNG du canevas Grasshopper (cadré sur toute la définition), sans déplacer la vue de l'utilisateur.

| Paramètre | Type | Description |
|---|---|---|
| `width` | integer |  (défaut : `1200`) |
| `height` | integer |  (défaut : `800`) |
| `zoom_to_fit` | boolean |  (défaut : `True`) |

### `gh_search_components`

Cherche les composants Grasshopper installés (plug-ins compris) par nom, surnom, catégorie ou description ; renvoie nom, catégorie, kind (component/parameter), bibliothèque et guid.

| Paramètre | Type | Description |
|---|---|---|
| `query` | string | Texte à chercher (ex. 'circle', 'divide curve'). |
| `category` | string | Ne garder qu'une catégorie (ex. 'Curve', 'Maths'). |
| `limit` | integer |  (défaut : `30`) |

### `gh_add_component`

Ajoute un objet sur le canevas : par nom exact (ex. 'Circle', 'Number Slider', 'Panel', 'Boolean Toggle', 'Value List', 'Colour Swatch' ; si un nom désigne aussi un paramètre, le composant est choisi) ou par guid (gh_search_components). Placé automatiquement à droite si x/y sont omis. value/min/max/decimals règlent tout de suite un curseur, un panneau, etc. Renvoie son id et ses paramètres.

| Paramètre | Type | Description |
|---|---|---|
| `name` | string |  |
| `guid` | string |  |
| `x` | number |  |
| `y` | number |  |
| `nickname` | string |  |
| `value` | valeur | Valeur initiale (curseur, panneau, interrupteur...). |
| `min` | number |  |
| `max` | number |  |
| `decimals` | integer |  |

### `gh_connect`

Relie une sortie d'un objet Grasshopper à une entrée d'un autre (replace=true remplace les fils existants de cette entrée), ou les déconnecte (disconnect=true).

| Paramètre | Type | Description |
|---|---|---|
| `source_id` **requis** | string | Identifiant (InstanceGuid) de l'objet Grasshopper. |
| `source_output` | integer ou string | Index (0, 1, ...) ou nom du paramètre. |
| `target_id` **requis** | string | Identifiant (InstanceGuid) de l'objet Grasshopper. |
| `target_input` | integer ou string | Index (0, 1, ...) ou nom du paramètre. |
| `disconnect` | boolean |  (défaut : `False`) |
| `replace` | boolean |  (défaut : `False`) |

### `gh_modify_objects`

Modifie des objets Grasshopper : nickname, position (x, y), enabled (activer/désactiver), preview (aperçu dans Rhino), params = liste de {param (nom ou index), side 'input'/'output', mapping 'none'/'flatten'/'graft', reverse, simplify}.

| Paramètre | Type | Description |
|---|---|---|
| `ids` **requis** | liste de string | Identifiants (InstanceGuid) Grasshopper. |
| `nickname` | string |  |
| `x` | number |  |
| `y` | number |  |
| `enabled` | boolean |  |
| `preview` | boolean |  |
| `params` | liste de object |  |

### `gh_delete`

Supprime des objets du canevas Grasshopper.

| Paramètre | Type | Description |
|---|---|---|
| `ids` **requis** | liste de string | Identifiants (InstanceGuid) Grasshopper. |

### `gh_group`

Organisation du canevas. action : group (ids, name, color) ; ungroup (group_id) ; note (texte libre sur le canevas : text, x, y, size).

| Paramètre | Type | Description |
|---|---|---|
| `action` | `group` / `ungroup` / `note` | Opération. (défaut : `group`) |
| `ids` | liste de string | Identifiants (InstanceGuid) Grasshopper. |
| `name` | string |  |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |
| `text` | string |  |
| `x` | number |  |
| `y` | number |  |
| `size` | number | Taille du texte de la note. |
| `group_id` | string | Identifiant (InstanceGuid) de l'objet Grasshopper. |

### `gh_set_value`

Règle une valeur Grasshopper : curseur (Number Slider : value, min, max, decimals ; 0 = entier), panneau (texte), interrupteur (true/false), liste de valeurs (nom ou index de l'élément), nuancier (couleur), paramètre isolé (Number, Point [x,y,z], Text...), ou entrée d'un composant (input = nom/index de l'entrée ; valeur ou liste de valeurs, l'entrée ne doit pas être reliée).

| Paramètre | Type | Description |
|---|---|---|
| `id` **requis** | string | Identifiant (InstanceGuid) de l'objet Grasshopper. |
| `value` **requis** | valeur | Nouvelle valeur (ou liste de valeurs). |
| `input` | integer ou string | Index (0, 1, ...) ou nom du paramètre. |
| `min` | number |  |
| `max` | number |  |
| `decimals` | integer | 0 = curseur entier. |

### `gh_reference_rhino_geometry`

Envoie des objets Rhino (rhino_ids) dans un paramètre Grasshopper (Curve, Brep, Point, Geometry...) ou dans l'entrée input d'un composant, comme « Set one/multiple ... » : ils restent liés au modèle Rhino.

| Paramètre | Type | Description |
|---|---|---|
| `id` **requis** | string | Identifiant (InstanceGuid) de l'objet Grasshopper. |
| `rhino_ids` **requis** | liste de string | Identifiants (GUID) des objets. |
| `input` | integer ou string | Index (0, 1, ...) ou nom du paramètre. |

### `gh_get_output`

Lit les données d'une sortie (ou, avec side='input', d'une entrée) Grasshopper : arbre de données avec nombres, textes, points, et résumés de géométrie (type, boîte, longueur...).

| Paramètre | Type | Description |
|---|---|---|
| `id` **requis** | string | Identifiant (InstanceGuid) de l'objet Grasshopper. |
| `output` | integer ou string | Index (0, 1, ...) ou nom du paramètre. |
| `side` | `output` / `input` | Côté du composant. (défaut : `output`) |
| `limit` | integer |  (défaut : `200`) |

### `gh_solve`

Recalcule toute la définition Grasshopper et liste les composants en erreur ou en avertissement.

### `gh_bake`

Cuit (bake) la géométrie d'un composant ou paramètre Grasshopper dans Rhino : toutes ses sorties, ou seulement output ; sur le calque layer (créé si besoin), avec name et color. Une étape d'annulation ; renvoie les ids Rhino.

| Paramètre | Type | Description |
|---|---|---|
| `id` **requis** | string | Identifiant (InstanceGuid) de l'objet Grasshopper. |
| `output` | integer ou string | Index (0, 1, ...) ou nom du paramètre. |
| `layer` | string | Calque (chemin complet, ex. 'Façade::Vitrage') ; créé s'il n'existe pas. |
| `name` | string | Nom à donner à l'objet. |
| `color` | valeur | Couleur : [r, g, b] (0-255), '#RRGGBB', un nom ('red') ou 'by_layer' (couleur du calque). |
