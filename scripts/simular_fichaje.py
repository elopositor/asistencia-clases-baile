"""Hace de lector RFID sin lector: sirve para probar el control de acceso.

    python scripts/simular_fichaje.py --alumno "Ana"        -> ficha a Ana
    python scripts/simular_fichaje.py --uid A1B2C3D4        -> ficha ese UID
    python scripts/simular_fichaje.py --alumno "Ana" --hora 20:05
    python scripts/simular_fichaje.py --listar              -> quien tiene tarjeta

Con --alumno, si esa persona no tiene tarjeta asignada se le inventa una y se le
asigna, que es justo lo que pasaria al pasar un llavero nuevo por el lector.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app import config, db  # noqa: E402


def main() -> None:
    config.consola_utf8()
    p = argparse.ArgumentParser(description="Simula un fichaje en la puerta")
    p.add_argument("--alumno", help="nombre (o parte del nombre) del alumno")
    p.add_argument("--uid", help="UID de tarjeta en hexadecimal")
    p.add_argument("--hora", help="hora del fichaje HH:MM (por defecto, ahora)")
    p.add_argument("--url", default="http://127.0.0.1:8000", help="direccion del servidor")
    p.add_argument("--listar", action="store_true", help="muestra quien tiene tarjeta")
    args = p.parse_args()

    db.inicializar()

    if args.listar:
        for a in db.listar_alumnos():
            marca = a["tarjeta_uid"] or "-- sin tarjeta --"
            print(f"  {a['sexo']}  {a['nombre']:<22} {marca}")
        pendientes = db.tarjetas_sin_duenno()
        if pendientes:
            print("\nTarjetas leidas sin asignar:")
            for t in pendientes:
                print(f"  {t['uid']}  vista {t['vista']}  ({t['veces']} veces)")
        return

    if not config.DEVICE_KEY:
        print("Falta DEVICE_KEY en el .env: el fichaje esta desactivado.")
        print('Genera una con:  python -c "import secrets; print(secrets.token_urlsafe(24))"')
        sys.exit(1)

    uid = args.uid
    if args.alumno:
        coincidencias = [a for a in db.listar_alumnos() if args.alumno.lower() in a["nombre"].lower()]
        if not coincidencias:
            print(f"No hay ningun alumno que se parezca a {args.alumno!r}")
            sys.exit(1)
        if len(coincidencias) > 1:
            print("Hay varios; se mas concreto:")
            for a in coincidencias:
                print(f"   {a['nombre']}")
            sys.exit(1)
        alumno = coincidencias[0]
        uid = alumno["tarjeta_uid"]
        if not uid:
            # UID falso pero estable para ese alumno, como el de un llavero real
            uid = hashlib.sha1(alumno["token"].encode()).hexdigest()[:8].upper()
            db.asignar_tarjeta(alumno["id"], uid)
            print(f"{alumno['nombre']} no tenia tarjeta; le asigno la {uid}")

    if not uid:
        print("Dime --alumno o --uid")
        sys.exit(1)

    if args.hora:
        # Fichaje con hora inventada: se escribe directo, sin pasar por la red
        alumno = db.alumno_por_uid(uid)
        if not alumno:
            print(f"La tarjeta {uid} no es de nadie")
            sys.exit(1)
        momento = datetime.combine(datetime.now().date(), datetime.strptime(args.hora, "%H:%M").time())
        res = db.registrar_acceso(alumno["id"], momento=momento, dispositivo="simulador")
        clase = res["clase"]["etiqueta"] if res["clase"] else "fuera de horario"
        print(f"{alumno['nombre']} -> {res['hora']} -> {clase}"
              f"{'  (repetido)' if res['repetido'] else ''}"
              f"{'  [no estaba apuntado]' if res['clase'] and not res['previsto'] else ''}")
        return

    r = httpx.post(
        f"{args.url.rstrip('/')}/api/fichaje",
        headers={"X-Device-Key": config.DEVICE_KEY},
        json={"uid": uid, "dispositivo": "simulador"},
        timeout=15,
    )
    print(f"HTTP {r.status_code}")
    try:
        d = r.json()
    except ValueError:
        print(r.text[:300])
        return
    print(f"  {d.get('mensaje') or d.get('detail')}")
    if d.get("ok"):
        print(f"  clase: {d.get('clase') or 'fuera de horario'} · {d['hora']}"
              f" · {'previsto' if d['previsto'] else 'no estaba apuntado'}")


if __name__ == "__main__":
    main()
