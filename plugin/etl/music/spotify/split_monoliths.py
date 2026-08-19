"""Propose une découpe des playlists monolithiques en sous-playlists « gravables ».

Usage: python plugin/etl/music/spotify/split_monoliths.py

- Monolithe = playlist >= MONOLITH_MIN titres, hors archives datées (année dans le nom)
  et hors viviers (Shazam, Backup, My Playlist #, Discover…).
- Découpe par sous-genre : tags Last.fm discriminants au sein de la playlist
  (assignement glouton : chaque titre rejoint le premier tag candidat qu'il porte).
- Dimensionnement : double CD audio = 2 x 75 min ~ 150 min ~ CD_TRACKS titres à ~4 min.
  Les groupes plus gros deviennent des volumes (Vol. 1, Vol. 2, …).
- Dans chaque volume, titres triés par energy croissante (montée progressive) quand dispo.

Sort deux onglets : « Monolithes » (le plan) et « Monolithes détail » (l'affectation
titre par titre), plus data/monoliths_plan.csv et data/monoliths_detail.csv.
"""
import csv
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
import export_library as ex
from enrich_library import LASTFM_CACHE, RECCO_CACHE, load_cache, norm
from coherence_check import track_tags

MONOLITH_MIN = 120
CD_TRACKS = 37          # ~150 min à ~4 min/titre
MIN_GROUP = 12          # en dessous, le groupe est fusionné dans « divers »
EXCLUDE = re.compile(r"\b(19|20)\d\d\b|^(Backup|My Playlist|Mes titres Shazam|My Shazam|\.)")


def split_playlist(name, rows, lastfm, recco):
    """rows = [artist, track, album] -> liste de (sous_nom, thème, [(a, t, alb, energy)])"""
    tracks = []
    df = {}
    for a, t, alb in rows:
        tags = track_tags(lastfm, a)
        f = recco.get(f"{norm(a)}||{norm(t)}", {})
        e = f.get("energy") if f.get("found") else None
        tracks.append((a, t, alb, tags, e))
        for tag in tags:
            df[tag] = df.get(tag, 0) + 1

    n = len(tracks)
    # candidats : tags qui discriminent (ni quasi-universels, ni anecdotiques)
    candidates = [tag for tag, c in sorted(df.items(), key=lambda kv: -kv[1])
                  if c <= 0.6 * n and c >= max(MIN_GROUP, 0.08 * n)][:8]

    groups = {}
    for a, t, alb, tags, e in tracks:
        dest = next((c for c in candidates if c in tags), "divers")
        groups.setdefault(dest, []).append((a, t, alb, e))
    # fusion des groupes trop petits
    for tag in [k for k, v in groups.items() if k != "divers" and len(v) < MIN_GROUP]:
        groups.setdefault("divers", []).extend(groups.pop(tag))

    out = []
    for tag, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        members.sort(key=lambda m: (m[3] is None, m[3]))  # energy croissante, inconnus en fin
        volumes = [members[i:i + CD_TRACKS] for i in range(0, len(members), CD_TRACKS)]
        for vi, vol in enumerate(volumes, 1):
            sub = f"{name} — {tag}" + (f" (Vol. {vi})" if len(volumes) > 1 else "")
            out.append((sub, tag, vol))
    return out


def main():
    load_dotenv(Path(__file__).resolve().parents[4] / ".env")
    cache = ex.load_cache()
    lastfm = load_cache(LASTFM_CACHE)
    recco = load_cache(RECCO_CACHE)

    plan = [["playlist d'origine", "titres", "sous-playlist proposée", "thème",
             "titres/CD", "durée estimée (min)", "artistes phares"]]
    detail = [["playlist d'origine", "sous-playlist", "artist", "track", "album", "energy"]]
    n_monoliths = 0
    for pl in cache["playlists"]:
        entry = cache["tracks"][pl["id"]]
        rows = entry["rows"]
        if len(rows) < MONOLITH_MIN or EXCLUDE.search(entry["name"]):
            continue
        n_monoliths += 1
        for sub, tag, vol in split_playlist(entry["name"], rows, lastfm, recco):
            from collections import Counter
            top_artists = ", ".join(a for a, _ in Counter(m[0] for m in vol).most_common(3))
            plan.append([entry["name"], len(rows), sub, tag, len(vol),
                         round(len(vol) * 4), top_artists])
            for a, t, alb, e in vol:
                detail.append([entry["name"], sub, a, t, alb,
                               round(e, 2) if e is not None else ""])

    with open("data/monoliths_plan.csv", "w", newline="") as f:
        csv.writer(f).writerows(plan)
    with open("data/monoliths_detail.csv", "w", newline="") as f:
        csv.writer(f).writerows(detail)
    print(f"{n_monoliths} monolithes, {len(plan) - 1} sous-playlists proposées, "
          f"{len(detail) - 1} titres affectés")

    import os
    import gspread
    sh = gspread.service_account(
        filename=str(Path(__file__).resolve().parents[4] / os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    ).open_by_key(os.environ["GSHEET_ID"])
    for title, rows_out in [("Monolithes", plan), ("Monolithes détail", detail)]:
        try:
            ws = sh.worksheet(title)
            ws.clear()
            ws.resize(rows=len(rows_out))
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title, rows=len(rows_out), cols=len(rows_out[0]))
        ws.update(values=rows_out, range_name="A1")
        print(f"onglet « {title} » : {len(rows_out) - 1} lignes")


if __name__ == "__main__":
    main()
