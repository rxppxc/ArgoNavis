# Historial de ARGO NAVIS

Qué se hizo, cuándo y por qué, revisión por revisión: del storage original
(«FileDrop - SNM») a la auditoría del 2026-11-14. Hasta esa fecha vivía en
CLAUDE.md; se separó para que la guía quede con las reglas vigentes.

**Cada sección dice lo que era cierto en su fecha.** Lo vigente está en
[CLAUDE.md](../CLAUDE.md): si algo de aquí lo contradice, manda CLAUDE.md (por
ejemplo, las filas de los técnicos en Embarque y Desembarque del 2026-11-11 y la
condición `solo_panamenos` se quitaron el 2026-11-14).

## Lo que se hizo en la adaptación storage → sistema (revisión `d4f1a8c27e90`)
- `transfers` / `transfer_files` se reemplazaron por `solicitudes`, `solicitud_tripulantes`, `solicitud_documentos` y `solicitud_eventos`. Las transferencias sueltas se eliminan al migrar (con sus carpetas). Se retiraron el enlace público `/t/{token}`, la subida suelta y la purga de 7 días.
- Las solicitudes son de la **agencia** (`agencias_navieras`, `users.agencia_id`), no del usuario. Rutas por `id` (`/solicitudes/{id}`), sin tokens.
- Documentos en `STORAGE_PATH/solicitud-{id}/`, validados en `infrastructure/almacenamiento.py`; los nuevos pasan por una carpeta `tmp-*` para no consumir un número si se rechazan.
- Bandejas paginadas en el servidor con conteos por estado; bloqueo de fila en las transiciones; separación de funciones; vencimientos con un solo ejecutor (`pg_try_advisory_xact_lock`, `infrastructure/tareas.py`); avisos armados en `domain/services/notificacion_service.py`.
- Cuentas locales endurecidas: política de contraseñas (hoy la del 2026-10-16, ver abajo), bloqueo de 15 min tras 5 fallos, cambio obligatorio (alta o restablecimiento) que el backend exige en `obtener_id_usuario_actual`. El LOGIN_FALLIDO ya queda en la bitácora (el endpoint responde sin relanzar).
- Se retiró el Formulario 4 (y la condición `si_custodia`). La columna `tipos_tramite.formulario` se conserva por si vuelve.
- Frontend: `ProveedorAutenticacion` / `ProveedorPermisos` (una sola carga por sesión), visor de documentos con blob autenticado, páginas de admin sobre `MarcoPagina`, lint en cero.
- Pruebas: `backend/tests/` (pytest sobre BD temporal, migración ida y vuelta incluida).

## Después (revisiones `b9e4d17a3c52` y `c7a2e94b1f30`)
- Catálogo alineado al Form. 3 y al documento de UCVMM (ver "Reglas" abajo).
- Validaciones de fechas, impedimentos por tripulante y puesto de finalización.
- Rol SysAdmin separado del Administrador. Desde el 2026-10-20 el Administrador tiene acceso total (también usuarios y roles); el SysAdmin sigue sin ver solicitudes.
- Tema Claro / Oscuro / Sistema (tokens en `styles/globals.css`, `public/tema-inicial.js` lo fija antes de pintar). La paleta "pizarra" de entonces se reemplazó por la del SNM el 2026-10-19 (ver "Interfaz").

## Revisión completa (2026-10-15, revisión `0a1c93f169d4`)
- Login sin enumeración de usuarios del AD; logs de la app configurados (`core/registro.py`).
- Sesión:
  - El frontend renueva el token mientras hay actividad (`VigilanteSesion` en `App.tsx`).
  - Cerrar sesión, cambiar o restablecer la contraseña y desactivar la cuenta invalidan los tokens (`users.sesiones_validas_desde`).
  - Tope de `SESION_MAXIMA_HORAS` (12) desde el login: el claim `ini` se conserva al renovar.
  - Tras el login se vuelve a la página pedida (enlaces de los correos). Después de cerrar la sesión, no: se entra por el inicio (2026-11-11, ver «Navegación y versión nueva»).
- Permisos de solo lectura: la API ya no los crea, edita ni borra (los siembran las migraciones).
- LDAP: TLS opcional (`LDAP_USAR_SSL` / `LDAP_STARTTLS` / `LDAP_CA_CERT`, apagado por defecto), conexiones que siempre se cierran y el esquema del AD leído una vez por proceso.
- Cabeceras de seguridad en nginx y en el backend cuando sirve el frontend; `.dockerignore` en backend y frontend.
- `IntegrityError` → 409 (manejador en `main.py`); un puesto que solo fue de finalización tampoco se borra.
- Subidas: el 413 ya no deja el archivo (Windows) y los nombres largos se recortan.
- Correos con el diseño "pase marítimo" elegido por el usuario (`core/email.py`):
  - Asunto `Autorizaciones Marítimas · {número} · {estado}`, armado por `Aviso.asunto`.
  - Logo de ARGO NAVIS incrustado por Content-ID (`app/recursos/logo-argo-navis-correo.png`, PNG porque Outlook de escritorio no muestra WebP).
  - Versión en texto plano y vista previa para la bandeja. Cada paso arma su aviso en `notificacion_service.py`.
  - Si el SMTP falla, el aviso se reintenta durante unas 24 horas, desde la cola persistente (2026-10-29, ver abajo). Antes eran dos reintentos en memoria (30 s y 2 min), y un reinicio a mitad los perdía.

## Endurecimiento ante usuarios externos (2026-10-15)
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

## Pruebas del frontend y formulario partido (2026-10-21)
- Las reglas espejadas tienen casos compartidos en `backend/tests/espejo/*.json` (IMO, contraseñas, checklist, tripulantes). Los corren `test_espejo.py` (pytest) y los `*.test.ts` (Vitest); `test_constantes_iguales_en_el_frontend` compara las constantes (formatos, 2 MB, contraseñas, edad, anticipación, adicionales, rangos con libreta).
  - Encontraron una diferencia real: el 29 de febrero el frontend daba 18 años a quien nació el 1 de marzo. Se corrigió en `desplazar` (`validacionFormulario.ts`).
- Pruebas en el navegador (`frontend/e2e/`, Playwright):
  - `flujo-completo.spec.ts`: envío, devolución, corrección, aprobación, PDF y QR, finalización y bitácora.
  - `formulario.spec.ts`: el formulario sin enviar (cambiar de trámite, quitar un tripulante, adicionales).
  - `backend/tests/servidor_e2e.py` levanta la API en 127.0.0.1:8001 con la BD `argonavis_e2e` y una cuenta local por rol que solo existe ahí. La BD se borra al terminar (`e2e/limpiar.ts`).
  - Los `<input type="file">` del checklist llevan `aria-label` («Adjuntar / Reemplazar <documento> de <tripulante>»): los usan los lectores de pantalla y el E2E.
- `PaginaSolicitud` (684 líneas) se partió sin cambiar lo que hace: carga (`useCargaFormulario`), formulario (`FormularioSolicitud`), estado (`useTripulantesFormulario`, `useDocumentosFormulario`), secciones (`DatosTramite`, `ChecklistSolicitud`) y la ida y vuelta sin React (`envioSolicitud.ts`, con sus pruebas: precarga y armado del envío).

## Revisión completa e integración continua (2026-10-27)
- **Integración continua** en `.github/workflows/ci.yml` (GitHub Actions). Corre en cada push a main y en los pull request:
  - pytest;
  - tipos, lint, Vitest y build;
  - el E2E con Chromium (`PLAYWRIGHT_CHROMIUM=1`);
  - la auditoría de dependencias (`pip-audit` sobre `requirements.lock` desde el 2026-11-10, y `npm audit`).
  - Usa las versiones de producción: Python 3.12 y Node 24 (los Dockerfile), la misma imagen de PostgreSQL que el compose y las librerías de `requirements.lock`, con sus hashes. Si cambias una allá, cámbiala en el flujo (`test_dependencias.py` lo comprueba con PostgreSQL).
  - La auditoría corre además los lunes y bloquea: un aviso nuevo deja el job en rojo. Se actualiza o, si no aplica, se documenta en el flujo con `--ignore-vuln` y su porqué (hoy no hay ninguno).
  - Sin pull requests de Dependabot: el usuario es el único autor en GitHub, y esos PR salen a nombre del bot. Solo las alertas.
- **Topes de entrada:** todo texto libre y toda lista de los esquemas llevan tope acorde a su columna (`Field(max_length=...)`).
  - Sin tope, un valor más largo que la columna llegaba a la BD y respondía 500. Pasaba con el usuario del login (va a la bitácora, VARCHAR 100) y con el nombre de un rol.
  - Archivos por envío: hasta `MAX_ARCHIVOS_POR_ENVIO` (2000, en `schemas/solicitud.py`) y uno solo por casilla (`_resolver_asignaciones`).
- **Errores de las descargas:** llegan como Blob; `leerErrorDeBlob` (`api/client.ts`) los lee para mostrar el motivo real del servidor.
- **Después de un despliegue,** si falta un archivo de la versión anterior, `main.tsx` recarga la página (`vite:preloadError`, como mucho una vez por minuto). Desde el 2026-11-11 además se avisa la versión nueva (`VigilanteVersion`, ver «Navegación y versión nueva»).
- **E2E `accesibilidad.spec.ts`:** prueba el enlace «Saltar al contenido», los nombres de los controles y esa recarga.
- **Sesión con varias pestañas** (segundo lote del mismo día). Antes, una pestaña olvidada cerraba a los 15 min la sesión de la que se estaba usando: borraba el token, que es de todas.
  - La inactividad es la de todas las pestañas: la última actividad vive en localStorage (`ultima-actividad`, `utils/actividad.ts`).
  - `VigilanteSesion` (`App.tsx`) tiene un solo temporizador que relee ese valor: sigue, avisa o cierra.
  - La actividad se anota como mucho cada `ANOTAR_ACTIVIDAD_MS` (5 s). Las demás pestañas reciben el evento `storage`: se quita su aviso, y «Continuar sesión» en una lo quita en todas.
  - `VigilanteSesion` solo se monta con sesión, así que al cerrarla no queda un aviso viejo para la siguiente.
  - **No borres `ultima-actividad` al cerrar sesión:** las otras pestañas lo leerían como 15 minutos sin actividad.
  - `ProveedorAutenticacion` sigue a las otras pestañas por el evento `storage` de `user`: si una sale (o entra otra cuenta), las demás la siguen sin esperar a un 401.
  - Lo prueba `e2e/sesion.spec.ts`, con dos pestañas y el reloj del navegador adelantado (`clock`). Corrido contra el código anterior, falla.
- **Tarea de vencimientos:** un error en una vuelta queda en el log y no corta las siguientes (`tarea_vencimientos`). Antes, un aviso mal formado detenía la tarea hasta reiniciar; hoy queda «fallido» en la cola de correos.
- **TLS del correo:** `MAIL_STARTTLS` (587 o 25) o `MAIL_USAR_SSL` (465), excluyentes; el certificado se valida con `MAIL_CA_CERT`, como el del AD.
  - Apagado por defecto, con `start_tls=False` explícito: con `None`, aiosmtplib intenta STARTTLS por su cuenta y, si no reconoce el certificado, no sale nada.
  - Con usuario y sin TLS, el backend lo advierte al arrancar.
  - El compose ahora pasa `MAIL_USERNAME`, `MAIL_PASSWORD`, el puerto y el TLS.
- **Dependencias:** Vite a 8.3.5 (avisos del servidor de desarrollo); `follow-redirects` 1.16.2 y `zod` 4.6.7 con `npm audit fix`; `pip-audit` en `requirements-dev.txt`.
  - `uuid` va forzado a ^11.1.1 (`overrides` en `package.json`) solo para la auditoría. El aviso (v3/v5/v6 con `buf`) no aplica: exceljs solo usa v4, y el navegador recibe su `dist` ya empaquetado.
- **`.gitattributes`:** `*.sh` en LF y `*.bat` en CRLF. El Dockerfile además quita los CR del entrypoint, por los clones de Windows anteriores.
- **PyJWT en lugar de python-jose** (tercer lote). python-jose tenía un aviso propio sin arreglo (GHSA-3qf3-8w2g-rqmx) y arrastraba `ecdsa`, también con un aviso sin arreglo.
  - Los tokens son idénticos byte a byte con las dos librerías: las sesiones abiertas sobreviven al despliegue, y también a una vuelta atrás.
  - `iat` sigue con fracción de segundo (la revocación en el mismo segundo depende de eso): PyJWT lo valida, pero no lo redondea.
  - `ALGORITHM` acepta solo HS256, HS384 o HS512 (`Literal` en `core/config.py`). PyJWT, a diferencia de python-jose, conoce `none`: con ese valor emitiría y aceptaría tokens sin firma.
  - `test_token_solo_con_el_algoritmo_y_la_clave_del_servidor`: vencido, sin firma, con otro algoritmo o con otra clave dan 401, nunca 500.
  - Una instalación de Windows que ya existía conserva python-jose, `ecdsa` y `rsa` hasta que se desinstalen: no estorban, pero el análisis los marca.
- **Documentación de la DTI en v0.2** (`docs/`, cuarto lote): el 00, 01, 04, 06, 07, 08 y 09 quedaron al día con el sistema del 27/10/2026. El 03 ya estaba en la 0.2; el 02 y el 05 siguen en la 0.1, porque lo que describen no cambió.
  - El 00, el 01 y el 08 tenían el diseño viejo: el 20/10 se generaron con el nuevo, pero no se copiaron a `docs/`. Ahora todos traen portada, control con firmas, historial e índice.
  - El 04 suma la sección M (RN-83, topes de entrada) sin renumerar: el 08 cita las reglas por número.
  - Las capturas del 01 y la 09 son de la interfaz del 27/10, con datos ficticios.
  - Si cambia el código, actualiza el documento afectado y su versión (`docs/README.md` → Mantenimiento).
- **Logs en archivo** (2026-10-29): con `LOG_CARPETA`, además de la consola, queda un archivo por día (`argonavis-AAAA-MM-DD.log`, `ArchivoDiario` en `core/registro.py`) que se borra a los `LOG_DIAS` días. Van el logger `app` y `uvicorn.error`; los accesos por petición, no. `LOG_NIVEL` fija el nivel de `app`.
  - **No uses `RotatingFileHandler`:** rota renombrando, y en Windows el renombre falla mientras otro de los 4 workers de `start-backend-prod.bat` tiene el archivo abierto. Por eso, un archivo por día que nunca se renombra.
  - En Windows el archivo se abre con `FILE_APPEND_DATA` (`_abrir_para_agregar`), que agrega cada línea al final de una sola vez. Con el modo `"a"` de Python, 4 procesos perdieron 6807 de 12000 líneas. Lo prueba `test_varios_procesos_no_se_pisan_las_lineas`, que falla con el modo `"a"`.
  - En Docker no hace falta: la salida estándar la guarda y rota Docker. Las pruebas vacían `LOG_CARPETA` (`conftest.py`, `servidor_e2e.py`).
