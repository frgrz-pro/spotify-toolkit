"""Enrich the deduped library with Last.fm genre tags and ReccoBeats audio features.

Usage:
  python plugin/etl/music/spotify/enrich_library.py --lastfm [--limit N]   # tags par artiste (genres/moods)
  python plugin/etl/music/spotify/enrich_library.py --recco  [--limit N]   # audio features par titre

Resumable like export_library.py: progress is cached after every few items in
data/.enrich_lastfm.json / data/.enrich_recco.json (separate files so both phases
can run concurrently). Rerunning skips whatever is already fetched.
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "music"
LIB_FILE = DATA_DIR / "library_dedup.csv"
LASTFM_CACHE = DATA_DIR / ".enrich_lastfm.json"
RECCO_CACHE = DATA_DIR / ".enrich_recco.json"
COUNTRY_CACHE = DATA_DIR / ".enrich_country.json"
MB_URL = "https://musicbrainz.org/ws/2/artist/"
MB_UA = "portal6/1.0 (fc.grzybowski.dev@gmail.com)"

LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
RECCO_URL = "https://api.reccobeats.com/v1"
FEATURE_KEYS = ["acousticness", "danceability", "energy", "instrumentalness",
                "liveness", "loudness", "speechiness", "tempo", "valence", "key", "mode"]
SAVE_EVERY = 20


def norm(s):
    return " ".join(s.casefold().split())


def load_cache(path):
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_cache(path, cache):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False))
    tmp.replace(path)


def load_library():
    with LIB_FILE.open() as f:
        return list(csv.DictReader(f))


def polite_get(session, url, *, params=None, max_retries=3):
    """GET with backoff on 429/5xx. Returns the response (raises after retries)."""
    for attempt in range(max_retries + 1):
        resp = session.get(url, params=params, timeout=20)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 0)) or 30 * (attempt + 1)
            wait = min(wait, 300)  # un Retry-After géant ne doit pas geler le process des heures
            print(f"  (429 — pause {wait}s…)", flush=True)
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        return resp
    resp.raise_for_status()
    return resp


# ---------- Last.fm : tags par artiste ----------

def run_lastfm(limit):
    load_dotenv(Path(__file__).resolve().parents[4] / ".env")
    key = os.environ["LASTFM_API_KEY"]
    rows = load_library()
    # tous les artistes splittés (les collabs comptent pour chaque nom)
    artists = []
    seen = set()
    for r in rows:
        for name in r["artist"].split(", "):
            name = name.strip()
            if name and norm(name) not in seen:
                seen.add(norm(name))
                artists.append(name)
    cache = load_cache(LASTFM_CACHE)
    todo = [a for a in artists if norm(a) not in cache]
    print(f"{len(artists)} artistes uniques, {len(artists) - len(todo)} déjà en cache, {len(todo)} à fetcher")
    if limit:
        todo = todo[:limit]

    session = requests.Session()
    for i, artist in enumerate(todo, 1):
        try:
            resp = polite_get(session, LASTFM_URL, params={
                "method": "artist.gettoptags", "artist": artist,
                "api_key": key, "format": "json", "autocorrect": 1,
            })
            d = resp.json()
            tags = d.get("toptags", {}).get("tag", [])
            cache[norm(artist)] = {
                "artist": artist,
                "tags": [{"name": t["name"].lower(), "count": t.get("count", 0)}
                         for t in tags[:12]],
                "error": d.get("error"),
            }
        except Exception as exc:
            print(f"  ⚠ {artist}: {exc}")
            cache[norm(artist)] = {"artist": artist, "tags": [], "error": str(exc)}
        if i % SAVE_EVERY == 0 or i == len(todo):
            save_cache(LASTFM_CACHE, cache)
            print(f"  [{i}/{len(todo)}] {artist} → {[t['name'] for t in cache[norm(artist)]['tags'][:4]]}")
        time.sleep(0.21)  # ~5 req/s max par politesse Last.fm
    save_cache(LASTFM_CACHE, cache)
    tagged = sum(1 for v in cache.values() if v["tags"])
    print(f"\nTerminé : {len(cache)} artistes en cache, {tagged} avec au moins un tag "
          f"({100 * tagged / max(len(cache), 1):.0f}%)")


# ---------- ReccoBeats : audio features par titre ----------

def search_title_variants(title):
    """Titre complet, puis sans suffixe ' - ...', puis sans '(feat…)/(remix…)'."""
    yield title
    if " - " in title:
        yield title.split(" - ")[0]
    if "(" in title:
        yield title.split("(")[0].strip()


def recco_lookup(session, artists_field, title):
    ours = {norm(a) for a in artists_field.split(", ") if a.strip()}
    for variant in dict.fromkeys(search_title_variants(title)):
        resp = polite_get(session, f"{RECCO_URL}/track/search", params={"searchText": variant})
        content = resp.json().get("content", [])
        best = None
        for c in content:
            names = {norm(a.get("name", "")) for a in c.get("artists", [])}
            if ours & names:
                if norm(c.get("trackTitle", "")) == norm(title):
                    best = c
                    break
                best = best or c
        if best:
            resp = polite_get(session, f"{RECCO_URL}/track/{best['id']}/audio-features")
            if resp.status_code != 200:
                return {"found": False, "error": f"features {resp.status_code}"}
            f = resp.json()
            out = {k: f.get(k) for k in FEATURE_KEYS}
            out["found"] = True
            out["matched_title"] = best.get("trackTitle")
            return out
    return {"found": False}


def run_recco(limit):
    rows = load_library()
    cache = load_cache(RECCO_CACHE)
    todo = [r for r in rows if f"{norm(r['artist'])}||{norm(r['track'])}" not in cache]
    print(f"{len(rows)} titres, {len(rows) - len(todo)} déjà en cache, {len(todo)} à fetcher")
    if limit:
        todo = todo[:limit]

    session = requests.Session()
    session.headers["User-Agent"] = "portal6/1.0 (export bibliothèque perso)"
    found = done = streak = 0
    for i, r in enumerate(todo, 1):
        k = f"{norm(r['artist'])}||{norm(r['track'])}"
        try:
            result = recco_lookup(session, r["artist"], r["track"])
        except Exception as exc:
            # erreur transitoire (5xx, timeout…) : on NE cache PAS — le titre sera retenté
            streak += 1
            print(f"  ⚠ transitoire ({streak}/5) {r['artist']} — {r['track']}: {exc}")
            if streak >= 5:
                print("⛔ Erreurs serveur en série : ReccoBeats est down ou nous bloque. "
                      "Arrêt propre — relance plus tard via plugin/etl/music/spotify/harvest.sh.")
                break
            time.sleep(15)
            continue
        streak = 0
        cache[k] = result
        done += 1
        found += 1 if result.get("found") else 0
        if done % SAVE_EVERY == 0:
            save_cache(RECCO_CACHE, cache)
            print(f"  [{i}/{len(todo)}] match {100 * found / max(done, 1):.0f}% — "
                  f"{r['artist']} — {r['track']} → {'✓' if result.get('found') else '✗'}")
        time.sleep(0.6)  # rythme adouci après le blocage 530 du 27/07
    save_cache(RECCO_CACHE, cache)
    total_found = sum(1 for v in cache.values() if v.get("found"))
    print(f"\nTerminé : {len(cache)} titres traités, {total_found} avec features "
          f"({100 * total_found / max(len(cache), 1):.0f}%)")


# ---------- MusicBrainz : pays par artiste ----------

ARTIST_KEYS = lambda cache: (k for k in cache if k != "_areas")


def unique_artists(rows):
    out, seen = [], set()
    for r in rows:
        for name in r["artist"].split(", "):
            name = name.strip()
            if name and norm(name) not in seen:
                seen.add(norm(name))
                out.append(name)
    return out


def area_country(session, area_id, areas):
    """Remonte la hiérarchie MB (ville -> région -> pays) jusqu'à un code ISO-3166-1."""
    seen = []
    while area_id and area_id not in seen:
        seen.append(area_id)
        if area_id in areas:
            code = areas[area_id]
            break
        resp = polite_get(session, f"https://musicbrainz.org/ws/2/area/{area_id}",
                          params={"fmt": "json", "inc": "area-rels"})
        time.sleep(1.1)
        d = resp.json()
        codes = d.get("iso-3166-1-codes") or []
        if codes:
            code = codes[0]
            break
        area_id = next(((rel.get("area") or {}).get("id")
                        for rel in d.get("relations", [])
                        if rel.get("type") == "part of" and rel.get("direction") == "backward"),
                       None)
    else:
        code = ""
    for a_id in seen:
        areas[a_id] = code
    return code


