# Sobe a ponte (uvicorn) em 127.0.0.1:8765. Gera o .env na primeira execucao.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"

if (-not (Test-Path $envFile)) {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
    $pin = "{0:D4}" -f (Get-Random -Minimum 0 -Maximum 10000)
    Set-Content -Path $envFile -Value @("BRIDGE_SECRET=$secret", "BRIDGE_PIN=$pin") -Encoding ascii
    Write-Host "Criado $envFile (BRIDGE_SECRET e BRIDGE_PIN gerados)."
}

foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$' -and $line -notmatch '^\s*#') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim('"')
    }
}

$port = if ($env:BRIDGE_PORT) { $env:BRIDGE_PORT } else { "8765" }
Set-Location (Join-Path $root "bridge")
python -m uvicorn server:app --host 127.0.0.1 --port $port
