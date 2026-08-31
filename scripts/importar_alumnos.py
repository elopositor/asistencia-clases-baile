"""Importa alumnos desde un CSV con cabecera: nombre,telefono,sexo

    python scripts/importar_alumnos.py alumnos.csv

El sexo admite H/M, hombre/mujer, h/m, chico/chica.
Los telefonos de 9 digitos se completan con el prefijo 34.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402

MAPA_SEXO = {
    "h": "H", "hombre": "H", "chico": "H", "m": "M", "mujer": "M", "chica": "M", "f": "M",
}


def main() -> None:
    config.consola_utf8()
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    fichero = Path(sys.argv[1])
    if not fichero.exists():
        print(f"No existe el fichero {fichero}")
        sys.exit(1)

    db.inicializar()
    altas = errores = 0
    with fichero.open(encoding="utf-8-sig", newline="") as f:
        for i, fila in enumerate(csv.DictReader(f), start=2):
            claves = {k.strip().lower(): (v or "").strip() for k, v in fila.items() if k}
            sexo = MAPA_SEXO.get(claves.get("sexo", "").lower(), "")
            try:
                a = db.crear_alumno(claves.get("nombre", ""), claves.get("telefono", ""), sexo)
                altas += 1
                print(f"  + {a['nombre']:<25} +{a['telefono']}  {a['sexo']}")
            except ValueError as e:
                errores += 1
                print(f"  ! linea {i}: {e}")

    print(f"\nAltas: {altas} · errores: {errores}")
    if altas:
        print("Reparte los enlaces desde /admin o lanza: python scripts/enviar_encuesta.py")


if __name__ == "__main__":
    main()