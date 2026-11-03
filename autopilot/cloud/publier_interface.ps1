# Met en ligne la web app « Autopilote » (lit le cloud : état, vidéos, avancement du workflow) sur https://bureau-des-faits.web.app
# À lancer par toi : powershell -File autopilot/cloud/publier_interface.ps1
# Les actions (relancer/écarter) et le journal direct restent réservés à `npm run console` sur le PC.
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
$env:VITE_CLOUD_REPO = "liliputiennn/bdf-workflow"   # l'interface lit l'état et les vidéos sur le dépôt GitHub public
try {
  npm run build:web          # vide dist-console : l'instantané est écrit APRÈS
  # le réseau coupe parfois la connexion à Google : jusqu'à 3 essais
  foreach ($essai in 1..3) {
    firebase deploy --only hosting --project bureau-des-faits
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep 5
  }
  if ($LASTEXITCODE -ne 0) { throw "Déploiement Firebase échoué (code $LASTEXITCODE). Si « credentials are no longer valid » : firebase login --reauth, puis relance ce script." }
} finally {
  Remove-Item Env:VITE_CLOUD_REPO -ErrorAction SilentlyContinue
}
"En ligne : https://bureau-des-faits.web.app (onglet Autopilote)"
