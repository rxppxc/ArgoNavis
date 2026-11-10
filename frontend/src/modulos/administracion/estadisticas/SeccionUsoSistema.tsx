import { useEffect, useState } from "react";
import { apiAdmin, type UsoSistema } from "../../../api/admin";
import { EstadoCarga } from "../../../components/EstadoCarga";
import { IconoArchivo, IconoBarco, IconoDisco, IconoUsuarios } from "../../../components/Iconos";
import { formatBytes } from "../../../utils/format";
import { mensajeDeError } from "../../../utils/errores";
import { cifra, porcentaje, segun } from "./calculos";
import { BarrasHorizontales, FilaGlobo, Indicador, TarjetaGrafico } from "./Graficos";
import graficos from "./Graficos.module.css";
import styles from "./Estadisticas.module.css";

/** Cuentas, agencias y documentos: totales a hoy, sin el filtro de periodo. */
export default function SeccionUsoSistema() {
  // Resultado único: "cargando" se deriva de que aún no hay respuesta.
  const [resultado, setResultado] = useState<{ uso: UsoSistema | null; error: string | null } | null>(null);

  useEffect(() => {
    let cancelado = false;
    apiAdmin.obtenerUso()
      .then((uso) => { if (!cancelado) setResultado({ uso, error: null }); })
      .catch((e) => {
        if (!cancelado) setResultado({ uso: null, error: mensajeDeError(e, "No se pudo cargar el uso del sistema.") });
      });
    return () => { cancelado = true; };
  }, []);

  const uso = resultado?.uso ?? null;
  const agencias = uso?.top_agencias ?? [];

  const tabla = (
    <table className={graficos.tabla}>
      <thead><tr><th>Agencia</th><th>Solicitudes</th></tr></thead>
      <tbody>
        {agencias.map((a) => (
          <tr key={a.agencia_id}><td>{a.nombre}</td><td className={graficos.numero}>{cifra(a.total)}</td></tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <section className={styles.seccion} aria-labelledby="titulo-uso">
      <div className={styles.cabeceraSeccion}>
        <h2 id="titulo-uso">Uso del sistema</h2>
        <p>Totales a hoy (no dependen del periodo).</p>
      </div>

      {resultado?.error && <div className={styles.error} role="alert">{resultado.error}</div>}

      {!resultado ? <EstadoCarga texto="Cargando el uso del sistema…" /> : uso && (
        <>
          <div className={`${styles.indicadores} ${styles.cuatro}`}>
            <Indicador
              icono={<IconoUsuarios />} etiqueta="Usuarios registrados" valor={cifra(uso.usuarios)}
              medidor={{ valor: uso.usuarios_activos, total: uso.usuarios, serie: "revision" }}
              nota={`${cifra(uso.usuarios_activos)} ${segun(uso.usuarios_activos, "activo", "activos")} (${porcentaje(uso.usuarios_activos, uso.usuarios)})`}
            />
            <Indicador icono={<IconoBarco tamano={20} />} etiqueta="Agencias navieras" valor={cifra(uso.agencias)} />
            <Indicador icono={<IconoArchivo />} etiqueta="Documentos en expedientes" valor={cifra(uso.documentos)} />
            <Indicador icono={<IconoDisco />} etiqueta="Almacenamiento usado" valor={formatBytes(uso.almacenamiento_bytes)} />
          </div>

          <div className={styles.grilla}>
            <TarjetaGrafico
              ancha
              titulo="Agencias con más solicitudes"
              descripcion="Las cinco primeras, desde el inicio."
              tabla={agencias.length > 0 ? tabla : undefined}
            >
              {agencias.length === 0 ? <p className={graficos.vacio}>Sin solicitudes aún.</p> : (
                <BarrasHorizontales
                  filas={agencias.map((a) => ({
                    clave: String(a.agencia_id),
                    nombre: a.nombre,
                    segmentos: [{ serie: "revision", valor: a.total }],
                    descripcion: `${a.nombre}: ${cifra(a.total)} ${segun(a.total, "solicitud", "solicitudes")}`,
                  }))}
                  globo={(clave) => {
                    const a = agencias.find((x) => String(x.agencia_id) === clave);
                    return a && (
                      <>
                        <p className={graficos.globoTitulo}>{a.nombre}</p>
                        <FilaGlobo serie="revision" valor={cifra(a.total)} etiqueta={segun(a.total, "solicitud", "solicitudes")} />
                      </>
                    );
                  }}
                />
              )}
            </TarjetaGrafico>
          </div>
        </>
      )}
    </section>
  );
}
