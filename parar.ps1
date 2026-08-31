# Para el sistema del todo: la tarea programada y los procesos que deja sueltos.
#   .\parar.ps1
#
# Hace falta porque Stop-ScheduledTask solo mata el script, no a sus hijos
# (el servidor y el tunel se quedarian vivos y ocupando el puerto 8000).

Set-Location $PSScriptRoot

if (Get-ScheduledTask -TaskName "OnStage-Publicar" -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName "OnStage-Publicar" -ErrorAction SilentlyContinue
    Write-Host "Tarea OnStage-Publicar parada." -ForegroundColor DarkGray
    Start-Sleep -Seconds 2
}

$muertos = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='cloudflared.exe' OR Name='powershell.exe'" |
    Where-Object {
        $_.ProcessId -ne $PID -and
        ($_.CommandLine -match "uvicorn\s+app\.main:app" -or
         $_.CommandLine -match "tunnel --no-autoupdate" -or
         $_.CommandLine -match "publicar\.ps1")
    } |
    ForEach-Object {
        Write-Host "  cerrando $($_.Name) PID $($_.ProcessId)" -ForegroundColor DarkGray
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $muertos++
    }

Remove-Item "data\base_url.txt" -ErrorAction SilentlyContinue

Write-Host ""
if ($muertos) { Write-Host "Todo parado ($muertos procesos)." -ForegroundColor Green }
else { Write-Host "No habia nada corriendo." -ForegroundColor Green }
Write-Host "Para volver a encenderlo:  Start-ScheduledTask OnStage-Publicar" -ForegroundColor Cyan
