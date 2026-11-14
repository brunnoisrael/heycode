# Registra o MCP "roomcode" no Claude Code e no Codex. Idempotente.
# -DryRun apenas mostra o que faria. Nao altera approval_policy nem sandbox do Codex.
param(
    [string]$BridgeUrl = "http://127.0.0.1:8765",
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$mcpUrl = $BridgeUrl.TrimEnd("/") + "/mcp"
if ($DryRun) { Write-Host "[DryRun] nada sera alterado." }

# segredo: ambiente ou config.env do diretorio do usuario (HEYCODE_HOME ou %APPDATA%\heycode)
$secret = $env:BRIDGE_SECRET
$heycodeHome = if ($env:HEYCODE_HOME) { $env:HEYCODE_HOME } elseif ($env:APPDATA) { Join-Path $env:APPDATA "heycode" } else { Join-Path $HOME ".local\share\heycode" }
$envFile = Join-Path $heycodeHome "config.env"
if (-not $secret -and (Test-Path $envFile)) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*BRIDGE_SECRET\s*=\s*(.*?)\s*$') { $secret = $Matches[1].Trim('"') }
    }
}
if (-not $secret) { Write-Warning "BRIDGE_SECRET nao encontrado (ambiente ou config.env); rode: heycode init"; $secret = "<BRIDGE_SECRET>" }

# (a) Claude Code
$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
    Write-Warning "CLI 'claude' nao encontrada; pulando o registro no Claude."
} else {
    $listed = (& claude mcp list 2>$null | Out-String)
    if ($listed -match '(?m)^\s*roomcode\b') {
        Write-Host "Claude: roomcode ja registrado."
    } elseif ($DryRun) {
        Write-Host "[DryRun] claude mcp add --transport http --scope user roomcode $mcpUrl --header `"Authorization: Bearer ***`""
    } else {
        & claude mcp add --transport http --scope user roomcode $mcpUrl --header "Authorization: Bearer $secret"
        Write-Host "Claude: roomcode registrado."
    }
}

# (b) Codex
$cfg = Join-Path $HOME ".codex\config.toml"
$block = "[mcp_servers.roomcode]`r`nurl = `"$mcpUrl`"`r`nbearer_token_env_var = `"BRIDGE_SECRET`"`r`n"
if (-not (Test-Path $cfg)) {
    Write-Warning "Codex: $cfg nao existe; pulando."
} else {
    $text = Get-Content $cfg -Raw
    if ($text -match '(?m)^\s*\[mcp_servers\.roomcode\]') {
        Write-Host "Codex: roomcode ja presente em $cfg."
    } else {
        $bak = "$cfg.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        if ($DryRun) {
            Write-Host "[DryRun] copiaria $cfg para $bak"
            Write-Host "[DryRun] acrescentaria ao final de ${cfg}:"
            Write-Host $block
        } else {
            Copy-Item $cfg $bak
            $sep = if ($text.Length -gt 0 -and -not $text.EndsWith("`n")) { "`r`n" } else { "" }
            Add-Content -Path $cfg -Value ($sep + "`r`n" + $block) -NoNewline -Encoding utf8
            Write-Host "Codex: roomcode acrescentado (backup em $bak)."
        }
    }
    if ($text -match '(?m)^\s*approval_policy\s*=\s*"never"' -or $text -match 'danger-full-access') {
        Write-Warning "Codex esta com approval_policy=never e/ou sandbox danger-full-access: ele executa sem pedir aprovacao. Este script NAO altera isso."
    }
}
Write-Host "Lembrete: o Codex le o segredo da variavel de ambiente BRIDGE_SECRET; exporte-a antes de abrir o Codex."