- **Cola persistente de correos** (2026-10-29, revisión `c4e9a2f7b815`, tabla `correos_salida`). Antes los reintentos vivían en memoria: con el SMTP caído más de ~2,5 min, o con un reinicio, el aviso se perdía.
  - Los avisos se encolan **en la transacción de la operación** (`encolar_avisos`, `infrastructure/cola_correos.py`): si no se confirma, no salen; si se confirma, no se pierden. Los endpoints lo hacen en `_programar` (`api/v1/solicitudes.py`), y los vencimientos, en su propia transacción.
  - Salen enseguida (`despachar_correos`, como tarea en segundo plano de la respuesta). Lo que falla, lo reintenta `tarea_correos` cada minuto, con esperas crecientes (`ESPERAS_REINTENTO`): 10 intentos en unas 24 h. Agotados, queda «fallido» y en el log.
  - Un despacho para en el primer error del SMTP (2026-11-02): los demás fallarían igual y cada intento retiene una conexión de la BD.
  - Un aviso que no se puede armar queda «fallido» sin reintentos: reintentar daría el mismo error.
  - **Cada correo se toma con `FOR UPDATE SKIP LOCKED`** (`RepositorioCorreo.tomar_pendiente`), en su propia transacción. Sin eso, 3 despachos a la vez enviaron 16 correos en vez de 6 (`test_varios_despachos_a_la_vez_no_envian_dos_veces`).
  - Si el backend cae a mitad de un envío, el correo se reintenta: puede llegar dos veces, pero no se pierde.
  - Sin `MAIL_HOST` no se encola nada (como antes, queda el aviso en el log). Enviados y fallidos se borran a los 30 días.
  - `enviar_mensaje` (`core/email.py`) es un solo intento; los reintentos son de la cola. Las pruebas de la cola la vacían antes y después (`cola_vacia`) e importan `app.main`, que registra todos los modelos.

## Puntos de la reunión del 2026-10-30 (revisiones `f7a2c9e4b136` y `b2e7d4c9a160`)
- **Documentos según el rango:** a los rangos distintos de Marino (militar, técnico, supernumerario y superintendente) se les piden **solo** las Generales de pasaporte y la Copia de Boleto Aéreo, en todos los trámites. Al Marino, lo de antes. Es la tercera excepción a la lectura literal (ver «Reglas»). Desde el 2026-11-11, en Embarque y Desembarque los técnicos, supernumerarios y superintendentes llevan otro juego (la cuarta excepción).
  - `tramite_documentos.rangos` (nulo = a todos). Va por fila y no por documento: el boleto lo pide Desembarque a todos y los demás trámites solo a los no marinos; y el Form. No. 6 combina nacionalidad y rango, y `condicion` admite una sola.
  - `aplica_al_rango` (`tramite_service.py`) está espejado en `aplicaAlRango` (`checklist.ts`). `TripulanteChecklist` lleva `rango` en vez de `porta_libreta`; la Libreta sigue con `requiere_libreta`.
  - Técnico ya no lleva la Carta Form. 7: solo admite rangos no marinos.
  - Las solicitudes enviadas conservan su foto del checklist; una corrección se valida con la regla nueva.
  - En el catálogo del Administrador, el alcance «marino» (valor de la API) se muestra «Por tripulante»: «Por marino» junto a un documento solo para técnicos se leía contradictorio.
- **PDF interno:** el personal del SNM (`es_personal_snm`) descarga una copia con el nombre de quien aprobó («Nombre (UCVMM)», del historial), la leyenda «Copia interna del SNM — no entregar a la agencia» y el archivo `Autorizacion-{número}-interna.pdf`. La agencia recibe «Servicio Nacional de Migración» (hasta el 2026-11-11, «UCVMM»).
- **Sin finalización en otro puesto:** se finaliza siempre en el puesto autorizado. Si la operación se hace en otro, la agencia presenta una nueva solicitud y la original vence sola. Lo dicen el formulario, el expediente aprobado, el PDF, el correo de aprobación y el panel del puesto.
  - `puesto_finalizacion_id` / `_nombre` se siguen llenando (con el autorizado), para las estadísticas por puesto y las finalizadas de antes, que se muestran como estaban.
  - `DatosFinalizar.puesto_finalizacion_id` queda solo para que una página abierta antes del cambio reciba el motivo (400) si manda otro puesto.
- **Máximo 30 tripulantes por solicitud:** `MAX_TRIPULANTES` en `solicitud_service.py` (400 al crear y al corregir), espejo en `validacionFormulario.ts`; en 30, «Agregar tripulante» se reemplaza por el aviso. El tope de 300 del esquema queda como protección genérica.
- **Fuera del horario laboral:** de lunes a viernes, de 07:00 a 15:00, hora de Panamá. Sin feriados. **Desde el 2026-11-06** (ver abajo) cuenta la hora en que UCVMM aprueba (`aprobada_en`) y las 15:00 en punto son laborales: fuera es de 15:01 a 06:59 y el fin de semana. Antes contaba la finalización del puesto y las 15:00 ya eran fuera.
  - La regla vive en `core/horario.py` y en SQL (`_fuera_de_horario`, `solicitud_repository.py`): tienen que coincidir. Lo prueba `tests/test_horario.py`, con los bordes (15:00:59 dentro, 15:01 fuera).
  - Estadísticas: la cifra, su medidor y el mapa de horas, con la lista de las 50 más recientes (rediseño del 2026-11-02, ver abajo).
  - Insignia «Aprobada fuera del horario» en el expediente y en las bandejas, en morado (`--acc-purple`, no es el color de ningún estado). Hasta el 2026-11-11 era solo para el SNM; desde entonces la ve también la agencia, con el costo migratorio (ver «Cambios del 2026-11-11»).
- **Notificaciones internas (la campana de la cabecera):** lo que le toca hacer a cada rol (por revisar, por corregir, por finalizar, con enlace a su bandeja) y las novedades de sus solicitudes.
  - No hay tabla de notificaciones: los pendientes salen de los conteos de las bandejas (`contar_por_estado_en`) y las novedades, del historial, filtradas con `evento_para` (antes `_evento_para`). No cuentan las acciones propias; lo prueba `tests/test_pendientes.py`. Solo se guarda `users.novedades_vistas_hasta`.
  - `GET /pendientes` y `POST /pendientes/vistas` (`api/v1/pendientes.py`, `ServicioPendientes`). El SysAdmin no tiene campana.
  - `ProveedorPendientes` consulta al entrar, al cambiar de página, cada `CONSULTA_PENDIENTES_MS` (60 s) con la pestaña a la vista y al volver a ella. **No cuenta como actividad**: no evita el cierre por inactividad.
  - Con pendientes, la pestaña del navegador dice «(N) …». Un `MutationObserver` repone el prefijo cuando la página cambia su título (`useTituloDocumento`).
  - En el código se llama «Pendientes», para no chocar con `Notificaciones` (los avisos emergentes) ni con `Aviso` (los correos). En pantalla dice «Notificaciones».
  - El número va en blanco sobre la pizarra; el punto de novedades sin leer, en amarillo (relleno). En los teléfonos «Menú» es solo un ícono (`aria-label="Menú"`): con la campana al lado, el escudo de la cabecera desaparecía.
  - `PaginaPanel` lee `?bandeja=&estado=` de la URL: así los enlaces de la campana abren esa pestaña.
  - El E2E `flujo-completo.spec.ts` recorre la campana de UCVMM y la de la agencia.
- **Texto del permiso `T-FINALIZAR-PUERTO`:** decía «y las finaliza, indicando dónde terminó la operación». Lo corrige la misma `b2e7d4c9a160` («…y las finaliza en el puesto autorizado»), con su `downgrade`. La `d8c3f1a6b294` (2026-11-06) le suma la verificación de impedimentos.
- **Documentación de la DTI a la v0.3** (`docs/`): el 00, 01, 03, 04 (sección N, RN-84 a RN-88, sin renumerar), 06, 08 y 09; el 02 y el 05 pasan a la 0.2, y se redibujaron los BPMN 01 y 05. El 07 no cambió. La 0.2 del 03 se había hecho editando el Word: desde esta versión, sus cambios están también en el generador.

## Estadísticas (rediseño del 2026-11-02; menos texto y exportación, 2026-11-10)
Pedidos del usuario: «más interesante, interactivo, llamativo, que cualquiera lo entienda» (2026-11-02) y «que se puedan exportar a Excel, a CSV o a PDF, que tengan identidad; hay mucho texto, siento que hasta enreda» (2026-11-10). Todo en `modulos/administracion/estadisticas/`. `PaginaEstadisticas` lleva el periodo y la unidad de la serie (los usan los gráficos y la exportación) y arma las dos secciones.
- **Forma, de arriba abajo:**
  - el encabezado con «Exportar: Excel · PDF · CSV» (`BotonesExportar`, azul de contorno: descargar es consultar);
  - el periodo (`SelectorPeriodo`: Todo, Últimos 30 días, Este mes, Mes pasado, Este año y «Otras fechas»), que acota toda la sección;
  - la cifra que encabeza (recibidas) y, al lado, el «Estado actual»: una barra que reparte el 100 % entre los estados de hoy, con su leyenda (nombre, cifra y porcentaje);
  - cinco cifras sueltas con el porcentaje junto a la cifra, una nota corta («de las recibidas») y su medidor;
  - columnas por día, mes o año (recibidas, aprobadas y finalizadas, que se encienden y apagan);
  - barras por trámite y por puesto (finalizadas, por finalizar y expiradas);
  - el mapa de horas de las aprobaciones de UCVMM con el horario laboral recuadrado, y la lista de las aprobadas fuera del horario.
- **Menos texto (2026-11-10):** salieron el párrafo con lo mismo en frases (`resumenEnPalabras`), la explicación bajo cada estado (queda como `title` de la leyenda), las frases bajo cada cifra y las descripciones de varias líneas; los títulos son cortos («Por trámite», «Hora de aprobación de UCVMM»). **No vuelvas a contar las cifras en párrafos:** el detalle va en el globo y en «Ver tabla».
- **La unidad de la serie sigue al periodo** (`unidadSugerida`, `calculos.ts`): por día hasta un mes, por mes hasta un año y por año más allá; con «Todo», por mes. Se puede cambiar a mano. Antes «Mes pasado» mostraba una sola columna. Cuando la serie no llega al comienzo del periodo, el gráfico dice «Últimos 31 días» o «Últimos 12 meses».
- **Exportar** (`GET /solicitudes/estadisticas/exportar?formato=xlsx|pdf|csv&desde&hasta&unidad`, con el mismo permiso que las estadísticas). Lo arma el servidor en un hilo (`asyncio.to_thread`): lo común en `core/informe_estadisticas.py` (datos, textos, colores, nombre del archivo) y un módulo por formato (`informe_excel.py`, `informe_pdf.py`, `informe_csv.py`). Van las estadísticas del periodo y el uso del sistema (`ServicioUsoSistema`, `domain/services/uso_service.py`, que usa también `/admin/stats`).
  - Identidad: el escudo del SNM y el logo de ARGO NAVIS (`app/recursos/logo-argo-navis.png`, PNG de 400 px: XlsxWriter no lee WebP), la franja amarilla, la paleta del PDF de la autorización y cada estado en el color de su insignia. Dicen el periodo, quién lo generó y cuándo, y «Uso interno del SNM» (la lista de fuera del horario lleva nombres de funcionarios).
  - **Excel** (XlsxWriter 3.2.9, nueva dependencia): «Resumen» con las cifras, el estado actual y el gráfico de la serie que se veía en pantalla, y una hoja por tabla con gráficos nativos de Excel. El mapa de horas se pinta como en la pantalla (los 5 niveles y el recuadro). Las cifras son números y las fechas, fechas; ningún texto se convierte en fórmula (`strings_to_formulas: False`).
  - **PDF** (reportlab, carta): la identidad del PDF de la autorización, recuadros con las cifras, la barra del estado actual, las columnas de la serie y el mapa de horas dibujados, y «Página N de M». Las tablas largas se parten (`seccion(..., partir=True)`): con `KeepTogether` la sección entera saltaba de página y dejaba un hueco.
  - **CSV**: un archivo con secciones, UTF-8 con BOM (Excel lo abre con los acentos bien) y separado por comas. Lo que empieza con `=`, `+`, `-`, `@`, tabulador o retorno lleva un apóstrofo delante (OWASP, «CSV injection»).
  - Lo prueban `tests/test_exportar_estadisticas.py` y `e2e/estadisticas.spec.ts`, que descarga los tres.
- **Sin librería de gráficos:** HTML y CSS propios (la CSP no admite las que usan `eval`). Cada gráfico tiene «Ver tabla» con las mismas cifras, y el detalle (`Globo`) sale con el mouse, el foco y el dedo. El mapa de horas se recorre con las flechas.
- **Colores:** `--graf-*` en `globals.css`, el de la insignia de cada estado en pasos para marcas, validados con el validador de dataviz en los dos temas. El verde de «aprobada» va oscuro y el verde azulado de «finalizada» claro: con la misma luminosidad no se distinguían. **Si cambias uno, vuelve a validarlos** (y los del tema claro en `informe_estadisticas.py`).
  - El mapa de horas va en `--graf-calor` (el verde de «aprobada», más claro en oscuro, para que sus pasos se distingan).
  - El morado de «Fuera del horario» y el azul de las recibidas no se distinguen con daltonismo (ΔE ~1): desde el 2026-11-10, «Fuera del horario» no se dibuja en el gráfico por día, mes o año (va en su globo y en su tabla). Antes, al encenderla se apagaban las recibidas, y eso confundía.
- **Dato de la API para el mapa de horas:** `aprobadas_por_hora` (día ISO y hora de Panamá, solo las casillas con alguna) en `/solicitudes/estadisticas`, de `RepositorioSolicitud.aprobadas_por_hora`. Hasta el 2026-11-06 era `finalizadas_por_hora`. Lo prueba `test_horario.py`.
- **Horario laboral espejado:** `HORA_INICIO_LABORAL` / `HORA_FIN_LABORAL` en `calculos.ts`, contra `core/horario.py` en `test_constantes_iguales_en_el_frontend`. El mapa va por horas enteras: la casilla de las 15 es fuera salvo las 15:00 en punto (`horarioDeCasilla`, «borde»).
- Los cálculos sin React (`calculos.ts`) tienen sus pruebas en `calculos.test.ts`. Las capturas se hacen con datos de ejemplo (guion en el scratchpad de la sesión).

## Revisión del código del 2026-11-02
- **Documentos servidos con el tipo de su formato:** se guarda y se sirve el MIME del formato verificado por estructura (`mime_del_formato`, `almacenamiento.py`); libmagic queda como control cruzado en el log.
  - Antes se guardaba lo que dijera libmagic. Un «PDF» con HTML delante (se admite contenido antes de `%PDF-`) quedaba como text/html, y el visor lo pintaba como una página del mismo origen.
  - El visor arma además el blob del PDF como application/pdf.
  - Lo prueba `test_un_pdf_con_html_delante_se_guarda_y_sirve_como_pdf`.
- **bcrypt en un hilo** (login, cambio y restablecimiento de contraseña, alta local): cada intento congelaba el worker ~0,25 s.
- **La cola de correos para en el primer error del SMTP:** con el servidor caído, cada despacho insistía con toda la cola, cada intento con una conexión de la BD tomada hasta que vencía el SMTP (`test_con_el_correo_caido_el_despacho_no_insiste_con_toda_la_cola`).
- **Agencias con más solicitudes:** agrupa por agencia con su nombre de hoy. Antes partía en dos filas a una agencia renombrada.
- **Búsquedas de las bandejas y de la bitácora:** «%» y «_» se buscan tal cual (`icontains(..., autoescape=True)`).
- **Usuarios únicos sin distinguir mayúsculas al crearlos** (`RepositorioUsuario.nombre_en_uso`): el login no las distingue, y «Agencia.Uno» y «agencia.uno» eran la misma cuenta para quien entra.
- **Expediente al día ante un 409:** si otra persona ya decidió o finalizó, `releerSiCambio` (`api/solicitudes.ts`) vuelve a pedir el expediente en vez de dejar los botones viejos.
- **Usuarios:** si la acción sale bien pero falla la recarga de la lista, ya no dice «No se pudo agregar».
- **Documentación de la DTI a la 0.4:** el 01, el 04 (sección O, RN-89 y RN-90, sin renumerar), el 06, el 08 y el 09 (con «Cómo leer las estadísticas» y su figura). El 00 y el 03 siguen en la 0.3; el 02, el 05 y el 07, en la 0.2.

