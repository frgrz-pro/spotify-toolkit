#!/bin/bash
# État des moissons, fenêtre nettoyée. Usage: ./plugin/etl/music/spotify/progress.sh
clear
cd "$(dirname "$0")/../.." || exit 1
exec .venv/bin/python plugin/etl/music/spotify/progress.py
