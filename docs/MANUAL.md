# Manual de operación

> Guía de uso diario del sistema de asistencia. Para la descripción del proyecto,
> vuelve al [README](../README.md).

Sistema para saber **cuánta gente va a cada clase y en qué proporción hombres/mujeres**.

El circuito completo:

1. El bot manda por WhatsApp a cada alumno un enlace personal.
2. El alumno abre el enlace en el móvil y ve **el horario del día como una rejilla táctil**
   (los mismos colores del cartel). Toca las horas a las que va y confirma.
3. La escuela ve en su panel, en tiempo real, cuántos hombres y cuántas mujeres hay en
   cada clase, con aviso cuando la clase está descompensada.
4. A la hora que quieras, el WhatsApp de empresa recibe el resumen del día.

## Coste: 0 €

Todo el sistema funciona gratis y sin dar de alta ninguna tarjeta:

| Pieza | Cómo se resuelve gratis |
|---|---|
| Servidor y base de datos | tu propio PC, con Python y un fichero SQLite |
| Dirección pública en internet | túnel de Cloudflare (`.\publicar.ps1`), sin cuenta ni tarjeta |
| Envío de los WhatsApp | modo `manual`: enlaces que abren tu WhatsApp con el texto escrito |
| Recepción del resumen | el mismo WhatsApp de la escuela |

Lo único de pago en todo el proyecto es **opcional**: la Cloud API de Meta (§3), que quita los
clics del envío. Mientras `WA_MODE=manual`, no hay ninguna factura en ninguna parte.

---

## 1. Puesta en marcha (5 minutos)

Abre PowerShell en esta carpeta y ejecuta:

```powershell
pip install -r requirements.txt
copy .env.example .env
notepad .env          # cambia ADMIN_KEY y TELEFONO_EMPRESA
.\run.ps1
```

Luego abre en el navegador:

| Página | Para qué | Quién entra |
|---|---|---|
| `http://localhost:8000/admin` | dar de alta alumnos | la escuela (con clave) |
| `http://localhost:8000/panel` | ver el recuento del día | la escuela (con clave) |
| `http://localhost:8000/a/<token>` | marcar las clases | cada alumno (enlace propio) |

### Verlo funcionando con datos inventados

```powershell
python scripts\demo.py
$env:DB_PATH="data\demo.db"; python -m uvicorn app.main:app --port 8000
```

Crea 22 alumnos y tres semanas de respuestas. El comando imprime un enlace de panel y
uno de alumno para que los abras directamente. Para borrarlo: `python scripts\demo.py --limpiar`.

---

## 2. Dar de alta a los alumnos

Desde `/admin` uno a uno, o de golpe con un CSV (`nombre,telefono,sexo`):

```powershell
python scripts\importar_alumnos.py scripts\alumnos_ejemplo.csv
```

Cada alumno recibe un **token permanente**. Su enlace no caduca: el mismo sirve todos los
días. El sexo se guarda una vez en el alta, así que el alumno nunca tiene que indicarlo.

---

## 3. El envío por WhatsApp: dos modos

Se elige con `WA_MODE` en `.env`.

### Modo `manual` (por defecto, gratis, funciona hoy mismo)

No necesita nada de Meta. `python scripts\enviar_encuesta.py` abre una página con un botón
por alumno; al pulsarlo se abre WhatsApp con el mensaje y su enlace ya escritos, y solo hay
que darle a enviar. Los botones ya pulsados se quedan en gris.

Los mismos botones están en el panel, en «Pedir asistencia».

- **A favor:** cero coste, cero papeleo, se puede usar con el WhatsApp normal de la escuela.
- **En contra:** hay que pulsar (unos segundos por alumno, una vez al día).

### Modo `cloud` (envío 100 % automático)

Usa la **WhatsApp Cloud API** de Meta. Requiere:

