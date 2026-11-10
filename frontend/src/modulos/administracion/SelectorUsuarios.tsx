import { useState } from "react";
import type { UsuarioSistema } from "../../api/admin";
import styles from "./PaginaCatalogos.module.css";

interface Props {
  usuarios: UsuarioSistema[];
  /** Los roles con el permiso que hace falta: los demás se listan solo con «Mostrar todos». */
  rolesCandidatos: Set<number>;
  seleccion: Set<number>;
  onSeleccion: (s: Set<number>) => void;
  ayuda: string;
  /** Un dato más del usuario («hoy en Agencia X»). */
  detalle?: (u: UsuarioSistema) => string | null;
  onGuardar: () => void;
  guardando: boolean;
}

/** La lista para asignar usuarios a una agencia, un puesto o un sector (el mismo
 *  selector en los tres; antes estaba dentro de la tarjeta de agencias y puestos).
 *  Asignar no da acceso sin el permiso del rol: por eso se puede mostrar a todos. */
export function SelectorUsuarios({ usuarios, rolesCandidatos, seleccion, onSeleccion, ayuda, detalle, onGuardar, guardando }: Props) {
  const [todos, setTodos] = useState(false);
  const candidatos = usuarios.filter(
    (u) => todos || (u.rol_id !== null && rolesCandidatos.has(u.rol_id)) || seleccion.has(u.id),
  );

  function alternar(id: number, marcado: boolean) {
    const s = new Set(seleccion);
    if (marcado) s.add(id); else s.delete(id);
    onSeleccion(s);
  }

  return (
    <div className={styles.selector}>
      <p className={styles.ayuda}>
        {ayuda}
        <label className={styles.checkTodos}>
          <input type="checkbox" checked={todos} onChange={(e) => setTodos(e.target.checked)} /> Mostrar todos los usuarios
        </label>
      </p>
      <div className={styles.listaUsuarios}>
        {candidatos.length === 0 && <span className={styles.vacio}>No hay usuarios con ese permiso.</span>}
        {candidatos.map((u) => {
          const extra = detalle?.(u);
          return (
            <label key={u.id} className={styles.opcionUsuario}>
              <input type="checkbox" checked={seleccion.has(u.id)} onChange={(e) => alternar(u.id, e.target.checked)} />
              <span>{u.full_name}</span>
              <em>
                @{u.username}{u.rol_personalizado ? ` · ${u.rol_personalizado.nombre}` : ""}
                {extra && ` · ${extra}`}
              </em>
            </label>
          );
        })}
      </div>
      <div className={styles.filaBotones}>
        <button type="button" className={styles.btnPrimario} onClick={onGuardar} disabled={guardando}>
          Guardar asignación
        </button>
      </div>
    </div>
  );
}
