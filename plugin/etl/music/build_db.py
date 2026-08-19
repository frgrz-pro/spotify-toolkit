"""Construit plugin/db/music.db — le référentiel SQLite unifié de la bibliothèque musicale.

Sources ingérées depuis le vault data/ (chacune optionnelle, le script prend ce qui est présent) :
- data/extract_spotify.xlsx  : export Spotify complet (onglets Sheet1, Analyse, Playlists)
- data/library_scan.csv      : scan des fichiers locaux (plugin/etl/music/local/scan_library.py)

Reconstruction complète à chaque run (drop & recreate) : les sources restent la
vérité, la DB est un artefact dérivé — pas de risque de perte, relançable à volonté.

Schéma :
- tracks         : référentiel canonique, unique par (norm_artist, norm_title)
- playlists      : playlists Spotify (+ profil de l'onglet « Playlists » si dispo)
- playlist_tracks: appartenance titre <-> playlist
- files          : fichiers physiques locaux, rattachés à un track si matchés
- enrichment     : genres/pays/mood/features par track (onglet « Analyse »)
- platform_refs  : IDs par plateforme (spotify/youtube/itunes) — vide pour l'instant,
                   sera rempli quand on récupérera/re-matchera les IDs.

Usage : python plugin/etl/music/build_db.py [--db plugin/db/music.db]
"""
import argparse
import csv
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data" / "music"                     # vault : donnée brute uniquement
DB_DIR = ROOT / "plugin" / "db"              # artefacts construits
XLSX_FILE = DATA_DIR / "extract_spotify.xlsx"
SCAN_FILE = DATA_DIR / "library_scan.csv"

# --- normalisation (même logique que plugin/etl/music/local/dedup_library.py) ---------
FEAT_RE = re.compile(r"\b(feat\.?|featuring|ft\.?)\b.*", re.IGNORECASE)
PAREN_RE = re.compile(r"[\(\[][^)\]]*[\)\]]")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = FEAT_RE.sub("", s)
    s = PAREN_RE.sub("", s)
    s = NON_ALNUM_RE.sub("", s)
    return s.strip()


# --- IDs projet : P6-<ACRONYME>-<numéro zéro-paddé> --------------------------
ID_WIDTHS = {"TRK": 6, "PLS": 4, "FIL": 6}
_counters = {k: 0 for k in ID_WIDTHS}


def new_id(prefix: str) -> str:
    _counters[prefix] += 1
    return f"P6-{prefix}-{_counters[prefix]:0{ID_WIDTHS[prefix]}d}"


SCHEMA = """
CREATE TABLE tracks (
    id           TEXT PRIMARY KEY,               -- P6-TRK-000001
    artist       TEXT NOT NULL,
    title        TEXT NOT NULL,
    album        TEXT,
    norm_artist  TEXT NOT NULL,
    norm_title   TEXT NOT NULL,
    origin       TEXT NOT NULL DEFAULT 'spotify',  -- première source qui l'a créé
    UNIQUE (norm_artist, norm_title)
);

CREATE TABLE playlists (
    id                TEXT PRIMARY KEY,           -- P6-PLS-0001
    name              TEXT NOT NULL UNIQUE,
    source            TEXT NOT NULL DEFAULT 'spotify',
    thematique        TEXT,
    genres_dominants  TEXT,
    artistes_phares   TEXT,
    energy            REAL,
    valence           REAL
);

CREATE TABLE playlist_tracks (
    playlist_id  TEXT NOT NULL REFERENCES playlists(id),
    track_id     TEXT NOT NULL REFERENCES tracks(id),
    PRIMARY KEY (playlist_id, track_id)
);

CREATE TABLE files (
    id            TEXT PRIMARY KEY,                -- P6-FIL-000001
    track_id      TEXT REFERENCES tracks(id),      -- NULL si pas encore matché/taggable
    path          TEXT NOT NULL UNIQUE,
    filename      TEXT,
    extension     TEXT,
    size_bytes    INTEGER,
    mtime         INTEGER,
    artist        TEXT,
    title         TEXT,
    album         TEXT,
    album_artist  TEXT,
    year          TEXT,
    track_number  TEXT,
    duration_sec  REAL,
    bitrate_kbps  INTEGER,
    sample_rate   INTEGER,
    tags_read     TEXT
);

CREATE TABLE enrichment (
    track_id          TEXT PRIMARY KEY REFERENCES tracks(id),
    genres            TEXT,
    country           TEXT,
    mood              TEXT,
    energy            REAL,
    valence           REAL,
    danceability      REAL,
    tempo             REAL,
    acousticness      REAL,
    instrumentalness  REAL,
    camelot           TEXT,
    duration          TEXT
);

CREATE TABLE platform_refs (
    track_id     TEXT NOT NULL REFERENCES tracks(id),
    platform     TEXT NOT NULL,                 -- 'spotify' | 'youtube' | 'itunes'
    external_id  TEXT NOT NULL,
    PRIMARY KEY (track_id, platform)
);

CREATE INDEX idx_tracks_norm ON tracks(norm_artist, norm_title);
CREATE INDEX idx_files_track ON files(track_id);

-- Vue de synthèse : où existe chaque titre ?
CREATE VIEW v_track_status AS
SELECT t.id, t.artist, t.title, t.album,
       (SELECT COUNT(*) FROM playlist_tracks pt WHERE pt.track_id = t.id) AS n_playlists,
       (SELECT COUNT(*) FROM files f WHERE f.track_id = t.id)             AS n_files,
       (SELECT MAX(f.bitrate_kbps) FROM files f WHERE f.track_id = t.id) AS best_bitrate,
       CASE WHEN EXISTS (SELECT 1 FROM playlist_tracks pt WHERE pt.track_id = t.id)
            THEN 1 ELSE 0 END AS on_spotify,
       CASE WHEN EXISTS (SELECT 1 FROM files f WHERE f.track_id = t.id)
            THEN 1 ELSE 0 END AS on_local
FROM tracks t;
"""


