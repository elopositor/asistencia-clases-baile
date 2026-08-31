"""Envio por WhatsApp con dos modos.

manual : no necesita nada de Meta. Genera enlaces wa.me con el mensaje ya escrito;
         se pulsan desde el panel y se abre WhatsApp Web / la app para enviar.
cloud  : WhatsApp Cloud API de Meta. Envio automatico de verdad, requiere numero
         dado de alta en Meta Business y una plantilla aprobada.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote

import httpx

from . import config, db, horario

GRAPH = "https://graph.facebook.com/v21.0"


# --------------------------------------------------------------------------- #
# Textos
# --------------------------------------------------------------------------- #
def enlace_alumno(token: str, fecha: str) -> str:
    return f"{config.base_url()}/a/{token}?d={fecha}"


def _dia_texto(fecha: str) -> str:
    d = date.fromisoformat(fecha)
    return f"{horario.NOMBRE_DIA[d.isoweekday()].lower()} {d.day}/{d.month}"


def mensaje_encuesta(alumno: dict, fecha: str) -> str:
    return (
        f"¡Hola {alumno['nombre'].split()[0]}! 💃🕺\n"
        f"¿A qué clases vienes el {_dia_texto(fecha)}?\n"
        f"Marca tus horas aquí (30 segundos):\n{enlace_alumno(alumno['token'], fecha)}\n\n"
        "Así cuadramos parejas y no falta gente de ningún lado. ¡Gracias!"
    )


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def mensaje_resumen(fecha: str) -> str:
    todas = db.recuento(fecha)
    filas = [c for c in todas if c["total"] > 0]
    cab = f"📋 ON STAGE · {_dia_texto(fecha)}"
    if not todas:
        return f"{cab}\nHoy no hay clases en el horario."
    if not filas:
        pendientes = len(db.sin_responder(fecha))
        return f"{cab}\nSin confirmaciones todavía. Faltan por contestar {_plural(pendientes, 'alumno', 'alumnos')}."

    icono = {"ok": "🟢", "ambar": "🟡", "rojo": "🔴", "vacia": "⚪"}
    lineas = [cab, ""]
    for c in filas:
        sala = f"S{c['sala']}"
        aviso = ""
        if c["estado"] in ("ambar", "rojo") and c["falta_sexo"]:
            que = "chicos" if c["falta_sexo"] == "H" else "chicas"
            aviso = f"  ← faltan {que}"
        lineas.append(
            f"{icono[c['estado']]} {c['hora']} {sala} · {c['etiqueta']}\n"
            f"    {c['hombres']}H / {c['mujeres']}M · total {c['total']}{aviso}"
        )
    total_h = sum(c["hombres"] for c in filas)
    total_m = sum(c["mujeres"] for c in filas)
    lineas += [
        "",
        f"TOTAL DÍA: {total_h}H / {total_m}M ({total_h + total_m} asistencias)",
        f"Sin contestar: {_plural(len(db.sin_responder(fecha)), 'alumno', 'alumnos')}",
        f"Panel: {config.base_url()}/panel?key={config.ADMIN_KEY}&d={fecha}",
    ]
    return "\n".join(lineas)


def enlace_wa_me(telefono: str, texto: str) -> str:
    return f"https://wa.me/{telefono}?text={quote(texto)}"


# --------------------------------------------------------------------------- #
# Envio
# --------------------------------------------------------------------------- #
def cloud_configurada() -> bool:
    return config.WA_MODE == "cloud" and bool(config.WA_TOKEN and config.WA_PHONE_ID)


def enviar_texto(telefono: str, texto: str) -> dict:
    """Envia por Cloud API. Solo funciona dentro de la ventana de 24 h de atencion."""
    if not cloud_configurada():
        return {"ok": False, "modo": "manual", "enlace": enlace_wa_me(telefono, texto)}
    r = httpx.post(
        f"{GRAPH}/{config.WA_PHONE_ID}/messages",
        headers={"Authorization": f"Bearer {config.WA_TOKEN}"},
        json={
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "text",
            "text": {"preview_url": True, "body": texto},
        },
        timeout=20,
    )
    return {"ok": r.is_success, "modo": "cloud", "http": r.status_code, "respuesta": r.text[:400]}


def enviar_plantilla(telefono: str, parametros: list[str]) -> dict:
    """Primer contacto del dia: fuera de la ventana de 24 h hay que usar plantilla.

    Plantilla sugerida (`recordatorio_clase`, categoria UTILITY):
        Hola {{1}}, ¿a qué clases vienes el {{2}}? Marca tus horas aquí: {{3}}
    """
    if not cloud_configurada():
        return {"ok": False, "modo": "manual"}
    r = httpx.post(
        f"{GRAPH}/{config.WA_PHONE_ID}/messages",
        headers={"Authorization": f"Bearer {config.WA_TOKEN}"},
        json={
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "template",
            "template": {
                "name": config.WA_PLANTILLA,
                "language": {"code": config.WA_IDIOMA},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in parametros],
                    }
                ],
            },
        },
        timeout=20,
    )
    return {"ok": r.is_success, "modo": "cloud", "http": r.status_code, "respuesta": r.text[:400]}


def enviar_encuesta(alumno: dict, fecha: str) -> dict:
    """Manda la encuesta del dia a un alumno y lo deja registrado."""
    texto = mensaje_encuesta(alumno, fecha)
    if cloud_configurada():
        res = enviar_plantilla(
            alumno["telefono"],
            [alumno["nombre"].split()[0], _dia_texto(fecha), enlace_alumno(alumno["token"], fecha)],
        )
        db.registrar_envio(
            alumno["id"], fecha, "cloud", "ok" if res["ok"] else "error", str(res.get("respuesta", ""))
        )
        return res
    res = {"ok": False, "modo": "manual", "enlace": enlace_wa_me(alumno["telefono"], texto)}
    db.registrar_envio(alumno["id"], fecha, "manual", "pendiente", res["enlace"])
    return res