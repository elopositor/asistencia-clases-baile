"""Manda la encuesta del dia a los alumnos que aun no han contestado.

    python scripts/enviar_encuesta.py              -> hoy
    python scripts/enviar_encuesta.py 2026-09-02   -> una fecha concreta
    python scripts/enviar_encuesta.py --todos      -> tambien a quien ya contesto
    python scripts/enviar_encuesta.py --no-abrir   -> genera la pagina sin abrirla

En modo manual (por defecto) no envia nada: escribe un HTML con un boton por
alumno; al pulsarlo se abre WhatsApp con el mensaje ya redactado.
En modo cloud envia de verdad por la API de Meta.
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
    todos = "--todos" in sys.argv
    fecha = db.validar_fecha(args[0]) if args else db.hoy()

    db.inicializar()
    alumnos = db.listar_alumnos(solo_activos=True) if todos else db.sin_responder(fecha)
    if not alumnos:
        print(f"[{fecha}] No hay a quien preguntar: todos han contestado.")
        return

    print(f"[{fecha}] {len(alumnos)} alumnos · modo {'cloud' if whatsapp.cloud_configurada() else 'manual'}")

    if whatsapp.cloud_configurada():
        ok = 0
        for a in alumnos:
            res = whatsapp.enviar_encuesta(a, fecha)
            ok += bool(res.get("ok"))
            print(f"  {'OK ' if res.get('ok') else 'ERR'} {a['nombre']:<25} {res.get('respuesta', '')[:90]}")
        print(f"\nEnviados {ok}/{len(alumnos)}.")
        return

    salida = config.DATA / f"envios-{fecha}.html"
    salida.write_text(_html(alumnos, fecha), encoding="utf-8")
    for a in alumnos:
        db.registrar_envio(a["id"], fecha, "manual", "pendiente", "")
    print(f"\nPagina generada: {salida}")
    print("Pulsa cada boton: se abre WhatsApp con el mensaje escrito, solo tienes que darle a enviar.")
    if "--no-abrir" not in sys.argv:
        webbrowser.open(salida.as_uri())


def _html(alumnos: list[dict], fecha: str) -> str:
    botones = "\n".join(
        f'<a class="b" target="_blank" rel="noopener" '
        f'href="{whatsapp.enlace_wa_me(a["telefono"], whatsapp.mensaje_encuesta(a, fecha))}">'
        f'{a["nombre"]} <small>{a["sexo"]}</small></a>'
        for a in alumnos
    )
    return f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enviar encuesta {fecha}</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#0a0708;color:#efe7d8;margin:0;padding:28px}}
 h1{{color:#e3c169;font-size:20px;letter-spacing:.1em;text-transform:uppercase}}
 p{{color:#a3968a;font-size:14px;line-height:1.6;max-width:620px}}
 .g{{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}}
 .b{{padding:12px 18px;border-radius:999px;text-decoration:none;color:#221806;font-weight:700;
     background:linear-gradient(135deg,#e3c169,#c9a24a)}}
 .b:visited{{background:#2a211c;color:#8d8073}}
 small{{opacity:.6;font-weight:400}}
</style>
<h1>Encuesta del {fecha}</h1>
<p>Pulsa cada nombre: se abre WhatsApp con el mensaje ya escrito y su enlace personal.
Los que ya has pulsado se quedan en gris.</p>
<div class="g">{botones}</div>
<p style="margin-top:26px">Panel de resultados:
<a style="color:#e3c169" href="{config.base_url()}/panel?key={config.ADMIN_KEY}&amp;d={fecha}">{config.base_url()}/panel</a></p>
</html>"""


if __name__ == "__main__":
    main()