## Cambios del 2026-11-06 (revisión `d8c3f1a6b294`)
Pedido del usuario: que el puesto también verifique impedimentos, plazos de 72 h, «Observaciones» en el formulario, estadísticas por día, mes y año y el horario contado con UCVMM.
- **El puesto de control verifica los impedimentos en SIMPLUS antes de finalizar** (obligatoria). Funciona como la de UCVMM y se guarda aparte, para que una no pise a la otra:
  - Columnas `solicitud_tripulantes.con_impedimento_puesto` y `solicitudes.impedimentos_puesto_*`; eventos `impedimentos_puesto` e `impedimentos_puesto_corregidos` (internos, en `_EVENTOS_INTERNOS`).
  - `POST /solicitudes/{id}/impedimentos-puesto` (`registrar_impedimentos_puesto`, con `_para_puerto`). En la bitácora, `IMPEDIMENTOS_REGISTRADOS` con `etapa`, sin valor nuevo en el tipo.
  - Las dos verificaciones comparten `_verificar_impedimentos`, parametrizado por `_EtapaVerificacion`. En el frontend, `useVerificacionImpedimentos(..., etapa)`, con una instancia por etapa en `PaginaDetalleSolicitud`.
  - `finalizar` responde 409 sin ella. Con impedimento igual se finaliza, como UCVMM puede aprobar: el aviso de confirmación nombra a esas personas para que el comentario diga qué pasó.
  - El puesto ve lo que marcó UCVMM como referencia («Con impedimento (UCVMM)»), pero marca lo suyo desde cero.
  - Las aprobadas pendientes al desplegar la piden antes de finalizarse; las finalizadas antes quedan sin ella.
- **Plazos de 72 h:** `PLAZO_CORRECCION_DIAS` = 3 (72 h desde la devolución) y `DIAS_GRACIA_FINALIZACION` = 2 (hasta las 23:59 del segundo día después de la operación: 72 h desde que empieza ese día). Antes, 2 y 1 (48 h).
  - Se calculan al devolver y al aprobar: lo ya abierto conserva su plazo.
  - En el servidor, un `backend/.env` con los valores viejos manda sobre los nuevos.
- **Formulario de la agencia:** «Observaciones para UCVMM» pasa a ser «Observaciones».
- **Fuera del horario por la aprobación de UCVMM**, con las 15:00 dentro (ver la reunión del 2026-10-30, arriba).
  - Renombra en la API de estadísticas: `aprobadas_fuera_horario`, `aprobadas_por_hora` y, en `operaciones_fuera_horario`, `aprobada_en` y `aprobada_por` (la foto del historial).
  - Sale `por_puesto[].fuera_horario`: medía al puesto.
- **Estadísticas por día, mes y año:** `por_dia` (los últimos 31 días del periodo), `por_mes` (hasta 12; antes, siempre los últimos 6) y `por_anio` (hasta 10), con filas `{periodo, …}` (antes `mes`).
  - Salen de `RepositorioSolicitud.serie_diaria`, agrupada en el servicio (`_serie`).
  - En la pantalla, «Ver por: Día · Mes · Año» (`GraficoTiempo`, antes `GraficoMeses`). Por día, en el celular, se desplaza de lado y arranca en los días más recientes.
- **Documentación de la DTI, juego 0.5:** cada documento que cambió subió un número sobre el que tenía.
  - El 01, 04 (sección P, RN-91 a RN-94, sin renumerar), 06, 08 y 09 pasan a la 0.5.
  - El 00 y el 03, a la 0.4. El 00 trae además la tabla de versiones al día.
  - El 02, 05 y 07, a la 0.3.
  - Se redibujaron los BPMN 01, 05 y 06 y el diagrama de estados.
  - `diagramas.py` (scratchpad) quedó al día con el BPMN 05.

## Auditoría de rendimiento y disponibilidad (2026-11-08, revisión `e7b2d5a9c4f1`)
Pedido del usuario: revisar todo en busca de fallos, saturación y lo que estorbe la disponibilidad con el tiempo.
- **Conexiones con la BD por proceso** (`BD_POOL` 5 + `BD_POOL_EXTRA` 10, `core/config.py`). Antes eran 10 + 20 fijos: con los 4 workers de `start-backend-prod.bat` se podían pedir 120 y PostgreSQL admite 100. **N workers × (BD_POOL + BD_POOL_EXTRA) tiene que quedar por debajo de `max_connections`.**
- **Topes de PostgreSQL por conexión** (`_ajustes_de_conexion`, `infrastructure/database.py`, solo con asyncpg): `statement_timeout` (`BD_TIEMPO_MAXIMO_CONSULTA`, 60 s) e `idle_in_transaction_session_timeout` (`BD_TIEMPO_MAXIMO_INACTIVA`, 300 s). Alembic usa su propio motor y no los tiene.
- **La BD caída, lenta o sin conexiones libres responde 503 con `detail` y `Retry-After`** (manejadores en `main.py`): pool agotado tras `BD_POOL_ESPERA` s, `OperationalError` / `InterfaceError`, conexión invalidada, consulta cancelada (SQLSTATE 57014) y `ConnectionError`. Un SQL mal armado sigue siendo 500 (`_es_falla_de_disponibilidad`). Lo prueba `tests/test_disponibilidad.py`.
- **`/api/health` consulta la BD** (`SELECT 1`, como mucho 3 s) y responde 503 sin ella. Es pública: reusa la respuesta 5 s para no cargar la BD.
- **Filtros por fecha como rango de instantes** (`entre_fechas_panama`, `core/horario.py`): bandejas, estadísticas y bitácora. **No vuelvas a filtrar con `date(timezone(...))` sobre la columna**: así PostgreSQL no usa el índice y recorre la tabla entera. Para agrupar por día (`_fecha_panama`) sí se usa.
- **Índices nuevos:** `solicitudes.created_at` (periodo de las estadísticas), `solicitudes.puesto_finalizacion_id` (FK sin índice: borrar un puesto recorría la tabla) y `audit_logs (accion, creado_en)`.
- **Las bandejas no cargan a los tripulantes:** `RepositorioSolicitud.alertas_de` cuenta en SQL los vencidos y si hay alguno restringido, con la regla de `_vencimientos_tripulante`; el expediente los sigue contando en Python. **Si cambias una, cambia la otra**: lo prueba `test_la_bandeja_cuenta_las_alertas_como_el_expediente`. Antes cada página traía hasta 100 × 30 filas solo para contarlas.
- **La campana hace una consulta por fuente** (`pendiente_en`: conteo y plazo más próximo juntos). Antes eran dos, cada minuto por pestaña abierta.
- **Correos:** cada envío espera al SMTP como mucho `MAIL_TIEMPO_ESPERA` s (20; antes los 60 de aiosmtplib), y hay **un solo despacho a la vez por proceso** (`_despachando` / `_otra_vuelta`, `cola_correos.py`): los que llegan mientras otro despacha le piden otra vuelta y terminan sin tomar una conexión. Entre workers los sigue separando SKIP LOCKED (la prueba llama a `_despachar_lote`).
- **Al apagar**, el ciclo de vida cierra el pool (`motor_bd.dispose()`).
- **Frontend:**
  - El formulario y el expediente (~40 KB cada uno) se cargan al entrar a su página (`lazy` en `App.tsx`, con un `Suspense` alrededor de las rutas). El paquete inicial bajó de 440 KB a 357 KB; lo que queda es sobre todo React, el router y axios.
  - La verificación del QR y el cambio de contraseña siguen en el paquete inicial: son chicas, y la primera la abre el público en el teléfono (diferida, además, el E2E pulsaba Tab antes de que apareciera).
  - **Cerrar sesión** borra primero la sesión del navegador y después avisa al servidor con el token que tenía (`cerrarSesion`, `ProveedorAutenticacion`). Al revés, «Cerrar sesión» navegaba a /login con el usuario todavía cargado y la campana consultaba /pendientes con el token ya revocado (401 en la consola). Lo prueba `e2e/sesion.spec.ts`, que falla con el código anterior.
  - `mensajeDeError` (`utils/errores.ts`) dice «No hay conexión con el servidor…» sin respuesta (red o VPN caída), «tardó demasiado» con el tiempo agotado y «no está disponible» con un 502/503/504 sin motivo. Antes cada pantalla mostraba su texto genérico.
- **Docker:**
  - Imagen del backend en dos etapas, sin compiladores (todas las dependencias traen binario para Linux; instalar build-essential detrás del proxy del SNM trancaba el build más de 13 min): la final corre como `argonavis` (uid 10001). Un volumen `documentos` creado antes hay que pasárselo una vez (README → Producción).
  - `UVICORN_WORKERS` (entrypoint, 1 por defecto; el compose pone 2) y `PYTHONUNBUFFERED`.
  - `verificar-despliegue.sh` (raíz): revisión de un despliegue con Docker, solo lectura salvo el freno del login (intentos con un usuario inexistente) y un archivo vacío en el volumen. Si agregas algo que el despliegue necesite (una variable, un servicio, un puerto), súmale su chequeo.
  - El servidor de pruebas (Rocky 9) no llega a Docker Hub (el firewall corta `auth.docker.io`): usa el espejo `mirror.gcr.io` en `/etc/docker/daemon.json` (`registry-mirrors`).
  - nginx resuelve `backend` en cada petición (`resolver 127.0.0.11` y `proxy_pass $api`): con el nombre fijo lo resolvía una vez al arrancar y, si el backend se recreaba con otra IP, respondía 502 hasta reiniciarlo.
- **Revisado y sin cambios:** LDAP, bcrypt y el PDF ya corren en hilos; las subidas tienen su propio tope de 300 s en el cliente; temporizadores y escuchas del frontend se limpian; las relaciones del ORM cargan en lote (`selectin`), sin N+1 en las bandejas.
- **Documentación de la DTI, juego 0.6:** el 06 (configuración, Docker, salud, índices) y el 08 (evidencias y pendientes) pasan a la 0.6; el 00, a la 0.5, por su tabla de versiones. Los demás no cambian. `v06.py` (scratchpad) hace los reemplazos en los generadores, como `v05.py`.

## «Vibe coder vs. desarrollador» (2026-11-08)
El usuario pidió revisar el proyecto contra cinco puntos:
- **No se cae con 100 usuarios:** prueba de carga `backend/tests/carga.py` (no la corre pytest). Levanta el backend con 2 procesos contra una BD temporal y pone a N usuarios a pedir algo cada 1 a 3 s.
  - Con 100 usuarios: 2.683 pedidos sin un error; mediana de ~1 s y techo de ~29 pedidos por segundo, con las 30 conexiones al tope (detalle en README → «Capacidad y disponibilidad»).
  - Consultas por pedido (en proceso, sin red): campana 8 a 9, bandejas 11 a 20, expediente 26. De esas, 6 son para saber quién pide.
  - Si un día hace falta más capacidad, ahí está el margen (pendiente 16). No se tocó: es código de autenticación y el uso real (~8 pedidos por segundo con 100 usuarios) está lejos del techo.
- **useEffect:** 34 en toda la app y como mucho 3 por componente. El lint exige las reglas del compilador de React y, además, `no-deriving-state-in-effects` y `void-use-memo` (`eslint.config.js`).
- **Permisos en la BD:** regla 19 de Seguridad.
- **Leer la traza:** el código de pedido (Errores, arriba).
- **Claves en el frontend:** ninguna. El `.env` nunca entró al repositorio (revisado en todo el historial), el frontend solo lee `VITE_API_URL` y ninguna clave del servidor aparece en el paquete compilado.

## Los 20 puntos de «sitio hecho a la carrera» (2026-11-08)
El usuario pidió revisar una lista de señales de sitios web públicos. ARGO NAVIS es un sistema **interno**: lo de buscadores no aplica, y lo de rastreadores aplica al revés.
- **Hecho:** página 404 propia (`PaginaNoEncontrada`; antes una ruta desconocida llevaba a las bandejas sin avisar), `<noscript>`, meta description, `noindex` en tres capas (`robots.txt`, la etiqueta robots de `index.html` y `X-Robots-Tag` en nginx y en `_CABECERAS_SPA`), source maps apagados de forma explícita (`vite.config.ts`) y la vigilancia de la consola en el E2E (`e2e/base.ts`: un `console.error`, un error sin atrapar o un 5xx hacen fallar la prueba; los 4xx no).
- **Ya estaba:** título por página (`useTituloDocumento`), un solo H1 por página, `alt` en las imágenes, `lang="es"`, favicon, paquete inicial partido (357 KB; exceljs y docx-preview se cargan solo al previsualizar).
- **No aplica, a propósito:** sitemap, tag canónico, OG image, datos estructurados y `llms.txt` (son para salir en buscadores y en IA; aquí nada debe indexarse). Vite y React son la decisión del proyecto. **No los agregues.**
- Los avisos que quedan en la consola de Firefox (contraseña en página insegura, `crypto.randomUUID` en su visor de PDF) son por servir en HTTP: los quita el HTTPS (pendiente 1).

## Sectores, supervisión y «pasajeros» (2026-11-10, revisiones `c1f7a3e9d2b6` y `d5b8e2f1a9c3`)
Pedido del usuario: dos sectores de UCVMM que no ven lo del otro, roles de supervisión de solo lectura, y «a los marinos tripulantes ahora se les llama pasajeros». Decisiones del usuario: un rol UCVMM con el sector asignado (no un rol por sector), supervisores con todo en solo lectura, un buzón por sector y el documento «Lista de Tripulantes» con su nombre oficial.
- **Sectores** (`sectores`, sembrados: Sector Pacífico y Sector Atlántico). Cada puesto es de uno (`puestos_control.sector_id`, obligatorio). La agencia sigue eligiendo solo el puesto, y de ahí sale el sector.
  - Los funcionarios se asignan en `usuarios_sectores` (Catálogos → Sectores), como los puestos. Uno puede estar en los dos (vacaciones, refuerzos).
  - El sector **no se guarda en la solicitud**: sale del puesto. Mover un puesto de sector mueve también sus solicitudes abiertas (la pantalla lo confirma). Así, al desplegar, todo quedó en el Pacífico (como funcionaba) y el administrador pasa a Atlántico sus puestos y sus usuarios.
  - El alcance vive en `ContextoAcceso` (`puestos_de_sectores`, `ve_todos_los_sectores`, `alcance_ucvmm`, `puede_revisar_esta`). **Si agregas una bandeja, una consulta o una estadística de UCVMM, filtra por ahí**: bandeja de revisión, campana, expediente, transiciones (`_para_revision`) y estadísticas ya lo hacen. Lo prueba `tests/test_sectores.py`.
  - El aviso de cada solicitud nueva o corregida va al buzón del sector (`sectores.correo`); sin buzón, al general (`CORREO_UCVMM`).
  - El sector se muestra al SNM (`sector_nombre` en la bandeja y el expediente; a la agencia le llega nulo). En las tarjetas, solo a quien ve los dos.
- **Estadísticas por sector:** UCVMM y el supervisor de sector ven las de sus sectores; el Administrador y el supervisor general, las de los dos, con un selector («Todos · Sector Pacífico · Sector Atlántico», `sector_id`). El uso del sistema (`/admin/stats`, totales de todo y las agencias de los dos sectores) queda solo para ellos. La exportación lleva el sector en el encabezado y en el nombre del archivo (`…-sector-atlantico-…`).
- **El rol «Sector Pacífico» pasó a llamarse «UCVMM».** El permiso conserva el código `T-PROCESAR-PACIFICO` (lo usan el backend y el frontend): no lo renombres.
- **«Pasajeros» en lugar de «tripulantes»**, en todo lo que ve el usuario: pantallas, mensajes de error, correos, PDF y las descripciones del catálogo (migración `d5b8e2f1a9c3`).
  - **En el código, la API y la BD sigue diciendo `tripulante(s)`** (`solicitud_tripulantes`, `cantidad_tripulantes`, `tripulantes` en el JSON, `TarjetaTripulante`): cambiarlos rompería el contrato con datos en producción. No los renombres.
  - El documento del Formulario No. 3 conserva su nombre oficial, «Lista de Tripulantes», hasta que UCVMM cambie el formulario.
  - Los ids de las tarjetas del formulario (`tripulante-${clave}`) no se ven: siguen igual (los usa el desplazamiento y la E2E).

