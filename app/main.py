"""API y web del sistema de asistencia."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import Body, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, horario, whatsapp

app = FastAPI(title="Asistencia clases de baile", version="1.0.0")
db.inicializar()

app.mount("/static", StaticFiles(directory=config.WEB), name="static")


def _pagina(nombre: str) -> FileResponse:
    return FileResponse(config.WEB / nombre, media_type="text/html; charset=utf-8")


def _exigir_clave(key: str | None, cabecera: str | None) -> None:
    if (key or cabecera) != config.ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Clave de administracion incorrecta")


def _fecha(d: str | None) -> str:
    if not d:
        return db.hoy()
    try:
        return db.validar_fecha(d)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


# --------------------------------------------------------------------------- #
# Paginas
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/panel")


@app.get("/a/{token}", response_class=HTMLResponse, include_in_schema=False)
def pagina_alumno(token: str):
    if not db.alumno_por_token(token):
        return HTMLResponse(
            "<h1 style='font-family:sans-serif;padding:2rem'>Enlace no válido</h1>"
            "<p style='font-family:sans-serif;padding:0 2rem'>Pide a la escuela que te reenvíe el tuyo.</p>",
            status_code=404,
        )
    return _pagina("alumno.html")


@app.get("/panel", response_class=HTMLResponse, include_in_schema=False)
def pagina_panel():
    return _pagina("panel.html")


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def pagina_admin():
    return _pagina("admin.html")


# --------------------------------------------------------------------------- #
# API alumno (autenticada por el token del enlace)
# --------------------------------------------------------------------------- #
@app.get("/api/alumno/{token}")
def api_alumno(token: str, d: str | None = None):
    alumno = db.alumno_por_token(token)
    if not alumno:
        raise HTTPException(status_code=404, detail="Enlace no valido")
    fecha = _fecha(d)
    dia = date.fromisoformat(fecha).isoweekday()
    recuento = {c["id"]: c for c in db.recuento(fecha)}

    clases = []
    for c in horario.clases_del_dia(dia):
        r = recuento.get(c["id"], {})
        clases.append(
            {
                **c,
                "total": r.get("total", 0),
                "falta_sexo": r.get("falta_sexo", ""),
                "estado": r.get("estado", "vacia"),
            }
        )
    return {
        "alumno": {"nombre": alumno["nombre"], "sexo": alumno["sexo"]},
        "fecha": fecha,
        "dia": dia,
        "dia_nombre": horario.NOMBRE_DIA.get(dia, ""),
        "hay_clase": bool(clases),
        "clases": clases,
        "seleccion": db.seleccion_de(alumno["id"], fecha),
        "respondido": db.ha_respondido(alumno["id"], fecha),
        "proximos_dias": _proximos_dias(fecha),
    }


def _proximos_dias(fecha: str, n: int = 7) -> list[dict]:
    base = date.fromisoformat(fecha)
    dias = []
    for i in range(-1, n):
        f = base + timedelta(days=i)
        if f.isoweekday() > 5:
            continue
        dias.append(
            {
                "fecha": f.isoformat(),
                "etiqueta": f"{horario.NOMBRE_DIA[f.isoweekday()][:3]} {f.day}",
                "actual": f.isoformat() == fecha,
            }
        )
    return dias


@app.post("/api/alumno/{token}")
def api_guardar(token: str, cuerpo: dict = Body(...)):
    alumno = db.alumno_por_token(token)
    if not alumno:
        raise HTTPException(status_code=404, detail="Enlace no valido")
    if not alumno["activo"]:
        raise HTTPException(status_code=403, detail="Alumno dado de baja")
    fecha = _fecha(cuerpo.get("fecha"))
    clases = cuerpo.get("clases") or []
    if not isinstance(clases, list):
        raise HTTPException(status_code=400, detail="'clases' debe ser una lista")
    try:
        db.guardar_respuesta(alumno["id"], fecha, [str(c) for c in clases])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return {"ok": True, "fecha": fecha, "guardadas": len(clases)}


# --------------------------------------------------------------------------- #
# API empresa (clave de administracion)
# --------------------------------------------------------------------------- #
@app.get("/api/panel")
def api_panel(d: str | None = None, key: str | None = None, x_admin_key: str | None = Header(None)):
    _exigir_clave(key, x_admin_key)
    fecha = _fecha(d)
    clases = db.recuento(fecha)
    activos = [a for a in db.listar_alumnos(solo_activos=True)]
    pendientes = db.sin_responder(fecha)
    return {
        "fecha": fecha,
        "dia_nombre": horario.NOMBRE_DIA[date.fromisoformat(fecha).isoweekday()],
        "clases": clases,
        "totales": {
            "hombres": sum(c["hombres"] for c in clases),
            "mujeres": sum(c["mujeres"] for c in clases),
            "asistencias": sum(c["total"] for c in clases),
            "alumnos_activos": len(activos),
            "han_contestado": len(activos) - len(pendientes),
            "pendientes": len(pendientes),
        },
        "dias_con_datos": db.dias_con_confirmaciones(fecha),
        "resumen_texto": whatsapp.mensaje_resumen(fecha),
        "enlace_resumen_wa": whatsapp.enlace_wa_me(
            config.TELEFONO_EMPRESA, whatsapp.mensaje_resumen(fecha)
        ),
    }


@app.get("/api/clase/{clase_id}")
def api_clase(clase_id: str, d: str | None = None, key: str | None = None,
              x_admin_key: str | None = Header(None)):
    _exigir_clave(key, x_admin_key)
    if not horario.existe(clase_id):
        raise HTTPException(status_code=404, detail="Clase desconocida")
    fecha = _fecha(d)
    fila = next((c for c in db.recuento(fecha) if c["id"] == clase_id), None)
    falta = fila["falta_sexo"] if fila else ""
    return {
        "clase": horario.POR_ID[clase_id],
        "fecha": fecha,
        "asistentes": db.nominal(fecha, clase_id),
        "sugerencias": db.candidatos_para_equilibrar(fecha, clase_id, falta) if falta else [],
        "falta_sexo": falta,
    }


@app.get("/api/alumnos")
def api_listar(key: str | None = None, x_admin_key: str | None = Header(None)):
    _exigir_clave(key, x_admin_key)
    alumnos = db.listar_alumnos()
    for a in alumnos:
        a["enlace"] = whatsapp.enlace_alumno(a["token"], db.hoy())
    return {"alumnos": alumnos, "total": len(alumnos)}


@app.post("/api/alumnos")
def api_crear(cuerpo: dict = Body(...), key: str | None = None,
              x_admin_key: str | None = Header(None)):
    _exigir_clave(key, x_admin_key)
    try:
        return db.crear_alumno(
            cuerpo.get("nombre", ""), cuerpo.get("telefono", ""),
            cuerpo.get("sexo", ""), cuerpo.get("notas", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@app.patch("/api/alumnos/{alumno_id}")
def api_editar(alumno_id: int, cuerpo: dict = Body(...), key: str | None = None,
               x_admin_key: str | None = Header(None)):
    _exigir_clave(key, x_admin_key)
    try:
        return db.actualizar_alumno(alumno_id, **cuerpo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except LookupError:
        raise HTTPException(status_code=404, detail="Alumno no encontrado") from None


@app.delete("/api/alumnos/{alumno_id}")
def api_borrar(alumno_id: int, key: str | None = None, x_admin_key: str | None = Header(None)):
    _exigir_clave(key, x_admin_key)
    db.borrar_alumno(alumno_id)
    return {"ok": True}


@app.get("/api/envios")
def api_envios(d: str | None = None, solo_pendientes: bool = True, key: str | None = None,
               x_admin_key: str | None = Header(None)):
    """Lista de alumnos con su enlace wa.me listo para pulsar (modo manual)."""
    _exigir_clave(key, x_admin_key)
    fecha = _fecha(d)
    alumnos = db.sin_responder(fecha) if solo_pendientes else db.listar_alumnos(solo_activos=True)
    return {
        "fecha": fecha,
        "modo": "cloud" if whatsapp.cloud_configurada() else "manual",
        "destinatarios": [
            {
                "id": a["id"],
                "nombre": a["nombre"],
                "telefono": a["telefono"],
                "sexo": a["sexo"],
                "enlace_wa": whatsapp.enlace_wa_me(
                    a["telefono"], whatsapp.mensaje_encuesta(a, fecha)
                ),
            }
            for a in alumnos
        ],
    }


@app.post("/api/enviar")
def api_enviar(d: str | None = None, key: str | None = None,
               x_admin_key: str | None = Header(None)):
    """Envio automatico a los pendientes. Solo hace algo real con WA_MODE=cloud."""
    _exigir_clave(key, x_admin_key)
    fecha = _fecha(d)
    if not whatsapp.cloud_configurada():
        raise HTTPException(
            status_code=409,
            detail="WhatsApp Cloud API no configurada. Usa los enlaces del modo manual.",
        )
    resultados = [
        {"alumno": a["nombre"], **whatsapp.enviar_encuesta(a, fecha)}
        for a in db.sin_responder(fecha)
    ]
    return {"fecha": fecha, "enviados": sum(1 for r in resultados if r["ok"]), "detalle": resultados}


@app.get("/api/resumen", response_class=PlainTextResponse)
def api_resumen(d: str | None = None, key: str | None = None,
                x_admin_key: str | None = Header(None)):
    _exigir_clave(key, x_admin_key)
    return whatsapp.mensaje_resumen(_fecha(d))


@app.get("/api/horario")
def api_horario():
    return {"salas": horario.SALAS, "dias": horario.DIAS_LECTIVOS, "clases": horario.CLASES}


# --------------------------------------------------------------------------- #
# Webhook de WhatsApp Cloud API (solo en modo cloud)
# --------------------------------------------------------------------------- #
@app.get("/wa/webhook", include_in_schema=False)
def wa_verificar(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == config.WA_VERIFY_TOKEN:
        return Response(content=p.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token de verificacion incorrecto")


@app.post("/wa/webhook", include_in_schema=False)
async def wa_entrante(request: Request):
    """Si un alumno responde por texto, le devolvemos su enlace personal."""
    datos = await request.json()
    try:
        for entrada in datos.get("entry", []):
            for cambio in entrada.get("changes", []):
                for msg in cambio.get("value", {}).get("messages", []):
                    tel = msg.get("from", "")
                    alumno = next(
                        (a for a in db.listar_alumnos(solo_activos=True) if a["telefono"] == tel), None
                    )
                    if alumno:
                        whatsapp.enviar_texto(tel, whatsapp.mensaje_encuesta(alumno, db.hoy()))
    except Exception:  # el webhook nunca debe devolver error a Meta
        pass
    return {"ok": True}