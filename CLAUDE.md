# Guía para asistentes IA — ARGO NAVIS (SNM)

Este archivo se carga automáticamente al iniciar un asistente Claude Code en este repositorio. Contiene contexto que NO está obvio leyendo el código.

## Resumen en una frase

**ARGO NAVIS** (antes "NAVIS" y, al principio, "FileDrop - SNM", con el repositorio FileTransfer, renombrado a ArgoNavis el 2026-10-16) es el Sistema Interno Marítimo del Servicio Nacional de Migración (Panamá). Hoy cubre las Autorizaciones Marítimas de UCVMM: las agencias navieras envían solicitudes con el expediente de los tripulantes, UCVMM las revisa y aprueba, y el puesto de control las finaliza. Nació como storage de archivos con enlace público; se adaptó y ese storage es ahora la capa documental del expediente (sin enlaces públicos).

El nombre del sistema es «ARGO NAVIS · Sistema Interno Marítimo» (logo, pestaña del navegador, README), pensando en módulos futuros (decisión del usuario del 2026-10-16). «Autorizaciones Marítimas» es el módulo de hoy: así se llaman el trámite, el asunto de los correos y el PDF.

## Stack
- Backend: FastAPI + SQLAlchemy 2 async + PostgreSQL + LDAP/AD + JWT (`python-jose`)
- Frontend: React 19 + TypeScript estricto + Vite + CSS Modules + React Router v7
- Rate limit: `slowapi` (almacenamiento en memoria — para multi-worker mover a Redis)
- MIME real: `python-magic` (binario `libmagic` en Windows via `python-magic-bin`)

## Convenciones críticas

### Idioma
Todo el código nuevo va en **español** (variables, funciones, clases, componentes, archivos, carpetas). Excepciones que se mantienen en inglés:

| Caso | Por qué |
|---|---|
| `useState`, `useEffect`, `useNavigate`, etc. | API de React/React Router |
| `title`, `message`, `recipient`, `status`, `expires_at`, etc. | Columnas SQL con datos en producción — renombrar requiere migración con downtime |
| `access_token`, `token_type`, claves JSON de la API | Contrato HTTP con el frontend; ver "Por qué no renombrar" en README |
| `username`, `password` en `SolicitudLogin` | Convención HTTP estándar |
| Prefijo `use*` de hooks | Convención React no negociable |
| `logger`, `Exception`, `dict`, etc. | Símbolos de la librería estándar Python |

Cuando agregues nombres nuevos, hazlo en español. Cuando toques nombres existentes, no los renombres "porque sí" — verifica primero si son de los inamovibles arriba.

### Naming
- Backend Python: `snake_case` funciones/variables, `PascalCase` clases, `UPPER_SNAKE` constantes.
- Frontend: `camelCase` variables/funciones, `PascalCase` componentes/tipos, `UPPER_SNAKE` constantes.
- Repositorios: `Repositorio<Agregado>` (ej. `RepositorioSolicitud`).
- Servicios: `Servicio<Dominio>` (ej. `ServicioSolicitud`).
- Schemas Pydantic: `Datos<Accion>` para entrada (request body), `Salida<Modelo>` o `Respuesta<X>` para respuesta.
- Páginas React: `Pagina<X>` (ej. `PaginaPanel`, `PaginaSubida`).
- Hooks: `use<Cosa>` (`useAutenticacion`, `usePermisos`, `useNotificacion`).
- Componentes utilitarios: nombre descriptivo en español (`BotonVolver`, `ModalConfirmacion`).

### Estructura

**Backend (DDD ligero)**:
```
api/v1/          → endpoints (router). Solo orquestan, no llevan lógica.
domain/services/ → reglas de negocio. Aquí van validaciones, FK checks, etc.
domain/repositories/ → único punto de acceso a la BD por agregado.
domain/models/   → ORM (SQLAlchemy 2). Tablas + relaciones.
domain/schemas/  → contratos (Pydantic). Entrada/salida HTTP.
core/            → cosas transversales: config, JWT, LDAP, email, rate limit.
infrastructure/  → engine BD y sesión, almacenamiento de documentos, tareas de fondo.
```

**Frontend (módulos por dominio)**:
```
modulos/<dominio>/  → páginas + CSS modules de ese dominio.
components/         → UI reutilizable entre módulos.
context/            → providers globales (tema, autenticación, permisos).
hooks/              → hooks compartidos (useAutenticacion y usePermisos leen de sus providers).
api/                → cliente HTTP + módulos por dominio.
constants/          → números mágicos.
```