## Dependencias: de dónde salen y fijadas (2026-11-10)
Pedido del usuario: «¿las librerías son descargadas, nada se saca de internet?». Revisado a fondo:
- **En ejecución no se descarga nada.** El frontend lleva sus librerías en el paquete compilado (sin CDN: sus letras, Archivo, Public Sans e IBM Plex Mono, van en el paquete desde el 2026-11-11) y la CSP solo deja cargar lo del propio servidor. El backend habla solo con PostgreSQL, el AD (ldap3) y el SMTP (aiosmtplib). Los correos llevan el logo incrustado (`cid:`). Las URLs que aparecen en el paquete compilado son espacios de nombres XML de Office y enlaces en mensajes de error, no descargas.
  - Única excepción, solo en desarrollo: `/api/docs` (Swagger de FastAPI) se carga desde un CDN. En producción está apagado.
  - requests y httpx están en el venv de desarrollo por pip-audit y las pruebas: no entran en producción.
- **Al instalar sí se descarga, y siempre lo mismo:**
  - **Python: se instala desde `backend/requirements.lock`**, con `pip install --require-hashes -r requirements.lock`; en Docker, además, `--only-binary :all:` (todas traen rueda para Linux y 3.12).
    - Trae todas las librerías (directas e indirectas) con la versión exacta y el hash, para Linux y Windows (`uv pip compile --universal`). `requirements.txt` es lo que se edita.
    - **No vuelvas a instalar desde `requirements.txt`:** las 36 indirectas tomaban la última versión de PyPI en cada build.
    - Al cambiar `requirements.txt`, regenera el bloqueo (el comando está al principio del archivo; `uv` está en `requirements-dev.txt`). Para subir una indirecta, `-P nombre`.
    - `tests/test_dependencias.py` falla si los dos archivos no coinciden, si falta un hash o si el Dockerfile deja de instalar desde el bloqueo.
  - Node: `package-lock.json` (con hashes); en un servidor, `npm ci`, nunca `npm install`.
  - **Imágenes Docker con la versión exacta:** `python:3.12.16-slim-trixie` (`ARG IMAGEN_PYTHON` en el Dockerfile), `node:24.22.2-alpine3.24`, `nginx:1.31.8-alpine` y `postgres:15.19-alpine3.24`, también en la CI. Con `nginx:alpine` o `python:3.12-slim`, cada build traía lo último sin que nadie lo decidiera. La misma prueba falla con una etiqueta flotante o si la CI usa otro PostgreSQL. Para actualizar, cambia la etiqueta.
- **La auditoría revisa el bloqueo** (`pip-audit -r requirements.lock --require-hashes`, en la CI y en el equipo). Con `requirements.txt` solo veía las directas.
  - Al cambiarla aparecieron 39 avisos en pillow 12.3.0 (la usa reportlab) y 4 en pyasn1 0.6.4 (la usa ldap3), que no se veían. Se subieron a 13.0.0 y 0.6.5, con su mínimo en `requirements.txt`.
- **Servidor sin salida a internet:**
  - Docker: `empaquetar-sin-internet.sh` (en un equipo con internet y Docker) guarda las imágenes ya construidas y el código del commit; en el servidor, `docker load` y `docker compose up -d --no-build --pull never`. Por eso el compose les da nombre fijo (`argonavis-backend`, `argonavis-frontend`, los mismos que ya ponía).
  - Windows: `pip download` del bloqueo, más setuptools (win-unicode-console viene sin compilar), e instalación con `--no-index --find-links`. Probado el 2026-11-10. Detalle en README → Producción.
- Las acciones de la CI siguen fijadas por etiqueta (`@v4`), no por commit: sin los PR de Dependabot nadie las actualizaría, y solo corren las pruebas.

## Recursos y topes (2026-11-10)
Pedido del usuario: «¿no hay riesgo de sobrecarga de recursos, procesos que afecten la operación?», y después: «¿por qué 200 MB si el máximo es 2 MB por archivo?», «los contenedores deben estar limitados» y «¿el respaldo nocturno ralentiza todo?». Lo prueba `tests/test_recursos.py`.
- **Tope del cuerpo de cada petición** (`TopeDelCuerpo`, `main.py`): 1 MB en la API (`TOPE_CUERPO_MB`) y `TOPE_CUERPO_ENVIO_MB` (345 desde el 2026-11-14; antes 285 y 283) al crear y corregir una solicitud (`_RUTA_DE_ENVIO`). Es lo más que pesa un envío válido: 30 pasajeros × 5 documentos (uno restringido, con la Visa) + 2 de la solicitud (el Formulario No. 3 y la Lista de Tripulantes) + 20 adicionales, de 2 MB, más 1 MB.
  - FastAPI lee el cuerpo **antes** de comprobar la sesión y el rate limit. Sin tope, cualquiera, sin cuenta, hacía leer al backend cientos de MB por petición, también en el login (un JSON va entero a la memoria). Con Content-Length se corta sin leer; sin él, se cuenta lo que llega.
  - nginx tiene los mismos: `client_max_body_size 1m` en `/api/` y un `location` anidado para los envíos, con el 413 en JSON. Antes eran 200 MB para todo `/api/`, que encima no alcanzaban para un envío máximo.
  - Si el catálogo pide más documentos, `test_el_tope_de_un_envio_alcanza_para_el_catalogo` falla: sube `MAX_DOCUMENTOS_*` (`solicitud_service.py`) y nginx. `test_nginx_tiene_los_mismos_topes_que_el_backend` compara los dos, y la CI corre `nginx -t` con la imagen de producción.
- **Topes por cuenta:** `LIMITE_EXPORTACIONES_POR_HORA` (30) y `LIMITE_PDF_POR_HORA` (120), como el de los envíos.
- **Trabajos pesados con turno** (`en_hilo_con_tope`, `infrastructure/trabajo_pesado.py`): el PDF y las exportaciones, como mucho `TRABAJOS_PESADOS_A_LA_VEZ` (2) por proceso. Los endpoints sueltan antes la conexión (`await sesion.commit()`: los datos ya están leídos y `expire_on_commit=False`). **Un trabajo nuevo de cientos de ms de CPU va por ahí**, no por `asyncio.to_thread`.
- **reportlab sin ASCII85** (`rl_config.useA85 = 0`, `pdf_autorizacion.py`): ~15 % menos de CPU y PDF más chicos.
- **Subidas al disco desde los 64 KB** (`MultiPartParser.spool_max_size`, `main.py`): Starlette dejaba en memoria cada archivo de hasta 1 MB, y un envío máximo ocupaba ~140 MB del proceso. Si Starlette deja de usar ese atributo, `test_los_archivos_de_un_envio_pasan_al_disco_temporal` falla.
- **Disco:** con menos de `ESPACIO_MINIMO_LIBRE_MB` (1024) libres en el disco de los documentos, no se reciben archivos (507 y error en el log). Es el mismo disco de PostgreSQL y de los respaldos.
- **Topes de cada contenedor** (`docker-compose-prod.yml`, ajustables en el `.env`): memoria (`POSTGRES_MEMORIA` y `BACKEND_MEMORIA`, 1g; `FRONTEND_MEMORIA`, 256m), CPU del backend (`BACKEND_CPUS`: tantos como workers, o 1.5 en una VM de 2 núcleos, como la de pruebas), `pids_limit` en los tres y `shm_size` de 256 MB en PostgreSQL.
  - Medido con 100 usuarios: el backend usa ~410 MB (~150 por proceso de uvicorn y ~110 el maestro).
  - Si un proceso de uvicorn se pasa, Docker lo corta y uvicorn lo levanta. `verificar-despliegue.sh` muestra el uso contra el límite y los procesos caídos.
- **Respaldo incremental** (`backup.sh`). La base, como antes. Los documentos, una copia por día:
  - se enlaza la copia anterior (`cp -al`), se copia lo nuevo (`cp -a -u --remove-destination`, que no escribe sobre la anterior) y sale lo que ya no está en el volumen;
  - con `nice`/`ionice`, `flock` y archivos parciales que no quedan con nombre de bueno;
  - antes era un `.tar.gz` de todo, cada noche, ×14.
  - **No vuelvas al tar de todo:** con los años llena el disco que comparte con PostgreSQL.
  - Sirve porque los documentos no se modifican (reemplazar es guardar otro). Si eso cambia, revisa el respaldo.
  - La restauración está en el README, probada con una base temporal (dropdb, createdb y psql con `ON_ERROR_STOP`).
- En pantalla, «Máximo permitido: 2 MB por archivo» en las tres secciones donde se adjunta (la de adicionales no lo decía) y en el aviso al elegir uno más pesado.

## Cambios del 2026-11-11 (revisiones `a8d4f2c6e913` y `c6f1d9a3b724`)
Pedido del usuario: otros documentos para técnicos, supernumerarios y superintendentes; nada de unidades internas en lo que ve la agencia; la solicitud aprobada fuera del horario con su costo, también para la agencia; y una forma de buscar solicitudes de cualquier año. Decisiones del usuario: en Embarque, lo de Desembarque sin el boleto; el nombre neutro es «Servicio Nacional de Migración» («SNM» en espacios cortos); el aviso del costo va en pantalla, correo y PDF; y la búsqueda es una página aparte, «Consulta histórica», solo para el SNM.
- **Documentos de técnicos, supernumerarios y superintendentes** (cuarta excepción del catálogo, ver «Reglas»):
  - Desembarque: Carta de Responsabilidad (Form. No. 7), Generales de pasaporte, Contrato de Trabajo (documento nuevo, `DOC-CONTRATO-TRABAJO`, sin descripción: el pedido no pone condiciones) y, **opcional**, la Copia de Boleto Aéreo. Embarque: los tres primeros, sin boleto. El militar y los demás trámites, como estaban.
  - `tramite_documentos.rangos_opcional` (nulo = obligatorio): los rangos para los que la fila es opcional. Va en otra columna y no en otra fila porque `uq_tramite_documento` admite una fila por documento y trámite.
  - `solicitud_casillas.obligatoria` guarda la foto. Una casilla opcional sin archivo no es faltante: no bloquea el envío, no cuenta en «N de M adjuntos» y en el expediente dice «Opcional · no se adjuntó». En el formulario lleva el rótulo «Opcional» y su campo de archivo se llama «Adjuntar … (opcional)».
  - `opcional_para` (`tramite_service.py`) está espejado en `opcionalPara` (`checklist.ts`), con su caso en `espejo/checklist.json` (`opcionales`).
- **Nombre neutro para la agencia:** a la agencia no se le nombran las unidades internas (UCVMM, los sectores): ve «Servicio Nacional de Migración».
  - Dónde: los avisos «En revisión por…» y «Aprobada … por…» del expediente, la corrección, la página pública del QR, la descripción de `index.html`, el mensaje de agencia desactivada, el autor de los pasos en el historial y en la campana (`INSTITUCION` y `_AUTOR_PARA_AGENCIA`, `solicitud_service.py`), el PDF de la agencia (encabezado «Sección de Autorizaciones Marítimas» y «Aprobada por») y los correos de devolución y de negación.
  - Lo del SNM no cambia: sus pantallas, la copia interna del PDF («Nombre (UCVMM)»), el correo al puesto y los informes siguen diciendo UCVMM.
  - **Un texto nuevo que vea la agencia no nombra a UCVMM ni a los sectores.** Lo prueban `test_ciclo_completo` (expediente, bandeja, campana y los cuatro correos de la agencia, con una expresión regular) y el E2E (`sinUnidadesInternas`, en cada pantalla de la agencia: el texto y también los atributos, como `title` o `placeholder`).
  - Los textos de las pantallas del SNM viajan en el mismo JavaScript: a la agencia no se le muestran, pero no son un secreto.
- **Fuera del horario, también para la agencia, con su costo migratorio:**
  - `COSTO_FUERA_DE_HORARIO` (B/.20.00). Se guarda en `solicitudes.costo_fuera_de_horario` al aprobar (foto: cambiar el monto no toca lo ya aprobado). Con 0 no hay costo, pero igual se avisa. Las aprobadas antes de la revisión quedan sin monto.
  - `fuera_de_horario` y `costo_fuera_de_horario` («B/.20.00», `texto_costo`) llegan a todos, en las bandejas y en el expediente.
  - Pantalla: la insignia morada con el monto en la bandeja y en la cabeza del expediente, y un aviso morado en el banner de aprobada y de finalizada (`AvisoFueraDeHorario`).
  - Correo de aprobación (a la agencia y al puesto): dos líneas, «Aprobada fuera del horario laboral (…)» y «Costo migratorio: …» (`aviso_fuera_de_horario`, `core/horario.py`). PDF: un recuadro morado bajo el estado, en las dos copias.
  - `TEXTO_HORARIO` está espejado en `TEXTO_HORARIO_LABORAL` (`presentacion.ts`), armado con las horas de `calculos.ts` (`test_constantes_iguales_en_el_frontend`).
  - Lo prueba `test_aprobada_fuera_del_horario_lleva_el_costo` (`tests/test_horario.py`), con el reloj simulado.
- **Consulta histórica** (`/historico`, `PaginaConsultaHistorica`): todas las solicitudes que ve el personal del SNM, de cualquier año, con filtros que las bandejas no tienen y exportación a Excel. La agencia sigue con su bandeja.
  - API: `GET /solicitudes/historico`, `/historico/opciones` (agencias, puestos de su alcance y trámites, también los desactivados) y `/historico/exportar`. Van **antes** de `/{solicitud_id}` en el enrutador: si no, «historico» se leería como un id.
  - Alcance: el de `puede_ver`, sin la vía de la agencia (`_alcance_historico` → `AlcanceSnm` en `FiltrosBandeja`). El Administrador y el supervisor general, todo; UCVMM y el supervisor de sector, los puestos de sus sectores; el puesto de control, sus puestos desde que se aprueban. **Si cambias `puede_ver`, cambia `_alcance_historico`.**
  - Filtros (`ConsultaHistorica`): texto, pasajero (nombre, apellido, los dos juntos o pasaporte, con un EXISTS sobre `solicitud_tripulantes`), agencia, puesto, trámite, estado, fecha de envío o de la operación con desde y hasta (y un atajo por año, desde `PRIMER_ANIO`) y «solo aprobadas fuera del horario».
  - Los filtros van en la URL, sin sumar entradas al historial: se puede recargar o compartir la búsqueda. La lógica sin React está en `consultaHistorica.ts`, con sus pruebas.
  - En el celular, agencia, puesto, trámite y fechas van plegados en «Más filtros». El sector de cada fila se muestra solo a quien ve los dos.
  - Excel (`core/informe_historico.py`): la identidad del informe de estadísticas, una fila por solicitud, el estado con el color de su insignia, filtros de Excel y encabezado fijo. Hasta `MAX_FILAS_EXPORTACION` (5000): si hay más, el archivo lo dice. Lleva el tope `LIMITE_EXPORTACIONES_POR_HORA` y va por `en_hilo_con_tope`.
  - Se entra por el menú y por un botón en las bandejas del SNM (`PERMISOS_PERSONAL_SNM`, `hooks/usePermisos.ts`, espejo de `es_personal_snm`).
  - Lo prueban `tests/test_historico.py`, `consultaHistorica.test.ts` y el E2E `flujo-completo.spec.ts`.
