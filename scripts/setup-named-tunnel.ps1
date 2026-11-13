# Roteiro do tunel nomeado do cloudflared (URL estavel). Nunca burla login: passos interativos so imprimem o comando.
# Por padrao so imprime o roteiro; -Apply executa os passos nao interativos apos revisao.
param(
    [string]$Hostname = "ponte.exemplo.com",
    [string]$TunnelName = "roomcode",
    [int]$Port = $(if ($env:BRIDGE_PORT) { [int]$env:BRIDGE_PORT } else { 8765 }),
    [switch]$DryRun,
    [switch]$Apply
)
$ErrorActionPreference = "Stop"
if ($DryRun -and $Apply) { throw 'Use -DryRun ou -Apply, nao ambos.' }
if ($Apply -and -not $PSBoundParameters.ContainsKey('Hostname')) { throw 'Informe -Hostname explicitamente com -Apply.' }
if ($Hostname -notmatch '^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$') { throw 'Hostname DNS invalido.' }
if ($TunnelName -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$') { throw 'Nome de tunel invalido.' }
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Porta invalida.' }
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
$cfDir = Join-Path $HOME ".cloudflared"
$cfg = Join-Path $cfDir "config.yml"
$preview = $DryRun -or -not $Apply
if ($preview) { Write-Host "[Previa] nada sera executado; abaixo o roteiro." }
if ((-not (Test-Path $cf)) -and -not $preview) { throw "cloudflared nao encontrado. Instale: winget install --id Cloudflare.cloudflared -e" }

function Step($n, $title, $cmd, $interactive) {
    Write-Host ""
    Write-Host "== Passo $n : $title" -ForegroundColor Cyan
    Write-Host "   > $cmd"
    if ($interactive) { Write-Host "   (exige SEU login/privilegio; execute voce mesmo)" -ForegroundColor Yellow }
}

Step 1 "Login na conta Cloudflare (abre o navegador, escolha o dominio)" "cloudflared tunnel login" $true
if (-not $preview -and -not (Test-Path (Join-Path $cfDir "cert.pem"))) {
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
Step 5 "Revisar e instalar tarefa do usuario" "scripts/install-tunnel-task.ps1 -ConfigPath <caminho-config.yml> -Apply" $true
Step 6 "Testar" "curl https://$Hostname/health" $false
Write-Host ""
Write-Host "Depois: BRIDGE_URL na Lambda = https://$Hostname (sem barra final)."

if ($preview) { return }
if (Test-Path -LiteralPath $cfg) { throw 'config.yml ja existe; nao sera substituido. Revise a configuracao existente.' }
$existingJson = & $cf tunnel list --name $TunnelName -o json
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel consultar tuneis existentes; nada foi criado.' }
$existing = @($existingJson | ConvertFrom-Json | Where-Object { $_.name -eq $TunnelName -and -not $_.deleted_at })
if ($existing.Count -gt 0) { throw 'Ja existe tunel com esse nome; revise-o manualmente. Nada foi criado.' }
& $cf tunnel create $TunnelName
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar tunel; DNS e configuracao nao foram alterados.' }
& $cf tunnel route dns $TunnelName $Hostname
if ($LASTEXITCODE -ne 0) { throw 'Tunel criado, mas DNS falhou. Revise o tunel criado na Cloudflare antes de tentar novamente.' }
$id = (& $cf tunnel list --name $TunnelName -o json | ConvertFrom-Json | Select-Object -First 1).id
if ($LASTEXITCODE -ne 0 -or -not $id) { throw 'Tunel e DNS criados, mas nao foi possivel confirmar o ID; configuracao local nao foi escrita.' }
if ($id) {
    $yml = $yml.Replace("<ID-DO-TUNEL>", $id)
    $file = [IO.File]::Open($cfg, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    try { $writer = New-Object IO.StreamWriter($file, [Text.Encoding]::ASCII); $writer.Write($yml); $writer.Flush() }
    finally { if ($writer) { $writer.Dispose() } else { $file.Dispose() } }
    Write-Host "config.yml gravado em $cfg."
}
Write-Host "PAUSA: revise o passo 5 antes de instalar a tarefa." -ForegroundColor Yellow
