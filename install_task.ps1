# Crée 2 tâches planifiées Windows (utilisateur courant, sans droits admin) :
#   - 09:00 : relevé + résumé quotidien envoyé sur le téléphone
#   - 21:00 : relevé, notification seulement si baisse de prix / signal d'achat
# Si le PC est éteint à l'heure prévue, la tâche s'exécute dès qu'il se rallume.
# Désinstaller : Unregister-ScheduledTask -TaskName "VolsSeoulJapon*" -Confirm:$false

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path (Split-Path -Parent (Get-Command python).Source) "pythonw.exe"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

$jobs = @(
    @{ Name = "VolsSeoulJapon-Matin"; At = "09:00"; Args = "--digest" },
    @{ Name = "VolsSeoulJapon-Soir";  At = "21:00"; Args = "" }
)
foreach ($j in $jobs) {
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$dir\run.py`" $($j.Args)" -WorkingDirectory $dir
    $trigger = New-ScheduledTaskTrigger -Daily -At $j.At
    Register-ScheduledTask -TaskName $j.Name -Action $action -Trigger $trigger -Settings $settings -Description "Tracker prix vols Paris-Seoul-Japon" -Force | Out-Null
    Write-Output "Tache $($j.Name) creee ($($j.At))"
}