- **Navegación y versión nueva** (pedido del usuario: «aunque cierre sesión y recargue, me mantiene en la última vista», «en consulta histórica no hay botón de volver al inicio» y el aviso de la versión nueva):
  - **Después de cerrar la sesión se entra por el inicio.** Antes, la guardia de las rutas mandaba al login recordando la página (`state.desde`), y el navegador conserva ese estado aunque se recargue. Ahora `ProveedorAutenticacion` lleva `sesionCerrada` (Salir, el aviso de inactividad, el cierre por inactividad, otra pestaña) y `RutaPrivada` no recuerda la página. Un enlace abierto sin sesión (el de un correo) y el `?siguiente=` del 401 siguen llevando a su página. Lo prueba `e2e/sesion.spec.ts` («se vuelve a entrar por el inicio»), que falla con el código anterior.
  - **«Volver» en la consulta histórica** (al inicio) e **«Inicio» arriba del menú** (salvo el SysAdmin, cuyo inicio es Usuarios). El escudo de la cabecera ya llevaba al inicio, pero no se notaba.
  - **El «Volver» del expediente regresa a donde se abrió:** la consulta con sus filtros y su página, las estadísticas o la bandeja con su pestaña. Va en el estado de la navegación (`estadoParaVolver` / `destinoDeVolver`, `utils/volver.ts`, solo rutas propias); sin él (correo, campana), al inicio. **Un enlace nuevo al expediente lleva su `state`.**
  - **Aviso de versión nueva** (`VigilanteVersion`, `utils/version.ts`): cada 5 min con la pestaña a la vista y al volver a ella (como mucho una vez por minuto) pide `/` sin caché y compara los archivos de `/assets/` de su index.html con los de la página cargada (llevan hash: no hay número de versión que subir). Si cambiaron, un aviso «Versión nueva» que no se cierra solo, con «Recargar»: la recarga la decide el usuario, que puede estar a mitad de un formulario. Una vez por versión. En desarrollo no revisa (Vite no empaqueta).
- **En las celdas de una tabla, `overflow-wrap: break-word`, no `anywhere`:** con `anywhere` la columna se encoge al mínimo y parte palabras normales («KENSINGTO-N»). `anywhere` sigue siendo lo indicado en los bloques de texto libre.
- **Vitest y la letra de unidad (Windows):** si todas las pruebas fallan con «Cannot read properties of undefined (reading 'config')», la carpeta de trabajo llegó como `c:\…` en minúscula y Vitest cargó dos copias de sí mismo. Se corre desde `C:\…`.

## Cambios del 2026-11-13 (revisiones `e5c2a8f1d376` y `f8b3d1e6a492`)
Pedido del usuario: a la agencia no mostrarle su rol; el Cambio de Puerto dentro de «Nueva solicitud» y no como trámite aparte; y el Formulario No. 3 obligatorio en todos los trámites. Decisiones del usuario: con cambio de puerto finaliza el puesto nuevo y el primero solo consulta; el «Sí» no pide documentos extra; la pregunta va en todos los trámites; el Form. 3 se pide para cualquier rango y convive con la Lista de Tripulantes.
- **Cabecera de la agencia:** su nombre y su agencia, sin el rol (`MenuCabecera`). El personal del SNM sigue viendo su rol.
- **Cambio de puerto** (`solicitudes.puesto_destino_id` / `puesto_destino_nombre`, foto como `puesto_nombre`; nulo = sin cambio):
  - En «Datos del trámite» de Embarque y Desembarque (`tipos_tramite.permite_cambio_puerto`, segundo lote): «¿Cambio de puerto?» (No por defecto) y, con «Sí», «Nuevo puesto de control» con los puestos activos **del mismo sector** que el elegido, sin él (`puestosParaCambio`, `validacionFormulario.ts`). `/catalogos/puestos` trae el `sector_id` de cada puesto, sin el nombre.
  - Va al final de «Datos del trámite», en su recuadro, con el nuevo puesto al lado de la pregunta (pedido del usuario). En los demás trámites no se ofrece, y un nuevo puesto que llegue igual se descarta.
  - El backend lo vuelve a validar (`_validar_cambio_de_puerto`): activo, distinto y del mismo sector. Si el nuevo puerto es del otro sector, va una solicitud nueva y esta vence sola. **El mensaje no nombra los sectores**: lo lee la agencia.
  - El sector, y con él UCVMM, sale siempre de `puesto_control_id`.
  - **El puesto que finaliza es el nuevo** (`Solicitud.puesto_autorizado_id` / `_nombre`, y `puesto_autorizado()` en SQL): su bandeja, su campana (`FiltrosBandeja.puestos_autorizados`), el correo de aprobación, `_es_del_puerto` y `finalizar`. El primero la ve (`_la_ve_como_puesto` en `puede_ver`, y la consulta histórica) pero no la finaliza: el 403 dice quién la finaliza.
  - El filtro «Puesto» de la consulta histórica encuentra los dos; las estadísticas por puesto cuentan el autorizado.
  - Se ve como «Balboa → Rodman» (`textoPuestos`, `presentacion.ts`) en las tarjetas, la consulta y su Excel, y como «Cambio de puerto a» en el expediente, el PDF, la verificación del QR y el correo.
  - El trámite F3-CAMBIO-PUERTO queda **desactivado, no borrado**: las solicitudes que lo usan lo conservan, y una devuelta se corrige igual (`corregir` no exige trámite activo; `/tramites/{codigo}` trae los inactivos).
  - Lo prueban `tests/test_cambio_de_puerto.py` y el E2E `formulario.spec.ts` (el desplegable), con dos puestos más sembrados en `servidor_e2e.py`.
- **Formulario No. 3 en todos los trámites** (DOC-FORMULARIO-3): uno por solicitud, con todos los pasajeros y para cualquier rango, primero entre los documentos de la solicitud. Es la quinta excepción del catálogo (ver «Reglas»).
  - Las solicitudes ya enviadas conservan su foto del checklist; una devuelta lo pide al corregirse.
  - `MAX_DOCUMENTOS_DE_LA_SOLICITUD` pasa a 2 y el tope de un envío a 285 MB (`TOPE_CUERPO_ENVIO_MB` y nginx).
  - En las pruebas, `enviar` (`tests/ayudas.py`) lo agrega solo al crear (`formulario_3=False` para probar que falta).
- **Rango «Pasajero»** (`pasajero`, segundo lote): un Marino sin libreta. En cada trámite se le piden los documentos del Marino (las filas de `tramite_documentos` cuyo `rangos` incluye `marino` llevan también `pasajero`) salvo la Libreta (`requiere_libreta`, solo `RANGOS_CON_LIBRETA`). Se elige en todos los trámites salvo el de Técnico. La restricción `ck_solicitud_tripulantes_rango` lo admite.
  - **Embarque y Desembarque admiten solo Marino, Pasajero y Militar** (`rangos_permitidos`): los técnicos, supernumerarios y superintendentes van por el trámite de Técnico, y el militar sigue con Generales y boleto (decisión del usuario, a sugerencia: un militar a bordo no es un pasajero).
  - Las filas de los técnicos en esos dos trámites (Carta, Contrato y boleto opcional, del 2026-11-11) quedan sin uso, no se borran: las solicitudes que las tienen en su foto del checklist se siguen viendo igual. El boleto opcional ya no se alcanza desde la pantalla; la lógica de lo opcional sigue y la prueban el espejo y pytest.
  - Lo prueban `test_documento_ucvmm.py` (el Pasajero en cada trámite, los técnicos rechazados en Embarque y Desembarque), su caso en `espejo/checklist.json` y el E2E `formulario.spec.ts`.
- **Datos del trámite:** la fecha de la operación va antes que el puesto de control (pedido del usuario).
- **Pasaporte con 3 meses de vigencia** (pedido del usuario): tiene que vencer al menos 3 meses después de la operación, en todos los trámites y rangos.
  - Se cuenta desde la operación (o desde hoy, si fuera anterior), no desde el día de la solicitud: la operación puede ir hasta 365 días adelante.
  - Meses de calendario, con el borde dentro (operación el 13/11 → vence el 13/02 o después). Si el día no existe, el último del mes (30/11 → 28/02).
  - `MESES_VIGENCIA_PASAPORTE` y `vigencia_minima_pasaporte` (`models/solicitud.py`), espejados en `validacionFormulario.ts` (con `estadoPasaporte`).
  - **El seamanbook vencido ya no bloquea** (decisión del usuario): la tarjeta del pasajero lo avisa («puedes enviar igual») y el expediente lo señala. El motivo sugerido al devolver (`ModalDecision`) ya no lo nombra.
  - Lo ya enviado no cambia. Las alertas del expediente (`pasaporte_vigencia_corta`, nuevo en la salida del pasajero) y de las bandejas (`alertas_de`, con `make_interval` en SQL) cuentan también el pasaporte con menos de 3 meses. Si cambias una, cambia la otra: `test_la_bandeja_cuenta_las_alertas_como_el_expediente` y `test_postgresql_suma_los_meses_como_python`.
  - Lo prueban los casos de `espejo/tripulantes.json`, `test_pasaporte_con_tres_meses_de_vigencia` y `test_seamanbook_vencido_no_impide_enviar` (`test_documento_ucvmm.py`), `test_reglas.py` y el E2E `formulario.spec.ts`.
- **Países con buscador** (bandera, país de nacimiento y nacionalidad; pedido del usuario): `SelectorBuscable` (`components/`), propio y sin librería (CSP), con el patrón «combobox» de la WAI-ARIA.
  - Busca sin distinguir mayúsculas ni tildes, también por el código («PAN»). Lo que empieza por lo escrito va primero (`filtrarOpciones`, `utils/busqueda.ts`, con sus pruebas).
  - Flechas, Enter o Tab para elegir, Escape para cerrar sin cambiar. Al salir con el mouse sin elegir, vale lo escrito solo si no hay duda (`opcionEscrita`).
  - La lista se pinta solo abierta: antes eran 2 × ~250 `<option>` por pasajero. Se abre hacia arriba si no cabe debajo.
  - En el E2E se busca por rol (`getByRole("combobox", { name })`): `getByLabel` encuentra también la lista, que lleva el mismo rótulo. Para elegir, `elegirPais` (`e2e/datos.ts`).

## Cambios del 2026-11-14 (revisión `c3e8a1f5d927`)
Pedido del usuario: Shore Pass solo para marinos, la visa obligatoria a los de nacionalidad restringida, los panameños sin visa, el nombre de quien finalizó en el PDF y que se pueda ver el PDF escaneando el QR sin VPN ni cuenta. Decisiones del usuario: la Visa es un documento nuevo, y quien además deba la Visa Especial de Marino sube las dos; la regla de los panameños va para todo rango y también en Cambio de nave; el nombre de quien finalizó, solo en la copia interna; y en el QR, ver el PDF «sin afectar la seguridad interna, sin vulnerabilidades y sin puntos muertos».
- **Sellado de Shore Pass solo para el Marino** (`rangos_permitidos`). El rango viene elegido y, con un solo rango posible, el campo lo dice («Único rango de este trámite», con `aria-describedby`) y la tarjeta del trámite suma «solo rango Marino».
- **La Visa a los restringidos** (DOC-VISA, «Visa»): una por pasajero de nacionalidad restringida, en todos los trámites (también el desactivado) y para cualquier rango, al final del checklist. Quien además deba la Visa Especial de Marino (Embarque y Cambio de nave) sube las dos.
  - El aviso de la tarjeta sale de las casillas: nombra lo que se le pide por su nacionalidad (`CasillaFormulario.condicion`, `textoRestringida` en `TarjetaTripulante`). Antes salía solo en los trámites con custodia.
  - `tiene_nacionalidad_restringida` (bandeja) y el chip «Restringida» del expediente, en todos los trámites.
  - `MAX_DOCUMENTOS_POR_TRIPULANTE` pasa a 5 (un restringido en Urgencia, Renovación o Desembarque) y el tope de un envío, a 345 MB (`TOPE_CUERPO_ENVIO_MB` y nginx).
- **Panameños sin visa ni boleto** (condición nueva `solo_extranjeros`, «No a panameños» en el catálogo; espejo en `checklist.ts`): la Visa Especial de Marino y el boleto aéreo de Embarque, el boleto de Desembarque y la Visa Especial de Cambio de nave. El marino panameño presenta Generales y Libreta; el pasajero y el militar, solo Generales; el militar de Cambio de nave sigue con su boleto. Un documento de la solicitud con esa condición no se pide si todos son panameños.
- **«Finalizada por» en la copia interna del PDF** («Nombre (Puesto de control)», del historial, como quien aprobó). La de la agencia no lleva nombres.
- **El PDF por el QR, sin VPN ni cuenta** (`GET /verificacion/{codigo}/autorizacion.pdf`, `api/v1/verificacion.py`):
  - La página de verificación suma «Ver autorización (PDF)», un enlace normal: el celular lo abre en su visor (Android lo descarga y lo abre). Se probó que Chrome lo muestra con la CSP del sistema, así que no hizo falta tocarla.
  - Es la copia de la agencia (`pdf_publico` → `_datos_pdf(interno=False)`), mientras valga (`_vigente`) y hasta `DIAS_PDF_PUBLICO` (30) días después de la operación (`pdf_publico_disponible`, y `pdf_disponible` en `SalidaVerificacion`).
  - Si no se puede, o el código no existe, responde 303 a `/verificar/{codigo}`, que explica por qué: **sin pantallas sin salida** («La agencia naviera lo descarga con su cuenta», «no está vigente», «no encontrada»).
  - Tope por IP (`LIMITE_PDF_PUBLICO_POR_MINUTO`, 10), `en_hilo_con_tope`, código validado por formato (422) y metido en la redirección con `quote`, `no-store` y `noindex`, y cada vista en la bitácora (AUTORIZACION_DESCARGADA con `publica` e IP, sin usuario).
  - **Sin VPN funciona solo cuando la DTI publique la verificación en internet**: con un nombre propio, HTTPS y solo estas rutas (plantilla `frontend/nginx-verificacion-publica.conf`, que no usa Docker). En el nginx interno va `set_real_ip_from` para la IP real, y en el `.env`, `URL_VERIFICACION_PUBLICA`: el QR apunta ahí (`url_base_verificacion`). `verificar-despliegue.sh` avisa mientras falte. README → «Verificación pública del QR».
  - Lo prueban `test_ciclo_completo` y `test_pdf_publico_solo_mientras_vale` (`test_flujo.py`), la lista de rutas públicas de `test_seguridad.py` y el E2E `flujo-completo.spec.ts` (el enlace y el PDF).
- Lo prueban también `test_visa_a_los_restringidos_*`, `test_panamenos_sin_visa_ni_boleto` y `test_shore_pass_solo_marino` (`test_documento_ucvmm.py`), los casos nuevos de `espejo/checklist.json` y el E2E `formulario.spec.ts`. La BD del E2E siembra Cuba como restringida (`servidor_e2e.py`).

## Auditoría del proyecto completo (2026-11-14 y 15, migración `d9a4b7e2c315`)

Pedido del usuario: revisar a fondo toda la estructura, los archivos y el código, y aplicar los hallazgos en tres lotes.

**Decisiones del usuario:**
- Quitar las filas de los técnicos de Embarque y Desembarque y la condición `solo_panamenos`. `rangos_opcional` se queda.
- Los Word de `docs/` son la fuente de la documentación de la DTI.
- El historial sale de CLAUDE.md a este archivo.
- El pasajero, fuera de la URL y de los logs.
- Agregar ruff.
- Quitar el alias `RATE_LIMIT_DOWNLOADS_PER_MINUTE` y la columna `tipos_tramite.formulario`, y renombrar los contenedores.

**Lote 1, errores:**
- El aviso de versión nueva («Recargar») ya no lo desplaza un cuarto aviso (`agregarAviso` saca el más viejo que se cierra solo).
- Los avisos se vuelven a ubicar bajo la cabecera al desplazarse.
- El punto de la campana tiene aro (contraste).
- Un `pagina` enorme ya no responde 500 (`MAX_PAGINA`).
- El Excel de la consulta histórica dice las cifras con separador de miles.
- El pasajero de la consulta histórica dejó la URL: viaja en el estado de la navegación, y la consulta y su exportación pasaron a POST.