### Seguridad — reglas no negociables
1. **Nunca** usar f-string para construir filtros LDAP. Usar `escape_filter_chars()`.
2. **Nunca** servir archivos sin validar que la ruta resuelta esté dentro de la raíz permitida (`.resolve().relative_to(raiz)`). Las rutas de la BD son **relativas** a `STORAGE_PATH` (`ruta_relativa` / `ruta_segura` en `almacenamiento.py`, revisión `b5c2e8f4a713`): no vuelvas a guardarlas absolutas, que se rompen al mover o renombrar la carpeta.
3. **Nunca** confiar en el `content_type` que envía el cliente — usar `python-magic` sobre el contenido.
4. **Nunca** loguear tokens, contraseñas ni el DN LDAP completo.
5. **Nunca** loguear queries SQL en producción (`echo=False` cuando `APP_ENV=production`).
6. **Nunca** versionar `.env`. Está en `.gitignore`. Si el usuario lo va a versionar, avisar.
7. **Nunca** usar `--no-verify`, `--no-gpg-sign`, ni saltarse hooks de git sin permiso explícito.
8. JWT se verifica contra BD en cada request — esto es **a propósito** para revocación inmediata: el estado de la cuenta y `users.sesiones_validas_desde` contra el `iat` del token (cerrar sesión, cambiar o restablecer la contraseña y desactivar la cuenta invalidan los tokens ya emitidos). No lo conviertas en caché sin pensar el trade-off.
9. Rate limit en `/auth/login`, `/auth/cambiar-contrasena` y `/verificacion/{codigo}` (el único endpoint público) — si agregas otro endpoint público, agrégalo, y súmalo a la lista de `test_solo_estas_rutas_responden_sin_sesion` (`tests/test_seguridad.py`), que falla con cualquier ruta sin token que no esté ahí.
10. Los documentos del expediente solo se sirven con sesión, validando acceso a la solicitud (`ServicioSolicitud.obtener_documento`) y dejando DOCUMENTO_VISTO/DESCARGADO en la bitácora. **Nunca** vuelvas a exponer archivos por token o enlace público.
11. Separación de funciones: nadie revisa (impedimentos, aprobar, devolver, negar) una solicitud que creó o que es de su agencia. No la quites "para probar": usa dos cuentas.
12. El login responde lo mismo si el usuario no existe y si la contraseña está mal (`ErrorAcceso` en `auth_service.py`); el motivo real va solo a la bitácora. No vuelvas a distinguirlos: revela qué cuentas existen en el AD.
    - Al AD solo se le pregunta por cuentas del AD **registradas y activas en ARGO NAVIS** (`ServicioAutenticacion._login_ad`). No vuelvas a consultarlo antes de esa comprobación: ARGO NAVIS serviría para probar contraseñas de cualquier cuenta del SNM (con la correcta respondía "no tienes acceso") y para bloquearlas.
    - El freno de las cuentas del AD vive en la BD (`users.intentos_fallidos` / `bloqueado_hasta`, las columnas del bloqueo de las locales) y la fila queda bloqueada durante el login (`RepositorioUsuario.buscar_para_login`, FOR UPDATE). No lo pases a memoria: con varios workers o pedidos en paralelo, al AD le llegarían más intentos (`test_freno_del_ad_con_intentos_en_paralelo`).
    - `LOGIN_AD_MAX_FALLOS` va por debajo del umbral de bloqueo del dominio y `LOGIN_AD_MINUTOS_ESPERA` es mayor o igual que su ventana de restablecimiento.
    - Se acepta que el freno (429) y el bloqueo de las locales (423) delaten que la cuenta existe en ARGO NAVIS: no revelan el directorio del AD.
13. nginx **reemplaza** `X-Forwarded-For` con `$remote_addr` (el backend confía en esa cabecera para el rate limit y la bitácora). No vuelvas a `$proxy_add_x_forwarded_for`: el cliente podría inventarse la IP.
14. Lo que sube una agencia es **no confiable**: entran por la VPN, pero no son del SNM. El Word se previsualiza en un `<iframe sandbox="">` con su propia CSP, sin enlaces, sin altChunks y con las imágenes como `data:` (`ModalPreview.tsx`). **Nunca** pintes en la página HTML que salga de un documento (docx-preview directo en el DOM, `dangerouslySetInnerHTML`): un enlace `javascript:` dentro de un .docx corría en ARGO NAVIS con la sesión de quien revisaba.
15. CSP en `frontend/nginx.conf` y en `_CABECERAS_SPA` (`backend/app/main.py`), iguales: si cambias una, cambia la otra. Solo código propio: nada en línea, nada de CDN, nada que use `eval` o `new Function`. Si una librería lo necesita, busca otra; no aflojes la CSP.
16. Crear y corregir solicitudes (lo que sube archivos) tienen tope por cuenta: `@limiter.limit(limite_envios, key_func=clave_usuario)` y `LIMITE_ENVIOS_POR_HORA`. Un endpoint nuevo que suba archivos lleva el mismo decorador.
17. En producción el backend no arranca con una `SECRET_KEY` de menos de 32 caracteres o de ejemplo (validador en `core/config.py`).
18. Los servidores de desarrollo escuchan solo en este equipo (`start-backend.bat` en 127.0.0.1, Vite en `localhost`): no tienen las protecciones de producción. `VITE_HOST=0.0.0.0` solo para probar desde otro equipo, y por un rato.

