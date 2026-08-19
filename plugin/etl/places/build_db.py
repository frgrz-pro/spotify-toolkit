"""Construit plugin/db/places.db — le référentiel SQLite unifié des lieux (Lot A).

Sources ingérées depuis le vault data/places/ (export Google Takeout) :
- *.kml / *.kmz : cartes My Maps (points avec coordonnées, calques)
- *.csv         : listes enregistrées (souvent sans coordonnées — celles extraites de
                  l'URL sont prises, le CID Google est stocké pour la passe de résolution)

Deux bases, deux contrats :
- plugin/db/places.db       : ARTEFACT — drop & recreate à chaque run, comme music.db.
- plugin/db/places_state.db : PERSISTANTE — jamais reconstruite. Porte le registre d'IDs
  (un lieu/une liste garde son P6-* d'un rebuild à l'autre), les compteurs, et le journal
  place_events (les écritures nées dans l'app, rejouées au rebuild — vide en Lot A, le
  rejeu arrive avec la première écriture app au Lot C).

Identité d'un lieu (clés du registre, par priorité) :
- cid:<paire hex Google>          si l'URL de liste porte un CID
- geo:<nom normalisé>|<geohash7>  si coordonnées connues (~76 m)
- raw:<nom normalisé>|<liste>     sinon (pas de fusion inter-sources possible)
Un même lieu peut cumuler plusieurs clés (alias) pointant vers le même ID.

Usage : python plugin/etl/places/build_db.py [--data-dir data/places] [--stats]
"""
import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

from takeout import discover, parse_my_map, parse_saved_csv

ROOT = Path(__file__).resolve().parents[3]
DB_DIR = ROOT / "plugin" / "db"

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return NON_ALNUM_RE.sub("", s.lower()).strip()


_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash(lat: float, lon: float, precision: int = 7) -> str:
    lat_lo, lat_hi, lon_lo, lon_hi = -90.0, 90.0, -180.0, 180.0
    bits, ch, even, out = 0, 0, True, []
    while len(out) < precision:
        if even:
            mid = (lon_lo + lon_hi) / 2
            ch = ch * 2 + (lon >= mid)
            lon_lo, lon_hi = (mid, lon_hi) if lon >= mid else (lon_lo, mid)
        else:
            mid = (lat_lo + lat_hi) / 2
            ch = ch * 2 + (lat >= mid)
            lat_lo, lat_hi = (mid, lat_hi) if lat >= mid else (lat_lo, mid)
        even = not even
        bits += 1
        if bits == 5:
            out.append(_BASE32[ch])
            bits, ch = 0, 0
    return "".join(out)


# --- Registre persistant : IDs stables d'un rebuild à l'autre -----------------

STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS registry (
    kind TEXT NOT NULL,             -- 'PLC' | 'PLL'
    key  TEXT NOT NULL,             -- clé d'identité (cid:/geo:/raw:, ou liste)
    id   TEXT NOT NULL,             -- P6-PLC-000001 — plusieurs clés peuvent partager un id
    PRIMARY KEY (kind, key)
);
CREATE TABLE IF NOT EXISTS counters (
    kind  TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS place_events (
    seq      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    type     TEXT NOT NULL,          -- CAPTURE / TRIAGE / TAG / ... (Lot C)
    place_id TEXT,
    payload  TEXT                    -- JSON
);
"""

ID_WIDTHS = {"PLC": 6, "PLL": 4}


class Registry:
    def __init__(self, state_con):
        self.con = state_con
        self.cur = state_con.cursor()
        self.cur.executescript(STATE_SCHEMA)
        self.n_new = 0

    def lookup(self, kind: str, key: str):
        row = self.cur.execute(
            "SELECT id FROM registry WHERE kind=? AND key=?", (kind, key)).fetchone()
        return row[0] if row else None

    def id_for(self, kind: str, keys: list[str]) -> str:
        """Cherche chaque clé dans l'ordre ; alloue si aucune ne matche ; aliase les manquantes."""
        pid = next((p for k in keys if (p := self.lookup(kind, k))), None)
        if pid is None:
            value = self.cur.execute(
                "SELECT value FROM counters WHERE kind=?", (kind,)).fetchone()
            n = (value[0] if value else 0) + 1
            self.cur.execute(
                "INSERT INTO counters (kind, value) VALUES (?, ?) "
                "ON CONFLICT(kind) DO UPDATE SET value=excluded.value", (kind, n))
            pid = f"P6-{kind}-{n:0{ID_WIDTHS[kind]}d}"
            self.n_new += 1
        for k in keys:
            self.cur.execute("INSERT OR IGNORE INTO registry (kind, key, id) VALUES (?, ?, ?)",
                             (kind, k, pid))
        return pid


# --- Schéma de l'artefact -----------------------------------------------------

SCHEMA = """
CREATE TABLE places (
    id           TEXT PRIMARY KEY,            -- P6-PLC-000001 (stable via registre)
    name         TEXT NOT NULL,
    norm_name    TEXT NOT NULL,
    lat          REAL,                        -- NULL = à résoudre (CID ou géocodage)
    lon          REAL,
    geohash      TEXT,
    description  TEXT,
    url          TEXT,
    status       TEXT NOT NULL DEFAULT 'VALIDATED',  -- INBOX/DRAFT/VALIDATED (imports = VALIDATED)
    origin       TEXT NOT NULL,               -- 'my_maps' | 'saved' (première source vue)
    source_file  TEXT NOT NULL,
    extra        TEXT                         -- ExtendedData KML (JSON)
);

CREATE TABLE lists (
    id           TEXT PRIMARY KEY,            -- P6-PLL-0001 (stable via registre)
    name         TEXT NOT NULL,               -- calque My Maps ou nom de liste Saved
    map_name     TEXT,                        -- carte My Maps d'origine (NULL pour Saved)
    type         TEXT NOT NULL,               -- 'my_maps' | 'saved'
    source_file  TEXT NOT NULL
);

CREATE TABLE list_places (
    list_id   TEXT NOT NULL REFERENCES lists(id),
    place_id  TEXT NOT NULL REFERENCES places(id),
    note      TEXT,
    tags      TEXT,                             -- colonne Tags des exports Saved, brute
    PRIMARY KEY (list_id, place_id)
);

CREATE TABLE platform_refs (
    place_id     TEXT NOT NULL REFERENCES places(id),
    platform     TEXT NOT NULL,               -- 'google' (CID) | 'osm' (à venir)
    external_id  TEXT NOT NULL,
    PRIMARY KEY (place_id, platform)
);

CREATE INDEX idx_places_geohash ON places(geohash);
CREATE INDEX idx_places_norm ON places(norm_name);

CREATE VIEW v_place_status AS
SELECT p.id, p.name, p.origin,
       (SELECT COUNT(*) FROM list_places lp WHERE lp.place_id = p.id) AS n_lists,
       CASE WHEN p.lat IS NOT NULL THEN 1 ELSE 0 END AS resolved
FROM places p;
"""


def place_keys(name, lat, lon, cid, list_key):
    """Clés d'identité par priorité : la première sert au lookup/création, les autres en alias."""
    norm = normalize(name)
    keys = []
    if cid:
        keys.append(f"cid:{cid}")
    if lat is not None and lon is not None:
        keys.append(f"geo:{norm}|{geohash(lat, lon)}")
    if not keys:
        keys.append(f"raw:{norm}|{list_key}")
    return keys


class Builder:
    def __init__(self, cur, registry):
        self.cur = cur
        self.registry = registry
        self.seen = set()      # ids déjà insérés ce run
        self.n_merged = 0      # occurrences fusionnées sur un lieu existant

    def upsert_place(self, *, name, lat, lon, cid, list_key, description, url,
                     origin, source_file, extra):
        keys = place_keys(name, lat, lon, cid, list_key)
        pid = self.registry.id_for("PLC", keys)
        if pid in self.seen:
            self.n_merged += 1
        else:
            self.seen.add(pid)
            self.cur.execute(
                "INSERT INTO places (id, name, norm_name, lat, lon, geohash, description, "
                "url, origin, source_file, extra) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, name or "(sans nom)", normalize(name), lat, lon,
                 geohash(lat, lon) if lat is not None else None,
                 description or None, url or None, origin, source_file,
                 json.dumps(extra, ensure_ascii=False) if extra else None))
        if cid:
            self.cur.execute(
                "INSERT OR IGNORE INTO platform_refs (place_id, platform, external_id) "
                "VALUES (?, 'google', ?)", (pid, cid))
        return pid

    def upsert_list(self, *, name, map_name, type_, source_file):
        lid = self.registry.id_for("PLL", [f"{type_}:{map_name or ''}/{name}"])
        self.cur.execute(
            "INSERT OR IGNORE INTO lists (id, name, map_name, type, source_file) "
            "VALUES (?,?,?,?,?)", (lid, name, map_name, type_, source_file))
        return lid

    def link(self, list_id, place_id, note, tags=None):
        self.cur.execute(
            "INSERT OR IGNORE INTO list_places (list_id, place_id, note, tags) VALUES (?,?,?,?)",
            (list_id, place_id, note or None, tags or None))


