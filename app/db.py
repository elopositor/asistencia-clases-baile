"""Capa de datos sobre SQLite (stdlib, sin dependencias)."""

from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta

from . import config, horario

ESQUEMA = """
CREATE TABLE IF NOT EXISTS alumnos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL,
    telefono  TEXT NOT NULL UNIQUE,
    sexo      TEXT NOT NULL CHECK (sexo IN ('H','M')),
    token     TEXT NOT NULL UNIQUE,
    activo    INTEGER NOT NULL DEFAULT 1,
    notas     TEXT NOT NULL DEFAULT '',
    creado    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asistencias (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id  INTEGER NOT NULL REFERENCES alumnos(id) ON DELETE CASCADE,
    clase_id   TEXT NOT NULL,
    fecha      TEXT NOT NULL,
    creado     TEXT NOT NULL,
    UNIQUE (alumno_id, clase_id, fecha)
);
CREATE INDEX IF NOT EXISTS ix_asis_fecha ON asistencias (fecha);

-- Una fila por alumno y dia: marca que ese alumno ya ha contestado (aunque diga que no va)
CREATE TABLE IF NOT EXISTS respuestas (
    alumno_id  INTEGER NOT NULL REFERENCES alumnos(id) ON DELETE CASCADE,
    fecha      TEXT NOT NULL,
    actualizado TEXT NOT NULL,
    PRIMARY KEY (alumno_id, fecha)
);

CREATE TABLE IF NOT EXISTS envios (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER NOT NULL REFERENCES alumnos(id) ON DELETE CASCADE,
    fecha     TEXT NOT NULL,
    canal     TEXT NOT NULL,
    estado    TEXT NOT NULL,
    detalle   TEXT NOT NULL DEFAULT '',
    creado    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_envios_fecha ON envios (fecha);
"""


def conectar() -> sqlite3.Connection:
    config.DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar() -> None:
    with conectar() as con:
        con.executescript(ESQUEMA)


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Telefonos
# --------------------------------------------------------------------------- #
def normalizar_telefono(bruto: str) -> str:
    """Devuelve el numero en formato internacional sin '+' (ej. 34600112233).

    Asume prefijo 34 (Espana) cuando llegan 9 digitos sueltos.
    """
    limpio = re.sub(r"[^\d+]", "", bruto or "")
    limpio = limpio.replace("+", "")
    if len(limpio) == 9 and limpio[0] in "6789":
        limpio = "34" + limpio
    if not limpio.isdigit() or not (8 <= len(limpio) <= 15):
        raise ValueError(f"Telefono no valido: {bruto!r}")
    return limpio


# --------------------------------------------------------------------------- #
# Alumnos
# --------------------------------------------------------------------------- #
def crear_alumno(nombre: str, telefono: str, sexo: str, notas: str = "") -> dict:
    nombre = (nombre or "").strip()
    sexo = (sexo or "").strip().upper()[:1]
    if not nombre:
        raise ValueError("El nombre es obligatorio")
    if sexo not in ("H", "M"):
        raise ValueError("El sexo debe ser 'H' o 'M'")
    tel = normalizar_telefono(telefono)
    with conectar() as con:
        fila = con.execute("SELECT id FROM alumnos WHERE telefono = ?", (tel,)).fetchone()
        if fila:
            raise ValueError(f"Ya existe un alumno con el telefono {tel}")
        cur = con.execute(
            "INSERT INTO alumnos (nombre, telefono, sexo, token, activo, notas, creado)"
            " VALUES (?,?,?,?,1,?,?)",
            (nombre, tel, sexo, secrets.token_urlsafe(12), notas.strip(), _ahora()),
        )
        return dict(con.execute("SELECT * FROM alumnos WHERE id = ?", (cur.lastrowid,)).fetchone())


def actualizar_alumno(alumno_id: int, **campos) -> dict:
    permitidos = {"nombre", "telefono", "sexo", "activo", "notas"}
    cambios = {k: v for k, v in campos.items() if k in permitidos and v is not None}
    if "telefono" in cambios:
        cambios["telefono"] = normalizar_telefono(cambios["telefono"])
    if "sexo" in cambios:
        cambios["sexo"] = str(cambios["sexo"]).upper()[:1]
        if cambios["sexo"] not in ("H", "M"):
            raise ValueError("El sexo debe ser 'H' o 'M'")
    if "activo" in cambios:
        cambios["activo"] = 1 if cambios["activo"] else 0
    if not cambios:
        return obtener_alumno(alumno_id)
    sets = ", ".join(f"{k} = ?" for k in cambios)
    with conectar() as con:
        con.execute(f"UPDATE alumnos SET {sets} WHERE id = ?", (*cambios.values(), alumno_id))
    return obtener_alumno(alumno_id)


