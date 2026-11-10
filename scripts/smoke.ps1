# Teste de fumaca: sobe a ponte numa porta livre, com banco temporario e segredo descartavel,
# confere os contratos principais e encerra SOMENTE o processo que iniciou. Nao toca no .env.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("roomcode-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null

$l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
$l.Start(); $port = $l.LocalEndpoint.Port; $l.Stop()

$secret = -join ((1..24) | ForEach-Object { "{0:x2}" -f (Get-Random -Maximum 256) })
$saved = @{}
foreach ($k in "BRIDGE_SECRET", "BRIDGE_PIN", "BRIDGE_DB", "NTFY_TOPIC", "HA_WEBHOOK_URL") { $saved[$k] = [Environment]::GetEnvironmentVariable($k) }
$env:BRIDGE_SECRET = $secret; $env:BRIDGE_PIN = "0000"; $env:BRIDGE_DB = Join-Path $tmp "smoke.db"
$env:NTFY_TOPIC = ""; $env:HA_WEBHOOK_URL = ""

$base = "http://127.0.0.1:$port"
$script:fail = 0
function Check($name, $ok, $detail) {
    if ($ok) { Write-Host "OK    $name" } else { Write-Host "FALHA $name ($detail)" -ForegroundColor Red; $script:fail++ }
}
function Code($method, $path, $headers, $body) {
    try {
        $p = @{ Uri = "$base$path"; Method = $method; UseBasicParsing = $true; TimeoutSec = 10; Headers = $headers }
        if ($body) { $p.Body = $body; $p.ContentType = "application/json" }
        return [int](Invoke-WebRequest @p).StatusCode
    } catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } else { return -1 }
    }
}

$proc = $null
try {
    $proc = Start-Process python -ArgumentList "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "$port" `
        -WorkingDirectory (Join-Path $root "bridge") -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $tmp "out.log") -RedirectStandardError (Join-Path $tmp "err.log")
    Write-Host "Ponte de teste: PID $($proc.Id), porta $port"
    $up = $false
    for ($i = 0; $i -lt 40; $i++) {
        if ($proc.HasExited) { break }
        if ((Code "GET" "/health" @{} $null) -eq 200) { $up = $true; break }
        Start-Sleep -Milliseconds 500
    }
    Check "ponte sobe" $up "ver err.log"
    if ($up) {
        Check "/health 200" ((Code "GET" "/health" @{} $null) -eq 200) ""
        Check "/status sem header 401" ((Code "GET" "/status" @{} $null) -eq 401) ""
        Check "/status com header 200" ((Code "GET" "/status" @{ "x-secret" = $secret } $null) -eq 200) ""
        $mcpBody = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'
        $mcpH = @{ Accept = "application/json, text/event-stream" }
        Check "/mcp sem credencial 401" ((Code "POST" "/mcp" $mcpH $mcpBody) -eq 401) ""
        $mcpH["Authorization"] = "Bearer $secret"
        Check "/mcp com credencial 200" ((Code "POST" "/mcp" $mcpH $mcpBody) -eq 200) ""
        Check "POST /mode 200" ((Code "POST" "/mode" @{ "x-secret" = $secret } '{"mode":"manual"}') -eq 200) ""
    }
} finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
        Write-Host "Encerrado PID $($proc.Id) (iniciado pelo smoke)."
    }
    foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
    Start-Sleep -Milliseconds 500
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
if ($script:fail -eq 0) { Write-Host "SMOKE OK" -ForegroundColor Green; exit 0 }
Write-Host "SMOKE COM $($script:fail) FALHA(S)" -ForegroundColor Red; exit 1
