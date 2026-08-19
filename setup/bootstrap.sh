#!/usr/bin/env bash
# Portal6 — bootstrap d'une nouvelle machine (macOS ou Ubuntu/WSL).
# Idempotent : relançable sans rien casser, ne réinstalle que ce qui manque.
#
# Usage :
#   macOS  : ./setup/bootstrap.sh
#   WSL    : lancé automatiquement par setup/bootstrap.ps1 (ou à la main depuis Ubuntu)
#
# Installe : brew (mac), zsh + oh-my-zsh, python + venv ~/.venvs/portal6,
# dépendances Python du projet, node (task runner npm), alias `portal6`.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$HOME/.venvs/portal6"
OS="$(uname -s)"

log() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# --- 1. Paquets système ------------------------------------------------------
if [ "$OS" = "Darwin" ]; then
  log "macOS détecté"
  if ! command -v brew >/dev/null 2>&1; then
    log "Installation de Homebrew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
  fi
  brew list python >/dev/null 2>&1 || brew install python
  command -v node >/dev/null 2>&1 || brew install node
elif grep -qi ubuntu /etc/os-release 2>/dev/null; then
  log "Ubuntu détecté (WSL ou natif)"
  sudo apt-get update -y
  sudo apt-get install -y zsh git curl build-essential python3 python3-venv python3-pip unzip
  if ! command -v node >/dev/null 2>&1; then
    # brew (linuxbrew) s'il est déjà là, sinon apt suffit pour un task runner
    if command -v brew >/dev/null 2>&1; then brew install node; else sudo apt-get install -y nodejs npm; fi
  fi
else
  echo "OS non géré : $OS (attendu : macOS ou Ubuntu)" >&2
  exit 1
fi

# --- 2. oh-my-zsh ------------------------------------------------------------
if [ ! -d "$HOME/.oh-my-zsh" ]; then
  log "Installation de oh-my-zsh"
  RUNZSH=no sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended || true
fi

# --- 3. Venv Python ----------------------------------------------------------
# Toujours dans le home (jamais dans le repo : un venv sur /mnt/* casse ensurepip sous WSL).
log "Venv Python : $VENV"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -q -r "$REPO/requirements.txt" mutagen openpyxl

# --- 4. Alias portal6 --------------------------------------------------------
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  [ -f "$rc" ] || continue
  if ! grep -q "alias portal6=" "$rc"; then
    echo "alias portal6='cd $REPO && source $VENV/bin/activate'" >> "$rc"
    log "alias portal6 ajouté à $rc"
  fi
done

# --- 5. Vérification ---------------------------------------------------------
log "Vérification"
"$VENV/bin/python" -c "import mutagen, pandas, openpyxl; print('Python + dépendances OK')"
command -v node >/dev/null 2>&1 && echo "node $(node --version) OK"

printf '\nTerminé. Ouvre un nouveau shell puis tape : portal6\n'