### Errores
- Backend: `HTTPException` con código y `detail` descriptivo. Nunca `except: pass`. Loggear con `logger.warning/.error` con contexto.
- Frontend: `useNotificacion()` (toast) para errores, `useConfirmar()` (modal) para acciones destructivas. **Nunca** `alert()` ni `window.confirm()`.

### Async correcto
- Backend: SQLAlchemy async siempre. No mezclar `Session` sincrónica.
- Si necesitas ejecutar CPU-bound (zip, hashing), usar `asyncio.to_thread()`.
- `obtener_sesion_bd()` ya hace `commit` en éxito y `rollback` en excepción — no hacerlo manualmente en endpoints.
- Pídela **siempre** como `Depends(obtener_sesion_bd, scope="function")`: con ese scope el commit corre antes de responder y antes de las tareas en segundo plano (correos). Sin el scope, FastAPI la trata como otra dependencia y habría dos sesiones en el mismo request.
- Transiciones de una solicitud: carga con `RepositorioSolicitud.buscar_por_id(id, bloquear=True)` (SELECT ... FOR UPDATE). La prueba `test_aprobar_y_negar_a_la_vez` falla si se quita.
- Lo que no se deshace con un rollback (borrar archivos) va en `al_confirmar(sesion, accion)` (`infrastructure/database.py`): corre después del commit y se descarta si hay rollback.

### Frontend strict
- `tsconfig` con `strict: true`. Si necesitas `any`, justifica el `// any` con un comentario.
- TS quita `noUnusedLocals` y `noUnusedParameters`. Si una variable sale, eliminarla.
- `eslint-plugin-react-hooks` en exhaustive deps. Si quitas una dep, deja `// eslint-disable-next-line` con el porqué.

### Interfaz (revisión de UI/UX del 2026-10-19)
- **Paleta SNM** (pedido del usuario del 2026-10-19: «basate en los colores del logo y en el estándar de la página web»). Sale del escudo (amarillo `#FFE400`, negro, celeste `#15B0DE`) y de los tokens propios de migracion.gob.pa (`--snm-*`):
  - Marino `#10233F` / `#17283E` para los textos, azul institucional `#003DA5`, amarillo `#F2C94C` (hover `#FFD633`), líneas `#DCE4ED` / `#CAD5E1`, fondos `#F6F9FC` / `#EEF4F8` y crema `#FFF8D8`.
  - El tema claro es el de la web. El oscuro, la pizarra de su cabecera. El detalle, con cada valor y su contraste, está en el comentario de `styles/globals.css`.
  - Cabecera y pie en pizarra (`#1B252F` / `#2D363F`) en los **dos** temas, como en la web: sus textos van en `--cabecera-texto*` / `--pie-texto`, no en `--text`.
  - El foco va en azul institucional en claro y en amarillo en oscuro y sobre la cabecera.
  - Sin colores fijos en los CSS: los tintes de estado se arman con `color-mix(in srgb, var(--acc-*) N%, transparent)`. Quedan fijos solo la bandera, la hoja del visor de documentos y la barra del navegador (`#1B252F`: `index.html`, `tema-inicial.js` y `ContextoTema.tsx`).
- El amarillo de marca (`--y`) es solo **relleno**: el botón principal de cada pantalla, lo seleccionado (pestaña, filtro, tema) y el foco en oscuro. **Nunca como color de texto** (en claro da 1.6:1 y el dorado se ve oliva): textos con `--text` / `--text-2` / `--muted`, estados con `--acc-*`. Sobre el amarillo, texto marino (`--on-accent`), como los botones de la web.
- Botones: principal amarillo; secundario neutro con borde; aprobar con `--exito-fuerte`, denegar/eliminar con `--peligro-fuerte` (o contorno rojo); "Volver" discreto. Desactivado en gris (`--overlay-2` + `--muted`), no amarillo a media opacidad. En `useConfirmar`, `peligroso` (rojo) o `exito` (verde) según la acción.
- "En corrección" va en naranja (`--acc-orange`): el ámbar se confundía con la marca.
- Encabezado de página: `EncabezadoPagina` (título y descripción a la izquierda, acciones a la derecha); el expediente lleva el suyo.
- Campos con `--input-border` / `--input-bg` (borde de 3:1). Las notas informativas, neutras con borde izquierdo `--acc-blue`.
- Tablas que en el celular pasan a fichas: cada `<td>` lleva `data-etiqueta` (tripulantes del expediente, usuarios).
- Si cambias un color, recalcula el contraste también sobre los fondos teñidos (insignias, avisos, contadores).
- El correo (`core/email.py`) y el PDF (`core/pdf_autorizacion.py`) usan la misma paleta (2026-10-20). El color de cada estado es el de su insignia (`InsigniaEstado`): recibida en azul, aprobada en verde, devuelta en naranja, denegada en rojo, expirada en gris y, en el PDF, finalizada en verde azulado.
- Revisión de UCVMM (propuesta 1A, elegida por el usuario el 2026-10-19):
  - Los impedimentos se marcan en una columna Sin / Con de la tabla de tripulantes (`SeccionTripulantes`). El estado vive en `useVerificacionImpedimentos`, que lo comparte con el panel de decisión (`PanelRevision`).
  - La columna lateral queda fija al bajar (sticky, 300 px) y cada decisión es un solo modal (`ModalDecision`).
  - `ModalDecision` va en un portal al `body`: dentro del sticky quedaba debajo de la cabecera.
