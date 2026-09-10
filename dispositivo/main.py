"""Lector de la puerta: Raspberry Pi Pico W + RFID RC522.

Lee el llavero del alumno y avisa al servidor. Si no hay red, guarda el fichaje y
lo reenvia cuando vuelve, para que no se pierda ninguna entrada.

Copiar a la Pico W (con Thonny): este fichero como main.py, junto a mfrc522.py y
config.py. Al arrancar la Pico se ejecuta solo.
"""

import network
import ujson
import urequests
from machine import I2C, Pin
from utime import sleep, sleep_ms, ticks_diff, ticks_ms

import config
import mfrc522

led = Pin("LED", Pin.OUT)          # el LED de la propia Pico W
PENDIENTES = "pendientes.json"     # fichajes que no se pudieron enviar
SERVIDOR_GUARDADO = "servidor.txt"  # ultima direccion del servidor que funciono
_servidor = ""

# La pantalla es opcional: si no esta conectada, todo funciona igual pero sin ella.
pantalla = None


def abrir_pantalla():
    """Devuelve la pantalla LCD, o None si no hay ninguna conectada."""
    try:
        import lcd

        i2c = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)
        direccion = lcd.buscar(i2c)
        if direccion is None:
            print("Sin pantalla LCD (no hay nada en el bus I2C)")
            return None
        p = lcd.LCD(i2c, direccion)
        print("Pantalla LCD en 0x%02X" % direccion)
        return p
    except Exception as e:
        print("Sin pantalla LCD:", e)
        return None


def decir(linea1, linea2="", segundos=0):
    """Escribe en la pantalla si la hay, y opcionalmente vuelve al reposo."""
    if pantalla is None:
        return
    try:
        pantalla.mostrar(linea1, linea2)
        if segundos:
            sleep(segundos)
            reposo()
    except Exception as e:
        print("La pantalla ha fallado:", e)


def reposo():
    if pantalla is not None:
        try:
            pantalla.mostrar("   ON STAGE", " Pasa tu llavero")
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Senales con el LED (mientras no haya pantalla)
# --------------------------------------------------------------------------- #
def parpadeo(veces, ms=120):
    for _ in range(veces):
        led.on()
        sleep_ms(ms)
        led.off()
        sleep_ms(ms)


def senal(resultado):
    if resultado == "ok":
        led.on(); sleep_ms(600); led.off()      # fijo: bienvenido
    elif resultado == "aviso":
        parpadeo(2)                             # dos: entra, pero algo que mirar
    else:
        parpadeo(5, 60)                         # rafaga: no se ha podido


# --------------------------------------------------------------------------- #
# Red
# --------------------------------------------------------------------------- #
def conectar_wifi(espera=20):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan
    print("Conectando a", config.WIFI_SSID)
    wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
    for _ in range(espera * 2):
        if wlan.isconnected():
            print("WiFi OK:", wlan.ifconfig()[0])
            return wlan
        led.toggle()
        sleep_ms(500)
    led.off()
    print("Sin WiFi")
    return wlan


def responde(url):
    """True si en esa direccion esta nuestro servidor (y no otra cosa cualquiera)."""
    try:
        r = urequests.get(url.rstrip("/") + "/api/horario")
        try:
            return r.status_code == 200 and "salas" in r.text[:200]
        finally:
            r.close()
    except Exception:
        return False


def buscar_servidor():
    """Recorre la red buscando el servidor.

    El PC coge la IP por DHCP, asi que el router puede darle otra distinta un dia
    cualquiera. En vez de dejar el lector muerto, se busca por toda la red y se
    guarda la que funcione.
    """
    import socket

    w = network.WLAN(network.STA_IF)
    if not w.isconnected():
        return None
    base = w.ifconfig()[0].rsplit(".", 1)[0]
    print("Buscando el servidor en", base + ".x")
    decir("Buscando", "el servidor...")

    for i in range(1, 255):
        ip = "%s.%d" % (base, i)
        s = socket.socket()
        s.settimeout(0.12)
        abierto = False
        try:
            s.connect((ip, 8000))
            abierto = True
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
        if abierto:
            url = "http://%s:8000" % ip
            if responde(url):
                print("Servidor encontrado en", url)
                try:
                    with open(SERVIDOR_GUARDADO, "w") as f:
                        f.write(url)
                except Exception:
                    pass
                return url
    print("No se ha encontrado el servidor en la red")
    return None


def servidor():
    """Direccion del servidor: la guardada si la hay, si no la del config."""
    global _servidor
    if _servidor:
        return _servidor
    try:
        with open(SERVIDOR_GUARDADO) as f:
            guardada = f.read().strip()
        if guardada.startswith("http"):
            _servidor = guardada
            return _servidor
    except Exception:
        pass
    _servidor = config.SERVIDOR
    return _servidor


def revisar_servidor():
    """Comprueba que el servidor sigue donde estaba; si no, lo busca."""
    global _servidor
    if responde(servidor()):
        return True
    otro = buscar_servidor()
    if otro:
        _servidor = otro
        return True
    return False


def enviar(uid):
    """Manda un fichaje. Devuelve el texto a mostrar, o None si no hubo red."""
    try:
        r = urequests.post(
            servidor().rstrip("/") + "/api/fichaje",
            headers={"Content-Type": "application/json", "X-Device-Key": config.DEVICE_KEY},
            data=ujson.dumps({"uid": uid, "dispositivo": config.NOMBRE}),
        )
        try:
            if r.status_code != 200:
                print("HTTP", r.status_code, r.text[:120])
                return {"ok": False, "mensaje": "Error del servidor"}
            return r.json()
        finally:
            r.close()
    except Exception as e:
        print("Sin conexion:", e)
        return None


