# Crea las tareas de Windows que hacen funcionar el sistema solo:
#
#   OnStage-Publicar  : mantiene el servidor y el tunel encendidos. Arranca al iniciar
#                       sesion en Windows y se reintenta solo si se cae.
#   OnStage-Preguntar : a las 12:00 de lunes a viernes, pide la asistencia del dia
#   OnStage-Resumen   : a las 18:00 de lunes a viernes, manda el recuento a la empresa
#
# Uso:   .\programar_tareas.ps1           (crea o actualiza; datos reales)
#        .\programar_tareas.ps1 -Demo     (igual, pero con la base de demostracion)
#        .\programar_tareas.ps1 -Quitar   (las borra todas)
#
# Las lanza el Programador de tareas de Windows, asi que no dependen de ninguna
# ventana abierta ni de quien las creo: sobreviven a cerrar sesion y a reiniciar.

param(
    [switch]$Quitar,
    [switch]$Demo,
    [string]$HoraPreguntar = "12:00",
    [string]$HoraResumen   = "18:00"
)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$python = (Get-Command python).Source
$pwsh = (Get-Command powershell).Source

$comunes = @{
    StartWhenAvailable        = $true
    DontStopIfGoingOnBatteries = $true
    AllowStartIfOnBatteries   = $true
}

# --- 1. servidor + tunel siempre encendidos -----------------------------------
$nombre = "OnStage-Publicar"
$existe = Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue
if ($existe) {
    Stop-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
}
if ($Quitar) {
    Write-Host "Borrada $nombre" -ForegroundColor Yellow
} else {
    $argumentos = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$raiz\publicar.ps1`""
    if ($Demo) { $argumentos += " -Demo" }

    $accion = New-ScheduledTaskAction -Execute $pwsh -Argument $argumentos -WorkingDirectory $raiz
    # -User es obligatorio: sin el, -AtLogOn significa "al iniciar sesion cualquier
    # usuario" y registrar eso exige permisos de administrador.
    $disparador = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    # ExecutionTimeLimit 0 = sin limite (por defecto Windows la mataria a las 72 h).
    # Si el tunel se cae, la tarea se reintenta sola hasta 999 veces cada 2 minutos.
    $ajustes = New-ScheduledTaskSettingsSet @comunes -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparador `
        -Settings $ajustes -Description "On Stage - servidor y tunel publico" -ErrorAction Stop | Out-Null
    Write-Host "Creada $nombre - arranca al iniciar sesion y se reintenta sola" -ForegroundColor Green
}

# --- 2. tareas diarias --------------------------------------------------------
$tareas = @(
    @{ Nombre = "OnStage-Preguntar"; Script = "scripts\enviar_encuesta.py"; Hora = $HoraPreguntar },
    @{ Nombre = "OnStage-Resumen";   Script = "scripts\resumen_diario.py";  Hora = $HoraResumen }
)

foreach ($t in $tareas) {
    $existe = Get-ScheduledTask -TaskName $t.Nombre -ErrorAction SilentlyContinue
    if ($existe) { Unregister-ScheduledTask -TaskName $t.Nombre -Confirm:$false }
    if ($Quitar) { Write-Host "Borrada $($t.Nombre)" -ForegroundColor Yellow; continue }

    $accion = New-ScheduledTaskAction -Execute $python `
        -Argument "`"$raiz\$($t.Script)`"" -WorkingDirectory $raiz
    $disparador = New-ScheduledTaskTrigger -Weekly `
        -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $t.Hora
    $ajustes = New-ScheduledTaskSettingsSet @comunes

    Register-ScheduledTask -TaskName $t.Nombre -Action $accion -Trigger $disparador `
        -Settings $ajustes -Description "On Stage - asistencia a clases de baile" | Out-Null
    Write-Host "Creada $($t.Nombre) - lunes a viernes a las $($t.Hora)" -ForegroundColor Green
}

if (-not $Quitar) {
    Write-Host ""
    Write-Host "Arrancar ahora sin esperar :  Start-ScheduledTask OnStage-Publicar" -ForegroundColor Cyan
    Write-Host "Ver los enlaces de hoy     :  .\ver_enlaces.ps1" -ForegroundColor Cyan
    Write-Host "Ver el estado de las tareas:  Get-ScheduledTask OnStage-*" -ForegroundColor Cyan
    Write-Host "Pararlo todo               :  Stop-ScheduledTask OnStage-Publicar" -ForegroundColor Cyan
}
