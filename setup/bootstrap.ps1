# Portal6 — bootstrap côté Windows : WSL2 + Ubuntu + fonction `p6`, puis
# délègue le setup Linux à setup/bootstrap.sh dans Ubuntu.
#
# Usage (depuis la racine du repo) :
#   powershell -ExecutionPolicy Bypass -File setup\bootstrap.ps1
#
# Relançable. Si WSL vient d'être installé : créer l'utilisateur Ubuntu au
# premier lancement, puis relancer ce script.
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$drive = $repo.Substring(0, 1).ToLower()
$wslRepo = "/mnt/$drive" + ($repo.Substring(2) -replace '\\', '/')
Write-Host "Repo : $repo  (WSL : $wslRepo)"

# --- 1. WSL + Ubuntu ---------------------------------------------------------
$distros = (wsl.exe -l -q 2>$null) -replace "`0", ''
if (-not ($distros -match 'Ubuntu')) {
    Write-Host "Ubuntu absent - installation de WSL (admin requis, redemarrage possible)..."
    wsl.exe --install -d Ubuntu
    Write-Host "Quand Ubuntu est pret (utilisateur cree), relance ce script."
    exit 0
}
wsl.exe --set-default Ubuntu | Out-Null
Write-Host "Ubuntu present, defini comme distro par defaut."

# --- 2. Fonction p6 dans le profil PowerShell --------------------------------
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force | Out-Null }
$fn = "function p6 { wsl.exe -d Ubuntu --cd $wslRepo -e zsh -c `"source ~/.venvs/portal6/bin/activate; exec zsh -i`" }"
$content = ""
if (Test-Path $PROFILE) { $content = Get-Content $PROFILE -Raw }
if ($content -notmatch 'function p6') {
    Add-Content $PROFILE $fn
    Write-Host "Fonction p6 ajoutee a $PROFILE"
} else {
    Write-Host "Fonction p6 deja presente dans le profil (non modifiee)."
}

# --- 3. Bootstrap cote Ubuntu ------------------------------------------------
Write-Host "`nLancement du bootstrap Linux dans Ubuntu..."
wsl.exe -d Ubuntu -e bash -c "cd $wslRepo && chmod +x setup/bootstrap.sh && ./setup/bootstrap.sh"

Write-Host "`nTermine. Ouvre un NOUVEAU PowerShell et tape : p6"
Write-Host "(si p6 est introuvable : Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)"
