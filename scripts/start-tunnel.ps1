# Abre um tunel rapido do Cloudflare para a ponte. A URL https://*.trycloudflare.com aparece no log.
$ErrorActionPreference = "Stop"
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
if (-not (Test-Path $cf)) {
    throw "cloudflared nao encontrado. Instale: winget install --id Cloudflare.cloudflared -e"
}
$port = if ($env:BRIDGE_PORT) { $env:BRIDGE_PORT } else { "8765" }
Write-Host "Procure a linha com https://<algo>.trycloudflare.com abaixo; use-a como BRIDGE_URL na Lambda."
$ErrorActionPreference = "Continue"
& $cf tunnel --url "http://127.0.0.1:$port" 2>&1 | ForEach-Object {
    if ($_ -match 'https://[a-z0-9-]+\.trycloudflare\.com') { Write-Host "URL DO TUNEL: $($Matches[0])" -ForegroundColor Green }
    $_
}
