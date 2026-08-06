from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "FileDrop - SNM"
    APP_ENV:  str = "development"

    SECRET_KEY:                   str
    ALGORITHM:                    str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:  int = 480

    DATABASE_URL: str

    LDAP_HOST:          str
    LDAP_PORT:          int = 389
    LDAP_BASE_DN:       str
    LDAP_BIND_USER:     str
    LDAP_BIND_PASSWORD: str
    LDAP_TIMEOUT:       int = 10
    LDAP_ALLOWED_OU:    str = ""   # ej: "OU=DTI,DC=migracion,DC=gob,DC=pa"

    STORAGE_PATH:         str = "./storage/transfers"
    MAX_FILE_SIZE_MB:     int = 50
    TRANSFER_EXPIRY_DAYS: int = 7

    FRONTEND_URL: str = "http://localhost:5173"
    # URL pública de la app (usada en enlaces de correo). Defínela con la IP/dominio real.
    APP_URL: str = ""

    MAIL_HOST:      str = ""
    MAIL_PORT:      int = 25
    MAIL_USERNAME:  str = ""
    MAIL_PASSWORD:  str = ""
    MAIL_FROM:      str = ""
    MAIL_FROM_NAME: str = "FileDrop - SNM"

    # Limpieza automática de transferencias expiradas
    LIMPIEZA_INTERVALO_HORAS: int = 6   # cada cuántas horas corre el proceso
    LIMPIEZA_RETENER_DIAS:    int = 0   # días de gracia tras la expiración antes de borrar

    # Rate limit del endpoint público de descarga (peticiones por IP por minuto). 0 = desactivado.
    RATE_LIMIT_DOWNLOADS_PER_MINUTE: int = 30

    # Login local de prueba (sin AD) — interruptor independiente de APP_ENV,
    # porque docker-compose-prod.yml fija APP_ENV=production también en el
    # servidor de pruebas. Debe quedar en False (o sin definir) antes de que
    # el sistema pase a producción real.
    PERMITIR_LOGIN_LOCAL: bool = False

    @property
    def app_base_url(self) -> str:
        return self.APP_URL or self.FRONTEND_URL

    @property
    def es_produccion(self) -> bool:
        return self.APP_ENV.lower() == "production"

@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()