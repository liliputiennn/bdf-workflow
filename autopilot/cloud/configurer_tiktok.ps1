# Configuration TikTok du cloud, en UNE commande (à lancer une seule fois) :
#   1. ouvre ton navigateur pour que TOI seul te connectes à TikTok et autorises l'application (personne ne peut le faire à ta place) ;
#   2. envoie les deux fichiers d'identifiants vers les secrets GitHub (le contenu ne s'affiche jamais) ;
#   3. lance un essai à blanc de la publication cloud.
# Ensuite, chaque Short prêt arrive tout seul dans ta boîte de réception TikTok ; il reste à toucher « Publier » dans l'application
# (TikTok n'autorise pas la publication publique automatique pour un outil réservé à ses propres comptes).
# Usage : powershell -File autopilot/cloud/configurer_tiktok.ps1
$ErrorActionPreference = "Stop"
$racine = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $racine
$gh = "C:\Program Files\GitHub CLI\gh.exe"
$depot = "liliputiennn/bdf-workflow"
$client = Join-Path $racine "autopilot\secrets\tiktok_client.json"
$jeton = Join-Path $racine "autopilot\secrets\tiktok_token.json"
if (-not (Test-Path $client)) { throw "tiktok_client.json introuvable : voir autopilot/tiktok/INSTALLATION.md" }
"1/3  Connexion à TikTok (une fenêtre de navigateur va s'ouvrir)..."
python autopilot/tiktok/auth.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $jeton)) { throw "La connexion TikTok n'a pas abouti." }
"2/3  Envoi des identifiants vers les secrets GitHub (contenu jamais affiché)..."
Get-Content -Raw $client | & $gh secret set TIKTOK_CLIENT --repo $depot
Get-Content -Raw $jeton | & $gh secret set TIKTOK_TOKEN --repo $depot
"3/3  Essai à blanc de la publication cloud..."
& $gh workflow run publication.yml --repo $depot -f a_blanc=true
Start-Sleep 20
$id = & $gh run list --repo $depot --workflow publication.yml --limit 1 --json databaseId --jq ".[0].databaseId"
& $gh run watch $id --repo $depot --exit-status
"Terminé."
