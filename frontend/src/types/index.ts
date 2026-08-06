export type EstadoTransferencia =
  | "active"     // disponible de inmediato, con enlace de descarga
  | "expired"    // venció por fecha o descargas
  | "deleted";   // borrada
export type EstadoUsuario       = "active" | "inactive";
export type TipoUsuario         = "ad" | "local";

export interface RolPersonalizadoMini {
  id:         number;
  nombre:     string;
  es_sistema: boolean;
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
  full_name: string;
}

export interface ArchivoTransferencia {
  id:            number;
  original_name: string;
  mime_type:     string | null;
  size:          number;
  es_original?:  boolean;
  subido_por_id?: number | null;
}

export interface Transferencia {
  id:            number;
  token:         string;
  title:         string | null;
  message:       string | null;
  recipient:     string | null;
  expires_at:    string | null;
  downloads:     number;
  max_downloads: number | null;
  status:        EstadoTransferencia;
  created_at:    string;
  files:         ArchivoTransferencia[];
  total_size:    number;
  is_expired:    boolean;
  user_id?:      number;
  sender?:       string | null;
}

export interface TransferenciaPublica {
  id:            number;
  token:         string;
  title:         string | null;
  message:       string | null;
  expires_at:    string | null;
  downloads:     number;
  max_downloads: number | null;
  is_expired:    boolean;
  files:         ArchivoTransferencia[];
  total_size:    number;
  sender:        string;
}

export interface RespuestaToken {
  access_token: string;
  token_type:   string;
  user:         Usuario;
}

export interface ErrorApi {
  detail: string;
}

