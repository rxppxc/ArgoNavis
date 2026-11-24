/**
 * El campo de fecha propio del sistema (2026-11-23). Pedido del usuario: «un calendario
 * propio, con buen diseño, fácil de seleccionar y entender». Reemplaza al
 * <input type="date"> del navegador, que muestra la fecha en el formato de cada Windows
 * (mm/dd en uno en inglés) y no dice qué fechas se pueden elegir.
 * - Se escribe dd/mm/aaaa (las barras se ponen solas) o se elige en el calendario.
 * - Bajo el campo: la fecha en palabras o, vacío, qué fechas se pueden elegir. Mal escrita o
 *   fuera de rango, el campo se pone en rojo y dice por qué, en ese momento (no al enviar).
 * - En el calendario, los días que no se pueden elegir van rayados (como todo lo desactivado),
 *   con el motivo al pasar el mouse; hoy lleva un anillo y la elegida va rellena.
 * - Teclado: flecha abajo abre el calendario; flechas, Re Pág / Av Pág (meses, con Mayús años),
 *   Inicio / Fin (semana), Enter elige, Escape cierra y vuelve al campo.
 * - Guarda AAAA-MM-DD, como el <input type="date">: el formulario y la API no cambian.
 * - El calendario no va dentro del <label>: su texto se sumaría al nombre del campo.
 */
import { useEffect, useId, useRef, useState, type FocusEvent, type KeyboardEvent, type ReactNode } from "react";
import {
  DIAS_SEMANA, MESES, acotar, aniosDisponibles, enmascarar, fechaLarga, fueraDeRango, isoATexto, isoDe, partesDe,
  semanasDelMes, sumarDias, sumarMeses, textoAIso, vistaInicial,
} from "../utils/calendario";
import { fechaISOLocal } from "../utils/fechas";
import { IconoAlerta, IconoCalendario, IconoChevronDerecha, IconoChevronIzquierda } from "./Iconos";
import estilos from "./SelectorFecha.module.css";

export interface AtajoFecha {
  etiqueta: string;
  fecha: string;   // AAAA-MM-DD
}

interface Props {
  /** El rótulo del campo (su nombre accesible). */
  etiqueta:       ReactNode;
  /** AAAA-MM-DD, o "" sin fecha. */
  valor:          string;
  onCambiar:      (iso: string) => void;
  min?:           string;
  max?:           string;
  /** Por qué no se puede elegir una fecha anterior a `min` o posterior a `max`: va bajo el
   *  campo si se escribe una y en los días rayados del calendario. */
  motivoAntes?:   string;
  motivoDespues?: string;
  /** La ayuda bajo el campo vacío (por defecto, qué fechas se pueden elegir). */
  ayuda?:         string;
  /** Botones rápidos al pie del calendario («Hoy», «Mañana»…); solo los que caen en el rango. */
  atajos?:        AtajoFecha[];
  /** Clase del contenedor (la de los campos del formulario). */
  className?:     string;
  /** Sin fecha elegida, el mes que muestra al abrir (por defecto, hoy o el borde más cercano). */
  vista?:         string;
  /** «Borrar» al pie del calendario (los filtros, que se pueden dejar vacíos). */
  borrable?:      boolean;
  /** La línea bajo el campo (la fecha en palabras o la ayuda). En una barra de filtros, donde
   *  desalinearía la fila, va en falso: solo aparece si hay un error. */
  nota?:          boolean;
}

/** Alto y ancho del calendario (como en el CSS): si no cabe, se abre hacia arriba o a la izquierda. */
const ALTO_CALENDARIO = 420;
const ANCHO_CALENDARIO = 340;
const NOMBRE_DIA = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const mayuscula = (texto: string) => texto.charAt(0).toUpperCase() + texto.slice(1);

function textoDelRango(min?: string, max?: string): string {
  if (min && max) return `Puedes elegir del ${isoATexto(min)} al ${isoATexto(max)}`;
  if (min) return `Puedes elegir desde el ${isoATexto(min)}`;
  if (max) return `Puedes elegir hasta el ${isoATexto(max)}`;
  return "";
}

