/* Panel de empresa: recuento H/M por clase, avisos de descompensacion y envios. */
(() => {
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);

  let clave = params.get("key") || localStorage.getItem("onstage_key") || "";
  let fecha = params.get("d") || new Date().toLocaleDateString("sv");
  let temporizador = null;

  $("fecha").value = fecha;

  function api(ruta, opciones = {}) {
    const sep = ruta.includes("?") ? "&" : "?";
    return fetch(`${ruta}${sep}key=${encodeURIComponent(clave)}`, opciones);
  }

  async function cargar() {
    if (!clave) return pedirClave();
    const r = await api(`/api/panel?d=${fecha}`);
    if (r.status === 401) return pedirClave(true);
    if (!r.ok) {
      $("contenido").textContent = "Error al cargar el panel.";
      return;
    }
    localStorage.setItem("onstage_key", clave);
    $("acceso").hidden = true;
    pintar(await r.json());
    const envios = await (await api(`/api/envios?d=${fecha}`)).json();
    pintarEnvios(envios);
  }

  function pedirClave(fallo) {
    clearInterval(temporizador);
    $("acceso").hidden = false;
    $("contenido").innerHTML = "";
    if (fallo) $("acceso").querySelector(".nota").textContent = "Clave incorrecta. Vuelve a intentarlo.";
  }

  function pintar(d) {
    const t = d.totales;
    const dif = Math.abs(t.hombres - t.mujeres);

    const tarjetas = `
      <div class="tarjetas">
        <div class="tarjeta"><div class="num">${t.asistencias}</div><div class="eti">Asistencias</div></div>
        <div class="tarjeta"><div class="num" style="color:#93bdf0">${t.hombres}</div><div class="eti">Hombres</div></div>
        <div class="tarjeta"><div class="num" style="color:#eda3ce">${t.mujeres}</div><div class="eti">Mujeres</div></div>
        <div class="tarjeta"><div class="num">${dif}</div><div class="eti">Descuadre</div></div>
        <div class="tarjeta"><div class="num">${t.han_contestado}/${t.alumnos_activos}</div><div class="eti">Han contestado</div></div>
      </div>`;

    // Si el dia elegido esta vacio pero hay confirmaciones cerca, decirlo: es muy
    // facil quedarse mirando una fecha sin datos creyendo que no se ha guardado nada.
    const otros = (d.dias_con_datos || [])
      .filter((x) => x.fecha !== d.fecha)
      .sort((a, b) => Math.abs(new Date(a.fecha) - new Date(d.fecha)) - Math.abs(new Date(b.fecha) - new Date(d.fecha)))
      .slice(0, 6)
      .sort((a, b) => a.fecha.localeCompare(b.fecha));
    const aviso =
      t.asistencias === 0 && otros.length
        ? `<div class="hecho" style="background:rgba(217,154,43,.14);border-color:rgba(217,154,43,.4);color:#f0c473;text-align:left">
             Ese día no hay nadie apuntado todavía. Sí hay confirmaciones en:
             <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">
               ${otros
                 .map(
                   (x) =>
                     `<button class="boton secundario ir-dia" data-f="${x.fecha}">${x.fecha
                       .split("-")
                       .reverse()
                       .join("/")} · ${x.asistencias}</button>`
                 )
                 .join("")}
             </div>
           </div>`
        : "";

    const filas = d.clases.length
      ? d.clases
          .map(
            (c) => `<button class="fila-clase ${c.estado}" data-id="${c.id}">
              <span class="hora">${c.hora}</span>
              <span>
                <span class="baile">${escapar(c.etiqueta)}</span>
                <div class="meta">Sala ${c.sala} · ${escapar(c.profe)}${
              c.falta_sexo && c.estado !== "ok"
                ? ` · <b style="color:var(--ambar)">faltan ${c.falta_sexo === "H" ? "chicos" : "chicas"}</b>`
                : ""
            }</div>
              </span>
              <span class="conteo">
                <span class="pastilla h">${c.hombres} H</span>
                <span class="pastilla m">${c.mujeres} M</span>
                <span class="pastilla t">${c.total}</span>
              </span>
            </button>`
          )
          .join("")
      : "<p class='nota'>Ese día no hay clases en el horario.</p>";

    $("contenido").className = "";
    $("contenido").innerHTML = `
      ${tarjetas}
      <div class="seccion">
        <h2>${escapar(d.dia_nombre)} ${fecha.split("-").reverse().join("/")}</h2>
        ${aviso}
        ${filas}
      </div>
      <div class="seccion">
        <h2>Resumen para el WhatsApp de empresa</h2>
        <pre class="nota" style="white-space:pre-wrap;background:rgba(22,16,15,.75);padding:14px;border-radius:12px;border:1px solid rgba(227,193,105,.18)">${escapar(
          d.resumen_texto
        )}</pre>
        <div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap">
          <a class="boton" href="${d.enlace_resumen_wa}" target="_blank" rel="noopener">Enviar por WhatsApp</a>
          <button class="boton secundario" id="copiar">Copiar texto</button>
        </div>
      </div>
      <div class="seccion" id="zona-envios"></div>`;

    $("contenido").querySelectorAll(".fila-clase").forEach((b) => {
      b.addEventListener("click", () => abrirClase(b.dataset.id));
    });
    $("contenido").querySelectorAll(".ir-dia").forEach((b) => {
      b.addEventListener("click", () => {
        fecha = b.dataset.f;
        $("fecha").value = fecha;
        history.replaceState(null, "", `/panel?d=${fecha}`);
        cargar();
      });
    });
    $("copiar").addEventListener("click", () => {
      navigator.clipboard.writeText(d.resumen_texto);
      $("copiar").textContent = "✓ Copiado";
      setTimeout(() => ($("copiar").textContent = "Copiar texto"), 1500);
    });
  }

  function pintarEnvios(e) {
    const zona = $("zona-envios");
    if (!zona) return;
    if (!e.destinatarios.length) {
      zona.innerHTML = "<h2>Pedir asistencia</h2><p class='nota'>Han contestado todos los alumnos activos.</p>";
      return;
    }
    const modo =
      e.modo === "cloud"
        ? `<button class="boton" id="enviar-todos">Enviar a los ${e.destinatarios.length} pendientes</button>`
        : `<p class="nota">Modo manual: pulsa cada nombre y se abre WhatsApp con el mensaje ya escrito.</p>`;
    zona.innerHTML = `<h2>Pedir asistencia · ${e.destinatarios.length} sin contestar</h2>${modo}
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
        ${e.destinatarios
          .map(
            (a) =>
              `<a class="boton secundario" href="${a.enlace_wa}" target="_blank" rel="noopener">${escapar(
                a.nombre
              )} <span style="opacity:.6">${a.sexo}</span></a>`
          )
          .join("")}
      </div>`;
    const btn = $("enviar-todos");
    if (btn)
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Enviando…";
        const r = await api(`/api/enviar?d=${fecha}`, { method: "POST" });
        const j = await r.json();
        btn.textContent = r.ok ? `✓ Enviados ${j.enviados}` : `Error: ${j.detail || "revisa la configuración"}`;
      });
  }

  async function abrirClase(id) {
    const r = await api(`/api/clase/${id}?d=${fecha}`);
    const d = await r.json();
    const lista = (sexo) =>
      d.asistentes.filter((a) => a.sexo === sexo).map((a) => escapar(a.nombre)).join("<br>") ||
      "<span style='opacity:.5'>nadie</span>";
    const sug = d.sugerencias.length
      ? `<h2 style="margin-top:18px">A quién avisar</h2>
         <p class="nota">Suelen venir a esta clase y hoy no han confirmado:</p>
         <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">
           ${d.sugerencias
             .map(
               (s) =>
                 `<a class="boton secundario" target="_blank" rel="noopener"
                    href="https://wa.me/${s.telefono}?text=${encodeURIComponent(
                   `¡Hola ${s.nombre.split(" ")[0]}! Hoy hay hueco en ${d.clase.etiqueta} de las ${d.clase.hora}. ¿Te animas? 💃`
                 )}">${escapar(s.nombre)} · ${s.veces}×</a>`
             )
             .join("")}
         </div>`
      : "";

    $("detalle").innerHTML = `
      <h2 style="color:var(--oro);letter-spacing:.1em;text-transform:uppercase;font-size:13px;margin:0 0 4px">
        ${d.clase.hora} · Sala ${d.clase.sala}
      </h2>
      <p style="font-size:19px;font-weight:700;margin:0 0 14px">${escapar(d.clase.etiqueta)}</p>
      <table class="tabla"><tr><th>Hombres</th><th>Mujeres</th></tr>
        <tr style="vertical-align:top"><td>${lista("H")}</td><td>${lista("M")}</td></tr></table>
      ${sug}
      <button class="boton" style="margin-top:18px;width:100%" onclick="this.closest('dialog').close()">Cerrar</button>`;
    $("detalle").showModal();
  }

  $("fecha").addEventListener("change", (e) => {
    fecha = e.target.value;
    history.replaceState(null, "", `/panel?d=${fecha}`);
    cargar();
  });
  $("hoy").addEventListener("click", () => {
    fecha = new Date().toLocaleDateString("sv");
    $("fecha").value = fecha;
    cargar();
  });
  $("entrar").addEventListener("click", () => {
    clave = $("clave").value.trim();
    cargar();
  });
  $("clave").addEventListener("keydown", (e) => e.key === "Enter" && $("entrar").click());
  $("ir-admin").addEventListener("click", () => localStorage.setItem("onstage_key", clave));

  function escapar(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  cargar();
  temporizador = setInterval(() => {
    if (!document.hidden && clave && $("acceso").hidden) cargar();
  }, 30000);
})();