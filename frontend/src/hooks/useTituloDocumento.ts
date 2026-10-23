import { useEffect } from "react";

/** Título de la pestaña del navegador: "<página> · ARGO NAVIS". Antes todas las
 *  pestañas decían lo mismo y con varias abiertas no se distinguían. */
export function useTituloDocumento(titulo: string | null | undefined) {
  useEffect(() => {
    document.title = titulo ? `${titulo} · ARGO NAVIS` : "ARGO NAVIS · Sistema Interno Marítimo";
  }, [titulo]);
}
