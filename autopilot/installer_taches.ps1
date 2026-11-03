# Installe les tâches planifiées du workflow Business (Bureau des Faits).
#   BDF-Fabrique     03:00        run_daily.py fabriquer, puis run_daily.py finaliser
#   BDF-Publication  08:00, 18:00 run_daily.py publier
# Réglages : réveil de l'ordinateur, rattrapage si une exécution est manquée, une seule instance à la fois,
# session de l'utilisateur ouverte (aucun mot de passe stocké), durée maximale bornée.
# Le rédacteur n'a pas de tâche Windows : il tourne dans la tâche planifiée de l'application Claude `bdf-redaction` (02:02).
# Une tâche n'est installée que si sa commande existe. Aucun réglage d'alimentation ou de sécurité n'est modifié.
# Usage : powershell -ExecutionPolicy Bypass -File autopilot\installer_taches.ps1 [-DryRun] [-Python C:\chemin\python.exe]
param(
    [switch]$DryRun,
    [string]$Python
)
$ErrorActionPreference = 'Stop'

$autopilot = Split-Path -Parent $MyInvocation.MyCommand.Path
$racine = Split-Path -Parent $autopilot
if (-not $Python) { $Python = (Get-Command python -ErrorAction Stop).Source }
$pythonw = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $Python }   # pythonw : pas de fenêtre de console pendant les passages
$runDaily = Join-Path $autopilot 'run_daily.py'
$stock = Join-Path $autopilot 'writer\stock.py'
$utilisateur = "$env:USERDOMAIN\$env:USERNAME"

function Nouvelle-Action([string]$exe, [string]$script, [string]$arguments) {
    New-ScheduledTaskAction -Execute $exe -Argument "`"$script`" $arguments" -WorkingDirectory $racine
}

$taches = @(
    @{ Nom = 'BDF-Fabrique'; Heures = @('03:00'); Heures_max = 6
       Requis = @($runDaily, (Join-Path $autopilot 'make_short.py'))
       Actions = @((Nouvelle-Action $pythonw $runDaily 'fabriquer'), (Nouvelle-Action $pythonw $runDaily 'finaliser'))
       Description = 'Bureau des Faits : voix + rendu + contrôle qualité, puis miniatures.' },
    @{ Nom = 'BDF-Publication'; Heures = @('08:00', '18:00'); Heures_max = 1
       Requis = @($runDaily)
       Actions = @((Nouvelle-Action $pythonw $runDaily 'publier'))
       Description = 'Bureau des Faits : publication YouTube des épisodes prêts.' }
)

$installees = @(); $ignorees = @()
foreach ($t in $taches) {
    $manquants = @($t.Requis | Where-Object { -not (Test-Path $_) })
    if ($manquants.Count -gt 0) {
        Write-Host "IGNORÉE  $($t.Nom) : commande absente ($($manquants -join ', '))" -ForegroundColor Yellow
        $ignorees += $t.Nom
        continue
    }
    if ($DryRun) {
        Write-Host "[dry-run] installerait $($t.Nom) à $($t.Heures -join ' et ') (limite $($t.Heures_max) h)"
        $installees += $t.Nom
        continue
    }
    $declencheurs = @($t.Heures | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ })
    $reglages = New-ScheduledTaskSettingsSet `
        -WakeToRun `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours $t.Heures_max) `
        -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)
    $principal = New-ScheduledTaskPrincipal -UserId $utilisateur -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $t.Nom -Description $t.Description -Action $t.Actions `
        -Trigger $declencheurs -Settings $reglages -Principal $principal -Force | Out-Null
    Write-Host "INSTALLÉE $($t.Nom) : $($t.Heures -join ' et ')" -ForegroundColor Green
    $installees += $t.Nom
}

if (-not $DryRun -and $installees.Count -gt 0) {
    Write-Host ''
    foreach ($n in $installees) {
        $i = Get-ScheduledTaskInfo -TaskName $n
        Write-Host ("{0,-16} prochaine exécution : {1}" -f $n, $i.NextRunTime)
    }
    Write-Host ''
    Write-Host 'Vérification : schtasks /query /tn BDF-Fabrique /v /fo list'
}
Write-Host ''
Write-Host 'À vérifier par le propriétaire (non modifié par ce script) : veille désactivée sur secteur, minuteries de réveil autorisées,'
Write-Host 'session Windows ouverte (verrouillée = OK, déconnectée = les tâches attendent la prochaine connexion).'
