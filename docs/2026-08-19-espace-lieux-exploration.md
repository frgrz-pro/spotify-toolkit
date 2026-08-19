# Note d'exploration — Espace « Lieux » (ex-Mapix) : référentiel de lieux perso + app go-to

> Phase : **exploration**. Refinement à suivre une fois les use cases et les arbitrages de fin
> de note tranchés. Walkthrough d'implem ensuite.

## Constat

- Le besoin : **consolider une DB de lieux personnelle** et en faire l'app go-to, spécialisée
  dans ses propres use cases — pas un clone de Google Maps.
- La matière première n'est **pas dans les anciens repos** : vérifié, ni `archive/Mapix` ni
  `archive/frgrz-mapix` ne contiennent le moindre dataset (CSV/KML/GeoJSON/DB). L'ancien Mapix
  était un SDK (wrapper Rx des API Google Maps), pas une app avec des données.
- La vraie donnée vit dans le **compte Google** : « des tonnes de maps » (Google My Maps) +
  vraisemblablement des listes de lieux enregistrés (Favoris, Envie d'y aller, listes custom).
- Ce qu'on récupère des anciens repos, ce sont des **concepts** (voir plus bas), et de
  l'espace musique de Portal6 un **modèle de pipeline éprouvé** : vault → ETL → référentiel
  SQLite → apps.
- Atout : une **infra perso** — on peut self-héberger géocodage, tuiles de cartes et backend,
  donc viser le zéro dépendance/coût Google à terme.

## Vision

Trois couches, dans cet ordre de construction (leçon anti-récidive : la donnée d'abord) :

1. **Le référentiel** : tous mes lieux, dédupliqués, taggés, sourcés — `plugin/db/places.db`,
   même contrat que `music.db` (vault = vérité, DB = artefact reconstruit, IDs `P6-PLC-*`).
2. **Le backend** : Ktor sur l'infra locale, qui sert le référentiel (recherche, filtres,
   proximité) et plus tard la sync.
3. **Les apps** : Kotlin Multiplatform / Compose Multiplatform — desktop, Android, iOS.
   Web : décision reportée (voir « À trancher »).

## Récupération des données Google (le nerf de la guerre)

Via **Google Takeout**, trois gisements aux caractéristiques très différentes :

| Gisement | Format Takeout | Contenu | Piège |
|---|---|---|---|
| **My Maps** (les « tonnes de maps ») | Un KMZ/KML par carte | Points **avec coordonnées**, noms, descriptions, calques/dossiers, styles | Aucun — c'est le gisement riche, à traiter en premier |
| **Listes enregistrées** (Saved) | Un CSV par liste | Titre, note perso, **URL Google Maps** | Les CSV n'ont en général **pas de coordonnées** — juste nom + URL. Il faut résoudre les URLs (ID de lieu dans l'URL) via l'API Places ou géocoder le nom |
| **Maps (divers)** | JSON | Lieux libellés (domicile/travail), avis publiés, requêtes | Volume faible, bonus |

À part : la **Timeline** (historique de localisation) est depuis 2024 stockée sur l'appareil,
export séparé depuis le téléphone. Hors périmètre de la v1, mais le schéma doit pouvoir
l'accueillir plus tard (table `visits` potentielle).

Stratégie proposée : **My Maps d'abord** (données complètes, zéro requête externe), listes CSV
ensuite (nécessitent une passe de résolution/géocodage — budget de requêtes à la
`export_library.py`, avec cache et reprise).

### Enrichissement — deux écoles

- **Google Places API** : données riches (horaires, photos, notes), mais coût réel et couplage.
- **Self-host OSM sur l'infra** : Nominatim ou Photon pour le géocodage, Overpass pour les
  métadonnées. Gratuit, illimité, local. Reco : **OSM self-host par défaut**, Places API en
  appoint ponctuel si un use case l'exige.

## Modèle de données (esquisse, miroir de l'espace musique)

```
places          (P6-PLC-*, nom, lat/lon, geohash, adresse, norm_name — canonique, dédupliqué)
lists           (P6-PLL-*, nom, source_map/liste d'origine, type: my_maps | saved | custom)
list_places     (n-n, avec note perso, date d'ajout si dispo)
tags            (cuisine, café, rando, à-tester, validé, ... — le vocabulaire des use cases)
place_tags      (n-n)
sources         (provenance de chaque attribut : quel KML, quel CSV, quelle passe d'enrichissement)
enrichment      (horaires, catégorie OSM, site web, ...)
platform_refs   (google_cid, osm_id, ... — l'équivalent de la table homonyme de music.db)
```

Dédup : normalisation du nom (même esprit que `normalize()` de `build_db.py`) + proximité
géographique (geohash). C'est l'équivalent du matching local↔Spotify — et on sait déjà que
c'est là que se joue la qualité du référentiel.

## Ce qu'on reprend des anciens repos (concepts, pas code)

| Concept | Origine | Usage ici |
|---|---|---|
| Pipeline vault → ETL → DB artefact, idempotence, caches, gestion de quotas | Espace musique (portal6) | Copié tel quel pour `plugin/etl/places/` |
| Step builder typé / Request-RequestParam | Mapix | Si on écrit un client Places/Overpass : ordre d'appel garanti par le compilateur |
| Socle KMP : Compose Multiplatform + Koin + MaterialKolor | KMPGameMaster | Base des apps — en modernisant : **SQLDelight** (pas Realm), Ktor client |
| Wrapper DB générique (`getAllAsFlow<T>`, DSL de contraintes) | KMPGameMaster `RealmDatabase.kt` | À transposer sur SQLDelight |
| Rule Pattern (règles composables + fold) | KMPGameMaster | Règles de dédup/qualité sur les lieux |
| Contrat d'espace (Router pattern) | Budget / frgrz-mapix | L'app lieux ne connaît pas le shell Portal6 |
| Écran seeding / données de dev | Budget `feature-developer` | Mini-DB de 50 lieux pour développer l'UI sans le Takeout complet |
| design-core / design-app | frgrz-mapix | Theming du shell vs identité de l'espace |

