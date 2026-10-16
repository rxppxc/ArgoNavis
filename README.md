# ARGO NAVIS · Sistema Interno Marítimo (SNM)

**ARGO NAVIS** es el Sistema Interno Marítimo del **Servicio Nacional de Migración (SNM) de Panamá**; el nombre viene de la constelación *Argo Navis*, «la nave Argo». Hoy cubre las **Autorizaciones Marítimas** de la UCVMM: las agencias navieras envían solicitudes con el expediente de los tripulantes, UCVMM las revisa y aprueba (o devuelve o deniega), y el puesto de control migratorio registra la operación y la finaliza. La autorización aprobada se descarga en PDF con un código QR verificable.

Nació como una herramienta de *storage* (transferencias de archivos con enlace público) y se adaptó: el almacenamiento pasó a ser la capa documental del expediente de cada solicitud. Ya no hay enlaces públicos de descarga. Antes se llamaba "FileDrop - SNM" y el repositorio, FileTransfer.

---

## Tecnologías

| Capa | Stack |
|---|---|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 async · PostgreSQL · Alembic · LDAP (Active Directory) · JWT · reportlab (PDF + QR) |
| **Frontend** | React 19 · TypeScript estricto · Vite · CSS Modules · React Router v7 |
| **Infraestructura** | Docker Compose (nginx + backend + PostgreSQL) o Windows (uvicorn + proxy) · slowapi (rate limit) |

---

## Arranque rápido

### Requisitos
- Python 3.12+ y Node.js 22+
- PostgreSQL (la base de `DATABASE_URL` creada)
- Acceso a un servidor LDAP / Active Directory (las cuentas locales no lo necesitan)

### Primera vez
```bat
:: Copiar plantilla de entorno y completarla (SECRET_KEY, DATABASE_URL, LDAP_*, MAIL_*...)
copy backend\.env.example backend\.env

:: Backend
cd backend
python -m venv venv
:: Siempre "venv\Scripts\python -m ...": los .exe del venv (pip, uvicorn...) guardan la ruta de la carpeta y fallan si se mueve.
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -I -m alembic upgrade head

:: Frontend
cd ..\frontend
npm install
```

### Desarrollo (dos terminales)
```bat
start-backend.bat
start-frontend.bat
```
Frontend en `http://localhost:5173` (el proxy de Vite manda `/api` al backend en `:8000`). Documentación de la API en `http://localhost:8000/api/docs` (solo con `APP_ENV=development`).

Los dos escuchan solo en este equipo. Para probar desde otro (p. ej. el celular): `set VITE_HOST=0.0.0.0` antes de `start-frontend.bat`.

### Pruebas
```bat
cd backend
venv\Scripts\python -m pytest
```
Crean una base de datos temporal en el servidor de `DATABASE_URL` (o `TEST_DATABASE_URL`), le aplican las migraciones, recorren el flujo completo por la API y la borran al terminar. No envían correos ni tocan la base de desarrollo.

```bat
cd frontend
node node_modules/typescript/bin/tsc -b --noEmit
npm run lint
npm run build
```

### Producción
**Docker** (`docker-compose-prod.yml`): copiar `.env.example` como `.env` en la raíz y completar. El backend aplica las migraciones al arrancar (`docker-entrypoint.sh`) y solo es accesible a través de nginx (`/api/`); su puerto no se publica.
```bash
docker compose -f docker-compose-prod.yml up -d --build
```

**Windows**: `APP_ENV=production` en `backend\.env`, `migrate.bat`, compilar el frontend (`npm run build`) y `start-backend-prod.bat` (sirve también `frontend/dist`).

