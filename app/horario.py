"""Horario semanal de On Stage Valladolid, tal cual el cartel de bailes latinos.

Dos salas funcionan a la vez y cada clase dura 1 hora.
Editar aqui es la unica forma de cambiar el horario: el resto del sistema lo lee.
"""

from __future__ import annotations

# Todos los dias de la semana; solo de lunes a viernes hay clase.
NOMBRE_DIA = {
    1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves",
    5: "Viernes", 6: "Sábado", 7: "Domingo",
}
DIAS_LECTIVOS = {d: NOMBRE_DIA[d] for d in (1, 2, 3, 4, 5)}

SALAS = {
    1: {"nombre": "Sala 1", "profe": "Sergio"},
    2: {"nombre": "Sala 2", "profe": "Omar"},
}

# (dia, hora, sala, baile, nivel, nota)
_FILAS = [
    # Lunes
    (1, "19:00", 1, "Latinos", "Nivel 3", ""),
    (1, "20:00", 1, "Latinos", "Nivel 4", ""),
    (1, "21:00", 1, "Latinos", "Iniciación 0", ""),
    (1, "21:00", 2, "Bachata", "Lady's Style", ""),
    # Martes
    (2, "18:30", 2, "Latinos", "Inicio", ""),
    (2, "19:30", 2, "Latinos", "Medio", ""),
    (2, "20:00", 1, "Iniciación a la salsa en línea y bachata", "", ""),
    (2, "20:30", 2, "Bachata Sensual", "Avanzado", ""),
    (2, "21:00", 1, "Kizomba", "Medio avanzado", ""),
    (2, "21:30", 2, "Salsa ON1", "Avanzado", ""),
    # Miercoles
    (3, "18:30", 1, "Latinos", "Nivel 1", ""),
    (3, "19:00", 2, "Bachata Sensual", "Inicio", ""),
    (3, "19:30", 1, "Latinos", "Iniciación 0", ""),
    (3, "20:00", 2, "Técnica Sensual", "Avanzado", ""),
    (3, "20:30", 1, "Latinos", "Nivel 2", ""),
    (3, "21:00", 2, "Salsa ON2", "Avanzado", ""),
    (3, "21:30", 1, "Iniciación a la bachata sensual", "", ""),
    # Jueves
    (4, "19:30", 1, "Latinos", "Nivel 4", ""),
    (4, "20:30", 1, "Bachata Sensual", "Nivel 3", ""),
    (4, "21:30", 1, "Bachata Sensual", "Nivel 2", ""),
    # Viernes
    (5, "19:30", 1, "Latinos", "Iniciación 0", ""),
    (5, "20:30", 1, "Latinos", "Nivel 4", "Línea y cubano + bachata"),
    (5, "21:00", 2, "Kizomba", "Inicial", ""),
    (5, "21:30", 1, "Latinos", "Nivel 3", ""),
    (5, "22:00", 2, "Kizomba", "Medio", ""),
]


def _clase_id(dia: int, hora: str, sala: int) -> str:
    return f"{dia}-{hora.replace(':', '')}-s{sala}"


def _fin(hora: str) -> str:
    h, m = (int(x) for x in hora.split(":"))
    return f"{(h + 1) % 24:02d}:{m:02d}"


CLASES: list[dict] = []
for dia, hora, sala, baile, nivel, nota in _FILAS:
    CLASES.append(
        {
            "id": _clase_id(dia, hora, sala),
            "dia": dia,
            "dia_nombre": NOMBRE_DIA[dia],
            "hora": hora,
            "hora_fin": _fin(hora),
            "sala": sala,
            "sala_nombre": SALAS[sala]["nombre"],
            "profe": SALAS[sala]["profe"],
            "baile": baile,
            "nivel": nivel,
            "nota": nota,
            "etiqueta": f"{baile} {nivel}".strip(),
        }
    )

POR_ID = {c["id"]: c for c in CLASES}


def clases_del_dia(dia: int) -> list[dict]:
    """Clases de un dia de la semana (1=lunes ... 5=viernes), ordenadas por hora y sala."""
    return sorted(
        (c for c in CLASES if c["dia"] == dia),
        key=lambda c: (c["hora"], c["sala"]),
    )


def existe(clase_id: str) -> bool:
    return clase_id in POR_ID