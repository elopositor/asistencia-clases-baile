"""Comprueba el cableado del RC522 y lee tarjetas, sin tocar el servidor.

Usalo la primera vez que conectes el lector, o cuando algo deje de ir. Desde el PC,
con la Pico enchufada por USB:

    python -m mpremote connect COM3 run probar_lector.py

Te dice si el lector responde y, si acercas una tarjeta, su UID.
"""

from utime import sleep_ms

import mfrc522

PINES = """
  RC522        Pico W      pin fisico
  SDA (SS)     GP1         2
  SCK          GP2         4
  MOSI         GP3         5
  MISO         GP4         6
  GND          GND         3
  RST          GP0         1
  3.3V         3V3(OUT)    36     <- NUNCA a 5 V
"""


def main():
    print("Probando el lector RC522...")
    lector = mfrc522.crear()
    v = lector.version()

    if v in (0x00, 0xFF):
        print("\nNO responde (VersionReg = 0x%02X)." % v)
        print("Casi siempre es una de estas tres cosas:")
        print("  1. Los pines del RC522 no estan soldados a la placa.")
        print("  2. Algun cable en el pin equivocado.")
        print("  3. El modulo sin alimentacion (3.3V y GND).")
        print(PINES)
        return

    print("Lector OK. VersionReg = 0x%02X (%s)"
          % (v, "clon v2" if v == 0x92 else "original v1" if v == 0x91 else "compatible"))
    print("\nAcerca una tarjeta o un llavero (Ctrl+C para salir)...\n")

    ultimo = ""
    while True:
        estado, _ = lector.detectar()
        if estado == mfrc522.OK:
            estado, uid = lector.uid()
            if estado == mfrc522.OK:
                texto = mfrc522.uid_a_texto(uid)
                if texto != ultimo:
                    ultimo = texto
                    print("  Tarjeta:", texto)
        sleep_ms(200)


main()