> **Servidores instalados antes de ARGO NAVIS** (una sola vez). Antes la base se llamaba `filetransfer` y los documentos vivían en `storage/transfers`. La revisión `b5c2e8f4a713` deja las rutas de los documentos relativas, así que solo cambian los nombres:
> - **Docker:** el proyecto ahora se llama `argonavis` (`name:` en `docker-compose-prod.yml`) y sus volúmenes son nuevos. Con todo detenido (`docker compose -f docker-compose-prod.yml down` desde la carpeta vieja), copia los datos; `docker volume ls` muestra el prefijo viejo:
>   ```bash
>   docker volume create argonavis_postgres_data && docker volume create argonavis_documentos
>   docker run --rm -v <viejo>_postgres_data:/de -v argonavis_postgres_data:/a alpine cp -a /de/. /a/
>   docker run --rm -v <viejo>_filetransfer_storage:/de -v argonavis_documentos:/a alpine cp -a /de/. /a/
>   ```
>   Pon `POSTGRES_DB=argonavis` en el `.env`, renombra la base y levanta todo (al arrancar, el backend aplica la migración de las rutas):
>   ```bash
>   docker compose -f docker-compose-prod.yml up -d postgres_db
>   docker exec snm_postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "ALTER DATABASE filetransfer RENAME TO argonavis"'
>   docker compose -f docker-compose-prod.yml up -d --build
>   ```
>   Actualiza la ruta de `backup.sh` en el cron. Cuando todo funcione, borra los volúmenes viejos y los respaldos `filetransfer_*.gz` (la retención ya solo limpia los `argonavis_*`).
> - **Windows:** detén el backend y corre `migrate.bat` (pasa las rutas a relativas). Después renombra la base (`ALTER DATABASE filetransfer RENAME TO argonavis` desde `psql`, conectado a `postgres`), mueve `backend\storage\transfers` a `backend\storage\documentos` y cambia `DATABASE_URL` y `STORAGE_PATH` en `backend\.env`.

> **HTTPS y TLS con el AD** (pendiente de infraestructura). Sin esto, la contraseña de cada login viaja en claro: del navegador al servidor (HTTP, puerto 80) y del backend al controlador de dominio (LDAP 389).
> - **Active Directory:** con el certificado del controlador de dominio, `LDAP_USAR_SSL=true` y `LDAP_PORT=636` (o `LDAP_STARTTLS=true` sobre el 389). `LDAP_HOST` debe ser el nombre que trae el certificado (no la IP) y `LDAP_CA_CERT`, la ruta al PEM de la CA interna (en Docker, montarlo con un volumen). Probarlo primero en desarrollo.
> - **Navegador:** un certificado para el servidor; en nginx, un `server` en el 443 (`ssl_certificate` / `ssl_certificate_key`) y el 80 redirigiendo al 443. Ya con HTTPS, agregar `Strict-Transport-Security`. En Windows, lo mismo en el proxy que esté delante de uvicorn.

> **Al migrar un servidor que venía del storage** (revisión `d4f1a8c27e90`): las transferencias sueltas que existan se **eliminan**, en la base y en disco. Si alguna hace falta, descárgala antes de actualizar.

> **Primer SysAdmin** (desde la revisión `c7a2e94b1f30`): usuarios, roles y permisos solo los gestiona el rol SysAdmin, y la migración no se lo asigna a nadie. Después de migrar, nómbralo desde la consola del servidor (el usuario ya tiene que existir; queda en la bitácora):
> ```bat
> cd backend
> venv\Scripts\python -m app.infrastructure.asignar_rol <usuario> SysAdmin
> ```
> Con Docker: `docker compose -f docker-compose-prod.yml exec backend python -m app.infrastructure.asignar_rol <usuario> SysAdmin`. El mismo comando sirve para recuperar el acceso si se pierde.

---

## Estructura

```
ArgoNavis/
├─ backend/
│  ├─ app/
│  │  ├─ main.py               # FastAPI, CORS, rutas, tarea de vencimientos
│  │  ├─ api/v1/               # endpoints: solo orquestan (auth, solicitudes, catálogos, admin, bitácora...)
│  │  ├─ core/                 # config, JWT, LDAP, permisos, correos, PDF, rate limit
│  │  ├─ domain/
│  │  │  ├─ models/            # ORM: solicitud, tramite, catalogo, user, rol, audit_log
│  │  │  ├─ schemas/           # contratos Pydantic de la API
│  │  │  ├─ repositories/      # acceso a BD, uno por agregado
│  │  │  └─ services/          # reglas: solicitud, tramite (checklist), notificacion, auth
│  │  └─ infrastructure/
│  │     ├─ database.py        # motor async y sesión por request
│  │     ├─ almacenamiento.py  # validación y guardado de documentos (carpeta por solicitud)
│  │     ├─ tareas.py          # vencimientos, con un solo ejecutor entre workers
│  │     └─ asignar_rol.py     # nombra el primer SysAdmin desde la consola
│  ├─ alembic/versions/        # el esquema completo vive aquí
│  ├─ tests/                   # pytest sobre BD temporal
│  └─ storage/documentos/      # documentos de los expedientes (NO versionar)
│
└─ frontend/src/
   ├─ App.tsx                  # rutas y proveedores (tema, sesión, permisos, avisos)
   ├─ api/                     # cliente axios + un módulo por dominio
   ├─ components/              # UI reutilizable (MarcoPagina, ModalPreview, Iconos...)
   ├─ context/                 # proveedores: tema, autenticación, permisos
   ├─ hooks/                   # useAutenticacion, usePermisos
   └─ modulos/
      ├─ autenticacion/        # login y cambio de contraseña
      ├─ solicitudes/          # bandejas, formulario, expediente, verificación del QR
      └─ administracion/       # usuarios, roles, catálogos, trámites, estadísticas, bitácora
```

