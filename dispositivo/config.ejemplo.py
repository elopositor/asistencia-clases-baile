"""Copia este fichero a la Pico W como  config.py  y rellena tus datos.

Ojo: config.py NO se sube a git (lleva la clave del WiFi y la del lector).
"""

# --- WiFi de la escuela -------------------------------------------------------
# La Pico W solo se conecta a redes de 2,4 GHz. Si tu router emite 2,4 y 5 GHz con
# el mismo nombre, normalmente funciona igual; si no, usa la red de 2,4.
WIFI_SSID = "WiFi-de-la-escuela"
WIFI_PASS = "la-contrasena"

# --- Servidor -----------------------------------------------------------------
# La IP del PC donde corre el sistema, dentro de la misma red que la Pico.
# En ese PC:  ipconfig    ->  "Direccion IPv4"
# Pon una IP fija al PC en el router, o el dia que cambie el lector dejara de fichar.
SERVIDOR = "http://192.168.1.50:8000"

# La misma cadena que pusiste en DEVICE_KEY dentro del .env del servidor
DEVICE_KEY = "pega-aqui-la-device-key"

# Nombre de este lector; sale en el registro de accesos
NOMBRE = "puerta"
