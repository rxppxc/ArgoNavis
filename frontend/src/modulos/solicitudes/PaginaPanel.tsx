/**
 * Panel principal — bandejas de Autorizaciones Marítimas según el rol:
 *
 *  - **Mi agencia** (Naviera): las solicitudes de su agencia naviera.
 *  - **Revisión** (UCVMM / Sector Pacífico): la cola de todas las solicitudes.
 *  - **Puesto de control**: las autorizaciones aprobadas de sus puestos.
 *
 * El admin ve las tres. Filtros, conteos por estado y páginas los resuelve el
 * servidor. Cada fila abre el expediente (/solicitudes/:id).
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  apiSolicitudes, type Bandeja, type ConsultaBandeja, type EstadoSolicitud, type PaginaSolicitudes,
} from "../../api/solicitudes";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { usePermisos } from "../../hooks/usePermisos";
import { MarcoPagina } from "../../components/MarcoPagina";
import FiltroFechas, { type RangoFechas } from "../../components/FiltroFechas";
import { IconoBandeja, IconoBuscar, IconoMas, IconoX } from "../../components/Iconos";
import { TarjetaSolicitud } from "./TarjetaSolicitud";
import { mensajeDeError } from "../../utils/errores";
import styles from "./PaginaPanel.module.css";

type FiltroEstado = EstadoSolicitud | "todas";

const POR_PAGINA = 20;

const VISTAS: Record<Bandeja, { etiqueta: string; subtitulo: string }> = {
  revision: { etiqueta: "Revisión UCVMM",    subtitulo: "Solicitudes de autorización de las agencias navieras" },
  puerto:   { etiqueta: "Puesto de control", subtitulo: "Autorizaciones aprobadas de tus puestos" },
  agencia:  { etiqueta: "Mi agencia",        subtitulo: "Solicitudes de autorización marítima de tu agencia" },
};

const PESTANAS: Record<Bandeja, { id: FiltroEstado; etiqueta: string }[]> = {
  revision: [
    { id: "review", etiqueta: "Por revisar" },
    { id: "returned", etiqueta: "En corrección" },
    { id: "approved", etiqueta: "Aprobadas" },
    { id: "finalized", etiqueta: "Finalizadas" },
    { id: "denied", etiqueta: "Denegadas" },
    { id: "expired", etiqueta: "Expiradas" },
    { id: "todas", etiqueta: "Todas" },
  ],
  puerto: [
    { id: "approved", etiqueta: "Por finalizar" },
    { id: "finalized", etiqueta: "Finalizadas" },
    { id: "expired", etiqueta: "Expiradas" },
    { id: "todas", etiqueta: "Todas" },
  ],
  agencia: [
    { id: "todas", etiqueta: "Todas" },
    { id: "review", etiqueta: "En revisión" },
    { id: "returned", etiqueta: "Por corregir" },
    { id: "approved", etiqueta: "Aprobadas" },
    { id: "finalized", etiqueta: "Finalizadas" },
    { id: "denied", etiqueta: "Denegadas" },
    { id: "expired", etiqueta: "Expiradas" },
  ],
};

interface Resultado {
  clave:  string;
  vista:  Bandeja;
  pagina: PaginaSolicitudes | null;
  error:  string | null;
}

export default function PaginaPanel() {
  const { usuario } = useAutenticacion();
  const { tiene, esAdmin, cargando: cargandoPermisos } = usePermisos();

  const puedeRevisar = esAdmin || tiene("T-PROCESAR-PACIFICO");
  const esPuerto     = esAdmin || tiene("T-FINALIZAR-PUERTO");
  const puedeCrear   = esAdmin || tiene("T-CREAR-BASICA");

  const vistas = useMemo(() => {
    const lista: Bandeja[] = [];
    if (puedeRevisar) lista.push("revision");
    if (esPuerto) lista.push("puerto");
    if (puedeCrear || lista.length === 0) lista.push("agencia");
    return lista;
  }, [puedeRevisar, esPuerto, puedeCrear]);

  const [vistaElegida, setVistaElegida] = useState<Bandeja | null>(null);
  const vista: Bandeja = vistaElegida && vistas.includes(vistaElegida) ? vistaElegida : vistas[0];
  const [filtroElegido, setFiltroElegido] = useState<FiltroEstado | null>(null);
  const filtro: FiltroEstado = filtroElegido ?? PESTANAS[vista][0].id;

  const [busqueda, setBusqueda] = useState("");
  const [texto, setTexto] = useState("");
  const [rango, setRango] = useState<RangoFechas>({ desde: null, hasta: null });
  const [pagina, setPagina] = useState(1);

  // La búsqueda se manda al servidor cuando se deja de escribir.
  useEffect(() => {
    const t = setTimeout(() => {
      setTexto(busqueda.trim());
      setPagina(1);
    }, 350);
    return () => clearTimeout(t);
  }, [busqueda]);

  const consulta = useMemo<ConsultaBandeja>(() => ({
    estado: filtro === "todas" ? undefined : filtro,
    texto: texto || undefined,
    desde: rango.desde ?? undefined,
    hasta: rango.hasta ?? undefined,
    pagina,
    por_pagina: POR_PAGINA,
  }), [filtro, texto, rango, pagina]);
  const clave = JSON.stringify([vista, consulta]);

  // El resultado recuerda de qué consulta es: "cargando" se deriva de eso, sin
  // setState síncrono dentro del efecto.
  const [resultado, setResultado] = useState<Resultado | null>(null);

  useEffect(() => {
    // Sin permisos todavía la bandeja sería "agencia" para todos: un revisor
    // recibiría 403. Se espera a saber qué bandejas le corresponden.
    if (cargandoPermisos) return;
    let cancelado = false;
    apiSolicitudes.bandeja(vista, consulta)
      .then((p) => { if (!cancelado) setResultado({ clave, vista, pagina: p, error: null }); })
      .catch((e) => {
        if (!cancelado) {
          setResultado({ clave, vista, pagina: null, error: mensajeDeError(e, "No se pudieron cargar las solicitudes.") });
        }
      });
    return () => { cancelado = true; };
  }, [vista, consulta, clave, cargandoPermisos]);

  const cargando = resultado?.clave !== clave;
  // Mientras llega la página nueva se deja ver la anterior de la misma bandeja.
  const datos = resultado?.vista === vista ? resultado.pagina : null;
  const error = resultado?.clave === clave ? resultado.error : null;
  const conteos = datos?.conteos ?? {};
  const totalTodas = Object.values(conteos).reduce((a, b) => a + (b ?? 0), 0);
  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / datos.por_pagina)) : 1;
  const hayFiltros = !!texto || rango.desde !== null || rango.hasta !== null;

  function cambiarVista(v: Bandeja) {
    setVistaElegida(v);
    setFiltroElegido(null);
    setPagina(1);
  }

  function cambiarFiltro(f: FiltroEstado) {
    setFiltroElegido(f);
    setPagina(1);
  }

  function cambiarRango(r: RangoFechas) {
    setRango(r);
    setPagina(1);
  }

  return (
    <MarcoPagina ancho="amplio">
      <div className={styles.encabezado}>
        <div>
          <h1 className={styles.saludo}>Bienvenido, {usuario?.full_name?.split(" ")[0] ?? usuario?.username}</h1>
          <p className={styles.subtitulo}>
            {VISTAS[vista].subtitulo}
            {vista === "agencia" && usuario?.agencia && <> — {usuario.agencia.nombre}</>}
          </p>
        </div>
        {puedeCrear && (
          <Link to="/new" className={styles.btnNuevo}>
            <IconoMas /> Nueva solicitud
          </Link>
        )}
      </div>

      {!cargandoPermisos && vistas.length > 1 && (
        <div className={styles.vistas} role="tablist" aria-label="Bandeja">
          {vistas.map((v) => (
            <button key={v} type="button" role="tab" aria-selected={v === vista}
              className={`${styles.vista} ${v === vista ? styles.vistaActiva : ""}`}
              onClick={() => cambiarVista(v)}>
              {VISTAS[v].etiqueta}
            </button>
          ))}
        </div>
      )}

      <div className={styles.pestanas} role="tablist" aria-label="Estado">
        {PESTANAS[vista].map((p) => (
          <button key={p.id} type="button" role="tab" aria-selected={p.id === filtro}
            className={`${styles.pestana} ${p.id === filtro ? styles.pestanaActiva : ""}`}
            onClick={() => cambiarFiltro(p.id)}>
            {p.etiqueta}
            <span className={styles.pestanaConteo}>{p.id === "todas" ? totalTodas : conteos[p.id] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <span className={styles.searchIcon}><IconoBuscar tamano={15} /></span>
          <input type="text" className={styles.searchInput} value={busqueda} maxLength={100}
            placeholder="Buscar por número, buque, IMO, agencia o puesto…"
            onChange={(e) => setBusqueda(e.target.value)} />
          {busqueda && (
            <button type="button" className={styles.searchLimpiar} onClick={() => setBusqueda("")} aria-label="Limpiar búsqueda">
              <IconoX tamano={13} />
            </button>
          )}
        </div>
        <FiltroFechas valor={rango} onCambio={cambiarRango} />
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {cargando && !datos ? (
        <div className={styles.cargando}><span className={styles.spinner} /> Cargando solicitudes…</div>
      ) : !datos || datos.items.length === 0 ? (
        !error && (
          <div className={styles.vacio}>
            <div className={styles.vacioIcono}><IconoBandeja tamano={30} /></div>
            <h3>{hayFiltros ? "Sin resultados" : "No hay solicitudes aquí"}</h3>
            <p>
              {hayFiltros ? "Nada coincide con la búsqueda o el rango de fechas."
                : vista === "agencia" ? "Cuando tu agencia envíe una solicitud de autorización aparecerá en esta lista."
                : vista === "puerto" ? "Aquí verás las autorizaciones aprobadas para tus puestos de control."
                : "No hay solicitudes en este estado."}
            </p>
            {vista === "agencia" && puedeCrear && !hayFiltros && (
              <Link to="/new" className={styles.btnNuevo}><IconoMas /> Nueva solicitud</Link>
            )}
          </div>
        )
      ) : (
        <>
          <div className={`${styles.lista} ${cargando ? styles.listaActualizando : ""}`} aria-busy={cargando}>
            {datos.items.map((s) => (
              <TarjetaSolicitud key={s.id} s={s} mostrarRemitente={vista !== "agencia"} />
            ))}
          </div>
          {totalPaginas > 1 && (
            <nav className={styles.paginacion} aria-label="Páginas">
              <button type="button" className={styles.btnPagina} disabled={pagina <= 1 || cargando}
                onClick={() => setPagina((p) => p - 1)}>
                Anterior
              </button>
              <span className={styles.paginaInfo}>
                Página {datos.pagina} de {totalPaginas} · {datos.total} solicitud{datos.total === 1 ? "" : "es"}
              </span>
              <button type="button" className={styles.btnPagina} disabled={pagina >= totalPaginas || cargando}
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