**Lote 2, limpieza:**
- Se borraron imágenes, íconos, tipos, clases CSS y constantes sin uso.
- Migración `d9a4b7e2c315`: borra las filas de los técnicos, el Contrato de Trabajo (si nadie lo usa), la condición `solo_panamenos` y la columna `formulario`, con su `downgrade`.
- Se quitó el alias del `.env`.
- Los contenedores pasan de `snm_*` a `argonavis_*`: en el servidor hay que recrearlos y actualizar las tareas programadas.
- ruff 0.17.5 (`backend/ruff.toml`), en la CI.

**Lote 3, repetición y estructura:**
- **Identidad y texto:** `core/identidad.py` (institución, paleta y logos, antes copiados en el correo, el PDF y los informes) y `core/texto.py` (`sin_tildes`, `slug`). La zona horaria sale siempre de `core/horario.py`.
- **Informes:** salen de `core/` a `app/informes/`.
  - `autorizacion_pdf`, `estadisticas` (y un módulo por formato), `historico_excel`.
  - Lo común en `comun.py`, `excel.py` (`LibroInforme`: la identidad arriba de cada hoja, antes copiada en los dos Excel) y `pdf.py` (fuentes y texto seguro).
- **Bitácora:** `auditar()` en `api/v1/dependencias.py` reemplaza seis copias que repetían la IP y el navegador.
- **Dependencias de sesión:** `obtener_id_usuario_actual` y `requerir_*` pasan a `api/v1/dependencias.py`. `core/` ya no importa de la BD ni de FastAPI para eso.
- **`main.py`** queda armando la aplicación (369 → 191 líneas): los manejadores de errores van a `api/manejadores.py` y los middlewares a `api/middleware.py`.
- **Servicios:** las reglas de usuarios, roles y catálogos salen de las rutas a `usuario_service.py`, `rol_service.py` y `catalogo_service.py`.
  - Las rutas solo orquestan, como dice la estructura.
  - `admin.py`: 449 → ~210 líneas.
- **`solicitud_service.py`:** salen el contexto de acceso (`acceso.py`) y las series de las estadísticas (`series.py`). El resto se queda, porque las pruebas reemplazan ahí `ahora_utc`.
- **Pruebas:**
  - Las ayudas repetidas van a `ayudas.py`.
  - Las variables de las tres BD temporales van a `entorno_pruebas.py`.
  - La consulta histórica y el expediente se comparan en las dos direcciones.
- **Frontend:**
  - `utils/texto.ts` (`sinTildes`), `utils/fechas.ts` (`dosCifras`, `fechaISOLocal`) y `constants/interfaz.ts` reemplazan copias.
  - `App.tsx` (255 → 91) deja las guardias en `RutasProtegidas` y el vigilante en `VigilanteSesion`.
  - `modulos/solicitudes` va en subcarpetas por pantalla.
  - `PaginaUsuarios` se partió en tres componentes (506 → ~160).
  - Los tipos de la API de solicitudes van a `tiposSolicitudes.ts` (se reexportan).

**Revisado y sin cambios:**
- Las tres asignaciones de usuarios de los catálogos: se parecen en la forma, pero cada una tiene su regla.
- Los estilos de los campos y la franja: los valores ya son tokens, y juntarlos pide cambiar la marca HTML.


## Boleta de recargo y supervisor general (2026-11-16, migración `e5c1a7d3b902`)

Pedido del usuario: validar el recargo por atención fuera del horario, integrar una boleta para cobrarlo y limitar al supervisor general.

**El recargo ya estaba como lo pidió** (desde el 2026-11-11), y se validó:
- son B/.20.00;
- cuenta la hora en que UCVMM aprueba;
- de lunes a viernes, de 07:00 a 15:00, es laboral (las 15:00 en punto todavía lo es);
- de 15:01 a 06:59 hay recargo, y el sábado y el domingo enteros.

Solo cambió el nombre visible: «Costo migratorio» pasó a «Recargo por atención fuera del horario laboral», en el expediente, el correo, el PDF y el Excel de la histórica. La API sigue con `costo_fuera_de_horario`.

**Boleta de recargo** (tabla `boletas_recargo`):
- **Quién la genera:** UCVMM, el supervisor de sector y el puesto de control (decisión del usuario), y el Administrador. Antes de generarla se pide el número de oficio.
- **El número:** único por boleta (decisión del usuario). Se compara sin distinguir mayúsculas, también contra las anuladas.
- **Si salió mal:** se anula con motivo y se genera otra (decisión del usuario: «como un talonario»). Hay una sola vigente por solicitud.
- **La agencia no la ve:** la imprime el SNM y se la entrega (decisión del usuario). Por eso el PDF no lleva nombres de funcionarios.
- **El formato es un borrador:** UCVMM tiene un modelo en papel, que se copiará después.
- **No se puede borrar:** la cuenta de la aplicación no tiene DELETE sobre la tabla (`TABLAS_SIN_BORRAR`).
- **Concurrencia:** dos generaciones a la vez dejan una sola vigente; la solicitud se bloquea.

**Supervisor general:**
- **Qué ve:** solo el trámite de Técnico, Superintendente o Supernumerario, de los dos sectores. Embarque y Desembarque (marinos, pasajeros y militares) «no interesan».
  - Qué trámites ve lo marca el catálogo (`tipos_tramite.supervision_general`), así que otro se suma con una migración.
  - Se descartó filtrar por el rango de los pasajeros, porque traería Urgencias, Renovación y Cambio de nave con técnicos.
- **Qué pierde:** las estadísticas, el uso del sistema (que queda solo para el Administrador) y la consulta histórica.
- **El supervisor de sector** no cambió.

**Pruebas:**
- `test_boletas.py`: 12 pruebas.
- `test_supervisor_general_solo_tecnico`.
- La cuenta de la BD sin DELETE sobre las boletas.
- `boleta.spec.ts` (E2E), con una solicitud de Técnico que siembra `servidor_e2e.py`.
- El paso del supervisor general de `flujo-completo.spec.ts`.

## Subir y bajar, sin ocupación y tipo de operación en la boleta (2026-11-16, migración `a7c2e9f4b618`)

Pedido del usuario, con sus decisiones:

**«¿Subir y bajar?»:**
- **Dónde:** solo en Embarque y Desembarque (`tipos_tramite.permite_subir_y_bajar`).
  - La pregunta va al final de «Datos del trámite», antes del cambio de puerto, que sigue último.
  - Empieza en «No».
- **Con «Sí»:** cada pasajero, sea marino, pasajero o militar, adjunta la Carta de Responsabilidad (Form. No. 7), además de lo demás del trámite.
  - Es una fila del catálogo con la condición nueva `subir_y_bajar`, espejada en `checklist.ts`.
  - La foto del checklist la guarda, como a las demás.
  - El Formulario No. 3 ya se pedía siempre.
- **Dónde se guarda:** `solicitudes.subir_y_bajar`.
- **Otros trámites:** la respuesta se descarta, como el cambio de puerto.
- **Dónde se ve:** en el expediente, en el PDF de la autorización y en la boleta.
- **Rangos:** Embarque y Desembarque ya admitían solo Marino, Pasajero y Militar (desde el 2026-11-13); no cambió.

**Ocupación:**
- Salió del formulario: `solicitud_tripulantes.ocupacion` admite nulo.
- **Solicitudes viejas:** la siguen mostrando (decisión del usuario). El expediente y el PDF titulan la columna «Rango / ocupación» solo si algún pasajero la tiene. Así, un PDF ya entregado sale igual si se vuelve a descargar.
- **Al corregir una devuelta:** se borra, porque podría quedar pegada a otra persona si la agencia cambia a alguien en la misma ficha.
- **Versión anterior abierta:** un navegador con la versión anterior que todavía la mande no falla, porque el campo se ignora.

**Boleta:**
- El tipo de operación va en casillas, como en un formulario en papel (decisión del usuario): los trámites activos, en su orden, con la X en el de la solicitud.
  - Una solicitud de un trámite ya inactivo (Cambio de Puerto) lo muestra al final, marcado.
- Si el trámite pregunta «¿Subir y bajar?», debajo va la respuesta.
- La línea bajo el título queda solo con el número de la autorización.

**Pruebas:**
- `test_documento_ucvmm.py`: el catálogo con la Carta y cinco pruebas de «subir y bajar», entre ellas la corrección de «Sí» a «No» y el PDF.
- `test_ocupacion.py`.
- Dos casos espejo en `checklist.json`.
- `test_casillas_operacion` y los datos de la boleta por la API.
- Vitest, para el envío, la precarga y la columna.
- E2E: la pregunta en `formulario.spec.ts` y el formulario sin ocupación en `flujo-completo.spec.ts`.

## Rediseño visual «B + C» (2026-11-17)

Pedido del usuario:
- «Busca todos los botones, remarcaciones y detalles, y mejóralos: más visual, más llamativo.»
- «Especialmente en el modo claro hay cosas que no se distinguen.»
- «Que cualquier persona lo entienda y no se pierda ni se frustre.»
- «Todo el frontend, en cada vista.»

**Proceso:**
- Revisión de todas las vistas por rol, en claro, oscuro y celular, contra la pila del E2E.
- Tres maquetas sobre las pantallas reales, con estilos inyectados en el navegador: A «Nítido», B «Color que guía» y C «Documento oficial».
- El usuario eligió la **mezcla B + C**.

**Lo que encontró la revisión (claro):**
- Tarjetas lavadas sobre el fondo.
- Lo elegido casi invisible: «Sin / Con» pálido, y la pestaña y el filtro activos con solo una raya.
- Lo desactivado igual al gris que sí funciona.
- La tabla de pasajeros del puesto cortaba la columna «Impedimento».
- Anchos y lenguajes distintos entre vistas.
- Un «−720 min» en las estadísticas, por la siembra del E2E.

**Qué cambió:**
- **Tokens:** claro más contrastado; tokens de sección, estado, desactivado y nota en los dos temas; la guarda `styles/contraste.test.ts`.
- **Piezas compartidas:**
  - títulos de sección en barra marino con el número en la franja (`styles/Secciones.module.css`);
  - lo desactivado rayado y el botón `sobreSeccion`;
  - pestañas y filtros activos rellenos, cada pestaña con el punto de su estado;
  - «Sin / Con» sólidos y notas en azul.
- **Bandejas e histórico:** pases con el color de su estado en el borde y el talón, y estados vacíos que dicen qué hacer.
- **Expediente:** «Qué sigue» según el rol y el estado (`pasosSiguientes`), y la tabla de pasajeros con el pasaporte y el seamanbook en una columna.
- **Formulario:**
  - indicador de avance de los 4 pasos (`pasosDelFormulario`) con enlaces;
  - casillas pendientes en naranja y cubiertas en verde;
  - campos más altos y rótulos más grandes.
- **Administración:**
  - encabezados en barra marino;
  - la bitácora con los rótulos y botones del resto y etiquetas por categoría (`categoriaAccion`);
  - pestañas de catálogos rellenas;
  - en las estadísticas, un tiempo negativo sale como «—» (y la siembra del E2E pone `created_at`).
- **Un solo ancho de página** (1240 px).

**Pruebas:**
- `contraste.test.ts`, `pasosSiguientes.test.ts`, `pasosDelFormulario.test.ts` y `categoriaAccion.test.ts`, más el caso negativo de `duracion`: 63 pruebas nuevas en Vitest.
- El E2E completo, sin cambios de selectores.

## Revisión del esquema al arrancar (2026-11-17, migración `c4e8a2f6d915`)

**Qué pasó:** tras las migraciones de la boleta y de «subir y bajar», el backend de desarrollo (con `--reload`) tomó el código nuevo, pero nadie corrió `migrate.bat`. Cada pedido respondía «Error interno del servidor (código …)», y la causa («no existe la columna solicitudes.subir_y_bajar») solo estaba en el log. Las pruebas no lo ven: arman su propia base, migrada hasta la última revisión. El usuario lo pidió «para hacer el despliegue»: en Windows, `migrate.bat` se corre a mano.

**Qué cambió:**
- Al arrancar, el backend compara la base con el ORM (`infrastructure/esquema.py`): tablas, columnas, tipos enum y sus valores. Solo mira lo que **falta**: una base más nueva que el código, como al volver a una versión anterior, no es una falla.
- Si falta algo:
  - el log dice qué falta y qué hacer («Corre migrate.bat y vuelve a levantar el backend»);
  - la API responde 503 con el motivo, que el frontend muestra (`EsquemaAlDia`, `api/middleware.py`);
  - `/api/health` responde 503, «base de datos sin migrar»;
  - las tareas de fondo no arrancan, porque fallarían en cada vuelta.
- Una base que no responde al arrancar no lo impide, como antes: queda un aviso en el log.

**Decisiones:**
- **El catálogo de PostgreSQL, no `alembic_version`:** la cuenta de la aplicación no puede leer esa tabla (`permisos_bd.py`), y así no hubo que darle más permisos.
- **No tumba el proceso:** uvicorn reinicia sin parar los procesos que caen al arrancar (0.49, `Multiprocess.keep_subprocess_alive`). Con varios procesos, eso llenaría el log cada medio segundo.

**Lo que encontró:** una base migrada desde cero no tenía `CHAT_CONSULTA` en el tipo de la bitácora. Ese valor lo dejó una función de chat ya retirada, que lo agregaba fuera de las migraciones: solo lo tenían las bases viejas, y el ORM lo conserva para leer sus registros. Sin arreglarlo, cada instalación nueva habría quedado en 503. Lo agrega la revisión `c4e8a2f6d915` (`IF NOT EXISTS`: en las bases viejas no hace nada).

**Pruebas:** `tests/test_esquema.py`, con 7 pruebas. `test_la_base_migrada_tiene_todo_lo_que_usa_el_codigo` falla también si un modelo cambia sin su migración.

## La operación de Técnico y los días del sellado de Shore Pass (2026-11-18, migraciones `b8f3d6a1c472` y `d2a7c5e9f831`)

Pedido del usuario: en la Autorización de Técnico, Superintendente o Supernumerario, «un select que se seleccione si es embarque, desembarque, subir y bajar». Decisiones del usuario: **los documentos no cambian** (solo se registra); se ve en el expediente, el PDF de la autorización, la boleta de recargo y el pase de la bandeja; y el select **empieza sin elegir** y es obligatorio.

- **Catálogo y datos:** `tipos_tramite.pide_operacion` (hoy, solo F3-TECNICO) y `solicitudes.operacion` (`embarque`, `desembarque` o `subir_y_bajar`, con la restricción `ck_solicitudes_operacion`). Nula en los demás trámites y en las solicitudes de antes.
- **Formulario:** «Operación *», en «Datos del trámite», después del puesto de control. Sin elegir, el backend responde 400 («Faltan datos obligatorios del formulario: Operación…», `validar_campos_cabecera`) y el formulario lo cuenta entre los datos que faltan (`validarFormulario`). Un valor que no existe responde 422. Al cambiar a otro trámite se borra; al corregir una devuelta, viene la suya.
- **Dónde se ve:** el pase de la bandeja («Autorización de Técnico… · Subir y bajar»), «Datos del trámite» del expediente, la línea «OPERACIÓN» del PDF de la autorización y, en la boleta, una fila de casillas bajo el tipo de operación (las de antes, sin la fila).
- **No es el «¿Subir y bajar?» de Embarque y Desembarque:** ese pide la Carta Form. 7 de cada pasajero; este no pide nada más.
- **Pruebas:** en `test_documento_ucvmm.py`, obligatoria y con los mismos documentos en las tres, un valor inválido, descartada en otro trámite, y en la bandeja, la corrección y el PDF; en `test_boletas.py`, la fila de la boleta; en Vitest, la validación y el envío; en el E2E, el formulario (`formulario.spec.ts`) y el pase y el expediente de la solicitud sembrada (`boleta.spec.ts`, que ahora es de «Subir y bajar»). `tests/ayudas.py` manda `operacion` en la cabecera de todas las pruebas: los demás trámites la descartan.

