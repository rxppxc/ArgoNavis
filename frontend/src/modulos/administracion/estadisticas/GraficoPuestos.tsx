import type { EstadisticasSolicitudes } from "../../../api/solicitudes";
import { cifra } from "./calculos";
import { BarrasHorizontales, FilaGlobo, Leyenda, TarjetaGrafico, type FilaBarras } from "./Graficos";
import styles from "./Graficos.module.css";

type Puesto = EstadisticasSolicitudes["por_puesto"][number];

/** Las aprobadas de un puesto terminan finalizadas o expiradas, o siguen por finalizar. */
const porFinalizar = (p: Puesto) => Math.max(0, p.aprobadas - p.finalizadas - p.expiradas);

/** Por puesto: las autorizaciones aprobadas, partidas en lo que pasó con ellas. */
export default function GraficoPuestos({ puestos }: { puestos: Puesto[] }) {
  // Un puesto con solicitudes, pero ninguna aprobada, no tiene nada que mostrar aquí.
  const conAprobadas = puestos.filter((p) => p.aprobadas > 0);
  const porNombre = new Map(conAprobadas.map((p) => [p.puesto, p]));
  const filas: FilaBarras[] = conAprobadas.map((p) => ({
    clave: p.puesto,
    nombre: p.puesto,
    segmentos: [
      { serie: "finalizada", valor: p.finalizadas },
      { serie: "aprobada", valor: porFinalizar(p) },
      { serie: "expirada", valor: p.expiradas },
    ],
    descripcion: `${p.puesto}: ${cifra(p.aprobadas)} aprobadas; ${cifra(p.finalizadas)} finalizadas, `
      + `${cifra(porFinalizar(p))} por finalizar y ${cifra(p.expiradas)} expiradas`,
  }));

  const tabla = (
    <table className={styles.tabla}>
      <thead>
        <tr>
          <th>Puesto</th><th>Aprobadas</th><th>Finalizadas</th><th>Por finalizar</th><th>Expiradas</th>
        </tr>
      </thead>
      <tbody>
        {conAprobadas.map((p) => (
          <tr key={p.puesto}>
            <td>{p.puesto}</td>
            <td className={styles.numero}>{cifra(p.aprobadas)}</td>
            <td className={styles.numero}>{cifra(p.finalizadas)}</td>
            <td className={styles.numero}>{cifra(porFinalizar(p))}</td>
            <td className={styles.numero}>{cifra(p.expiradas)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <TarjetaGrafico
      titulo="¿Qué pasó en cada puesto de control?"
      descripcion="Las autorizaciones aprobadas para cada puesto y en qué terminaron. La cifra es el total aprobado."
      tabla={conAprobadas.length > 0 ? tabla : undefined}
    >
      {conAprobadas.length === 0 ? <p className={styles.vacio}>Sin autorizaciones aprobadas en el periodo.</p> : (
        <>
          <Leyenda items={[
            { serie: "finalizada", etiqueta: "Finalizadas" },
            { serie: "aprobada", etiqueta: "Por finalizar" },
            { serie: "expirada", etiqueta: "Expiradas" },
          ]} />
          <BarrasHorizontales
            filas={filas}
            globo={(nombre) => {
              const p = porNombre.get(nombre);
              if (!p) return null;
              return (
                <>
                  <p className={styles.globoTitulo}>{p.puesto}</p>
                  <FilaGlobo valor={cifra(p.aprobadas)} etiqueta="Aprobadas" />
                  <FilaGlobo serie="finalizada" valor={cifra(p.finalizadas)} etiqueta="Finalizadas" />
                  <FilaGlobo serie="aprobada" valor={cifra(porFinalizar(p))} etiqueta="Por finalizar" />
                  <FilaGlobo serie="expirada" valor={cifra(p.expiradas)} etiqueta="Expiradas" />
                </>
              );
            }}
          />
        </>
      )}
    </TarjetaGrafico>
  );
}
