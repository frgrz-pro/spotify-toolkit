# Design — Serveur de web-radios (AzuraCast)

**Owner :** François Grzybowski
**Statut :** **BLOQUÉ** — aucun déploiement fonctionnel sur l'installation Windows actuelle
**Date :** 2026-08-12
**Piste :** SERVEUR — le poste qui consomme ces flux est décrit dans
[design-brandt-rk711s.md](design-brandt-rk711s.md)

> **À LIRE EN PREMIER — instructions d'exécution.**
> Ce chantier a déjà produit une impasse, et cette note existe d'abord pour ne pas la
> reproduire : **plusieurs `docker-compose.yml` ont été inventés dans des sessions
> précédentes, avec des images qui n'existent pas.** La règle qui prime sur tout le reste :
> **on ne rédige pas de compose, on prend celui du projet.** Voir §3.
> **On vérifie sur la source officielle avant de proposer**, on avance une étape à la fois, et
> on valide chaque étape avant la suivante.
> ⚠️ **Ne jamais exécuter `docker compose down -v`** tant que le contenu des volumes n'a pas
> été inventorié (§6).

---

## 0. L'objectif en un paragraphe

Faire tourner **plusieurs web-radios personnelles H24** depuis le DevLab, à partir d'une
**bibliothèque musicale centrale unique**, avec playlists et programmation horaire, via
**AzuraCast** (AutoDJ + Liquidsoap + Icecast). Le contenu éditorial — stations, grilles,
échelle d'énergie — est décrit dans
[design-programmation-editoriale.md](design-programmation-editoriale.md). Cette note-ci ne
traite que **l'infrastructure**.

---

## 1. État exact aujourd'hui

| Élément | État |
|---|---|
| Machine | Windows 11 + Docker Desktop + Docker Compose + Git (Git Bash disponible) |
| Bibliothèque musicale | `M:\music` |
| Racine Docker | `C:\docker\media` |
| Dépôt AzuraCast cloné | `C:\docker\media\azuracast` ✅ |
| `docker.sh` téléchargé | ✅ dans le dépôt |
| Compose global | `C:\docker\media\docker-compose.yml` — **contient probablement encore des images inexistantes** |
| Déploiement AzuraCast | ❌ **aucun déploiement fonctionnel ne doit être considéré comme établi** |

**Historique.** Une installation antérieure tournait dans un **LXC Proxmox** (`LXC-Radio`,
`/media/music`, `/srv/services/azuracast`) et avait validé le fonctionnement d'AzuraCast et de
la programmation, avec une station **Midnight Club** créée et configurée. Le projet a été
volontairement redémarré sur Windows 11 + Docker Desktop.

---

## 2. Les deux blocages constatés

### 2.1 Images Docker inexistantes

Les compose proposés référençaient :

```
azuracast/azuracast_web:latest
azuracast/azuracast_stations:latest
```

Docker répond :

```
pull access denied ... repository does not exist
```

**Diagnostic :** ce sont les images de l'**architecture pré-consolidation** d'AzuraCast, qui
séparait le conteneur web et le conteneur stations. Cette architecture est retirée ; les
versions actuelles s'appuient sur une image consolidée. **Les compose qui les référencent sont
définitivement invalides.**

### 2.2 `docker.sh` refuse de s'exécuter sous Git Bash

```
[FAIL] Operating System: MINGW64_NT-10.0-26200
You are running an unsupported operating system.
```

**Diagnostic :** Git Bash n'est pas l'environnement attendu par le script officiel. Le script
est pensé pour un hôte Linux — ce qui, sur Windows, désigne **WSL2**, pas MINGW.

> Note de méthode : la bonne commande de téléchargement sous PowerShell est
> `Invoke-WebRequest ... -OutFile`, car `curl` y est un alias d'`Invoke-WebRequest` et
> n'accepte pas `-L`. Ce point-là est réglé.

---

## 3. La règle qui prime sur tout

> **On ne rédige pas de `docker-compose.yml` pour AzuraCast.**
> On prend celui que le projet fournit, on ne remplace pas une image par une autre « qui
> ressemble », et on ne devine pas un nom de service.
> Si une information manque, on la lit dans la **documentation officielle ou le dépôt**, pas
> dans une mémoire.

Corollaire : la **première action** du prochain chantier n'est pas d'écrire du YAML, c'est de
**vérifier la méthode d'installation actuellement supportée** (§5, Phase 1).

