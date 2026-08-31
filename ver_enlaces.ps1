# Muestra los enlaces de hoy y si el sistema esta encendido o no.
#   .\ver_enlaces.ps1          (datos reales)
#   .\ver_enlaces.ps1 -Demo    (base de demostracion)

param([switch]$Demo)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:DB_PATH = if ($Demo) { "data\demo.db" } else { "data\asistencia.db" }

$ficheroUrl = Join-Path $PSScriptRoot "data\base_url.txt"
$clave = (Select-String -Path ".env" -Pattern "^ADMIN_KEY=(.*)$").Matches.Groups[1].Value
$vivo = (Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -WarningAction SilentlyContinue).TcpTestSucceeded

if (-not $vivo) {
    Write-Host ""
    Write-Host "  El sistema esta APAGADO." -ForegroundColor Red
    Write-Host "  Encendelo con:  Start-ScheduledTask OnStage-Publicar" -ForegroundColor Yellow
    Write-Host "  (o, sin tareas programadas, con  .\publicar.ps1 )" -ForegroundColor DarkGray
    Write-Host ""
    return
}

if (-not (Test-Path $ficheroUrl)) {
    Write-Host ""
    Write-Host "  El servidor esta encendido pero todavia sin direccion publica." -ForegroundColor Yellow
    Write-Host "  El tunel tarda unos 10 segundos; vuelve a probar." -ForegroundColor DarkGray
    Write-Host "  Mientras tanto, en este PC:  http://localhost:8000/panel?key=$clave" -ForegroundColor DarkGray
    Write-Host ""
    return
}

$url = (Get-Content $ficheroUrl -Raw).Trim()

# Comprobar que la direccion publica responde de verdad, no solo que exista el fichero
$publicaOk = $false
try {
    $r = Invoke-WebRequest -Uri "$url/api/horario" -UseBasicParsing -TimeoutSec 20
    $publicaOk = ($r.StatusCode -eq 200)
} catch {
    $publicaOk = $false
}

Write-Host ""
if ($publicaOk) {
    Write-Host "  ENCENDIDO y accesible desde internet" -ForegroundColor Green
} else {
    Write-Host "  El servidor va, pero la direccion publica NO responde." -ForegroundColor Red
    Write-Host "  Reinicia el tunel:  Stop-ScheduledTask OnStage-Publicar" -ForegroundColor Yellow
    Write-Host "                      Start-ScheduledTask OnStage-Publicar" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Panel de empresa:" -ForegroundColor Cyan
Write-Host "  $url/panel?key=$clave"
Write-Host ""
Write-Host "  Alta de alumnos:" -ForegroundColor Cyan
Write-Host "  $url/admin?key=$clave"
Write-Host ""

# Enlace personal de cada alumno, por si hay que reenviar alguno a mano
$env:PYTHONIOENCODING = "utf-8"
python -c @"
import sys; sys.path.insert(0, '.')
from app import db, whatsapp
alumnos = db.listar_alumnos(solo_activos=True)
if alumnos:
    print('  Enlaces de los alumnos (%d):' % len(alumnos))
    for a in alumnos[:8]:
        print('   %-22s %s' % (a['nombre'], whatsapp.enlace_alumno(a['token'], db.hoy())))
    if len(alumnos) > 8:
        print('   ... y %d mas. La lista completa esta en /admin' % (len(alumnos) - 8))
else:
    print('  Todavia no hay alumnos dados de alta: entra en /admin')
"@
Write-Host ""
