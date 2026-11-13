import { memo } from "react";
import type { Pais } from "../../api/catalogos";
import type { DocumentoSolicitud, RangoMarino, TripulanteEntrada } from "../../api/solicitudes";
import { IconoAlerta, IconoBasura, IconoChevronAbajo } from "../../components/Iconos";
import { SelectorBuscable } from "../../components/SelectorBuscable";
import type { OpcionBuscable } from "../../utils/busqueda";
import type { CasillaFormulario } from "./checklist";
import { ChecklistDocumentos } from "./ChecklistDocumentos";
import { FechaEnPalabras } from "./FechaEnPalabras";
import { ETIQUETA_RANGO, ETIQUETA_SEXO, TODOS_LOS_RANGOS, formatearFecha, hoyISO } from "./presentacion";
import {
  MESES_VIGENCIA_PASAPORTE, NACIMIENTO_MINIMO, estadoPasaporte, nacimientoMaximo, portaLibreta, textoVigenciaCorta,
  type FichaTripulante,
} from "./validacionFormulario";
import styles from "./PaginaSolicitud.module.css";

interface Props {
  ficha:            FichaTripulante;
  indice:           number;
  puedeQuitar:      boolean;
  opcionesPais:     OpcionBuscable[];
  paises:           Map<string, Pais>;
  validaVigencia:   boolean;
  fechaReferencia:  string;
  /** Rangos que admite el trámite (null = cualquiera). */
  rangosPermitidos: RangoMarino[] | null;
  /** El trámite exige el Form. No. 6 a los restringidos (Desembarque, como en el Form. 3). */
  exigeCustodia:    boolean;
  /** Al aprobar se avisa que se debe tramitar la custodia (lo dice el proceso del trámite). */
  avisoCustodia:    boolean;
  /** Casillas del checklist que corresponden a este tripulante. */
  casillas:   CasillaFormulario[];
  nuevos:     Record<string, File>;
  existentes: Record<string, DocumentoSolicitud[]>;
  contraida:  boolean;
  onCambiar:   (clave: string, campo: keyof TripulanteEntrada, valor: string) => void;
  onQuitar:    (clave: string) => void;
  onAlternar:  (clave: string) => void;
  onElegir:    (clave: string, archivo: File) => void;
  onDescartar: (clave: string) => void;
  onVer:       (documento: DocumentoSolicitud) => void;
}

/** Ficha de un tripulante con sus propios documentos. Memoizada: con muchos
 *  tripulantes, escribir en uno no vuelve a pintar los demás. Los países van en
 *  selectores con buscador, que pintan su lista solo abiertos. Se puede contraer
 *  para no alargar la página. */
