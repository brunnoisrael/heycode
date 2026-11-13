# Registra um conector nomeado já provisionado como tarefa do usuário, sem tocar no DNS ou em credenciais.
param(
    [Parameter(Mandatory=$true)][string]$ConfigPath,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$taskName = 'RoomCodeTunnel'
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe' }
$config = [IO.Path]::GetFullPath($ConfigPath)
$runner = Join-Path $PSScriptRoot 'run-named-tunnel.ps1'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -ConfigPath "{1}"' -f $runner, $config

Write-Host "Tarefa: $taskName; executavel: $cf; configuracao: $config"
Write-Host 'Gatilho: logon deste usuario; janela oculta; reinicio em falha; nenhuma alteracao no DNS.'
if (-not $Apply) {
    Write-Host 'PREVIA: nenhuma alteracao feita. Para instalar, revise a configuracao e use -Apply.'
    exit 0
}
if (-not (Test-Path -LiteralPath $cf -PathType Leaf)) { throw 'cloudflared nao encontrado.' }
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) { throw 'Arquivo de configuracao do tunel nao encontrado.' }
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'Executor do tunel nao encontrado.' }

# Não substitui tarefa preexistente: apenas reutiliza se a ação for exatamente a esperada.
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    $actions = @($existing.Actions)
    if ($actions.Count -ne 1 -or $actions[0].Execute -ne $powershell -or $actions[0].Arguments -ne $arguments) {
        throw 'Ja existe uma tarefa RoomCodeTunnel com outra acao; revise-a manualmente. Nada foi alterado.'
    }
    Write-Host 'Tarefa existente reconhecida; configuracao preservada.'
} else {
    # A validação não exibe o YAML nem o conteúdo dos arquivos de credenciais.
    & $cf tunnel --config $config ingress validate *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Configuracao de ingresso invalida. Revise-a localmente antes de instalar.' }
    $action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory ([IO.Path]::GetDirectoryName($config))
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $settings = New-ScheduledTaskSettingsSet -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
    Write-Host 'Tarefa criada.'
}
$current = Get-ScheduledTask -TaskName $taskName
if ($current.State -ne 'Running') { Start-ScheduledTask -TaskName $taskName; Write-Host 'Inicializacao solicitada.' }
else { Write-Host 'Tarefa ja estava em execucao.' }
Write-Host 'Confira a disponibilidade externa com scripts/diagnose-connection.ps1.'
