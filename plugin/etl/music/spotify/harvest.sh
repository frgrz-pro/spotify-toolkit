#!/bin/bash
# (Re)lance les moissons d'enrichissement manquantes + le watcher du sheet.
# Idempotent : un process déjà actif n'est pas relancé. Usage: ./plugin/etl/music/spotify/harvest.sh
cd "$(dirname "$0")/../.." || exit 1

start() {  # start <label> <pattern pgrep> <commande...>
  local label="$1" pattern="$2"; shift 2
  if pgrep -f "$pattern" > /dev/null; then
    echo "• $label : déjà en cours"
  else
    nohup "$@" >> "data/$(echo "$label" | tr ' ' '_').log" 2>&1 &
    disown
    echo "• $label : relancé (pid $!)"
  fi
}

start "enrich_freq"    "enrich_library.py --freq"    .venv/bin/python -u plugin/etl/music/spotify/enrich_library.py --freq
start "enrich_country" "enrich_library.py --country" .venv/bin/python -u plugin/etl/music/spotify/enrich_library.py --country
start "build_analysis" "build_analysis.py --watch"   .venv/bin/python -u plugin/etl/music/spotify/build_analysis.py --watch

# reste en veille : ré-affiche l'état à chaque +1pp, ligne gagnante surlignée
exec .venv/bin/python -u plugin/etl/music/spotify/progress.py --follow
