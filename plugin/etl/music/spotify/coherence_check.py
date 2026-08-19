"""Détecte les incohérences entre le profil d'une playlist et son contenu.

Usage: python plugin/etl/music/spotify/coherence_check.py

Deux détections, par playlist :
- écart de GENRE : le profil = tags Last.fm dominants des artistes de la playlist
  (fréquence documentaire) ; un titre dont les artistes ne partagent AUCUN des tags
  majeurs du profil est signalé. Les titres sans tags connus sont ignorés (inconnu ≠ incohérent).
- écart de FEATURES : z-score d'energy/valence vs la moyenne de la playlist
  (seulement si assez de titres couverts par ReccoBeats — relançable quand la moisson avance).

Sort data/coherence.csv et réécrit l'onglet « Cohérence » du sheet.
Les playlists « fourre-tout » (archives annuelles, viviers Shazam/Discover…) sont
évaluées mais leurs écarts de genre ne sont pas listés : l'hétérogénéité y est assumée.
"""
import csv
import json
import re
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
import export_library as ex
from enrich_library import LASTFM_CACHE, RECCO_CACHE, load_cache, norm
from build_analysis import TAG_BLACKLIST

TOP_TAGS = 12          # taille du profil de genre d'une playlist
MIN_TRACKS = 8         # en dessous, pas assez de matière pour parler de profil
MIN_FEAT_COVER = 15    # titres avec features nécessaires pour les z-scores
Z_THRESHOLD = 2.2
CATCHALL = re.compile(r"^(20\d\d|Best-of|Discover|Backup|My Playlist|Mes titres Shazam|My Shazam|\.)")


JUNK_TAG = re.compile(r"[0-9_]|.{26,}")


def track_tags(lastfm, artists_field):
    tags = set()
    for name in artists_field.split(", "):
        e = lastfm.get(norm(name.strip()))
        if e:
            tags.update(t["name"] for t in e["tags"][:8]
                        if t["name"] not in TAG_BLACKLIST and not JUNK_TAG.search(t["name"]))
    return tags


def main():
    load_dotenv(Path(__file__).resolve().parents[4] / ".env")
    cache = ex.load_cache()
    lastfm = load_cache(LASTFM_CACHE)
    recco = load_cache(RECCO_CACHE)

    # --- pass 1 : profils de toutes les playlists (pour la détection ET les recommandations)
    profiles = {}   # name -> {"df": {tag: count}, "n": n_tagged, "e_mean": float|None}
    for pl in cache["playlists"]:
        entry = cache["tracks"][pl["id"]]
        rows = entry["rows"]
        if len(rows) < MIN_TRACKS:
            continue
        df, n_tagged = {}, 0
        feats_e = []
        for a, t, _ in rows:
            tags = track_tags(lastfm, a)
            if tags:
                n_tagged += 1
                for tag in tags:
                    df[tag] = df.get(tag, 0) + 1
            f = recco.get(f"{norm(a)}||{norm(t)}", {})
            if f.get("found") and f.get("energy") is not None:
                feats_e.append(f["energy"])
        profiles[entry["name"]] = {
            "df": df, "n": max(n_tagged, 1),
            "e_mean": statistics.mean(feats_e) if len(feats_e) >= MIN_FEAT_COVER else None,
            "catchall": bool(CATCHALL.match(entry["name"])),
        }

    def recommend(track_tags_, current, energy=None):
        best, best_score = "", 0.0
        for name, prof in profiles.items():
            if name == current or prof["catchall"]:
                continue
            score = sum(prof["df"][t] / prof["n"] for t in track_tags_ if t in prof["df"])
            if energy is not None and prof["e_mean"] is not None:
                score *= 1 - 0.5 * abs(energy - prof["e_mean"])
            if score > best_score:
                best, best_score = name, score
        return best if best_score >= 0.3 else ""

    outliers = []   # [playlist, artist, track, écart, détail, recommended]
    summary = []    # [playlist, n, %aligné, tags profil]
    for pl in cache["playlists"]:
        entry = cache["tracks"][pl["id"]]
        rows = entry["rows"]
        if len(rows) < MIN_TRACKS:
            continue
        catchall = bool(CATCHALL.match(entry["name"]))

        # --- profil de genre : fréquence documentaire des tags dans la playlist
        df = {}
        per_track = []
        for a, t, alb in rows:
            tags = track_tags(lastfm, a)
            per_track.append((a, t, tags))
            for tag in tags:
                df[tag] = df.get(tag, 0) + 1
        profile = {tag for tag, _ in sorted(df.items(), key=lambda kv: -kv[1])[:TOP_TAGS]}
        tagged = [(a, t, tags) for a, t, tags in per_track if tags]
        misfits = [(a, t, tags) for a, t, tags in tagged if not (tags & profile)]
        aligned_pct = 100 * (1 - len(misfits) / len(tagged)) if tagged else None

        if not catchall:
            for a, t, tags in misfits:
                f = recco.get(f"{norm(a)}||{norm(t)}", {})
                e = f.get("energy") if f.get("found") else None
                outliers.append([entry["name"], a, t, "genre",
                                 f"tags [{', '.join(sorted(tags)[:4])}] étrangers au profil "
                                 f"[{', '.join(sorted(profile)[:5])}…]",
                                 recommend(tags, entry["name"], e)])

        # --- écarts de features (energy/valence)
        feats = []
        for a, t, _ in rows:
            f = recco.get(f"{norm(a)}||{norm(t)}", {})
            if f.get("found") and f.get("energy") is not None:
                feats.append((a, t, f["energy"], f["valence"]))
        if len(feats) >= MIN_FEAT_COVER:
            for idx, key in [(2, "energy"), (3, "valence")]:
                vals = [f[idx] for f in feats]
                mean, std = statistics.mean(vals), statistics.pstdev(vals)
                if std < 0.05:
                    continue
                for a, t, e, v in feats:
                    z = ((e, v)[idx - 2] - mean) / std
                    if abs(z) > Z_THRESHOLD:
                        outliers.append([entry["name"], a, t, key,
                                         f"{key}={(e, v)[idx - 2]:.2f} vs moyenne {mean:.2f} (z={z:+.1f})",
                                         recommend(track_tags(lastfm, a), entry["name"], e)])

        summary.append([entry["name"], len(rows),
                        f"{aligned_pct:.0f}%" if aligned_pct is not None else "?",
                        "fourre-tout" if catchall else ", ".join(sorted(profile)[:6])])

    # tri : playlists les moins cohérentes d'abord dans le résumé
    summary.sort(key=lambda r: float(r[2].rstrip("%")) if r[2] != "?" else 100)

    with open("data/coherence.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["playlist", "artist", "track", "écart", "détail", "recommended playlist"])
        w.writerows(outliers)
    print(f"{len(outliers)} écarts détectés → data/coherence.csv")
    for r in summary[:15]:
        print(f"  {r[2]:>4} alignés | {r[0]} ({r[1]} titres) | {r[3]}")

    # push sheet
    import os
    import gspread
    sh = gspread.service_account(
        filename=str(Path(__file__).resolve().parents[4] / os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    ).open_by_key(os.environ["GSHEET_ID"])
    rows_out = ([["playlist", "artist", "track", "écart", "détail", "recommended playlist"]] + outliers)
    try:
        ws = sh.worksheet("Cohérence")
        ws.clear()
        ws.resize(rows=len(rows_out))
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Cohérence", rows=len(rows_out), cols=6)
    ws.update(values=rows_out, range_name="A1")
    print(f"onglet « Cohérence » : {len(outliers)} écarts")


if __name__ == "__main__":
    main()