- Paso 1 de «Nueva solicitud» en tarjetas (`SelectorTramite`, propuesta 2A): la descripción sale del catálogo y lo que pide, del checklist. Cambiar de trámite con archivos ya adjuntos pide confirmación (se quitan).
  - Cada trámite tiene ícono y color propios (`PRESENTACION`, por código, en el frontend): mosaico sólido en un `--acc-*` con el ícono en `--card`. Con todos en gris no se distinguían (pedido del usuario del 2026-10-19). En la grilla, los colores vecinos no se parecen.

## Estado actual (snapshot 2026-10-16)

### Lo que se hizo en la adaptación storage → sistema (revisión `d4f1a8c27e90`)
- `transfers` / `transfer_files` se reemplazaron por `solicitudes`, `solicitud_tripulantes`, `solicitud_documentos` y `solicitud_eventos`. Las transferencias sueltas se eliminan al migrar (con sus carpetas). Se retiraron el enlace público `/t/{token}`, la subida suelta y la purga de 7 días.
- Las solicitudes son de la **agencia** (`agencias_navieras`, `users.agencia_id`), no del usuario. Rutas por `id` (`/solicitudes/{id}`), sin tokens.
- Documentos en `STORAGE_PATH/solicitud-{id}/`, validados en `infrastructure/almacenamiento.py`; los nuevos pasan por una carpeta `tmp-*` para no consumir un número si se rechazan.
- Bandejas paginadas en el servidor con conteos por estado; bloqueo de fila en las transiciones; separación de funciones; vencimientos con un solo ejecutor (`pg_try_advisory_xact_lock`, `infrastructure/tareas.py`); avisos armados en `domain/services/notificacion_service.py`.
- Cuentas locales endurecidas: política de contraseñas (hoy la del 2026-10-16, ver abajo), bloqueo de 15 min tras 5 fallos, cambio obligatorio (alta o restablecimiento) que el backend exige en `obtener_id_usuario_actual`. El LOGIN_FALLIDO ya queda en la bitácora (el endpoint responde sin relanzar).
- Se retiró el Formulario 4 (y la condición `si_custodia`). La columna `tipos_tramite.formulario` se conserva por si vuelve.
- Frontend: `ProveedorAutenticacion` / `ProveedorPermisos` (una sola carga por sesión), visor de documentos con blob autenticado, páginas de admin sobre `MarcoPagina`, lint en cero.
- Pruebas: `backend/tests/` (pytest sobre BD temporal, migración ida y vuelta incluida).

### Después (revisiones `b9e4d17a3c52` y `c7a2e94b1f30`)
- Catálogo alineado al Form. 3 y al documento de UCVMM (ver "Reglas" abajo).
- Validaciones de fechas, impedimentos por tripulante y puesto de finalización.
- Rol SysAdmin separado del Administrador. Desde el 2026-10-20 el Administrador tiene acceso total (también usuarios y roles); el SysAdmin sigue sin ver solicitudes.
- Tema Claro / Oscuro / Sistema (tokens en `styles/globals.css`, `public/tema-inicial.js` lo fija antes de pintar). La paleta "pizarra" de entonces se reemplazó por la del SNM el 2026-10-19 (ver "Interfaz").

### Revisión completa (2026-10-15, revisión `0a1c93f169d4`)
- Login sin enumeración de usuarios del AD; logs de la app configurados (`core/registro.py`).
- Sesión:
  - El frontend renueva el token mientras hay actividad (`GestorSesion` en `App.tsx`).
  - Cerrar sesión, cambiar o restablecer la contraseña y desactivar la cuenta invalidan los tokens (`users.sesiones_validas_desde`).
  - Tope de `SESION_MAXIMA_HORAS` (12) desde el login: el claim `ini` se conserva al renovar.
  - Tras el login se vuelve a la página pedida (enlaces de los correos).
