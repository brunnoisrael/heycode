# Diagnóstico sem revelar URLs, segredos, nomes de projetos ou conteúdo de respostas.
param(
    [string]$Hostname = '',
    [int]$Port = 8765,
    [switch]$Authenticate
)
$ErrorActionPreference = 'Stop'
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Porta invalida.' }
if ($Hostname -and $Hostname -notmatch '^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$') {
    throw 'Informe somente um hostname DNS, sem protocolo, porta ou caminho.'
}
if ($Authenticate -and -not $Hostname) { throw 'A verificacao autenticada requer -Hostname.' }
function Get-Code($uri, $headers) {
    # Nunca encaminha credenciais a outro destino via redirecionamento.
    try { return [int](Invoke-WebRequest -Uri $uri -Headers $headers -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 8).StatusCode }
    catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }; return 0 }
}
$local = Get-Code "http://127.0.0.1:$Port/health" @{}
Write-Host "Ponte local: $(if ($local -eq 200) { 'OK' } else { 'indisponivel' })"
$task = Get-ScheduledTask -TaskName 'RoomCodeTunnel' -ErrorAction SilentlyContinue
Write-Host "Tarefa do conector: $(if ($task) { $task.State } else { 'nao instalada' }) (estado da tarefa nao comprova conexao)"
if ($Hostname) {
    $remote = "https://$Hostname"
    $publicHealth = Get-Code "$remote/health" @{}
    $unauth = Get-Code "$remote/status" @{}
    Write-Host "Saude externa: $(if ($publicHealth -eq 200) { 'OK' } else { 'indisponivel ou erro' })"
    Write-Host "Controle sem credencial: $(if ($unauth -eq 401) { 'recusado como esperado' } else { 'nao comprovado' })"
    if ($Authenticate) {
        $secret = [Environment]::GetEnvironmentVariable('BRIDGE_CONTROL_SECRET')
        if (-not $secret) { throw 'Defina BRIDGE_CONTROL_SECRET no ambiente para a verificacao autenticada.' }
        $auth = Get-Code "$remote/status" @{ 'x-secret' = $secret }
        Write-Host "Controle autenticado externo: $(if ($auth -eq 200) { 'OK' } else { 'indisponivel ou recusado' })"
    }
} else {
    Write-Host 'Saude externa: nao verificada (informe -Hostname).'
}
Write-Host 'Alexa/Echo: nao verificado por este diagnostico; teste pela skill no dispositivo autorizado.'