---

## El flujo

| Rol | Permiso | Qué hace |
|---|---|---|
| **Naviera** (usuario de una agencia) | `T-CREAR-BASICA` | Envía solicitudes de su agencia y las corrige cuando UCVMM las devuelve. Todos los usuarios de la agencia comparten sus solicitudes. |
| **Sector Pacífico** (UCVMM) | `T-PROCESAR-PACIFICO` | Verifica impedimentos tripulante por tripulante (obligatorio para aprobar), aprueba, devuelve a corrección o deniega. |
| **Puesto de Control** | `T-FINALIZAR-PUERTO` + puestos asignados | Ve las aprobadas de sus puestos y las finaliza con un comentario, indicando en qué puesto terminó la operación. |
| **Administrador** | todos los `T-*` | Bandejas y expedientes, catálogo de trámites, agencias, puestos, nacionalidades restringidas, estadísticas y bitácora. Ve la lista de usuarios para asignarlos a agencias y puestos, pero no los crea ni les cambia el rol. |
| **SysAdmin** | ninguno | Rol técnico: usuarios, roles (con los permisos fijos del sistema) y bitácora. No ve solicitudes ni expedientes. |

Administrador y SysAdmin se reconocen por el nombre del rol (`rol_personalizado.nombre`) y no se pueden renombrar. El último SysAdmin activo no se puede desactivar, borrar ni cambiar de rol.

**Estados:** `review` → `approved` → `finalized`; `review` → `returned` → (corrige) `review`; `review` → `denied`. Una aprobada sin finalizar a tiempo, o una devuelta sin corregir en el plazo (`PLAZO_CORRECCION_DIAS`), pasa a `expired`.

**Reglas que conviene conocer:**
- El checklist de documentos de cada trámite vive en BD (`tipos_tramite`, `documentos_requeridos`, `tramite_documentos`). Las condiciones se resuelven en `ServicioTramite.construir_casillas`, espejado en `frontend/src/modulos/solicitudes/checklist.ts`.
- Fechas del formulario:
  - La operación va de hoy hasta `DIAS_MAXIMOS_ANTICIPACION` (365) días.
  - Cada tripulante debe tener 18 años cumplidos y haber nacido desde 1900.
  - El pasaporte y el seamanbook tienen que vencer después del nacimiento.
- En ningún trámite se puede enviar la solicitud si el pasaporte o el seamanbook vence antes del día de la operación. Solo el rango Marino porta seamanbook; en Embarque se le pide la libreta sin importar la nacionalidad.
- El catálogo sigue tal cual los documentos:
  - Los documentos de cada trámite son los del Formulario No. 3 oficial.
  - Todos se suben por tripulante, salvo la Lista de Tripulantes, que va a la solicitud.
- Nacionalidad restringida:
  - En Desembarque se exige el Formulario No. 6 de custodia por tripulante.
  - En Desembarque, Urgencias, Renovación y Shore Pass, al aprobar se avisa a la agencia que debe realizar el trámite de solicitud de custodia (`tipos_tramite.aviso_custodia`).
  - La lista de nacionalidades restringidas la marca el admin; no viene ninguna sembrada.
- El trámite de Técnico, Superintendente o Supernumerario solo admite tripulantes con esos rangos (`tipos_tramite.rangos_permitidos`).
- `backend/tests/test_documento_ucvmm.py` tiene la lectura del Formulario No. 3 y del documento de UCVMM trámite por trámite (campos, documentos, vigencias, custodia): si el catálogo se aparta de él, la prueba falla.
- Además del checklist, se pueden adjuntar hasta 20 documentos adicionales por solicitud.
- Lo interno no le llega a la agencia, porque el backend lo filtra, no solo la vista:
  - La verificación de impedimentos (por tripulante).
  - La observación de aprobación.
  - El comentario del puesto de control.
  - Los nombres de los funcionarios: en su historial ve "UCVMM" o "Puesto de control".
  - Sí ve los motivos de devolución y de negación.