- Permisos de solo lectura: la API ya no los crea, edita ni borra (los siembran las migraciones).
- LDAP: TLS opcional (`LDAP_USAR_SSL` / `LDAP_STARTTLS` / `LDAP_CA_CERT`, apagado por defecto), conexiones que siempre se cierran y el esquema del AD leído una vez por proceso.
- Cabeceras de seguridad en nginx y en el backend cuando sirve el frontend; `.dockerignore` en backend y frontend.
- `IntegrityError` → 409 (manejador en `main.py`); un puesto que solo fue de finalización tampoco se borra.
- Subidas: el 413 ya no deja el archivo (Windows) y los nombres largos se recortan.
- Correos con el diseño "pase marítimo" elegido por el usuario (`core/email.py`):
  - Asunto `Autorizaciones Marítimas · {número} · {estado}`, armado por `Aviso.asunto`.
  - Logo de ARGO NAVIS incrustado por Content-ID (`app/recursos/logo-argo-navis-correo.png`, PNG porque Outlook de escritorio no muestra WebP).
  - Versión en texto plano y vista previa para la bandeja. Cada paso arma su aviso en `notificacion_service.py`.
  - Si el SMTP falla, el aviso se reintenta a los 30 s y a los 2 min (`_ESPERAS_REINTENTO`, 2026-10-20). Los reintentos viven en memoria: un reinicio a mitad los pierde.

### Endurecimiento ante usuarios externos (2026-10-15)
Las agencias entran por la VPN, pero no son del SNM: se las trata como no confiables (reglas 12 y 14–18).
- Login del AD solo para cuentas registradas y activas en ARGO NAVIS, con freno en la BD y la fila bloqueada.
- Word en un marco aislado; CSP en nginx y en el backend.
- Tope de envíos por cuenta; los 429 responden con `detail` como el resto de los errores.
- `SECRET_KEY` fuerte en producción; servidores de desarrollo solo en este equipo.
- `test_solo_estas_rutas_responden_sin_sesion` hace el inventario de las rutas sin token.
- Decisiones del usuario (2026-10-16):
  - Contraseñas de las cuentas locales: 12 a 64 caracteres con mayúscula, minúscula, número y carácter especial, sin el nombre de usuario ni palabras obvias (`problema_de_contrasena` en `domain/schemas/user.py`, **espejado** en `frontend/src/utils/contrasena.ts`). Quien entra con una que ya no cumple debe cambiarla (`_login_local`). La temporal del restablecimiento la cumple.
  - Agencia desactivada = sus usuarios no entran: el login responde 403 (solo tras validar la contraseña) y `obtener_id_usuario_actual` corta la sesión abierta con 401.
  - Los funcionarios también entran por la VPN: el login del AD no se restringe por red.
  - Segundo factor (TOTP) para las agencias: más adelante. Antivirus de los archivos: por ahora no.

### Lo que sigue pendiente (no urgente)
1. **HTTPS y TLS con el AD** — la configuración está lista (README → "Producción"); falta el certificado del servidor y el del controlador de dominio (infraestructura).
2. **JWT en cookie httpOnly** — actualmente en localStorage, con la CSP como barrera (regla 15). Plan en README → "Decisiones documentadas".
3. **Redis para rate limit** si se escala a varios hosts (en un host con varios workers el límite es por proceso).
4. **Refactor de componentes grandes** (`PaginaSolicitud` ~680 líneas) extrayendo subcomponentes y hooks. El expediente ya se partió (2026-10-19).
5. **Edición del catálogo de trámites desde la UI** — hoy se ajusta con migraciones.
6. **Solicitud de Custodia y Solicitud de Transbordos** — el documento de UCVMM dice que faltan por levantar; no están modeladas.
7. **Política de retención de datos personales** — decisión del equipo.
8. **Segundo factor (TOTP) para las cuentas de las agencias** — decidido para más adelante (2026-10-16).
9. **Antivirus (ClamAV) para los archivos subidos** — por ahora no (2026-10-16); necesita el servicio en el servidor.
10. **Cambio de puerto de una autorización ya aprobada** — en consulta con UCVMM (2026-10-16). **No construir nada hasta tener su respuesta.**
    - Hoy solo el puesto autorizado (o el Administrador) la ve y la finaliza; puede anotar que terminó en otro puesto.
    - Dos vías: el trámite «Cambio de Puerto» del Form. 3 ligado a la original (que pasaría a un estado nuevo «Reemplazada»), o una reasignación del puesto con un permiso propio. Recomendada la primera si UCVMM la confirma: es su trámite.
    - Preguntas abiertas: ¿aplica solo a embarques («nuevo puerto a embarcar»)? ¿Puede ser de algunos tripulantes? ¿Se reutilizan los documentos? ¿Quién cierra un cambio de último minuto? ¿Qué pasa con la original?
    - Mientras tanto: la agencia presenta el «Cambio de Puerto» con el número original en las observaciones (la original vence sola), o el puesto autorizado finaliza indicando dónde terminó.
