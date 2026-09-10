"""Pantalla LCD 1602 con adaptador I2C (PCF8574), para MicroPython.

Dos lineas de 16 caracteres. La pantalla no conoce acentos ni enes, asi que el
texto se limpia antes de escribirlo.

Cableado a la Pico W (I2C1, que deja libres los pines del lector RFID):

    LCD (modulo I2C)   Pico W     pin fisico
    GND                GND        8
    VCC                3V3(OUT)   36     <- ver la nota de abajo
    SDA                GP6        9
    SCL                GP7        10

Nota sobre el voltaje: estas pantallas piden 5 V para verse bien, pero si las
alimentas con los 5 V del pin 40 (VBUS), sus resistencias de pull-up ponen 5 V en
SDA y SCL, y las patas de la Pico solo aguantan 3,3 V. Empieza siempre a 3,3 V y
sube el contraste con el potenciometro azul del modulo. Si aun asi no se lee,
hace falta un adaptador de niveles.
"""

from utime import sleep_ms, sleep_us

# Bits del PCF8574 tal y como los cablean estos modulos
_RS = 0x01          # 0 = comando, 1 = caracter
_EN = 0x04          # pulso de validacion
_LUZ = 0x08         # retroiluminacion

_LIMPIAR = 0x01
_INICIO = 0x02
_MODO_ENTRADA = 0x04
_CONTROL = 0x08
_FUNCION = 0x20

# La pantalla no tiene acentos: se sustituyen por la letra sin tilde
_SIN_TILDE = {
    "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
    "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N",
    "¿": "?", "¡": "!", "·": "-", "—": "-", "–": "-", "«": '"', "»": '"',
}


def limpiar_texto(t):
    return "".join(_SIN_TILDE.get(c, c) for c in t)


class LCD:
    def __init__(self, i2c, direccion=0x27, columnas=16, filas=2):
        self.i2c = i2c
        self.dir = direccion
        self.columnas = columnas
        self.filas = filas
        self.luz = _LUZ
        self._iniciar()

    # --- capa baja --------------------------------------------------------- #
    def _enviar(self, dato):
        self.i2c.writeto(self.dir, bytes([dato | self.luz]))

    def _pulso(self, dato):
        self._enviar(dato | _EN)
        sleep_us(500)
        self._enviar(dato & ~_EN)
        sleep_us(100)

    def _escribir4(self, dato):
        self._enviar(dato)
        self._pulso(dato)

    def _escribir(self, dato, modo=0):
        """La pantalla va en modo de 4 bits: cada byte se manda en dos mitades."""
        self._escribir4(modo | (dato & 0xF0))
        self._escribir4(modo | ((dato << 4) & 0xF0))

    # --- arranque ---------------------------------------------------------- #
    def _iniciar(self):
        sleep_ms(50)
        for _ in range(3):          # secuencia de despertar del HD44780
            self._escribir4(0x30)
            sleep_ms(5)
        self._escribir4(0x20)       # a partir de aqui, 4 bits
        sleep_ms(5)

        self._escribir(_FUNCION | 0x08)          # 2 lineas, fuente 5x8
        self._escribir(_CONTROL | 0x04)          # pantalla encendida, sin cursor
        self._escribir(_MODO_ENTRADA | 0x02)     # escribe hacia la derecha
        self.limpiar()

    # --- uso normal -------------------------------------------------------- #
    def limpiar(self):
        self._escribir(_LIMPIAR)
        sleep_ms(2)

    def cursor(self, columna, fila):
        salto = [0x00, 0x40, 0x14, 0x54]
        self._escribir(0x80 | (salto[fila] + columna))

    def escribir(self, texto, fila=0):
        """Escribe una linea entera, rellenando con espacios lo que sobre."""
        texto = limpiar_texto(str(texto))[: self.columnas]
        # MicroPython no trae str.ljust, asi que el relleno se hace a mano
        texto = texto + " " * (self.columnas - len(texto))
        self.cursor(0, fila)
        for c in texto:
            self._escribir(ord(c), _RS)

    def mostrar(self, linea1="", linea2=""):
        self.escribir(linea1, 0)
        if self.filas > 1:
            self.escribir(linea2, 1)

    def encender_luz(self, encendida=True):
        self.luz = _LUZ if encendida else 0
        self._enviar(0)


def buscar(i2c):
    """Direccion I2C de la pantalla. Estos modulos usan 0x27 o 0x3F."""
    encontrados = i2c.scan()
    for candidata in (0x27, 0x3F):
        if candidata in encontrados:
            return candidata
    return encontrados[0] if encontrados else None
