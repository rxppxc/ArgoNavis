/**
 * Lista desplegable con buscador (2026-11-13): para las listas largas, como los
 * países. Se escribe parte del nombre o el código y la lista se acota, sin
 * distinguir mayúsculas ni tildes (`filtrarOpciones`, utils/busqueda.ts).
 *
 * Es el patrón «combobox» de la WAI-ARIA (campo de texto con su lista):
 * - Flechas para moverse, Enter o Tab para elegir la marcada, Escape para cerrar
 *   sin cambiar nada. Al escribir se marca la primera coincidencia.
 * - Si se sale con el mouse sin elegir, vale lo escrito solo si es un nombre, un
 *   código o una sola coincidencia (`opcionEscrita`); si no, queda lo que había.
 *   Con el campo vacío, queda sin elegir.
 * - Solo se pinta la lista mientras está abierta: con 30 pasajeros eran 60 listas
 *   de ~250 países en la página.
 * - La lista no va dentro del <label>: su texto se sumaría al nombre del campo.
 */
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { filtrarOpciones, opcionEscrita, type OpcionBuscable } from "../utils/busqueda";
import { IconoCheck, IconoChevronAbajo } from "./Iconos";
import estilos from "./SelectorBuscable.module.css";

interface Props {
  /** El rótulo del campo (su nombre accesible). */
  etiqueta:     ReactNode;
  opciones:     OpcionBuscable[];
  valor:        string;
  onCambiar:    (valor: string) => void;
  /** Clase del contenedor (la de los campos del formulario). */
  className?:   string;
  placeholder?: string;
}

/** Alto máximo de la lista (igual que en el CSS): si no cabe debajo, se abre hacia arriba. */
const ALTO_LISTA = 264;
const SALTO_PAGINA = 8;

/** La opción marcada, a la vista dentro de la lista (no mueve nada si ya se ve). */
function mostrarMarcada(elemento: HTMLLIElement | null) {
  elemento?.scrollIntoView?.({ block: "nearest" });
}

