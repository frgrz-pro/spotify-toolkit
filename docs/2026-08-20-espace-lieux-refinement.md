# Note de refinement — Espace « Lieux » : design retenu

> Phase : **refinement**. Suite de `2026-08-19-espace-lieux-exploration.md`. Les use cases
> réels ont été recueillis ; cette note pose la solution. Le walkthrough d'implem détaillé
> de chaque étape fera l'objet de notes courtes au fil de l'eau.

## Les use cases (recueillis, reformulés, priorisés)

**UC1 — Le répertoire de cartes (LE cœur).** Des « playlists de points » : pouvoir charger,
superposer et administrer plusieurs couches de lieux sur une même carte. Le grief fondateur :
toutes les apps existantes n'offrent qu'une seule couche, ce qui rend tout illisible. Le
produit = une DB de points consolidés et enrichis + une app avec *ma* carte et *mes* listes.

**UC2 — La capture « Shazam de lieux ».** Déposer un point sans friction (sans rien remplir à
la main), et le reviewer plus tard. Un point capturé entre dans une inbox de triage.

**UC3 — Le mode voyage.** Le déclencheur historique de ce genre de projets : avant/pendant les
vacances, renseigner en masse des repérages, et se préparer des itinéraires.

**UC4 — « Autour de moi ».** Quand on ne sait pas où aller (manger, sortir) : accès immédiat
à la liste de mes points à proximité. À terme : détecter aussi les événements, associations et
activités autour de moi (données externes).

**UC5 — Y aller vraiment.** (Ajouté après les protos desktop.) On enregistre beaucoup plus de
points qu'on n'en visite : il faut voir ceux où on n'est **jamais allé**. Statut visité /
à découvrir par lieu, filtre dédié sur la carte, et c'est ce signal qui guidera les
recommandations (quoi me proposer = mes points jamais visités, pondérés par contexte).

**Priorisation retenue :**

| Lot | Contenu |
|---|---|
| Lot A | Le référentiel existe (Takeout → ETL → `places.db`), aucune UI |
| Lot B | UC1 en lecture + UC4 (points à proximité) : carte, couches togglables, recherche, fiche lieu, filtre visité/à découvrir (UC5, lecture) |
| Lot C | UC2 : capture rapide + inbox de triage + « j'y suis allé » (UC5) — premières écritures |
| Lot D | UC3 : voyages, saisie en masse, itinéraires, offline mobile |
| Lot E | UC4 étendu (événements/assos : OSM, OpenAgenda, datatourisme…) + recommandations guidées par les non-visités (UC5) |

Chaque lot est une tranche verticale finie et utilisée avant d'ouvrir le suivant.

## Impact des use cases sur le modèle de données

Le modèle esquissé à l'exploration tient, avec ces précisions :

- **`lists` est le concept central**, pas un accessoire : c'est la « playlist de points ».
  Attributs : nom, couleur, icône, `visible` (état de la couche), groupe (le répertoire peut
  organiser les listes en dossiers — miroir des calques My Maps). Symétrie assumée avec
  `playlists` de `music.db`.
- **`places.status`** : `INBOX → DRAFT → VALIDATED`. La capture UC2 crée un point `INBOX`
  (lat/lon + timestamp + note libre optionnelle). Le « Shazam » proprement dit = au moment du
  triage, l'app propose automatiquement le POI OSM le plus proche (reverse geocoding + Overpass)
  pour pré-remplir nom/catégorie/adresse — l'utilisateur confirme ou corrige.
