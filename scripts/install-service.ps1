# Instala a ponte como tarefa agendada "RoomCodeBridge" (ao logon, janela oculta, reinicia em falha).
# Idempotente: recria a tarefa se ja existir. -DryRun apenas mostra o que faria.
# -ReplaceExisting encerra o processo que escuta na porta da ponte, SOMENTE se a linha de comando contiver "server:app".
param(
    [string]$TaskName = "RoomCodeBridge",
    [int]$Port = $(if ($env:BRIDGE_PORT) { [int]$env:BRIDGE_PORT } else { 8765 }),
    [switch]$ReplaceExisting,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runScript = Join-Path $PSScriptRoot "run-bridge.ps1"
if ($DryRun) { Write-Host "[DryRun] nada sera alterado." }

$argLine = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runScript`""
$user = "$env:USERDOMAIN\$env:USERNAME"

# Quem escuta na porta?
$listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
foreach ($l in $listeners) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId = $($l.OwningProcess)" -ErrorAction SilentlyContinue
    $cmd = if ($p) { $p.CommandLine } else { "" }
    $isBridge = $cmd -match 'server:app'
    if ($ReplaceExisting -and $isBridge) {
        if ($DryRun) { Write-Host "[DryRun] encerraria PID $($l.OwningProcess) (ponte em :$Port)." }
        else { Stop-Process -Id $l.OwningProcess -Force; Write-Host "Encerrado PID $($l.OwningProcess) (ponte antiga em :$Port)." }
    } elseif ($isBridge) {
        Write-Warning "Ja ha uma ponte (PID $($l.OwningProcess)) na porta $Port. Use -ReplaceExisting para substitui-la, senao a nova disputara a porta."
    } else {
        Write-Warning "Porta $Port ocupada por PID $($l.OwningProcess) que NAO parece a ponte; nao sera tocado."
    }
}

$exists = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($exists) {
    if ($DryRun) { Write-Host "[DryRun] removeria a tarefa existente '$TaskName' para recria-la." }
    else { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
}

if ($DryRun) {
    Write-Host "[DryRun] criaria a tarefa '$TaskName': gatilho ao logon de $user; acao: powershell.exe $argLine; reinicio a cada 1 min (ate 99 vezes); sem limite de tempo; apenas uma instancia."
    Write-Host "[DryRun] depois: Start-ScheduledTask -TaskName $TaskName"
    return
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argLine -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Write-Host "Tarefa '$TaskName' criada. Iniciando..."
Start-ScheduledTask -TaskName $TaskName
Write-Host "Teste: curl http://127.0.0.1:$Port/health"