def run_country(limit):
    rows = load_library()
    artists = unique_artists(rows)
    cache = load_cache(COUNTRY_CACHE)
    todo = [a for a in artists if norm(a) not in cache]
    print(f"{len(artists)} artistes uniques, {len(artists) - len(todo)} déjà en cache, {len(todo)} à fetcher")
    if limit:
        todo = todo[:limit]

    session = requests.Session()
    session.headers["User-Agent"] = MB_UA
    for i, artist in enumerate(todo, 1):
        try:
            resp = polite_get(session, MB_URL, params={
                "query": f'artist:"{artist}"', "fmt": "json", "limit": 1,
            })
            found = resp.json().get("artists", [])
            a = found[0] if found else {}
            score = a.get("score", 0)
            country = a.get("country", "") if score >= 85 else ""
            area = a.get("area") or {}
            if not country and score >= 85 and area.get("id"):
                # ville/région sans code pays : on remonte la hiérarchie des zones
                country = area_country(session, area["id"], cache.setdefault("_areas", {}))
            cache[norm(artist)] = {
                "artist": artist,
                "country": country,  # toujours un code ISO-2 (ou vide)
                "area": area.get("name", "") if score >= 85 else "",
                "score": score,
            }
        except Exception as exc:
            print(f"  ⚠ {artist}: {exc}")
            cache[norm(artist)] = {"artist": artist, "country": "", "area": "", "error": str(exc)}
        if i % SAVE_EVERY == 0 or i == len(todo):
            save_cache(COUNTRY_CACHE, cache)
            e = cache[norm(artist)]
            print(f"  [{i}/{len(todo)}] {artist} → {e.get('country') or '?'} ({e.get('area', '')})")
        time.sleep(1.1)  # rate limit MusicBrainz : 1 req/s
    save_cache(COUNTRY_CACHE, cache)
    n_art = sum(1 for _ in ARTIST_KEYS(cache))
    with_c = sum(1 for k in ARTIST_KEYS(cache) if cache[k].get("country"))
    print(f"\nTerminé : {n_art} artistes, {with_c} avec pays ({100 * with_c / max(n_art, 1):.0f}%)")


