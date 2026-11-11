/**
 * Consulta histórica (2026-11-11): todas las solicitudes que ve el personal del
 * SNM, de cualquier año («estoy en 2028 y busco una de 2027»), con filtros que
 * las bandejas no tienen (agencia, puesto, trámite, pasajero, fecha de la
 * operación, fuera del horario) y exportación a Excel.
 *
 * El alcance lo pone el servidor: el mismo del expediente (UCVMM y el supervisor
 * de sector, sus sectores; el puesto, sus puestos desde que se aprueban). Los
 * filtros van en la URL (sin sumar entradas al historial): se puede recargar o
 * compartir la misma búsqueda.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  apiSolicitudes, type EstadoSolicitud, type OpcionFiltro, type OpcionesHistorico, type PaginaSolicitudes,
} from "../../api/solicitudes";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import { EstadoCarga } from "../../components/EstadoCarga";
import { IconoAlerta, IconoArchivo, IconoDescargar, IconoReloj } from "../../components/Iconos";
import { MarcoPagina } from "../../components/MarcoPagina";
import { useNotificacion } from "../../components/Notificaciones";
import { usePermisos } from "../../hooks/usePermisos";
import { mensajeDeError } from "../../utils/errores";
import {
  FILTROS_VACIOS, anioDelRango, aniosDisponibles, consultaDeFiltros, filtrosDeUrl, hayFiltros, paginaDeUrl,
  rangoDeAnio, ultimaPagina, urlDeFiltros, type FiltrosHistorico,
} from "./consultaHistorica";
import { FechaEnPalabras } from "./FechaEnPalabras";
import { InsigniaEstado } from "./InsigniaEstado";
import { formatearFecha, formatearFechaHora, TEXTO_HORARIO_LABORAL } from "./presentacion";
import panel from "./PaginaPanel.module.css";
import styles from "./ConsultaHistorica.module.css";

const POR_PAGINA = 25;

const PESTANAS: { id: EstadoSolicitud | ""; etiqueta: string }[] = [
  { id: "", etiqueta: "Todas" },
  { id: "review", etiqueta: "En revisión" },
  { id: "returned", etiqueta: "En corrección" },
  { id: "approved", etiqueta: "Aprobadas" },
  { id: "finalized", etiqueta: "Finalizadas" },
  { id: "denied", etiqueta: "Denegadas" },
  { id: "expired", etiqueta: "Expiradas" },
];

interface Resultado {
  clave: string;
  pagina: PaginaSolicitudes | null;
  error: string | null;
}

/** Un desplegable de las opciones del servidor; lo desactivado lo dice. */
function Opciones({ lista }: { lista: OpcionFiltro[] | undefined }) {
  return (
    <>
      {(lista ?? []).map((o) => (
        <option key={o.id} value={o.id}>{o.nombre}{o.activo ? "" : " (desactivado)"}</option>
      ))}
    </>
  );
}

