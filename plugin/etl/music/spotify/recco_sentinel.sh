#!/bin/bash
# Attend le retour de l'API ReccoBeats puis lance la moisson. Usage: via harvest.sh/nohup.
cd "$(dirname "$0")/../.." || exit 1
until [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 'https://api.reccobeats.com/v1/track/search?searchText=test')" = "200" ]; do
  echo "$(date '+%H:%M:%S') API indisponible — nouvel essai dans 10 min"
  sleep 600
done
echo "$(date '+%H:%M:%S') API de retour — lancement de la moisson"
exec .venv/bin/python -u plugin/etl/music/spotify/enrich_library.py --recco
