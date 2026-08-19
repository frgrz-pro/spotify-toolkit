"""Analyse le CSV produit par scan_library.py (sur la tour Windows) et repère
les doublons dans la bibliothèque locale.

Ne supprime jamais rien automatiquement. Génère :
- data/local_duplicates_report.csv : tous les doublons détectés, classés par
  groupe, avec la piste recommandée à garder (meilleure qualité) marquée.
- data/quarantine_duplicates.ps1 : script PowerShell généré, qui DÉPLACE (ne
  supprime pas) les fichiers candidats à la suppression vers un sous-dossier
  "_a_trier" à côté de chaque fichier. À copier sur la tour Windows, relire,
  puis lancer toi-même. Rien n'est jamais supprimé automatiquement par nous.

Usage: python scripts/local/dedup_library.py [--csv data/library_scan.csv]
"""
import argparse
import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"

FEAT_RE = re.compile(r"\b(feat\.?|featuring|ft\.?)\b.*", re.IGNORECASE)
PAREN_RE = re.compile(r"[\(\[][^)\]]*[\)\]]")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = FEAT_RE.sub("", s)
    s = PAREN_RE.sub("", s)
    s = NON_ALNUM_RE.sub("", s)
    return s.strip()


def quality_key(row):
    def to_num(v, default=0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default
    return (to_num(row.get("bitrate_kbps")), to_num(row.get("size_bytes")))


def load_rows(csv_path: Path):
    with csv_path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", default=str(DATA_DIR / "library_scan.csv"))
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(
            f"Fichier introuvable: {csv_path}\n"
            "Lance d'abord scan_library.py sur la tour Windows, puis dépose le CSV ici (data/library_scan.csv)."
        )

    rows = load_rows(csv_path)
    print(f"{len(rows)} fichiers chargés depuis {csv_path}")

    groups = defaultdict(list)
    for row in rows:
        key = (normalize(row.get("artist", "")), normalize(row.get("title", "")))
        if key == ("", ""):
            continue  # rien d'exploitable pour dédoublonner
        groups[key].append(row)

    dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"{len(dupe_groups)} groupes en doublon ({sum(len(v) for v in dupe_groups.values())} fichiers concernés)")

    report_rows = []
    ps1_lines = [
        "# Script généré par dedup_library.py — à relire avant exécution.",
        "# Déplace les doublons de moindre qualité vers un sous-dossier _a_trier",
        "# à côté de chaque fichier (rien n'est supprimé).",
        "$ErrorActionPreference = 'Stop'",
        "",
    ]

    for group_id, (key, items) in enumerate(sorted(dupe_groups.items()), 1):
        ranked = sorted(items, key=quality_key, reverse=True)
        for rank, row in enumerate(ranked, 1):
            action = "keep" if rank == 1 else "candidate_removal"
            report_rows.append({
                "group_id": group_id,
                "artist": row.get("artist", ""),
                "title": row.get("title", ""),
                "rank": rank,
                "action": action,
                "path": row.get("path", ""),
                "bitrate_kbps": row.get("bitrate_kbps", ""),
                "size_bytes": row.get("size_bytes", ""),
                "extension": row.get("extension", ""),
            })
            if action == "candidate_removal":
                p = row.get("path", "")
                ps1_lines.append(
                    f'$src = "{p}"; '
                    f'$dst = Join-Path (Split-Path $src) "_a_trier"; '
                    f'New-Item -ItemType Directory -Force -Path $dst | Out-Null; '
                    f'Move-Item -LiteralPath $src -Destination $dst -Force'
                )

    DATA_DIR.mkdir(exist_ok=True)
    report_path = DATA_DIR / "local_duplicates_report.csv"
    with report_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "group_id", "artist", "title", "rank", "action", "path",
            "bitrate_kbps", "size_bytes", "extension",
        ])
        writer.writeheader()
        writer.writerows(report_rows)
    print(f"Rapport: {report_path}")

    ps1_path = DATA_DIR / "quarantine_duplicates.ps1"
    ps1_path.write_text("\n".join(ps1_lines), encoding="utf-8")
    n_candidates = sum(1 for r in report_rows if r["action"] == "candidate_removal")
    print(f"Script de quarantaine ({n_candidates} fichiers à déplacer): {ps1_path}")
    print("\n-> Copie ce .ps1 sur la tour Windows, relis-le, puis lance-le toi-même depuis PowerShell.")
    print("   Rien n'est supprimé : les fichiers vont dans un dossier _a_trier que tu vides ensuite à la main.")


if __name__ == "__main__":
    main()
