# Sobe a ponte (uvicorn) em 127.0.0.1:8765. Gera/completa o .env: BRIDGE_SECRET (agente),
# BRIDGE_CONTROL_SECRET (controle, so na Lambda) e BRIDGE_PIN, tudo via CSPRNG.
# -DryRun so informa o que faria (nunca escreve .env, nunca sobe o servidor, nunca imprime segredos).
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"

function New-Hex($nBytes) {
    $bytes = New-Object byte[] $nBytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes); $rng.Dispose()
    return (($bytes | ForEach-Object { $_.ToString("x2") }) -join "")
}
function New-Pin {
    # 4 digitos sem vies: rejeita UInt16 >= 60000 (multiplo de 10000)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $b = New-Object byte[] 2
    do { $rng.GetBytes($b); $v = [BitConverter]::ToUInt16($b, 0) } while ($v -ge 60000)
    $rng.Dispose()
    return ("{0:D4}" -f ($v % 10000))
}

if ($DryRun) { Write-Host "[DryRun] nada sera alterado nem iniciado." }

if (-not (Test-Path $envFile)) {
    if ($DryRun) {
        Write-Host "[DryRun] criaria .env com BRIDGE_SECRET (48 hex), BRIDGE_CONTROL_SECRET (48 hex) e BRIDGE_PIN (4 digitos), via RandomNumberGenerator."
    } else {
        Set-Content -Path $envFile -Encoding ascii -Value @(
            "BRIDGE_SECRET=$(New-Hex 24)", "BRIDGE_CONTROL_SECRET=$(New-Hex 24)", "BRIDGE_PIN=$(New-Pin)")
        Write-Host "Criado $envFile (BRIDGE_SECRET, BRIDGE_CONTROL_SECRET e BRIDGE_PIN gerados)."
    }
} elseif (-not (@(Get-Content $envFile) | Where-Object { $_ -match '^\s*BRIDGE_CONTROL_SECRET\s*=' })) {
    if ($DryRun) {
        Write-Host "[DryRun] .env existe sem BRIDGE_CONTROL_SECRET: acrescentaria somente essa linha (48 hex), sem tocar no resto."
    } else {
        $text = Get-Content $envFile -Raw
        $sep = if ($text.Length -gt 0 -and -not $text.EndsWith("`n")) { "`r`n" } else { "" }
        Add-Content -Path $envFile -Value ($sep + "BRIDGE_CONTROL_SECRET=$(New-Hex 24)`r`n") -NoNewline -Encoding ascii
        Write-Host "Acrescentado BRIDGE_CONTROL_SECRET ao .env. Configure o mesmo valor na Lambda da skill."
    }
} elseif ($DryRun) {
    Write-Host "[DryRun] .env ja completo; nada a gerar."
}

if ($DryRun) {
    Write-Host "[DryRun] subiria: python -m uvicorn server:app --host 127.0.0.1 --port <BRIDGE_PORT ou 8765>"
    return
}

foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$' -and $line -notmatch '^\s*#') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim('"')
    }
}

$port = if ($env:BRIDGE_PORT) { $env:BRIDGE_PORT } else { "8765" }
Set-Location (Join-Path $root "bridge")
python -m uvicorn server:app --host 127.0.0.1 --port $port