export function SelectorBuscable({
  etiqueta, opciones, valor, onCambiar, className, placeholder = "Escribe para buscar",
}: Props) {
  const id = useId();
  const idCampo = `${id}campo`;
  const idRotulo = `${id}rotulo`;
  const idLista = `${id}lista`;
  const idOpcion = (o: OpcionBuscable) => `${id}op-${o.valor}`;
  const entrada = useRef<HTMLInputElement>(null);

  const [abierta, setAbierta] = useState(false);
  const [haciaArriba, setHaciaArriba] = useState(false);
  /** Lo escrito desde que se abrió; null = no se escribió (se ve el nombre elegido). */
  const [consulta, setConsulta] = useState<string | null>(null);
  const [marcada, setMarcada] = useState(-1);

  const elegida = opciones.find((o) => o.valor === valor);
  const visibles = consulta === null ? opciones : filtrarOpciones(opciones, consulta);
  const conLista = abierta && visibles.length > 0;
  const opcionMarcada = abierta ? visibles[marcada] : undefined;
  const escrito = consulta?.trim() ?? "";

  function abrir(indice: number) {
    const caja = entrada.current?.getBoundingClientRect();
    if (caja) {
      const alto = window.visualViewport?.height ?? window.innerHeight;
      const abajo = alto - caja.bottom;
      setHaciaArriba(abajo < ALTO_LISTA + 12 && caja.top > abajo);
    }
    setAbierta(true);
    setMarcada(indice);
  }

  function cerrar() {
    setAbierta(false);
    setConsulta(null);
    setMarcada(-1);
  }

  function elegir(opcion: OpcionBuscable | null | undefined) {
    if (opcion && opcion.valor !== valor) onCambiar(opcion.valor);
    cerrar();
  }

  /** Al abrir sin escribir se marca la elegida (ninguna si no hay); con algo escrito, la primera. */
  const indiceInicial = () => (consulta === null ? opciones.findIndex((o) => o.valor === valor) : 0);

  function escribir(texto: string) {
    setConsulta(texto);
    const indice = texto.trim() ? 0 : -1;
    if (abierta) setMarcada(indice);
    else abrir(indice);
  }

  function alTeclear(e: KeyboardEvent<HTMLInputElement>) {
    const ultima = visibles.length - 1;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (!abierta) abrir(e.altKey ? -1 : indiceInicial());
        else setMarcada((m) => Math.min(m + 1, ultima));
        break;
      case "ArrowUp":
        e.preventDefault();
        if (!abierta) abrir(indiceInicial());
        else setMarcada((m) => Math.max(m - 1, 0));
        break;
      case "PageDown":
        if (abierta) { e.preventDefault(); setMarcada((m) => Math.min(m + SALTO_PAGINA, ultima)); }
        break;
      case "PageUp":
        if (abierta) { e.preventDefault(); setMarcada((m) => Math.max(m - SALTO_PAGINA, 0)); }
        break;
      case "Enter":
        // Abierta, Enter elige y no envía el formulario.
        if (abierta) { e.preventDefault(); elegir(opcionMarcada); }
        break;
      case "Escape":
        if (abierta) { e.preventDefault(); cerrar(); }
        break;
      case "Tab":
        // Tab con una opción marcada la elige, y el foco pasa al campo siguiente.
        if (opcionMarcada) elegir(opcionMarcada);
        break;
    }
  }

  function alSalir() {
    if (consulta !== null) {
      if (!escrito) { if (valor) onCambiar(""); }
      else elegir(opcionEscrita(opciones, consulta));
    }
    cerrar();
  }

  function alternar() {
    if (abierta) cerrar();
    else abrir(indiceInicial());
    entrada.current?.focus();
  }

  return (
    <div className={className}>
      <label id={idRotulo} htmlFor={idCampo}>{etiqueta}</label>
      <div className={estilos.caja}>
        <input
          ref={entrada}
          id={idCampo}
          className={estilos.entrada}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={conLista}
          aria-controls={idLista}
          aria-activedescendant={opcionMarcada ? idOpcion(opcionMarcada) : undefined}
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={consulta ?? elegida?.texto ?? ""}
          onChange={(e) => escribir(e.target.value)}
          onKeyDown={alTeclear}
          onFocus={(e) => e.target.select()}
          onClick={() => { if (!abierta) abrir(indiceInicial()); }}
          onBlur={alSalir}
        />
        {/* La flecha es para el mouse: fuera del Tab y del lector de pantalla, que abren la
            lista con las flechas del teclado. Así el campo no tiene dos controles con su nombre. */}
        <button type="button" className={estilos.flecha} tabIndex={-1} aria-hidden="true"
          // Que el clic no saque el foco del campo.
          onMouseDown={(e) => e.preventDefault()} onClick={alternar}>
          <IconoChevronAbajo tamano={16} />
        </button>
        <ul id={idLista} role="listbox" aria-labelledby={idRotulo} hidden={!conLista}
          className={`${estilos.lista} ${haciaArriba ? estilos.arriba : ""}`}
          onMouseDown={(e) => e.preventDefault()}>
          {conLista && visibles.map((o, i) => (
            <li key={o.valor} id={idOpcion(o)} role="option" aria-selected={i === marcada}
              ref={i === marcada ? mostrarMarcada : undefined}
              className={`${estilos.opcion} ${i === marcada ? estilos.marcada : ""} ${o.valor === valor ? estilos.elegida : ""}`}
              onMouseMove={() => { if (i !== marcada) setMarcada(i); }}
              onClick={() => elegir(o)}>
              <span>{o.texto}</span>
              {o.valor === valor && <IconoCheck tamano={14} />}
            </li>
          ))}
        </ul>
        {abierta && visibles.length === 0 && (
          <div className={`${estilos.lista} ${estilos.sinResultados} ${haciaArriba ? estilos.arriba : ""}`}>
            Sin coincidencias con «{escrito}»
          </div>
        )}
        {/* Para el lector de pantalla: cuántas quedan al escribir. */}
        <span className="sr-only" aria-live="polite">
          {abierta && escrito
            ? visibles.length === 0 ? "Sin coincidencias"
              : visibles.length === 1 ? "1 resultado" : `${visibles.length} resultados`
            : ""}
        </span>
      </div>
    </div>
  );
}