---

## 4. Architecture cible

```
                         ┌─────────────────────┐
                         │      M:\music       │
                         │  Bibliothèque MP3   │
                         │  (source unique)    │
                         └──────────┬──────────┘
                                    │  montée en lecture (et écriture maîtrisée)
                     ┌──────────────▼──────────────┐
                     │          AzuraCast          │
                     │  ┌────────┐ ┌────────┐      │
                     │  │Station1│ │Station2│ ...  │
                     │  └────────┘ └────────┘      │
                     │  playlists / scheduling     │
                     │  AutoDJ / Icecast / API     │
                     └──────────────┬──────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                │                   │                   │
             Stream             Metadata               API
                │                   │                   │
                ▼                   ▼                   ▼
        ┌───────────────┐      ┌─────────┐        ┌──────────┐
        │ LE POSTE      │      │  XMLTV  │        │ Scripts  │
        │ Brandt RK711S │      │  / M3U  │        │ énergie, │
        └───────────────┘      └────┬────┘        │ likes    │
                                    ▼             └──────────┘
                                  xTeVe → Plex
```

**Organisation Docker visée :**

```
C:\docker\media
├── docker-compose.yml       ← compose global
├── azuracast\               ← dépôt + fichiers du projet
├── dozzle\                  ← visualisation des logs, port 8888:8080
└── autres services
```

### Principe non négociable : la bibliothèque n'appartient pas aux radios

```
M:\music
├── Library
├── Live
├── Mixtapes
├── Playlists
├── Radio
└── Workspace
```

**Les radios ne doivent pas imposer leur organisation au stockage, ni dupliquer les fichiers.**
Plusieurs stations doivent pouvoir pointer sur les **mêmes fichiers physiques** et n'en
sélectionner que des sous-ensembles via playlists.

C'est pour cette raison que le répertoire créé automatiquement par AzuraCast — du type
`/var/azuracast/stations/<slug>/media` — **n'est pas** la bibliothèque du projet : il ne doit
pas devenir le lieu où vivent les MP3.

> **Point à instruire (Q3) :** comment exactement monter `M:\music` dans AzuraCast pour que
> plusieurs stations le partagent sans copie ? Selon les versions, AzuraCast propose des
> chemins média partagés entre stations. **À vérifier dans la doc, pas à supposer.**

---

## 5. Plan de reprise

### PHASE 1 — Vérifier la méthode officielle (avant tout YAML)

Lire la documentation et le dépôt AzuraCast sur : Docker Desktop, Windows 11, **WSL2**,
installation manuelle par Docker Compose, **fichiers compose réellement fournis**, **images
réellement publiées**, et support officiel — ou non — de Windows.

> **STOP / VÉRIFIER (Phase 1) :** la méthode supportée est identifiée et **écrite dans cette
> note**, avec le nom exact des images et le chemin du compose fourni. Aucun YAML n'a été
> rédigé.

### PHASE 2 — Nettoyer l'existant

Inventorier ce qui traîne avant de lancer quoi que ce soit :

```powershell
docker version
docker compose version
docker ps -a
docker volume ls
docker network ls
```

```powershell
cd C:\docker\media
docker compose config
```

Corriger ou remplacer le compose global fautif (§2.1).

> **STOP / VÉRIFIER (Phase 2) :** `docker compose config` sort une configuration valide, sans
> aucune image inexistante · l'inventaire des volumes est écrit (§6) · **aucun `down -v`**.

### PHASE 3 — Déployer AzuraCast

Selon la méthode retenue en Phase 1. Vérifier les **conflits de ports** avant lancement :
AzuraCast utilise notamment **80**, **443**, **2022**, plus une plage de ports par station.

> **STOP / VÉRIFIER (Phase 3) :** interface AzuraCast accessible · aucun conflit de port avec
> les autres services · Dozzle toujours joignable.

### PHASE 4 — Brancher la bibliothèque

Monter `M:\music` **sans que les stations n'y imposent leur arborescence**, et sans copie.

> **STOP / VÉRIFIER (Phase 4) :** deux stations différentes lisent le **même fichier
> physique** · aucun MP3 dupliqué dans les répertoires d'AzuraCast · `M:\music` inchangé.

### PHASE 5 — Recréer Midnight Club