def borrar_alumno(alumno_id: int) -> None:
    with conectar() as con:
        con.execute("DELETE FROM alumnos WHERE id = ?", (alumno_id,))


def obtener_alumno(alumno_id: int) -> dict:
    with conectar() as con:
        fila = con.execute("SELECT * FROM alumnos WHERE id = ?", (alumno_id,)).fetchone()
    if not fila:
        raise LookupError("Alumno no encontrado")
    return dict(fila)


def alumno_por_token(token: str) -> dict | None:
    with conectar() as con:
        fila = con.execute("SELECT * FROM alumnos WHERE token = ?", (token,)).fetchone()
    return dict(fila) if fila else None


def listar_alumnos(solo_activos: bool = False) -> list[dict]:
    sql = "SELECT * FROM alumnos"
    if solo_activos:
        sql += " WHERE activo = 1"
    sql += " ORDER BY nombre COLLATE NOCASE"
    with conectar() as con:
        return [dict(f) for f in con.execute(sql)]


# --------------------------------------------------------------------------- #
# Asistencias
# --------------------------------------------------------------------------- #
def guardar_respuesta(alumno_id: int, fecha: str, clase_ids: list[str]) -> None:
    """Sustituye la seleccion del alumno para esa fecha (lista vacia = hoy no voy)."""
    validar_fecha(fecha)
    dia = date.fromisoformat(fecha).isoweekday()
    for cid in clase_ids:
        if not horario.existe(cid):
            raise ValueError(f"Clase desconocida: {cid}")
        if horario.POR_ID[cid]["dia"] != dia:
            raise ValueError(f"La clase {cid} no se imparte el {fecha}")
    with conectar() as con:
        con.execute("DELETE FROM asistencias WHERE alumno_id = ? AND fecha = ?", (alumno_id, fecha))
        con.executemany(
            "INSERT INTO asistencias (alumno_id, clase_id, fecha, creado) VALUES (?,?,?,?)",
            [(alumno_id, cid, fecha, _ahora()) for cid in dict.fromkeys(clase_ids)],
        )
        con.execute(
            "INSERT INTO respuestas (alumno_id, fecha, actualizado) VALUES (?,?,?)"
            " ON CONFLICT(alumno_id, fecha) DO UPDATE SET actualizado = excluded.actualizado",
            (alumno_id, fecha, _ahora()),
        )


def seleccion_de(alumno_id: int, fecha: str) -> list[str]:
    with conectar() as con:
        filas = con.execute(
            "SELECT clase_id FROM asistencias WHERE alumno_id = ? AND fecha = ?", (alumno_id, fecha)
        )
        return [f["clase_id"] for f in filas]


def ha_respondido(alumno_id: int, fecha: str) -> bool:
    with conectar() as con:
        fila = con.execute(
            "SELECT 1 FROM respuestas WHERE alumno_id = ? AND fecha = ?", (alumno_id, fecha)
        ).fetchone()
    return fila is not None


def recuento(fecha: str) -> list[dict]:
    """Para cada clase de ese dia: hombres, mujeres, total y estado del balance."""
    validar_fecha(fecha)
    dia = date.fromisoformat(fecha).isoweekday()
    with conectar() as con:
        filas = con.execute(
            "SELECT a.clase_id, al.sexo, COUNT(*) AS n"
            " FROM asistencias a JOIN alumnos al ON al.id = a.alumno_id"
            " WHERE a.fecha = ? GROUP BY a.clase_id, al.sexo",
            (fecha,),
        ).fetchall()
    conteos: dict[str, dict[str, int]] = {}
    for f in filas:
        conteos.setdefault(f["clase_id"], {"H": 0, "M": 0})[f["sexo"]] = f["n"]

    salida = []
    for clase in horario.clases_del_dia(dia):
        c = conteos.get(clase["id"], {"H": 0, "M": 0})
        h, m = c.get("H", 0), c.get("M", 0)
        salida.append({**clase, "hombres": h, "mujeres": m, "total": h + m, **_balance(h, m)})
    return salida