def get_or_create_track(cur, cache, artist, title, album, origin):
    """Retourne l'id du track canonique, en le créant si besoin. cache = {(na,nt): id}."""
    na, nt = normalize(artist), normalize(title)
    if not na and not nt:
        return None  # rien d'exploitable, pas de canonique
    key = (na, nt)
    if key in cache:
        return cache[key]
    tid = new_id("TRK")
    cur.execute(
        "INSERT INTO tracks (id, artist, title, album, norm_artist, norm_title, origin) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tid, artist or "", title or "", album or None, na, nt, origin),
    )
    cache[key] = tid
    return tid


def import_spotify(cur, cache):
    import pandas as pd

    print(f"Import Spotify depuis {XLSX_FILE.name} ...")
    xl = pd.ExcelFile(XLSX_FILE)

    # -- profils de playlists (onglet « Playlists », optionnel)
    profiles = {}
    if "Playlists" in xl.sheet_names:
        for _, r in xl.parse("Playlists").iterrows():
            profiles[str(r["playlist"])] = r

    # -- bibliothèque (Sheet1 = dédoublonnée par (playlist, titre))
    lib = xl.parse("Sheet1").fillna("")
    playlist_ids = {}
    n_links = 0
    for _, r in lib.iterrows():
        pname = str(r["playlist"])
        if pname not in playlist_ids:
            p = profiles.get(pname)
            pid = new_id("PLS")
            cur.execute(
                "INSERT INTO playlists (id, name, source, thematique, genres_dominants, "
                "artistes_phares, energy, valence) VALUES (?, ?, 'spotify', ?, ?, ?, ?, ?)",
                (
                    pid,
                    pname,
                    str(p["thématique (lecture Claude)"]) if p is not None else None,
                    str(p["genres dominants"]) if p is not None else None,
                    str(p["artistes phares"]) if p is not None else None,
                    float(p["energy"]) if p is not None and str(p["energy"]) not in ("", "nan") else None,
                    float(p["valence"]) if p is not None and str(p["valence"]) not in ("", "nan") else None,
                ),
            )
            playlist_ids[pname] = pid
        tid = get_or_create_track(cur, cache, str(r["artist"]), str(r["track"]), str(r["album"]), "spotify")
        if tid:
            cur.execute(
                "INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id) VALUES (?, ?)",
                (playlist_ids[pname], tid),
            )
            n_links += 1
    print(f"  {len(playlist_ids)} playlists, {len(cache)} tracks canoniques, {n_links} liens")

    # -- enrichissement (onglet « Analyse ») : une ligne par (playlist, titre) -> dédupe par track
    if "Analyse" in xl.sheet_names:
        ana = xl.parse("Analyse").fillna("")
        n_enriched = 0
        for _, r in ana.iterrows():
            key = (normalize(str(r["artist"])), normalize(str(r["track"])))
            tid = cache.get(key)
            if not tid:
                continue

            def num(col):
                v = str(r.get(col, ""))
                try:
                    return float(v)
                except ValueError:
                    return None

            cur.execute(
                "INSERT OR IGNORE INTO enrichment (track_id, genres, country, mood, energy, "
                "valence, danceability, tempo, acousticness, instrumentalness, camelot, duration) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tid,
                    str(r.get("genres", "")) or None,
                    str(r.get("country", "")) or None,
                    str(r.get("mood", "")) or None,
                    num("energy"), num("valence"), num("danceability"), num("tempo"),
                    num("acousticness"), num("instrumentalness"),
                    str(r.get("camelot", "")) or None,
                    str(r.get("durée", "")) or None,
                ),
            )
            n_enriched += cur.rowcount if cur.rowcount > 0 else 0
        print(f"  {n_enriched} tracks enrichis (genres/features)")


