"""Active Directory: búsqueda de usuarios (cuenta de servicio) y verificación
de contraseñas (bind con la cuenta del usuario).

  - TLS opcional por configuración: LDAPS (LDAP_USAR_SSL, puerto 636) o
    StartTLS (LDAP_STARTTLS). Sin TLS, la contraseña de cada login viaja en
    claro hasta el controlador de dominio.
  - Cada conexión se cierra al terminar (también si falla).
  - El esquema del AD se lee en el primer bind del proceso y se reutiliza:
    ldap3 lo descargaba completo en cada bind (y cada login hace dos).
"""
import logging
import ssl

from ldap3 import ALL, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError, LDAPException, LDAPStartTLSError
from ldap3.utils.conv import escape_filter_chars

from app.core.config import obtener_configuracion

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_ATRIBUTOS = ["cn", "givenName", "sn", "mail", "sAMAccountName", "distinguishedName", "objectGUID", "department"]


def _datos_usuario(entrada) -> dict:
    return {
        "username":   str(entrada.sAMAccountName) if entrada.sAMAccountName else "",
        "name":       str(entrada.givenName)      if entrada.givenName      else "",
        "last_name":  str(entrada.sn)             if entrada.sn             else "",
        "email":      str(entrada.mail)           if entrada.mail           else "",
        "guid":       str(entrada.objectGUID)     if entrada.objectGUID     else "",
        "department": str(entrada.department)     if entrada.department     else "",
    }


class ServicioLDAP:
    def __init__(self):
        tls = None
        if configuracion.LDAP_USAR_SSL or configuracion.LDAP_STARTTLS:
            # El certificado del AD se valida (CA interna en LDAP_CA_CERT, o las
            # del sistema) y debe corresponder a LDAP_HOST.
            tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=configuracion.LDAP_CA_CERT or None)
        self.servidor = Server(
            configuracion.LDAP_HOST,
            port=configuracion.LDAP_PORT,
            use_ssl=configuracion.LDAP_USAR_SSL,
            tls=tls,
            get_info=ALL,
            connect_timeout=configuracion.LDAP_TIMEOUT,
        )

    def _abrir(self, usuario: str, contrasena: str) -> Connection:
        """Conexión con el bind hecho (y StartTLS antes, si está configurado).
        Si el bind se rechaza, la cierra y lanza LDAPBindError con el mensaje
        del servidor (trae el código de AD: "data 52e", "data 775"...)."""
        conexion = Connection(
            self.servidor, user=usuario, password=contrasena,
            receive_timeout=configuracion.LDAP_TIMEOUT,
        )
        try:
            if configuracion.LDAP_STARTTLS:
                conexion.open(read_server_info=False)
                if not conexion.start_tls(read_server_info=False):
                    raise LDAPStartTLSError("No se pudo iniciar StartTLS con el Active Directory.")
            if not conexion.bind(read_server_info=self.servidor.schema is None):
                resultado = conexion.result or {}
                raise LDAPBindError(resultado.get("message") or resultado.get("description") or "bind rechazado")
        except Exception:
            self._cerrar(conexion)
            raise
        return conexion

    @staticmethod
    def _cerrar(conexion: Connection) -> None:
        try:
            conexion.unbind()
        except Exception as exc:   # el socket pudo quedar cerrado por el propio error
            logger.debug("[LDAP] No se pudo cerrar la conexión: %s", exc)

    def _conectar_cuenta_servicio(self) -> Connection:
        return self._abrir(configuracion.LDAP_BIND_USER, configuracion.LDAP_BIND_PASSWORD)

    def buscar_usuario(self, nombre_usuario: str) -> dict | None:
        base = configuracion.LDAP_ALLOWED_OU or configuracion.LDAP_BASE_DN
        try:
            conexion = self._conectar_cuenta_servicio()
        except LDAPException as e:
            logger.error(f"Error al conectar con la cuenta de servicio LDAP: {e}")
            raise
        try:
            # Escapa todos los caracteres reservados de filtros LDAP (RFC 4515)
            usuario_seguro = escape_filter_chars(nombre_usuario)
            conexion.search(
                search_base   = base,
                search_filter = f"(&(objectClass=user)(sAMAccountName={usuario_seguro}))",
                search_scope  = SUBTREE,
                attributes    = _ATRIBUTOS,
            )
            if not conexion.entries:
                return None
            entrada = conexion.entries[0]
            # El DN solo se usa para el bind del usuario: no se registra ni se envía al navegador.
            return {"dn": str(entrada.entry_dn), **_datos_usuario(entrada)}
        except LDAPException as e:
            logger.error(f"Error al buscar usuario en LDAP: {e}")
            raise
        finally:
            self._cerrar(conexion)

    def autenticar(self, dn: str, contrasena: str) -> bool:
        """True si el AD acepta la contraseña; False si la rechaza. Un error de
        conexión se relanza (el login responde 503, no "contraseña incorrecta")."""
        # Defensa explícita contra el "unauthenticated bind" de LDAP: un bind
        # con usuario y contraseña vacía puede resolverse como bind anónimo
        # exitoso en algunos servidores, lo que sería un bypass de login.
        # ldap3 ya lanza LDAPPasswordIsMandatoryError, pero no dependemos de eso.
        if not contrasena or not contrasena.strip():
            logger.warning("[LDAP] Intento de autenticación con contraseña vacía — rechazado.")
            return False
        try:
            conexion = self._abrir(dn, contrasena)
        except LDAPBindError as e:
            msg = str(e)
            # No incluir el DN en el log — revela la estructura del AD (regla #4).
            logger.warning("[LDAP] Autenticación fallida (bind rechazado).")
            if "data 773" in msg or "data 532" in msg:
                logger.warning("[LDAP] La cuenta requiere cambio de contraseña o está expirada.")
            elif "data 533" in msg:
                logger.warning("[LDAP] La cuenta está deshabilitada en Active Directory.")
            elif "data 775" in msg:
                logger.warning("[LDAP] La cuenta está bloqueada en Active Directory.")
            return False
        self._cerrar(conexion)
        logger.info("[LDAP] Autenticación exitosa")
        return True

    def buscar_usuarios_ad(self, termino: str) -> list[dict]:
        """Búsqueda parcial en AD por usuario, nombre o email (máx. 20 resultados)."""
        # Escape RFC 4515 para evitar LDAP injection (admin)(&(|...) etc.
        t = escape_filter_chars(termino)
        if not t:
            return []
        base = configuracion.LDAP_ALLOWED_OU or configuracion.LDAP_BASE_DN
        filtro = (
            f"(&(objectClass=user)(objectCategory=person)"
            f"(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
            f"(|(sAMAccountName=*{t}*)(cn=*{t}*)(mail=*{t}*)))"
        )
        try:
            conexion = self._conectar_cuenta_servicio()
        except LDAPException as e:
            logger.error(f"Error al conectar con la cuenta de servicio LDAP: {e}")
            raise
        try:
            conexion.search(
                search_base  = base,
                search_filter= filtro,
                search_scope = SUBTREE,
                attributes   = _ATRIBUTOS,
                size_limit   = 20,
            )
            return [datos for datos in (_datos_usuario(e) for e in conexion.entries) if datos["username"]]
        except LDAPException as e:
            logger.error(f"Error al buscar usuarios en AD: {e}")
            raise
        finally:
            self._cerrar(conexion)


servicio_ldap = ServicioLDAP()
