# Spotify Toolkit

Deux objectifs :
1. Analyser/réorganiser les playlists actuelles (doublons, titres orphelins) et gérer toute ta bibliothèque, en ligne (Spotify) comme hors-ligne (fichiers locaux).
2. À partir de l'historique d'écoute complet, établir une liste d'albums à racheter en physique (vinyle/CD) avant de quitter Spotify.

Le projet est séparé en deux flows indépendants :
- **`scripts/spotify/`** — tout ce qui parle à l'API Spotify (nécessite internet + une app développeur).
- **`scripts/local/`** — scan et nettoyage de ta bibliothèque locale sur la tour Windows (aucune dépendance internet, aucune dépendance au flow Spotify).

---

## Partie A — Spotify (online)

### 0. Setup

```bash
cd /Users/r2d2/DevLab/spotify-toolkit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 1. Demander l'export de données (à faire en premier, ça prend jusqu'à 30 jours)

1. Va sur https://www.spotify.com/account/privacy/
2. Section "Télécharger tes données" → coche **"Extended streaming history"** (l'historique complet, pas juste le résumé annuel)
3. Confirme la demande. Tu recevras un email avec un lien de téléchargement (généralement sous 5-30 jours).
4. Quand tu reçois le ZIP : dézippe son contenu dans le dossier `exports/` de ce projet (les fichiers s'appellent `Streaming_History_Audio_YYYY_N.json`).

### 2. Créer une app Spotify Developer (pour l'automatisation des playlists)

**Prérequis : ton compte Spotify doit être en Premium** (obligatoire depuis les changements de février 2026 pour que l'API fonctionne, même en usage strictement personnel).

1. Va sur https://developer.spotify.com/dashboard et connecte-toi avec ton compte Spotify.
2. "Create app" → nom libre (ex: `perso-spotify-toolkit`), description libre.
3. Redirect URI : `http://127.0.0.1:8888/callback`
4. API utilisée : Web API.
5. Une fois créée, va dans "Settings" de l'app pour récupérer le **Client ID** et le **Client Secret**.
6. Colle-les dans le fichier `.env` :
   ```
   SPOTIFY_CLIENT_ID=...
   SPOTIFY_CLIENT_SECRET=...
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```

La première exécution d'un script ouvrira ton navigateur pour te connecter directement sur spotify.com (tu authentifies toi-même, aucune donnée ne transite par moi).

### 3. Exporter toute la bibliothèque en CSV + Google Sheet

```bash
python scripts/spotify/export_library.py
```

CSV minimal `data/library.csv` (`playlist, artist, track, album`, Liked Songs inclus en pseudo-playlist)
et push live vers un Google Sheet par paquets. Résilient au quota journalier : chaque page est
cachée dans `data/.export_cache.json`, un 429 est une sortie normale — relancer toutes les ~24h
jusqu'à complétion. Voir [docs/2026-07-26-export-csv-incremental.md](docs/2026-07-26-export-csv-incremental.md).

Prérequis Sheets (sinon le script tourne en local et le Sheet rattrape au run suivant) :
service account Google Cloud avec l'API Sheets activée, sa clé JSON dans `service-account.json`
(racine du projet, gitignoré), le Sheet partagé en éditeur avec l'email du service account,
et `GOOGLE_SERVICE_ACCOUNT_FILE` + `GSHEET_ID` dans `.env`.

### 4. Analyser les playlists actuelles

```bash
python scripts/spotify/analyze_playlists.py
```

Détecte : titres présents dans plusieurs playlists, titres likés ("Liked Songs") absents de toute playlist. Exporte le détail dans `data/playlists_tracks.csv`.

### 5. Construire la liste d'albums à racheter (une fois l'export reçu)

```bash
python scripts/spotify/analyze_listening_history.py
```

Agrège par artiste/album (heures d'écoute, nombre de lectures, période), classe par temps d'écoute décroissant. Sort `data/albums_ranked.csv` et `data/artists_ranked.csv` — base de départ pour la liste d'achats vinyle/CD.

---

## Partie B — Bibliothèque locale (offline, tour Windows)

Contexte : la tour tourne iTunes/Winamp, n'a pas d'accès internet, et sert de dépôt principal
pour la musique perso. Objectif : scanner cette bibliothèque en local (aucune dépendance),
ramener le CSV ici pour analyse et repérer les doublons à nettoyer.

### 1. Scanner la bibliothèque sur la tour Windows

`scripts/local/scan_library.py` est un fichier **autonome** — copie-le seul sur la tour (clé USB),
pas besoin du reste du projet.

Optionnel mais recommandé : installer `mutagen` (lecture des tags ID3/FLAC/MP4) pour de bien
meilleurs résultats que le fallback "nom de fichier". `mutagen` est pur Python, sans dépendance —
un seul fichier `.whl` à transférer par USB suffit, pas besoin d'internet sur la tour :

```bash
# Ici, avec internet : télécharge le wheel à transférer sur la tour
pip download mutagen --no-deps -d ./mutagen_offline
```
```powershell
# Sur la tour Windows, hors-ligne, une fois le .whl copié :
python -m pip install --no-index --find-links=. mutagen
```

Puis, sur la tour :

```powershell
python scan_library.py "D:\Musique" --out library_scan.csv
```

(plusieurs dossiers racine possibles : `python scan_library.py "D:\Musique" "E:\Autre" --out library_scan.csv`)

Ramène ensuite `library_scan.csv` par clé USB et dépose-le dans `data/` de ce projet.

### 2. Analyser et dédoublonner

```bash
python scripts/local/dedup_library.py --csv data/library_scan.csv
```

Regroupe par (artiste, titre) normalisés, classe chaque groupe par qualité (bitrate puis taille).
Sort deux fichiers :
- `data/local_duplicates_report.csv` — détail de tous les doublons, piste à garder marquée.
- `data/quarantine_duplicates.ps1` — script PowerShell **généré**, qui **déplace** (ne supprime
  jamais) les doublons de moindre qualité vers un sous-dossier `_a_trier` à côté de chaque fichier.

À ramener sur la tour par USB, à relire, puis à lancer toi-même depuis PowerShell. Une fois les
`_a_trier` vérifiés, tu vides ces dossiers manuellement.

---

## Prochaines étapes possibles

- Croiser `albums_ranked.csv` avec Discogs (disponibilité vinyle/CD, prix) pour prioriser les achats.
- Croiser la bibliothèque locale (Partie B) avec la liste Spotify (Partie A) pour voir ce qui existe déjà en local avant d'acheter.
- Scripts de réorganisation automatique (tri par genre/décennie, fusion de playlists en double).
