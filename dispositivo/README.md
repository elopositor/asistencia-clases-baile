# Lector de la puerta — Raspberry Pi Pico W + RFID RC522

Cada alumno lleva un llavero. Lo acerca al lector al entrar y el sistema apunta que
ha venido de verdad, no solo que dijo que vendría.

## Qué hace falta

| Pieza | Notas |
|---|---|
| Raspberry Pi Pico W | la **W** es imprescindible: es la que lleva WiFi |
| Módulo RFID RC522 | viene con una tarjeta y un llavero |
| LCD 1602 con adaptador I2C | opcional, para que el alumno vea que ha fichado |
| Cables jumper hembra-hembra | 7 para el lector, 4 más si pones pantalla |
| Soldador | los pines del RC522 vienen sueltos, hay que soldar la tira |
| Un llavero por alumno | los packs de 10 salen por unos 6 € |

## Cableado

El RC522 trabaja a **3,3 V**. La Pico también, así que se conectan directos.
Nunca lo alimentes a 5 V: se estropea.

| RC522 | Pico W | Pin físico |
|---|---|---|
| SDA (SS) | GP1 | 2 |
| SCK | GP2 | 4 |
| MOSI | GP3 | 5 |
| MISO | GP4 | 6 |
| GND | GND | 3 |
| RST | GP0 | 1 |
| 3.3V | 3V3(OUT) | 36 |
| IRQ | — | no se conecta |

Los siete cables van seguidos salvo el de alimentación: el pin 36 está en la otra
punta de la placa. Si cambias de pines, ajusta `mfrc522.crear()` en el código.

## Puesta en marcha

1. **MicroPython en la Pico W.** Descarga el `.uf2` de
   [micropython.org/download/RPI_PICO_W](https://micropython.org/download/RPI_PICO_W/).
   Conecta la Pico al PC con el USB **mientras mantienes pulsado el botón BOOTSEL**:
   aparece como una unidad USB. Copia el `.uf2` dentro y se reinicia sola.

2. **Thonny** ([thonny.org](https://thonny.org)), que es el editor con el que se
   copian ficheros a la placa. Abajo a la derecha, elige *MicroPython (Raspberry Pi Pico)*.

3. **Copia los tres ficheros** a la Pico (en Thonny: abrir el fichero → *Guardar como…*
   → *Raspberry Pi Pico*):
   - `mfrc522.py`
   - `main.py`
   - `config.ejemplo.py`, guardado **con el nombre `config.py`** y ya relleno.

4. **Rellena `config.py`**: el WiFi de la escuela (la Pico W solo va en 2,4 GHz), la
   IP del PC servidor y la `DEVICE_KEY`.

5. **En el servidor**, pon la misma clave en el `.env`:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(24))"   # genera una
   notepad .env                                                    # DEVICE_KEY=...
   .\publicar.ps1 -EnRed                                           # escuchar la red local
   ```

   Sin `-EnRed` el servidor solo se escucha a sí mismo y el lector no llega.

Al arrancar la Pico, el LED parpadea mientras busca WiFi y se queda apagado cuando
está lista.

## Cómo se usa

**Dar de alta un llavero**: pásalo por el lector. Como no es de nadie, el sistema lo
anota y aparece en `/admin`, en «Tarjetas sin asignar», con un desplegable para decir
de quién es. Se hace una vez por alumno.

**El día a día**: cada uno pasa su llavero al entrar. En el panel, cada clase muestra
`3/8 dentro`, y al abrirla se ve quién ha llegado, a qué hora, y quién ha entrado sin
haberse apuntado.

## Qué dice el LED

| Señal | Significado |
|---|---|
| Encendido fijo un segundo | fichado y estaba apuntado |
| Dos parpadeos | fichado, pero no se había apuntado (o repite fichaje) |
| Ráfaga de cinco | no se pudo enviar; queda guardado y se reintenta |
| Parpadeo continuo de tres | error grave, mira `error.log` en la placa |

## Si se va la red

Los fichajes se guardan en `pendientes.json` dentro de la propia Pico y se reenvían
cuando vuelve la conexión: se comprueba cada dos minutos, y también al arrancar. No se
pierde ninguna entrada mientras la Pico tenga corriente.

Cuando pasa, la pantalla avisa con **«Sin conexion / Quedas apuntado»**. No hay que hacer
nada: el fichaje llegará solo.

## Si deja de leer tarjetas

Casi siempre es lo mismo: **la placa se ha quedado sin ejecutar el programa**. Pasa cuando
alguien le copia ficheros o le habla por `mpremote`, porque eso la deja en modo consola y
`main.py` no vuelve a arrancar por su cuenta.

| Señal | Qué pasa |
|---|---|
| La pantalla no pone `Pasa tu llavero` | el programa no está corriendo |
| Pasas la tarjeta y no hace nada | lo mismo |

Se arregla de dos formas:

```powershell
python -m mpremote connect COM3 reset
```

o directamente **desenchufando y volviendo a enchufar** la Pico, que es lo más rápido y no
necesita ordenador. Al arrancar tarda unos segundos en conectar al WiFi; si fichas justo en
ese momento verás «Sin conexion», pero el fichaje se guarda igual.

> Después de copiar ficheros a la placa, **reiníciala siempre**. Si no, se queda muda.

## La pantalla (opcional)

Un LCD 1602 con adaptador I2C saluda al alumno por su nombre y le dice a qué clase ha
fichado. Si no la conectas, el sistema funciona igual: al arrancar la busca, no la
encuentra y sigue.

| LCD (módulo I2C) | Pico W | Pin físico |
|---|---|---|
| SDA | GP6 | 9 |
| SCL | GP7 | 10 |
| GND | GND | 8 |
| VCC | 3V3(OUT) | 36, **por un empalme** |

GP6 y GP7 son el bus I2C1, elegidos para no chocar con los cinco pines del lector.

**El pin 36 es el único de 3,3 V y el lector ya lo ocupa.** Hay que repartirlo: corta un
jumper, retuerce los tres extremos, suelda y aísla — te queda un cable con una pata y dos
salidas. Con la masa no hace falta, que hay ocho pines de GND.

**Nunca la alimentes con los 5 V del pin 40.** Se vería mejor, pero sus resistencias de
pull-up meterían 5 V en SDA y SCL, y las patas de la Pico solo aguantan 3,3.

Para comprobarla:

```powershell
python -m mpremote connect COM3 run probar_pantalla.py
```

Te dice en qué dirección responde (0x27 o 0x3F) y escribe mensajes de prueba. **Si no se
lee nada, casi siempre es el contraste**, que viene al mínimo: se sube con el potenciómetro
azul del módulo.

La pantalla no tiene acentos ni eñes; el driver los sustituye solo.

## Para más adelante

**Relé para abrir la puerta**. Lo tienes en el kit, pero hay que pensarlo antes: qué pasa
si se va la luz o cae la red. Una puerta que no abre es un problema de seguridad, no un
fallo de software.
