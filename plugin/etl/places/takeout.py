"""Parsing des exports Google Takeout « lieux » — partagé par inventory.py et build_db.py.

Deux gisements :
- My Maps : un fichier KML/KMZ par carte. Structure Document > Folder (calque) > Placemark.
  Les points ont toujours des coordonnées ; les tracés (LineString/Polygon) sont comptés
  mais pas ingérés pour l'instant (matière des futurs itinéraires).
- Listes enregistrées (Saved) : un CSV par liste. Colonnes Title/Titre, Note, URL,
  Comment/Commentaire. En général PAS de coordonnées : on tente de les extraire de l'URL
  (formes /search/lat,lon ou @lat,lon), et on capture le CID Google (paire hex 0x...:0x...)
  pour la passe de résolution ultérieure.
"""
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

KML_NS = "{http://www.opengis.net/kml/2.2}"

CID_RE = re.compile(r"(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)")
SEARCH_COORDS_RE = re.compile(r"/search/\+?(-?\d+\.\d+),\s*\+?(-?\d+\.\d+)")
AT_COORDS_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")

GEOMETRIES = ("Point", "LineString", "Polygon", "MultiGeometry")


# --- My Maps (KML / KMZ) ------------------------------------------------------

def load_kml_root(path: Path) -> ET.Element:
    if path.suffix.lower() == ".kmz":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
            return ET.fromstring(z.read(name))
    return ET.parse(path).getroot()


def _text(el, tag):
    child = el.find(KML_NS + tag)
    return child.text.strip() if child is not None and child.text else ""


def _parse_placemark(pm):
    geometry, lat, lon = None, None, None
    for g in GEOMETRIES:
        if pm.find(KML_NS + g) is not None:
            geometry = g
            break
    if geometry == "Point":
        coords = _text(pm.find(KML_NS + "Point"), "coordinates")
        parts = coords.split(",")
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                pass
    extended = {}
    ext = pm.find(KML_NS + "ExtendedData")
    if ext is not None:
        for data in ext.findall(KML_NS + "Data"):
            extended[data.get("name", "")] = _text(data, "value")
    return {
        "name": _text(pm, "name"),
        "description": _text(pm, "description"),
        "geometry": geometry,
        "lat": lat,
        "lon": lon,
        "extended": extended,
    }


def parse_my_map(path: Path) -> dict:
    """Retourne {"name": nom de la carte, "layers": [{"name", "placemarks": [...]}]}.

    Les placemarks directement sous Document (carte sans calque) vont dans un
    calque implicite nommé "".
    """
    root = load_kml_root(path)
    doc = root.find(KML_NS + "Document")
    if doc is None:
        doc = root
    map_name = _text(doc, "name") or path.stem
    layers = []
    rootless = [_parse_placemark(pm) for pm in doc.findall(KML_NS + "Placemark")]
    if rootless:
        layers.append({"name": "", "placemarks": rootless})
    for folder in doc.findall(KML_NS + "Folder"):
        layers.append({
            "name": _text(folder, "name"),
            "placemarks": [_parse_placemark(pm) for pm in folder.findall(KML_NS + "Placemark")],
        })
    return {"name": map_name, "layers": layers}


# --- Listes enregistrées (CSV) ------------------------------------------------

_COLMAP = {
    "title": {"title", "titre"},
    "note": {"note"},
    "url": {"url"},
    "tags": {"tags"},
    "comment": {"comment", "commentaire"},
}


def coords_from_url(url: str):
    for rx in (SEARCH_COORDS_RE, AT_COORDS_RE):
        m = rx.search(url)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


def parse_saved_csv(path: Path) -> list[dict]:
    """Une ligne par lieu : {"title", "note", "url", "comment", "lat", "lon", "cid"}."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = {}
        for raw in reader.fieldnames or []:
            for key, variants in _COLMAP.items():
                if raw.strip().lower() in variants:
                    fields[key] = raw
        rows = []
        for r in reader:
            get = lambda key: (r.get(fields.get(key, ""), "") or "").strip()
            url, title = get("url"), get("title")
            if not title and not url:
                continue  # les exports réels contiennent des lignes entièrement vides
            lat, lon = coords_from_url(url)
            cid = CID_RE.search(url)
            rows.append({
                "title": title,
                "note": get("note"),
                "url": url,
                "tags": get("tags"),
                "comment": get("comment"),
                "lat": lat,
                "lon": lon,
                "cid": cid.group(1) if cid else None,
            })
        return rows


# --- Découverte du vault ------------------------------------------------------

def discover(data_dir: Path) -> dict:
    """Classe les fichiers du vault : {"my_maps": [Path], "saved": [Path], "other": [Path]}."""
    out = {"my_maps": [], "saved": [], "other": []}
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file() or p.name == ".gitkeep":
            continue
        suffix = p.suffix.lower()
        if suffix in (".kml", ".kmz"):
            out["my_maps"].append(p)
        elif suffix == ".csv":
            out["saved"].append(p)
        else:
            out["other"].append(p)
    return out
