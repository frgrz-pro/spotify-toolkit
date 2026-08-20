# Portal6

Monorepo perso autour de la musique : référentiel unifié de la bibliothèque (Spotify + fichiers locaux),
outils d'analyse/rationalisation des playlists, et à terme web radio privée + sync multi-plateformes
(iTunes / Spotify / YouTube).

Le domaine musique (**Portal6-music**) a deux faces : la partie **software** (ETL, DB, analyses —
tout ce qui est décrit ci-dessous) et la partie **hardware** (`hardware/` : transformation d'un
poste Brandt RK 711S en web-radio cliente d'un serveur AzuraCast — cf. [hardware/README.md](hardware/README.md)).

## Structure

```
Portal6/
├── apps/                      # projets applicatifs (api, web, mobile) — à venir
├── plugin/
│   ├── db/                    # music.db (SQLite, artefact construit — gitignoré)
│   └── etl/
│       └── music/             # ETL musique
│           ├── build_db.py    # hydrate la DB depuis le vault data/
│           ├── spotify/       # extraction & enrichissement Spotify (API, Last.fm, ReccoBeats…)
│           └── local/         # scan & dedup de la bibliothèque de fichiers locale
├── data/                      # VAULT : donnée brute qui hydrate la DB (gitignoré)
│   ├── extract_spotify.xlsx   # export complet du Google Sheet « extract spotify »
│   └── library_scan.csv       # scan des fichiers locaux (produit par scan_library.py)
├── docs/                      # notes d'analyse et décisions
├── exports/                   # extended streaming history Spotify (quand reçu)
└── hardware/                  # projet Radio : Brandt RK 711S → web-radio (notes de design + BOM)
```

## Setup d'une nouvelle machine

Bootstrap automatisé dans `setup/` (idempotent, relançable) :

- **Windows** : `powershell -ExecutionPolicy Bypass -File setup\bootstrap.ps1`
  → installe WSL2 + Ubuntu si absents, la fonction PowerShell `p6`, puis enchaîne sur le `.sh` dans Ubuntu.
- **macOS / Ubuntu** : `./setup/bootstrap.sh`
  → brew (mac), zsh + oh-my-zsh, venv Python `~/.venvs/portal6` + dépendances, node, alias `portal6`.

Raccourcis obtenus : `p6` (PowerShell → Ubuntu, dans le projet, venv activé) et `portal6` (dans zsh/bash).

Le venv vit dans le home Linux, jamais dans le repo (un venv sur `/mnt/c` casse `ensurepip` sous WSL).
Le task runner est npm — les scripts restent en Python.

## La DB — référentiel unifié

```bash
npm run build:db    # (re)construit plugin/db/music.db depuis le vault data/
npm run db:stats    # synthèse sans reconstruire (Spotify vs local, matchés, orphelins)
```

Reconstruction complète à chaque run : les sources du vault restent la vérité, la DB est
un artefact dérivé. Tables : `tracks` (canonique, dédup par artiste+titre normalisés),
`playlists`, `playlist_tracks`, `files` (fichiers physiques), `enrichment` (genres, pays,
mood, audio features), `platform_refs` (IDs spotify/youtube/itunes — pour la future sync).

**IDs projet** : `P6-TRK-000001` (tracks), `P6-PLS-0001` (playlists), `P6-FIL-000001` (fichiers).
⚠️ Réattribués à chaque rebuild tant que la DB est un artefact dérivé ; à geler le jour où
elle devient référentiel maître.

## Flow local — scanner la bibliothèque de fichiers

```bash
python plugin/etl/music/local/scan_library.py "/mnt/m" --out data/library_scan.csv
```

Lecture seule (tags via mutagen, fallback nom de fichier). Puis `npm run build:db` pour
intégrer et matcher contre les tracks Spotify.

Dédoublonnage : `python plugin/etl/music/local/dedup_library.py --csv data/library_scan.csv`
génère un rapport + un `.ps1` de quarantaine qui **déplace** (jamais ne supprime) les
doublons de moindre qualité vers `_a_trier` — à relire avant exécution.

## Flow Spotify (historique — fait sur le Mac, conservé pour référence)

L'extraction complète a déjà tourné : 14 017 titres, 110 playlists, enrichis à 95 % en genres
(Last.fm), 84 % en pays (MusicBrainz), ~18 % en audio features (ReccoBeats, moisson interrompue).
Le tout vit dans le Google Sheet « extract spotify », dont `data/extract_spotify.xlsx` est l'export.

Scripts dans `plugin/etl/music/spotify/` :
- `export_library.py` — export incrémental des playlists (résilient au quota API 24h, cache reprennable)
- `enrich_library.py` — moissons Last.fm / ReccoBeats / MusicBrainz (`--lastfm`, `--recco`, `--country`, `--freq`)
- `analyze_playlists.py`, `coherence_check.py`, `split_monoliths.py`, `build_analysis.py` — analyses et onglets du Sheet
- `harvest.sh`, `progress.py` — orchestration des moissons (écrits pour macOS, à adapter si relancés ici)

Setup API (si on relance une moisson) : app sur https://developer.spotify.com/dashboard,
credentials dans `.env` (cf. `.env.example`), compte Premium requis depuis février 2026.

## Historique d'écoute (en attente)

Demander l'« Extended streaming history » sur https://www.spotify.com/account/privacy/
(délai 5-30 jours), dézipper dans `exports/`, puis :

```bash
python plugin/etl/music/spotify/analyze_listening_history.py
```

→ classement albums/artistes par temps d'écoute — base de la liste d'achats vinyle/CD.

## Roadmap

1. ✅ Extraction Spotify + enrichissement (Mac, juillet 2026)
2. ✅ DB SQLite unifiée (`plugin/db/music.db`)
3. ⏳ Scan bibliothèque locale `M:` + matching local ↔ Spotify
4. Dédoublonnage des fichiers locaux
5. Reprise moisson ReccoBeats (features audio) vers la DB
6. Web radio privée (Docker sur la tour) alimentée par la DB — design dans `hardware/design-serveur-azuracast.md`
   et `hardware/design-programmation-editoriale.md` ; le poste physique dans `hardware/design-brandt-rk711s.md`
7. Sync playlists iTunes / Spotify / YouTube (`platform_refs`)
