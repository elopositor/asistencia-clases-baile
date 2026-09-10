"""Busca la pantalla LCD y escribe en ella, para comprobar el cableado.

    python -m mpremote connect COM3 run probar_pantalla.py

Si no encuentra nada, repasa los cuatro cables. Si los encuentra pero no se lee,
gira el potenciometro azul del modulo I2C: viene con el contraste al minimo.
"""

from machine import I2C, Pin
from utime import sleep

import lcd

PINES = """
  LCD (modulo I2C)   Pico W     pin fisico
  GND                GND        8
  VCC                3V3(OUT)   36
  SDA                GP6        9
  SCL                GP7        10
"""


def main():
    print("Buscando la pantalla en I2C1 (GP6 = SDA, GP7 = SCL)...")
    i2c = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)
    encontrados = i2c.scan()

    if not encontrados:
        print("\nNo hay nada en el bus I2C.")
        print("  1. Repasa los cuatro cables.")
        print("  2. Comprueba que el modulo I2C esta bien soldado a la pantalla.")
        print("  3. La retroiluminacion deberia encenderse solo con dar corriente:")
        print("     si no se enciende, es que no le llega alimentacion.")
        print(PINES)
        return

    print("  encontrado(s):", ", ".join("0x%02X" % d for d in encontrados))
    direccion = lcd.buscar(i2c)
    print("  uso la direccion 0x%02X" % direccion)

    p = lcd.LCD(i2c, direccion)
    p.mostrar("On Stage", "pantalla lista")
    print("\nDeberias leer 'On Stage / pantalla lista'.")
    print("Si la ves en blanco o toda en negro, gira el potenciometro azul.")

    sleep(3)
    for texto in (("Hola Alejandro", "20:00 Latinos"), ("Ana Bravo", "faltan chicos"),
                  ("Que aproveche", "la clase :)")):
        p.mostrar(*texto)
        sleep(2)
    p.mostrar("Pasa tu llavero", "")
    print("Prueba terminada.")


main()
