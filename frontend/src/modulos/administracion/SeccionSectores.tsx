import { useState } from "react";
import type { UsuarioSistema } from "../../api/admin";
import { apiCatalogos, type SectorAdmin } from "../../api/catalogos";
import { IconoAncla, IconoEditar, IconoUsuarios } from "../../components/Iconos";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";
import { SelectorUsuarios } from "./SelectorUsuarios";
import styles from "./PaginaCatalogos.module.css";

/** Un sector: su buzón, sus puestos (se cambian desde cada puesto) y sus
 *  funcionarios (UCVMM y supervisores de sector). Los sectores son fijos. */
function TarjetaSector({ sector, usuarios, rolesCandidatos, onCambio }: {
  sector: SectorAdmin;
  usuarios: UsuarioSistema[];
  rolesCandidatos: Set<number>;
  onCambio: (s: SectorAdmin) => void;
}) {
  const { mostrar } = useNotificacion();
  const [editando, setEditando] = useState(false);
  const [correo, setCorreo] = useState(sector.correo ?? "");
  const [asignando, setAsignando] = useState(false);
  const [seleccion, setSeleccion] = useState<Set<number>>(new Set(sector.usuarios.map((u) => u.id)));
  const [guardando, setGuardando] = useState(false);

  async function guardarCorreo() {
    setGuardando(true);
    try {
      onCambio(await apiCatalogos.actualizarSector(sector.id, correo.trim() || null));
      setEditando(false);
      mostrar("Correo del sector guardado.", "exito");
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo guardar el correo."), "error");
    } finally {
      setGuardando(false);
    }
  }

  async function guardarAsignacion() {
    setGuardando(true);
    try {
      onCambio(await apiCatalogos.asignarUsuariosSector(sector.id, [...seleccion]));
      setAsignando(false);
      mostrar("Asignación guardada.", "exito");
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo guardar la asignación."), "error");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className={styles.tarjeta}>
      <div className={styles.tarjetaCabecera}>
        {editando ? (
          <div className={styles.formEnLinea}>
            <input className={styles.input} value={correo} maxLength={255} type="email" autoFocus
              aria-label={`Correo de ${sector.nombre}`} placeholder="Correo del sector (opcional)"
              onChange={(e) => setCorreo(e.target.value)} />
            <button type="button" className={styles.btnPrimario} onClick={guardarCorreo} disabled={guardando}>Guardar</button>
            <button type="button" className={styles.btnTexto}
              onClick={() => { setEditando(false); setCorreo(sector.correo ?? ""); }}>
              Cancelar
            </button>
          </div>
        ) : (
          <>
            <div className={styles.tarjetaInfo}>
              <div className={styles.tarjetaNombre}>{sector.nombre}</div>
              <div className={styles.tarjetaMeta}>
                {sector.correo ?? "Sin correo: los avisos van al buzón general de UCVMM"}
              </div>
            </div>
            <button type="button" className={styles.btnIcono} onClick={() => setEditando(true)}
              title="Editar el correo" aria-label={`Editar el correo de ${sector.nombre}`}>
              <IconoEditar tamano={14} />
            </button>
          </>
        )}
      </div>

      <div className={styles.asignados}>
        <IconoAncla tamano={14} />
        {sector.puestos.length === 0
          ? <span className={styles.vacio}>Sin puestos de control</span>
          : sector.puestos.map((p) => <span key={p.id} className={styles.chip}>{p.nombre}</span>)}
      </div>

      <div className={styles.asignados}>
        <IconoUsuarios tamano={14} />
        {sector.usuarios.length === 0
          ? <span className={styles.vacio}>Sin funcionarios asignados</span>
          : sector.usuarios.map((u) => <span key={u.id} className={styles.chip}>{u.full_name}</span>)}
        <button type="button" className={styles.btnSecundario} onClick={() => {
          if (!asignando) setSeleccion(new Set(sector.usuarios.map((u) => u.id)));
          setAsignando((v) => !v);
        }}>
          {asignando ? "Cerrar" : "Asignar funcionarios"}
        </button>
      </div>

      {asignando && (
        <SelectorUsuarios
          usuarios={usuarios} rolesCandidatos={rolesCandidatos} seleccion={seleccion} onSeleccion={setSeleccion}
          ayuda="Se listan los usuarios de UCVMM y los supervisores de sector. Uno puede estar en los dos sectores (vacaciones, refuerzos)."
          onGuardar={guardarAsignacion} guardando={guardando}
        />
      )}
    </div>
  );
}

export function SeccionSectores({ sectores, usuarios, rolesCandidatos, onCambio }: {
  sectores: SectorAdmin[];
  usuarios: UsuarioSistema[];
  rolesCandidatos: Set<number>;
  onCambio: (s: SectorAdmin) => void;
}) {
  return (
    <>
      <p className={styles.descripcion}>
        UCVMM y los supervisores de sector ven solo las solicitudes de los puestos de su sector. El supervisor general
        y el Administrador ven las de los dos. El aviso de cada solicitud nueva va al correo del sector.
      </p>
      <div className={styles.lista}>
        {sectores.map((s) => (
          <TarjetaSector key={s.id} sector={s} usuarios={usuarios} rolesCandidatos={rolesCandidatos} onCambio={onCambio} />
        ))}
      </div>
    </>
  );
}
