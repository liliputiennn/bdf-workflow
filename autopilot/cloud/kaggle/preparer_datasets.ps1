# Envoie UNE FOIS tes modèles de voix vers Kaggle, en jeux de données PRIVÉS (rien n'est public).
# Prérequis : compte Kaggle, `pip install kaggle`, $env:KAGGLE_USERNAME et $env:KAGGLE_API_TOKEN définis par toi (jeton : kaggle.com > Settings > API).
# Aucune copie locale : on ajoute juste un petit fichier dataset-metadata.json dans chaque dossier (le disque C: est presque plein).
# Usage : powershell -File autopilot/cloud/kaggle/preparer_datasets.ps1
$ErrorActionPreference = "Stop"
if (-not $env:KAGGLE_USERNAME) { throw "Définis d'abord `$env:KAGGLE_USERNAME = 'ton-pseudo-kaggle'" }
$scripts = Join-Path (Split-Path (python -m site --user-site)) "Scripts"
$env:Path += ";$scripts"   # kaggle.exe n'est pas dans le PATH après pip install --user
python -m pip install -q six   # dépendance oubliée par kaggle 2.2.5
if (-not (Get-Command kaggle -ErrorAction SilentlyContinue)) { throw "kaggle introuvable : pip install kaggle" }
$ap = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$jeux = @(
  @{ slug = "bdf-voix-modele";  titre = "BDF voix modele";  dossier = "C:\VoiceStudio\qwen3-tts-0.6b-base" },
  @{ slug = "bdf-voix-whisper"; titre = "BDF voix whisper"; dossier = "C:\VoiceStudio\whisper-small" },
  @{ slug = "bdf-voix-ref";     titre = "BDF voix ref";     dossier = (Join-Path $ap "voix") }
)
foreach ($j in $jeux) {
  if (-not (Test-Path $j.dossier)) { throw "dossier introuvable : $($j.dossier)" }
  $meta = @{ title = $j.titre; id = "$($env:KAGGLE_USERNAME)/$($j.slug)"; licenses = @(@{ name = "other" }) } | ConvertTo-Json -Depth 4
  $fichier = Join-Path $j.dossier "dataset-metadata.json"
  # UTF-8 SANS BOM : PowerShell 5.1 en ajoute un avec Set-Content -Encoding utf8, et Kaggle ne sait pas le lire
  [System.IO.File]::WriteAllText($fichier, $meta, (New-Object System.Text.UTF8Encoding($false)))
  "Envoi de $($j.slug) ..."
  try {
    kaggle datasets create -p $j.dossier --dir-mode zip   # privé par défaut
    if ($LASTEXITCODE -ne 0) { throw "ÉCHEC de l'envoi de $($j.slug) (code $LASTEXITCODE) : lis le message ci-dessus." }
  } finally {
    Remove-Item $fichier -ErrorAction SilentlyContinue
  }
}
"Jeux de données présents chez Kaggle :"
kaggle datasets list --mine
"Terminé. Vérifie sur kaggle.com > Your Work > Datasets que les 3 jeux sont bien en « Private »."
