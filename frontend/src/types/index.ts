export type EstadoUsuario = "active" | "inactive";
export type TipoUsuario   = "ad" | "local";

export interface RolPersonalizadoMini {
  id:         number;
  nombre:     string;
  es_sistema: boolean;
}

export interface CatalogoMini {
  id:     number;
  nombre: string;
}

export interface Usuario {
  id:        number;
  username:  string;
  name:      string | null;
  last_name: string | null;
  email:     string | null;
  user_type: TipoUsuario;
  status:    EstadoUsuario;
  rol_id:    number | null;
  rol_personalizado: RolPersonalizadoMini | null;
  /** Agencia naviera del usuario: comparte con ella sus solicitudes. */
  agencia_id: number | null;
  agencia:    CatalogoMini | null;
  /** Cuenta local recién creada o restablecida: debe cambiar la contraseña. */
  debe_cambiar_password: boolean;
  full_name: string;
}

export interface RespuestaToken {
  access_token: string;
  token_type:   string;
  user:         Usuario;
}

export interface ErrorApi {
  detail: string;
}
