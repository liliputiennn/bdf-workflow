# Met à jour le dépôt cloud local (C:\Users\ESSAI\bdf-cloud) avec ton code actuel, puis l'envoie sur GitHub.
# Usage : powershell -File autopilot/cloud/sync_depot.ps1 [-TestEpisode appli-gratuite-argent]
#   -TestEpisode : dans le dépôt cloud SEULEMENT, remet cet épisode à « ecrit » pour tester la fabrication de nuit.
param([string]$Dest = "C:\Users\ESSAI\bdf-public", [string]$TestEpisode = "")
$ErrorActionPreference = "Stop"
$src = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not (Test-Path (Join-Path $Dest ".git"))) { throw "$Dest n'est pas le dépôt cloud (lance d'abord exporter_depot.ps1)" }
$ok = '^(autopilot|src|tools|sfx-src|app|server|episodes-b|tests|miniatures-manuelles|miniatures-ref|public|\.github)/|^(package\.json|package-lock\.json|remotion\.config\.ts|tsconfig\.json|eslint\.config\.mjs|vitest\.config\.ts|firebase\.json|\.firebaserc|\.gitignore|README\.md)$'
# dépôt PUBLIC : jamais d'audio (ta voix), ni idées / planning / anciens épisodes
$files = git -C $src -c core.quotepath=off ls-files | Where-Object { $_ -match $ok -and $_ -notmatch '\.(mp3|wav)$' }
$suspects = $files | Where-Object { $_ -match "client_secret|token(-[\w-]+)?\.json|tiktok_client|(^|/)\.env($|\.(local|secret))|\.pem$|id_rsa" }
if ($suspects) { throw "Fichiers suspects suivis par Git : $($suspects -join ', ')" }
foreach ($f in $files) {
  $from = Join-Path $src $f
  if (-not (Test-Path $from)) { continue }
  $to = Join-Path $Dest $f
  New-Item -ItemType Directory -Force (Split-Path $to) | Out-Null
  Copy-Item $from $to -Force
}
# fichiers du cloud pas encore suivis par Git dans le dépôt principal
foreach ($d in "autopilot\cloud", "server\autopilot.ts", "tools\autopilot-snapshot.ts", "autopilot\episode_action.py", "autopilot\visuels.py") {
  $p = Join-Path $src $d
  if (Test-Path $p) { Copy-Item $p (Join-Path $Dest (Split-Path $d)) -Recurse -Force }
}
# l'état des épisodes (status.json) est ignoré par Git sur le PC, mais le cloud en a besoin pour savoir ce qui est déjà fait
Get-ChildItem (Join-Path $src "episodes-b") -Directory | Where-Object { $_.Name -notlike "_*" } | ForEach-Object {
  $st = Join-Path $_.FullName "status.json"
  if (Test-Path $st) {
    $to = Join-Path $Dest "episodes-b\$($_.Name)\status.json"
    # jamais d'écrasement : une fois dans le cloud, l'état du cloud fait foi
    if ((Test-Path (Split-Path $to)) -and -not (Test-Path $to)) { Copy-Item $st $to }
  }
}
# dans le dépôt cloud, status.json doit être suivi par Git (retire la règle d'exclusion)
$gi = Join-Path $Dest ".gitignore"
(Get-Content $gi) | Where-Object { $_ -ne "episodes-b/**/status.json" } | Set-Content $gi -Encoding utf8
$wf = Join-Path $Dest ".github\workflows"
New-Item -ItemType Directory -Force $wf | Out-Null
Get-ChildItem (Join-Path $PSScriptRoot "github\workflows") -Filter *.yml | Where-Object { $_.Name -ne "mesure.yml" } | Copy-Item -Destination $wf -Force
if ($TestEpisode) {
  $st = Join-Path $Dest "episodes-b\$TestEpisode\status.json"
  $j = Get-Content $st -Raw | ConvertFrom-Json
  $j.etat = "ecrit"; $j.raison = $null; $j.tentatives = 0
  [System.IO.File]::WriteAllText($st, ($j | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
  "Épisode de test remis à « ecrit » (dépôt cloud uniquement) : $TestEpisode"
}
git -C $Dest add -A
git -C $Dest diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git -C $Dest commit -q -m "Synchronisation du code ($(Get-Date -Format s))" }
git -C $Dest push -q origin main
"Dépôt cloud à jour et envoyé."
