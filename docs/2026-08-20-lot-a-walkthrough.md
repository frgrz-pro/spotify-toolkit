# Walkthrough — Lot A : le référentiel de lieux

> Phase : **walkthrough d'implem**. Suite de `2026-08-20-espace-lieux-refinement.md`.
> État : implémenté et testé sur fixtures ; en attente du Takeout réel pour les étapes 1–2,
> et la passe de résolution (étape 4) sera écrite quand on connaîtra la forme réelle des CSV.

## Ce qui est livré

Trois fichiers dans `plugin/etl/places/`, Python stdlib uniquement (zéro dépendance) :

- **`takeout.py`** — parsing partagé des exports : cartes My Maps (KML et KMZ, calques,
  points, ExtendedData ; les tracés LineString/Polygon sont comptés mais pas ingérés — matière
  des itinéraires du Lot D), et listes enregistrées (CSV, colonnes FR/EN, extraction des
  coordonnées depuis l'URL — formes `/search/lat,lon` et `@lat,lon` — et du CID Google).
- **`inventory.py`** — l'état des lieux du vault AVANT ingestion : cartes/calques/points,
  tracés, et pour chaque liste CSV la répartition « coordonnées directes / résoluble par
  CID / nom seul à géocoder ». À lancer en premier quand le Takeout arrive.
- **`build_db.py`** — construit le référentiel.

## Le design à deux bases (la décision structurante du lot)

| Base | Contrat |
|---|---|
| `plugin/db/places.db` | **Artefact** — drop & recreate à chaque run, comme `music.db` |
| `plugin/db/places_state.db` | **Persistante** — jamais reconstruite |

La base d'état porte : le **registre d'IDs** (`registry` : clé d'identité → `P6-PLC-*`/`P6-PLL-*`),
les **compteurs** d'allocation, et la table **`place_events`** (journal des écritures nées dans
l'app). Résultat vérifié au test : deux rebuilds successifs donnent exactement les mêmes IDs
(« IDs nouveaux ce run : 0 » au second run). Le gel des IDs exigé par le refinement est acquis.

`place_events` est créée mais vide : la **logique de rejeu arrive au Lot C** avec la première
écriture app — l'écrire maintenant serait du code mort non testable. Le mécanisme de
persistance (la partie qu'on ne peut pas rattraper après coup), lui, est en place.

⚠️ `plugin/db/*.db` est gitignoré : `places_state.db` contiendra à terme de la donnée
non-reconstructible (captures, triages). À intégrer à la stratégie de sauvegarde du vault.

## L'identité d'un lieu

Clés du registre, par priorité : `cid:<paire hex Google>` → `geo:<nom normalisé>|<geohash 7>`
(~76 m) → `raw:<nom normalisé>|<liste>` (pas de fusion inter-sources possible sans coordonnées).
Un lieu cumule plusieurs clés (alias) vers le même ID ; le lookup essaie toutes les clés avant
d'allouer — c'est ce qui permet à une ligne Saved portant CID + coordonnées de fusionner avec
un point My Maps déjà connu par sa clé géo (cas vérifié en test : le lieu récupère alors sa
ref Google dans `platform_refs`).

Cas assumé : une ligne Saved **sans** coordonnées ne peut pas fusionner avec son équivalent
My Maps avant la passe de résolution. Elle vivra comme doublon temporaire (`lat IS NULL`),
résorbé quand la résolution lui donnera des coordonnées et la clé géo correspondante.

## Schéma de l'artefact

`places` (id stable, nom, lat/lon/geohash, description, url, status — les imports naissent
`VALIDATED`, `INBOX` est réservé aux captures du Lot C —, origin, source_file, extra JSON),
`lists` (calque My Maps avec sa carte d'origine, ou liste Saved), `list_places` (avec note),
`platform_refs` (CID Google, OSM à venir), vue `v_place_status` (n_lists, resolved).
Pas de R*Tree ni de colonnes spéculatives (couleur/visible de couche = état d'app, Lot B/C).

## Usage

```bash
npm run places:inventory   # état des lieux du vault data/places/
npm run places:build       # construit places.db (+ registre)
npm run places:stats       # synthèse sans reconstruire
```

Testé sur `plugin/etl/places/fixtures/` (carte KML 2 calques avec doublon inter-calques et
tracé, CSV avec les 3 variantes d'URL) : 6 lieux canoniques, 2 fusions, 2 à résoudre,
2 refs CID, IDs stables sur rebuild. Les fixtures restent dans le repo comme base de
non-régression (`--data-dir plugin/etl/places/fixtures`).

## Reste à faire pour clore le Lot A

1. **Takeout** (action utilisateur) : sections « Maps (My Maps) » + « Enregistrés/Saved »,
   à déposer dans `data/places/` (dossier créé).
2. `npm run places:inventory` sur le réel → ajuster le parsing si le Takeout révèle des
   variantes non couvertes, puis `places:build`.
3. Écrire la **passe de résolution** des lieux sans coordonnées (CID → coordonnées, sinon
   géocodage du nom) : pattern `export_library.py` (cache, reprise, budget de requêtes).
   Le choix Photon vs Nominatim se fera à ce moment-là, sur la volumétrie réelle donnée
   par l'inventaire.
