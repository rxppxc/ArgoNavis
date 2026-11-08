import type { EstadisticasSolicitudes } from "../../../api/solicitudes";
import { cifra, porcentaje } from "./calculos";
import { BarrasHorizontales, FilaGlobo, TarjetaGrafico, type FilaBarras } from "./Graficos";
import styles from "./Graficos.module.css";

type Tramite = EstadisticasSolicitudes["por_tipo"][number];

/** Barras por trámite, de la que más llegó a la que menos. */
export default function GraficoTramites({ tramites }: { tramites: Tramite[] }) {
  const ordenados = [...tramites].sort((a, b) => b.recibidas - a.recibidas);
  const porCodigo = new Map(ordenados.map((t) => [t.codigo, t]));
  const filas: FilaBarras[] = ordenados.map((t) => ({
    clave: t.codigo,
    nombre: t.nombre,
    segmentos: [{ serie: "revision", valor: t.recibidas }],
    descripcion: `${t.nombre}: ${cifra(t.recibidas)} recibidas, ${cifra(t.aprobadas)} aprobadas, `
      + `${cifra(t.negadas)} denegadas, ${cifra(t.expiradas)} expiradas`,
  }));

  const tabla = (
    <table className={styles.tabla}>
      <thead>
        <tr><th>Trámite</th><th>Recibidas</th><th>Aprobadas</th><th>Denegadas</th><th>Expiradas</th></tr>
      </thead>
      <tbody>
        {ordenados.map((t) => (
          <tr key={t.codigo}>
            <td>{t.nombre}</td>
            <td className={styles.numero}>{cifra(t.recibidas)}</td>
            <td className={styles.numero}>{cifra(t.aprobadas)}</td>
            <td className={styles.numero}>{cifra(t.negadas)}</td>
            <td className={styles.numero}>{cifra(t.expiradas)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <TarjetaGrafico
      titulo="¿Qué trámites se piden más?"
      descripcion="Solicitudes recibidas en el periodo, por tipo de trámite."
      tabla={ordenados.length > 0 ? tabla : undefined}
    >
      {ordenados.length === 0 ? <p className={styles.vacio}>Sin solicitudes en el periodo.</p> : (
        <BarrasHorizontales
          filas={filas}
          globo={(codigo) => {
            const t = porCodigo.get(codigo);
            if (!t) return null;
            return (
              <>
                <p className={styles.globoTitulo}>{t.nombre}</p>
                <FilaGlobo serie="revision" valor={cifra(t.recibidas)} etiqueta="Recibidas" />
                <FilaGlobo serie="aprobada" valor={cifra(t.aprobadas)} etiqueta={`Aprobadas (${porcentaje(t.aprobadas, t.recibidas)})`} />
                <FilaGlobo serie="denegada" valor={cifra(t.negadas)} etiqueta="Denegadas" />
                <FilaGlobo serie="expirada" valor={cifra(t.expiradas)} etiqueta="Expiradas" />
              </>
            );
          }}
        />
      )}
    </TarjetaGrafico>
  );
}
