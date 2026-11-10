# Remove a tarefa agendada "RoomCodeBridge". Nao encerra processos. -DryRun apenas mostra.
param([string]$TaskName = "RoomCodeBridge", [switch]$DryRun)
$ErrorActionPreference = "Stop"
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $t) { Write-Host "Tarefa '$TaskName' nao existe; nada a fazer."; return }
if ($DryRun) { Write-Host "[DryRun] pararia e removeria a tarefa '$TaskName' (processos ja em execucao nao sao encerrados por este script)."; return }
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Tarefa '$TaskName' removida."
