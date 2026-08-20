"""Identifie par empreinte acoustique les fichiers aux tags faibles (Shazam-like).

Pipeline par fichier : Chromaprint (fpcalc, calcul local de l'empreinte) ->
AcoustID (matching contre MusicBrainz) -> artiste/titre/album canoniques.

Prérequis :
- fpcalc : sudo apt install -y libchromaprint-tools
- clé API gratuite : https://acoustid.org/new-application -> ACOUSTID_API_KEY dans .env

Usage :
  python plugin/etl/music/local/fingerprint_library.py            # moisson complète (reprennable)
  python plugin/etl/music/local/fingerprint_library.py --limit 20 # essai sur 20 fichiers

Cibles : les fichiers du scan aux tags inexploitables (artiste ou titre absent, ou
titre purement numérique) — les mêmes que dedup_library ignore.

Reprennable comme les moissons Spotify : cache data/music/.fingerprint_cache.json
écrit tous les SAVE_EVERY fichiers, Ctrl-C sans perte, relancer reprend où on était.

Sortie : data/music/retag_plan.csv — le PLAN de retagging, à relire. AUCUN fichier
n'est modifié par ce script ; l'application des tags sera une étape séparée.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "data" / "music"
SCAN_FILE = DATA_DIR / "library_scan.csv"
CACHE_FILE = DATA_DIR / ".fingerprint_cache.json"
PLAN_FILE = DATA_DIR / "retag_plan.csv"

ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"
MIN_SCORE = 0.80          # sous ce score de confiance, on ne propose pas le tag
SAVE_EVERY = 50
REQUEST_INTERVAL = 0.40   # AcoustID autorise 3 req/s — on reste poli


def normalize_key(artist, title):
    """Clé faible = même critère que dedup_library : artiste/titre inexploitables."""
    a = (artist or "").strip()
    t = (title or "").strip()
    return not a or not t or t.isdigit()


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache):
    tmp = CACHE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False))
    tmp.replace(CACHE_FILE)


def fpcalc(path):
    """Empreinte Chromaprint. Retourne (duration, fingerprint) ou None si échec."""
    try:
        out = subprocess.run(
            ["fpcalc", "-json", path],
            capture_output=True, text=True, timeout=120,
        )
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)
        return data["duration"], data["fingerprint"]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, FileNotFoundError):
        return None


def acoustid_lookup(session, api_key, duration, fingerprint):
    """Interroge AcoustID. Retourne l'entrée de cache (status + tags proposés)."""
    for attempt in range(4):
        try:
            resp = session.post(ACOUSTID_URL, data={
                "client": api_key,
                "duration": int(duration),
                "fingerprint": fingerprint,
                "meta": "recordings releasegroups",
            }, timeout=30)
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        if resp.status_code != 200:
            return {"status": "error", "detail": f"http {resp.status_code}"}
        payload = resp.json()
        if payload.get("status") != "ok":
            return {"status": "error", "detail": str(payload.get("error", "?"))}
        results = payload.get("results", [])
        best = None
        for res in results:
            score = res.get("score", 0)
            for rec in res.get("recordings", []):
                if not rec.get("title") or not rec.get("artists"):
                    continue
                if best is None or score > best["score"]:
                    rgs = rec.get("releasegroups") or []
                    albums = [rg["title"] for rg in rgs if rg.get("type") == "Album" and rg.get("title")]
                    best = {
                        "score": round(score, 3),
                        "artist": ", ".join(a["name"] for a in rec["artists"]),
                        "title": rec["title"],
                        "album": albums[0] if albums else (rgs[0]["title"] if rgs and rgs[0].get("title") else ""),
                        "mbid": rec.get("id", ""),
                    }
        if best is None:
            return {"status": "nomatch"}
        if best["score"] < MIN_SCORE:
            return {"status": "low_score", **best}
        return {"status": "ok", **best}
    return {"status": "error", "detail": "retries exhausted"}


def write_plan(cache, rows_by_path):
    """Régénère le plan CSV complet depuis le cache (même partiel)."""
    with PLAN_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["path", "old_artist", "old_title", "new_artist", "new_title",
                    "new_album", "score", "mbid", "status"])
        for path, entry in cache.items():
            row = rows_by_path.get(path, {})
            w.writerow([
                path, row.get("artist", ""), row.get("title", ""),
                entry.get("artist", ""), entry.get("title", ""), entry.get("album", ""),
                entry.get("score", ""), entry.get("mbid", ""), entry["status"],
            ])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(SCAN_FILE))
    ap.add_argument("--limit", type=int, default=0, help="s'arrêter après N nouveaux fichiers")
    ap.add_argument("--exclude", default="_a_trier,/radio/,/downloads/",
                    help="sous-chaînes de chemins à exclure, séparées par des virgules "
                         "(défaut : quarantaine, mixtapes radio, téléchargements)")
    args = ap.parse_args()
    excludes = [e for e in args.exclude.split(",") if e]

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("ACOUSTID_API_KEY", "")
    if not api_key:
        sys.exit("ACOUSTID_API_KEY manquante dans .env — crée une app sur https://acoustid.org/new-application")
    try:
        subprocess.run(["fpcalc", "-version"], capture_output=True, timeout=10)
    except FileNotFoundError:
        sys.exit("fpcalc introuvable — sudo apt install -y libchromaprint-tools")

    with Path(args.csv).open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    targets = [r for r in rows if normalize_key(r.get("artist"), r.get("title"))
               and not any(e in r["path"] for e in excludes)]
    rows_by_path = {r["path"]: r for r in targets}
    print(f"{len(targets)} fichiers à tags faibles sur {len(rows)} scannés")

    cache = load_cache()
    todo = [r for r in targets if r["path"] not in cache]
    print(f"{len(cache)} déjà traités, {len(todo)} restants")

    session = requests.Session()
    done_this_run = 0
    t0 = time.time()
    try:
        for r in todo:
            path = r["path"]
            if not Path(path).exists():
                cache[path] = {"status": "missing"}  # déplacé/quarantainé depuis le scan
            else:
                fp = fpcalc(path)
                if fp is None:
                    cache[path] = {"status": "fpcalc_failed"}
                else:
                    cache[path] = acoustid_lookup(session, api_key, *fp)
                    time.sleep(REQUEST_INTERVAL)
            done_this_run += 1
            if done_this_run % SAVE_EVERY == 0:
                save_cache(cache)
                rate = done_this_run / (time.time() - t0)
                eta_h = (len(todo) - done_this_run) / rate / 3600 if rate else 0
                pct = 100 * len(cache) / len(targets)
                print(f"  {len(cache)}/{len(targets)} ({pct:.1f}%) — {rate:.1f} fichiers/s — ETA {eta_h:.1f} h")
            if args.limit and done_this_run >= args.limit:
                print(f"--limit {args.limit} atteint, arrêt propre.")
                break
    except KeyboardInterrupt:
        print("\nInterrompu — progression sauvegardée, relance pour reprendre.")
    finally:
        save_cache(cache)
        write_plan(cache, rows_by_path)

    ok = sum(1 for e in cache.values() if e["status"] == "ok")
    nomatch = sum(1 for e in cache.values() if e["status"] in ("nomatch", "low_score"))
    err = sum(1 for e in cache.values() if e["status"] not in ("ok", "nomatch", "low_score"))
    print(f"\nIdentifiés: {ok} | sans match fiable: {nomatch} | erreurs/absents: {err}")
    print(f"Plan de retagging : {PLAN_FILE}")
    print("Aucun fichier modifié — l'application des tags est l'étape suivante, séparée.")


if __name__ == "__main__":
    main()
