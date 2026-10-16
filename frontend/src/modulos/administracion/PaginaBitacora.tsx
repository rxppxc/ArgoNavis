/** Bitácora del sistema (audit_logs): todo lo que se hace en la aplicación. Solo admin. */
import { Fragment, useEffect, useState } from "react";
import { apiAdmin, type FiltrosBitacora, type PaginaBitacora as Pagina } from "../../api/admin";
import { MarcoPagina } from "../../components/MarcoPagina";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";
import type { EstadoSolicitud } from "../../api/solicitudes";
import { ETIQUETA_ESTADO, formatearFechaHora } from "../solicitudes/presentacion";
import styles from "./PaginaBitacora.module.css";

const ETIQUETA_ACCION: Record<string, string> = {
  LOGIN_EXITOSO: "Inicio de sesión",
  LOGIN_FALLIDO: "Inicio de sesión fallido",
  CERRAR_SESION: "Cierre de sesión",
  SESION_EXPIRADA: "Sesión expirada",
  TRANSFERENCIA_CREADA: "Transferencia creada (legado)",
  TRANSFERENCIA_ELIMINADA: "Transferencia eliminada (legado)",
  DESCARGA_REALIZADA: "Descarga de archivo (legado)",
  CHAT_CONSULTA: "Consulta de chat (legado)",
  SOLICITUD_CREADA: "Solicitud enviada",
  SOLICITUD_CONSULTADA: "Solicitud consultada",
  SOLICITUD_CORREGIDA: "Solicitud corregida",
  IMPEDIMENTOS_REGISTRADOS: "Impedimentos registrados",
  SOLICITUD_DEVUELTA: "Solicitud devuelta",
  SOLICITUD_APROBADA: "Solicitud aprobada",
  SOLICITUD_NEGADA: "Solicitud denegada",
  SOLICITUD_COMENTADA: "Comentario del puerto",
  SOLICITUD_FINALIZADA: "Solicitud finalizada",
  SOLICITUD_EXPIRADA: "Solicitud expirada",
  AUTORIZACION_DESCARGADA: "Autorización descargada (PDF)",
  AUTORIZACION_VERIFICADA: "Verificación de QR",
  DOCUMENTO_VISTO: "Documento visto",
  DOCUMENTO_DESCARGADO: "Documento descargado",
  CONTRASENA_CAMBIADA: "Contraseña cambiada",
  CONTRASENA_RESTABLECIDA: "Contraseña restablecida",
  CUENTA_BLOQUEADA: "Cuenta bloqueada por intentos",
  USUARIO_CREADO: "Usuario creado",
  USUARIO_ACTUALIZADO: "Usuario actualizado",
  USUARIO_ELIMINADO: "Usuario eliminado",
  ROL_CREADO: "Rol creado",
  ROL_ACTUALIZADO: "Rol actualizado",
  ROL_ELIMINADO: "Rol eliminado",
  PERMISO_CREADO: "Permiso creado",
  PERMISO_ACTUALIZADO: "Permiso actualizado",
  PERMISO_ELIMINADO: "Permiso eliminado",
  PUESTO_CREADO: "Puesto de control creado",
  PUESTO_ACTUALIZADO: "Puesto de control actualizado",
  PUESTO_ELIMINADO: "Puesto de control eliminado",
  AGENCIA_CREADA: "Agencia naviera creada",
  AGENCIA_ACTUALIZADA: "Agencia naviera actualizada",
  AGENCIA_ELIMINADA: "Agencia naviera eliminada",
  PAIS_ACTUALIZADO: "Nacionalidad actualizada",
};

const POR_PAGINA = 50;
const FILTROS_VACIOS: FiltrosBitacora = { accion: "", usuario: "", texto: "", desde: "", hasta: "" };

function resumenDetalle(detalle: Record<string, unknown> | null): string {
  if (!detalle) return "—";
  return Object.entries(detalle)
    .filter(([clave, valor]) => clave !== "token" && valor !== null && valor !== "")
    .map(([clave, valor]) => {
      // Los estados se guardan con su valor técnico (approved, returned…)
      if ((clave === "estado" || clave === "estado_anterior") && typeof valor === "string" && valor in ETIQUETA_ESTADO) {
        return `${clave}: ${ETIQUETA_ESTADO[valor as EstadoSolicitud]}`;
      }
      return `${clave}: ${typeof valor === "object" ? JSON.stringify(valor) : String(valor)}`;
    })
    .join(" · ") || "—";
}