# --------------------------------------------------------------------------- #
# Cola para cuando se cae la red
# --------------------------------------------------------------------------- #
def guardar_pendiente(uid):
    cola = leer_pendientes()
    cola.append(uid)
    try:
        with open(PENDIENTES, "w") as f:
            ujson.dump(cola[-200:], f)     # no crecer sin limite
    except Exception as e:
        print("No se pudo guardar el pendiente:", e)


def leer_pendientes():
    try:
        with open(PENDIENTES) as f:
            return ujson.load(f)
    except Exception:
        return []


def reenviar_pendientes():
    cola = leer_pendientes()
    if not cola:
        return
    print("Reenviando", len(cola), "fichajes guardados")
    quedan = []
    for uid in cola:
        if enviar(uid) is None:
            quedan.append(uid)
    try:
        with open(PENDIENTES, "w") as f:
            ujson.dump(quedan, f)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Bucle principal
# --------------------------------------------------------------------------- #
def main():
    global pantalla
    print("Lector", config.NOMBRE, "->", config.SERVIDOR)

    pantalla = abrir_pantalla()
    decir("   ON STAGE", "  arrancando...")

    conectar_wifi()
    if not revisar_servidor():
        decir("Sin servidor", "Sigo intentando", 3)
    reenviar_pendientes()
    lector = mfrc522.crear()

    # Aviso claro si el RC522 no responde: es el fallo mas comun al montarlo
    if not lector.conectado():
        print("AVISO: el lector no responde (VersionReg = 0x%02X)." % lector.version())
        print("Revisa los siete cables; sigo funcionando por si lo conectas ahora.")
        parpadeo(10, 60)
        decir("Lector KO", "Revisa cables", 4)

    reposo()

    ultimo_uid = ""
    ultimo_ms = 0
    ultimo_reintento = ticks_ms()

    presente = ""            # tarjeta apoyada ahora mismo en el lector
    ciclos_sin_tarjeta = 0

    while True:
        # Una tarjeta apoyada se lee varias veces por segundo. Solo cuenta como
        # fichaje nuevo cuando antes se ha retirado: si no, quien deja el llavero
        # encima ficha una y otra vez. Otra tarjeta distinta si entra al momento,
        # que en la puerta la gente pasa una detras de otra.
        estado, _ = lector.detectar()

        if estado != mfrc522.OK:
            ciclos_sin_tarjeta += 1
            if ciclos_sin_tarjeta > 8:      # ~1,2 s sin ver nada = retirada
                presente = ""
        else:
            ciclos_sin_tarjeta = 0
            estado, uid = lector.uid()
            if estado == mfrc522.OK:
                texto = mfrc522.uid_a_texto(uid)
                rebote = texto == ultimo_uid and ticks_diff(ticks_ms(), ultimo_ms) < 2000
                if texto != presente and not rebote:
                    presente = texto
                    ultimo_uid, ultimo_ms = texto, ticks_ms()
                    print("Tarjeta", texto)
                    decir("Leyendo...", "")
                    respuesta = enviar(texto)

                    if respuesta is None:
                        guardar_pendiente(texto)
                        senal("error")
                        decir("Sin conexion", "Quedas apuntado", 3)

                    elif respuesta.get("ok"):
                        print(" ", respuesta.get("mensaje"))
                        senal("ok" if respuesta.get("previsto") else "aviso")
                        nombre = respuesta.get("nombre", "").split(" ")[0]
                        if respuesta.get("tipo") == "salida":
                            saldo = respuesta.get("saldo")
                            if respuesta.get("con_bono") and saldo is not None:
                                decir("Hasta luego " + nombre[:4],
                                      "Te quedan %d" % saldo, 4)
                            else:
                                decir("Hasta luego", nombre, 3)
                            continue
                        if respuesta.get("repetido"):
                            segunda = "Ya fichado " + respuesta.get("entrada", "")
                        elif respuesta.get("clase"):
                            segunda = respuesta["clase"]
                            if not respuesta.get("previsto"):
                                segunda = "No te apuntaste"
                        else:
                            segunda = "Fuera de horario"
                        decir("Hola " + nombre, segunda, 4)

                    else:
                        print(" ", respuesta.get("mensaje"))
                        senal("aviso")
                        motivo = respuesta.get("motivo")
                        if motivo == "sin_saldo":
                            decir("Bono agotado", "Ve a recepcion", 5)
                        elif motivo == "desconocida":
                            decir("Tarjeta nueva", "Ve a recepcion", 4)
                        elif motivo == "baja":
                            decir("Estas de baja", "Habla con Sergio", 4)
                        else:
                            decir("No ha podido ser", "Prueba otra vez", 4)

        # Cada 2 minutos: mirar la red y vaciar la cola si hay algo
        if ticks_diff(ticks_ms(), ultimo_reintento) > 120_000:
            ultimo_reintento = ticks_ms()
            wlan = network.WLAN(network.STA_IF)
            if not wlan.isconnected():
                conectar_wifi(espera=10)
            elif leer_pendientes():
                # Si hay cola es que algo falla: puede que el PC haya cambiado de IP
                if revisar_servidor():
                    reenviar_pendientes()
                    reposo()

        sleep_ms(150)


try:
    main()
except Exception as e:
    # Si algo revienta, dejar rastro y parpadear en vez de quedarse mudo
    print("ERROR:", e)
    try:
        with open("error.log", "a") as f:
            f.write(str(e) + "\n")
    except Exception:
        pass
    while True:
        parpadeo(3, 80)
        sleep(2)