- El PDF de la autorización no lleva observaciones. Una vez finalizada, dice en qué puesto terminó la operación, que puede ser distinto del autorizado.
- **Separación de funciones:** nadie revisa una solicitud que creó o que es de su propia agencia.
- Cada transición bloquea la fila de la solicitud: dos revisores no pueden aprobar y negar la misma a la vez.
- Las solicitudes no se borran. Un usuario, agencia o puesto con solicitudes se desactiva en lugar de eliminarse.
- El QR del PDF lleva a `/verificar/{codigo}`, una página pública que solo muestra lo necesario para verificar la autorización (pasaportes enmascarados).

**Avisos por correo** (en segundo plano, después de guardar): a UCVMM (`CORREO_UCVMM`) cuando llega o se corrige una solicitud; a la agencia (su buzón y sus usuarios) cuando se aprueba, devuelve, deniega o expira; al puesto de control (su buzón y sus funcionarios) cuando se aprueba. El asunto es `Autorizaciones Marítimas · AM-2026-000011 · Aprobada`; el cuerpo es un "pase marítimo" con el logo de ARGO NAVIS incrustado (se ve aunque el cliente bloquee las imágenes externas), y el correo lleva versión en texto plano. El remitente sale de `MAIL_FROM_NAME`.

**Documentos del expediente:** se ven y descargan solo con sesión y acceso a la solicitud (`GET /api/v1/solicitudes/{id}/documentos/{doc}`). Cada vista y cada descarga queda en la bitácora con el usuario. **Se aceptan PDF, Word y Excel** (.pdf, .doc, .docx, .xls y .xlsx). Al subirse se validan:
- la extensión y el tamaño;
- que el contenido sea de verdad de ese formato (un archivo renombrado no pasa);
- que los de Word y Excel no traigan macros;
- el tipo real del contenido.

La vista previa muestra PDF, .docx y .xlsx; los .doc y .xls del formato viejo se descargan.

### Puesta en marcha
1. **Usuarios** (SysAdmin, en `/admin`): agrega los del Active Directory o crea cuentas locales para los usuarios externos, y asigna su rol (Naviera, Sector Pacífico, Puesto de Control, Administrador o SysAdmin). El primer SysAdmin se nombra desde la consola (ver *Producción*).
2. **Agencias navieras** (Administrador, en `/admin/catalogos`): crea cada agencia y asígnale sus usuarios. Un usuario sin agencia no puede enviar solicitudes.
3. **Puestos de control** (misma página): crea los puestos y asígnales sus funcionarios.
4. **Nacionalidades restringidas** (misma página): marca las de la lista oficial.

### Acceso
- **Active Directory:** la contraseña y su política viven en el AD. ARGO NAVIS solo le consulta por cuentas registradas y activas en ARGO NAVIS, y tras `LOGIN_AD_MAX_FALLOS` (3) fallos seguidos deja de hacerlo por `LOGIN_AD_MINUTOS_ESPERA` (30) minutos. Así, desde la VPN de las agencias no se pueden probar contraseñas del dominio ni bloquearle la cuenta a un funcionario. Ajusta esos dos valores a la política de bloqueo del dominio (ver `backend/.env.example`).
- **Cuentas locales** (`PERMITIR_LOGIN_LOCAL=true`): para usuarios sin cuenta en el dominio, como los de las agencias. Contraseña de 12 a 64 caracteres con mayúscula, minúscula, número y carácter especial, sin el nombre de usuario ni palabras obvias (password, navis, 123456…); quien entra con una que ya no cumple debe cambiarla. Bloqueo de 15 minutos tras 5 intentos fallidos; el admin puede restablecerla (genera una temporal) y el usuario debe cambiarla al entrar.
- Si el Administrador desactiva una agencia, sus usuarios no pueden entrar y su sesión abierta se cierra.
- El login responde lo mismo si el usuario no existe y si la contraseña está mal (no revela qué cuentas hay en el AD); el motivo real queda en la bitácora.
- El JWT se verifica contra la BD en cada request: desactivar una cuenta la saca de inmediato.
- Mientras el usuario trabaja, el token se renueva solo; tras 15 minutos sin actividad se cierra la sesión (con aviso). Ninguna sesión dura más de `SESION_MAXIMA_HORAS` (12) desde el login.
- Cerrar sesión, cambiar la contraseña o que el SysAdmin la restablezca invalida los tokens ya emitidos de esa cuenta (en cualquier navegador).
- Si se pide una página sin sesión (p. ej. el enlace de un correo), tras el login se vuelve a ella.