11. **Importar tripulantes desde una plantilla Excel** (propuesta 3 de la revisión de UI) — por ahora no (2026-10-19).
    - Vale la pena si las tripulaciones suelen ser grandes. Para decidir: `SELECT count(*), round(avg(cantidad_tripulantes), 1), max(cantidad_tripulantes), count(*) FILTER (WHERE cantidad_tripulantes > 10) FROM solicitudes;`.

### Flujo actual: Autorizaciones Marítimas (UCVMM)

Basado en el documento de UCVMM "Documentación requerida para las autorizaciones marítimas". Backend: `api/v1/solicitudes.py` → `domain/services/solicitud_service.py` → `domain/repositories/solicitud_repository.py`. Frontend: `modulos/solicitudes/`.

**Roles:**
- **Naviera** (`T-CREAR-BASICA` + `users.agencia_id`) — envía solicitudes de su agencia (`/new`) y corrige las devueltas dentro del plazo. Cualquier usuario de la agencia ve y corrige las de la agencia. Sin agencia no puede enviar; con la agencia desactivada no entra.
- **Sector Pacífico / UCVMM** (`T-PROCESAR-PACIFICO`) — revisa:
  - Verifica impedimentos **por tripulante** (`solicitud_tripulantes.con_impedimento`, NULL = sin verificar). Todos marcados es obligatorio para aprobar; con impedimento igual se puede aprobar. El comentario es opcional.
  - Registrada, la verificación queda de solo lectura. Cambiarla es una **corrección**:
    - Exige `motivo_correccion`.
    - Deja un evento `impedimentos_corregidos` (interno, como `impedimentos`) con qué cambió y por qué.
    - Repetirla sin cambios responde 409.
    - `corregir()` de la agencia la reinicia: la siguiente es una verificación nueva, no una corrección.
  - Aprueba, devuelve a corrección o deniega (el estado se muestra como "Denegada"; en la BD y la API sigue siendo `denied` / `/negar`).
- **Puesto de Control** (`T-FINALIZAR-PUERTO` + asignación en `usuarios_puestos`) — ve las aprobadas de sus puestos y las finaliza: un solo paso con comentario obligatorio.
  - El comentario sin finalizar (`POST /solicitudes/{id}/comentarios`) se retiró el 2026-10-20: no tenía pantalla. Los eventos `comentario` de antes se siguen mostrando, solo al SNM.
  - Indica el puesto donde terminó la operación (`puesto_finalizacion_id` / `_nombre`, por defecto el autorizado). Puede ser otro: se muestra en el expediente, el PDF y la verificación pública.
  - El rol se siembra con `es_sistema = false` (el admin puede renombrarlo o borrarlo).
- **Administrador** — acceso total (decisión del usuario del 2026-10-20): bandejas y expedientes (atajo a todos los `T-*`), catálogo de trámites, agencias/puestos/nacionalidades (`/admin/catalogos`), estadísticas, bitácora y también usuarios y roles (`/admin`, `/admin/roles`). Antes solo listaba usuarios y roles.
- **SysAdmin** — rol técnico, sin permisos `T-*` y sin atajo: usuarios (`/admin`), roles (`/admin/roles`; los permisos son fijos y solo se asignan a roles) y bitácora. No ve solicitudes (403 en la API; el frontend lo manda a `/admin`).
  - El último SysAdmin activo no se puede desactivar, borrar ni cambiar de rol (409).
  - Administrador y SysAdmin no se pueden renombrar y sus permisos son fijos (400 en `asignar_permisos_a_rol`): el SysAdmin no puede darse permisos `T-*`.
  - Nadie cambia su propio rol (400): ni subirse de rol ni quedarse fuera por error.
  - El primero se nombra desde la consola: `python -m app.infrastructure.asignar_rol <usuario> SysAdmin` (queda en la bitácora como "consola").

**Estados (`solicitudes.estado`, con CHECK en la BD):** `review` → `approved` → `finalized`; `review` → `returned` → (corrige) `review`; `review` → `denied`; `approved` o `returned` con el plazo vencido → `expired` (`infrastructure/tareas.py`).

**Reglas que no son obvias leyendo el código:**
- El checklist vive en BD (`tipos_tramite`, `documentos_requeridos`, `tramite_documentos`) y sus condiciones se resuelven en `ServicioTramite.construir_casillas`, **espejado** en `frontend/src/modulos/solicitudes/checklist.ts`: si cambias uno, cambia el otro.
- Cada solicitud guarda la **foto del checklist** con el que se envió (`solicitud_casillas`). La foto se vuelve a tomar en cada corrección.
  - El expediente se evalúa contra esa foto, no contra el catálogo de hoy. Es el mismo principio que `nacionalidad_restringida` del tripulante.
  - Un cambio del catálogo no deja incompletas las solicitudes ya enviadas ni los expedientes cerrados. La siguiente corrección sí se valida con las reglas nuevas.
  - Antes de `7e3f1a9c2d64` se evaluaba en vivo, y el cambio de `b9e4d17a3c52` (Carta y Reporte "por tripulante") marcó como faltantes documentos que sí estaban.
