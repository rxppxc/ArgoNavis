import { memo } from "react";
import type { Pais } from "../../../api/catalogos";
import type { DocumentoSolicitud, RangoMarino, TripulanteEntrada } from "../../../api/solicitudes";
import { IconoAlerta, IconoBasura, IconoChevronAbajo } from "../../../components/Iconos";
import { SelectorBuscable } from "../../../components/SelectorBuscable";
import { SelectorFecha } from "../../../components/SelectorFecha";
import type { OpcionBuscable } from "../../../utils/busqueda";
import { isoATexto, sumarDias, sumarMeses } from "../../../utils/calendario";
import type { CasillaFormulario } from "../checklist";
import { ChecklistDocumentos } from "./ChecklistDocumentos";
import { fechaISOLocal } from "../../../utils/fechas";
import { ETIQUETA_RANGO, ETIQUETA_SEXO, TODOS_LOS_RANGOS, formatearFecha } from "../presentacion";
import {
  EDAD_MINIMA, MESES_VIGENCIA_PASAPORTE, NACIMIENTO_MINIMO, estadoPasaporte, nacimientoMaximo, portaLibreta,
  textoVigenciaCorta, vigenciaMinimaPasaporte, type FichaTripulante,
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
  /** Al aprobar se avisa que se debe tramitar la custodia (lo dice el proceso del trámite). */
  avisoCustodia:    boolean;
  /** Al corregir, si la revisión le marcó impedimento: tiene que quitarse (2026-11-26). */
  conImpedimento?:  boolean;
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

/** «Visa» · «Visa» y «Formulario No. 6» · «A», «B» y «C». */
function enumerar(nombres: string[]): string {
  const citados = nombres.map((n) => `«${n}»`);
  return citados.length < 2 ? citados.join("") : `${citados.slice(0, -1).join(", ")} y ${citados[citados.length - 1]}`;
}

/** Las visas, que el aviso de un restringido nombra aunque su condición sea otra. */
const VISAS = ["DOC-VISA", "DOC-VISA-MARINO"];

/** El aviso de un tripulante de nacionalidad restringida: lo que debe adjuntar (la Visa en
 *  el trámite de Técnico y al Militar, la Visa Especial de Marino al Marino y al Pasajero,
 *  desde el 2026-11-18, y el Form. No. 6 en Desembarque) y, en los trámites que lo dicen,
 *  que al aprobarse se tramita la custodia. */
function textoRestringida(documentos: string[], avisoCustodia: boolean): string {
  // Sin nada que adjuntar ni custodia (un Militar fuera del trámite de Técnico, 2026-11-26): solo se señala.
  if (!documentos.length && !avisoCustodia) return "Nacionalidad restringida.";
  const partes = ["Nacionalidad restringida:"];
  if (documentos.length) partes.push(`debe adjuntar ${enumerar(documentos)}.`);
  if (avisoCustodia) {
    partes.push(`${documentos.length ? "Al" : "al"} aprobarse, la agencia deberá realizar el trámite de solicitud de custodia.`);
  }
  return partes.join(" ");
}

/** Ficha de un tripulante con sus propios documentos. Memoizada: con muchos
 *  tripulantes, escribir en uno no vuelve a pintar los demás. Los países van en
 *  selectores con buscador, que pintan su lista solo abiertos. Se puede contraer
 *  para no alargar la página. */
export const TarjetaTripulante = memo(function TarjetaTripulante({
  ficha, indice, puedeQuitar, opcionesPais, paises, validaVigencia, fechaReferencia, rangosPermitidos,
  avisoCustodia, conImpedimento = false, casillas, nuevos, existentes, contraida,
  onCambiar, onQuitar, onAlternar, onElegir, onDescartar, onVer,
}: Props) {
  const conLibreta = portaLibreta(ficha);
  const pais = paises.get(ficha.nacionalidad);
  // Se señala en todos los trámites (desde el 2026-11-14), con la visa que le corresponda.
  const restringida = pais?.nacionalidad_restringida ?? false;
  // Lo que se le pide por su nacionalidad (la visa y, en Desembarque, el Form. No. 6). Desde el 2026-11-18,
  // al Marino y al Pasajero, la Visa Especial de Marino, que en Embarque y Cambio de nave ya se le pide a
  // todo extranjero (otra condición): también se nombra.
  const porRestringida = casillas
    .filter((c) => c.condicion === "nacionalidad_restringida" || VISAS.includes(c.documento_codigo))
    .map((c) => c.documento_nombre);
  // El pasaporte, con al menos 3 meses de vigencia desde la operación (2026-11-13).
  const pasaporte = estadoPasaporte(ficha.pasaporte_expira, fechaReferencia);
  const pasaporteVencido = pasaporte === "vencido";
  const pasaporteCorto = pasaporte === "corto";
  // El seamanbook vencido solo se avisa: se puede enviar igual.
  const libretaVencida = conLibreta && !!ficha.libreta_expira && ficha.libreta_expira < fechaReferencia;
  const avisoResumen = pasaporteVencido || libretaVencida ? "documento vencido"
    : pasaporteCorto ? `pasaporte con menos de ${MESES_VIGENCIA_PASAPORTE} meses de vigencia` : null;
  const rangos = rangosPermitidos ?? TODOS_LOS_RANGOS;
  // Un solo rango posible (Sellado de Shore Pass: solo Marino, 2026-11-14): ya elegido, y se dice.
  const rangoUnico = rangos.length === 1 ? rangos[0] : null;
  const idNotaRango = `tripulante-${ficha.clave}-nota-rango`;
  const nombre = `${ficha.nombre} ${ficha.apellido}`.trim();

  // Las opcionales no cuentan: completo es tener todas las obligatorias.
  const obligatorias = casillas.filter((c) => c.obligatoria);
  const cubiertas = obligatorias.filter((c) => nuevos[c.clave] || existentes[c.clave]?.length).length;
  const completo = cubiertas === obligatorias.length;

  // Los rangos de los calendarios (SelectorFecha, 2026-11-23): lo que no se puede elegir va rayado.
  const hoy = fechaISOLocal();
  const nacidoHasta = nacimientoMaximo(hoy);
  const despuesDelNacimiento = ficha.fecha_nacimiento ? sumarDias(ficha.fecha_nacimiento, 1) : undefined;
  const minimoPasaporte = validaVigencia ? vigenciaMinimaPasaporte(fechaReferencia) : despuesDelNacimiento;

  const campo = (nombreCampo: keyof TripulanteEntrada) => ({
    value: (ficha[nombreCampo] as string | null | undefined) ?? "",
    onChange: (e: { target: { value: string } }) => onCambiar(ficha.clave, nombreCampo, e.target.value),
  });

  return (
    <div id={`tripulante-${ficha.clave}`} className={`${styles.marino} ${contraida ? styles.marinoContraido : ""}`}>
      <div className={styles.marinoCabecera}>
        <span className={styles.marinoNum}>{indice + 1}</span>
        <span className={styles.marinoTitulo}>{nombre || "Nuevo tripulante"}</span>
        {restringida && <span className={styles.chipRestringida}>Nacionalidad restringida</span>}
        {casillas.length > 0 && (
          <span className={completo ? styles.chipDocsOk : styles.chipDocsFalta}>
            {cubiertas}/{obligatorias.length} documentos
          </span>
        )}
        <button type="button" className={styles.btnContraer} onClick={() => onAlternar(ficha.clave)}
          aria-expanded={!contraida} aria-label={contraida ? `Expandir tripulante ${indice + 1}` : `Contraer tripulante ${indice + 1}`}
          title={contraida ? "Expandir" : "Contraer"}>
          <span className={contraida ? styles.chevronCerrado : styles.chevronAbierto}><IconoChevronAbajo /></span>
        </button>
        {puedeQuitar && (
          <button type="button" className={styles.btnQuitar}
            onClick={() => onQuitar(ficha.clave)} title="Quitar tripulante"
            aria-label={`Quitar tripulante ${indice + 1}`}>
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
            <SelectorFecha className={styles.campo} etiqueta="Fecha de nacimiento *" valor={ficha.fecha_nacimiento ?? ""}
              onCambiar={(iso) => onCambiar(ficha.clave, "fecha_nacimiento", iso)}
              min={NACIMIENTO_MINIMO} max={nacidoHasta} vista={sumarMeses(hoy, -12 * 30)}
              motivoAntes="La fecha de nacimiento no puede ser anterior a 1900."
              motivoDespues={`Debe ser mayor de edad: ${EDAD_MINIMA} años cumplidos (nacido el ${isoATexto(nacidoHasta)} o antes).`}
              ayuda={`Mayor de edad: nacido el ${isoATexto(nacidoHasta)} o antes.`} />

            <SelectorBuscable className={styles.campo} etiqueta="País de nacimiento *" opciones={opcionesPais}
              valor={ficha.pais_nacimiento} onCambiar={(valor) => onCambiar(ficha.clave, "pais_nacimiento", valor)} />
            <SelectorBuscable className={styles.campo} etiqueta="Nacionalidad *" opciones={opcionesPais}
              valor={ficha.nacionalidad} onCambiar={(valor) => onCambiar(ficha.clave, "nacionalidad", valor)} />
            <label className={styles.campo}>
              <span>Rango *</span>
              <select {...campo("rango")} aria-describedby={rangoUnico ? idNotaRango : undefined}>
                {rangos.map((r) => (
                  <option key={r} value={r}>{ETIQUETA_RANGO[r]}</option>
                ))}
              </select>
              {/* aria-hidden: no se suma al nombre del campo; el lector la lee como su descripción. */}
              {rangoUnico && (
                <small id={idNotaRango} className={styles.notaCampo} aria-hidden="true">
                  Único rango de este trámite.
                </small>
              )}
            </label>

            <label className={styles.campo}>
              <span>N° de pasaporte *</span>
              <input type="text" maxLength={100} autoComplete="off" {...campo("pasaporte")} />
            </label>
            {/* Con la vigencia del trámite, los días con menos de 3 meses desde la operación
                van rayados; el aviso de la tarjeta (abajo) explica la regla entera. */}
            <SelectorFecha className={styles.campo} etiqueta="Vence el pasaporte *" valor={ficha.pasaporte_expira ?? ""}
              onCambiar={(iso) => onCambiar(ficha.clave, "pasaporte_expira", iso)}
              min={minimoPasaporte}
              motivoAntes={validaVigencia
                ? `Debe vencer el ${isoATexto(minimoPasaporte)} o después.`
                : "El pasaporte debe vencer después de la fecha de nacimiento."}
              ayuda={validaVigencia
                ? `Debe vencer el ${isoATexto(minimoPasaporte)} o después: ${MESES_VIGENCIA_PASAPORTE} meses desde la operación.`
                : undefined} />
            {conLibreta ? (
              <>
                {/* El número y el vencimiento del seamanbook son opcionales (2026-11-23). */}
                <label className={styles.campo}>
                  <span>N° de seamanbook <em>(opcional)</em></span>
                  <input type="text" maxLength={100} autoComplete="off" {...campo("libreta_marino")} />
                </label>
                <SelectorFecha className={styles.campo} etiqueta={<>Vence el seamanbook <em>(opcional)</em></>}
                  valor={ficha.libreta_expira ?? ""} borrable
                  onCambiar={(iso) => onCambiar(ficha.clave, "libreta_expira", iso)}
                  min={despuesDelNacimiento}
                  motivoAntes="El seamanbook debe vencer después de la fecha de nacimiento."
                  ayuda="Si ya venció, puedes enviar igual: quedará señalado en la revisión." />
              </>
            ) : (
              <div className={styles.sinLibreta}>
                {ETIQUETA_RANGO[ficha.rango]}: no porta seamanbook, no se pide libreta ni se valida su vencimiento.
              </div>
            )}
          </div>

          {(conImpedimento || restringida || pasaporteVencido || pasaporteCorto || libretaVencida) && (
            <div className={styles.marinoAlertas}>
              {conImpedimento && (
                <div className={styles.alertaError} role="alert">
                  <IconoAlerta tamano={13} />
                  Tiene impedimento según la revisión: la solicitud no puede avanzar con esta persona. Quítala; si va
                  otra persona, agrégala como tripulante nuevo.
                </div>
              )}
              {restringida && (
                <div className={porRestringida.length ? styles.alertaInfo : styles.alertaAviso}>
                  <IconoAlerta tamano={13} />
                  {textoRestringida(porRestringida, avisoCustodia)}
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
              <div className={styles.marinoDocsTitulo}>Documentos de {nombre || `tripulante ${indice + 1}`}</div>
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
