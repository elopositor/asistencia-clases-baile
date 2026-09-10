/* Alta y mantenimiento de alumnos. */
(() => {
  const $ = (id) => document.getElementById(id);
  let clave = new URLSearchParams(location.search).get("key") || localStorage.getItem("onstage_key") || "";

  const api = (ruta, opciones = {}) => {
    const sep = ruta.includes("?") ? "&" : "?";
    return fetch(`${ruta}${sep}key=${encodeURIComponent(clave)}`, {
      headers: { "Content-Type": "application/json" },
      ...opciones,
    });
  };

  async function cargar() {
    if (!clave) return ($("acceso").hidden = false);
    const r = await api("/api/alumnos");
    if (r.status === 401) {
      $("acceso").hidden = false;
      $("app").hidden = true;
      $("acceso").querySelector(".nota").textContent = "Clave incorrecta.";
      return;
    }
    localStorage.setItem("onstage_key", clave);
    $("acceso").hidden = true;
    $("app").hidden = false;
    pintar((await r.json()).alumnos);
    pintarTarjetas();
  }

  // Tarjetas que el lector ha visto y no son de nadie: se asignan con un clic
  async function pintarTarjetas() {
    const zona = $("tarjetas");
    if (!zona) return;
    const r = await api("/api/tarjetas");
    if (!r.ok) return;
    const { tarjetas } = await r.json();
    if (!tarjetas.length) {
      zona.innerHTML = "";
      return;
    }
    zona.innerHTML = `<h2>Tarjetas sin asignar</h2>
      <p class="nota">Pasa un llavero nuevo por el lector y aparecerá aquí. Elige de quién es.</p>
      ${tarjetas
        .map(
          (t) => `<div style="display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap">
            <code style="color:var(--oro);font-size:15px">${escapar(t.uid)}</code>
            <span class="nota">vista ${escapar(t.vista.replace("T", " "))}</span>
            <select class="campo asignar-a" data-uid="${escapar(t.uid)}">
              <option value="">— asignar a —</option>
              ${alumnosCache
                .map((a) => `<option value="${a.id}">${escapar(a.nombre)}</option>`)
                .join("")}
            </select>
          </div>`
        )
        .join("")}`;

    zona.querySelectorAll(".asignar-a").forEach((sel) => {
      sel.addEventListener("change", async (e) => {
        if (!e.target.value) return;
        const r = await api(`/api/alumnos/${e.target.value}/tarjeta`, {
          method: "POST",
          body: JSON.stringify({ uid: e.target.dataset.uid }),
        });
        const j = await r.json();
        $("aviso").textContent = r.ok ? `✓ Tarjeta de ${j.nombre}` : `⚠ ${j.detail}`;
        cargar();
      });
    });
  }

  let alumnosCache = [];

  function pintar(alumnos) {
    alumnosCache = alumnos;
    const h = alumnos.filter((a) => a.sexo === "H" && a.activo).length;
    const m = alumnos.filter((a) => a.sexo === "M" && a.activo).length;
    const conTarjeta = alumnos.filter((a) => a.tarjeta_uid).length;
    $("contador").textContent =
      `· ${h} hombres / ${m} mujeres activos` + (conTarjeta ? ` · ${conTarjeta} con tarjeta` : "");

    $("tabla").innerHTML =
      `<tr><th>Nombre</th><th>Teléfono</th><th>Sexo</th><th>Activo</th><th>Tarjeta</th><th>Último fichaje</th><th>Enlace</th><th></th></tr>` +
      alumnos
        .map(
          (a) => `<tr data-id="${a.id}" style="${a.activo ? "" : "opacity:.45"}">
            <td>${escapar(a.nombre)}</td>
            <td>+${a.telefono}</td>
            <td><select class="campo sexo" style="padding:5px 8px">
              <option value="H" ${a.sexo === "H" ? "selected" : ""}>H</option>
              <option value="M" ${a.sexo === "M" ? "selected" : ""}>M</option>
            </select></td>
            <td><input type="checkbox" class="activo" ${a.activo ? "checked" : ""}></td>
            <td>${
              a.tarjeta_uid
                ? `<code style="font-size:12px;color:var(--oro)">${escapar(a.tarjeta_uid)}</code>
                   <button class="boton secundario quitar-tarjeta" style="padding:4px 8px;font-size:11px">quitar</button>`
                : `<span style="opacity:.4;font-size:12px">sin tarjeta</span>`
            }</td>
            <td>${fichaje(a.ultimo_acceso)}</td>
            <td><button class="boton secundario copiar" data-e="${a.enlace}">Copiar</button></td>
            <td><button class="boton secundario borrar" style="color:var(--rojo);border-color:rgba(207,75,75,.4)">Borrar</button></td>
          </tr>`
        )
        .join("");

    $("tabla").querySelectorAll("tr[data-id]").forEach((tr) => {
      const id = tr.dataset.id;
      tr.querySelector(".sexo").addEventListener("change", (e) =>
        api(`/api/alumnos/${id}`, { method: "PATCH", body: JSON.stringify({ sexo: e.target.value }) }).then(cargar)
      );
      tr.querySelector(".activo").addEventListener("change", (e) =>
        api(`/api/alumnos/${id}`, { method: "PATCH", body: JSON.stringify({ activo: e.target.checked }) }).then(cargar)
      );
      tr.querySelector(".copiar").addEventListener("click", (e) => {
        navigator.clipboard.writeText(e.target.dataset.e);
        e.target.textContent = "✓";
        setTimeout(() => (e.target.textContent = "Copiar"), 1200);
      });
      const quitar = tr.querySelector(".quitar-tarjeta");
      if (quitar)
        quitar.addEventListener("click", () => {
          api(`/api/alumnos/${id}/tarjeta`, { method: "POST", body: JSON.stringify({ uid: null }) })
            .then(cargar);
        });
      tr.querySelector(".borrar").addEventListener("click", () => {
        if (confirm("¿Borrar este alumno y todo su histórico?"))
          api(`/api/alumnos/${id}`, { method: "DELETE" }).then(cargar);
      });
    });
  }

  $("anadir").addEventListener("click", async () => {
    const cuerpo = {
      nombre: $("nombre").value,
      telefono: $("telefono").value,
      sexo: $("sexo").value,
    };
    const r = await api("/api/alumnos", { method: "POST", body: JSON.stringify(cuerpo) });
    const j = await r.json();
    if (!r.ok) {
      $("aviso").textContent = `⚠ ${j.detail}`;
      return;
    }
    $("aviso").textContent = `✓ ${j.nombre} añadido`;
    $("nombre").value = $("telefono").value = "";
    $("nombre").focus();
    cargar();
  });

  $("entrar").addEventListener("click", () => {
    clave = $("clave").value.trim();
    cargar();
  });
  $("clave").addEventListener("keydown", (e) => e.key === "Enter" && $("entrar").click());
  ["nombre", "telefono"].forEach((id) =>
    $(id).addEventListener("keydown", (e) => e.key === "Enter" && $("anadir").click())
  );

  // "2026-09-10 15:11" -> "hoy 15:11" / "ayer 21:30" / "10/09 15:11"
  function fichaje(valor) {
    if (!valor) return `<span style="opacity:.35;font-size:12px">nunca</span>`;
    const [fecha, hora] = valor.split(" ");
    const dia = new Date(fecha + "T00:00:00");
    const hoy = new Date();
    hoy.setHours(0, 0, 0, 0);
    const dias = Math.round((hoy - dia) / 86400000);
    const cuando =
      dias === 0 ? "hoy" : dias === 1 ? "ayer" : fecha.slice(8) + "/" + fecha.slice(5, 7);
    const viejo = dias > 21;
    return `<span style="font-size:12.5px;${viejo ? "opacity:.45" : ""}">
              ${cuando} <span class="mono" style="opacity:.7">${escapar(hora)}</span>
            </span>`;
  }

  function escapar(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  cargar();
})();