- `solicitud_documentos.documento_id` nulo = documento adicional (fuera del checklist; máx. 20 por solicitud).
- Asignar un usuario a una agencia o a un puesto no le da acceso sin el permiso de su rol: la API exige las dos cosas (`ContextoAcceso`). Por eso la pantalla de catálogos ofrece «Mostrar todos los usuarios» a propósito.
- `valida_vigencia` está activa en **todos** los trámites: un pasaporte o seamanbook que vence antes del día de la operación no deja enviar. Los rangos distintos de "marino" no portan seamanbook.
- Fechas (`ServicioTramite.validar_tripulantes` y `_validar_formulario`, espejadas en `validacionFormulario.ts`):
  - La operación va de hoy a `DIAS_MAXIMOS_ANTICIPACION` (365).
  - Tripulantes con 18 años cumplidos y nacidos desde 1900.
  - Pasaporte y seamanbook vencen después del nacimiento.
- Formatos del expediente: PDF, Word y Excel (`.pdf .doc .docx .xls .xlsx`, decisión del usuario del 2026-10-15, "de momento"; antes solo PDF). En `infrastructure/almacenamiento.py`, espejo en `utils/archivos.ts`:
  - El contenido se comprueba por formato: firma `%PDF-`; OLE2 para .doc/.xls; ZIP OOXML con su parte principal para .docx/.xlsx.
  - Los de Office se rechazan si traen macros: `oletools`, que falla cerrado, y cualquier `vbaProject.bin` dentro de un .docx/.xlsx.
  - El MIME sale de python-magic o, si no lo precisa, del formato ya verificado.
  - La vista previa muestra .docx y .xlsx; .doc y .xls se descargan.
  - Máximo **2 MB por archivo**, en cualquier formato (decisión del usuario del 2026-10-16): `TAMANO_MAXIMO_MB` en `almacenamiento.py`, espejo en `utils/archivos.ts`. Es una constante y no una variable de entorno a propósito, para que backend y frontend no se desalineen. Los documentos ya cargados que pesan más se siguen viendo.
- **El catálogo sigue tal cual los documentos, sin criterio propio** (lo pidió el usuario):
  - Qué documentos: el recuadro del trámite en el **Formulario No. 3 oficial**. Por eso Desembarque lleva Generales de pasaporte, aunque el documento de proceso no la liste.
  - Por tripulante o por solicitud: cada proceso dice "para cada tripulante…". La única excepción escrita es la Lista de Tripulantes, que "debe subirse al trámite" (pág. 9). Por eso la Carta de responsabilidad y el Reporte médico van por tripulante.
  - Flujo y requisitos del sistema: págs. 9–10 del documento de proceso.
  - **Dos excepciones decididas por el usuario** sobre la lectura literal (2026-10-14):
    - La vigencia se valida en los 8 trámites, no solo en los 3 que la mencionan.
    - La libreta de Embarque se pide a todo Marino (`siempre`), no solo a los panameños. La condición `solo_panamenos` queda en el enum sin uso.
- Nacionalidad restringida (`paises.nacionalidad_restringida`):
  - El Form. No. 6 se adjunta **solo en Desembarque** ("cuando aplique", como en el Form. 3).
  - `tipos_tramite.aviso_custodia` marca los trámites cuyo proceso dice que, al aprobar, se avisa a la agencia que debe realizar el trámite de solicitud de custodia: Desembarque, Urgencias, Renovación y Shore Pass.
  - En los demás trámites no se menciona: ni en el formulario, ni en el expediente, ni en el correo, ni en el PDF.
  - **Ninguna nacionalidad viene sembrada**: la lista oficial la marca el admin.
- `tipos_tramite.rangos_permitidos` limita los rangos del trámite (nulo = cualquiera); hoy solo F3-TECNICO, por el nombre del trámite en el Form. 3. Lo valida `ServicioTramite.validar_tripulantes` y lo espeja `validacionFormulario.ts`.
- Las aclaraciones del instructivo del Form. 3 para el buque y el puerto ("nueva nave a embarcar", etc.) viven en `AYUDA_CAMPOS_TRAMITE` (`modulos/solicitudes/presentacion.ts`).
- `tipos_tramite.descripcion` (revisión `a3d9c6e1f584`) es una línea con cuándo se usa el trámite, para las tarjetas del paso 1.
  - Primera versión del 2026-10-19, apoyada en los documentos que pide cada trámite (el boleto aéreo del Desembarque, la cita del consulado de la Renovación): **falta validarla con UCVMM**.
  - Se cambia con una migración, como el resto del catálogo.