def import_local(cur, cache):
    print(f"Import scan local depuis {SCAN_FILE.name} ...")
    with SCAN_FILE.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    n_matched = n_created = n_orphans = 0
    for r in rows:
        na, nt = normalize(r.get("artist", "")), normalize(r.get("title", ""))
        key = (na, nt)
        if not na and not nt:
            tid = None
            n_orphans += 1
        elif key in cache:
            tid = cache[key]
            n_matched += 1
        else:
            tid = get_or_create_track(cur, cache, r.get("artist", ""), r.get("title", ""),
                                      r.get("album", ""), "local")
            n_created += 1

        def num(field, cast=float):
            v = r.get(field, "")
            try:
                return cast(float(v))
            except (TypeError, ValueError):
                return None

        cur.execute(
            "INSERT OR IGNORE INTO files (id, track_id, path, filename, extension, size_bytes, "
            "mtime, artist, title, album, album_artist, year, track_number, duration_sec, "
            "bitrate_kbps, sample_rate, tags_read) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id("FIL"), tid, r.get("path", ""), r.get("filename", ""), r.get("extension", ""),
                num("size_bytes", int), num("mtime", int),
                r.get("artist", ""), r.get("title", ""), r.get("album", ""),
                r.get("album_artist", ""), r.get("year", ""), r.get("track_number", ""),
                num("duration_sec"), num("bitrate_kbps", int), num("sample_rate", int),
                r.get("tags_read", ""),
            ),
        )
    print(f"  {len(rows)} fichiers : {n_matched} matchés Spotify, "
          f"{n_created} nouveaux tracks locaux, {n_orphans} sans artiste/titre exploitables")


def summary(cur):
    q = lambda sql: cur.execute(sql).fetchone()[0]
    print("\n=== Synthèse ===")
    print(f"tracks canoniques : {q('SELECT COUNT(*) FROM tracks')}")
    print(f"  - vus sur Spotify : {q('SELECT COUNT(*) FROM v_track_status WHERE on_spotify=1')}")
    print(f"  - présents en local : {q('SELECT COUNT(*) FROM v_track_status WHERE on_local=1')}")
    print(f"  - sur les deux : {q('SELECT COUNT(*) FROM v_track_status WHERE on_spotify=1 AND on_local=1')}")
    print(f"  - Spotify uniquement : {q('SELECT COUNT(*) FROM v_track_status WHERE on_spotify=1 AND on_local=0')}")
    print(f"  - local uniquement : {q('SELECT COUNT(*) FROM v_track_status WHERE on_spotify=0 AND on_local=1')}")
    print(f"playlists : {q('SELECT COUNT(*) FROM playlists')}")
    print(f"fichiers locaux : {q('SELECT COUNT(*) FROM files')}")
    print(f"  - non rattachés (tags KO) : {q('SELECT COUNT(*) FROM files WHERE track_id IS NULL')}")
    print(f"tracks enrichis : {q('SELECT COUNT(*) FROM enrichment')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB_DIR / "music.db"))
    ap.add_argument("--stats", action="store_true",
                    help="affiche la synthèse de la DB existante sans la reconstruire")
    args = ap.parse_args()

    db_path = Path(args.db)
    if args.stats:
        if not db_path.exists():
            sys.exit(f"DB introuvable : {db_path} — lance d'abord build:db.")
        con = sqlite3.connect(db_path)
        summary(con.cursor())
        con.close()
        return

    if not XLSX_FILE.exists() and not SCAN_FILE.exists():
        sys.exit("Aucune source trouvée (ni extract_spotify.xlsx ni library_scan.csv dans data/).")

    if db_path.exists():
        db_path.unlink()  # rebuild complet : la DB est un artefact dérivé des sources
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    cache = {}  # (norm_artist, norm_title) -> track_id
    if XLSX_FILE.exists():
        import_spotify(cur, cache)
    else:
        print(f"! {XLSX_FILE.name} absent — partie Spotify sautée")
    if SCAN_FILE.exists():
        import_local(cur, cache)
    else:
        print(f"! {SCAN_FILE.name} absent — partie locale sautée (relance ce script quand le scan est fini)")

    con.commit()
    summary(cur)
    con.close()
    print(f"\nDB écrite : {db_path}")


if __name__ == "__main__":
    main()
