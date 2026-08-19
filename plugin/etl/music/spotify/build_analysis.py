"""Build/refresh the « Analyse » tab from the enrichment caches.

Usage:
  python plugin/etl/music/spotify/build_analysis.py            # one shot
  python plugin/etl/music/spotify/build_analysis.py --watch    # refresh every 5 min until harvests complete

Idempotent full rewrite of the tab (one Sheets write call per pass), so it can run
while enrich_library.py harvests are still filling the caches.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from enrich_library import LASTFM_CACHE, RECCO_CACHE, COUNTRY_CACHE, FREQ_CACHE, LIB_FILE, load_cache, norm

HEADER = ["playlist", "artist", "track", "album", "genres", "country", "mood",
          "energy", "valence", "danceability", "tempo", "acousticness", "instrumentalness",
          "camelot", "durée"]
# tags Last.fm fréquents qui ne sont pas des genres
TAG_BLACKLIST = {"seen live", "favorites", "favourites", "female vocalists", "male vocalists",
                 "under 2000 listeners", "spotify", "french", "france", "british", "american",
                 "usa", "uk", "german", "ninja tune", "all", "beautiful", "awesome", "love"}


def artist_genres(lastfm, artists_field, k=3):
    tags = {}
    for name in artists_field.split(", "):
        entry = lastfm.get(norm(name.strip()))
        if entry:
            for t in entry["tags"]:
                if t["name"] not in TAG_BLACKLIST:
                    tags[t["name"]] = max(tags.get(t["name"], 0), t["count"])
    top = sorted(tags.items(), key=lambda kv: -kv[1])[:k]
    return ", ".join(name for name, _ in top)


def mood_of(f):
    e, v = f.get("energy"), f.get("valence")
    if e is None or v is None:
        return ""
    if e >= 0.5:
        return "energetic" if v >= 0.4 else "aggressive"
    return "chill" if v >= 0.4 else "melancholic"


def build_rows():
    lastfm = load_cache(LASTFM_CACHE)
    recco = load_cache(RECCO_CACHE)
    freq = load_cache(FREQ_CACHE)
    countries = load_cache(COUNTRY_CACHE)
    with LIB_FILE.open() as fh:
        lib = list(csv.DictReader(fh))
    rows = []
    n_genre = n_feat = 0
    for r in lib:
        k = f"{norm(r['artist'])}||{norm(r['track'])}"
        fq = freq.get(k, {})
        f = fq if fq.get("found") else recco.get(k, {})
        if f is fq and fq.get("found"):
            f = dict(fq, tempo=fq.get("bpm"))  # même clé que recco pour la suite
        genres = artist_genres(lastfm, r["artist"])
        n_genre += bool(genres)
        n_feat += bool(f.get("found"))
        fmt = lambda k: round(f[k], 2) if f.get("found") and f.get(k) is not None else ""
        first = r["artist"].split(", ")[0].strip()
        c = countries.get(norm(first), {})
        country = c.get("country") or ""
        dur = f.get("duration_ms")
        rows.append([r["playlist"], r["artist"], r["track"], r["album"], genres, country,
                     (f.get("mood") or mood_of(f)) if f.get("found") else "",
                     fmt("energy"), fmt("valence"), fmt("danceability"),
                     round(f["tempo"]) if f.get("found") and f.get("tempo") else "",
                     fmt("acousticness"), fmt("instrumentalness"),
                     f.get("camelot") or "",
                     f"{dur // 60000}:{dur % 60000 // 1000:02d}" if dur else ""])
    return rows, n_genre, n_feat, len(lastfm), len(recco)


def push(rows):
    import gspread
    import os
    sh = gspread.service_account(
        filename=str(Path(__file__).resolve().parents[4] / os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    ).open_by_key(os.environ["GSHEET_ID"])
    try:
        ws = sh.worksheet("Analyse")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Analyse", rows=len(rows) + 1, cols=len(HEADER))
    if ws.row_count < len(rows) + 1:
        ws.add_rows(len(rows) + 1 - ws.row_count)
    ws.update(values=[HEADER] + rows, range_name="A1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=int, default=300)
    args = ap.parse_args()
    load_dotenv(Path(__file__).resolve().parents[4] / ".env")

    while True:
        rows, n_genre, n_feat, n_artists, n_tracks = build_rows()
        push(rows)
        done = n_tracks >= len(rows)
        print(f"[{time.strftime('%H:%M:%S')}] Analyse: {len(rows)} lignes | "
              f"genres {n_genre} | features {n_feat} | caches: {n_artists} artistes, "
              f"{n_tracks} titres{' — moissons terminées' if done else ''}", flush=True)
        if not args.watch or done:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
