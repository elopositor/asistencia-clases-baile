"""Manda al WhatsApp de empresa el recuento de hombres y mujeres por clase.

    python scripts/resumen_diario.py              -> hoy
    python scripts/resumen_diario.py 2026-09-02
    python scripts/resumen_diario.py --solo-texto -> solo imprime el texto
    python scripts/resumen_diario.py --no-abrir   -> imprime tambien el enlace, sin abrir
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db, whatsapp  # noqa: E402


def main() -> None:
    config.consola_utf8()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fecha = db.validar_fecha(args[0]) if args else db.hoy()

    db.inicializar()
    texto = whatsapp.mensaje_resumen(fecha)
    print(texto)

    if "--solo-texto" in sys.argv:
        return

    if whatsapp.cloud_configurada():
        res = whatsapp.enviar_texto(config.TELEFONO_EMPRESA, texto)
        print(f"\n{'Enviado' if res['ok'] else 'ERROR'} al {config.TELEFONO_EMPRESA}: {res.get('respuesta', '')[:200]}")
    else:
        enlace = whatsapp.enlace_wa_me(config.TELEFONO_EMPRESA, texto)
        if "--no-abrir" in sys.argv:
            print(f"\nEnlace para enviarlo al {config.TELEFONO_EMPRESA}:\n{enlace}")
        else:
            print(f"\nAbriendo WhatsApp para enviarlo al {config.TELEFONO_EMPRESA}…")
            webbrowser.open(enlace)


if __name__ == "__main__":
    main()