Station de test et de référence (slug probable `midnight_club`), avec sa grille
([design-programmation-editoriale.md](design-programmation-editoriale.md)).

> **STOP / VÉRIFIER (Phase 5) :** la station diffuse en continu 24 h sans intervention · la
> grille horaire est respectée · le flux est lisible depuis un lecteur externe.

### PHASE 6 — Exposer pour le poste

Rendre les flux et l'API joignables depuis Internet, et vérifier ce dont le poste a besoin.

> **STOP / VÉRIFIER (Phase 6) :** flux joignable hors du LAN · API stations et now-playing
> répondent · **CORS** vérifié si la route web est retenue côté poste
> ([design-visualiseur.md](design-visualiseur.md)).

### PHASE 7 — Le reste

Stations 2 et 3, tagging énergie, système de likes, XMLTV/M3U → xTeVe → Plex. Voir
[design-programmation-editoriale.md](design-programmation-editoriale.md).

---

## 6. Volumes — prudence

Une installation antérieure (LXC) avait créé des volumes nommés du type :

```
azuracast_acme            azuracast_backups         azuracast_db_data
azuracast_geolite_install azuracast_rsas_install    azuracast_sftpgo_data
azuracast_station_data    azuracast_www_uploads     …
```

Ils **peuvent** contenir des données utiles de l'ancienne installation, mais **ne doivent pas
être supposés présents ni réutilisables** sous Windows. Inventorier avant toute action
destructive.

---

## 7. Configuration cible

```
TZ   = Europe/Paris
PUID = 1000
PGID = 1000

Bibliothèque   : M:\music
Racine Docker  : C:\docker\media
AzuraCast      : C:\docker\media\azuracast
Station 1      : Midnight Club  (slug probable : midnight_club)
Dozzle         : 8888:8080
```

---

## 8. Ce que le poste attend de ce serveur

Contrat côté poste : [design-brandt-rk711s.md](design-brandt-rk711s.md) §4.5 et §11.

| Le poste consomme | Statut |
|---|---|
| Flux Icecast stables, joignables depuis Internet | Phase 6 |
| API liste des stations | Native AzuraCast |
| API now-playing (titre, artiste, pochette) | Native AzuraCast |
| Énergie **E1–E5** du créneau en cours (optionnel, pilote le visualiseur) | Concept défini, **non exposé** — à concevoir |
| En-têtes **CORS** (si route web côté poste) | À configurer |

**Ce serveur est sur le chemin critique de la Phase 2 du poste.** En attendant, le poste se
teste sur des flux publics.

---

## 9. Questions ouvertes

1. **Q1 — Windows est-il le bon hôte ?** AzuraCast est un projet pensé pour Linux. Le retour
   sur un hôte Linux (LXC Proxmox, comme avant, ou une VM/WSL2 dédiée) est peut-être moins
   coûteux que de faire entrer un outil Linux dans Windows. **À trancher en Phase 1, avec la
   doc officielle en main** — c'est la question qui décide de tout le reste de ce chantier.
2. **Q2 — Que faire des données de l'ancienne installation LXC ?** Récupérer la station
   Midnight Club configurée, ou repartir propre ?
3. **Q3 — Montage partagé de `M:\music`** entre plusieurs stations, sans duplication (§4).
4. **Q4 — Exposition Internet** : nom de domaine, TLS, reverse proxy déjà présent dans le
   DevLab ?
5. **Q5 — Sauvegardes** : que sauvegarde-t-on, et où ? (la bibliothèque, la configuration
   AzuraCast, les grilles)

---

## 10. Liste des interdits (DO-NOT)

1. **Ne pas** rédiger un `docker-compose.yml` AzuraCast à la main ou de mémoire (§3).
2. **Ne pas** réutiliser les images `azuracast_web` / `azuracast_stations` : elles n'existent
   plus (§2.1).
3. **Ne pas** exécuter `docker compose down -v` avant l'inventaire des volumes (§6).
4. **Ne pas** exécuter `docker.sh` depuis Git Bash (§2.2).
5. **Ne pas** laisser AzuraCast devenir le propriétaire de la bibliothèque : `M:\music` reste
   la source unique, non réorganisée par les radios (§4).
6. **Ne pas** dupliquer les MP3 par station.
7. **Ne pas** lancer un déploiement sans avoir vérifié les conflits de ports (Phase 3).
8. **Ne pas** considérer une étape comme acquise sans sa vérification.
