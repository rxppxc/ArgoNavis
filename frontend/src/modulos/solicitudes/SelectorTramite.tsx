import { useRef, useState, type ReactNode } from "react";
import type { TipoTramite } from "../../api/tramites";
import {
  IconoAncla, IconoArchivo, IconoCaminar, IconoCheck, IconoCruzMedica, IconoDesembarque, IconoEmbarque,
  IconoHerramienta, IconoIntercambio, IconoPasaporte,
} from "../../components/Iconos";
import { AYUDA_CAMPOS_TRAMITE } from "./presentacion";
import styles from "./SelectorTramite.module.css";

/** Ícono y color de cada trámite del Form. 3, para distinguir las tarjetas de
 *  un vistazo. Es presentación: el catálogo no lo guarda (un trámite nuevo
 *  sale con el ícono genérico, en gris). En la grilla los colores vecinos no
 *  se parecen: verde junto a cian, azul junto a morado, turquesa lejos del verde. */
const PRESENTACION: Partial<Record<string, { icono: typeof IconoAncla; tono: string }>> = {
  "F3-EMBARQUE":        { icono: IconoEmbarque,    tono: styles.tonoVerde },
  "F3-DESEMBARQUE":     { icono: IconoDesembarque, tono: styles.tonoCian },
  "F3-CAMBIO-PUERTO":   { icono: IconoAncla,       tono: styles.tonoAzul },
  "F3-CAMBIO-NAVE":     { icono: IconoIntercambio, tono: styles.tonoMorado },
  "F3-RENOV-PASAPORTE": { icono: IconoPasaporte,   tono: styles.tonoNaranja },
  "F3-TECNICO":         { icono: IconoHerramienta, tono: styles.tonoGris },
  "F3-SHORE-PASS":      { icono: IconoCaminar,     tono: styles.tonoTurquesa },
  "F3-URGENCIA-MEDICA": { icono: IconoCruzMedica,  tono: styles.tonoRojo },
};
const GENERICA = { icono: IconoArchivo, tono: styles.tonoGris };

/** Qué pide el trámite, en una línea, sacado del checklist del catálogo
 *  (p. ej. "Hasta 4 documentos por tripulante · Lista de Tripulantes"). "Hasta"
 *  cuando alguno depende del tripulante: el seamanbook solo lo porta el
 *  Marino y el Form. No. 6 es para los de nacionalidad restringida. */
function resumenRequisitos(t: TipoTramite): string {
  const porTripulante = t.documentos.filter((d) => d.alcance === "marino");
  const fijos = porTripulante.filter((d) => d.condicion === "siempre" && !d.requiere_libreta).length;
  const n = porTripulante.length;
  const partes = [
    n > 0 && `${fijos < n ? "Hasta " : ""}${n} documento${n === 1 ? "" : "s"} por tripulante`,
    ...t.documentos.filter((d) => d.alcance === "solicitud" && d.condicion === "siempre").map((d) => d.nombre),
    t.requiere_puerto && (AYUDA_CAMPOS_TRAMITE[t.codigo]?.puerto?.toLowerCase() ?? "puerto"),
    t.requiere_puerto_desembarque && "puerto de desembarque",
    t.requiere_motivo && "motivo",
    t.requiere_clinica && "clínica u hospital",
  ].filter((p): p is string => typeof p === "string");
  const texto = partes.join(" · ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function Requisitos({ tipo }: { tipo: TipoTramite }) {
  const texto = resumenRequisitos(tipo);
  if (!texto) return null;
  return <span className={styles.requisitos}><IconoArchivo tamano={12} /> {texto}</span>;
}

interface Props {
  tipos: TipoTramite[];
  elegido: TipoTramite | null;
  /** Al corregir, el trámite no se cambia: solo se muestra. */
  fijo?: boolean;
  /** Devuelve si el cambio se hizo: la página puede pedir confirmación antes. */
  onElegir: (codigo: string) => Promise<boolean>;
  /** Notas del trámite elegido (vigencia, avisos), debajo del resumen. */
  children?: ReactNode;
}

/** Paso 1 de «Nueva solicitud»: los trámites en tarjetas, con cuándo se usa
 *  cada uno y qué pide. Antes era una lista desplegable con los nombres solos,
 *  y lo que pedía cada trámite se descubría después de elegirlo. Elegido, se
 *  resume en una línea con «Cambiar». */
export function SelectorTramite({ tipos, elegido, fijo = false, onElegir, children }: Props) {
  const [cambiando, setCambiando] = useState(false);
  const refElegido = useRef<HTMLDivElement>(null);

  async function elegir(t: TipoTramite) {
    if (t.codigo !== elegido?.codigo && !(await onElegir(t.codigo))) return;
    setCambiando(false);
    // La tarjeta pulsada desaparece: el foco pasa al resumen (y lo trae a la vista).
    requestAnimationFrame(() => refElegido.current?.focus());
  }

  if (elegido && !cambiando) {
    const { icono: Icono, tono } = PRESENTACION[elegido.codigo] ?? GENERICA;
    return (
      <>
        <div ref={refElegido} tabIndex={-1} className={`${styles.elegido} ${tono}`}>
          <div className={styles.elegidoInfo}>
            <span className={styles.icono}><Icono tamano={24} /></span>
            <div className={styles.texto}>
              <div className={styles.nombre}>{elegido.nombre}</div>
              {elegido.descripcion && <div className={styles.descripcion}>{elegido.descripcion}</div>}
              <Requisitos tipo={elegido} />
            </div>
          </div>
          {fijo
            ? <span className={styles.fijo}>Al corregir no se cambia el trámite.</span>
            : <button type="button" className={styles.btnCambiar} onClick={() => setCambiando(true)}>Cambiar</button>}
        </div>
        {children}
      </>
    );
  }

  if (!tipos.length) return <p className={styles.ayuda}>No hay trámites activos en el catálogo.</p>;

  return (
    <>
      {cambiando && (
        <div className={styles.cabecera}>
          <span className={styles.ayuda}>Elige otro trámite.</span>
          <button type="button" className={styles.btnTexto} onClick={() => setCambiando(false)}>Cancelar</button>
        </div>
      )}
      <div className={styles.tarjetas} role="group" aria-label="Tipo de trámite">
        {tipos.map((t) => {
          const { icono: Icono, tono } = PRESENTACION[t.codigo] ?? GENERICA;
          const actual = t.codigo === elegido?.codigo;
          return (
            <button key={t.id} type="button" aria-pressed={actual} onClick={() => elegir(t)}
              className={`${styles.tarjeta} ${tono} ${actual ? styles.tarjetaElegida : ""}`}>
              {actual && <span className={styles.marca}><IconoCheck tamano={13} /></span>}
              <span className={styles.icono}><Icono tamano={24} /></span>
              <span className={styles.texto}>
                <span className={styles.nombre}>{t.nombre}</span>
                {t.descripcion && <span className={styles.descripcion}>{t.descripcion}</span>}
                <Requisitos tipo={t} />
              </span>
            </button>
          );
        })}
      </div>
    </>
  );
}
