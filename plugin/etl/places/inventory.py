"""Inventaire du vault data/places/ — forme et volumétrie des exports Takeout AVANT ingestion.

Répond aux questions du Lot A étape 2 : combien de cartes, de calques, de points ?
Quelle part des tracés (LineString/Polygon) ? Combien de lignes dans les listes
enregistrées, et surtout quelle part a des coordonnées exploitables (directes ou via URL)
vs à résoudre (CID seul) vs orpheline (nom seul) ?

Usage : python plugin/etl/places/inventory.py [--data-dir data/places]
"""
import argparse
from pathlib import Path

from takeout import discover, parse_my_map, parse_saved_csv

ROOT = Path(__file__).resolve().parents[3]


def inventory_my_maps(paths):
    total_points = total_tracks = 0
    print(f"\n=== My Maps : {len(paths)} carte(s) ===")
    for p in paths:
        try:
            m = parse_my_map(p)
        except Exception as e:  # fichier corrompu : on le signale sans stopper l'inventaire
            print(f"  !! {p.name} : illisible ({e})")
            continue
        n_points = sum(1 for l in m["layers"] for pm in l["placemarks"] if pm["geometry"] == "Point")
        n_tracks = sum(1 for l in m["layers"] for pm in l["placemarks"] if pm["geometry"] != "Point")
        n_noname = sum(1 for l in m["layers"] for pm in l["placemarks"] if not pm["name"])
        total_points += n_points
        total_tracks += n_tracks
        layers = ", ".join(f"{l['name'] or '(sans calque)'}:{len(l['placemarks'])}" for l in m["layers"])
        print(f"  {m['name']} ({p.name}) — {n_points} points, {n_tracks} tracés"
              + (f", {n_noname} sans nom" if n_noname else ""))
        print(f"    calques : {layers or '(aucun)'}")
    print(f"  TOTAL : {total_points} points, {total_tracks} tracés (non ingérés en Lot A)")


def inventory_saved(paths):
    total = with_coords = with_cid_only = orphan = 0
    print(f"\n=== Listes enregistrées : {len(paths)} liste(s) ===")
    for p in paths:
        try:
            rows = parse_saved_csv(p)
        except Exception as e:
            print(f"  !! {p.name} : illisible ({e})")
            continue
        n_coords = sum(1 for r in rows if r["lat"] is not None)
        n_cid = sum(1 for r in rows if r["lat"] is None and r["cid"])
        n_orphan = len(rows) - n_coords - n_cid
        total += len(rows)
        with_coords += n_coords
        with_cid_only += n_cid
        orphan += n_orphan
        print(f"  {p.stem} — {len(rows)} lieux : {n_coords} avec coordonnées, "
              f"{n_cid} à résoudre (CID), {n_orphan} nom seul")
    if total:
        print(f"  TOTAL : {total} lieux — {with_coords} exploitables directs, "
              f"{with_cid_only} résolubles par CID, {orphan} à géocoder au nom")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(ROOT / "data" / "places"))
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Vault introuvable : {data_dir} — dépose l'export Takeout dedans.")

    found = discover(data_dir)
    if not found["my_maps"] and not found["saved"]:
        raise SystemExit(f"Aucun KML/KMZ/CSV dans {data_dir} — le Takeout n'est pas encore déposé.")

    if found["my_maps"]:
        inventory_my_maps(found["my_maps"])
    if found["saved"]:
        inventory_saved(found["saved"])
    if found["other"]:
        print(f"\n{len(found['other'])} fichier(s) non reconnus : "
              + ", ".join(p.name for p in found["other"][:10]))


if __name__ == "__main__":
    main()
