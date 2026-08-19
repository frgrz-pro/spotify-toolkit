"""Parse the Spotify "Extended streaming history" export into a ranked
album/artist shortlist for physical (vinyl/CD) repurchase.

Usage:
  1. Unzip the export Spotify emails you into exports/
     (files named like Streaming_History_Audio_2023_1.json)
  2. python plugin/etl/music/spotify/analyze_listening_history.py
Output: data/albums_ranked.csv, data/artists_ranked.csv
"""
import json
from pathlib import Path

import pandas as pd

EXPORTS_DIR = Path(__file__).resolve().parents[4] / "exports"
DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "music"

MIN_MS_PLAYED = 30_000  # ignore plays under 30s (skips)


def load_history():
    files = sorted(EXPORTS_DIR.rglob("Streaming_History_Audio_*.json"))
    if not files:
        raise SystemExit(
            f"Aucun fichier Streaming_History_Audio_*.json trouvé dans {EXPORTS_DIR}.\n"
            "Dézippe l'export reçu par email de Spotify dans ce dossier."
        )
    records = []
    for f in files:
        records.extend(json.loads(f.read_text()))
    return records


def main():
    records = load_history()
    df = pd.DataFrame(records)
    df = df[df["ms_played"] >= MIN_MS_PLAYED]
    df = df[df["master_metadata_album_artist_name"].notna()]

    df["hours_played"] = df["ms_played"] / 1000 / 3600

    albums = (
        df.groupby(["master_metadata_album_artist_name", "master_metadata_album_album_name"])
        .agg(
            plays=("ms_played", "count"),
            hours_played=("hours_played", "sum"),
            distinct_tracks=("master_metadata_track_name", "nunique"),
            first_played=("ts", "min"),
            last_played=("ts", "max"),
        )
        .reset_index()
        .rename(columns={
            "master_metadata_album_artist_name": "artist",
            "master_metadata_album_album_name": "album",
        })
        .sort_values("hours_played", ascending=False)
    )

    artists = (
        df.groupby("master_metadata_album_artist_name")
        .agg(
            plays=("ms_played", "count"),
            hours_played=("hours_played", "sum"),
            distinct_albums=("master_metadata_album_album_name", "nunique"),
        )
        .reset_index()
        .rename(columns={"master_metadata_album_artist_name": "artist"})
        .sort_values("hours_played", ascending=False)
    )

    DATA_DIR.mkdir(exist_ok=True)
    albums.to_csv(DATA_DIR / "albums_ranked.csv", index=False)
    artists.to_csv(DATA_DIR / "artists_ranked.csv", index=False)

    print(f"{len(df)} écoutes analysées ({df['ts'].min()} → {df['ts'].max()})")
    print(f"\nTop 30 albums par temps d'écoute (→ data/albums_ranked.csv) :\n")
    print(albums.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
