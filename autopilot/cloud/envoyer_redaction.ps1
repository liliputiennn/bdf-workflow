# Envoie au cloud les épisodes que ton Claude vient d'écrire (état « ecrit ») : copie leurs fichiers texte dans le dépôt cloud
# public (C:\Users\ESSAI\bdf-public) puis pousse sur GitHub. Le cloud les fabriquera la nuit suivante, PC éteint.
# Usage : powershell -File autopilot/cloud/envoyer_redaction.ps1
param([string]$Dest = "C:\Users\ESSAI\bdf-public")
$ErrorActionPreference = "Stop"
$src = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not (Test-Path (Join-Path $Dest ".git"))) { throw "$Dest n'est pas le dépôt cloud." }
$nouveaux = @()
Get-ChildItem (Join-Path $src "episodes-b") -Directory | Where-Object { $_.Name -notlike "_*" } | ForEach-Object {
  $st = Join-Path $_.FullName "status.json"
  if (-not (Test-Path $st)) { return }
  if ((Get-Content $st -Raw | ConvertFrom-Json).etat -ne "ecrit") { return }
  $cible = Join-Path $Dest "episodes-b\$($_.Name)"
  if (Test-Path $cible) { return }   # déjà envoyé
  # texte seulement : jamais d'audio, de vidéo ni de cache dans un dépôt public
  robocopy $_.FullName $cible /E /XD cache /XF *.wav *.mp3 *.mp4 *.lock *.log *.err /NFL /NDL /NJH /NJS /NP | Out-Null
  $nouveaux += $_.Name
}
if ($nouveaux.Count -eq 0) { "Rien de nouveau à envoyer (aucun épisode « ecrit » absent du cloud)."; exit 0 }
"Épisodes envoyés au cloud :"; $nouveaux | ForEach-Object { "  - $_" }
git -C $Dest add -A episodes-b
git -C $Dest -c user.name=Azur -c user.email=noreply@users.noreply.github.com commit -q -m "Rédaction : $($nouveaux.Count) épisode(s) ($(Get-Date -Format s))"
git -C $Dest push -q origin main
"Envoyé. Le cloud les fabriquera à la prochaine fabrication (voir l'onglet Autopilote)."
