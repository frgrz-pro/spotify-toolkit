# Note d'analyse — Export complet de la bibliothèque en CSV, résilient au quota 24h

## Constat

- Dernier run : 429 (Retry-After ~24h) avant d'avoir mis en cache la moindre playlist.
  `data/` ne contient qu'un `playlists_tracks.csv` vide, pas de fichier cache — on est reparti de zéro.
- Le quota journalier Dev Mode (changements fév. 2026) est petit et opaque : chaque requête compte.
- `analyze_playlists.py` fait déjà cache incrémental + reprise sur 429, mais il dépense des
  requêtes hors objectif (saved tracks, payloads complets) et mélange export et analyse.

## Objectif

Un CSV minimal `data/library.csv` : colonnes `playlist, artist, track, album`, une ligne par
(playlist, titre). Rien d'autre. On itère run par run, toutes les ~24h, jusqu'à complétion.

## Budget requêtes (estimation)

| Poste | Requêtes |
|---|---|
| Liste des playlists | ceil(N / 50) |
| Titres d'une playlist | ceil(nb_titres / 100) |
| `current_user` (filtre "mes" playlists) | 1, puis 0 (user id caché localement) |
| Playlists vides | 0 (le listing donne `tracks.total`, on skip sans requête) |

Le run 1 servira aussi de mesure : le compteur de requêtes affiché en continu nous dira
combien passent avant le 429, donc combien de jours il faudra.

## Design retenu

Nouveau script dédié `scripts/export_library.py` :

1. **Persistance locale = source de vérité.** `data/.export_cache.json` écrit après chaque
   playlist fetchée. Toute interruption (429, Ctrl-C, crash) est sans perte ; relancer reprend
   exactement où on s'est arrêté.
2. **Économie maximale de requêtes** :
   - `fields=` sur `playlist_items` pour ne recevoir que `next` + `track(name, artists(name))` ;
   - skip gratuit des playlists vides ;
   - user id mis en cache après le premier run ;
   - la liste des playlists elle-même est mise en cache (re-listée seulement si absente).
3. **429 = sortie propre**, pas une erreur : sauvegarde du cache, affichage du Retry-After et
   du pourcentage de progression, message « relance demain ».
4. **CSV régénéré depuis le cache** à chaque fin de run, même partiel — toujours cohérent,
   importable dans Google Sheets à tout moment.

## Google Sheet — deux options

- **A. Push live par l'API Sheets** (gspread + service account) : la feuille se remplit par
  paquets après chaque playlist. Coût : setup Google Cloud côté utilisateur (projet, service
  account, clé JSON, partage de la feuille). Le quota Sheets est large, aucun risque de ce côté.
- **B. Pas d'API Sheets** : la reprise est déjà garantie par le cache local ; on importe
  `library.csv` dans Google Sheets (Fichier → Importer) après chaque run partiel ou juste à la fin.

**Décision : A** (push live retenu, malgré le setup GCP). Détail d'implémentation important :
l'écriture Sheets se fait à des offsets de lignes explicites (pas des appends), avec le compteur
de lignes poussées persisté dans le cache — une reprise après crash réécrit la même plage au
lieu de dupliquer. Si le Sheet n'est pas encore configuré au moment d'un run, le script tourne
en local seulement et le Sheet se met à niveau au run suivant (rattrapage automatique).

## Décision

- Liked Songs inclus comme pseudo-playlist `Liked Songs`, récupérés en dernier pour ne pas
  cannibaliser le quota des playlists.

## Walkthrough

1. Écrire `scripts/export_library.py` (+ option Sheets si A retenue).
2. Run 1 : mesurer le quota réel (compteur de requêtes au moment du 429).
3. Re-runs quotidiens jusqu'à 100 % — possibilité d'un rappel/cron quotidien.
4. Import final dans Google Sheets.