**Los días del sellado de Shore Pass** (segundo pedido del mismo día: «que se pueda seleccionar si el sellado de shore pass es de 5 o 15 días»). Decisiones del usuario: lo mismo que la operación de Técnico. Solo se registran (no cambian los documentos ni la vigencia de la autorización), se ven en los mismos cuatro lugares y el select empieza sin elegir.
- `tipos_tramite.pide_dias_sellado` (hoy, solo F3-SHORE-PASS) y `solicitudes.dias_sellado` (5 o 15, con `ck_solicitudes_dias_sellado`).
- «Días del sellado *», en «Datos del trámite». Sin elegir, 400 («Días del sellado (5 o 15)»); otro valor, 422.
- Se leen «15 días» en el pase de la bandeja, el expediente, el PDF de la autorización («DÍAS DEL SELLADO») y la boleta.
- La boleta recibe ahora las dos en `elecciones` (rótulo, opciones, elegida): cada una es una fila de casillas.
- **Pruebas:** las mismas que la operación, en `test_documento_ucvmm.py`, `test_boletas.py` (parametrizada con las dos), Vitest y `formulario.spec.ts`.

## Tripulantes otra vez, «Subir y bajar» solo en Técnico, visas según el trámite y estadísticas sin UCVMM (2026-11-18, migraciones `f4c9b2e7a813` y `a1d6f3b8c524`)

Pedido del usuario: «la opción de subir y bajar solo va en el trámite de autorización de técnico, superintendente y supernumerario, no en ningún otro trámite»; la visa de los restringidos «solo también en trámite de autorización de técnico»; «cuando dice pasajeros que se normalice a tripulante»; y «la opción de estadísticas solo la debe ver el supervisor de sector, no UCVMM». Decisiones del usuario: con la operación «Subir y bajar», la Carta Form. 7 de cada tripulante; el rango Pasajero conserva su nombre («es un tipo; lo otro es una forma general de llamar a todos los rangos»); el Administrador sigue viendo las estadísticas; al Marino y al Pasajero restringidos de los demás trámites se les exige la Visa Especial de Marino, y el Militar «se mantiene como está».

- **«Subir y bajar»:**
  - Embarque y Desembarque dejan de preguntarlo (`permite_subir_y_bajar` en falso) y de pedir la Carta.
  - El trámite de Técnico la pide con su operación «Subir y bajar» (`con_carta_subir_y_bajar`, espejado en `conCartaSubirYBajar`, con sus casos en `espejo/subir_y_bajar.json`). Bajo el select, un aviso lo dice.
  - Las solicitudes de Embarque y Desembarque que respondieron «Sí» (del 16 al 18) conservan su Carta en la foto del checklist y lo siguen mostrando en el expediente, el PDF y la boleta.
- **Visas de los restringidos:**
  - La «Visa» (DOC-VISA): en Técnico, a todos sus rangos; en los demás trámites, solo al Militar; Shore Pass, que admite solo al Marino, la pierde.
  - La Visa Especial de Marino (DOC-VISA-MARINO), al Marino y al Pasajero restringidos de los demás trámites. En Embarque y Cambio de nave ya la lleva todo extranjero.
  - Un técnico que vaya por otro trámite no lleva visa: sigue señalado.
  - El aviso de la tarjeta nombra la visa que corresponde, aunque su condición sea otra (`VISAS`, `TarjetaTripulante.tsx`).
- **Estadísticas:** solo el supervisor de sector y el Administrador (`_PUEDE_VER_ESTADISTICAS` y `PERMISOS_ESTADISTICAS`). UCVMM recibe 403 y no las ve en el menú. El E2E entra con un supervisor de sector nuevo (`e2e.supsector`).
- **«Tripulantes»** en todo lo que ve el usuario: pantallas, mensajes de error, correos, PDF de la autorización, boleta, consulta histórica (su Excel y su filtro) y las descripciones del catálogo (migración `a1d6f3b8c524`, que deshace la `d5b8e2f1a9c3`).
  - El rango «Pasajero» se queda.
  - Los títulos y los textos del historial ya guardados (por ejemplo, «… — 2 pasajeros») no cambian.
  - Los nombres que son contrato tampoco: el filtro `pasajero` de la consulta histórica y el estado de «Volver».
- **Pruebas:**
  - `test_documento_ucvmm.py`: la tabla literal; la visa según el trámite y el rango (`test_la_visa_de_los_restringidos`); la Carta de «Subir y bajar» en Técnico y en ningún otro trámite; la corrección; y el PDF de las de antes.
  - `test_sectores.py`: UCVMM sin estadísticas. Las pruebas de estadísticas pasan al supervisor de sector.
  - El espejo `subir_y_bajar.json`.
  - E2E: `formulario.spec.ts` y `estadisticas.spec.ts`.

## Carta de garantía en Técnico, cambio de puerto a cualquier sector y métodos de pago en la boleta (2026-11-18, migración `b5e1c8d4f207`)

Pedido del usuario:
- en el trámite de Técnico, con Embarque o Desembarque, «carta de garantía de la agencia contratante o contrato»; con «Subir y bajar», «carta de garantía»;
- en la boleta, «métodos de pago (efectivo, tarjeta o cheque a favor del Servicio Nacional de Migración)»;
- en el cambio de puerto, quitar el filtro: «que se pueda cambiar el puesto de uno del Pacífico a uno del Atlántico».

Decisiones del usuario: con «Subir y bajar», la carta de garantía y también la Carta Form. 7 de cada tripulante; una carta por solicitud, no por tripulante; y el nombre «… de la agencia contratante».

- **Documentos nuevos** (una por solicitud, al final del checklist de Técnico):
  - `DOC-GARANTIA-O-CONTRATO`, «Carta de garantía de la agencia contratante o contrato» (cualquiera de los dos, en una casilla), con la condición nueva `embarque_o_desembarque`;
  - `DOC-CARTA-GARANTIA`, «Carta de garantía de la agencia contratante», con `subir_y_bajar`.
  - Caben en el tope de 2 documentos de la solicitud (`MAX_DOCUMENTOS_DE_LA_SOLICITUD`): el Formulario No. 3 y una de las dos.
- **La condición `embarque_o_desembarque`** se evalúa con la operación. `construir_casillas` y `construirCasillas` reciben la operación; sin elegir, no se pide ninguna de las dos garantías.
- **Cambio de puerto:**
  - `_validar_cambio_de_puerto` ya no exige el mismo sector, y `puestosParaCambio` ofrece todos los demás puestos.
  - Se quitó el aviso «si el nuevo puerto no está en la lista, presenta una nueva solicitud».
  - Las opciones siguen sin nombrar los sectores, porque las lee la agencia.
  - La revisa UCVMM del sector del primer puesto (el sector sale siempre de `puesto_control_id`) y la finaliza el puesto nuevo. UCVMM del otro sector no la ve.
- **Boleta:** una fila «MÉTODOS DE PAGO» bajo el total, también en las anuladas. El sistema sigue sin registrar el pago.
- **Pruebas:**
  - `test_documento_ucvmm.py`: la garantía según la operación, en otros trámites no, y la corrección de «Subir y bajar» a Embarque.
  - `test_cambio_de_puerto.py`: a otro sector, y de punta a punta con el puesto del Atlántico.
  - `test_boletas.py`: los métodos de pago, capturando los párrafos del PDF.
  - Los casos nuevos del espejo del checklist y el E2E `formulario.spec.ts`.

## Auditoría del stack y revisión de los documentos de Office (2026-11-22)

Pedido del usuario: «el stack actualmente utilizado, ¿consideras que es el adecuado para este tipo de proyecto? Revisa y haz una auditoría completa a fondo», y después «procedamos con lo urgente y después vamos abarcando los demás puntos».

- **El stack se queda.** Lo que falta y su orden, en CLAUDE.md («Lo que sigue pendiente», punto 21).
- **Un documento de Office podía tumbar el backend.** `oletools`, que buscaba las macros, leía partes enteras del archivo sin tope. Bastaba una cuenta de agencia. Medido en local:
  - un .docx de 20 KB con 20 MB en `_rels/.rels`: +518 MB de memoria, y se aceptaba;
  - un .docx de 400 KB con un objeto OLE2 de 400 MB: +832 MB (el contenedor tiene 1 GB);
  - un .doc de 408 KB: 8,3 s de CPU, que crece al cuadrado (con los 2 MB que se admiten, minutos; un envío lleva hasta 172 archivos);
  - al rechazar, a veces dejaba el archivo abierto (en Windows, un 500 en vez del 415).
- **Por qué no bastaba con un tope antes de analizar:** la librería abre el archivo por varios caminos (ZIP, OLE2, MHTML, XML), y el tamaño que declara un ZIP lo escribe quien lo arma.
- **`infrastructure/revision_office.py` la reemplaza.** Recorre el archivo de a trozos, sin guardar lo que se descomprime. Con los mismos ataques al máximo (1.500 MB en un .docx de 1,5 MB): 3 MB de memoria y 0,2 s.
  - **Formato:** en .doc y .xls exige el flujo principal de Word o Excel. Antes bastaba la firma OLE2, y un instalador (.msi) o un correo (.msg) renombrados pasaban. Un .docx con contraseña renombrado a .doc, también.
  - **Macros:** el nombre del flujo `_VBA_PROJECT` en el directorio OLE2 (va entero, sin comprimir y sin distinguir mayúsculas) o el comienzo del código VBA; en los .docx y .xlsx, además, en cualquier parte que sea OLE2, y `vbaProject.bin`.
  - **Tamaño:** 50 MB descomprimidos, 2.000 partes y solo deflate. Mide lo que cada parte ocupa de verdad y rechaza la que no mide lo que declara. El mensaje: «ocupa demasiado al abrirse. Guárdalo como PDF e intenta de nuevo.»
  - Lo rechazado por macros o por tamaño queda en el log.
- **Paridad comprobada con 26 archivos reales** (Word y Excel de Office 2021, 97 y 95; con objetos incrustados; con clave; complementos de Office con macros, también con el proyecto renombrado; los documentos de `docs/`): detecta los 7 con macros y no rechaza ninguno bueno, igual que la librería.
- **Dependencias:** salen 11 paquetes del bloqueo (`oletools` y lo que arrastraba: `olefile`, `msoffcrypto-tool`, `pcodedmp`, `cryptography`, `cffi`, `pyparsing`…). Ninguno de los demás cambia de versión.
- **Pruebas:** `test_revision_office.py` (58). Quitando de a una cada defensa, alguna prueba falla. La suite completa pasa con esas librerías bloqueadas.
- **Repositorio:** se quitó de este archivo la IP del servidor de pruebas. El historial de git se revisó entero: sin claves ni tokens, solo marcadores de ejemplo.

## Contenedores endurecidos, redes separadas y PostgreSQL 15.20 (2026-11-22)

Punto 1 de la hoja de ruta de la auditoría. El repositorio a privado queda para el final, por decisión del usuario.

- **Los tres contenedores** (`x-endurecido` en `docker-compose-prod.yml`): sin root, `cap_drop: ALL`, `no-new-privileges` y la imagen de solo lectura.
  - PostgreSQL corre con el usuario 70 desde que arranca (antes, root hasta el `gosu`); nginx, con el 101 (antes, el maestro era root). El backend ya corría con el 10001.
  - nginx escucha en el 8080, porque el 80 es solo de root; Docker lo publica en el 80. Con `absolute_redirect off`, para que una redirección no agregue el 8080.
  - Lo que escriben: los volúmenes de siempre, dos nuevos para los envíos mientras llegan (`temporales_backend` en `/tmp` y `temporales_nginx` en `/var/cache/nginx`) y tmpfs chicos para el socket y el pid.
- **Redes:** PostgreSQL y el backend en `datos`; nginx, solo con el backend. `datos` ocupa un /28 (`RED_DATOS`): Docker le daría un /16 de 172.x, que puede coincidir con una red del SNM o de la VPN.
- **PostgreSQL 15.20** (del 12/11/2026): corrige 43 vulnerabilidades. Sus notas piden reconstruir índices GIN, `pg_trgm` GiST o de `bpchar` sin largo; el esquema no tiene ninguno.
- **CI:** el trabajo `contenedores` construye la pila y la levanta sobre una base de la versión anterior arrancada como root, después de un reinicio y desde cero, y corre `verificar-despliegue.sh --solo-la-pila`.
- **Verificación:** las imágenes oficiales se leyeron por dentro (usuarios, dueños de las carpetas y guiones de arranque), el compose se validó con el cliente de Docker y los chequeos nuevos se probaron con herramientas de mentira, en los casos buenos y malos. **No se levantó ningún contenedor en el equipo de desarrollo** (no tiene virtualización): la primera vez que corre de verdad es en la CI.
- **README:** el `chown` del volumen viejo va con `docker run`; con `docker compose run` ya no tiene permiso.
- **Pruebas:** `test_contenedores.py` (12).

## Registros, vigilancia y prueba de restauración (2026-11-22)

Puntos 2, 3 (en parte) y 4 de la hoja de ruta de la auditoría.

- **Registros que sobreviven al despliegue.** Docker borra su salida cada vez que recrea el contenedor. El backend escribe además un archivo por día en el volumen `registros` (`LOG_CARPETA`, que ya existía para Windows) y nginx, sus accesos en `registros_nginx`, con la fecha en el nombre (`map $time_iso8601 $dia`), así que no hay que rotarlos. Se guardan `LOG_DIAS` (90). Los dos contenedores llevan la hora de Panamá (`TZ=EST5`).
  - Con una variable en el nombre, nginx no escribe si la raíz de la petición no existe: por eso `root` va también en el `server`.
- **`vigilar.py`:** avisa por correo cuando algo falla. Hasta ahora nadie se enteraba: había que correr `verificar-despliegue.sh` a mano.
  - Cada 5 minutos: contenedores, aplicación, base, correos fallidos o atascados, procesos caídos, rachas de errores, respaldos, discos, memoria y reloj. Avisa a la segunda falla seguida, recuerda una vez al día y avisa cuando se resuelve; si el correo no sale, lo reintenta.
  - Cada mañana (`--diario`): `verificar-despliegue.sh --diario`, sin la prueba del freno del login, que llenaría la bitácora. Los lunes manda el resultado siempre y prueba el respaldo. También borra los accesos viejos de nginx.
  - Corre en el servidor, con el Python 3.9 del sistema y la biblioteca estándar: tiene que avisar aunque Docker esté caído.
  - Falta poner `CORREO_ALERTAS` y las dos líneas del cron en cada servidor. Si el servidor entero se apaga, tiene que verlo el monitoreo de la DTI.
- **`probar-restauracion.sh`:** carga el último respaldo en una base aparte y comprueba los datos y cada documento. `backup.sh` no tenía pruebas; ahora las tiene, con un `docker` de mentira, y en la CI los dos corren con PostgreSQL real.
- **PostgreSQL 18 en la CI:** el backend se prueba con la 15.20 y con la 18.7, la del servidor nuevo. Si la 18 falla, se ve pero no deja el push en rojo.
- **Queda del punto 3:** copiar los respaldos a otro equipo, cifrados. Depende de la DTI: si las VM de producción entran en el respaldo de vSphere, puede que ya esté resuelto.
- **Pruebas:** `test_vigilar.py` (35; también se corrió con un Python 3.9 real), `test_respaldos.py` (12) y los casos nuevos de `test_contenedores.py` y `test_dependencias.py`.

## Consultar las autorizaciones muchos años después (2026-11-22, revisión `c6e2a9f1d438`)

