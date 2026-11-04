# Envoie (ou met à jour) tes musiques de fond vers Kaggle, en jeu de données PRIVÉ « bdf-musique ».
# Les pistes ne vont jamais dans le dépôt public (licence Pixabay : pas de redistribution) ; la fabrication cloud les télécharge d'ici.
# Prérequis : comme preparer_datasets.ps1 ($env:KAGGLE_USERNAME et $env:KAGGLE_API_TOKEN définis par toi, `pip install kaggle six`).
# Usage : powershell -File autopilot/cloud/kaggle/envoyer_musique.ps1
$ErrorActionPreference = "Stop"
if (-not $env:KAGGLE_USERNAME) { throw "Définis d'abord `$env:KAGGLE_USERNAME = 'ton-pseudo-kaggle'" }
$scripts = Join-Path (Split-Path (python -m site --user-site)) "Scripts"
$env:Path += ";$scripts"
python -m pip install -q six
if (-not (Get-Command kaggle -ErrorAction SilentlyContinue)) { throw "kaggle introuvable : pip install kaggle" }
$dossier = (Resolve-Path (Join-Path $PSScriptRoot "..\..\musique")).Path
$pistes = Get-ChildItem $dossier -File | Where-Object { $_.Extension -in ".mp3", ".wav", ".m4a", ".ogg", ".flac" }
if ($pistes.Count -lt 1) { throw "Aucune piste dans $dossier : lis LISEZ-MOI.md" }
"$($pistes.Count) piste(s) : " + (($pistes | ForEach-Object { $_.Name }) -join ", ")
$slug = "bdf-musique"
$meta = @{ title = "BDF musique"; id = "$($env:KAGGLE_USERNAME)/$slug"; licenses = @(@{ name = "other" }) } | ConvertTo-Json -Depth 4
$fichier = Join-Path $dossier "dataset-metadata.json"
# UTF-8 SANS BOM (Kaggle ne lit pas le BOM de PowerShell 5.1)
[System.IO.File]::WriteAllText($fichier, $meta, (New-Object System.Text.UTF8Encoding($false)))
try {
  kaggle datasets status "$($env:KAGGLE_USERNAME)/$slug" 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    "Mise à jour du jeu existant ..."
    kaggle datasets version -p $dossier -m "pistes mises à jour" --dir-mode zip
  } else {
    "Création du jeu (privé par défaut) ..."
    kaggle datasets create -p $dossier --dir-mode zip
  }
  if ($LASTEXITCODE -ne 0) { throw "ÉCHEC de l'envoi (code $LASTEXITCODE) : lis le message ci-dessus." }
} finally {
  Remove-Item $fichier -ErrorAction SilentlyContinue
}
"Terminé. Vérifie sur kaggle.com > Your Work > Datasets que « BDF musique » est bien en « Private »."
