# Publica la app en internet GRATIS, sin tarjeta ni cuenta, con un tunel de Cloudflare.
#
#   .\publicar.ps1          -> datos reales
#   .\publicar.ps1 -Demo    -> base de demostracion
#
# Mantiene el servidor y el tunel encendidos hasta que pulses Ctrl+C, y si el tunel
# se cae (suspension del PC, corte de red) lo vuelve a abrir solo.
#
# La direccion cambia en cada arranque: por eso se guarda en data\base_url.txt y
# la app la lee de ahi, asi los mensajes que envies hoy llevan la de hoy.

param(
    [switch]$Demo,
    [int]$Puerto = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$bin = Join-Path $PSScriptRoot "bin"
$exe = Join-Path $bin "cloudflared.exe"
$logTunel = Join-Path $PSScriptRoot "data\tunel.log"
$logServidor = Join-Path $PSScriptRoot "data\servidor.log"
$ficheroUrl = Join-Path $PSScriptRoot "data\base_url.txt"

New-Item -ItemType Directory -Force -Path $bin, (Join-Path $PSScriptRoot "data") | Out-Null

# Cuando esto corre como tarea programada no hay ventana donde ver los errores:
# se quedan aqui.
try { Start-Transcript -Path (Join-Path $PSScriptRoot "data\publicar.log") -Force | Out-Null } catch {}

# Ruta absoluta de python: el PATH de una tarea programada no es el de tu terminal.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" }
if (-not (Test-Path $python)) { throw "No encuentro python. Instalalo o corrige la ruta en publicar.ps1" }

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

# --- cloudflared --------------------------------------------------------------
$enPath = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($enPath) {
    $exe = $enPath.Source
} elseif (-not (Test-Path $exe)) {
    Write-Host "Descargando cloudflared (unos 50 MB, solo la primera vez)..." -ForegroundColor Yellow
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    $anterior = $ProgressPreference
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
    $ProgressPreference = $anterior
    Write-Host "Descargado en $exe" -ForegroundColor Green
}

# Abre un tunel nuevo y devuelve @{ Proceso = ...; Url = ... }
function Abrir-Tunel {
    Remove-Item $logTunel, "$logTunel.out" -ErrorAction SilentlyContinue
    # -WindowStyle Hidden y NO -NoNewWindow: como tarea programada no hay consola
    # que heredar y -NoNewWindow hace fallar el Start-Process entero.
    $p = Start-Process $exe `
        -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$Puerto" `
        -PassThru -WindowStyle Hidden -RedirectStandardError $logTunel -RedirectStandardOutput "$logTunel.out"

    foreach ($i in 1..60) {
        Start-Sleep -Milliseconds 700
        # -Raw devuelve $null mientras el fichero esta vacio, y [regex]::Match
        # revienta con null: por eso se comprueba antes de buscar.
        $texto = if (Test-Path $logTunel) { Get-Content $logTunel -Raw -ErrorAction SilentlyContinue } else { $null }
        if ($texto) {
            $m = [regex]::Match($texto, "https://[a-z0-9-]+\.trycloudflare\.com")
            if ($m.Success) { return @{ Proceso = $p; Url = $m.Value } }
        }
        if ($p.HasExited) { throw "cloudflared se ha cerrado. Mira $logTunel" }
    }
    throw "No se ha podido obtener la direccion. Mira $logTunel"
}

# Matar restos de arranques anteriores. Hace falta porque Stop-ScheduledTask (y
# cerrar la ventana a lo bruto) matan este script pero dejan vivos a sus hijos:
# el uvicorn huerfano se queda con el puerto 8000 y el siguiente arranque no puede
# escuchar, muere, y el Programador entra en un bucle de reintentos.
function Limpiar-Restos {
    $yo = $PID
    $muertos = 0
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='cloudflared.exe'" |
        Where-Object {
            $_.ProcessId -ne $yo -and
            ($_.CommandLine -match "uvicorn\s+app\.main:app" -or
             $_.CommandLine -match "trycloudflare|tunnel --no-autoupdate")
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            $muertos++
        }
    if ($muertos) {
        Write-Host "Limpiados $muertos proceso(s) de un arranque anterior." -ForegroundColor DarkGray
        Start-Sleep -Seconds 2   # dar tiempo a que Windows libere el puerto
    }
}

function Arrancar-Servidor {
    Start-Process $python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Puerto" `
        -PassThru -WindowStyle Hidden `
        -RedirectStandardError $logServidor -RedirectStandardOutput "$logServidor.out"
}

function Guardar-Url([string]$u) {
    # Sin BOM: Set-Content -Encoding utf8 lo mete en PS 5.1 y la app descartaria la URL.
    [System.IO.File]::WriteAllText($ficheroUrl, $u, (New-Object System.Text.UTF8Encoding($false)))
}

function Responde([string]$u) {
    try { return (Invoke-WebRequest -Uri "$u/api/horario" -UseBasicParsing -TimeoutSec 20).StatusCode -eq 200 }
    catch { return $false }
}

# --- servidor -----------------------------------------------------------------
$env:DB_PATH = if ($Demo) { "data\demo.db" } else { "data\asistencia.db" }
if ($Demo -and -not (Test-Path "data\demo.db")) { & $python scripts\demo.py | Out-Null }

Remove-Item $ficheroUrl -ErrorAction SilentlyContinue
Limpiar-Restos
Write-Host "Arrancando el servidor en el puerto $Puerto..." -ForegroundColor Cyan
$servidor = Arrancar-Servidor

$tunel = $null
try {
    Write-Host "Abriendo el tunel..." -ForegroundColor Cyan
    $t = Abrir-Tunel
    $tunel = $t.Proceso
    $publica = $t.Url
    Guardar-Url $publica

    $clave = (Select-String -Path ".env" -Pattern "^ADMIN_KEY=(.*)$").Matches.Groups[1].Value

    Write-Host ""
    Write-Host "  ===================================================" -ForegroundColor Green
    Write-Host "   YA ESTA EN INTERNET - coste 0 EUR" -ForegroundColor Green
    Write-Host "  ===================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Panel de empresa:" -ForegroundColor Cyan
    Write-Host "   $publica/panel?key=$clave"
    Write-Host ""
    Write-Host "   Alta de alumnos:" -ForegroundColor Cyan
    Write-Host "   $publica/admin?key=$clave"
    Write-Host ""
    Write-Host "   Se vigila solo: si el tunel se cae, se reabre." -ForegroundColor Yellow
    Write-Host "   Ctrl+C para cerrarlo todo." -ForegroundColor DarkGray

    # --- vigilancia -----------------------------------------------------------
    $fallos = 0
    while ($true) {
        Start-Sleep -Seconds 60

        # Si el servidor se cae, se levanta otro en el mismo puerto y el tunel sigue
        # sirviendo: asi la direccion publica no cambia y los enlaces enviados valen.
        if ($servidor.HasExited) {
            Write-Host "$(Get-Date -Format 'HH:mm:ss')  el servidor se ha caido, lo relanzo" -ForegroundColor Yellow
            $servidor = Arrancar-Servidor
            Start-Sleep -Seconds 4
            if ($servidor.HasExited) { throw "El servidor no arranca. Mira $logServidor" }
            Write-Host "Servidor relanzado; la direccion sigue siendo la misma." -ForegroundColor Green
            continue
        }

        $caido = $tunel.HasExited -or -not (Responde $publica)
        if (-not $caido) { $fallos = 0; continue }

        # Un fallo suelto puede ser un corte de un segundo; dos seguidos, no.
        $fallos++
        Write-Host "$(Get-Date -Format 'HH:mm:ss')  el tunel no responde ($fallos)" -ForegroundColor Yellow
        if ($fallos -lt 2) { continue }

        Write-Host "Reabriendo el tunel..." -ForegroundColor Yellow
        if (-not $tunel.HasExited) { Stop-Process -Id $tunel.Id -Force -ErrorAction SilentlyContinue }
        try {
            $t = Abrir-Tunel
            $tunel = $t.Proceso
            $publica = $t.Url
            Guardar-Url $publica
            $fallos = 0
            Write-Host "Nueva direccion: $publica" -ForegroundColor Green
            Write-Host "OJO: los enlaces enviados con la anterior ya no valen." -ForegroundColor Yellow
        } catch {
            Write-Host "No se ha podido reabrir; se reintenta en un minuto." -ForegroundColor Red
        }
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
    throw
}
finally {
    Write-Host "`nCerrando..." -ForegroundColor DarkGray
    foreach ($p in @($tunel, $servidor)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
    Remove-Item $ficheroUrl -ErrorAction SilentlyContinue
    Write-Host "Servidor y tunel cerrados." -ForegroundColor DarkGray
    try { Stop-Transcript | Out-Null } catch {}
}