## Stack proposée

- **Apps : Kotlin Multiplatform + Compose Multiplatform** (Android, iOS, Desktop JVM).
- **Persistance locale app : SQLDelight** (KMP natif, SQL explicite — cohérent avec la culture
  SQLite du projet).
- **Backend : Ktor** sur l'infra locale. Sert le référentiel + les tuiles (voir ci-dessous) +
  point de sync entre appareils.
- **DI : Koin** (éprouvé dans KMPGameMaster). Navigation : Compose Navigation ou Voyager — à
  fixer au refinement.
- **La carte — le point dur du KMP.** Il n'existe pas de solution Compose Multiplatform
  « évidente » pour le rendu carto sur les 3 cibles. Piste principale : **MapLibre**
  (le standard open-source, natif Android/iOS ; le projet `maplibre-compose` vise le
  multiplateforme). Côté tuiles : **PMTiles/Protomaps self-hostés** — un seul fichier de tuiles
  monde ou Europe, servable par Ktor, zéro coût, offline-friendly. **Un spike est obligatoire
  avant d'engager quoi que ce soit** : valider le rendu desktop, c'est le critère qui départage.
  Plan B assumé : carte native par plateforme, ou WebView MapLibre GL JS sur desktop.
- **Web : reporté.** Si un front web devient nécessaire, MapLibre GL JS est le standard — ce
  serait un petit front séparé consommant l'API Ktor, pas du Compose Web.

## Use cases candidats (à valider — c'est LE sujet du refinement)

L'app est « spécialisée dans la gestion de MES use cases » : il faut les nommer. Candidats
plausibles, à confirmer/corriger/prioriser :

1. **« On va où ? »** — recherche filtrée autour de moi ou d'un point : tags, testé/à-tester,
   type de lieu. Le use case resto/café/bar.
2. **Préparation de voyage** — constituer/consulter la carte d'une ville ou d'un trip
   (l'usage historique des My Maps ?), idéalement consultable offline sur mobile.
3. **Journal des lieux** — noter ce qu'on a testé, avis perso, à-retester.
4. **Recos** — partager une sélection de lieux à quelqu'un.

La tranche verticale v1 sera taillée sur le top 1–2 réel, pas sur les quatre.

## Première tranche verticale (proposition)

**v0 — le référentiel existe (aucune UI)** :
1. Takeout demandé et déposé dans le vault (`data/places/`).
2. ETL `plugin/etl/places/build_db.py` : parse des KML My Maps → `places.db` + rapport de
   consolidation (nb lieux, doublons détectés, lieux sans coordonnées, répartition par carte).
3. Passe 2 : ingestion des CSV de listes + résolution/géocodage avec cache et reprise.

**v1 — la première app voit le référentiel** :
4. Spike carte KMP (critère : afficher 1 000 points sur desktop + Android depuis des tuiles
   self-hostées).
5. App : carte + recherche + fiche lieu + filtres par tags/listes, en lecture seule sur un
   export du référentiel. L'écriture (tags, journal) vient après.

L'étape 0 de tout ça — et elle ne dépend d'aucune décision de stack — c'est **lancer le
Google Takeout** (My Maps + Saved), pour connaître le volume et la forme réels des données.

## Figma / UX

Proposition : attendre la fin du refinement des use cases. L'UX se travaille quand on sait ce
que l'app doit faire et qu'on a vu la forme des données consolidées (combien de lieux, combien
de listes, quels tags émergent). À ce moment-là, un Figma (ou une maquette rapide) pour les
2–3 écrans de la v1 aura du sens.

## Les trois projets qui atterrissent (cadrage général)

Confirmé : trois espaces cibles pour Portal6, alimentés par les idées/concepts/données des
anciens repos — pas leur code.

1. **Lieux** (cette note) — prioritaire.
2. **Budget** — besoin réel d'un outil solide ; fondation : le moteur de comptabilité en partie
   double (testé) + le modèle 50/30/20/ICEBOX. Note dédiée à venir quand Lieux sera lancé.
3. **Jeux** (gamemaster) — en dernier ; KMPGameMaster reste utilisable en satellite en attendant.

Un espace à la fois, tranche verticale finie avant d'ouvrir le suivant.

## À trancher au refinement

1. **Les use cases réels, priorisés** (top 2 pour la v1) — input utilisateur indispensable.
2. **Emplacement** : la data dans Portal6 (`plugin/etl/places/`, reco forte — même pipeline que
   la musique) ; l'app KMP dans `apps/` du monorepo ou repo dédié ?
3. **Carte** : résultat du spike MapLibre/`maplibre-compose` + choix tuiles (PMTiles self-host
   proposé) → décision ferme.
4. **Enrichissement** : OSM self-host par défaut, Places API en appoint — à confirmer, et
   définir le budget requêtes pour la résolution des CSV Saved.
5. **Navigation KMP** : Compose Navigation vs Voyager.
6. **Offline mobile** : exigence v1 ou plus tard ? (impacte le choix tuiles + sync)