- `tests/test_documento_ucvmm.py` es la lectura literal del Form. 3 y del documento de UCVMM por trámite: si cambias el catálogo, esa tabla tiene que seguir coincidiendo (o cambia porque UCVMM cambió el requisito).
- Lo interno no le llega a la agencia. Lo filtra el backend (`ContextoAcceso.es_personal_snm`, `_evento_para` en `solicitud_service.py`), no la vista:
  - Los eventos `impedimentos` y `comentario`.
  - El texto de `aprobada` y `finalizada`.
  - `observacion_aprobacion`, `comentario_finalizacion`, `aprobada_por`, `finalizada_por` y `con_impedimento`.
  - Los nombres de los funcionarios: el autor sale como "UCVMM" o "Puesto de control".
  - Los motivos de devolución y de negación **sí** los ve.
- La observación de aprobación es interna: no va en el PDF ni en el correo de aprobación. El PDF no tiene sección de observaciones.
- El PDF dice "Aprobada por: UCVMM", sin el nombre del funcionario. Lo recibe la agencia, que tampoco ve esos nombres en el expediente (decisión del usuario del 2026-10-15).
- `agencia_nombre`, `puesto_nombre` y `puesto_finalizacion_nombre` son una foto (al enviar o al finalizar): renombrar la agencia o el puesto no cambia expedientes viejos.
- Las solicitudes no se eliminan; un usuario (FK RESTRICT), agencia o puesto con solicitudes no se borra (se desactiva).
- El PDF (`core/pdf_autorizacion.py`, reportlab) lleva un QR a `/verificar/{codigo_verificacion}` (público, con rate limit). Ese código solo verifica: no abre el expediente.
- Bitácora = `audit_logs`. Los valores nuevos de `accionauditoria` se agregan en migración con `ALTER TYPE ... ADD VALUE IF NOT EXISTS` dentro de `op.get_context().autocommit_block()`. Los valores del storage (`TRANSFERENCIA_*`, `DESCARGA_REALIZADA`) se conservan para leer el historial.

### Historia que queda a propósito
Desde el 2026-10-16 todo se llama ARGO NAVIS: la base `argonavis`, los documentos en `storage/documentos` (en Docker, el proyecto `argonavis` y su volumen `documentos`), los respaldos `argonavis_*` y el repositorio `ArgoNavis`. El paso a paso para servidores instalados antes está en el README (Producción). Del storage original quedan, a propósito:
- Los valores `TRANSFERENCIA_*` y `DESCARGA_REALIZADA` de la bitácora, las migraciones viejas de Alembic (no se editan), `test_migraciones.py` (prueba la migración desde el storage) y la prueba de que `/transfers` ya no existe.
- `RATE_LIMIT_DOWNLOADS_PER_MINUTE` se sigue leyendo como alias de `LIMITE_VERIFICACIONES_POR_MINUTO`, para no romper los `.env` existentes.

### Lo que no debe romperse
- El flujo Agencia → UCVMM → Puesto de control descrito arriba.
- Documentos solo con sesión y auditados (ningún enlace público).
- El proxy de Vite (`/api` → backend) en dev; el frontend usa `/api/v1` relativo por defecto.
- Los roles fijos se reconocen por nombre: `rol_personalizado.nombre === "Administrador"` / `"SysAdmin"` (única fuente de verdad; `es_admin_efectivo` / `es_sysadmin_efectivo` en `core/permisos.py`, `esAdmin` / `esSysAdmin` en `ProveedorPermisos`).
- Las migraciones Alembic (`backend/alembic/versions/`) deben tener un `downgrade` que funcione (`tests/test_migraciones.py` lo comprueba).

## Cómo trabajar acá

### Antes de cambiar código
1. Lee el módulo completo antes de editar. La estructura DDD no es opcional.
2. Si vas a tocar el contrato HTTP (schemas o endpoints), busca primero quién los consume en el frontend con Grep.
3. Si vas a tocar la BD, el esquema lo maneja Alembic (`backend/alembic/versions/`): crea una revisión nueva con su `downgrade`.

### Antes de proponer un cambio grande
Hacé una pregunta corta primero. El proyecto está en producción de un organismo gubernamental, los cambios silenciosos no son gratis.

### Comandos útiles
```bat
:: Backend: validar imports rápido
cd backend && venv\Scripts\python -c "from app.main import aplicacion"

:: Backend: pruebas (BD temporal en el servidor de DATABASE_URL; no envía correos)
cd backend && venv\Scripts\python -m pytest

:: Frontend: typecheck y lint
cd frontend && node node_modules/typescript/bin/tsc -b --noEmit
cd frontend && npm run lint

:: Arranque dev (dos terminales separadas)
start-backend.bat
start-frontend.bat

:: Health check
curl http://localhost:8000/api/health
```

### Estilo de respuesta esperado
- Hablar español al usuario (es panameño, comunicación informal "vos/tú" ok).
- Resúmenes cortos al final, no parrafadas.
- Si modificás varios archivos, listar los paths al final con `path:linea`.
- Si una decisión rompe contrato (BD/API), avisar **antes** de hacerlo.
