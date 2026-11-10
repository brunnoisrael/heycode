# Gera novo BRIDGE_SECRET no .env (com backup), reinicia a tarefa e diz o que atualizar.
# -DryRun nao escreve nada nem reinicia, e nunca imprime o segredo.
param([string]$TaskName = "RoomCodeBridge", [switch]$DryRun)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw ".env nao encontrado; rode scripts\run-bridge.ps1 uma vez." }
if ($DryRun) { Write-Host "[DryRun] nada sera alterado." }

$bytes = New-Object byte[] 24
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$new = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
$lines = @(Get-Content $envFile)
$has = $lines | Where-Object { $_ -match '^\s*BRIDGE_SECRET\s*=' }
$backup = "$envFile.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($DryRun) {
    Write-Host "[DryRun] copiaria .env para $backup"
    $verb = if ($has) { "substituiria" } else { "acrescentaria" }
    Write-Host "[DryRun] $verb BRIDGE_SECRET por um novo valor de 48 hex (nao exibido)."
    if ($task) { Write-Host "[DryRun] reiniciaria a tarefa '$TaskName'." }
    else { Write-Host "[DryRun] tarefa '$TaskName' nao existe; reinicie a ponte manualmente." }
} else {
    Copy-Item $envFile $backup
    $out = @(); $done = $false
    foreach ($l in $lines) {
        if ($l -match '^\s*BRIDGE_SECRET\s*=') { $out += "BRIDGE_SECRET=$new"; $done = $true } else { $out += $l }
    }
    if (-not $done) { $out += "BRIDGE_SECRET=$new" }
    Set-Content -Path $envFile -Value $out -Encoding ascii
    Write-Host "Novo BRIDGE_SECRET gravado em .env (backup: $backup). O backup contem o segredo antigo: apague-o depois."
    if ($task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Tarefa '$TaskName' reiniciada."
    } else { Write-Host "Tarefa '$TaskName' nao existe; reinicie a ponte manualmente." }
}
Write-Host ""
Write-Host "Atualize o novo valor (leia do .env) em:"
Write-Host "  1. Lambda da skill: variavel BRIDGE_SECRET (e faca Deploy)"
Write-Host "  2. Hooks/ambiente do Claude Code e do Codex: BRIDGE_SECRET (bearer_token_env_var)"
Write-Host "  3. MCP do Claude: remova o registro antigo (claude mcp remove roomcode) e rode scripts\setup-agents.ps1"