export default function PaginaConsultaHistorica() {
  const { mostrar } = useNotificacion();
  const { tiene, esAdmin } = usePermisos();
  // El sector, solo a quien ve los dos (como en las bandejas): a los demás les sobraría en cada fila.
  const veLosDos = esAdmin || tiene("T-SUPERVISAR-TODO");
  // En el celular los filtros menos usados van plegados: antes empujaban los resultados una pantalla abajo.
  const [masFiltros, setMasFiltros] = useState(false);
  const [parametros, setParametros] = useSearchParams();
  // Los filtros viven aquí y la URL los copia: así se pueden recargar o compartir.
  const [filtros, setFiltros] = useState<FiltrosHistorico>(() => filtrosDeUrl(parametros));
  const [pagina, setPagina] = useState(() => paginaDeUrl(parametros));
  // Lo que se escribe se busca cuando se deja de escribir.
  const [escrito, setEscrito] = useState({ texto: filtros.texto, pasajero: filtros.pasajero });

  useEffect(() => {
    if (escrito.texto === filtros.texto && escrito.pasajero === filtros.pasajero) return;
    const t = setTimeout(() => {
      setFiltros((f) => ({ ...f, texto: escrito.texto, pasajero: escrito.pasajero }));
      setPagina(1);
    }, 350);
    return () => clearTimeout(t);
  }, [escrito, filtros.texto, filtros.pasajero]);

  useEffect(() => {
    setParametros(urlDeFiltros(filtros, pagina), { replace: true });
  }, [filtros, pagina, setParametros]);

  const [opciones, setOpciones] = useState<OpcionesHistorico | null>(null);
  useEffect(() => {
    let cancelado = false;
    apiSolicitudes.opcionesHistorico()
      .then((o) => { if (!cancelado) setOpciones(o); })
      .catch((e) => { if (!cancelado) mostrar(mensajeDeError(e, "No se pudieron cargar los filtros."), "error"); });
    return () => { cancelado = true; };
  }, [mostrar]);

  const consulta = useMemo(() => consultaDeFiltros(filtros, pagina, POR_PAGINA), [filtros, pagina]);
  const clave = JSON.stringify(consulta);
  // El resultado recuerda de qué consulta es: "cargando" se deriva de eso.
  const [resultado, setResultado] = useState<Resultado | null>(null);
  useEffect(() => {
    let cancelado = false;
    apiSolicitudes.historico(consulta)
      .then((p) => {
        if (cancelado) return;
        // Un enlace con una página que ya no existe (hoy hay menos resultados): a la última.
        const ultima = ultimaPagina(p.total, p.por_pagina);
        if (p.pagina > ultima) setPagina(ultima);
        else setResultado({ clave, pagina: p, error: null });
      })
      .catch((e) => {
        if (!cancelado) setResultado({ clave, pagina: null, error: mensajeDeError(e, "No se pudo hacer la consulta.") });
      });
    return () => { cancelado = true; };
  }, [consulta, clave]);

  const cargando = resultado?.clave !== clave;
  // Mientras llega la página nueva se deja ver la anterior.
  const datos = resultado?.pagina ?? null;
  const error = resultado?.clave === clave ? resultado.error : null;
  const conteos = datos?.conteos ?? {};
  const totalTodas = Object.values(conteos).reduce((a, b) => a + (b ?? 0), 0);
  const totalPaginas = datos ? ultimaPagina(datos.total, datos.por_pagina) : 1;
  const anios = aniosDisponibles(new Date());
  const anio = anioDelRango(filtros.desde, filtros.hasta, anios);
  const conFiltros = hayFiltros(filtros);
  const plegadosActivos = [filtros.agencia, filtros.puesto, filtros.tramite, filtros.desde || filtros.hasta]
    .filter(Boolean).length;

  function cambiar(parcial: Partial<FiltrosHistorico>) {
    setFiltros((f) => ({ ...f, ...parcial }));
    setPagina(1);
  }

  function cambiarAnio(valor: string) {
    if (valor === "todos") cambiar({ desde: "", hasta: "" });
    else if (valor !== "otras") cambiar(rangoDeAnio(Number(valor)));
  }

  // Con el desde después del hasta no habría nada: el otro lo sigue (como en las estadísticas).
  function cambiarDesde(desde: string) {
    cambiar({ desde, hasta: desde && filtros.hasta && filtros.hasta < desde ? desde : filtros.hasta });
  }
  function cambiarHasta(hasta: string) {
    cambiar({ hasta, desde: hasta && filtros.desde && filtros.desde > hasta ? hasta : filtros.desde });
  }

  function limpiar() {
    setEscrito({ texto: "", pasajero: "" });
    setFiltros(FILTROS_VACIOS);
    setPagina(1);
  }

  const [exportando, setExportando] = useState(false);
  async function exportar() {
    setExportando(true);
    try {
      const nombre = await apiSolicitudes.exportarHistorico(consultaDeFiltros(filtros, 1, POR_PAGINA));
      mostrar(`Se descargó «${nombre}».`, "exito");
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo exportar la consulta."), "error");
    } finally {
      setExportando(false);
    }
  }

  return (
    <MarcoPagina ancho="amplio">
      <EncabezadoPagina
        antetitulo="Personal del SNM"
        titulo="Consulta histórica"
        descripcion="Todas las solicitudes que puedes ver, de cualquier año."
        acciones={
          // Azul de contorno: descargar es consultar. Exporta lo que cumple los filtros, no solo esta página.
          <button type="button" className={styles.btnExportar} onClick={exportar}
            disabled={exportando || !datos || datos.total === 0} aria-busy={exportando}>
            <IconoDescargar tamano={15} /> {exportando ? "Generando…" : "Exportar a Excel"}
          </button>
        }
      />

      <form className={styles.ficha} role="search" aria-label="Filtros de la consulta"
        onSubmit={(e) => e.preventDefault()}>
        <div className={styles.gridAncha}>
          <label className={styles.campo}>
            <span>Buscar</span>
            <input type="search" value={escrito.texto} maxLength={100} placeholder="Ej. número, buque, IMO, agencia"
              onChange={(e) => setEscrito((v) => ({ ...v, texto: e.target.value }))} />
          </label>
          <label className={styles.campo}>
            <span>Pasajero</span>
            <input type="search" value={escrito.pasajero} maxLength={100} placeholder="Ej. nombre, apellido o pasaporte"
              onChange={(e) => setEscrito((v) => ({ ...v, pasajero: e.target.value }))} />
          </label>
        </div>
        <button type="button" className={styles.btnMasFiltros} aria-expanded={masFiltros}
          aria-controls="filtros-plegables" onClick={() => setMasFiltros((v) => !v)}>
          {masFiltros ? "Menos filtros" : `Más filtros${plegadosActivos ? ` (${plegadosActivos})` : ""}`}
        </button>
        <div id="filtros-plegables" className={`${styles.plegables} ${masFiltros ? styles.plegablesAbiertos : ""}`}>
          <div className={styles.grid}>
            <label className={styles.campo}>
              <span>Agencia naviera</span>
              <select value={filtros.agencia} onChange={(e) => cambiar({ agencia: e.target.value })}>
                <option value="">Todas</option>
                <Opciones lista={opciones?.agencias} />
              </select>
            </label>
            <label className={styles.campo}>
              <span>Puesto de control</span>
              <select value={filtros.puesto} onChange={(e) => cambiar({ puesto: e.target.value })}>
                <option value="">Todos</option>
                <Opciones lista={opciones?.puestos} />
              </select>
            </label>
            <label className={styles.campo}>
              <span>Trámite</span>
              <select value={filtros.tramite} onChange={(e) => cambiar({ tramite: e.target.value })}>
                <option value="">Todos</option>
                <Opciones lista={opciones?.tramites} />
              </select>
            </label>
          </div>
          <div className={styles.grid}>
            <label className={styles.campo}>
              <span>Fechas por</span>
              <select value={filtros.fecha} onChange={(e) => cambiar({ fecha: e.target.value as FiltrosHistorico["fecha"] })}>
                <option value="envio">Fecha de envío</option>
                <option value="operacion">Fecha de la operación</option>
              </select>
            </label>
            <label className={styles.campo}>
              <span>Año</span>
              <select value={String(anio)} onChange={(e) => cambiarAnio(e.target.value)}>
                <option value="todos">Todos los años</option>
                {anios.map((a) => <option key={a} value={a}>{a}</option>)}
                {anio === "otras" && <option value="otras">Otras fechas</option>}
              </select>
            </label>
            <label className={styles.campo}>
              <span>Desde</span>
              <input type="date" value={filtros.desde} onChange={(e) => cambiarDesde(e.target.value)} />
              <FechaEnPalabras iso={filtros.desde} />
            </label>
            <label className={styles.campo}>
              <span>Hasta</span>
              <input type="date" value={filtros.hasta} onChange={(e) => cambiarHasta(e.target.value)} />
              <FechaEnPalabras iso={filtros.hasta} />
            </label>
          </div>
        </div>
        <div className={styles.pie}>
          <label className={styles.casilla} title={`Horario laboral: ${TEXTO_HORARIO_LABORAL}`}>
            <input type="checkbox" checked={filtros.fueraDeHorario}
              onChange={(e) => cambiar({ fueraDeHorario: e.target.checked })} />
            Solo aprobadas fuera del horario laboral
          </label>
          {conFiltros && (
            <button type="button" className={styles.btnLimpiar} onClick={limpiar}>Limpiar filtros</button>
          )}
        </div>
      </form>

      <div className={panel.pestanas} role="tablist" aria-label="Estado">
        {PESTANAS.map((p) => (
          <button key={p.id || "todas"} type="button" role="tab" aria-selected={p.id === filtros.estado}
            className={`${panel.pestana} ${p.id === filtros.estado ? panel.pestanaActiva : ""}`}
            onClick={() => cambiar({ estado: p.id })}>
            {p.etiqueta}
            <span className={panel.pestanaConteo}>{p.id === "" ? totalTodas : conteos[p.id] ?? 0}</span>
          </button>
        ))}
      </div>

      {error && <div className={panel.error} role="alert"><IconoAlerta tamano={16} /> {error}</div>}

      {cargando && !datos ? (
        <EstadoCarga texto="Consultando…" />
      ) : !datos || datos.items.length === 0 ? (
        !error && (
          <div className={panel.vacio}>
            <div className={panel.vacioIcono}><IconoArchivo tamano={30} /></div>
            <h3>{conFiltros || filtros.estado ? "Sin resultados" : "Todavía no hay solicitudes"}</h3>
            <p>{conFiltros || filtros.estado
              ? "Ninguna solicitud coincide con los filtros."
              : "Cuando haya solicitudes que puedas ver, aparecerán aquí."}</p>
          </div>
        )
      ) : (
        <>
          <p className={styles.resumen} aria-live="polite">
            {datos.total} solicitud{datos.total === 1 ? "" : "es"}, de la más reciente a la más antigua por{" "}
            {filtros.fecha === "operacion" ? "fecha de la operación" : "fecha de envío"}.
          </p>
          <div className={`${styles.tablaMarco} ${cargando ? panel.listaActualizando : ""}`} aria-busy={cargando}>
            <table className={styles.tabla}>
              <caption className="sr-only">Resultados de la consulta histórica</caption>
              <thead>
                <tr>
                  <th scope="col">N.º</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Trámite</th>
                  <th scope="col">Agencia naviera</th>
                  <th scope="col">Puesto</th>
                  <th scope="col">Buque</th>
                  <th scope="col">Operación</th>
                  <th scope="col">Enviada</th>
                </tr>
              </thead>
              <tbody>
                {datos.items.map((s) => (
                  <tr key={s.id}>
                    <td data-etiqueta="N.º">
                      <Link to={`/solicitudes/${s.id}`} className={styles.numero}>{s.numero ?? `#${s.id}`}</Link>
                    </td>
                    <td data-etiqueta="Estado">
                      <InsigniaEstado estado={s.estado} />
                      {s.fuera_de_horario && (
                        <span className={styles.chipHorario} title={`Aprobada fuera del horario laboral (${TEXTO_HORARIO_LABORAL})`}>
                          <IconoReloj tamano={11} /> Fuera del horario
                          {s.costo_fuera_de_horario && <> · {s.costo_fuera_de_horario}</>}
                        </span>
                      )}
                    </td>
                    <td data-etiqueta="Trámite">{s.tipo_tramite_nombre}</td>
                    <td data-etiqueta="Agencia naviera">{s.agencia_nombre}</td>
                    <td data-etiqueta="Puesto">
                      {s.puesto_nombre}
                      {veLosDos && s.sector_nombre && <small>{s.sector_nombre}</small>}
                    </td>
                    <td data-etiqueta="Buque">
                      {s.nombre_buque ?? "—"}
                      {s.imo && <small className={styles.mono}>IMO {s.imo}</small>}
                    </td>
                    <td data-etiqueta="Operación" className={styles.mono}>{formatearFecha(s.fecha_operacion)}</td>
                    <td data-etiqueta="Enviada">{formatearFechaHora(s.enviada_en)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPaginas > 1 && (
            <nav className={panel.paginacion} aria-label="Páginas">
              <button type="button" className={panel.btnPagina} disabled={pagina <= 1 || cargando}
                onClick={() => setPagina((p) => p - 1)}>
                Anterior
              </button>
              <span className={panel.paginaInfo}>Página {datos.pagina} de {totalPaginas}</span>
              <button type="button" className={panel.btnPagina} disabled={pagina >= totalPaginas || cargando}
                onClick={() => setPagina((p) => p + 1)}>
                Siguiente
              </button>
            </nav>
          )}
        </>
      )}
    </MarcoPagina>
  );
}
