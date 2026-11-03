# Prépare un dépôt Git LOCAL propre pour le cloud (rien n'est envoyé nulle part).
# Contenu : uniquement les fichiers suivis par Git dans section3-motion/pixel-faits (donc sans secrets, états, vidéos, node_modules)
#           + le workflow de mesure + la voix d'un épisode de test (nécessaire au rendu de mesure).
# Usage : powershell -File autopilot/cloud/exporter_depot.ps1 [-Dest C:\Users\ESSAI\bdf-cloud]
param([string]$Dest = "C:\Users\ESSAI\bdf-cloud", [string]$Episode = "appli-gratuite-argent")
$ErrorActionPreference = "Stop"
$src = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (Test-Path $Dest) { throw "$Dest existe déjà : choisis un autre -Dest ou supprime-le toi-même." }

$files = git -C $src -c core.quotepath=off ls-files
# garde-fou : aucun fichier qui ressemble à un secret ne part dans le dépôt
$suspects = $files | Where-Object { $_ -match "client_secret|token\.json|tiktok_client|(^|/)\.env($|\.(local|secret))|\.pem$|id_rsa" }
if ($suspects) { throw "Fichiers suspects suivis par Git : $($suspects -join ', ')" }

foreach ($f in $files) {
  $from = Join-Path $src $f
  if (-not (Test-Path $from)) { continue }   # fichier supprimé dans le dossier de travail
  $to = Join-Path $Dest $f
  New-Item -ItemType Directory -Force (Split-Path $to) | Out-Null
  Copy-Item $from $to
}
$wf = Join-Path $Dest ".github\workflows"
New-Item -ItemType Directory -Force $wf | Out-Null
Copy-Item (Join-Path $PSScriptRoot "github\workflows\*.yml") $wf
$voice = Join-Path $src "episodes-b\$Episode\voice.wav"
if (Test-Path $voice) { Copy-Item $voice (Join-Path $Dest "episodes-b\$Episode\voice.wav") }

git -C $Dest init -q -b main
git -C $Dest add -A
git -C $Dest add -f "episodes-b/$Episode/voice.wav" 2>$null   # ignorée par .gitignore, forcée ici (fixture de mesure)
git -C $Dest commit -q -m "Dépôt cloud du Bureau des Faits (phase 1 : mesure)"
$n = (git -C $Dest ls-files | Measure-Object).Count
"OK : $n fichiers dans $Dest (local, rien d'envoyé)."
"Étape suivante, par toi, avec ton compte GitHub :"
"  cd $Dest"
"  gh auth login          (si besoin)"
"  gh repo create bureau-des-faits --private --source . --push"
