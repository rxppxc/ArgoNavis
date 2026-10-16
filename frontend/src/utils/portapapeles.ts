/**
 * `navigator.clipboard` solo existe en contextos seguros (HTTPS o localhost).
 * Este servidor corre en HTTP plano sobre IP interna, así que la API ni
 * siquiera está definida — llamarla directo revienta con
 * "navigator.clipboard is undefined". Acá se usa si está disponible, y si no,
 * se cae al método viejo (execCommand) vía un textarea oculto, que sí
 * funciona en HTTP.
 */
export async function copiarAlPortapapeles(texto: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(texto);
      return true;
    } catch {
      // sigue al respaldo de abajo
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = texto;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let ok: boolean;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  document.body.removeChild(textarea);
  return ok;
}