### Seguridad
Las agencias entran por la VPN, pero no son del SNM: ARGO NAVIS las trata como usuarios no confiables.
- **Archivos:** PDF, Word y Excel de hasta 2 MB cada uno, comprobados por su contenido; los de Office con macros se rechazan. La vista previa del Word va en un marco aislado (sin scripts, sin enlaces, sin acceso a la sesión).
- **Navegador:** Content-Security-Policy (solo código propio de ARGO NAVIS), `X-Frame-Options: DENY` y `nosniff`, en nginx y en el backend cuando sirve el frontend.
- **Topes:** login por IP (10 por minuto), envíos por cuenta (`LIMITE_ENVIOS_POR_HORA`, 30) y 2 MB por archivo, en cualquier formato. Se cuentan en memoria, por proceso: con varios workers, cada uno lleva su cuenta.
- **Rutas sin sesión:** solo el login, la verificación del QR y el health check; una prueba falla si aparece otra.
- **Producción:** no arranca con una `SECRET_KEY` corta o de ejemplo.

### Tareas de fondo
Cada `VENCIMIENTOS_INTERVALO_MINUTOS` se expiran las solicitudes con plazos vencidos y se avisa a la agencia. Con varios workers, un *advisory lock* de PostgreSQL deja que una sola vuelta haga el trabajo.

---

## Convenciones

El detalle (idioma, naming, capas, seguridad, errores) está en [CLAUDE.md](CLAUDE.md). En resumen:
- Código nuevo en español. Se conservan en inglés las APIs de librerías y las columnas y claves heredadas que ya están en uso (`users.username`, `access_token`, etc.).
- Backend en capas: los endpoints solo orquestan, las reglas viven en `domain/services/` y el acceso a BD en `domain/repositories/`.
- La sesión de BD se pide siempre como `Depends(obtener_sesion_bd, scope="function")`: así el commit ocurre antes de responder y los correos salen después.
- Frontend: errores con `useNotificacion()`, acciones destructivas con `useConfirmar()`. Nunca `alert()` ni `confirm()`.

---

## Decisiones documentadas

### Por qué la tabla `users` conserva nombres en inglés
`username`, `name`, `status`, etc. son columnas con datos en producción y claves del contrato de la API (`SalidaUsuario`). Las tablas del flujo (`solicitudes`, `solicitud_*`, catálogos) ya nacieron en español.

### Por qué el JWT vive en `localStorage`
Decisión heredada. Pasarlo a una cookie `httpOnly` requiere `Set-Cookie` en el backend, un token CSRF, `withCredentials` en axios y un despliegue coordinado. Mitigación actual: Content-Security-Policy (solo scripts propios, sin `eval` ni conexiones a otros sitios), vista previa del Word aislada, revocación inmediata por la verificación en BD (incluido el cierre de sesión), ningún log de tokens, rate limit del login, cabeceras de seguridad y documentos que exigen la cabecera `Authorization` (no se abren con un enlace).

---

## Variables de entorno

Ver [backend/.env.example](backend/.env.example) (desarrollo / Windows) y [.env.example](.env.example) (Docker Compose). Ambos traen cada variable documentada.

Frontend (opcionales):
- `VITE_API_URL`: base de la API. Por defecto `/api/v1` (mismo origen: proxy de Vite en dev, nginx en producción).
- `VITE_PROXY_TARGET`: destino del proxy de Vite en dev. Por defecto `http://localhost:8000`.
- `VITE_HOST`: dónde escucha el servidor de desarrollo. Por defecto `localhost` (solo este equipo); `0.0.0.0` para probar desde otro.

---

## Pendiente (decisiones del equipo)
- HTTPS en el servidor y TLS con el Active Directory (la configuración ya está; ver *Producción*).
- Edición del catálogo de trámites desde la interfaz.
- Envío por partes para tripulaciones muy grandes (nginx corta en 200 MB por envío).
- Política de retención de datos personales (Ley 81 de 2019) y copia de los respaldos fuera del servidor.
- Solicitud de Custodia y Solicitud de Transbordos (el documento de UCVMM dice que faltan por levantar).
- Segundo factor (código TOTP) para las cuentas de las agencias: decidido para más adelante.
- Antivirus (ClamAV) para los archivos que suben las agencias: por ahora no; necesita el servicio en el servidor.
- Cambio de puerto de una autorización ya aprobada: en consulta con UCVMM (el trámite «Cambio de Puerto» del Form. 3 o una reasignación del puesto). Mientras tanto, la agencia presenta el «Cambio de Puerto» citando el número de la autorización original en las observaciones, o el puesto autorizado la finaliza indicando dónde terminó.
