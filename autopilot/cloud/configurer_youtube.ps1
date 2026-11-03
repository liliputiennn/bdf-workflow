# Configuration YouTube du cloud, en UNE commande (à lancer une seule fois) :
#   1. ouvre ton navigateur pour que TOI seul autorises l'accès à ta chaîne (Google l'exige, personne ne peut le faire à ta place) ;
#   2. envoie les deux fichiers d'identifiants directement vers les secrets GitHub (le contenu ne s'affiche jamais) ;
#   3. lance un essai à blanc de la publication cloud et affiche son résultat.
# Usage : powershell -File autopilot/cloud/configurer_youtube.ps1
$ErrorActionPreference = "Stop"
$racine = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $racine
$gh = "C:\Program Files\GitHub CLI\gh.exe"
$depot = "liliputiennn/bdf-workflow"
$client = Join-Path $racine "autopilot\secrets\client_secret.json"
$jeton = Join-Path $racine "autopilot\secrets\token.json"
if (-not (Test-Path $client)) { throw "client_secret.json introuvable : voir autopilot/publish/INSTALLATION.md" }

"1/3  Connexion à YouTube (une fenêtre de navigateur va s'ouvrir)..."
python autopilot/publish/auth.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $jeton)) { throw "La connexion YouTube n'a pas abouti." }

"2/3  Envoi des identifiants vers les secrets GitHub (contenu jamais affiché)..."
Get-Content -Raw $client | & $gh secret set YT_CLIENT_SECRET --repo $depot
Get-Content -Raw $jeton | & $gh secret set YT_TOKEN --repo $depot

"3/3  Essai à blanc de la publication cloud..."
& $gh workflow run publication.yml --repo $depot -f a_blanc=true
Start-Sleep 20
$id = & $gh run list --repo $depot --workflow publication.yml --limit 1 --json databaseId --jq ".[0].databaseId"
& $gh run watch $id --repo $depot --exit-status
"Terminé : consulte l'onglet Autopilote ou github.com/$depot/actions"
