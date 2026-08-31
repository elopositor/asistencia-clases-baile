"""Configuracion leida de .env (o de variables de entorno reales)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
WEB = RAIZ / "web"


def _cargar_env() -> None:
    """Mini-parser de .env para no depender de python-dotenv."""
    fichero = RAIZ / ".env"
    if not fichero.exists():
        return
    for linea in fichero.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(clave, valor)


def consola_utf8() -> None:
    """La consola de Windows va en cp1252 y los emojis del resumen la revientan."""
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")


_cargar_env()

# URL publica de la app (la que ven los alumnos en el enlace de WhatsApp).
# publicar.ps1 escribe aqui la direccion del tunel de Cloudflare, que cambia en
# cada arranque; por eso se lee en caliente y no solo al importar el modulo.
FICHERO_URL = DATA / "base_url.txt"
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def base_url() -> str:
    """URL publica actual: la del tunel si hay uno vivo, si no la de .env.

    Se lee con utf-8-sig porque PowerShell y el Bloc de notas escriben BOM: sin
    eso la URL empieza por \\ufeff, no supera el startswith, y los enlaces de
    WhatsApp saldrian apuntando a localhost.
    """
    try:
        url = FICHERO_URL.read_text(encoding="utf-8-sig").strip().strip('"').rstrip("/")
    except (OSError, UnicodeDecodeError):
        return BASE_URL
    return url if url.startswith("http") else BASE_URL

# Clave para entrar al panel de empresa y al alta de alumnos
ADMIN_KEY = os.environ.get("ADMIN_KEY", "cambia-esta-clave")

# Numero de WhatsApp de la empresa que recibe el resumen (formato internacional, sin +)
TELEFONO_EMPRESA = os.environ.get("TELEFONO_EMPRESA", "34600000000")

# manual = genera enlaces wa.me para pulsar; cloud = envia solo por la API de Meta
WA_MODE = os.environ.get("WA_MODE", "manual").lower()
WA_TOKEN = os.environ.get("WA_TOKEN", "")
WA_PHONE_ID = os.environ.get("WA_PHONE_ID", "")
WA_PLANTILLA = os.environ.get("WA_PLANTILLA", "recordatorio_clase")
WA_IDIOMA = os.environ.get("WA_IDIOMA", "es")
WA_VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "onstage-verify")

# Aviso de descompensacion: a partir de cuanta diferencia H/M se marca la clase
UMBRAL_AMBAR = int(os.environ.get("UMBRAL_AMBAR", "2"))
UMBRAL_ROJO = int(os.environ.get("UMBRAL_ROJO", "4"))

DB_PATH = Path(os.environ.get("DB_PATH", DATA / "asistencia.db"))