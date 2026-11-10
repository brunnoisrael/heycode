# Gera novo segredo no .env (com backup), reinicia a tarefa e diz o que atualizar.
# -Which agent (BRIDGE_SECRET), control (BRIDGE_CONTROL_SECRET) ou both (padrao).
# -DryRun nao escreve nada nem reinicia, e nunca imprime o segredo.
param([string]$TaskName = "RoomCodeBridge", [ValidateSet("agent", "control", "both")][string]$Which = "both", [switch]$DryRun)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw ".env nao encontrado; rode scripts\run-bridge.ps1 uma vez." }
if ($DryRun) { Write-Host "[DryRun] nada sera alterado." }

$names = switch ($Which) { "agent" { @("BRIDGE_SECRET") } "control" { @("BRIDGE_CONTROL_SECRET") } default { @("BRIDGE_SECRET", "BRIDGE_CONTROL_SECRET") } }
$lines = @(Get-Content $envFile)
$backup = "$envFile.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

function New-Hex($nBytes) {
    $bytes = New-Object byte[] $nBytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes); $rng.Dispose()
    return (($bytes | ForEach-Object { $_.ToString("x2") }) -join "")
}

if ($DryRun) {
    Write-Host "[DryRun] copiaria .env para $backup"
    foreach ($n in $names) {
        $has = $lines | Where-Object { $_ -match "^\s*$n\s*=" }
        $verb = if ($has) { "substituiria" } else { "acrescentaria" }
        Write-Host "[DryRun] $verb $n por um novo valor de 48 hex (nao exibido)."
    }
    if ($task) { Write-Host "[DryRun] reiniciaria a tarefa '$TaskName'." }
    else { Write-Host "[DryRun] tarefa '$TaskName' nao existe; reinicie a ponte manualmente." }
} else {
    Copy-Item $envFile $backup
    foreach ($n in $names) {
        $new = New-Hex 24
        $out = @(); $done = $false
        foreach ($l in $lines) {
            if ($l -match "^\s*$n\s*=") { $out += "$n=$new"; $done = $true } else { $out += $l }
        }
        if (-not $done) { $out += "$n=$new" }
        $lines = $out
    }
    Set-Content -Path $envFile -Value $lines -Encoding ascii
    Write-Host "Gravado em .env: $($names -join ', ') (backup: $backup). O backup contem o segredo antigo: apague-o depois."
    if ($task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Tarefa '$TaskName' reiniciada."
    } else { Write-Host "Tarefa '$TaskName' nao existe; reinicie a ponte manualmente." }
}
Write-Host ""
Write-Host "Atualize o novo valor (leia do .env) em:"
if ($names -contains "BRIDGE_CONTROL_SECRET") {
    Write-Host "  - Lambda da skill: variavel BRIDGE_CONTROL_SECRET (e faca Deploy)"
}
if ($names -contains "BRIDGE_SECRET") {
    Write-Host "  - Hooks/ambiente do Claude Code e do Codex: BRIDGE_SECRET (bearer_token_env_var)"
    Write-Host "  - MCP do Claude: remova o registro antigo (claude mcp remove roomcode) e rode scripts\setup-agents.ps1"
}
