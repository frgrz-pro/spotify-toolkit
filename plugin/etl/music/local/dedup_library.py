"""Analyse le CSV produit par scan_library.py (sur la tour Windows) et repère
les doublons dans la bibliothèque locale.

Ne supprime jamais rien automatiquement. Génère :
- data/local_duplicates_report.csv : tous les doublons détectés, classés par
  groupe, avec la piste recommandée à garder (meilleure qualité) marquée.
- data/quarantine_duplicates.ps1 : script PowerShell généré, qui DÉPLACE (ne
  supprime pas) les fichiers candidats à la suppression vers un sous-dossier
  "_a_trier" à côté de chaque fichier. À copier sur la tour Windows, relire,
  puis lancer toi-même. Rien n'est jamais supprimé automatiquement par nous.

Usage: python plugin/etl/music/local/dedup_library.py [--csv data/library_scan.csv]
"""
import argparse
import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "music"

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


WSL_MNT_RE = re.compile(r"^/mnt/([a-z])/(.*)$")


def to_windows_path(path: str) -> str:
    """Convertit un chemin WSL (/mnt/m/...) en chemin Windows (M:\\...) pour le .ps1.
    Laisse inchangé un chemin déjà Windows (scan fait nativement)."""
    m = WSL_MNT_RE.match(path)
    if m:
        return f"{m.group(1).upper()}:\\" + m.group(2).replace("/", "\\")
    return path


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
    n_skipped = 0
    for row in rows:
        key = (normalize(row.get("artist", "")), normalize(row.get("title", "")))
        # Clé faible = faux positifs garantis (fichiers sans tags groupés sur "01", "track2"…).
        # On exige artiste ET titre non vides, et un titre qui n'est pas qu'un numéro.
        if not key[0] or not key[1] or key[1].isdigit():
            n_skipped += 1
            continue
        groups[key].append(row)
    print(f"{n_skipped} fichiers ignorés (tags trop faibles pour dédoublonner sans risque)")

    dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"{len(dupe_groups)} groupes en doublon ({sum(len(v) for v in dupe_groups.values())} fichiers concernés)")

    report_rows = []
    quarantine_paths = []

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
                quarantine_paths.append(to_windows_path(row.get("path", "")))

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

    # Les chemins sont de la DONNÉE (quarantine_paths.txt), jamais du code inline dans
    # le .ps1 : les apostrophes typographiques et autres caractères spéciaux des noms
    # de fichiers cassent le parsing PowerShell, aucun échappement n'est fiable à 100 %.
    # utf-8-sig (BOM) obligatoire : sans BOM, Windows PowerShell 5.1 lit en ANSI.
    paths_file = DATA_DIR / "quarantine_paths.txt"
    paths_file.write_text("\n".join(quarantine_paths), encoding="utf-8-sig")

    ps1_path = DATA_DIR / "quarantine_duplicates.ps1"
    ps1_path.write_text(
        "\n".join([
            "# Script généré par dedup_library.py — à relire avant exécution.",
            "# Lit quarantine_paths.txt (même dossier) et DÉPLACE chaque fichier À PLAT dans",
            "# le dossier de quarantaine unique <disque>:\\_a_trier\\ (pas de sous-dossiers ;",
            "# collisions de noms suffixées ~2, ~3…). Rien n'est jamais supprimé.",
            "# Rattrape les fichiers déjà quarantainés par les versions précédentes du script",
            "# (_a_trier adjacents ou arborescence miroir), puis supprime les dossiers vides.",
            "$ErrorActionPreference = 'Stop'",
            "$list = Join-Path $PSScriptRoot 'quarantine_paths.txt'",
            "$moved = 0",
            "$already = 0",
            "$missing = 0",
            "$central = $null",
            "foreach ($orig in (Get-Content -LiteralPath $list -Encoding UTF8)) {",
            "    if (-not $orig.Trim()) { continue }",
            "    $qualifier = Split-Path -Path $orig -Qualifier             # ex: M:",
            "    $central = Join-Path $qualifier '_a_trier'",
            "    $rel = $orig.Substring($qualifier.Length + 1)               # chemin sans 'M:\\'",
            "    $leaf = Split-Path -Path $orig -Leaf",
            "    $candidates = @(",
            "        $orig,                                                                              # encore à sa place",
            "        (Join-Path (Join-Path (Split-Path -Path $orig -Parent) '_a_trier') $leaf),          # v1 : _a_trier adjacent",
            "        (Join-Path $central $rel),                                                          # v2 : miroir centralisé",
            "        (Join-Path $central $leaf)                                                          # déjà à plat",
            "    )",
            "    $src = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1",
            "    if (-not $src) { Write-Warning \"introuvable: $orig\"; $missing++; continue }",
            "    New-Item -ItemType Directory -Force -Path $central | Out-Null",
            "    $dst = Join-Path $central $leaf",
            "    if ($src -eq $dst) { $already++; continue }                # déjà en place",
            "    if (Test-Path -LiteralPath $dst) {",
            "        $base = [IO.Path]::GetFileNameWithoutExtension($leaf); $ext = [IO.Path]::GetExtension($leaf)",
            "        $i = 2",
            "        while (Test-Path -LiteralPath $dst) { $dst = Join-Path $central \"$base~$i$ext\"; $i++ }",
            "    }",
            "    Move-Item -LiteralPath $src -Destination $dst -Force",
            "    $moved++",
            "}",
            "if ($central) {",
            "    Write-Host 'Nettoyage des dossiers vides...'",
            "    if (Test-Path -LiteralPath $central) {",
            "        Get-ChildItem -LiteralPath $central -Recurse -Directory | Sort-Object { $_.FullName.Length } -Descending |",
            "            Where-Object { -not (Get-ChildItem -LiteralPath $_.FullName -Force) } | Remove-Item -Force",
            "    }",
            "    $qualifier = Split-Path -Path $central -Qualifier",
            "    Get-ChildItem -Path \"$qualifier\\\" -Recurse -Directory -Filter '_a_trier' -ErrorAction SilentlyContinue |",
            "        Where-Object { $_.FullName -ne $central -and -not (Get-ChildItem -LiteralPath $_.FullName -Recurse -File) } |",
            "        Remove-Item -Recurse -Force",
            "    Write-Host \"$moved fichiers déplacés dans $central (+$already déjà en place), $missing introuvables.\"",
            "}",
        ]),
        encoding="utf-8-sig",
    )
    n_candidates = len(quarantine_paths)
    print(f"Script de quarantaine ({n_candidates} fichiers à déplacer): {ps1_path}")
    print("\n-> Copie ce .ps1 sur la tour Windows, relis-le, puis lance-le toi-même depuis PowerShell.")
    print("   Rien n'est supprimé : les fichiers vont dans un dossier _a_trier que tu vides ensuite à la main.")


if __name__ == "__main__":
    main()
