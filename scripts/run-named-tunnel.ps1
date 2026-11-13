# Executado pela tarefa RoomCodeTunnel; não exibe o conteúdo da configuração nem credenciais.
param([Parameter(Mandatory=$true)][string]$ConfigPath)
$ErrorActionPreference = 'Stop'
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe' }
if (-not (Test-Path -LiteralPath $cf -PathType Leaf)) { throw 'cloudflared nao encontrado.' }
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw 'Configuracao do tunel nao encontrada.' }
& $cf tunnel --config $ConfigPath run
exit $LASTEXITCODE