export default function PaginaBitacora() {
  const { mostrar } = useNotificacion();
  const [acciones, setAcciones] = useState<string[]>([]);
  const [borrador, setBorrador] = useState<FiltrosBitacora>(FILTROS_VACIOS);
  const [filtros, setFiltros] = useState<FiltrosBitacora>(FILTROS_VACIOS);
  const [pagina, setPagina] = useState(1);
  // Respuesta etiquetada con la consulta que la produjo: "cargando" se deriva
  // de si corresponde a la consulta actual, y mientras tanto se sigue mostrando
  // la anterior (sin saltos en la tabla).
  const [respuesta, setRespuesta] = useState<{ clave: string; datos: Pagina | null } | null>(null);
  const [abierto, setAbierto] = useState<number | null>(null);

  useEffect(() => {
    apiAdmin.accionesBitacora()
      .then((r) => setAcciones(r.data))
      .catch(() => { /* el filtro por acción queda vacío; la bitácora igual carga */ });
  }, []);

  const clave = JSON.stringify({ ...filtros, pagina });

  useEffect(() => {
    let cancelado = false;
    apiAdmin.consultarBitacora({ ...filtros, pagina, por_pagina: POR_PAGINA })
      .then(({ data }) => { if (!cancelado) setRespuesta({ clave, datos: data }); })
      .catch((e) => {
        if (cancelado) return;
        setRespuesta((previa) => ({ clave, datos: previa?.datos ?? null }));
        mostrar(mensajeDeError(e, "No se pudo cargar la bitácora."), "error");
      });
    return () => { cancelado = true; };
  }, [clave, filtros, pagina, mostrar]);

  const cargando = respuesta?.clave !== clave;
  const resultado = respuesta?.datos ?? null;

  function aplicar(e: React.FormEvent) {
    e.preventDefault();
    setPagina(1);
    setFiltros({ ...borrador });
  }

  function limpiar() {
    setBorrador(FILTROS_VACIOS);
    setPagina(1);
    setFiltros(FILTROS_VACIOS);
  }

  const totalPaginas = resultado ? Math.max(1, Math.ceil(resultado.total / POR_PAGINA)) : 1;
  const campo = (nombre: keyof FiltrosBitacora) => ({
    value: (borrador[nombre] as string | undefined) ?? "",
    onChange: (e: { target: { value: string } }) => setBorrador((prev) => ({ ...prev, [nombre]: e.target.value })),
  });

  return (
    <MarcoPagina volverA="/dashboard" ancho="amplio">
      <div className={styles.titulo}>
        <h1>Bitácora</h1>
        <p>Registro de todo lo que se realiza en la aplicación: sesiones, solicitudes, verificaciones y administración.</p>
      </div>

      <form className={styles.filtros} onSubmit={aplicar}>
        <label>
          <span>Acción</span>
          <select {...campo("accion")}>
            <option value="">Todas</option>
            {acciones.map((a) => <option key={a} value={a}>{ETIQUETA_ACCION[a] ?? a}</option>)}
          </select>
        </label>
        <label>
          <span>Usuario</span>
          <input type="text" placeholder="usuario" maxLength={100} {...campo("usuario")} />
        </label>
        <label>
          <span>Texto en el detalle o IP</span>
          <input type="text" placeholder="N° de solicitud, nombre, IP…" maxLength={200} {...campo("texto")} />
        </label>
        <label>
          <span>Desde</span>
          <input type="date" {...campo("desde")} />
        </label>
        <label>
          <span>Hasta</span>
          <input type="date" {...campo("hasta")} />
        </label>
        <div className={styles.botones}>
          <button type="submit" className={styles.btnPrimario}>Filtrar</button>
          <button type="button" className={styles.btnTexto} onClick={limpiar}>Limpiar</button>
        </div>
      </form>

      <div className={styles.panel}>
        <div className={styles.resumen}>
          {resultado ? `${resultado.total.toLocaleString("es-PA")} registro${resultado.total === 1 ? "" : "s"}` : "—"}
          {cargando && <span className={styles.cargando}>Cargando…</span>}
        </div>
        <div className={styles.tablaScroll}>
          <table className={styles.tabla}>
            <thead>
              <tr>
                <th>Fecha y hora</th>
                <th>Usuario</th>
                <th>Acción</th>
                <th>Detalle</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {resultado?.items.map((r) => (
                <Fragment key={r.id}>
                  <tr className={styles.fila} onClick={() => setAbierto(abierto === r.id ? null : r.id)}>
                    <td className={styles.nowrap}>{formatearFechaHora(r.creado_en)}</td>
                    <td>{r.username ?? "—"}</td>
                    <td><span className={styles.accion}>{ETIQUETA_ACCION[r.accion] ?? r.accion}</span></td>
                    <td className={styles.detalle}>{resumenDetalle(r.detalle)}</td>
                    <td className={styles.nowrap}>{r.ip ?? "—"}</td>
                  </tr>
                  {abierto === r.id && (
                    <tr className={styles.filaDetalle}>
                      <td colSpan={5}><pre>{JSON.stringify(r.detalle, null, 2)}</pre></td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {resultado && resultado.items.length === 0 && (
                <tr><td colSpan={5} className={styles.vacio}>Ningún registro coincide con los filtros.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className={styles.paginacion}>
          <button type="button" className={styles.btnTexto} disabled={pagina <= 1 || cargando} onClick={() => setPagina((p) => p - 1)}>
            ‹ Anterior
          </button>
          <span>Página {pagina} de {totalPaginas}</span>
          <button type="button" className={styles.btnTexto} disabled={pagina >= totalPaginas || cargando} onClick={() => setPagina((p) => p + 1)}>
            Siguiente ›
          </button>
        </div>
      </div>
    </MarcoPagina>
  );
}
