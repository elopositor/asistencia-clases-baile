/* Vista del alumno: horario del dia como rejilla tactil. */
(() => {
  const token = location.pathname.split("/").pop();
  const params = new URLSearchParams(location.search);

  let fecha = params.get("d") || "";
  let datos = null;
  let seleccion = new Set();

  const $ = (id) => document.getElementById(id);

  async function cargar(nuevaFecha) {
    if (nuevaFecha) fecha = nuevaFecha;
    $("contenido").className = "cargando";
    $("contenido").textContent = "Cargando horario…";

    const url = `/api/alumno/${encodeURIComponent(token)}${fecha ? `?d=${fecha}` : ""}`;
    const r = await fetch(url);
    if (!r.ok) {
      $("contenido").textContent = "No hemos podido cargar tu horario. Prueba a abrir el enlace otra vez.";
      return;
    }
    datos = await r.json();
    fecha = datos.fecha;
    seleccion = new Set(datos.seleccion);
    history.replaceState(null, "", `${location.pathname}?d=${fecha}`);
    pintar();
  }

  function pintar() {
    $("saludo").textContent = `Hola ${datos.alumno.nombre.split(" ")[0]}, marca tus clases`;
    $("titulo").textContent = datos.dia_nombre || "Fin de semana";
    pintarDias();

    if (!datos.hay_clase) {
      $("contenido").className = "cargando";
      $("contenido").innerHTML =
        "<p>Ese día no hay clases.</p><p class='nota'>Elige otro día arriba.</p>";
      $("barra").hidden = true;
      return;
    }

    const salas = [...new Set(datos.clases.map((c) => c.sala))].sort();
    const html = salas
      .map((s) => {
        const clases = datos.clases.filter((c) => c.sala === s);
        const profe = clases[0].profe;
        return `<section class="sala-${s}">
          <p class="sala-titulo">Sala ${s} · ${profe}</p>
          <div class="lista">${clases.map(tarjeta).join("")}</div>
        </section>`;
      })
      .join("");

    $("contenido").className = "";
    $("contenido").innerHTML = `<div class="salas ${salas.length > 1 ? "doble" : ""}">${html}</div>
      ${datos.respondido ? "<p class='hecho'>✓ Ya nos has contestado hoy. Puedes cambiarlo cuando quieras.</p>" : ""}`;

    $("contenido").querySelectorAll(".clase").forEach((b) => {
      b.addEventListener("click", () => alternar(b.dataset.id, b));
    });

    $("barra").hidden = false;
    actualizarBarra();
  }

  function tarjeta(c) {
    const marcada = seleccion.has(c.id);
    const nota = c.nota ? `<div class="meta">${escapar(c.nota)}</div>` : "";
    let aviso = "";
    if (c.falta_sexo && c.falta_sexo === datos.alumno.sexo && c.estado !== "ok") {
      const q = c.falta_sexo === "H" ? "chicos" : "chicas";
      aviso = `<div class="aviso-equilibrio">Faltan ${q} en esta clase</div>`;
    }
    return `<button type="button" class="clase ${marcada ? "marcada" : ""}" data-id="${c.id}"
              aria-pressed="${marcada}">
        <span class="hora">${c.hora}</span>
        <span class="detalle">
          <span class="baile">${escapar(c.baile)}</span>
          ${c.nivel ? `<div class="nivel">${escapar(c.nivel)}</div>` : ""}
          <div class="meta">${c.hora}–${c.hora_fin} · ${c.total} apuntad${c.total === 1 ? "o" : "os"}</div>
          ${nota}${aviso}
        </span>
        <span class="marca-check">✓</span>
      </button>`;
  }

  function alternar(id, boton) {
    if (seleccion.has(id)) seleccion.delete(id);
    else seleccion.add(id);
    boton.classList.toggle("marcada");
    boton.setAttribute("aria-pressed", seleccion.has(id));
    actualizarBarra();
  }

  function actualizarBarra() {
    const n = seleccion.size;
    $("contador").innerHTML = n
      ? `<b>${n}</b> clase${n === 1 ? "" : "s"} seleccionada${n === 1 ? "" : "s"}`
      : "Hoy no voy a ninguna";
    $("confirmar").textContent = n ? "Confirmar" : "Hoy no voy";
  }

  function pintarDias() {
    $("dias").innerHTML = datos.proximos_dias
      .map(
        (d) =>
          `<button class="dia-btn ${d.actual ? "activo" : ""}" data-f="${d.fecha}">${d.etiqueta}</button>`
      )
      .join("");
    $("dias").querySelectorAll(".dia-btn").forEach((b) => {
      b.addEventListener("click", () => cargar(b.dataset.f));
    });
  }

  $("confirmar").addEventListener("click", async () => {
    const boton = $("confirmar");
    boton.disabled = true;
    boton.textContent = "Guardando…";
    try {
      const r = await fetch(`/api/alumno/${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fecha, clases: [...seleccion] }),
      });
      if (!r.ok) throw new Error(await r.text());
      boton.textContent = "✓ Guardado";
      setTimeout(() => {
        boton.disabled = false;
        cargar(fecha);
      }, 900);
    } catch (e) {
      boton.disabled = false;
      boton.textContent = "Reintentar";
      alert("No se ha podido guardar. Comprueba tu conexión.");
    }
  });

  function escapar(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  cargar();
})();