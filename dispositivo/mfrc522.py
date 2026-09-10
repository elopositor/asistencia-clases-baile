"""Driver minimo del lector RFID MFRC522 para MicroPython (Raspberry Pi Pico W).

Solo hace lo que necesitamos: detectar una tarjeta cerca y leer su UID. No lee ni
escribe los bloques de memoria de la tarjeta, que aqui no hacen falta.

Copiar este fichero a la Pico junto a main.py.
"""

from machine import Pin, SPI
from utime import sleep_ms

OK = 0
SIN_TARJETA = 1
ERROR = 2

# Comandos del chip
_IDLE = 0x00
_TRANSCEIVE = 0x0C
_RESET = 0x0F

# Comandos de la norma ISO14443
_REQIDL = 0x26
_ANTICOLL = 0x93


class MFRC522:
    def __init__(self, spi, gpioRst, gpioCs):
        self.spi = spi
        self.rst = Pin(gpioRst, Pin.OUT)
        self.cs = Pin(gpioCs, Pin.OUT)
        self.rst.value(0)
        self.cs.value(1)
        self.rst.value(1)
        self.init()

    # --- acceso a registros ------------------------------------------------ #
    def _escribir(self, reg, val):
        self.cs.value(0)
        self.spi.write(bytes([0xFF & ((reg << 1) & 0x7E), 0xFF & val]))
        self.cs.value(1)

    def _leer(self, reg):
        self.cs.value(0)
        self.spi.write(bytes([0xFF & (((reg << 1) & 0x7E) | 0x80)]))
        val = self.spi.read(1)
        self.cs.value(1)
        return val[0]

    def _poner_bits(self, reg, mascara):
        self._escribir(reg, self._leer(reg) | mascara)

    def _quitar_bits(self, reg, mascara):
        self._escribir(reg, self._leer(reg) & (~mascara))

    # --- ciclo de vida ----------------------------------------------------- #
    def init(self):
        self.reset()
        self._escribir(0x2A, 0x8D)   # TModeReg
        self._escribir(0x2B, 0x3E)   # TPrescalerReg
        self._escribir(0x2D, 30)     # TReloadReg bajo
        self._escribir(0x2C, 0)      # TReloadReg alto
        self._escribir(0x15, 0x40)   # TxASKReg: modulacion 100 % ASK
        self._escribir(0x11, 0x3D)   # ModeReg
        self.antena_on()

    def reset(self):
        self._escribir(0x01, _RESET)
        sleep_ms(50)

    def version(self):
        """Registro VersionReg: 0x91 o 0x92 si el lector responde.

        0x00 o 0xFF significan que no hay lector al otro lado (cable suelto, mal
        pin o los pines sin soldar).
        """
        return self._leer(0x37)

    def conectado(self):
        return self.version() not in (0x00, 0xFF)

    def antena_on(self, on=True):
        if on and ~(self._leer(0x14) & 0x03):
            self._poner_bits(0x14, 0x03)
        elif not on:
            self._quitar_bits(0x14, 0x03)

    # --- dialogo con la tarjeta -------------------------------------------- #
    def _hablar(self, comando, datos):
        recibido = []
        bits = irq_en = espera = n = 0

        if comando == _TRANSCEIVE:
            irq_en = 0x77
            espera = 0x30

        self._escribir(0x02, irq_en | 0x80)   # ComIEnReg
        self._quitar_bits(0x04, 0x80)         # ComIrqReg
        self._poner_bits(0x0A, 0x80)          # FIFOLevelReg: vaciar
        self._escribir(0x01, _IDLE)

        for byte in datos:
            self._escribir(0x09, byte)        # FIFODataReg
        self._escribir(0x01, comando)

        if comando == _TRANSCEIVE:
            self._poner_bits(0x0D, 0x80)      # BitFramingReg: iniciar envio

        # ~35 ms de margen: mas que de sobra para una tarjeta pegada al lector
        i = 2000
        while True:
            n = self._leer(0x04)
            i -= 1
            if not ((i != 0) and (not (n & 0x01)) and (not (n & espera))):
                break

        self._quitar_bits(0x0D, 0x80)

        if i == 0:
            return ERROR, recibido, bits

        if self._leer(0x06) & 0x1B:           # ErrorReg
            return ERROR, recibido, bits

        estado = OK
        if n & irq_en & 0x01:
            estado = SIN_TARJETA

        if comando == _TRANSCEIVE:
            n = self._leer(0x0A)
            ultimos = self._leer(0x0C) & 0x07
            bits = (n - 1) * 8 + ultimos if ultimos else n * 8
            n = 1 if n == 0 else (16 if n > 16 else n)
            for _ in range(n):
                recibido.append(self._leer(0x09))

        return estado, recibido, bits

    def detectar(self):
        """Devuelve (estado, tipo). OK si hay una tarjeta delante."""
        self._escribir(0x0D, 0x07)            # BitFramingReg
        estado, recibido, bits = self._hablar(_TRANSCEIVE, [_REQIDL])
        if (estado != OK) | (bits != 0x10):
            return ERROR, None
        return estado, recibido

    def uid(self):
        """Devuelve (estado, uid como lista de bytes)."""
        self._escribir(0x0D, 0x00)
        estado, recibido, _ = self._hablar(_TRANSCEIVE, [_ANTICOLL, 0x20])
        if estado != OK:
            return ERROR, None
        if len(recibido) != 5:
            return ERROR, None
        # El ultimo byte es la comprobacion (XOR de los cuatro anteriores)
        control = 0
        for i in range(4):
            control = control ^ recibido[i]
        if control != recibido[4]:
            return ERROR, None
        return OK, recibido[:4]


def crear(sck=2, mosi=3, miso=4, cs=1, rst=0):
    """Lector con el cableado que usa este proyecto (SPI0 de la Pico W)."""
    spi = SPI(0, baudrate=1_000_000, polarity=0, phase=0,
              sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
    return MFRC522(spi, rst, cs)


def uid_a_texto(uid):
    """[4, 162, 159, 27] -> '04A29F1B', que es como lo guarda el servidor."""
    return "".join("{:02X}".format(b) for b in uid)