export function SelectorFecha({
  etiqueta, valor, onCambiar, min, max, motivoAntes, motivoDespues, ayuda, atajos = [], className, vista,
  borrable = false, nota: conNota = true,
}: Props) {
  const id = useId();
  const idCampo = `${id}campo`;
  const idRotulo = `${id}rotulo`;
  const idNota = `${id}nota`;
  const idCalendario = `${id}calendario`;
  const contenedor = useRef<HTMLDivElement>(null);
  const entrada = useRef<HTMLInputElement>(null);
  const rejilla = useRef<HTMLTableElement>(null);
  const llevarFoco = useRef(false);
  const hoy = fechaISOLocal();

  /** Lo que se está escribiendo; null = se ve la fecha elegida (dd/mm/aaaa). */
  const [borrador, setBorrador] = useState<string | null>(null);
  const [malEscrita, setMalEscrita] = useState(false);
  const [abierto, setAbierto] = useState(false);
  const [posicion, setPosicion] = useState({ arriba: false, derecha: false });
  const [mes, setMes] = useState(() => vistaInicial(valor || vista || "", hoy, min, max));
  const [enfocado, setEnfocado] = useState(() => (partesDe(valor) ? valor : acotar(hoy, min, max)));

  const elegida = partesDe(valor) ? valor : "";
  const fuera = elegida ? fueraDeRango(elegida, min, max) : null;
  const rango = textoDelRango(min, max);
  const motivo = (lado: "antes" | "despues" | null) =>
    lado === "antes" ? motivoAntes ?? `La fecha no puede ser anterior al ${isoATexto(min)}.`
    : lado === "despues" ? motivoDespues ?? `La fecha no puede ser posterior al ${isoATexto(max)}.`
    : "";

  // Con el calendario abierto por teclado, el foco va al día marcado (y lo sigue al moverse).
  useEffect(() => {
    if (!abierto || !llevarFoco.current) return;
    llevarFoco.current = false;
    rejilla.current?.querySelector<HTMLButtonElement>(`[data-fecha="${enfocado}"]`)?.focus();
  }, [abierto, enfocado, mes]);

  function abrir(conFoco: boolean) {
    const caja = entrada.current?.getBoundingClientRect();
    if (caja) {
      const alto = window.visualViewport?.height ?? window.innerHeight;
      const ancho = window.visualViewport?.width ?? window.innerWidth;
      const abajo = alto - caja.bottom;
      setPosicion({
        arriba: abajo < ALTO_CALENDARIO + 12 && caja.top > abajo,
        derecha: caja.left + ANCHO_CALENDARIO > ancho - 16,
      });
    }
    setMes(vistaInicial(elegida || vista || "", hoy, min, max));
    setEnfocado(elegida || acotar(vista || hoy, min, max));
    llevarFoco.current = conFoco;
    setAbierto(true);
  }

  function cerrar(volverAlCampo: boolean) {
    setAbierto(false);
    if (volverAlCampo) entrada.current?.focus();
  }

  function elegir(iso: string) {
    if (fueraDeRango(iso, min, max)) return;   // rayado: no se elige (el motivo está en el día)
    setBorrador(null);
    setMalEscrita(false);
    if (iso !== valor) onCambiar(iso);
    cerrar(true);
  }

  function borrar() {
    setBorrador(null);
    setMalEscrita(false);
    if (valor) onCambiar("");
    cerrar(true);
  }

  function escribir(texto: string) {
    const limpio = enmascarar(texto);
    setBorrador(limpio);
    setMalEscrita(false);
    const iso = textoAIso(limpio);
    if (iso) {
      if (iso !== valor) onCambiar(iso);
      const p = partesDe(iso);
      if (p) { setMes({ anio: p.anio, mes: p.mes }); setEnfocado(iso); }
    } else if (!limpio && valor) {
      onCambiar("");
    }
  }

  /** Al salir del campo (y del calendario): lo escrito vale si es una fecha; si no, se avisa. */
  function alSalir(e: FocusEvent<HTMLDivElement>) {
    if (contenedor.current?.contains(e.relatedTarget as Node | null)) return;
    setAbierto(false);
    if (borrador === null) return;
    if (!borrador.trim() || textoAIso(borrador)) { setBorrador(null); return; }
    setMalEscrita(true);
    if (valor) onCambiar("");
  }

  function moverA(iso: string) {
    const p = partesDe(iso);
    if (!p) return;
    setEnfocado(iso);
    setMes({ anio: p.anio, mes: p.mes });
    llevarFoco.current = true;
  }

  function alTeclearCampo(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") { e.preventDefault(); abrir(true); }
    else if (e.key === "Escape" && abierto) { e.preventDefault(); cerrar(false); }
  }

  function alTeclearRejilla(e: KeyboardEvent<HTMLTableElement>) {
    const dia = new Date(`${enfocado}T00:00:00Z`).getUTCDay();
    const pasos: Record<string, () => string> = {
      ArrowLeft: () => sumarDias(enfocado, -1),
      ArrowRight: () => sumarDias(enfocado, 1),
      ArrowUp: () => sumarDias(enfocado, -7),
      ArrowDown: () => sumarDias(enfocado, 7),
      Home: () => sumarDias(enfocado, -dia),
      End: () => sumarDias(enfocado, 6 - dia),
      PageUp: () => sumarMeses(enfocado, e.shiftKey ? -12 : -1),
      PageDown: () => sumarMeses(enfocado, e.shiftKey ? 12 : 1),
    };
    if (pasos[e.key]) { e.preventDefault(); moverA(pasos[e.key]()); }
    else if (e.key === "Escape") { e.preventDefault(); cerrar(true); }
  }

  /** Cambiar de mes desde la cabecera: el día marcado pasa al mismo día de ese mes. */
  function verMes(anio: number, mesNuevo: number) {
    const fecha = new Date(Date.UTC(anio, mesNuevo, 1));
    const p = partesDe(enfocado);
    const ultimo = new Date(Date.UTC(fecha.getUTCFullYear(), fecha.getUTCMonth() + 1, 0)).getUTCDate();
    setMes({ anio: fecha.getUTCFullYear(), mes: fecha.getUTCMonth() });
    setEnfocado(isoDe(fecha.getUTCFullYear(), fecha.getUTCMonth(), Math.min(p?.dia ?? 1, ultimo)));
  }

  const ultimoDelAnterior = isoDe(mes.anio, mes.mes, 0);
  const primeroDelSiguiente = isoDe(mes.anio, mes.mes + 1, 1);
  const hayAnterior = !min || ultimoDelAnterior >= min;
  const haySiguiente = !max || primeroDelSiguiente <= max;
  const anios = aniosDisponibles(hoy, min, max);
  if (!anios.includes(mes.anio)) anios.push(mes.anio);   // un año fuera de la lista (escrito a mano)
  const visibles = atajos.filter((a) => !fueraDeRango(a.fecha, min, max));

  const nota = malEscrita
    ? `Fecha no válida: escríbela como dd/mm/aaaa (por ejemplo, ${isoATexto(hoy)}).`
    : fuera ? motivo(fuera)
    : elegida ? fechaLarga(elegida)
    : ayuda ?? (rango ? `${rango}.` : "Escribe la fecha (dd/mm/aaaa) o elígela en el calendario.");
  const conError = malEscrita || !!fuera;

  return (
    <div ref={contenedor} className={`${className ?? ""} ${estilos.contenedor}`} onBlur={alSalir}>
      <label id={idRotulo} htmlFor={idCampo} className={estilos.rotulo}>{etiqueta}</label>
      <div className={`${estilos.caja} ${conError ? estilos.conError : ""}`}>
        <input
          ref={entrada}
          id={idCampo}
          className={estilos.entrada}
          type="text"
          // El patrón «combobox» con un calendario (el selector de fecha de la WAI-ARIA).
          role="combobox"
          aria-autocomplete="none"
          inputMode="numeric"
          autoComplete="off"
          spellCheck={false}
          placeholder="dd/mm/aaaa"
          maxLength={10}
          aria-describedby={conNota || conError ? idNota : undefined}
          aria-invalid={conError || undefined}
          aria-haspopup="dialog"
          aria-expanded={abierto}
          aria-controls={abierto ? idCalendario : undefined}
          value={borrador ?? isoATexto(valor)}
          onChange={(e) => escribir(e.target.value)}
          onKeyDown={alTeclearCampo}
          onClick={() => { if (!abierto) abrir(false); }}
        />
        {/* El botón es para el mouse: el teclado abre el calendario con la flecha abajo, y así
            el campo no tiene dos controles con su nombre. */}
        <button type="button" className={estilos.boton} tabIndex={-1} aria-hidden="true"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => { if (abierto) cerrar(true); else { abrir(false); entrada.current?.focus(); } }}>
          <IconoCalendario tamano={17} />
        </button>

        {abierto && (
          // Se llama «Calendario» y lo describe el rótulo: con el mismo nombre que el campo, buscar
          // el campo por su rótulo encontraba dos cosas.
          <div id={idCalendario} role="dialog" aria-label="Calendario" aria-describedby={idRotulo} tabIndex={-1}
            className={`${estilos.calendario} ${posicion.arriba ? estilos.arriba : ""} ${posicion.derecha ? estilos.derecha : ""}`}>
            <div className={estilos.cabecera}>
              <button type="button" className={estilos.navegar} aria-label="Mes anterior" disabled={!hayAnterior}
                onClick={() => verMes(mes.anio, mes.mes - 1)}>
                <IconoChevronIzquierda tamano={15} />
              </button>
              <select className={estilos.selector} aria-label="Mes" value={mes.mes}
                onChange={(e) => verMes(mes.anio, Number(e.target.value))}>
                {MESES.map((nombre, i) => <option key={nombre} value={i}>{mayuscula(nombre)}</option>)}
              </select>
              <select className={`${estilos.selector} ${estilos.anio}`} aria-label="Año" value={mes.anio}
                onChange={(e) => verMes(Number(e.target.value), mes.mes)}>
                {anios.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
              <button type="button" className={estilos.navegar} aria-label="Mes siguiente" disabled={!haySiguiente}
                onClick={() => verMes(mes.anio, mes.mes + 1)}>
                <IconoChevronDerecha tamano={15} />
              </button>
            </div>

            <table ref={rejilla} role="grid" className={estilos.rejilla} onKeyDown={alTeclearRejilla}
              aria-label={`${mayuscula(MESES[mes.mes])} de ${mes.anio}`}>
              <thead>
                <tr>{DIAS_SEMANA.map((d, i) => <th key={d} scope="col" abbr={NOMBRE_DIA[i]}>{d}</th>)}</tr>
              </thead>
              <tbody>
                {semanasDelMes(mes.anio, mes.mes).map((semana) => (
                  <tr key={semana[0]}>
                    {semana.map((iso) => {
                      const p = partesDe(iso);
                      const lado = fueraDeRango(iso, min, max);
                      const porQue = motivo(lado);
                      const clases = [
                        estilos.dia,
                        p?.mes !== mes.mes && estilos.otroMes,
                        iso === hoy && estilos.hoy,
                        iso === elegida && estilos.elegido,
                        lado && estilos.apagado,
                      ].filter(Boolean).join(" ");
                      return (
                        <td key={iso} role="gridcell" aria-selected={iso === elegida}>
                          <button type="button" data-fecha={iso} className={clases}
                            tabIndex={iso === enfocado ? 0 : -1}
                            aria-label={`${fechaLarga(iso)}${iso === hoy ? ", hoy" : ""}${porQue ? `. ${porQue}` : ""}`}
                            aria-disabled={lado ? true : undefined}
                            title={porQue || undefined}
                            onFocus={() => { if (iso !== enfocado) setEnfocado(iso); }}
                            onClick={() => elegir(iso)}>
                            {p?.dia}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>

            {(visibles.length > 0 || (borrable && valor) || rango) && (
              <div className={estilos.pie}>
                {(visibles.length > 0 || (borrable && valor)) && (
                  <div className={estilos.atajos}>
                    {visibles.map((a) => (
                      <button key={a.etiqueta} type="button" className={estilos.atajo} onClick={() => elegir(a.fecha)}>
                        {a.etiqueta}
                      </button>
                    ))}
                    {borrable && valor && (
                      <button type="button" className={`${estilos.atajo} ${estilos.borrar}`} onClick={borrar}>Borrar</button>
                    )}
                  </div>
                )}
                {rango && <p className={estilos.rango}>{rango}.</p>}
              </div>
            )}
          </div>
        )}
      </div>
      {(conNota || conError) && (
        <small id={idNota} className={conError ? estilos.error : estilos.nota} aria-live="polite">
          {conError && <IconoAlerta tamano={13} />}
          <span>{nota}</span>
        </small>
      )}
    </div>
  );
}
