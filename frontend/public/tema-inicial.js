/* Fija el tema antes de que cargue la aplicación: así la primera pintada ya
   sale en el tema correcto y no hay parpadeo. Script clásico (no módulo) y en
   archivo propio para que funcione aunque se agregue una CSP sin 'unsafe-inline'.
   Misma lógica que src/context/ContextoTema.tsx: si cambias una, cambia la otra. */
(function () {
  var preferencia = "system";
  try {
    var guardada = localStorage.getItem("tema");
    if (guardada === "light" || guardada === "dark" || guardada === "system") preferencia = guardada;
  } catch (e) { /* almacenamiento bloqueado: se sigue al sistema */ }

  var tema = preferencia;
  if (preferencia === "system") {
    tema = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  document.documentElement.setAttribute("data-theme", tema);

  var barra = document.querySelector('meta[name="theme-color"]');
  if (barra) barra.setAttribute("content", tema === "light" ? "#FFFFFF" : "#0F1218");
})();
