# Roteiro do tunel nomeado do cloudflared (URL estavel). Nunca burla login: passos interativos so imprimem o comando.
# -DryRun imprime o roteiro sem executar nada. Sem -DryRun, executa apenas os passos nao interativos
# (create, route dns, config.yml) e PAUSA no login para o dono fazer.
param(
    [string]$Hostname = "ponte.exemplo.com",
    [string]$TunnelName = "roomcode",
    [int]$Port = $(if ($env:BRIDGE_PORT) { [int]$env:BRIDGE_PORT } else { 8765 }),
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
$cfDir = Join-Path $HOME ".cloudflared"
$cfg = Join-Path $cfDir "config.yml"
if ($DryRun) { Write-Host "[DryRun] nada sera executado; abaixo o roteiro." }
if ((-not (Test-Path $cf)) -and -not $DryRun) { throw "cloudflared nao encontrado. Instale: winget install --id Cloudflare.cloudflared -e" }

function Step($n, $title, $cmd, $interactive) {
    Write-Host ""
    Write-Host "== Passo $n : $title" -ForegroundColor Cyan
    Write-Host "   > $cmd"
    if ($interactive) { Write-Host "   (exige SEU login/privilegio; execute voce mesmo)" -ForegroundColor Yellow }
}

Step 1 "Login na conta Cloudflare (abre o navegador, escolha o dominio)" "cloudflared tunnel login" $true
if (-not $DryRun -and -not (Test-Path (Join-Path $cfDir "cert.pem"))) {
    Write-Host "PAUSA: cert.pem nao encontrado. Rode o comando acima, conclua o login e execute este script de novo." -ForegroundColor Yellow
    return
}
Step 2 "Criar o tunel" "cloudflared tunnel create $TunnelName" $false
Step 3 "Apontar o DNS" "cloudflared tunnel route dns $TunnelName $Hostname" $false
$yml = @"
tunnel: $TunnelName
credentials-file: $cfDir\<ID-DO-TUNEL>.json
ingress:
  - hostname: $Hostname
    service: http://127.0.0.1:$Port
  - service: http_status:404
"@
Write-Host ""
Write-Host "== Passo 4 : config.yml em $cfg (troque <ID-DO-TUNEL> pelo UUID impresso no passo 2)" -ForegroundColor Cyan
Write-Host $yml
Step 5 "Instalar como servico do Windows (terminal de administrador)" "cloudflared service install" $true
Step 6 "Testar" "curl https://$Hostname/health" $false
Write-Host ""
Write-Host "Depois: BRIDGE_URL na Lambda = https://$Hostname (sem barra final)."

if ($DryRun) { return }
& $cf tunnel create $TunnelName
& $cf tunnel route dns $TunnelName $Hostname
$id = (& $cf tunnel list --name $TunnelName -o json | ConvertFrom-Json | Select-Object -First 1).id
if ($id) {
    $yml = $yml.Replace("<ID-DO-TUNEL>", $id)
    if (Test-Path $cfg) { Copy-Item $cfg "$cfg.bak" -Force }
    Set-Content -Path $cfg -Value $yml -Encoding ascii
    Write-Host "config.yml gravado em $cfg."
}
Write-Host "PAUSA: rode o passo 5 em um terminal de administrador (nao sera feito aqui)." -ForegroundColor Yellow
