#!/bin/bash
# État des moissons, fenêtre nettoyée. Usage: ./scripts/spotify/progress.sh
clear
cd "$(dirname "$0")/../.." || exit 1
exec .venv/bin/python scripts/spotify/progress.py
