# Désinstalle les tâches planifiées BDF-Fabrique et BDF-Publication (et elles seules).
# Usage : powershell -ExecutionPolicy Bypass -File autopilot\desinstaller_taches.ps1
$ErrorActionPreference = 'Stop'
foreach ($nom in 'BDF-Fabrique', 'BDF-Publication') {
    $t = Get-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
    if ($t) {
        Stop-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $nom -Confirm:$false
        Write-Host "SUPPRIMÉE $nom" -ForegroundColor Green
    } else {
        Write-Host "absente   $nom"
    }
}