Pedido del usuario: «necesitamos que las solicitudes se puedan consultar, las aprobadas y finalizadas, inclusive muchos años después». Sobre la propuesta respondió: que salgan también las aprobadas que vencieron sin finalizarse; la consulta histórica, solo de UCVMM y del supervisor de sector; «el sector que revisó, aunque que se indique que fueron procesadas antes en y el cambio a hoy»; y «además de la información, los archivos también deben verse, revisa todo eso a fondo».

- **Lo que ya estaba bien:** nada borra solicitudes, documentos ni bitácora; los nombres de la agencia, del puesto y de los funcionarios son una foto; los archivos se abren en cualquier estado, con permiso.
- **«Autorizadas»**, una pestaña de la consulta histórica (y un filtro del Excel): las que se aprobaron alguna vez (`aprobada_en`), vigentes, finalizadas y vencidas sin finalizar. «Aprobadas» es el estado de hoy y dura unos días: de hace años daba cero. Cada expirada dice si se llegó a aprobar.
- **La búsqueda** no distingue tildes, admite las palabras en cualquier orden y busca también el seamanbook; antes tenía que ser el texto exacto y seguido. Al buscar un tripulante, la lista dice cuál es. Es la misma de las bandejas.
- **Velocidad**, con 10 años simulados (200.000 solicitudes y un millón de tripulantes) en PostgreSQL 17.10:

  | Búsqueda | Antes | Ahora |
  |---|---|---|
  | Un pasaporte | 12,7 s | 0,04 s |
  | Nombre y apellido | 11,8 s | 0,03 s |
  | Un número | 3,3 s | 0,06 s |
  | Un IMO | 2,7 s | 0,03 s |
  | Un apellido común (20.000 resultados) | — | 0,2 s |
  | Dos letras (100.000 resultados) | — | 0,4 a 1,4 s |

  - Columnas `busqueda` calculadas por PostgreSQL, con un índice de trigramas (`pg_trgm`). Con esos datos, los índices ocupan 135 MB y la migración tarda menos de 2 minutos.
  - Las pestañas y el total de una bandeja salen de una sola cuenta (antes, dos).
  - En la pantalla, las ocho pestañas van como fichas: con cantidades grandes no caben en una fila.
  - Los índices GIN se crean ya con PostgreSQL 15.20, que corrigió sus fallas de `VACUUM`. Una base de desarrollo en 17.10 o anterior conviene reindexarla al subirla.
- **El sector que la revisó la conserva** (`sector_revision_id`), aunque el puesto cambie de sector. Antes, mover un puesto se llevaba todo su historial al otro. Vale para la consulta, las bandejas, los expedientes con sus archivos, las boletas y las estadísticas. El expediente dice «Sector Pacífico, que la revisó. Hoy el puesto es del Sector Atlántico», y el filtro por puesto sigue ofreciendo los que cambiaron. Las que están en revisión pasan al sector nuevo, como antes. Las que ya existían quedaron con el sector de hoy de su puesto.
- **Quién la tiene:** UCVMM, el supervisor de sector y el Administrador. El puesto de control ya no: consulta las suyas en su bandeja, como la agencia (ahí se busca por número, buque, IMO o agencia, sin rango de fechas ni tripulante). Con cambio de puerto, el primer puesto solo la encontraba ahí; ya no la ve (abajo).
- **Los archivos:**
  - Se comprobó que se ven y se descargan en los seis estados, con los permisos de cada rol.
  - `infrastructure/revisar_documentos.py` compara cada documento registrado con su archivo (que esté y que mida lo mismo). Lo corre `verificar-despliegue.sh`, cada mañana con `vigilar.py`: un archivo que se pierde sin que nadie lo note salía de los respaldos a los 14 días.
  - El PDF de la que se aprobó y venció lo descarga el SNM, con el sello EXPIRADA y sin la vigencia. La agencia y el QR, no.
- **Quedó para decidir**, y se hizo ese mismo día (sección siguiente): los documentos que la agencia reemplaza al corregir se borraban para siempre, los archivos no llevaban huella y el PDF se armaba cada vez.
- **Pruebas:** `test_consulta_de_anios.py` (22) y `test_revisar_documentos.py` (8), la migración con una dueña que no es superusuario (`test_migraciones.py`), los casos nuevos de Vitest y el E2E. Quitando de a una las 33 reglas nuevas, alguna prueba falla.

## El historial completo de una solicitud (2026-11-22, revisión `d7f3b0c5e849`)

Respuestas del usuario: «1. El puesto no debe tener acceso a consulta histórica; 2. ya no debe verla y debe aparecerle al nuevo puesto; 3. sí (conservar lo reemplazado y el PDF como se emitió, con huella); 4. aún no se sabe, pero debe haber un margen e historial completos».

- **Cambio de puerto:** la ve, la finaliza y genera su boleta solo el puesto nuevo. El primero no la abre ni con el enlace (antes la consultaba): no tiene nada que hacer con ella, y si llega alguien con el PDF, el QR dice a qué puesto fue.
- **Al corregir se conserva lo enviado.** Antes se borraban los documentos reemplazados, los tripulantes que salían, sus datos y la verificación de impedimentos.
  - `solicitud_versiones`: la foto de lo que se había enviado, con los nombres de ese día, quién la envió, quién la devolvió y por qué. En pares (rótulo, valor), para que se lea igual aunque cambien las columnas o el catálogo.
  - Los documentos que salen quedan retirados (`retirado_en`), con el nombre de su tripulante. La llave del tripulante pasa de CASCADE a SET NULL.
  - El registro dice qué cambió la agencia («Buque: AURORA → AURORA II», «Tripulante quitado: …»): le sirve a UCVMM para revisar una corregida.
  - Las correcciones de antes no se pueden recuperar: la pantalla lo dice.
- **La huella (SHA-256)** de cada archivo, calculada al recibirlo. Se comprueba al abrirlo: si no coincide, no se muestra y queda en el log. A los de antes se les calcula una vez, en segundo plano.
- **La autorización, tal como se emitió** (`documentos_emitidos`, `emision.py`): se arma una vez al aprobar y otra al finalizar, después del commit, y es la que reciben la agencia y el QR. Antes se armaba en cada descarga, con el formato de ese día. Pesa unos 150 KB.
  - Si el proceso se cae entre aprobar y emitir, la completa la tarea de fondo (`cuidar_archivo`, un solo proceso a la vez) o la primera descarga. Dos a la vez dejan una sola.
  - Si el archivo se dañó, la agencia recibe una armada de nuevo (no se queda sin su autorización), queda el error en el log y el registro no muestra otra cosa que la emitida.
- **La pantalla:** «Historial completo» en el expediente, para el SNM que la ve antes de aprobarse. Se pide al abrirlo. La vista previa abre también los retirados y las emitidas (`obtenerArchivo`).
- **En la base:** la cuenta de la aplicación solo agrega a las dos tablas nuevas y no puede borrar documentos.
- **Se quitó `al_confirmar`:** ya no se borra ningún archivo registrado.
- **Respaldos con margen:** 14 noches, la primera de los últimos 12 meses y la primera de los últimos 10 años. La base se cuenta ahora por noches y no por la fecha del archivo, para que siempre esté junto a sus documentos. La copia de los documentos solo agrega: lo que se pierde o cambia en el servidor no la contagia, y lo dice en su registro.
- **Revisión diaria:** también los retirados y las emitidas, y relee los de un día del mes para comprobar su huella (en 31 días, todos).
- **Pruebas:** `test_historial_completo.py` (15), los casos nuevos de `test_revisar_documentos.py`, `test_respaldos.py`, `test_permisos_bd.py`, `test_migraciones.py` y `test_cambio_de_puerto.py`, `registro.test.ts` y el E2E. Quitando de a una 49 reglas, falla alguna prueba en 47; las otras dos las frena otra barrera. La CI comprobará con contenedores de verdad que la copia conserva el dueño y que se recupera lo perdido.

## HTTPS listo para activar y PostgreSQL 18 elegible (2026-11-22)
Lo que faltaba por código «antes de producción» (CLAUDE.md, pendiente 21). Sin tocar el `.env`, un servidor de hoy sigue igual: por HTTP y con la 15.
- **HTTPS en el `.env`** (`USAR_HTTPS=true` y `APP_URL=https://<nombre>`), con el certificado en `certificados/https`:
  - `frontend/nginx/elegir-modo.sh` corre al arrancar nginx y decide dónde escucha: 8080 (HTTP) u 8443 (HTTPS) con el 8080 solo para redirigir. `nginx.conf` es el mismo en los dos modos, así que las cabeceras, los topes y las rutas no se pueden separar.
  - Redirige al nombre de `APP_URL` y no al que escribió el usuario: por la IP, el certificado no coincide.
  - Si falta el certificado, la clave, un permiso o la dirección, nginx no arranca y el registro dice qué. Volver solo a HTTP, sin que nadie se entere, sería peor.
  - TLS 1.2 y 1.3, y `Strict-Transport-Security` de un año solo por HTTPS (`map $https $hsts`: nginx no manda una cabecera vacía). Sin HTTP/2 a propósito: un envío rechazado por grande se corta distinto y el formulario no podría leer el motivo.
  - El chequeo de salud del contenedor pasó al 8081, que no sale de él: el 8080 redirige.
  - La clave privada la ve solo nginx y la CA interna (Active Directory y correo), solo el backend; las dos carpetas, de solo lectura. `certificados/` no va al repositorio.
- **Se vigila:** `vigilar.py` mira el certificado que nginx está usando (no el archivo) y avisa 21 días antes de que venza; `verificar-despliegue.sh` revisa la redirección, el nombre, la fecha, los intermedios, los permisos de la clave y si se cambió sin recargar. Con la CA interna, la vigilancia manda sus avisos por el correo con TLS.
- **Al arrancar**, el backend dice si la CA que nombra el `.env` no está (antes: «invalid CA public key file», sin decir cuál, o cada correo fallando).
- **PostgreSQL 18** en el `.env` (`POSTGRES_IMAGEN` y `POSTGRES_VOLUMEN`): su imagen guarda los datos en otra carpeta y no abre los de la 15, así que lleva su propio volumen y el de la 15 queda intacto. `verificar-despliegue.sh` comprueba que los datos estén en un volumen con nombre.
- **La CI** levanta la pila con la 15 y con la 18, carga en la 18 un respaldo de la 15, la pone por HTTPS con un certificado de prueba (entrando por el nombre y validándolo), lo cambia sin reiniciar, comprueba que la vigilancia avise y que sin la clave no arranque.
- De paso, en `verificar-despliegue.sh`: con `pipefail`, `curl | grep -q` daba por fallida una respuesta buena; lo que se busca, ahora se busca después de guardarlo.
- **Lo que encontró la CI la primera vez que levantó la pila** (commit `1d57796`): la pila arrancaba y pasaba la revisión del servidor, pero `asignar_rol --crear-local` (el primer SysAdmin de una instalación nueva) se caía al correrlo solo: «expression 'AgenciaNaviera' failed to locate a name». Las tablas se cargaban en `main.py`, y la orden de consola no lo importa. Desde ahí, importar cualquier modelo los trae todos (`app/domain/models/__init__.py`), y `tests/test_consola.py` corre cada orden de consola en un proceso aparte, como en el servidor. Su prueba de antes la llamaba desde pytest, con todo ya cargado, y no lo veía.

## Dependencias al día, tipos, cobertura y menos consultas (2026-11-22)
Lo de «Después» de la auditoría que no dependía de nadie (CLAUDE.md, pendiente 21).
- **FastAPI 0.162.7, Starlette 1.10.0, uvicorn 0.54.0 y python-multipart 0.0.33** (venían de 0.138, 1.3.1, 0.49 y 0.0.32). Se leyeron las notas de cada versión. Los cambios de FastAPI en formularios y archivos (0.147 a 0.162) no tocan los envíos: van con un campo de texto y una lista de archivos. Los topes nuevos del cuerpo y del formulario (0.164 y 0.165) vienen apagados. Se quedó en la 0.162.7, que cierra esa serie y arregla la limpieza de las dependencias con `yield` (la sesión de la base) cuando el cliente corta; las siguientes tenían días. Entra `opentelemetry-api`, que FastAPI pide desde la 0.142. Sin vulnerabilidades conocidas (`pip-audit`); pytest y el E2E pasan con el Python 3.12 de producción (`E2E_PYTHON`, nuevo).
- **mypy en la CI** (`backend/mypy.ini`). Encontró 111 avisos; ninguno era una falla en producción, pero varios dependían de que el código de antes ya lo hubiera validado (la fecha de la operación, una cuenta sin usuario en `asignar_rol`, una URL de la base sin nombre en `permisos_bd`). Quedaron explícitos.
- **La cobertura de las pruebas, con piso** (`backend/.coveragerc`): 95 %; si baja de 93 %, la CI falla. Sin `concurrency = greenlet` medía 87 %: SQLAlchemy async corre la base en greenlets y coverage perdía el rastro después de cada consulta.
- **Menos consultas por pedido** (pendiente 16): el usuario se lee una vez, con su rol y su agencia, y queda en la sesión; los permisos, una vez por pedido. Una bandeja pasó de 20 consultas a 13 o 15, y `/auth/me`, de 4 a 1. El usuario se guarda en `sesion.info` porque el mapa de identidad de SQLAlchemy guarda referencias débiles: sin eso se perdía al volver de la dependencia y se leía otra vez. Lo cuenta `tests/test_consultas_por_pedido.py`.
- **Las acciones de la CI en Node 24** (checkout, setup-python, setup-node y upload-artifact en la v7): GitHub ya las forzaba a Node 24 y avisaba en cada corrida.

## Documentación de la DTI, juego 0.7 (2026-11-23)
Los 10 documentos de `docs/`, al día con lo del 10 al 22/11/2026 (esquema `d7f3b0c5e849`). Cada uno sube un número: el 06 y el 08 a la 0.7; el 00, el 01, el 04 y el 09 a la 0.6; el 03 a la 0.5; el 02, el 05 y el 07 a la 0.4.
- **Antes de tocarlos** se volvieron a generar los de la 0.6 con sus guiones (fuera del repositorio) y el texto salió idéntico al de los Word: nadie los había cambiado a mano, así que regenerarlos no pisa nada.
- **Lo nuevo:**
  - 03: los supervisores y los sectores en la matriz, con columnas propias.
  - 04: las reglas RN-95 a RN-122, en las secciones Q a V, sin cambiar la numeración anterior.
  - 06: 72 rutas, 23 tablas y la configuración nueva.
  - 07: la vigilancia, el monitoreo externo y el QR en internet.
  - 08: los riesgos R-24 a R-27, los 29 pendientes en el orden de la auditoría del stack y 26 reglas más 19 puntos para validar con UCVMM.
  - 09: los supervisores, la boleta, la consulta histórica y el historial completo.
- **Capturas nuevas** del 01 y la 09, con la interfaz de hoy, contra la pila del E2E (base temporal, sin correos y con datos ficticios). Para que las estadísticas no salieran vacías, la historia de prueba se repartió en meses anteriores, solo en esa base.
- **Diagramas:**
  - BPMN 00, 01, 03, 04 y 05: el carril de UCVMM es el del sector del puesto, la autorización se emite y se guarda, y finaliza el puesto nuevo cuando hay cambio de puerto.
  - Mermaid: la arquitectura (HTTPS, PostgreSQL 15 o 18, vigilancia y respaldos) y el modelo de datos (sectores, boletas, versiones y autorizaciones emitidas).
- **Corrige errores que traían los documentos:**
  - El BPMN 04 seguía con el plazo de corrección de «2 días» y la vigencia «+1 día», de antes del 06/11/2026.
  - El BPMN 01 pedía «pasaporte y seamanbook vigentes» (desde el 13/11, el pasaporte con 3 meses).
  - El 07 y el 08 decían que Docker corre un solo proceso (son 2 desde el 08/11).
- **Armado:** se unieron las secciones seguidas de la misma orientación (03, 04, 08 y 09), que dejaban páginas casi vacías, y cada imagen va con su pie. Son 173 páginas.
