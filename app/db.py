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

-- Entradas reales por el lector de la puerta. 'asistencias' es lo que el alumno
-- dijo que haria; esto es lo que hizo.
CREATE TABLE IF NOT EXISTS accesos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id   INTEGER NOT NULL REFERENCES alumnos(id) ON DELETE CASCADE,
    fecha       TEXT NOT NULL,
    hora        TEXT NOT NULL,
    clase_id    TEXT,
    dispositivo TEXT NOT NULL DEFAULT '',
    creado      TEXT NOT NULL,
    UNIQUE (alumno_id, fecha, clase_id)
);
CREATE INDEX IF NOT EXISTS ix_accesos_fecha ON accesos (fecha);

-- Tarjetas leidas que aun no pertenecen a nadie, para poder asignarlas desde /admin
-- con un clic en vez de teclear el UID a mano.
CREATE TABLE IF NOT EXISTS tarjetas_sin_duenno (
    uid       TEXT PRIMARY KEY,
    vista     TEXT NOT NULL,
    veces     INTEGER NOT NULL DEFAULT 1
);
"""

# Columnas anadidas despues de la primera version: SQLite no las crea con
# CREATE TABLE IF NOT EXISTS sobre una tabla que ya existe.
COLUMNAS_NUEVAS = {
    "alumnos": {"tarjeta_uid": "TEXT"},
}


def conectar() -> sqlite3.Connection:
    config.DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar() -> None:
    with conectar() as con:
        con.executescript(ESQUEMA)
        for tabla, columnas in COLUMNAS_NUEVAS.items():
            existentes = {f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")}
            for nombre, tipo in columnas.items():
                if nombre not in existentes:
                    con.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}")
        # UNIQUE en tarjeta_uid, pero permitiendo que muchos alumnos no tengan tarjeta:
        # un indice unico normal ya trata cada NULL como distinto.
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_alumnos_tarjeta ON alumnos (tarjeta_uid)"
        )


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


def listar_alumnos(solo_activos: bool = False, con_ultimo_acceso: bool = False) -> list[dict]:
    """Los alumnos. Con con_ultimo_acceso anade cuando fue la ultima vez que ficho.

    Sirve para ver de un vistazo quien lleva semanas sin aparecer, o si el llavero
    de alguien ha dejado de leerse.
    """
    if con_ultimo_acceso:
        sql = (
            "SELECT al.*, (SELECT a.fecha || ' ' || a.hora FROM accesos a"
            "   WHERE a.alumno_id = al.id ORDER BY a.fecha DESC, a.hora DESC LIMIT 1"
            " ) AS ultimo_acceso FROM alumnos al"
        )
        if solo_activos:
            sql += " WHERE al.activo = 1"
        sql += " ORDER BY al.nombre COLLATE NOCASE"
    else:
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
# Control de acceso (lector de la puerta)
# --------------------------------------------------------------------------- #
# Margen para decidir a que clase corresponde un fichaje, en minutos respecto a
# la hora de inicio. Se ficha antes de entrar, y siempre hay quien llega tarde.
ANTES = 30
DESPUES = 45


def normalizar_uid(bruto: str) -> str:
    """UID de la tarjeta en mayusculas y sin separadores: '04 a2:9f' -> '04A29F'."""
    limpio = re.sub(r"[^0-9A-Fa-f]", "", bruto or "").upper()
    if not 4 <= len(limpio) <= 32:
        raise ValueError(f"UID no valido: {bruto!r}")
    return limpio


def alumno_por_uid(uid: str) -> dict | None:
    with conectar() as con:
        fila = con.execute("SELECT * FROM alumnos WHERE tarjeta_uid = ?", (normalizar_uid(uid),)).fetchone()
    return dict(fila) if fila else None


def asignar_tarjeta(alumno_id: int, uid: str | None) -> dict:
    """Vincula (o desvincula, con uid None) una tarjeta a un alumno."""
    if uid is None:
        with conectar() as con:
            con.execute("UPDATE alumnos SET tarjeta_uid = NULL WHERE id = ?", (alumno_id,))
        return obtener_alumno(alumno_id)

    limpio = normalizar_uid(uid)
    with conectar() as con:
        otro = con.execute(
            "SELECT nombre FROM alumnos WHERE tarjeta_uid = ? AND id <> ?", (limpio, alumno_id)
        ).fetchone()
        if otro:
            raise ValueError(f"Esa tarjeta ya es de {otro['nombre']}")
        con.execute("UPDATE alumnos SET tarjeta_uid = ? WHERE id = ?", (limpio, alumno_id))
        con.execute("DELETE FROM tarjetas_sin_duenno WHERE uid = ?", (limpio,))
    return obtener_alumno(alumno_id)


def _minutos(hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    return h * 60 + m


def clase_en_curso(fecha: str, hora: str, alumno_id: int | None = None) -> dict | None:
    """A que clase corresponde un fichaje a esa hora.

    Con dos salas a la vez hay empates: si el alumno habia confirmado una de las
    candidatas, se le apunta a esa; si no, a la que empiece mas cerca.
    """
    dia = date.fromisoformat(fecha).isoweekday()
    ahora = _minutos(hora)
    candidatas = [
        c for c in horario.clases_del_dia(dia)
        if -ANTES <= ahora - _minutos(c["hora"]) <= DESPUES
    ]
    if not candidatas:
        return None
    if len(candidatas) > 1 and alumno_id is not None:
        confirmadas = set(seleccion_de(alumno_id, fecha))
        preferidas = [c for c in candidatas if c["id"] in confirmadas]
        if preferidas:
            candidatas = preferidas
    return min(candidatas, key=lambda c: abs(ahora - _minutos(c["hora"])))


def registrar_acceso(alumno_id: int, momento: datetime | None = None, dispositivo: str = "") -> dict:
    """Apunta una entrada real. Repetir el fichaje en la misma clase no duplica."""
    momento = momento or datetime.now()
    fecha = momento.date().isoformat()
    hora = momento.strftime("%H:%M")
    clase = clase_en_curso(fecha, hora, alumno_id)
    clase_id = clase["id"] if clase else None

    with conectar() as con:
        ya = con.execute(
            "SELECT hora FROM accesos WHERE alumno_id = ? AND fecha = ? AND clase_id IS ?",
            (alumno_id, fecha, clase_id),
        ).fetchone()
        if ya:
            repetido, hora = True, ya["hora"]
        else:
            repetido = False
            con.execute(
                "INSERT INTO accesos (alumno_id, fecha, hora, clase_id, dispositivo, creado)"
                " VALUES (?,?,?,?,?,?)",
                (alumno_id, fecha, hora, clase_id, dispositivo, _ahora()),
            )

    previsto = bool(clase_id) and clase_id in seleccion_de(alumno_id, fecha)
    return {
        "fecha": fecha,
        "hora": hora,
        "clase": clase,
        "repetido": repetido,
        "previsto": previsto,
    }


def presentes(fecha: str) -> dict[str, dict[str, int]]:
    """Cuantos han entrado de verdad en cada clase, por sexo."""
    with conectar() as con:
        filas = con.execute(
            "SELECT a.clase_id, al.sexo, COUNT(*) AS n FROM accesos a"
            " JOIN alumnos al ON al.id = a.alumno_id"
            " WHERE a.fecha = ? AND a.clase_id IS NOT NULL"
            " GROUP BY a.clase_id, al.sexo",
            (fecha,),
        ).fetchall()
    salida: dict[str, dict[str, int]] = {}
    for f in filas:
        d = salida.setdefault(f["clase_id"], {"H": 0, "M": 0})
        d[f["sexo"]] = f["n"]
    return salida


def dentro_de_clase(fecha: str, clase_id: str) -> list[dict]:
    with conectar() as con:
        filas = con.execute(
            "SELECT al.nombre, al.sexo, a.hora FROM accesos a"
            " JOIN alumnos al ON al.id = a.alumno_id"
            " WHERE a.fecha = ? AND a.clase_id = ? ORDER BY a.hora",
            (fecha, clase_id),
        )
        return [dict(f) for f in filas]


def accesos_del_dia(fecha: str) -> list[dict]:
    """Todas las entradas del dia, tambien las de fuera del horario de clase.

    Sin esto, quien ficha a una hora en la que no hay clase queda registrado pero
    no aparece en ninguna pantalla, y parece que el lector no funciona.
    """
    with conectar() as con:
        filas = con.execute(
            "SELECT al.nombre, al.sexo, a.hora, a.clase_id, a.dispositivo FROM accesos a"
            " JOIN alumnos al ON al.id = a.alumno_id"
            " WHERE a.fecha = ? ORDER BY a.hora DESC",
            (fecha,),
        ).fetchall()
    salida = []
    for f in filas:
        clase = horario.POR_ID.get(f["clase_id"] or "")
        salida.append(
            {
                "nombre": f["nombre"],
                "sexo": f["sexo"],
                "hora": f["hora"],
                "clase": clase["etiqueta"] if clase else "",
                "clase_hora": clase["hora"] if clase else "",
                "dispositivo": f["dispositivo"],
            }
        )
    return salida


def anotar_tarjeta_desconocida(uid: str) -> None:
    limpio = normalizar_uid(uid)
    with conectar() as con:
        con.execute(
            "INSERT INTO tarjetas_sin_duenno (uid, vista, veces) VALUES (?,?,1)"
            " ON CONFLICT(uid) DO UPDATE SET vista = excluded.vista, veces = veces + 1",
            (limpio, _ahora()),
        )


def tarjetas_sin_duenno() -> list[dict]:
    with conectar() as con:
        return [dict(f) for f in con.execute(
            "SELECT * FROM tarjetas_sin_duenno ORDER BY vista DESC LIMIT 20"
        )]


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