def import_my_maps(b, paths):
    n_points = n_skipped = 0
    for p in paths:
        m = parse_my_map(p)
        for layer in m["layers"]:
            lid = b.upsert_list(name=layer["name"] or "(sans calque)",
                                map_name=m["name"], type_="my_maps", source_file=p.name)
            for pm in layer["placemarks"]:
                if pm["geometry"] != "Point":
                    n_skipped += 1  # tracés : matière des itinéraires, hors Lot A
                    continue
                pid = b.upsert_place(
                    name=pm["name"], lat=pm["lat"], lon=pm["lon"], cid=None,
                    list_key=f"my_maps:{m['name']}/{layer['name']}",
                    description=pm["description"], url=None,
                    origin="my_maps", source_file=p.name, extra=pm["extended"])
                b.link(lid, pid, pm["description"])
                n_points += 1
    print(f"My Maps : {len(paths)} carte(s), {n_points} points ingérés"
          + (f", {n_skipped} tracés ignorés" if n_skipped else ""))


def import_saved(b, paths):
    n_rows = n_unresolved = 0
    for p in paths:
        rows = parse_saved_csv(p)
        lid = b.upsert_list(name=p.stem, map_name=None, type_="saved", source_file=p.name)
        for r in rows:
            note = " — ".join(x for x in (r["note"], r["comment"]) if x)
            pid = b.upsert_place(
                name=r["title"], lat=r["lat"], lon=r["lon"], cid=r["cid"],
                list_key=f"saved:{p.stem}", description=None, url=r["url"],
                origin="saved", source_file=p.name, extra=None)
            b.link(lid, pid, note, r["tags"])
            n_rows += 1
            if r["lat"] is None:
                n_unresolved += 1
    print(f"Saved : {len(paths)} liste(s), {n_rows} lieux ingérés, "
          f"{n_unresolved} sans coordonnées (passe de résolution à venir)")


def summary(cur):
    q = lambda sql, *a: cur.execute(sql, a).fetchone()[0]
    print("\n=== Synthèse ===")
    print(f"lieux canoniques : {q('SELECT COUNT(*) FROM places')}")
    print(f"  - avec coordonnées : {q('SELECT COUNT(*) FROM places WHERE lat IS NOT NULL')}")
    print(f"  - à résoudre : {q('SELECT COUNT(*) FROM places WHERE lat IS NULL')}")
    print(f"  - dans plusieurs listes : {q('SELECT COUNT(*) FROM v_place_status WHERE n_lists > 1')}")
    print(f"listes : {q('SELECT COUNT(*) FROM lists')} "
          f"(my_maps : {q('SELECT COUNT(*) FROM lists WHERE type=?', 'my_maps')}, "
          f"saved : {q('SELECT COUNT(*) FROM lists WHERE type=?', 'saved')})")
    print(f"liens liste-lieu : {q('SELECT COUNT(*) FROM list_places')}")
    print(f"refs Google (CID) : {q('SELECT COUNT(*) FROM platform_refs')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(ROOT / "data" / "places"))
    ap.add_argument("--db", default=str(DB_DIR / "places.db"))
    ap.add_argument("--state", default=str(DB_DIR / "places_state.db"))
    ap.add_argument("--stats", action="store_true",
                    help="affiche la synthèse de la DB existante sans la reconstruire")
    args = ap.parse_args()

    db_path = Path(args.db)
    if args.stats:
        if not db_path.exists():
            sys.exit(f"DB introuvable : {db_path} — lance d'abord places:build.")
        con = sqlite3.connect(db_path)
        summary(con.cursor())
        con.close()
        return

    found = discover(Path(args.data_dir))
    if not found["my_maps"] and not found["saved"]:
        sys.exit(f"Aucune source dans {args.data_dir} — dépose l'export Takeout dedans.")

    state_con = sqlite3.connect(args.state)   # persistante — jamais supprimée
    registry = Registry(state_con)

    if db_path.exists():
        db_path.unlink()  # l'artefact est reconstruit ; les IDs viennent du registre
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    b = Builder(cur, registry)
    if found["my_maps"]:
        import_my_maps(b, found["my_maps"])
    if found["saved"]:
        import_saved(b, found["saved"])

    con.commit()
    state_con.commit()
    if b.n_merged:
        print(f"Fusions : {b.n_merged} occurrence(s) rattachée(s) à un lieu déjà vu")
    print(f"IDs nouveaux ce run : {registry.n_new} (les autres viennent du registre)")
    summary(cur)
    con.close()
    state_con.close()
    print(f"\nDB écrite : {db_path}\nRegistre : {args.state}")


if __name__ == "__main__":
    main()
