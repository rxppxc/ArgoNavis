from typing import Literal
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Configuracion(BaseSettings):
    # extra="ignore": los .env existentes pueden traer variables ya retiradas
    # (p. ej. TRANSFER_EXPIRY_DAYS o LIMPIEZA_* del storage original) y no
    # deben impedir el arranque.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "ARGO NAVIS - SNM"
    APP_ENV:  str = "development"

    # Logs de la aplicación. Además de la consola, en LOG_CARPETA queda un archivo
    # por día (argonavis-AAAA-MM-DD.log) que se borra a los LOG_DIAS días. Vacío =
    # solo la consola: en Docker alcanza, porque Docker guarda y rota esa salida.
    LOG_CARPETA: str = ""
    LOG_DIAS:    int = 30
    LOG_NIVEL:   Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    SECRET_KEY:                   str
    # Solo HMAC con SECRET_KEY. PyJWT también conoce "none" (tokens sin firma):
    # con ese valor, cualquiera se haría pasar por cualquiera.
    ALGORITHM:                    Literal["HS256", "HS384", "HS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:  int = 480
    # Duración máxima de una sesión aunque se renueve el token (/auth/refresh):
    # pasado este tiempo desde el login hay que volver a entrar.
    SESION_MAXIMA_HORAS:          int = 12

    DATABASE_URL: str
    # Cuenta dueña de las tablas, solo para las migraciones (alembic/env.py) y para
    # crear la de la aplicación (infrastructure/permisos_bd.py). Vacía = las migraciones
    # usan DATABASE_URL. En Docker, el entrypoint la borra antes de levantar uvicorn.
    MIGRACIONES_DATABASE_URL: str = ""
    # Conexiones con la base de datos, POR PROCESO: con N workers el máximo es
    # N × (BD_POOL + BD_POOL_EXTRA), y tiene que quedar por debajo de max_connections
    # de PostgreSQL (100 por defecto). Con los 4 de start-backend-prod.bat: 4 × 15 = 60.
    # Antes eran 10 + 20 fijos: con 4 workers podían pedirse 120 y PostgreSQL rechazaba.
    BD_POOL:       int = 5
    BD_POOL_EXTRA: int = 10
    # Segundos que una petición espera una conexión libre antes de responder 503.
    BD_POOL_ESPERA: int = 10
    # Topes en segundos (0 = sin tope): una consulta y una transacción abierta sin
    # actividad. Así una consulta descontrolada o una petición colgada no retienen
    # la conexión ni los bloqueos de fila (las transiciones usan FOR UPDATE).
    BD_TIEMPO_MAXIMO_CONSULTA: int = 60
    BD_TIEMPO_MAXIMO_INACTIVA: int = 300

    LDAP_HOST:          str
    LDAP_PORT:          int = 389
    LDAP_BASE_DN:       str
    LDAP_BIND_USER:     str
    LDAP_BIND_PASSWORD: str
    LDAP_TIMEOUT:       int = 10
    LDAP_ALLOWED_OU:    str = ""   # ej: "OU=DTI,DC=migracion,DC=gob,DC=pa"
    # TLS con el AD (sin TLS, la contraseña de cada login viaja en claro hasta
    # el controlador de dominio). LDAPS: LDAP_USAR_SSL=true y LDAP_PORT=636.
    # StartTLS: LDAP_STARTTLS=true sobre el 389. El certificado del AD se valida
    # contra LDAP_CA_CERT (PEM de la CA interna) o, vacío, contra las CA del
    # sistema; LDAP_HOST debe ser el nombre que trae el certificado, no la IP.
    LDAP_USAR_SSL:      bool = False
    LDAP_STARTTLS:      bool = False
    LDAP_CA_CERT:       str  = ""

    # Raíz de los documentos de los expedientes (una carpeta por solicitud).
    # Documentos de los expedientes, una carpeta por solicitud. La BD guarda las
    # rutas relativas a esta carpeta: se puede mover cambiando solo esta variable.
    STORAGE_PATH:     str = "./storage/documentos"

    FRONTEND_URL: str = "http://localhost:5173"
    # URL pública de la app (usada en enlaces de correo). Defínela con la IP/dominio real.
    APP_URL: str = ""

    MAIL_HOST:      str = ""
    MAIL_PORT:      int = 25
    MAIL_USERNAME:  str = ""
    MAIL_PASSWORD:  str = ""
    MAIL_FROM:      str = ""
    MAIL_FROM_NAME: str = "ARGO NAVIS - SNM"
    # TLS con el servidor de correo (sin TLS, el usuario y la contraseña del SMTP
    # y los avisos viajan en claro). SMTPS: MAIL_USAR_SSL=true y MAIL_PORT=465.
    # STARTTLS: MAIL_STARTTLS=true (587 o 25). El certificado se valida contra
    # MAIL_CA_CERT (PEM de la CA interna) o, vacío, contra las CA del sistema;
    # MAIL_HOST debe ser el nombre que trae el certificado, no la IP.
    MAIL_USAR_SSL:  bool = False
    MAIL_STARTTLS:  bool = False
    MAIL_CA_CERT:   str  = ""
    # Segundos de espera por el servidor de correo en cada envío (antes, los 60 de
    # aiosmtplib): mientras espera, el envío retiene una conexión de la BD.
    MAIL_TIEMPO_ESPERA: int = 20

    # ── Autorizaciones Marítimas ──
    # Buzón de la sección de autorizaciones (UCVMM): recibe el aviso de cada
    # solicitud nueva o corregida. Vacío = no se avisa por correo.
    CORREO_UCVMM: str = ""
    # Días que tiene la naviera para subsanar una solicitud devuelta a corrección,
    # desde la devolución: 3 = 72 h (2026-11-06; antes 2, 48 h).
    PLAZO_CORRECCION_DIAS: int = 3
    # Días tras la fecha de la operación para que el puesto de control finalice
    # una autorización aprobada antes de que expire (vence a las 23:59 del último):
    # 2 = 72 h desde que empieza el día de la operación (2026-11-06; antes 1, 48 h).
    DIAS_GRACIA_FINALIZACION: int = 2
    # Con cuánta anticipación máxima se puede pedir una autorización (fecha de la operación).
    DIAS_MAXIMOS_ANTICIPACION: int = 365
    # Cada cuántos minutos se revisan plazos vencidos (corrección / finalización).
    VENCIMIENTOS_INTERVALO_MINUTOS: int = 15

    # Rate limit de los endpoints públicos (verificación del QR), por IP y por minuto. 0 = desactivado.
    # (Antes RATE_LIMIT_DOWNLOADS_PER_MINUTE, de las descargas del storage: se sigue leyendo.)
    LIMITE_VERIFICACIONES_POR_MINUTO: int = Field(
        30, validation_alias=AliasChoices("LIMITE_VERIFICACIONES_POR_MINUTO", "RATE_LIMIT_DOWNLOADS_PER_MINUTE"),
    )
    # Envíos (crear o corregir una solicitud, que suben archivos) por usuario y
    # por hora: frena que una cuenta (p. ej. de una agencia comprometida) llene
    # el disco o sature la validación de archivos. 0 = sin límite.
    LIMITE_ENVIOS_POR_HORA: int = 30

    # Cuentas locales (sin AD): las de usuarios externos, como las agencias
    # navieras. Interruptor independiente de APP_ENV. Con False solo entran
    # las cuentas del Active Directory.
    PERMITIR_LOGIN_LOCAL: bool = False
    # Bloqueo temporal de una cuenta local tras varios intentos fallidos seguidos.
    LOGIN_MAX_INTENTOS:    int = 5
    LOGIN_MINUTOS_BLOQUEO: int = 15
    # Freno del login de las cuentas del AD (en la BD: vale para todos los
    # workers). Tras LOGIN_AD_MAX_FALLOS fallos seguidos, ARGO NAVIS deja de
    # consultar al AD por esa cuenta durante LOGIN_AD_MINUTOS_ESPERA. Así nadie
    # (p. ej. desde la VPN de las agencias) le bloquea a propósito la cuenta del
    # dominio a un funcionario. Ajústalo a la política de bloqueo del AD (TI):
    #   - LOGIN_AD_MAX_FALLOS por debajo del umbral de bloqueo, con margen para
    #     los errores del propio usuario en su PC;
    #   - LOGIN_AD_MINUTOS_ESPERA mayor o igual que "Restablecer el contador de
    #     bloqueos de cuenta después de".
    LOGIN_AD_MAX_FALLOS:     int = 3
    LOGIN_AD_MINUTOS_ESPERA: int = 30

    @property
    def app_base_url(self) -> str:
        return self.APP_URL or self.FRONTEND_URL

    @property
    def es_produccion(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @model_validator(mode="after")
    def _clave_fuerte_en_produccion(self) -> "Configuracion":
        """En producción no arranca con una SECRET_KEY corta o de ejemplo: con
        ella se firman los tokens (quien la adivine se hace pasar por cualquiera)."""
        if self.es_produccion and (len(self.SECRET_KEY) < 32 or "REEMPLAZAR" in self.SECRET_KEY.upper()):
            raise ValueError(
                "SECRET_KEY débil o de ejemplo: en producción usa al menos 32 caracteres aleatorios "
                "(python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
            )
        return self

    @model_validator(mode="after")
    def _un_solo_tls_para_el_correo(self) -> "Configuracion":
        """SMTPS y STARTTLS se excluyen: con los dos, ningún aviso saldría."""
        if self.MAIL_USAR_SSL and self.MAIL_STARTTLS:
            raise ValueError("MAIL_USAR_SSL y MAIL_STARTTLS se excluyen: usa uno (465 o 587).")
        return self

@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()