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
  }

  function pintar(alumnos) {
    const h = alumnos.filter((a) => a.sexo === "H" && a.activo).length;
    const m = alumnos.filter((a) => a.sexo === "M" && a.activo).length;
    $("contador").textContent = `· ${h} hombres / ${m} mujeres activos`;

    $("tabla").innerHTML =
      `<tr><th>Nombre</th><th>Teléfono</th><th>Sexo</th><th>Activo</th><th>Enlace</th><th></th></tr>` +
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

  function escapar(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  cargar();
})();