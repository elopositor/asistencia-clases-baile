# Arranca el servidor. Doble clic no funciona: abre PowerShell aqui y ejecuta  .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env a partir de .env.example - revisa ADMIN_KEY y TELEFONO_EMPRESA." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Panel de empresa : http://localhost:8000/panel" -ForegroundColor Cyan
Write-Host "  Alta de alumnos  : http://localhost:8000/admin" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