# ---------- FreqBlog : audio features complètes par titre (bulk 50) ----------

FREQ_CACHE = DATA_DIR / ".enrich_freq.json"
FREQ_URL = "https://api.freqblog.com"
FREQ_BATCH = 50
FREQ_BUDGET = 14800  # marge sous les 15 000 req/mois du plan
FREQ_KEEP = ["found", "track_name", "artist_name", "isrc", "mbid", "release_date",
             "duration_ms", "bpm", "key", "camelot", "open_key", "mode",
             "time_signature", "energy", "valence", "danceability", "acousticness",
             "instrumentalness", "speechiness", "liveness", "loudness_db",
             "mood", "genre", "is_remix", "feature_source"]


def run_freq(limit):
    load_dotenv(Path(__file__).resolve().parents[4] / ".env")
    key = os.environ["FREQBLOG_API_KEY"]
    rows = load_library()
    cache = load_cache(FREQ_CACHE)
    used = cache.get("_requests_used", 0)
    todo = [r for r in rows if f"{norm(r['artist'])}||{norm(r['track'])}" not in cache]
    print(f"{len(rows)} titres, {len(rows) - len(todo)} déjà en cache, {len(todo)} à fetcher "
          f"(quota déjà consommé : {used})")
    if limit:
        todo = todo[:limit]

    session = requests.Session()
    session.headers.update({"X-Api-Key": key, "User-Agent": "portal6/1.0"})
    found_run = done_run = 0
    for start in range(0, len(todo), FREQ_BATCH):
        batch = todo[start:start + FREQ_BATCH]
        if used + len(batch) > FREQ_BUDGET:
            print(f"⛔ Budget mensuel presque atteint ({used}/{FREQ_BUDGET}) — arrêt propre.")
            break
        body = [{"track": r["track"][:200],
                 "artist": (r["artist"].split(", ")[0] or None)} for r in batch]
        for attempt in (1, 2, 3):
            resp = session.post(f"{FREQ_URL}/bulk", json=body, timeout=120)
            if resp.status_code == 429:
                wait = min(int(resp.headers.get("Retry-After", 30)), 300)
                print(f"  (429 — pause {wait}s…)", flush=True)
                time.sleep(wait)
            elif resp.status_code >= 500:
                time.sleep(10 * attempt)
            else:
                break
        resp.raise_for_status()
        d = resp.json()
        used += d.get("requests_used", len(batch))
        for r, item in zip(batch, d.get("results", [])):
            k = f"{norm(r['artist'])}||{norm(r['track'])}"
            res = item.get("result") or {}
            entry = {f: res.get(f) for f in FREQ_KEEP if f in res}
            entry["found"] = bool(item.get("found"))
            cache[k] = entry
            done_run += 1
            found_run += 1 if entry["found"] else 0
        cache["_requests_used"] = used
        save_cache(FREQ_CACHE, cache)
        print(f"  [{start + len(batch)}/{len(todo)}] match {100 * found_run / max(done_run, 1):.0f}% "
              f"| quota {used}", flush=True)
        time.sleep(0.5)
    n = sum(1 for k in cache if k != "_requests_used")
    f = sum(1 for k, v in cache.items() if k != "_requests_used" and v.get("found"))
    print(f"\nTerminé : {n} titres traités, {f} trouvés ({100 * f / max(n, 1):.0f}%), quota {used}/15000")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lastfm", action="store_true")
    ap.add_argument("--recco", action="store_true")
    ap.add_argument("--country", action="store_true")
    ap.add_argument("--freq", action="store_true")
    ap.add_argument("--freq-retry", action="store_true",
                    help="purge les non-trouvés du cache freq puis re-bulk (après backfill)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not (args.lastfm or args.recco or args.country or args.freq or args.freq_retry):
        ap.error("choisir --lastfm, --recco, --country et/ou --freq")
    if args.lastfm:
        run_lastfm(args.limit)
    if args.recco:
        run_recco(args.limit)
    if args.country:
        run_country(args.limit)
    if args.freq_retry:
        cache = load_cache(FREQ_CACHE)
        misses = [k for k, v in cache.items() if k != "_requests_used" and not v.get("found")]
        for k in misses:
            del cache[k]
        save_cache(FREQ_CACHE, cache)
        print(f"{len(misses)} non-trouvés purgés — re-bulk (le backfill a eu le temps de tourner)")
        run_freq(args.limit)
    elif args.freq:
        run_freq(args.limit)