export const TarjetaTripulante = memo(function TarjetaTripulante({
  ficha, indice, puedeQuitar, opcionesPais, paises, validaVigencia, fechaReferencia, rangosPermitidos,
  exigeCustodia, avisoCustodia, casillas, nuevos, existentes, contraida,
  onCambiar, onQuitar, onAlternar, onElegir, onDescartar, onVer,
}: Props) {
  const conLibreta = portaLibreta(ficha);
  const pais = paises.get(ficha.nacionalidad);
  // Solo se señala en los trámites cuyo proceso menciona la custodia.
  const restringida = (pais?.nacionalidad_restringida ?? false) && (exigeCustodia || avisoCustodia);
  // El pasaporte, con al menos 3 meses de vigencia desde la operación (2026-11-13).
  const pasaporte = estadoPasaporte(ficha.pasaporte_expira, fechaReferencia);
  const pasaporteVencido = pasaporte === "vencido";
  const pasaporteCorto = pasaporte === "corto";
  // El seamanbook vencido solo se avisa: se puede enviar igual.
  const libretaVencida = conLibreta && !!ficha.libreta_expira && ficha.libreta_expira < fechaReferencia;
  const avisoResumen = pasaporteVencido || libretaVencida ? "documento vencido"
    : pasaporteCorto ? `pasaporte con menos de ${MESES_VIGENCIA_PASAPORTE} meses de vigencia` : null;
  const rangos = rangosPermitidos ?? TODOS_LOS_RANGOS;
  const nombre = `${ficha.nombre} ${ficha.apellido}`.trim();

  // Las opcionales no cuentan: completo es tener todas las obligatorias.
  const obligatorias = casillas.filter((c) => c.obligatoria);
  const cubiertas = obligatorias.filter((c) => nuevos[c.clave] || existentes[c.clave]?.length).length;
  const completo = cubiertas === obligatorias.length;

  const campo = (nombreCampo: keyof TripulanteEntrada) => ({
    value: (ficha[nombreCampo] as string | null | undefined) ?? "",
    onChange: (e: { target: { value: string } }) => onCambiar(ficha.clave, nombreCampo, e.target.value),
  });

  return (
    <div id={`tripulante-${ficha.clave}`} className={`${styles.marino} ${contraida ? styles.marinoContraido : ""}`}>
      <div className={styles.marinoCabecera}>
        <span className={styles.marinoNum}>{indice + 1}</span>
        <span className={styles.marinoTitulo}>{nombre || "Nuevo pasajero"}</span>
        {restringida && <span className={styles.chipRestringida}>Nacionalidad restringida</span>}
        {casillas.length > 0 && (
          <span className={completo ? styles.chipDocsOk : styles.chipDocsFalta}>
            {cubiertas}/{obligatorias.length} documentos
          </span>
        )}
        <button type="button" className={styles.btnContraer} onClick={() => onAlternar(ficha.clave)}
          aria-expanded={!contraida} aria-label={contraida ? `Expandir pasajero ${indice + 1}` : `Contraer pasajero ${indice + 1}`}
          title={contraida ? "Expandir" : "Contraer"}>
          <span className={contraida ? styles.chevronCerrado : styles.chevronAbierto}><IconoChevronAbajo /></span>
        </button>
        {puedeQuitar && (
          <button type="button" className={styles.btnQuitar}
            onClick={() => onQuitar(ficha.clave)} title="Quitar pasajero"
            aria-label={`Quitar pasajero ${indice + 1}`}>
            <IconoBasura tamano={14} />
          </button>
        )}
      </div>

      {contraida ? (
        <div className={styles.marinoResumen}>
          {[pais?.nombre, ficha.pasaporte && `Pasaporte ${ficha.pasaporte}`, ETIQUETA_RANGO[ficha.rango]]
            .filter(Boolean).join(" · ") || "Sin datos todavía"}
          {avisoResumen && <span className={styles.resumenAlerta}> · {avisoResumen}</span>}
        </div>
      ) : (
        <>
          <div className={styles.marinoGrid}>
            <label className={styles.campo}>
              <span>Nombre(s) *</span>
              <input type="text" maxLength={150} autoComplete="off" {...campo("nombre")} />
            </label>
            <label className={styles.campo}>
              <span>Apellido(s) *</span>
              <input type="text" maxLength={150} autoComplete="off" {...campo("apellido")} />
            </label>
            <label className={styles.campo}>
              <span>Sexo *</span>
              <select {...campo("sexo")}>
                <option value="">Selecciona…</option>
                {Object.entries(ETIQUETA_SEXO).map(([valor, etiqueta]) => (
                  <option key={valor} value={valor}>{etiqueta}</option>
                ))}
              </select>
            </label>
            <label className={styles.campo}>
              <span>Fecha de nacimiento *</span>
              <input type="date" min={NACIMIENTO_MINIMO} max={nacimientoMaximo(hoyISO())} {...campo("fecha_nacimiento")} />
              <FechaEnPalabras iso={ficha.fecha_nacimiento} />
            </label>

            <SelectorBuscable className={styles.campo} etiqueta="País de nacimiento *" opciones={opcionesPais}
              valor={ficha.pais_nacimiento} onCambiar={(valor) => onCambiar(ficha.clave, "pais_nacimiento", valor)} />
            <SelectorBuscable className={styles.campo} etiqueta="Nacionalidad *" opciones={opcionesPais}
              valor={ficha.nacionalidad} onCambiar={(valor) => onCambiar(ficha.clave, "nacionalidad", valor)} />
            <label className={styles.campo}>
              <span>Rango *</span>
              <select {...campo("rango")}>
                {rangos.map((r) => (
                  <option key={r} value={r}>{ETIQUETA_RANGO[r]}</option>
                ))}
              </select>
            </label>
            <label className={styles.campo}>
              <span>Ocupación *</span>
              <input type="text" maxLength={150} placeholder="Ej. Capitán, cocinero" {...campo("ocupacion")} />
            </label>

            <label className={styles.campo}>
              <span>N° de pasaporte *</span>
              <input type="text" maxLength={100} autoComplete="off" {...campo("pasaporte")} />
            </label>
            <label className={styles.campo}>
              <span>Vence el pasaporte *</span>
              <input type="date" min={ficha.fecha_nacimiento || undefined} {...campo("pasaporte_expira")} />
              <FechaEnPalabras iso={ficha.pasaporte_expira} />
            </label>
            {conLibreta ? (
              <>
                <label className={styles.campo}>
                  <span>N° de seamanbook *</span>
                  <input type="text" maxLength={100} autoComplete="off" {...campo("libreta_marino")} />
                </label>
                <label className={styles.campo}>
                  <span>Vence el seamanbook *</span>
                  <input type="date" min={ficha.fecha_nacimiento || undefined} {...campo("libreta_expira")} />
                  <FechaEnPalabras iso={ficha.libreta_expira} />
                </label>
              </>
            ) : (
              <div className={styles.sinLibreta}>
                {ETIQUETA_RANGO[ficha.rango]}: no porta seamanbook, no se pide libreta ni se valida su vencimiento.
              </div>
            )}
          </div>

          {(restringida || pasaporteVencido || pasaporteCorto || libretaVencida) && (
            <div className={styles.marinoAlertas}>
              {restringida && (
                <div className={exigeCustodia ? styles.alertaInfo : styles.alertaAviso}>
                  <IconoAlerta tamano={13} />
                  {exigeCustodia
                    ? "Nacionalidad restringida: debe adjuntar el Formulario No. 6 de custodia aprobada."
                    : "Nacionalidad restringida: al aprobarse, la agencia deberá realizar el trámite de solicitud de custodia."}
                </div>
              )}
              {pasaporteVencido && (
                <div className={validaVigencia ? styles.alertaError : styles.alertaAviso}>
                  <IconoAlerta tamano={13} />
                  El pasaporte vence el {formatearFecha(ficha.pasaporte_expira)}, antes de la operación
                  {validaVigencia
                    ? ` — este trámite exige al menos ${MESES_VIGENCIA_PASAPORTE} meses de vigencia a partir de la operación.`
                    : "."}
                </div>
              )}
              {pasaporteCorto && (
                <div className={validaVigencia ? styles.alertaError : styles.alertaAviso}>
                  <IconoAlerta tamano={13} />
                  El pasaporte {textoVigenciaCorta(ficha.pasaporte_expira, fechaReferencia)}
                </div>
              )}
              {libretaVencida && (
                // Solo un aviso (2026-11-13): el seamanbook vencido no impide enviar.
                <div className={styles.alertaAviso}>
                  <IconoAlerta tamano={13} />
                  El seamanbook vence el {formatearFecha(ficha.libreta_expira)}, antes de la operación. Puedes enviar
                  la solicitud igual: quedará señalado en la revisión.
                </div>
              )}
            </div>
          )}

          {casillas.length > 0 && (
            <div className={styles.marinoDocs}>
              <div className={styles.marinoDocsTitulo}>Documentos de {nombre || `pasajero ${indice + 1}`}</div>
              <ChecklistDocumentos
                casillas={casillas}
                nuevos={nuevos}
                existentes={existentes}
                sinTripulante
                onElegir={onElegir}
                onDescartar={onDescartar}
                onVer={onVer}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
});
