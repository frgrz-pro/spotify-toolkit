"""Fetch all playlists + saved tracks and report duplicates / unclassified tracks.

Usage: python plugin/etl/music/spotify/analyze_playlists.py
Output: data/playlists_tracks.csv, prints a summary report.

Dev Mode apps have a strict daily request quota (as of the Feb 2026 changes).
With 100+ playlists this script can exhaust it in one run. To survive that,
already-fetched playlists are cached in data/.playlist_tracks_cache.json —
rerunning after the quota resets picks up where it left off instead of
re-fetching everything.
"""
import json
import sys
from pathlib import Path

import pandas as pd
from spotipy.exceptions import SpotifyException

sys.path.insert(0, str(Path(__file__).parent))
from auth import get_client

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "music"
CACHE_FILE = DATA_DIR / ".playlist_tracks_cache.json"


def fetch_all_playlists(sp):
    playlists = []
    results = sp.current_user_playlists(limit=50)
    while results:
        playlists.extend(results["items"])
        results = sp.next(results) if results["next"] else None
    return playlists


def fetch_playlist_tracks(sp, playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id, additional_types=["track"])
    while results:
        for item in results["items"]:
            track = item.get("track")
            if track and track.get("id"):
                tracks.append({
                    "track_id": track["id"],
                    "track_name": track["name"],
                    "artist": track["artists"][0]["name"] if track["artists"] else "",
                    "album": track["album"]["name"] if track.get("album") else "",
                })
        results = sp.next(results) if results["next"] else None
    return tracks


def fetch_saved_tracks(sp):
    tracks = []
    results = sp.current_user_saved_tracks(limit=50)
    while results:
        tracks.extend(item["track"] for item in results["items"] if item.get("track"))
        results = sp.next(results) if results["next"] else None
    return tracks


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache):
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache))


def retry_after_str(exc: SpotifyException) -> str:
    header = getattr(exc, "headers", None) or {}
    seconds = header.get("Retry-After")
    if seconds:
        hours = int(seconds) / 3600
        return f"{seconds}s (~{hours:.1f}h)"
    return "délai inconnu"


def main():
    sp = get_client()
    me = sp.current_user()
    print(f"Connecté en tant que: {me['display_name']} ({me['id']})")

    playlists = fetch_all_playlists(sp)
    owned = [pl for pl in playlists if pl["owner"]["id"] == me["id"]]
    print(f"{len(playlists)} playlists visibles, {len(owned)} t'appartiennent :")

    cache = load_cache()
    print(f"{len(cache)} playlists déjà en cache (ne seront pas re-fetchées).")

    quota_hit = False
    for i, pl in enumerate(owned, 1):
        if pl["id"] in cache:
            continue
        print(f"  [{i}/{len(owned)}] {pl['name']}...")
        try:
            tracks = fetch_playlist_tracks(sp, pl["id"])
        except SpotifyException as exc:
            if exc.http_status == 429:
                print(f"\nQuota API atteint. Retry-After: {retry_after_str(exc)}")
                print("Progression sauvegardée. Relance ce script après ce délai pour continuer.")
                save_cache(cache)
                quota_hit = True
                break
            raise
        cache[pl["id"]] = {"name": pl["name"], "tracks": tracks}
        save_cache(cache)  # incremental save, survives interruption

    rows = []
    for pl_id, entry in cache.items():
        for t in entry["tracks"]:
            rows.append({
                "playlist_id": pl_id,
                "playlist_name": entry["name"],
                **t,
            })

    df = pd.DataFrame(rows, columns=["playlist_id", "playlist_name", "track_id", "track_name", "artist", "album"])
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(DATA_DIR / "playlists_tracks.csv", index=False)
    print(f"\nExport: {DATA_DIR / 'playlists_tracks.csv'} ({len(df)} lignes, {len(cache)}/{len(owned)} playlists traitées)")

    if df.empty:
        return

    # Doublons : même track_id présent dans plusieurs playlists différentes
    dupes = (
        df.groupby("track_id")
        .filter(lambda g: g["playlist_id"].nunique() > 1)
        .sort_values("track_id")
    )
    if not dupes.empty:
        n_tracks = dupes["track_id"].nunique()
        print(f"\n{n_tracks} titres présents dans plusieurs playlists :")
        for track_id, g in dupes.groupby("track_id"):
            names = ", ".join(g["playlist_name"].unique())
            print(f"  - {g.iloc[0]['artist']} - {g.iloc[0]['track_name']}: {names}")
    else:
        print("\nAucun doublon entre playlists.")

    if quota_hit:
        return  # skip saved-tracks call, save remaining quota for the resume run

    # Titres sauvegardés (Liked Songs) absents de toute playlist
    try:
        saved = fetch_saved_tracks(sp)
    except SpotifyException as exc:
        if exc.http_status == 429:
            print(f"\nQuota atteint avant de pouvoir vérifier les titres likés (Retry-After: {retry_after_str(exc)}).")
            return
        raise
    saved_ids = {t["id"] for t in saved if t.get("id")}
    playlisted_ids = set(df["track_id"])
    orphans = saved_ids - playlisted_ids
    print(f"\n{len(orphans)} titres likés ne sont dans aucune playlist ({len(saved_ids)} likés au total).")


if __name__ == "__main__":
    main()
