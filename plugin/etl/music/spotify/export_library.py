"""Export the whole library (playlists + Liked Songs) to CSV and a Google Sheet.

Usage: python plugin/etl/music/spotify/export_library.py

Built around the Dev Mode daily quota (429 + Retry-After ~24h):
- every fetched page is persisted in data/.export_cache.json before the next request,
  so any interruption (429, Ctrl-C, crash) loses at most one page;
- hitting the quota is a normal exit, not an error — rerun after the delay to resume;
- the Google Sheet is written at explicit row offsets (never appends), with the pushed
  row count persisted in the cache, so a retry rewrites the same range instead of
  duplicating rows;
- data/library.csv is regenerated from the cache at the end of every run, even partial.

The client is created with retries=0: spotipy's built-in retry sleeps for the full
Retry-After, which on this quota means hanging for ~24h instead of exiting.
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

from spotipy.exceptions import SpotifyException

sys.path.insert(0, str(Path(__file__).parent))
from auth import get_client

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "music"
CACHE_FILE = DATA_DIR / ".export_cache.json"
CSV_FILE = DATA_DIR / "library.csv"
HEADER = ["playlist", "artist", "track", "album"]
LIKED_NAME = "Liked Songs"
TAB_MAX_ROWS = int(os.environ.get("SHEET_TAB_MAX_ROWS", "14000"))
# No fields= filter: a run silently lost 38 playlists because the filtered response
# came back with empty items. Full payloads cost the same quota (requests, not bytes).

request_count = 0


class QuotaExhausted(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after


def api(fn, *args, **kwargs):
    global request_count
    request_count += 1
    try:
        return fn(*args, **kwargs)
    except SpotifyException as exc:
        if exc.http_status == 429:
            headers = getattr(exc, "headers", None) or {}
            raise QuotaExhausted(headers.get("Retry-After")) from exc
        raise


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {"tracks": {}}


def save_cache(cache):
    DATA_DIR.mkdir(exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False))
    tmp.replace(CACHE_FILE)


def fetch_playlists(sp, cache):
    """List owned playlists, one cached page at a time."""
    if "playlists" in cache:
        return cache["playlists"]
    partial = cache.setdefault("playlists_partial", {"offset": 0, "items": []})
    while True:
        page = api(sp.current_user_playlists, limit=50, offset=partial["offset"])
        for pl in page["items"]:
            if not pl or not pl.get("id"):
                continue
            partial["items"].append({
                "id": pl["id"],
                "name": pl.get("name") or pl["id"],
                "owner": (pl.get("owner") or {}).get("id"),
                # missing => unknown count (fetch anyway); 0 => skippable for free
                "total": (pl.get("tracks") or {}).get("total"),
            })
        partial["offset"] += len(page["items"])
        save_cache(cache)
        if not page["next"]:
            break
    cache["playlists"] = [p for p in partial["items"] if p["owner"] == cache["user_id"]]
    del cache["playlists_partial"]
    save_cache(cache)
    return cache["playlists"]


def item_row(item):
    """Parse one playlist/liked item into [artist, track, album], else None."""
    if not item:
        return None
    track = item.get("track") or item.get("item") or item.get("episode")
    if not track or not track.get("name"):
        return None
    artists = ", ".join(a["name"] for a in track.get("artists", []) if a.get("name"))
    album = (track.get("album") or {}).get("name") or ""
    return [artists, track["name"], album]


def parse_page_items(items, context):
    """Parse a page; refuse to continue if real items yield nothing (unknown format).

    Marking a page as consumed while having parsed zero of its tracks is how a whole
    day of quota got wasted once — better to crash with the raw payload in hand.
    """
    rows = [r for r in (item_row(it) for it in items) if r]
    if items and not rows and any(items):
        sample = json.dumps(items[0], ensure_ascii=False)[:600]
        raise RuntimeError(
            f"Format de réponse inattendu pour {context} : {len(items)} items, 0 titres "
            f"parsés. Page NON validée (rien n'est perdu). Premier item brut :\n{sample}"
        )
    return rows


def fetch_playlist_tracks(sp, cache, pl):
    entry = cache["tracks"].setdefault(
        pl["id"], {"name": pl["name"], "offset": 0, "done": False, "rows": []}
    )
    if pl["total"] == 0:
        entry["done"] = True
        save_cache(cache)
        return
    while not entry["done"]:
        page = api(
            sp.playlist_items, pl["id"],
            limit=100, offset=entry["offset"],
            additional_types=["track"],
        )
        entry["rows"].extend(parse_page_items(page["items"], f"playlist « {pl['name']} »"))
        entry["offset"] += len(page["items"])
        if not page["next"]:
            entry["done"] = True
        save_cache(cache)


def fetch_liked(sp, cache):
    entry = cache.setdefault("liked", {"offset": 0, "done": False, "rows": []})
    while not entry["done"]:
        page = api(sp.current_user_saved_tracks, limit=50, offset=entry["offset"])
        entry["total"] = page["total"]
        entry["rows"].extend(parse_page_items(page["items"], "Liked Songs"))
        entry["offset"] += len(page["items"])
        if not page["next"]:
            entry["done"] = True
        save_cache(cache)


def completed_rows(cache):
    """[playlist, artist, track] rows for the contiguous prefix of completed units.

    Playlists are processed strictly in listing order, so completed ones always form
    a prefix — which makes this list append-only across runs, the property the
    offset-based Sheet writes rely on.
    """
    rows = []
    for pl in cache.get("playlists", []):
        entry = cache["tracks"].get(pl["id"])
        if not entry or not entry["done"]:
            return rows
        rows.extend([entry["name"], *r] for r in entry["rows"])
    liked = cache.get("liked")
    if liked and liked["done"]:
        rows.extend([LIKED_NAME, *r] for r in liked["rows"])
    return rows


def all_rows(cache):
    """Everything fetched so far, partial units included (for the CSV snapshot)."""
    rows = []
    for pl in cache.get("playlists", []):
        entry = cache["tracks"].get(pl["id"])
        if entry:
            rows.extend([entry["name"], *r] for r in entry["rows"])
    liked = cache.get("liked")
    if liked:
        rows.extend([LIKED_NAME, *r] for r in liked["rows"])
    return rows


def get_spreadsheet():
    """Open the target spreadsheet, or return None (with a printed reason) to run local-only."""
    sheet_id = os.environ.get("GSHEET_ID")
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not sheet_id or not sa_file:
        print("Google Sheet non configuré (GSHEET_ID / GOOGLE_SERVICE_ACCOUNT_FILE dans .env) : "
              "export local uniquement, le Sheet rattrapera au prochain run.")
        return None
    sa_path = Path(sa_file)
    if not sa_path.is_absolute():
        sa_path = Path(__file__).resolve().parents[4] / sa_path
    if not sa_path.exists():
        print(f"⚠ Clé service account introuvable ({sa_path}) : export local uniquement ce run.")
        return None
    import gspread
    gc = gspread.service_account(filename=str(sa_path))
    try:
        return gc.open_by_key(sheet_id)
    except PermissionError:
        email = json.loads(sa_path.read_text()).get("client_email", "?")
        print(f"⚠ Accès refusé au Sheet : partage-le en Éditeur avec {email}, "
              "puis relance. Export local uniquement ce run.")
        return None


def sheets_call(fn, *args, **kwargs):
    """One retry after a pause when the per-minute Sheets write quota is hit."""
    import gspread
    for attempt in (1, 2):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if attempt == 1 and status == 429:
                print("  (quota Sheets par minute atteint — pause 70s puis retry…)")
                time.sleep(70)
            else:
                raise


def push_to_sheet(sh, cache):
    """Write pending rows into the active tab; rotate to a new tab past TAB_MAX_ROWS.

    Per-tab row counts live in the cache and writes go to explicit offsets, so a
    retry rewrites the same range instead of duplicating. Sorting a FROZEN (full)
    tab is harmless; sorting the active tab mid-run only unsorts it, never loses rows.
    """
    rows = completed_rows(cache)
    tabs = cache.get("sheet_tabs")
    if tabs is None:  # migrate from the single-tab era
        tabs = cache["sheet_tabs"] = [{"title": "Sheet1", "rows": cache.pop("sheet_rows", 0)}]
    while True:
        pushed = sum(t["rows"] for t in tabs)
        new = rows[pushed:]
        if not new:
            return
        active = tabs[-1]
        room = TAB_MAX_ROWS - active["rows"]
        if room <= 0:
            tabs.append({"title": f"Sheet{len(tabs) + 1}", "rows": 0})
            save_cache(cache)
            continue
        import gspread
        try:
            ws = sh.worksheet(active["title"])
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(active["title"], rows=100, cols=len(HEADER))
        chunk = new[:room]
        if active["rows"] == 0:
            sheets_call(ws.update, values=[HEADER], range_name="A1")
        start = active["rows"] + 2  # 1-based, after the header row
        end = start + len(chunk) - 1
        if end > ws.row_count:
            sheets_call(ws.add_rows, end - ws.row_count)
        sheets_call(ws.update, values=chunk, range_name=f"A{start}")
        active["rows"] += len(chunk)
        save_cache(cache)


def write_csv(cache):
    rows = all_rows(cache)
    DATA_DIR.mkdir(exist_ok=True)
    with CSV_FILE.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return len(rows)


def progress(cache):
    expected = sum(pl["total"] or 0 for pl in cache.get("playlists", []))
    fetched = sum(e["offset"] for e in cache["tracks"].values())
    liked = cache.get("liked", {})
    expected += liked.get("total", 0)
    fetched += liked.get("offset", 0)
    return fetched, expected


def main():
    cache = load_cache()
    sp = get_client(retries=0, status_retries=0)
    try:
        sh = get_spreadsheet()
    except Exception as exc:
        print(f"⚠ Google Sheet inaccessible ({type(exc).__name__}: {exc}) — "
              "export local uniquement ce run.")
        sh = None

    complete = False
    try:
        if "user_id" not in cache:
            cache["user_id"] = api(sp.current_user)["id"]
            save_cache(cache)
        playlists = fetch_playlists(sp, cache)
        done_before = sum(1 for p in playlists if cache["tracks"].get(p["id"], {}).get("done"))
        print(f"{len(playlists)} playlists à toi, {done_before} déjà complètes en cache.")

        for i, pl in enumerate(playlists, 1):
            if cache["tracks"].get(pl["id"], {}).get("done"):
                continue
            print(f"  [{i}/{len(playlists)}] {pl['name']} ({pl['total'] if pl['total'] is not None else '?'} titres)…")
            fetch_playlist_tracks(sp, cache, pl)
            if sh:
                try:
                    push_to_sheet(sh, cache)
                except Exception as exc:
                    print(f"⚠ Push Sheets en échec ({exc}) — on continue en local.")
                    sh = None

        print("Playlists complètes. Récupération des Liked Songs…")
        fetch_liked(sp, cache)
        if sh:
            push_to_sheet(sh, cache)
        complete = True
    except SpotifyException as exc:
        if exc.http_status == 403 and "premium" in str(exc).lower():
            print("\n⛔ L'API refuse l'accès : le compte propriétaire de l'app doit être en "
                  "Premium (règle de fév. 2026). Réactive Premium, attends quelques heures, "
                  "puis relance — la progression déjà en cache est conservée.")
        else:
            raise
    except QuotaExhausted as exc:
        fetched, expected = progress(cache)
        pct = f"{100 * fetched / expected:.0f}%" if expected else "?"
        delay = f"{exc.retry_after}s (~{int(exc.retry_after) / 3600:.1f}h)" if exc.retry_after else "inconnu"
        print(f"\nQuota API épuisé après {request_count} requêtes ce run.")
        print(f"Progression : {fetched}/{expected or '?'} titres ({pct}). Retry-After : {delay}.")
        print("Tout est sauvegardé — relance ce script après le délai pour continuer.")

    n = write_csv(cache)
    print(f"\nCSV : {CSV_FILE} ({n} lignes). Sheet : {sum(t['rows'] for t in cache.get('sheet_tabs', []))} lignes poussées.")
    if complete:
        print(f"✅ Export terminé ({request_count} requêtes ce run).")


if __name__ == "__main__":
    main()