def _balance(h: int, m: int) -> dict:
    dif = abs(h - m)
    if h + m == 0:
        estado = "vacia"
    elif dif < config.UMBRAL_AMBAR:
        estado = "ok"
    elif dif < config.UMBRAL_ROJO:
        estado = "ambar"
    else:
        estado = "rojo"
    faltan = "" if dif == 0 else ("H" if h < m else "M")
    return {"diferencia": dif, "estado": estado, "falta_sexo": faltan}


def nominal(fecha: str, clase_id: str) -> list[dict]:
    """Quien ha dicho que va a esa clase (para pasar lista en recepcion)."""
    with conectar() as con:
        filas = con.execute(
            "SELECT al.nombre, al.sexo, al.telefono FROM asistencias a"
            " JOIN alumnos al ON al.id = a.alumno_id"
            " WHERE a.fecha = ? AND a.clase_id = ?"
            " ORDER BY al.sexo, al.nombre COLLATE NOCASE",
            (fecha, clase_id),
        )
        return [dict(f) for f in filas]


def dias_con_confirmaciones(fecha: str, atras: int = 7, adelante: int = 14) -> list[dict]:
    """Fechas cercanas que tienen gente apuntada, para no mirar un dia vacio sin saberlo."""
    base = date.fromisoformat(fecha)
    desde = (base - timedelta(days=atras)).isoformat()
    hasta = (base + timedelta(days=adelante)).isoformat()
    with conectar() as con:
        filas = con.execute(
            "SELECT fecha, COUNT(*) AS n FROM asistencias"
            " WHERE fecha BETWEEN ? AND ? GROUP BY fecha ORDER BY fecha",
            (desde, hasta),
        )
        return [{"fecha": f["fecha"], "asistencias": f["n"]} for f in filas]


def sin_responder(fecha: str) -> list[dict]:
    with conectar() as con:
        filas = con.execute(
            "SELECT al.* FROM alumnos al"
            " WHERE al.activo = 1 AND al.id NOT IN (SELECT alumno_id FROM respuestas WHERE fecha = ?)"
            " ORDER BY al.nombre COLLATE NOCASE",
            (fecha,),
        )
        return [dict(f) for f in filas]


def candidatos_para_equilibrar(fecha: str, clase_id: str, sexo: str, semanas: int = 6) -> list[dict]:
    """Alumnos del sexo que falta que suelen ir a esa clase y hoy no han confirmado.

    Sirve para el aviso: 'faltan 3 chicos en Bachata Sensual N3, avisa a estos'.
    """
    desde = (date.fromisoformat(fecha) - timedelta(weeks=semanas)).isoformat()
    with conectar() as con:
        filas = con.execute(
            "SELECT al.id, al.nombre, al.telefono, al.sexo, COUNT(*) AS veces"
            " FROM asistencias a JOIN alumnos al ON al.id = a.alumno_id"
            " WHERE a.clase_id = ? AND a.fecha >= ? AND a.fecha < ? AND al.sexo = ? AND al.activo = 1"
            "   AND al.id NOT IN (SELECT alumno_id FROM asistencias WHERE fecha = ? AND clase_id = ?)"
            " GROUP BY al.id ORDER BY veces DESC, al.nombre COLLATE NOCASE LIMIT 10",
            (clase_id, desde, fecha, sexo, fecha, clase_id),
        )
        return [dict(f) for f in filas]


# --------------------------------------------------------------------------- #
# Envios
# --------------------------------------------------------------------------- #
def registrar_envio(alumno_id: int, fecha: str, canal: str, estado: str, detalle: str = "") -> None:
    with conectar() as con:
        con.execute(
            "INSERT INTO envios (alumno_id, fecha, canal, estado, detalle, creado) VALUES (?,?,?,?,?,?)",
            (alumno_id, fecha, canal, estado, detalle[:500], _ahora()),
        )


def envios_del_dia(fecha: str) -> list[dict]:
    with conectar() as con:
        filas = con.execute(
            "SELECT e.*, al.nombre FROM envios e JOIN alumnos al ON al.id = e.alumno_id"
            " WHERE e.fecha = ? ORDER BY e.creado DESC",
            (fecha,),
        )
        return [dict(f) for f in filas]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def validar_fecha(fecha: str) -> str:
    try:
        date.fromisoformat(fecha)
    except (TypeError, ValueError):
        raise ValueError(f"Fecha no valida (usa AAAA-MM-DD): {fecha!r}") from None
    return fecha


def hoy() -> str:
    return date.today().isoformat()