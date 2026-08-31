"""Rellena la base con alumnos y respuestas inventadas para ver el sistema en marcha.

    python scripts/demo.py           -> crea data/demo.db y la deja lista
    python scripts/demo.py --limpiar -> borra la base de demo

Usa una base aparte (data/demo.db) para no tocar los datos reales. Se puede
apuntar a otro fichero con la variable de entorno DB_PATH.
"""

from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DB_PATH", str(RAIZ / "data" / "demo.db"))

from app import config, db, horario, whatsapp  # noqa: E402

NOMBRES_H = ["Alejandro Martín", "Carlos Ruiz", "Javier Santos", "Pablo Ortega", "Diego Lara",
             "Rubén Casas", "Iván Prieto", "Hugo Ferrer", "Mario Nieto", "Álvaro Cid"]
NOMBRES_M = ["Lucía Fernández", "Marta Gómez", "Sara Delgado", "Elena Vidal", "Ana Bravo",
             "Clara Ibáñez", "Nerea Sanz", "Paula Rojo", "Irene Muñoz", "Alba Costa",
             "Rocío Pardo", "Julia Mena"]


def main() -> None:
    config.consola_utf8()
    ruta = Path(os.environ["DB_PATH"])
    if "--limpiar" in sys.argv:
        ruta.unlink(missing_ok=True)
        print(f"Borrada {ruta}")
        return

    ruta.unlink(missing_ok=True)
    db.inicializar()

    alumnos = []
    tel = 600100000
    for lista, sexo in ((NOMBRES_H, "H"), (NOMBRES_M, "M")):
        for nombre in lista:
            tel += 137
            alumnos.append(db.crear_alumno(nombre, str(tel), sexo))

    # Respuestas de las ultimas 3 semanas y de los proximos dias, con sesgo
    # realista (mas mujeres que hombres) para que se vea el aviso de descuadre.
    hoy = date.today()
    for delta in range(-21, 5):
        f = hoy + timedelta(days=delta)
        if f.isoweekday() > 5:
            continue
        clases = horario.clases_del_dia(f.isoweekday())
        for a in alumnos:
            prob = 0.30 if a["sexo"] == "H" else 0.45
            elegidas = [c["id"] for c in clases if random.random() < prob / max(len(clases) / 4, 1)]
            if elegidas or random.random() < 0.5:
                db.guardar_respuesta(a["id"], f.isoformat(), elegidas)

    proximo = hoy
    while proximo.isoweekday() > 5:  # si hoy es finde, enseñamos el lunes
        proximo += timedelta(days=1)
    fecha = proximo.isoformat()

    print(f"Base de demo: {ruta}")
    print(f"{len(alumnos)} alumnos · respuestas de las ultimas 3 semanas\n")
    print(whatsapp.mensaje_resumen(fecha))
    print("\nArranca con la base de demo:")
    print(f'  $env:DB_PATH="{ruta}"; python -m uvicorn app.main:app --port 8000')
    print(f"\n  Panel  : {config.base_url()}/panel?key={config.ADMIN_KEY}&d={fecha}")
    print(f"  Alumno : {config.base_url()}/a/{alumnos[0]['token']}?d={fecha}   ({alumnos[0]['nombre']})")


if __name__ == "__main__":
    main()
