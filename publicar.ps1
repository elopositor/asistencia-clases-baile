# Publica la app en internet, gratis.
#
#   .\publicar.ps1          -> datos reales
#   .\publicar.ps1 -Demo    -> base de demostracion
#   .\publicar.ps1 -EnRed   -> ademas accesible en la red local (lector RFID)
#
# Con NGROK_TOKEN y NGROK_DOMINIO en el .env usa ngrok, y entonces la direccion es
# SIEMPRE LA MISMA: los enlaces que mandes hoy siguen valiendo dentro de un mes.
# Sin esos datos cae en un tunel de Cloudflare, que da una direccion nueva cada vez.
#
# En ambos casos la direccion viva se guarda en data\base_url.txt y la app la lee
# de ahi en caliente. Mantiene servidor y tunel encendidos hasta que pulses Ctrl+C,
# y los levanta solos si se caen.

param(
    [switch]$Demo,
    [switch]$EnRed,          # escuchar tambien en la red local, para el lector RFID
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

function Leer-Env([string]$clave) {
    $m = Select-String -Path ".env" -Pattern "^$clave=(.*)$" -ErrorAction SilentlyContinue
    if ($m) { return $m.Matches.Groups[1].Value.Trim() }
    return ""
}

# ngrok con dominio propio: la direccion es siempre la misma, asi que los enlaces
# que ya has mandado por WhatsApp siguen funcionando manana.
function Abrir-Ngrok([string]$token, [string]$dominio) {
    $ngrok = Join-Path $bin "ngrok.exe"
    if (-not (Test-Path $ngrok)) { throw "No encuentro bin\ngrok.exe" }

    & $ngrok config add-authtoken $token 2>&1 | Out-Null

    Remove-Item $logTunel, "$logTunel.out" -ErrorAction SilentlyContinue
    $p = Start-Process $ngrok `
        -ArgumentList "http", "--domain=$dominio", "--log=stdout", "$Puerto" `
        -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $logTunel -RedirectStandardError "$logTunel.out"

    $url = "https://$dominio"
    foreach ($i in 1..40) {
        Start-Sleep -Milliseconds 750
        if ($p.HasExited) { throw "ngrok se ha cerrado. Mira $logTunel" }
        if (Responde $url) { return @{ Proceso = $p; Url = $url } }
    }
    throw "ngrok no responde en $url. Mira $logTunel"
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
            if ($m.Success) {
                # El subdominio existe en cuanto cloudflared lo anuncia, pero el DNS
                # tarda unos segundos en conocerlo. Sin esta espera, la vigilancia lo
                # toma por caido, abre otro tunel, y se entra en un bucle de
                # direcciones nuevas que nunca llegan a resolver.
                Write-Host "Direccion $($m.Value) - esperando a que resuelva el DNS..." -ForegroundColor DarkGray
                foreach ($j in 1..30) {
                    if (Responde $m.Value) {
                        return @{ Proceso = $p; Url = $m.Value }
                    }
                    Start-Sleep -Seconds 3
                }
                Write-Host "Sigue sin resolver despues de 90 s; la doy por buena igualmente." -ForegroundColor Yellow
                return @{ Proceso = $p; Url = $m.Value }
            }
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
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='cloudflared.exe' OR Name='ngrok.exe'" |
        Where-Object {
            $_.ProcessId -ne $yo -and
            ($_.CommandLine -match "uvicorn\s+app\.main:app" -or
             $_.CommandLine -match "trycloudflare|tunnel --no-autoupdate" -or
             $_.CommandLine -match "ngrok.exe.* http")
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
    # 127.0.0.1 = solo este PC (el tunel ya da el acceso de fuera).
    # 0.0.0.0 = tambien la red local, necesario para que el lector RFID llegue.
    $escucha = if ($EnRed) { "0.0.0.0" } else { "127.0.0.1" }
    Start-Process $python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $escucha, "--port", "$Puerto" `
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
$ngrokToken = Leer-Env "NGROK_TOKEN"
$ngrokDominio = Leer-Env "NGROK_DOMINIO"
$conNgrok = $ngrokToken -and $ngrokDominio

try {
    if ($conNgrok) {
        Write-Host "Abriendo ngrok en $ngrokDominio (direccion fija)..." -ForegroundColor Cyan
        $t = Abrir-Ngrok $ngrokToken $ngrokDominio
    } else {
        Write-Host "Abriendo tunel de Cloudflare (direccion nueva cada vez)..." -ForegroundColor Cyan
        $t = Abrir-Tunel
    }
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
    $abierto = Get-Date
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

        $fallos++
        Write-Host "$(Get-Date -Format 'HH:mm:ss')  el tunel no responde ($fallos)" -ForegroundColor Yellow

        # Mientras cloudflared siga conectado, el tunel esta bien y lo que falla es
        # que el nombre aun no se ha publicado en el DNS (puede tardar 10 minutos).
        # Reabrir en ese momento solo genera otra direccion que empieza de cero, y
        # se entra en un bucle donde ninguna llega a resolver nunca.
        if (-not $tunel.HasExited -and ((Get-Date) - $abierto).TotalMinutes -lt 15) {
            Write-Host "  cloudflared sigue conectado: es el DNS, que tarda. Espero." -ForegroundColor DarkGray
            continue
        }
        if ($fallos -lt 3) { continue }

        Write-Host "Reabriendo el tunel..." -ForegroundColor Yellow
        if (-not $tunel.HasExited) { Stop-Process -Id $tunel.Id -Force -ErrorAction SilentlyContinue }
        try {
            $t = if ($conNgrok) { Abrir-Ngrok $ngrokToken $ngrokDominio } else { Abrir-Tunel }
            $tunel = $t.Proceso
            $publica = $t.Url
            Guardar-Url $publica
            $fallos = 0
            $abierto = Get-Date
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