1. Cuenta en [Meta for Developers](https://developers.facebook.com) → app de tipo Business.
2. Añadir el producto WhatsApp y un número de teléfono **que no esté en la app normal de WhatsApp**.
3. Crear una plantilla llamada `recordatorio_clase`, categoría *Utility*, en español:

   > Hola {{1}}, ¿a qué clases vienes el {{2}}? Marca tus horas aquí: {{3}}

   Meta tarda entre minutos y 24 h en aprobarla.
4. Rellenar en `.env`: `WA_MODE=cloud`, `WA_TOKEN`, `WA_PHONE_ID`.
5. Webhook (opcional, para responder a quien escriba): apuntar a `https://tudominio/wa/webhook`
   con el token de `WA_VERIFY_TOKEN`.

Coste orientativo: las conversaciones de servicio son gratuitas y las de utilidad cuestan
céntimos por conversación de 24 h. Con 60 alumnos y 5 días a la semana está en el entorno
de unos pocos euros al mes.

> **Importante:** fuera de la ventana de 24 h desde la última respuesta del alumno, Meta
> solo deja enviar plantillas aprobadas. Por eso el envío diario usa plantilla y las
> respuestas del webhook usan texto libre.

---

## 4. El resumen a la empresa

```powershell
python scripts\resumen_diario.py
```

Genera y envía este mensaje al número de `TELEFONO_EMPRESA`:

```
📋 ON STAGE · lunes 31/8

🟡 19:00 S1 · Latinos Nivel 3
    2H / 4M · total 6  ← faltan chicos
🟢 21:00 S2 · Bachata Lady's Style
    4H / 5M · total 9
🔴 21:00 S1 · Latinos Iniciación 0
    2H / 8M · total 10  ← faltan chicos

TOTAL DÍA: 15H / 21M (36 asistencias)
Sin contestar: 2 alumnos
Panel: http://.../panel?key=...&d=2026-08-31
```

El semáforo sale de `UMBRAL_AMBAR` y `UMBRAL_ROJO` en `.env` (diferencia entre hombres y
mujeres): por defecto 🟢 menos de 2, 🟡 de 2 a 3, 🔴 4 o más.

---

## 5. Que funcione solo, sin ventanas abiertas

```powershell
.\programar_tareas.ps1          # datos reales
.\programar_tareas.ps1 -Demo    # con la base de demostración
```

Crea tres tareas en el Programador de tareas de Windows:

| Tarea | Cuándo | Qué hace |
|---|---|---|
| `OnStage-Publicar` | al iniciar sesión | mantiene el servidor y el túnel encendidos |
| `OnStage-Preguntar` | 12:00, L-V | pide la asistencia del día |
| `OnStage-Resumen` | 18:00, L-V | manda el recuento a la empresa |

Las horas se cambian con `-HoraPreguntar 11:00 -HoraResumen 17:30`; se quitan todas con
`-Quitar`. Como las lanza Windows y no tu terminal, **sobreviven a cerrar la consola, a cerrar
sesión y a reiniciar el ordenador**. No hacen falta permisos de administrador.

`OnStage-Publicar` se reintenta sola cada 2 minutos si el script se cae, y el propio script
comprueba cada minuto que la dirección pública responda: si no, cierra el túnel y abre otro
(tarda unos 2 minutos en recuperarse). Cuando eso pasa la dirección cambia, así que los
enlaces ya enviados dejan de valer — vuelve a mandar la encuesta con `enviar_encuesta.py`.

---

## 6. Ponerlo en internet — coste 0 €

Con `BASE_URL=http://localhost:8000` los enlaces **solo funcionan en tu ordenador**. Para que
los alumnos los abran desde su móvil hace falta una dirección pública. Un solo comando:

```powershell
.\publicar.ps1
```

Descarga [cloudflared](https://developers.cloudflare.com/cloudflared/) la primera vez (50 MB),
limpia lo que hubiera de antes, arranca el servidor, abre el túnel, **lo vigila y lo reabre
solo si se cae**, y te enseña la dirección pública ya montada:

```
   YA ESTA EN INTERNET - coste 0 EUR

   Panel de empresa:
   https://algo-al-azar.trycloudflare.com/panel?key=TU_CLAVE
```

**Gratis de verdad:** sin tarjeta, sin cuenta, sin límite de tiempo ni de visitas. Es un
servicio que Cloudflare da abierto. `.\publicar.ps1 -Demo` hace lo mismo con datos de prueba.

### Lo que hay que saber

- **La dirección cambia en cada arranque.** No importa para el uso normal: el mensaje de
  WhatsApp se envía cada día con la dirección de ese día. La app la lee de `data/base_url.txt`
  en caliente, así que no hay que tocar el `.env` ni reiniciar nada.
- **Manda la encuesta con el túnel abierto**, y déjalo abierto hasta que acaben las clases.
  Si lo cierras, los enlaces ya enviados dejan de abrir.
- **El PC tiene que estar encendido** mientras dure.
- **Si cierras la ventana, se apaga todo.** Por eso lo normal no es lanzarlo a mano, sino
  dejarlo como tarea de Windows (§5): así lo arranca el sistema al iniciar sesión, sin ventana
  que cerrar por accidente, y se reintenta solo si algo falla.

### Encender, apagar y comprobar

| Quiero… | Comando |
|---|---|
| ver si está encendido y con qué enlaces | `.\ver_enlaces.ps1` |
| encenderlo | `Start-ScheduledTask OnStage-Publicar` |
| apagarlo del todo | `.\parar.ps1` |

Usa `.\parar.ps1` y no solo `Stop-ScheduledTask`: parar la tarea mata el script pero **deja
vivos al servidor y al túnel**, que se quedan ocupando el puerto 8000 e impiden el siguiente
arranque. `parar.ps1` los remata; `publicar.ps1` también limpia restos al arrancar.

### Si quieres que funcione con el PC apagado

Ahí sí entra dinero o trabajo extra. Las opciones honestas:

| Opción | Coste | Pega |
|---|---|---|
| Dejar el PC encendido con `publicar.ps1` | 0 € | luz; dirección nueva cada arranque |
| Cuenta gratis de Cloudflare + dominio propio | ~10 €/año el dominio | dirección **fija**, se configura una vez |
| VPS pequeño (Hetzner, Ionos…) | 4-5 €/mes | hay que administrarlo |

Los planes gratuitos de Render y Vercel **no sirven aquí**: borran el disco al reiniciar y se
llevarían por delante la base de datos. Si algún día quieres la opción del dominio propio,
dímelo y la dejo montada.

---

## 7. Cambiar el horario

Todo el horario está en [`app/horario.py`](../app/horario.py), en la lista `_FILAS`, con el
formato `(día, hora, sala, baile, nivel, nota)`. Día 1 = lunes. Al editarlo cambian a la vez
la vista del alumno, el panel y los resúmenes; el histórico de clases que desaparezcan se
conserva en la base pero deja de mostrarse.

---

## 8. Detalles que igual no esperas

- **Cambiar de opinión:** el alumno puede reabrir su enlace y modificar la selección; se
  guarda la última. «Hoy no voy» también se registra, y así el panel distingue entre
  «ha dicho que no» y «no ha contestado».
- **Elegir otro día:** en la barra de arriba el alumno puede marcar toda la semana de una vez.
- **A quién avisar:** al pulsar una clase en el panel sale la lista nominal por sexo y, si
  está descompensada, los alumnos del sexo que falta que suelen ir a esa clase y hoy no han
  confirmado — con su botón de WhatsApp listo. Se calcula con las últimas 6 semanas.
- **Seguridad:** el panel y el alta van con la clave de `ADMIN_KEY`; cada alumno solo puede
  ver y tocar lo suyo mediante su token. No hay contraseñas de alumno que gestionar.
- **Datos personales:** guardas nombre, teléfono, sexo y asistencia. Con el RGPD delante,
  avisa a los alumnos de para qué es y borra al que se dé de baja (botón *Borrar* en `/admin`,
  que elimina también su histórico).

---

## Estructura

```
app/horario.py     el horario del cartel (lo único que se toca a menudo)
app/db.py          SQLite: alumnos, asistencias, recuentos, sugerencias
app/whatsapp.py    textos de los mensajes y envío (manual / cloud)
app/main.py        API y páginas
web/               las tres pantallas: alumno, panel y admin
scripts/           enviar encuesta, resumen, importar CSV, demo
data/              la base de datos (no la borres)
```
