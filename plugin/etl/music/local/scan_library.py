"""Scan une bibliothèque musicale locale (Windows, hors-ligne) et exporte un CSV.

Fichier 100% autonome : aucune dépendance au reste du projet portal6,
copiable seul sur une machine sans accès internet et sans autre setup.

Dépendance optionnelle : mutagen (lecture des tags ID3/FLAC/MP4/OGG).
- Si présent : artiste, titre, album, album_artist, année, piste, durée, bitrate.
- Si absent : le scan tourne quand même, mais artiste/titre sont devinés depuis
  le nom de fichier (best effort) — installe mutagen pour de meilleurs résultats
  (voir instructions dans le README, section "Installer mutagen hors-ligne").

Usage (Windows, cmd ou PowerShell) :
    python scan_library.py "D:\\Musique" [--out library_scan.csv]
    python scan_library.py "D:\\Musique" "E:\\AutreDossier" --out library_scan.csv

Le CSV produit est à ramener (clé USB) et à déposer dans data/ du projet
portal6, puis à traiter avec plugin/etl/music/local/dedup_library.py.
"""
import argparse
import csv
import sys
from pathlib import Path

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg", ".wma", ".aiff", ".alac"}

try:
    import mutagen
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

FIELDS = [
    "path", "filename", "extension", "size_bytes", "mtime",
    "artist", "title", "album", "album_artist", "year", "track_number",
    "duration_sec", "bitrate_kbps", "sample_rate", "tags_read",
]


def guess_from_filename(stem: str):
    """Best-effort artiste/titre depuis le nom de fichier, sans tags.
    Gère les patterns courants: 'Artiste - Titre', '01 - Artiste - Titre', '01. Titre'.
    """
    parts = stem.split(" - ")
    parts = [p.strip() for p in parts if p.strip()]
    # retire un éventuel numéro de piste en tête ("01", "01.", "track 01")
    if parts and parts[0].replace(".", "").isdigit():
        parts = parts[1:]
    if len(parts) >= 2:
        return parts[0], " - ".join(parts[1:])
    return "", stem


def read_tags(path: Path):
    """Retourne un dict de tags si mutagen est dispo et sait lire le fichier, sinon None."""
    if not HAS_MUTAGEN:
        return None
    try:
        f = mutagen.File(path, easy=True)
    except Exception:
        return None
    if f is None:
        return None

    def first(key):
        val = f.get(key)
        return val[0] if val else ""

    info = getattr(f, "info", None)
    return {
        "artist": first("artist"),
        "title": first("title"),
        "album": first("album"),
        "album_artist": first("albumartist"),
        "year": first("date")[:4] if first("date") else "",
        "track_number": first("tracknumber"),
        "duration_sec": round(info.length, 1) if info and getattr(info, "length", None) else "",
        "bitrate_kbps": round(info.bitrate / 1000) if info and getattr(info, "bitrate", None) else "",
        "sample_rate": getattr(info, "sample_rate", "") if info else "",
    }


def scan_file(path: Path):
    stat = path.stat()
    row = {
        "path": str(path),
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "mtime": int(stat.st_mtime),
        "artist": "", "title": "", "album": "", "album_artist": "",
        "year": "", "track_number": "", "duration_sec": "", "bitrate_kbps": "",
        "sample_rate": "", "tags_read": "no",
    }
    tags = read_tags(path)
    if tags and (tags["artist"] or tags["title"]):
        row.update(tags)
        row["tags_read"] = "yes"
    else:
        artist, title = guess_from_filename(path.stem)
        row["artist"] = row["artist"] or artist
        row["title"] = row["title"] or title
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="+", help="Dossier(s) racine à scanner")
    parser.add_argument("--out", default="library_scan.csv", help="Fichier CSV de sortie")
    args = parser.parse_args()

    print(f"mutagen {'disponible' if HAS_MUTAGEN else 'absent (fallback nom de fichier — tags non lus)'}")

    rows = []
    for root_str in args.roots:
        root = Path(root_str)
        if not root.exists():
            print(f"! Dossier introuvable, ignoré : {root}", file=sys.stderr)
            continue
        print(f"Scan de {root} ...")
        count = 0
        for path in root.rglob("*"):
            if "_a_trier" in path.parts:
                continue  # quarantaine dedup : jamais réindexée
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
                try:
                    rows.append(scan_file(path))
                except Exception as exc:
                    print(f"! Erreur sur {path}: {exc}", file=sys.stderr)
                count += 1
                if count % 500 == 0:
                    print(f"  ... {count} fichiers scannés")
        print(f"  -> {count} fichiers audio trouvés dans {root}")

    out_path = Path(args.out)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    n_tagged = sum(1 for r in rows if r["tags_read"] == "yes")
    print(f"\n{len(rows)} fichiers écrits dans {out_path.resolve()}")
    print(f"({n_tagged} avec tags lus, {len(rows) - n_tagged} devinés depuis le nom de fichier)")


if __name__ == "__main__":
    main()
