#!/usr/bin/env python
"""État des moissons d'enrichissement + complétion du sheet.

Usage:
  progress.py            # affichage one-shot
  progress.py --follow   # reste ouvert : un nouveau bloc s'empile à chaque point de %
                         # gagné, ligne surlignée dans la couleur de son stream (▲ +Xpp)
"""
import json
import re
import sys
import time
from pathlib import Path

DATA = Path(__file__).resolve().parents[4] / "data" / "music"
N_ARTISTS = 9636
N_TRACKS = 14017
POLL_S = 20

# nom -> couleur ANSI
COLORS = {"Last.fm": "35", "FreqBlog": "36", "Pays (MB)": "33", "Sheet": "32"}
RESET, BOLD = "\033[0m", "\033[1m"


def load(name):
    try:
        return json.loads((DATA / name).read_text())
    except FileNotFoundError:
        return {}


def snapshot():
    """-> {stream: (pct_int, ligne d'affichage sans couleur)}"""
    lf = load(".enrich_lastfm.json")
    rb = {k: v for k, v in load(".enrich_freq.json").items() if k != "_requests_used"}
    quota = load(".enrich_freq.json").get("_requests_used", 0)
    cy = {k: v for k, v in load(".enrich_country.json").items() if k != "_areas"}
    ok = sum(1 for v in rb.values() if v.get("found"))
    pays = sum(1 for v in cy.values() if v.get("country"))
    out = {
        "Last.fm": (100 * len(lf) // N_ARTISTS,
                    f"Last.fm    : {len(lf)}/{N_ARTISTS} artistes ({100 * len(lf) / N_ARTISTS:.0f}%)"),
        "FreqBlog": (100 * len(rb) // N_TRACKS,
                     f"FreqBlog   : {len(rb)}/{N_TRACKS} titres ({100 * len(rb) / N_TRACKS:.0f}%), "
                     f"match {100 * ok / max(len(rb), 1):.0f}%, quota {quota}/15000"),
        "Pays (MB)": (100 * len(cy) // N_ARTISTS,
                      f"Pays (MB)  : {len(cy)}/{N_ARTISTS} artistes ({100 * len(cy) / N_ARTISTS:.0f}%), "
                      f"avec pays {100 * pays / max(len(cy), 1):.0f}%"),
    }
    try:
        last = [l for l in (DATA / "build_analysis.log").read_text().splitlines() if "Analyse" in l][-1]
        h, rest = last.lstrip("[").split("] ", 1)
        g = int(re.search(r"genres (\d+)", rest)[1])
        f = int(re.search(r"features (\d+)", rest)[1])
        out["Sheet"] = (100 * f // N_TRACKS,
                        f"Sheet      : genres {100 * g / N_TRACKS:.0f}%, mood+features "
                        f"{100 * f / N_TRACKS:.0f}% (push de {h})")
    except (FileNotFoundError, IndexError, TypeError):
        out["Sheet"] = (0, "Sheet      : pas encore de passage du watcher")
    return out


def render(snap, gains=None):
    print(f"─── moissons portal6 ── {time.strftime('%H:%M:%S')} ───")
    for name, (pct, line) in snap.items():
        color = COLORS[name]
        if gains and name in gains:
            print(f"\033[{color}m{BOLD}{line}  ▲ +{gains[name]}pp{RESET}")
        else:
            print(f"\033[{color}m{line}{RESET}" if not gains else f"\033[2m{line}{RESET}")
    if gains is None:
        return
    done = all(pct >= 100 for name, (pct, _) in snap.items() if name != "Sheet")
    if done:
        print("\n✅ moissons terminées")
        sys.exit(0)


def main():
    follow = "--follow" in sys.argv
    snap = snapshot()
    render(snap, gains=None)
    if not follow:
        return
    shown = {k: v[0] for k, v in snap.items()}
    print("\n(mode follow : ré-affichage à chaque +1pp — Ctrl-C pour quitter)")
    while True:
        time.sleep(POLL_S)
        snap = snapshot()
        gains = {k: snap[k][0] - shown[k] for k in snap if snap[k][0] > shown[k]}
        if gains:
            render(snap, gains=gains)
            shown = {k: v[0] for k, v in snap.items()}


if __name__ == "__main__":
    main()
