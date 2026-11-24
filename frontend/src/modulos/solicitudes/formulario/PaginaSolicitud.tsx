/**
 * Formulario de Solicitud de Autorización Marítima (Formulario 3).
 *
 * Dos modos:
 *  - `/new`: un usuario de la agencia crea la solicitud (a nombre de su agencia).
 *  - `/solicitudes/:id/corregir`: la agencia corrige una solicitud que UCVMM
 *    devolvió. Se precarga todo; los documentos ya cargados se conservan
 *    salvo que se reemplacen o se quiten.
 *
 * La página carga lo necesario (useCargaFormulario) y muestra el formulario
 * (FormularioSolicitud). En una nueva, «Volver» le pregunta antes al formulario: con un
 * trámite elegido, regresa a los trámites; desde ahí, al inicio (2026-11-23).
 */
import { useCallback, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EstadoCarga } from "../../../components/EstadoCarga";
import { IconoAlerta } from "../../../components/Iconos";
import { MarcoPagina } from "../../../components/MarcoPagina";
import { useTituloDocumento } from "../../../hooks/useTituloDocumento";
import { FormularioSolicitud } from "./FormularioSolicitud";
import { useCargaFormulario } from "./useCargaFormulario";
import styles from "./PaginaSolicitud.module.css";

export default function PaginaSolicitud() {
  const { id } = useParams<{ id: string }>();
  const solicitudId = id ? Number(id) : null;
  const carga = useCargaFormulario(solicitudId);
  const navegar = useNavigate();
  const volverA = solicitudId !== null ? `/solicitudes/${solicitudId}` : "/dashboard";
  // Ya cargado, el título lo pone el encabezado del formulario.
  useTituloDocumento(solicitudId !== null ? "Corregir solicitud" : "Nueva solicitud");

  // Lo que hace «Volver» lo decide el formulario (lo registra al montarse).
  const volverDelFormulario = useRef<(() => boolean) | null>(null);
  const registrarVolver = useCallback((volver: (() => boolean) | null) => { volverDelFormulario.current = volver; }, []);
  // «Empezar de nuevo»: el formulario ya borró el borrador; se monta uno vacío.
  const [vuelta, setVuelta] = useState(0);
  const empezarDeNuevo = useCallback(() => setVuelta((v) => v + 1), []);

  return (
    <MarcoPagina volverA={volverA}
      alVolver={solicitudId === null ? () => { if (!volverDelFormulario.current?.()) navegar(volverA); } : undefined}>
      {carga.estado === "cargando" && <EstadoCarga texto="Cargando formulario…" pagina />}
      {carga.estado === "error" && (
        <div className={styles.errorCarga} role="alert">
          <IconoAlerta /> {carga.mensaje}
          {solicitudId !== null && <Link to={volverA} className={styles.enlace}>Ver la solicitud</Link>}
        </div>
      )}
      {carga.estado === "lista" && (
        <FormularioSolicitud key={`${solicitudId ?? "nueva"}-${vuelta}`} {...carga.datos}
          borrador={vuelta === 0 ? carga.datos.borrador : null}
          registrarVolver={registrarVolver} onEmpezarDeNuevo={empezarDeNuevo} />
      )}
    </MarcoPagina>
  );
}