- **Les visites (UC5) sont des événements, pas une colonne.** Une visite = un `place_events`
  de type `VISIT` (date, note libre, éventuellement une appréciation) — donnée née dans l'app,
  rejouable au rebuild comme les captures. Le statut « visité / à découvrir » et le compteur de
  visites sont **dérivés** dans l'artefact (vue `v_place_status`). Tous les lieux importés
  naissent « jamais visité » — c'est exactement le point : rendre visible la masse des
  non-visités. Le filtre carte (Tous / À découvrir / Visités) arrive dès le Lot B (tout sera
  « à découvrir » au début, c'est normal) ; l'action « j'y suis allé » arrive au Lot C avec les
  autres écritures ; les recommandations pilotées par ce signal sont du Lot E.
- **`trips`** (Lot D) : un voyage = un groupe de listes + des itinéraires ordonnés
  (`trip_stops` avec position). Pas dans le schéma du Lot A, mais le modèle n'y ferme pas la porte.
- **Requêtes de proximité** : index R*Tree SQLite (module natif) sur `places` — disponible
  côté backend comme côté SQLDelight on-device. Le geohash reste pour la dédup.
- **`sources`** garde la provenance de chaque point (quel KML, quel CSV, quelle capture) —
  indispensable pour reconstruire la DB depuis le vault sans perdre les données nées dans l'app.

**Conséquence structurante — le gel des IDs arrive plus tôt que prévu.** Dès le Lot C, l'app
*écrit* (captures, triage, tags). La DB ne peut plus être un artefact jeté/reconstruit : le
vault Takeout reste la vérité pour les données *importées*, mais les données *nées dans l'app*
vivent dans la DB. Design retenu : table `id_registry` persistée (norm_name+geohash → P6-PLC-*)
qui survit aux rebuilds, et les écritures app sont journalisées dans une table d'événements
(`place_events`, le journal typé hérité de KMPGameMaster) rejouable après un rebuild. Le Lot A
doit livrer ce mécanisme, pas le bricoler plus tard.

## Décisions

1. **Emplacement : tout dans le monorepo Portal6.** Data : `plugin/etl/places/` +
   `plugin/db/places.db`. App : `apps/places/` — projet KMP autonome (structure wizard KMP :
   `composeApp` + `shared` + `server`), le module `server` étant le backend **Ktor** déployé
   sur l'infra locale.
2. **Carte : MapLibre + tuiles PMTiles self-hostées** (Protomaps, extrait Europe, servi par
   Ktor). Le **spike est la première étape du Lot B** — critère de validation : afficher
   ~1 000 points avec clustering sur desktop JVM *et* Android depuis les tuiles self-hostées.
   Plan B si le rendu desktop n'est pas au niveau : WebView MapLibre GL JS sur desktop,
   MapLibre natif sur mobile, même API de couches au-dessus.
3. **Enrichissement : OSM self-host par défaut** — Nominatim ou Photon (géocodage/reverse) +
   Overpass (POI) en containers sur l'infra. Google Places API uniquement en dépannage pour la
   résolution des CSV Saved qui résistent, avec budget de requêtes explicite.
4. **Persistance app : SQLDelight** (+ R*Tree). Pas de Realm.
5. **Navigation : Compose Navigation multiplateforme** (JetBrains). Voyager en repli si les
   transitions/deep-links coincent.
6. **Offline : Lot D, pas Lot B.** Mais les choix du Lot B le préparent gratuitement : PMTiles embarquables
   sur l'appareil, SQLDelight local, sync = rejeu de `place_events`.
7. **Web : hors périmètre** jusqu'à nouvel ordre. Si besoin, front MapLibre GL JS séparé sur
   l'API Ktor.

## Architecture cible

```
portal6/
├── data/places/                  # vault : Takeout (KML My Maps, CSV Saved) — la vérité importée
├── plugin/
│   ├── etl/places/               # Python : build_db, resolve_saved, enrich (OSM), rapport
│   └── db/places.db              # référentiel (id_registry + place_events persistés)
├── apps/places/                  # projet KMP
│   ├── shared/                   #   domaine + SQLDelight + client API
│   ├── composeApp/               #   Compose Multiplatform : desktop, android, ios
│   └── server/                   #   Ktor : API places + service des tuiles PMTiles
└── infra (tour) : containers Nominatim/Photon + Overpass ; Ktor ; fichiers PMTiles
```

Flux : Takeout → ETL → `places.db` → API Ktor → apps. Les écritures app remontent en
`place_events` dans la DB via l'API ; l'ETL les préserve au rebuild.

## Walkthrough (macro)

**Lot A — référentiel** (Python pur, aucune décision de stack en jeu) :
1. Takeout (My Maps + Saved) déposé dans `data/places/`.
2. Script d'inventaire : forme réelle des KML/CSV, volumétrie, taux de coordonnées manquantes.
3. `build_db.py` : parse KML → `places.db` + `id_registry` + rapport de consolidation.
4. Passe résolution/géocodage des CSV Saved (cache, reprise, budget — pattern `export_library`).

**Lot B — app lecture** :
5. Spike carte (critère ci-dessus) → décision ferme plan A/plan B.
6. Scaffold `apps/places/` + API Ktor lecture (listes, points, bbox, proximité R*Tree).
7. Écrans : carte + gestionnaire de couches, « autour de moi », fiche lieu, recherche.

**Lot C — capture** :
8. Bouton capture (mobile) → point INBOX ; écran de triage avec suggestion POI OSM ;
   `place_events` bout en bout (capture → triage → rebuild sans perte).

**Lots D / E** : voyages + itinéraires + offline ; puis sources d'événements.

## UX

C'est maintenant que la maquette a du sens : trois écrans structurants à dessiner avant le Lot B —
**la carte avec son gestionnaire de couches** (le cœur, là où aucune app existante ne satisfait),
**la fiche lieu**, et **l'inbox de triage** (Lot C, mais elle contraint le modèle). Figma
possible ; alternative plus rapide : maquettes directement ici (canvas de design éditable),
puis Figma seulement si besoin d'aller plus loin.

## Reste ouvert (à trancher pendant l'implem, pas bloquant)

- Choix Nominatim vs Photon (essayer Photon d'abord : plus léger, suffisant pour du reverse).
- Étendue des tuiles PMTiles (Europe vs monde — question de disque).
- Format exact de la suggestion « Shazam » au triage (rayon de recherche POI, scoring).
