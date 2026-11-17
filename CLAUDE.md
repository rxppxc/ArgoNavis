# Guía para asistentes IA — ARGO NAVIS (SNM)

Este archivo se carga automáticamente al iniciar un asistente Claude Code en este repositorio. Contiene contexto que NO está obvio leyendo el código.

## Resumen en una frase

**ARGO NAVIS** (antes "NAVIS" y, al principio, "FileDrop - SNM", con el repositorio FileTransfer, renombrado a ArgoNavis el 2026-10-16) es el Sistema Interno Marítimo del Servicio Nacional de Migración (Panamá). Hoy cubre las Autorizaciones Marítimas de UCVMM: las agencias navieras envían solicitudes con el expediente de los tripulantes, UCVMM las revisa y aprueba, y el puesto de control las finaliza. Nació como storage de archivos con enlace público; se adaptó y ese storage es ahora la capa documental del expediente (sin enlaces públicos).

El nombre del sistema es «ARGO NAVIS · Sistema Interno Marítimo» (logo, pestaña del navegador, README), pensando en módulos futuros (decisión del usuario del 2026-10-16). «Autorizaciones Marítimas» es el módulo de hoy: así se llaman el trámite, el asunto de los correos y el PDF.

## Stack
- Backend: FastAPI + SQLAlchemy 2 async + PostgreSQL + LDAP/AD + JWT (`PyJWT`; hasta el 2026-10-27, `python-jose`)
- Frontend: React 19 + TypeScript estricto + Vite + CSS Modules + React Router v7
- Rate limit: `slowapi` (almacenamiento en memoria — para multi-worker mover a Redis)
- MIME real: `python-magic` (binario `libmagic` en Windows via `python-magic-bin`)
- PDF: `reportlab` (la autorización y el informe de estadísticas); Excel: `XlsxWriter` (solo escribe, desde el 2026-11-10)
- Lint: `ruff` en el backend (`backend/ruff.toml`) y ESLint en el frontend; los dos en la CI

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

En pantalla se dice **«pasajeros»** (desde el 2026-11-10; antes «tripulantes»), pero en el código, la API y la BD sigue `tripulante(s)`: es contrato (ver «Sectores, supervisión y pasajeros» en docs/HISTORIAL.md).

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
api/v1/          → endpoints (router). Solo orquestan: llaman al servicio, arman la salida y dejan la bitácora.
api/v1/dependencias.py → quién pide (obtener_id_usuario_actual, usuario_actual), qué puede (requerir_*) y auditar().
api/manejadores.py, api/middleware.py → errores que no son HTTPException; tope del cuerpo y código de pedido.
domain/services/ → reglas de negocio (validaciones, FK checks…): solicitudes, usuarios, roles, catálogos, acceso…
domain/repositories/ → único punto de acceso a la BD por agregado.
domain/models/   → ORM (SQLAlchemy 2). Tablas + relaciones.
domain/schemas/  → contratos (Pydantic). Entrada/salida HTTP.
informes/        → los archivos que arma el sistema: PDF de la autorización, estadísticas (Excel, PDF, CSV), histórico.
core/            → transversal y sin BD: config, contraseñas y JWT, LDAP, correo, rate limit, horario, identidad, texto.
infrastructure/  → engine BD y sesión, almacenamiento de documentos, tareas de fondo, trabajos pesados.
main.py          → arma la aplicación: ciclo de vida, middlewares, rutas, salud y el frontend compilado.
```
`core/` no importa de `api/` ni de `infrastructure/` (auditoría del 2026-11-14). La identidad (nombre de la institución, paleta, logos) vive en `core/identidad.py`: la usan los correos, los informes y los textos de la agencia.

**Frontend (módulos por dominio)**:
```
modulos/<dominio>/  → páginas + CSS modules de ese dominio. Solicitudes, por pantalla: formulario/,
                      expediente/, bandejas/, historico/, verificacion/; en la raíz, lo compartido
                      (presentacion, checklist, InsigniaEstado, FechaEnPalabras).
components/         → UI reutilizable entre módulos (también las guardias de ruta, RutasProtegidas,
                      y los vigilantes de sesión y de versión).
context/            → providers globales (tema, autenticación, permisos).
hooks/              → hooks compartidos (useAutenticacion y usePermisos leen de sus providers).
api/                → cliente HTTP + módulos por dominio.
constants/          → números mágicos.
utils/              → funciones sin React (fechas, texto sin tildes, archivos, errores…), con sus pruebas.
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
9. Rate limit en `/auth/login`, `/auth/cambiar-contrasena`, `/verificacion/{codigo}` y su `/autorizacion.pdf` (los únicos endpoints públicos, con el login) — si agregas otro endpoint público, agrégalo, y súmalo a la lista de `test_solo_estas_rutas_responden_sin_sesion` (`tests/test_seguridad.py`), que falla con cualquier ruta sin token que no esté ahí.
10. Los documentos del expediente solo se sirven con sesión, validando acceso a la solicitud (`ServicioSolicitud.obtener_documento`) y dejando DOCUMENTO_VISTO/DESCARGADO en la bitácora. **Nunca** vuelvas a exponer archivos por token o enlace público.
    - La única excepción es el **PDF de la autorización**, que no es un documento del expediente: lo arma el sistema. Desde el 2026-11-14 quien escanea el QR lo ve sin sesión (`GET /verificacion/{codigo}/autorizacion.pdf`, decisión del usuario). Es la copia de la agencia, sin nombres de funcionarios ni nada interno. Se ve mientras la autorización valga y hasta `DIAS_PDF_PUBLICO` días después de la operación, con tope por IP y en la bitácora (ver «Cambios del 2026-11-14» en docs/HISTORIAL.md). No le agregues lo interno, y no abras así ningún otro archivo.
11. Separación de funciones: nadie revisa (impedimentos, aprobar, devolver, negar) una solicitud que creó o que es de su agencia. No la quites "para probar": usa dos cuentas.
    - Y cada sector de UCVMM ve y revisa solo las solicitudes de los puestos de su sector (2026-11-10). No lo abras "para probar": asigna el usuario a los dos sectores.
12. El login responde lo mismo si el usuario no existe y si la contraseña está mal (`ErrorAcceso` en `auth_service.py`); el motivo real va solo a la bitácora. No vuelvas a distinguirlos: revela qué cuentas existen en el AD.
    - Al AD solo se le pregunta por cuentas del AD **registradas y activas en ARGO NAVIS** (`ServicioAutenticacion._login_ad`). No vuelvas a consultarlo antes de esa comprobación: ARGO NAVIS serviría para probar contraseñas de cualquier cuenta del SNM (con la correcta respondía "no tienes acceso") y para bloquearlas.
    - El freno de las cuentas del AD vive en la BD (`users.intentos_fallidos` / `bloqueado_hasta`, las columnas del bloqueo de las locales) y la fila queda bloqueada durante el login (`RepositorioUsuario.buscar_para_login`, FOR UPDATE). No lo pases a memoria: con varios workers o pedidos en paralelo, al AD le llegarían más intentos (`test_freno_del_ad_con_intentos_en_paralelo`).
    - `LOGIN_AD_MAX_FALLOS` va por debajo del umbral de bloqueo del dominio y `LOGIN_AD_MINUTOS_ESPERA` es mayor o igual que su ventana de restablecimiento.
    - Se acepta que el freno (429) y el bloqueo de las locales (423) delaten que la cuenta existe en ARGO NAVIS: no revelan el directorio del AD.
13. nginx **reemplaza** `X-Forwarded-For` con `$remote_addr` (el backend confía en esa cabecera para el rate limit y la bitácora). No vuelvas a `$proxy_add_x_forwarded_for`: el cliente podría inventarse la IP.
14. Lo que sube una agencia es **no confiable**: entran por la VPN, pero no son del SNM. El Word se previsualiza en un `<iframe sandbox="">` con su propia CSP, sin enlaces, sin altChunks y con las imágenes como `data:` (`ModalPreview.tsx`). **Nunca** pintes en la página HTML que salga de un documento (docx-preview directo en el DOM, `dangerouslySetInnerHTML`): un enlace `javascript:` dentro de un .docx corría en ARGO NAVIS con la sesión de quien revisaba.
15. CSP en `frontend/nginx.conf` y en `_CABECERAS_SPA` (`backend/app/main.py`), iguales: si cambias una, cambia la otra. Solo código propio: nada en línea, nada de CDN, nada que use `eval` o `new Function`. Si una librería lo necesita, busca otra; no aflojes la CSP.
16. Crear y corregir solicitudes (lo que sube archivos) tienen tope por cuenta: `@limiter.limit(limite_envios, key_func=clave_usuario)` y `LIMITE_ENVIOS_POR_HORA`. Un endpoint nuevo que suba archivos lleva el mismo decorador.
    - Y entra en `_RUTA_DE_ENVIO` (`api/middleware.py`) y en el `location` de los envíos de `frontend/nginx.conf`: el resto de la API admite cuerpos de 1 MB (`TopeDelCuerpo`, 2026-11-10).
17. En producción el backend no arranca con una `SECRET_KEY` de menos de 32 caracteres o de ejemplo (validador en `core/config.py`).
18. Los servidores de desarrollo escuchan solo en este equipo (`start-backend.bat` en 127.0.0.1, Vite en `localhost`): no tienen las protecciones de producción. `VITE_HOST=0.0.0.0` solo para probar desde otro equipo, y por un rato.
19. La aplicación entra a PostgreSQL con **su propia cuenta** (`DATABASE_URL`, en Docker `argonavis_app`), no con la dueña de las tablas ni con un superusuario (2026-11-08):
    - La crea y la pone al día `infrastructure/permisos_bd.py` después de cada migración, con la dueña (`MIGRACIONES_DATABASE_URL`, que el entrypoint borra antes de levantar uvicorn).
    - Lee y escribe filas, pero no crea ni cambia tablas ni ejecuta programas del servidor (`COPY ... TO PROGRAM`).
    - `audit_logs` y `solicitud_eventos` son **solo para agregar** (sin UPDATE ni DELETE): la bitácora y el historial no se pueden tapar desde la aplicación. Las FK con `ON DELETE SET NULL` las aplica PostgreSQL con la dueña, así que borrar un usuario funciona igual.
    - `boletas_recargo` (2026-11-16) va **sin borrar** (`TABLAS_SIN_BORRAR`: sin DELETE ni TRUNCATE): una boleta se anula, nunca se borra.
    - No conectes la aplicación como dueña ni le des UPDATE o DELETE sobre esas tablas. Una tabla nueva que necesite otro trato va en `TABLAS_SOLO_AGREGAR`, `TABLAS_SIN_BORRAR` o `TABLAS_SIN_ACCESO`.
    - Lo prueban `tests/test_permisos_bd.py` y el E2E, cuyo backend entra con una cuenta así (`servidor_e2e.py`).

### Errores
- Backend: `HTTPException` con código y `detail` descriptivo. Nunca `except: pass`. Loggear con `logger.warning/.error` con contexto.
- Cada pedido lleva un código (`X-Request-ID`, middleware `CodigoDePedido` en `api/middleware.py`, 2026-11-08). Va en cada línea del log (`[%(pedido)s]`, `core/registro.py`), en la respuesta y en el cuerpo de los 5xx (`codigo`), que el frontend agrega al mensaje (`mensajeDeError`). Para un error reportado, busca su código en el log: ahí está la traza. Un error sin controlar lo registra el middleware, con la traza, y responde 500 con el código.
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
- `noUnusedLocals` y `noUnusedParameters` están encendidos: lo que no se usa, se borra.
- `eslint-plugin-react-hooks` en exhaustive deps. Si quitas una dep, deja `// eslint-disable-next-line` con el porqué.

### Identidad «pase oficial» (elegida por el usuario el 2026-11-11)
Pedido del usuario: «el diseño es genérico, típico de IAs; necesitamos identidad». Entre tres propuestas (carta náutica, pase oficial y código de señales) eligió **la B, «pase oficial», con el fondo de hoy**: cada pantalla como un documento oficial sobre la carta celeste (`FondoPagina`, que no cambia, con su animación en el login).
- **Letras propias**, servidas por el propio servidor (`@fontsource`, importadas en `App.tsx`; licencia OFL; la CSP no cambia):
  - Archivo extendida en títulos, rótulos y botones (`--letra-titulo`, `--ancho-titulo` / `--ancho-etiqueta`);
  - Public Sans en el texto (`--letra-texto`);
  - IBM Plex Mono en números de documento, cifras y la línea mecánica (`--letra-mono`).
  - Solo se baja el subconjunto latino (~160 KB, en caché). **No vuelvas a Segoe UI ni a fuentes de un CDN.**
- **Tokens nuevos** (`globals.css`): `--franja` (el amarillo del escudo, `#FFE400` en claro), `--guilloche` / `--guilloche-oro` (ondas de seguridad en SVG), `--principal` / `--sobre-principal` / `--principal-hover`, `--celeste-texto`, y esquinas casi rectas (`--r-*`, de 3 a 10 px).
- **Piezas:**
  - Cabecera blanca en claro y marino en oscuro: franja amarilla arriba, guilloche detrás, escudo, institución, marca ARGO NAVIS y una línea de microtexto decorativa. Pie marino con la franja, igual en los dos temas. Se quitó la franja de la bandera de la cabecera.
  - Estados como **sellos de tinta** (`InsigniaEstado`: doble borde, mayúsculas; `inclinado` en el talón del pase). El color de cada estado no cambia.
  - Bandejas: cada solicitud es un **pase con talón perforado** (`TarjetaSolicitud`). Las muescas son una máscara en el `.pase` interior: el anillo de foco va en el enlace exterior, porque la máscara lo recortaría.
  - Expediente: la **cabeza del documento** (franja, rótulo, trámite, «N.º» y el sello grande ladeado), las secciones de la columna principal numeradas con contadores de CSS (`content: counter() / ""`, que el lector de pantalla no lee), los datos con su rótulo encima y el valor sobre la línea, y al pie la **línea de lectura mecánica** de los pasaportes (`lineasMecanicas`, decorativa, `aria-hidden`).
  - Login: un **pasaporte abierto** sobre la carta animada: la tapa marino con guilloche dorado y el emblema de ARGO NAVIS, y la hoja con el acceso.
  - Modales, resumen de estadísticas y tarjetas sueltas: la franja amarilla arriba. Pestañas como separadores de expediente; desde el 2026-11-17 la activa va rellena (abajo).
  - **Avisos emergentes «sello centrado»** (elegidos por el usuario el 2026-11-11, entre «sello», «comprobante», «cinta» y dos mezclas): una cinta centrada bajo la cabecera, del ancho de su mensaje (hasta 860 px), con el sello de tinta del resultado a la izquierda. En el celular va de borde a borde, con el sello y la X arriba (`Notificaciones.tsx`; lo que no es React, en `avisos.ts`, con sus pruebas).
    - **El sello:**
      - si la acción cambió el estado de una solicitud, el de ese estado, en el color de su insignia: ENVIADA, REENVIADA, DEVUELTA, APROBADA, DENEGADA o FINALIZADA (`mostrar(texto, "exito", { sello: "devuelta" })`);
      - si no, el del tipo: LISTO, REVISA (validaciones, en tinta con el amarillo de la franja), NO SE PUDO y AVISO.
    - **El número de solicitud** del texto va en letra de máquina y sin partirse; la hora («10:30 a. m.») tampoco se parte.
    - **El tiempo:** 4 s los éxitos, 6 s los que llevan sello y 10 s los errores y las validaciones. Una barra lo muestra y se detiene con el mouse encima o con el foco adentro. El aviso se cierra cuando la barra termina su animación.
      - Por eso la barra lleva `data-movimiento`: con «reducir movimiento», la regla global la dejaría en 0 s y el aviso se cerraría al aparecer.
      - Lo prueban `formulario.spec.ts` (con `reducedMotion`) y `flujo-completo.spec.ts` (la pausa con el mouse).
    - **Cuántos:** como mucho tres, el más nuevo arriba; uno repetido no se apila.
    - **Ubicación:** justo bajo la cabecera, que se mide (`data-cabecera`). Así no tapan la campana, el menú, el «Volver» ni el panel de decisión. Si la cabecera ya no se ve, van arriba.
    - **Lector de pantalla:** dos regiones siempre presentes, `alert` (errores y validaciones) y `status` (éxitos).
    - Un archivo que no cumple (formato o 2 MB) es una validación (REVISA), no un error.
    - Un aviso puede llevar un botón junto a «Cerrar» (`accion`): lo usa el de la versión nueva («Recargar», ver «Cambios del 2026-11-11» en docs/HISTORIAL.md).
- **Reglas:**
  - El guilloche va solo en lo que identifica a un documento (cabecera, cabeza del expediente, tapa del pasaporte, hoja del login): sobre la carta del fondo, dos texturas juntas ensucian.
  - El amarillo sigue siendo relleno. La única excepción como texto es la tapa del pasaporte: dorado sobre marino, 10:1.
  - Las mayúsculas son siempre de CSS (`text-transform`): el texto leído y los nombres accesibles no cambian, y el E2E los busca tal cual.
- Maquetas y capturas de la elección: en el scratchpad de la sesión (`diseno/`).

### Rediseño visual «B + C» (elegido por el usuario el 2026-11-17)
Pedido del usuario: «en el modo claro hay cosas que no se distinguen»; «que cualquier persona lo entienda, no se pierda ni se frustre»; «todo: cada card, ícono, bandeja, select…». Vio maquetas sobre las pantallas reales y eligió la mezcla de **B** («Color que guía»: cada estado con su color y «Qué sigue») y **C** («Documento oficial»: títulos de sección en marino). Se aplicó con tokens y piezas compartidas, sin cambiar la identidad «pase oficial».
- **Tokens nuevos** (`globals.css`, en los dos temas):
  - `--seccion-fondo` / `--seccion-texto`: la barra de los títulos;
  - `--estado-<estado>` y `--estado-<estado>-tinte`: los seis estados, con el color de su insignia;
  - `--desactivado-*` y `--nota-*`.
- **Claro más contrastado:** fondo #E3EBF3, líneas #C8D4E1 / #A9B9CC, textos secundarios más oscuros y sombras marcadas.
- **Contraste:** lo comprueba `styles/contraste.test.ts`, en los dos temas (texto ≥ 4.5:1; borde de campos, estados y notas). **Un color nuevo pasa por esa prueba**: ya no se recalcula a mano.
- **Títulos de sección:** una barra marino con el número en la franja (`styles/Secciones.module.css`: `barra`, `numero`, `contador`).
  - Cada módulo la compone; su tarjeta declara el relleno en `--relleno-y` / `--relleno-x`.
  - Un botón dentro de la barra usa `sobreSeccion` (`Botones.module.css`).
  - Los modales usan `modalTitulo`, sin barra.
- **Lo elegido, relleno:**
  - pestañas de estado, filtros de fecha y de sector, «Día · Mes · Año», catálogos y el selector de bandeja: con `--principal` (marino en claro, amarillo en oscuro);
  - cada pestaña de estado lleva el punto de su color (`data-estado`, decorativo).
- **Pases de las bandejas:** el borde izquierdo y el talón llevan el color de su estado (`data-estado` en el `.pase`).
  - La muesca se corre 6 px por ese borde (`--muesca`).
  - La sombra va en el enlace con `drop-shadow`, porque la máscara recortaría una `box-shadow`.
- **«Sin / Con»:** el elegido va relleno en verde o rojo, con su marca (✓ / !).
- **Lo desactivado va rayado, con borde punteado:** en gris liso se confundía con «Desactivar», que sí funciona.
- **«Qué sigue»** en el expediente (`QueSigue`, con la lógica en `pasosSiguientes.ts` y sus pruebas): los pasos de quien mira, según su rol y el estado, con los hechos marcados.
  - Sin nada que hacer, no se muestra.
  - Lo que lee la agencia no nombra a UCVMM.
- **Formulario:**
  - el indicador de avance de los 4 pasos (`AvanceFormulario`, con la lógica en `pasosDelFormulario.ts`), fijo arriba y con un enlace a cada sección;
  - las casillas pendientes van en naranja y las cubiertas en verde;
  - «Adjuntar» va en azul.
- **Bitácora:** las etiquetas de cada acción llevan el color de su categoría (`categoriaAccion.ts`), y los rótulos y botones son los del resto.
- **Rótulos más grandes y menos espaciados:** de .6–.66rem a .68–.74rem.
- **La tabla de pasajeros** lleva el pasaporte y el seamanbook en una columna. Antes, en el puesto, la del impedimento quedaba fuera de la vista.
- **Un solo ancho de página** (1240 px, `MarcoPagina`). `angosto` se queda para la contraseña y el 404.
- Maquetas, capturas de antes y después y el script que las toma (contra la pila del E2E, sin correos): en el scratchpad (`visual/`).

### Interfaz (revisión de UI/UX del 2026-10-19)
- **Paleta SNM** (pedido del usuario del 2026-10-19: «basate en los colores del logo y en el estándar de la página web»). Sale del escudo (amarillo `#FFE400`, negro, celeste `#15B0DE`) y de los tokens propios de migracion.gob.pa (`--snm-*`):
  - Marino `#10233F` / `#17283E` para los textos, azul institucional `#003DA5`, amarillo `#F2C94C` (hover `#FFD633`), líneas `#DCE4ED` / `#CAD5E1`, fondos `#F6F9FC` / `#EEF4F8` y crema `#FFF8D8`.
  - El tema claro es el de la web. El oscuro, la pizarra de su cabecera. El detalle, con cada valor y su contraste, está en el comentario de `styles/globals.css`.
  - Cabecera y pie: desde el 2026-11-11, los de la identidad «pase oficial» (arriba). Sus textos van en `--cabecera-texto*` / `--pie-texto`, no en `--text`.
  - El foco va en azul institucional en claro y en amarillo en oscuro, también sobre la cabecera (`--foco`).
  - Sin colores fijos en los CSS: los tintes de estado se arman con `color-mix(in srgb, var(--acc-*) N%, transparent)`. Quedan fijos solo la hoja del visor de documentos y la barra del navegador, que sigue a la cabecera de cada tema (`#FFFFFF` / `#131E2B`: `index.html`, `tema-inicial.js` y `ContextoTema.tsx`).
- El amarillo de marca (`--y`) es solo **relleno**: la franja, lo seleccionado (pestaña, filtro, tema), el foco en oscuro y, en oscuro, el botón principal. **Nunca como color de texto** (en claro da 1.6:1 y el dorado se ve oliva): textos con `--text` / `--text-2` / `--muted`, estados con `--acc-*`. Sobre el amarillo, texto marino (`--on-accent`), como los botones de la web.
- Cada acción con su color (pedido del usuario del 2026-10-22), definido en `Botones.module.css`. En las solicitudes, el color es el de la insignia del estado al que lleva:
  - azul: consultar (ver, descargar, buscar, editar, asignar);
  - verde: aprobar, activar;
  - verde azulado: finalizar;
  - naranja: devolver a corrección, corregir;
  - gris: desactivar;
  - morado: restablecer una contraseña;
  - rojo: denegar, eliminar, quitar.
  
  Relleno para la acción que decide; contorno teñido (`.tono` con `--tono`) para las de una fila. Un naranja de contorno junto a uno rojo no se distingue en claro: por eso «Devolver» lleva relleno y «Desactivar» va en gris. El modal de confirmación toma el color con `tono`.
- Botones (en mayúsculas de Archivo desde el 2026-11-11): principal marino en claro y amarillo en oscuro (`--principal`); secundario con borde de tinta; aprobar con `--exito-fuerte`, denegar/eliminar con `--peligro-fuerte` (o contorno rojo); "Volver" sólido (`--card` con borde: sobre el fondo decorativo, transparente no se leía). Desactivado rayado con borde punteado (desde el 2026-11-17; antes, gris liso), no amarillo a media opacidad. En `useConfirmar`, `peligroso` (rojo) o `exito` (verde) según la acción.
  - Un botón principal no se desactiva porque falten datos: al pulsarlo dice qué falta (gris y sin explicación no se entendía, 2026-10-22). Se desactiva solo mientras guarda, o cuando al lado dice por qué (revisión de UCVMM).
- Fondo «carta celeste» entre la cabecera y el pie, en todas las vistas y el login (`FondoPagina`, elegido por el usuario el 2026-10-22). Es decorativo y tenue a propósito, porque cruza títulos y botones. `.medio` lleva `overflow: clip`, no `hidden`: con hidden deja de funcionar el panel fijo de la revisión.
  - Solo en el login tiene movimiento (`animado`), con la variante «rutas vivas» que eligió el usuario el 2026-10-23: las rutas se trazan al entrar, las recorren luces doradas y las estrellas laten. En las pantallas de trabajo no se anima, para no distraer.
  - Sin haz de faro ni giro del astrolabio: mueven capas del tamaño de la pantalla y, en equipos sin tarjeta gráfica, el login caía a 22 cuadros por segundo.
  - Estrellas y luces son elementos HTML que mueve la tarjeta gráfica, no parte del SVG: solo se animan transform y opacity, y las luces van con Web Animations y cuadros clave en cada vértice (`RutasVivas`). El lienzo copia el encuadre del SVG (1600×900, «xMidYMid slice»).
  - Dentro del SVG, el navegador redibujaba toda la pantalla en cada cuadro: el login usaba más de un núcleo entero contando todos sus procesos (el «~13 %» de antes era solo el hilo de la página). Así, ese hilo queda en ~1 % y la animación suma ~20 puntos de un núcleo con tarjeta gráfica y ~45 sin ella, a 60 cuadros por segundo (medido el 2026-10-26). **No vuelvas a animar dentro del SVG.**
  - Se mueve aunque el equipo pida «reducir movimiento» (decisión del usuario del 2026-10-23: muchos equipos del SNM traen las animaciones de Windows apagadas y no se veía nada). Para eso, `data-movimiento` lo saca de la regla global de `globals.css`.
  - Sin botón de pausa: el usuario lo quitó el 2026-10-23. La WCAG 2.2.2 pide uno para lo que se mueve solo más de 5 s; se aceptó porque es solo el login. Si el movimiento pasa a otras pantallas, el botón vuelve.
- "En corrección" va en naranja (`--acc-orange`): el ámbar se confundía con la marca.
- Encabezado de página: `EncabezadoPagina` (título y descripción a la izquierda, acciones a la derecha); el expediente lleva el suyo.
- Campos con `--input-border` / `--input-bg` (borde de 3:1). Las notas informativas, en azul (`--nota-fondo` / `--nota-borde`, desde el 2026-11-17) con borde izquierdo `--acc-blue`.
- Texto libre que escribe un usuario (observaciones, motivos, comentarios, nombres de archivo y de buque): con `overflow-wrap: anywhere`, para que una palabra larguísima sin espacios corte la línea en vez de salirse de su caja (2026-11-08; el `body` lleva `break-word` por defecto). Lo prueba `sinTextoDesbordado` en `e2e/flujo-completo.spec.ts`, que falla con los estilos anteriores.
- Revisión de UX del 2026-11-08 (40 pantallas por rol, en claro, oscuro y celular):
  - Bajo cada campo de fecha del formulario va la fecha en palabras (`FechaEnPalabras`: «jueves, 13 de noviembre de 2026»). El navegador muestra la fecha en su propio formato (en un Windows en inglés, mm/dd/aaaa), y así no se confunde el día con el mes. Va con `aria-hidden`, para no cambiar el nombre del campo.
  - Los ejemplos dentro de un campo empiezan con «Ej.» («Ej. IMO 9074729»): sin eso parecían un dato ya cargado.
  - El panel del puesto va en tres pasos numerados (verificar, comentario, finalizar), con el plazo arriba. Antes eran tres párrafos seguidos en la columna angosta.
  - En «Usuarios», cada bloque dice qué hace («Agregar un funcionario del Active Directory», «Crear una cuenta local…»), y la tabla tiene un filtro.
  - La sección 4 del formulario se llama «Resumen de documentos» cuando el trámite no pide documentos generales. Antes decía «no pide documentos» junto a «0 / 3 en total».
- Tablas que en el celular pasan a fichas: cada `<td>` lleva `data-etiqueta` (tripulantes del expediente, usuarios).
- Accesibilidad (2026-10-27):
  - Enlace «Saltar al contenido» (clase global `.saltar-contenido`) en `MarcoPagina` y en el login, hacia `<main id="contenido">`.
  - Los íconos son decorativos (`aria-hidden` en `crearIcono`). Todo botón de solo ícono lleva `aria-label` con qué hace y sobre qué: «Ver informe.pdf», «Quitar tripulante 2».
  - Errores y avisos quedan 10 s en pantalla; éxitos e informativos, 4 s, y 6 s los que llevan el sello de un estado (`Notificaciones`, diseño «sello centrado» del 2026-11-11, en «Identidad»).
- Si cambias un color, corre `styles/contraste.test.ts` (los tokens, en los dos temas). Y recalcula a mano los fondos teñidos con `color-mix`, que esa prueba no ve (insignias, avisos, contadores).
- El correo (`core/email.py`) y el PDF (`informes/autorizacion_pdf.py`) usan la misma paleta (`core/identidad.py`) (2026-10-20). El color de cada estado es el de su insignia (`InsigniaEstado`): recibida en azul, aprobada en verde, devuelta en naranja, denegada en rojo, expirada en gris y, en el PDF, finalizada en verde azulado.
- Revisión de UCVMM (propuesta 1A, elegida por el usuario el 2026-10-19):
  - Los impedimentos se marcan en una columna Sin / Con de la tabla de tripulantes (`SeccionTripulantes`). El estado vive en `useVerificacionImpedimentos`, que lo comparte con el panel de decisión (`PanelRevision`).
  - La columna lateral queda fija al bajar (sticky, 300 px) y cada decisión es un solo modal (`ModalDecision`).
  - `ModalDecision` va en un portal al `body`: dentro del sticky quedaba debajo de la cabecera.
- Paso 1 de «Nueva solicitud» en tarjetas (`SelectorTramite`, propuesta 2A): la descripción sale del catálogo y lo que pide, del checklist. Cambiar de trámite con archivos ya adjuntos pide confirmación (se quitan).
  - Cada trámite tiene ícono y color propios (`PRESENTACION`, por código, en el frontend): mosaico sólido en un `--acc-*` con el ícono en `--card`. Con todos en gris no se distinguían (pedido del usuario del 2026-10-19). En la grilla, los colores vecinos no se parecen.

## Estado actual (2026-11-16)

El sistema cubre el ciclo completo de las Autorizaciones Marítimas: la agencia envía, UCVMM revisa por sector y el puesto de control finaliza. Tiene además:
- supervisión y consulta histórica;
- el recargo por atención fuera del horario laboral y su boleta, con el tipo de operación en casillas (2026-11-16);
- «¿Subir y bajar?» en Embarque y Desembarque, con la Carta Form. 7 de cada pasajero, y la ocupación fuera del formulario (2026-11-16);
- estadísticas con exportación a Excel, PDF y CSV;
- la verificación pública del PDF por el QR;
- la identidad «pase oficial».

**Qué se hizo, cuándo y por qué está en [docs/HISTORIAL.md](docs/HISTORIAL.md)**, una sección por revisión, del storage original a la auditoría del 2026-11-14. Aquí quedan las reglas vigentes.

### Reglas aprendidas (no se ven leyendo el código)
Cada una salió de un problema real. El detalle está en el historial.

**Base de datos y alcance**
- Filtra por fecha como un rango de instantes (`entre_fechas_panama`, `core/horario.py`).
  - **Nunca** uses `date(timezone(...))` sobre la columna: así PostgreSQL no usa el índice.
  - Para agrupar por día sí se usa (`_fecha_panama`).
- La cantidad de procesos × (`BD_POOL` + `BD_POOL_EXTRA`) tiene que quedar por debajo de `max_connections` de PostgreSQL.
- El horario laboral vive en `core/horario.py` y en SQL (`_fuera_de_horario`). Tienen que coincidir (`test_horario.py`).
- Las alertas de la bandeja se cuentan en SQL (`alertas_de`) y las del expediente en Python (`_vencimientos_tripulante`).
  - Si cambias una, cambia la otra (`test_la_bandeja_cuenta_las_alertas_como_el_expediente`).
- La consulta histórica (`_alcance_historico`, en SQL) y el expediente (`puede_ver`) tienen que ver exactamente lo mismo.
  - `test_cada_uno_ve_lo_suyo` lo prueba en las dos direcciones.
- Una bandeja, consulta o estadística nueva de UCVMM filtra por el sector (`ContextoAcceso`, `domain/services/acceso.py`).
- Las rutas fijas de `/solicitudes` (`/historico/opciones`, `/estadisticas`…) van antes de `/{solicitud_id}` en el enrutador.
- La consulta histórica y su exportación son POST, con el cuerpo: el pasajero (un dato personal) no va en la URL ni en los logs de acceso.

**Correos, logs y tareas**
- Cada correo se toma con `FOR UPDATE SKIP LOCKED` (`RepositorioCorreo.tomar_pendiente`), en su propia transacción.
- Los avisos se encolan en la transacción de la operación (`encolar_avisos`).
- Los logs en archivo van uno por día, y el archivo nunca se renombra (`ArchivoDiario`, `core/registro.py`).
  - **No uses `RotatingFileHandler`:** en Windows falla con varios procesos.
  - Tampoco el modo `"a"` de Python: pierde líneas.
- Un trabajo de cientos de ms de CPU (PDF, Excel) va por `en_hilo_con_tope` (`infrastructure/trabajo_pesado.py`), no por `asyncio.to_thread`.
  - Suelta antes la conexión (`await sesion.commit()`).
- Desde la API, la bitácora se anota con `auditar()` o `auditar_admin()` (`api/v1/dependencias.py`), que agregan la IP y el navegador.

**Despliegue y dependencias**
- Python se instala desde `requirements.lock` con `--require-hashes`.
  - **No vuelvas a instalar desde `requirements.txt`:** ese es el que se edita, y después se regenera el bloqueo.
  - Node se instala con `npm ci`.
- Las imágenes Docker llevan la versión exacta, también en la CI (`test_dependencias.py`).
- El respaldo de los documentos es incremental (`backup.sh`, `cp -al`).
  - **No vuelvas al tar de todo:** llena el disco que comparte con PostgreSQL.
  - Sirve porque los documentos no se modifican.
- Si agregas algo que el despliegue necesite (una variable, un servicio, un puerto), súmale su chequeo a `verificar-despliegue.sh`.
- Los topes del cuerpo (`api/middleware.py`) y los de nginx tienen que coincidir (`test_nginx_tiene_los_mismos_topes_que_el_backend`).
  - Si el catálogo pide más documentos, sube `MAX_DOCUMENTOS_*` y los dos topes.

**Frontend**
- **No borres `ultima-actividad` al cerrar sesión:** las otras pestañas lo leerían como 15 minutos sin actividad.
- La campana no cuenta como actividad.
- Un enlace nuevo al expediente lleva su `state` (`estadoParaVolver`, `utils/volver.ts`): así «Volver» regresa a donde se abrió.
  - El pasajero de la consulta histórica viaja en ese estado.
- Un texto nuevo que vea la agencia no nombra a UCVMM ni a los sectores (`INSTITUCION`, `core/identidad.py`).
  - Lo prueban `test_ciclo_completo` y `sinUnidadesInternas` (E2E).
- En las celdas de una tabla va `overflow-wrap: break-word`; `anywhere`, solo en los bloques de texto libre.
- Nada de sitemap, canónico, imagen OG ni `llms.txt`: es un sistema interno y nada debe indexarse.
- Vitest se corre desde `C:\…` en mayúscula: con `c:\…` carga dos copias de sí mismo.
- Una acción nueva de la bitácora (`AccionAuditoria`) lleva su nombre en `ETIQUETA_ACCION` (`PaginaBitacora.tsx`): sin él, se ve el código crudo (`test_la_bitacora_nombra_todas_las_acciones`).

**Pruebas**
- Las pruebas que simulan la hora reemplazan `solicitud_service.ahora_utc`.
  - Lo que dependa de la hora vive en ese módulo: por eso el servicio no se partió en varios.
- Las variables que apagan el AD, el correo y los logs de las pruebas están en un solo lugar: `tests/entorno_pruebas.py`.
  - Lo usan `conftest.py`, `servidor_e2e.py` y `carga.py`.
  - Una configuración nueva que en las pruebas tenga que quedar apagada va ahí.
- Las ayudas comunes (enviar, verificar impedimentos, `login`, `panama`) están en `tests/ayudas.py`.

### Lo que sigue pendiente (no urgente)
1. **HTTPS y TLS con el AD** — la configuración está lista (README → "Producción"); falta el certificado del servidor y el del controlador de dominio (infraestructura).
2. **JWT en cookie httpOnly** — actualmente en localStorage, con la CSP como barrera (regla 15). Plan en README → "Decisiones documentadas".
3. **Redis para rate limit** si se escala a varios hosts (en un host con varios workers el límite es por proceso).
4. **Refactor de componentes grandes** — el expediente (2026-10-19), el formulario (2026-10-21) y `PaginaUsuarios` (2026-11-14) ya se partieron; `PaginaCatalogos` ya está hecha de componentes. Queda, si hace falta, `solicitud_service.py` (~1500 líneas): partirlo exige que lo que depende de la hora siga en un solo módulo (las pruebas reemplazan `ahora_utc` ahí). Y los estilos de los campos repetidos en varios CSS: juntarlos pide cambiar la marca de los formularios y una revisión visual.
5. **Edición del catálogo de trámites desde la UI** — hoy se ajusta con migraciones.
6. **Solicitud de Custodia y Solicitud de Transbordos** — el documento de UCVMM dice que faltan por levantar; no están modeladas.
7. **Política de retención de datos personales** — decisión del equipo.
8. **Segundo factor (TOTP) para las cuentas de las agencias** — decidido para más adelante (2026-10-16).
9. **Antivirus (ClamAV) para los archivos subidos** — por ahora no (2026-10-16); necesita el servicio en el servidor.
10. **Importar tripulantes desde una plantilla Excel** (propuesta 3 de la revisión de UI) — por ahora no (2026-10-19). Con el tope de 30 tripulantes (2026-10-30), pesa menos.
    - Vale la pena si las tripulaciones suelen ser grandes. Para decidir: `SELECT count(*), round(avg(cantidad_tripulantes), 1), max(cantidad_tripulantes), count(*) FILTER (WHERE cantidad_tripulantes > 10) FROM solicitudes;`.
11. **FastAPI, Starlette y uvicorn** (de la revisión del 2026-10-27; el resto de sus errores ya se corrigió). Sin avisos en las versiones instaladas, no se subieron.
    - Entre la 0.143 y la 0.162 (del 8 al 23/10/2026), FastAPI cambió cómo lee formularios, archivos y cuerpos, que es justo el envío de solicitudes; la 0.162 revierte parte de la 0.147.
    - Subirlas cuando se asiente: solas, y probando el envío (pytest y E2E).
12. **De la reunión del 2026-10-30, para más adelante:** los feriados en el horario laboral (necesitan un catálogo que mantenga el Administrador) y la notificación de Windows de la campana (el navegador pide permiso).
13. **Validar con UCVMM:** el aviso de custodia al aprobar no es un documento, así que sigue saliendo para todos los rangos; a los no marinos ya no se les pide el Form. No. 6. Confirmar si les aplica.
14. **Respaldos fuera del servidor** (de la revisión del 2026-10-27). Hoy `backup.sh` es solo para Docker y deja todo en el mismo servidor; se copian con `rsync -aH` (README). Desde el 2026-11-10 es incremental y la restauración está documentada y probada con una base temporal; falta probarla entera en el servidor de pruebas.
15. **De la auditoría del 2026-11-08, para decidir:**
    - Retención de la bitácora (`audit_logs`): es la tabla que más crece (cada documento visto, cada login) y no se purga. Va con la política de retención (punto 7).
    - Búsqueda por texto de las bandejas y la bitácora: `ILIKE '%…%'` recorre la tabla. Con muchos miles de filas, un índice trigram (`pg_trgm`) la acelera; hoy no hace falta.
    - Lo mismo la consulta histórica (2026-11-11): busca pasajeros con `ILIKE` y filtra por `fecha_operacion`, que no tiene índice.
    - Tope global del login y de la verificación en nginx (`limit_req`): el de slowapi es por proceso. Antes, confirmar si las agencias salen de la VPN con una sola IP (las frenaría a todas juntas).
16. **Menos consultas por pedido, si crece el uso** (prueba de carga del 2026-11-08). Hoy cada pedido hace 6 consultas solo para saber quién es el usuario:
    - `obtener_id_usuario_actual` y `usuario_actual` leen el mismo usuario dos veces;
    - los permisos se consultan en cada pedido (a veces dos veces);
    - el expediente vuelve a leer el catálogo (trámites, documentos y países) y carga `creada_por` con su rol y su agencia.
    Juntar la verificación del token con la carga del usuario y cachear el catálogo por proceso ahorraría entre 10 y 20 %. Correr `tests/carga.py` antes y después.
17. **Documentación de la DTI, juego 0.7:** `docs/` no tiene todavía la identidad «pase oficial» ni los cambios del 2026-11-11 (documentos de los técnicos, nombre neutro para la agencia, costo fuera del horario y consulta histórica), del 2026-11-13 (cambio de puerto, Formulario No. 3 en todos los trámites, cabecera de la agencia, rango Pasajero, pasaporte con 3 meses) del 2026-11-14 (la Visa de los restringidos, los panameños, Shore Pass, quien finalizó y el PDF por el QR) y del 2026-11-16 (la boleta de recargo con el tipo de operación, el alcance del supervisor general, «¿Subir y bajar?» con la Carta Form. 7 y la ocupación fuera del formulario), ni el rediseño visual «B + C» del 2026-11-17 (las capturas de los manuales quedaron con el diseño anterior).
18. **Recargo fuera del horario, con UCVMM:**
    - La boleta (2026-11-16) es un **borrador**: UCVMM tiene un modelo en papel, que el usuario pasará para copiarlo tal cual (`informes/boleta_recargo_pdf.py`).
    - El sistema no registra el pago ni dice dónde se paga (desde el 2026-11-11).
19. **Del 2026-11-13, para decidir o validar:** si el Formulario No. 3 va firmado y sellado (lo diría la descripción del documento); generarlo prellenado con los datos del formulario, para imprimir, firmar y subir; un «Desistir» para que la agencia cierre una solicitud que ya no usará (hoy queda aprobada hasta que vence); y, con UCVMM, que los 3 meses de vigencia del pasaporte apliquen también a la gente de mar.
20. **Del 2026-11-14:**
    - Con la DTI: publicar la verificación del QR en internet (plantilla `frontend/nginx-verificacion-publica.conf`, HTTPS, `set_real_ip_from` y `URL_VERIFICACION_PUBLICA`). Mientras tanto, el QR solo funciona dentro de la red del SNM.
    - Con UCVMM: el nombre y la descripción de la Visa de los restringidos (hoy «Visa», «Para el pasajero de nacionalidad restringida.»; se cambian con una migración).
    - Si las agencias van a entrar al sistema desde internet sin VPN (el usuario lo mencionó), es otra decisión con la DTI: hoy todo está pensado para la VPN. Publicar todo pediría al menos HTTPS, el segundo factor de las agencias (punto 8) y un WAF.

### Flujo actual: Autorizaciones Marítimas (UCVMM)

Basado en el documento de UCVMM "Documentación requerida para las autorizaciones marítimas". Backend: `api/v1/solicitudes.py` → `domain/services/solicitud_service.py` → `domain/repositories/solicitud_repository.py`. Frontend: `modulos/solicitudes/`.

**Roles:**
- **Naviera** (`T-CREAR-BASICA` + `users.agencia_id`) — envía solicitudes de su agencia (`/new`) y corrige las devueltas dentro del plazo. Cualquier usuario de la agencia ve y corrige las de la agencia. Sin agencia no puede enviar; con la agencia desactivada no entra.
- **UCVMM** (`T-PROCESAR-PACIFICO` + asignación en `usuarios_sectores`; el rol se llamaba «Sector Pacífico» hasta el 2026-11-10) — revisa las solicitudes de los puestos de **sus sectores** (ver «Sectores, supervisión y pasajeros» en docs/HISTORIAL.md). Sin sector asignado, su bandeja responde 409:
  - Verifica impedimentos **por pasajero** (`solicitud_tripulantes.con_impedimento`, NULL = sin verificar). Todos marcados es obligatorio para aprobar; con impedimento igual se puede aprobar. El comentario es opcional.
  - Registrada, la verificación queda de solo lectura. Cambiarla es una **corrección**:
    - Exige `motivo_correccion`.
    - Deja un evento `impedimentos_corregidos` (interno, como `impedimentos`) con qué cambió y por qué.
    - Repetirla sin cambios responde 409.
    - `corregir()` de la agencia la reinicia: la siguiente es una verificación nueva, no una corrección.
  - Aprueba, devuelve a corrección o deniega (el estado se muestra como "Denegada"; en la BD y la API sigue siendo `denied` / `/negar`).
  - Genera y anula la boleta de recargo de las aprobadas fuera del horario de sus sectores (ver «Boleta de recargo» abajo).
- **Puesto de Control** (`T-FINALIZAR-PUERTO` + asignación en `usuarios_puestos`) — ve las aprobadas de sus puestos, verifica los impedimentos en SIMPLUS (obligatoria desde el 2026-11-06, aparte de la de UCVMM) y las finaliza con comentario obligatorio.
  - El comentario sin finalizar (`POST /solicitudes/{id}/comentarios`) se retiró el 2026-10-20: no tenía pantalla. Los eventos `comentario` de antes se siguen mostrando, solo al SNM.
  - Finaliza siempre en el puesto autorizado (reunión del 2026-10-30; antes podía indicar otro). Con cambio de puerto (2026-11-13), el autorizado es el nuevo; el primero solo la consulta. Si la operación se hace en otro puesto, no se finaliza: vence sola y la agencia presenta una nueva solicitud. Las finalizadas en otro puesto antes del cambio se siguen mostrando así en el expediente, el PDF y la verificación pública.
  - El rol se siembra con `es_sistema = false` (el admin puede renombrarlo o borrarlo).
  - Genera y anula la boleta de recargo de las solicitudes que ve.
- **Supervisor de sector** (`T-SUPERVISAR-SECTOR` + `usuarios_sectores`) y **Supervisor general** (`T-SUPERVISAR-TODO`; UCVMM en Tocumen) — solo lectura (2026-11-10): la bandeja «Supervisión» (`GET /solicitudes/supervision`), los expedientes con sus documentos (cada apertura queda en la bitácora) y el PDF de la autorización (copia interna). Ningún botón de decisión (`revisar` y `finalizar` en falso) y sin campana.
  - El de sector ve las de sus sectores, con sus estadísticas (con exportación) y la consulta histórica, y genera y anula la boleta de recargo.
  - El general (desde el 2026-11-16) ve **solo el trámite de Técnico, Superintendente o Supernumerario**, de los dos sectores (`tipos_tramite.supervision_general`, `ContextoAcceso.supervisa_tramite`). No tiene estadísticas, ni el uso del sistema, ni la consulta histórica (`ve_historico`). Descarga las boletas de sus solicitudes, sin generarlas.
  - `ve_todos_los_sectores` es solo del Administrador desde el 2026-11-16.
- **Administrador** — acceso total (decisión del usuario del 2026-10-20): bandejas y expedientes (atajo a todos los `T-*`), catálogo de trámites, agencias/puestos/sectores/nacionalidades (`/admin/catalogos`), estadísticas, bitácora y también usuarios y roles (`/admin`, `/admin/roles`). Antes solo listaba usuarios y roles. No necesita sector: ve los dos.
- **SysAdmin** — rol técnico, sin permisos `T-*` y sin atajo: usuarios (`/admin`), roles (`/admin/roles`; los permisos son fijos y solo se asignan a roles) y bitácora. No ve solicitudes (403 en la API; el frontend lo manda a `/admin`).
  - El último SysAdmin activo no se puede desactivar, borrar ni cambiar de rol (409).
  - Administrador y SysAdmin no se pueden renombrar y sus permisos son fijos (400 en `asignar_permisos_a_rol`): el SysAdmin no puede darse permisos `T-*`.
  - Nadie cambia su propio rol (400): ni subirse de rol ni quedarse fuera por error.
  - El primero se nombra desde la consola: `python -m app.infrastructure.asignar_rol <usuario> SysAdmin` (queda en la bitácora como "consola"). En una instalación nueva no hay usuarios y el AD solo deja entrar a los registrados: `--crear-ad` lo da de alta desde el AD y `--crear-local` crea una cuenta local con contraseña temporal (2026-11-08, `test_la_consola_crea_el_primer_usuario`).

**Estados (`solicitudes.estado`, con CHECK en la BD):** `review` → `approved` → `finalized`; `review` → `returned` → (corrige) `review`; `review` → `denied`; `approved` o `returned` con el plazo vencido → `expired` (`infrastructure/tareas.py`).

**Reglas que no son obvias leyendo el código:**
- El checklist vive en BD (`tipos_tramite`, `documentos_requeridos`, `tramite_documentos`) y sus condiciones se resuelven en `ServicioTramite.construir_casillas`, **espejado** en `frontend/src/modulos/solicitudes/checklist.ts`: si cambias uno, cambia el otro.
- Cada solicitud guarda la **foto del checklist** con el que se envió (`solicitud_casillas`). La foto se vuelve a tomar en cada corrección.
  - El expediente se evalúa contra esa foto, no contra el catálogo de hoy. Es el mismo principio que `nacionalidad_restringida` del tripulante.
  - Un cambio del catálogo no deja incompletas las solicitudes ya enviadas ni los expedientes cerrados. La siguiente corrección sí se valida con las reglas nuevas.
  - Antes de `7e3f1a9c2d64` se evaluaba en vivo, y el cambio de `b9e4d17a3c52` (Carta y Reporte "por tripulante") marcó como faltantes documentos que sí estaban.
- `solicitud_documentos.documento_id` nulo = documento adicional (fuera del checklist; máx. 20 por solicitud).
- Asignar un usuario a una agencia o a un puesto no le da acceso sin el permiso de su rol: la API exige las dos cosas (`ContextoAcceso`). Por eso la pantalla de catálogos ofrece «Mostrar todos los usuarios» a propósito.
- `valida_vigencia` está activa en **todos** los trámites. Desde el 2026-11-13:
  - el pasaporte tiene que vencer al menos 3 meses después de la operación (`vigencia_minima_pasaporte`), si no, no deja enviar;
  - el seamanbook vencido ya no bloquea: se avisa en el formulario y se señala en el expediente.
  - Antes, los dos bastaba con que vencieran después del día de la operación. Los rangos distintos de "marino" no portan seamanbook.
- Fechas (`ServicioTramite.validar_tripulantes` y `_validar_formulario`, espejadas en `validacionFormulario.ts`):
  - La operación va de hoy a `DIAS_MAXIMOS_ANTICIPACION` (365).
  - Tripulantes con 18 años cumplidos y nacidos desde 1900.
  - Pasaporte y seamanbook vencen después del nacimiento.
- Formatos del expediente: PDF, Word y Excel (`.pdf .doc .docx .xls .xlsx`, decisión del usuario del 2026-10-15, "de momento"; antes solo PDF). En `infrastructure/almacenamiento.py`, espejo en `utils/archivos.ts`:
  - El contenido se comprueba por formato: firma `%PDF-`; OLE2 para .doc/.xls; ZIP OOXML con su parte principal para .docx/.xlsx.
  - Los de Office se rechazan si traen macros: `oletools`, que falla cerrado, y cualquier `vbaProject.bin` dentro de un .docx/.xlsx.
  - El MIME que se guarda y con el que se sirve es el del formato verificado (`mime_del_formato`); python-magic queda como control cruzado en el log (2026-11-02: antes un «PDF» con HTML delante quedaba como text/html).
  - La vista previa muestra .docx y .xlsx; .doc y .xls se descargan.
  - Máximo **2 MB por archivo**, en cualquier formato (decisión del usuario del 2026-10-16): `TAMANO_MAXIMO_MB` en `almacenamiento.py`, espejo en `utils/archivos.ts`. Es una constante y no una variable de entorno a propósito, para que backend y frontend no se desalineen. Los documentos ya cargados que pesan más se siguen viendo.
- **El catálogo sigue tal cual los documentos, sin criterio propio** (lo pidió el usuario):
  - Qué documentos: el recuadro del trámite en el **Formulario No. 3 oficial**. Por eso Desembarque lleva Generales de pasaporte, aunque el documento de proceso no la liste.
  - Por tripulante o por solicitud: cada proceso dice "para cada tripulante…". La única excepción escrita es la Lista de Tripulantes, que "debe subirse al trámite" (pág. 9). Por eso la Carta de responsabilidad y el Reporte médico van por tripulante.
  - Flujo y requisitos del sistema: págs. 9–10 del documento de proceso.
  - **Siete excepciones decididas por el usuario** sobre la lectura literal:
    - La vigencia se valida en todos los trámites, no solo en los 3 que la mencionan (2026-10-14). Desde el 2026-11-13, el pasaporte con al menos 3 meses a partir de la operación, y el seamanbook vencido solo se señala.
    - La libreta de Embarque se pide a todo Marino (`siempre`), no solo a los panameños (2026-10-14). La condición `solo_panamenos` se quitó el 2026-11-14 (nunca se usó).
    - A los rangos distintos de Marino solo se les piden las Generales de pasaporte y el boleto aéreo, en todos los trámites (reunión del 2026-10-30, `tramite_documentos.rangos`), salvo lo de la cuarta.
    - A los técnicos, supernumerarios y superintendentes, en Desembarque, Carta, Generales, Contrato y boleto opcional (2026-11-11). Desde el 2026-11-13 van por el trámite de Técnico, y esas filas se borraron el 2026-11-14 (migración `d9a4b7e2c315`). La lógica de lo opcional (`tramite_documentos.rangos_opcional`, `opcional_para` / `opcionalPara`) se queda, con sus pruebas, para el próximo documento opcional.
    - El Formulario No. 3 en todos los trámites, uno por solicitud y para cualquier rango; el Cambio de Puerto deja de ser un trámite: se indica en Embarque y Desembarque, con el nuevo puesto del mismo sector; y el rango Pasajero presenta lo del Marino sin la Libreta, con Embarque y Desembarque solo para Marino, Pasajero y Militar (2026-11-13).
    - La Visa (DOC-VISA) a todo pasajero de nacionalidad restringida, en todos los trámites y rangos; a los panameños, sin visa ni boleto aéreo en Embarque y Desembarque ni la Visa Especial de Marino en Cambio de nave (condición `solo_extranjeros`); y el Sellado de Shore Pass solo para el Marino (2026-11-14).
    - «¿Subir y bajar?» (Sí / No, empieza en No) en Embarque y Desembarque. Con «Sí», cada pasajero, de cualquier rango, adjunta la Carta de Responsabilidad (Form. No. 7), además de lo demás del trámite (2026-11-16, migración `a7c2e9f4b618`):
      - El trámite la pregunta si tiene `tipos_tramite.permite_subir_y_bajar`, y la respuesta se guarda en `solicitudes.subir_y_bajar`.
      - La Carta va con la condición `subir_y_bajar`, espejada en `checklist.ts`: `construir_casillas(..., subir_y_bajar)`.
      - En los demás trámites, la respuesta se descarta, como el cambio de puerto.
      - La muestran el expediente, el PDF de la autorización y la boleta.
- Nacionalidad restringida (`paises.nacionalidad_restringida`):
  - Desde el 2026-11-14 se le pide la **Visa** (DOC-VISA) en todos los trámites y rangos, y se señala en todos: el chip de la tarjeta, la bandeja y el expediente, y el aviso del formulario, que nombra lo que debe adjuntar.
  - El Form. No. 6 se adjunta **solo en Desembarque** ("cuando aplique", como en el Form. 3).
  - `tipos_tramite.aviso_custodia` marca los trámites cuyo proceso dice que, al aprobar, se avisa a la agencia que debe realizar el trámite de solicitud de custodia: Desembarque, Urgencias, Renovación y Shore Pass.
  - En los demás trámites no se menciona la custodia: ni en el formulario, ni en el expediente, ni en el correo, ni en el PDF.
  - **Ninguna nacionalidad viene sembrada**: la lista oficial la marca el admin.
- La **ocupación** del pasajero salió del formulario el 2026-11-16:
  - `solicitud_tripulantes.ocupacion` admite nulo.
  - Las solicitudes de antes la siguen mostrando: el expediente y el PDF titulan la columna «Rango / ocupación» solo si algún pasajero la tiene (`tituloColumnaRango` / `titulo_columna_rango`).
  - Al corregir una devuelta se borra: podría quedar pegada a otra persona si la agencia cambia a alguien en la misma ficha.
  - Un navegador con la versión anterior que la mande no falla: se ignora.
- `tipos_tramite.rangos_permitidos` limita los rangos del trámite (nulo = cualquiera): F3-TECNICO (sus tres rangos, por el nombre del trámite en el Form. 3), Embarque y Desembarque (Marino, Pasajero y Militar, 2026-11-13) y Shore Pass (solo Marino, 2026-11-14). Lo valida `ServicioTramite.validar_tripulantes` y lo espeja `validacionFormulario.ts`. Con un solo rango, el formulario lo trae elegido y lo dice bajo el campo y en la tarjeta del trámite.
- Las aclaraciones del instructivo del Form. 3 para el buque y el puerto ("nueva nave a embarcar", etc.) viven en `AYUDA_CAMPOS_TRAMITE` (`modulos/solicitudes/presentacion.ts`).
- `tipos_tramite.descripcion` (revisión `a3d9c6e1f584`) es una línea con cuándo se usa el trámite, para las tarjetas del paso 1.
  - Primera versión del 2026-10-19, apoyada en los documentos que pide cada trámite (el boleto aéreo del Desembarque, la cita del consulado de la Renovación): **falta validarla con UCVMM**.
  - Se cambia con una migración, como el resto del catálogo.
- `tests/test_documento_ucvmm.py` es la lectura literal del Form. 3 y del documento de UCVMM por trámite: si cambias el catálogo, esa tabla tiene que seguir coincidiendo (o cambia porque UCVMM cambió el requisito).
- Lo interno no le llega a la agencia. Lo filtra el backend (`ContextoAcceso.es_personal_snm`, `evento_para` en `solicitud_service.py`, que usan también las novedades de la campana), no la vista:
  - Los eventos de las verificaciones de impedimentos (de UCVMM y del puesto, con sus correcciones) y `comentario`.
  - El texto de `aprobada` y `finalizada`.
  - `observacion_aprobacion`, `comentario_finalizacion`, `aprobada_por`, `finalizada_por`, `con_impedimento`, `con_impedimento_puesto` y los `impedimentos_puesto_*`.
  - Los nombres de los funcionarios: el autor sale como «Servicio Nacional de Migración» (hasta el 2026-11-11, "UCVMM") o "Puesto de control". Tampoco se le nombran las unidades internas (UCVMM, los sectores).
  - Los motivos de devolución y de negación **sí** los ve.
  - Desde el 2026-11-11 **sí** ve si se aprobó fuera del horario y su recargo (`fuera_de_horario`, `costo_fuera_de_horario`).
  - Las boletas de recargo **no** (`boletas` le llega en null, y los eventos `boleta_generada` / `boleta_anulada` son internos): las imprime el SNM y se las entrega.
- **Boleta de recargo** (2026-11-16, `boletas_recargo`, revisión `e5c1a7d3b902`). Aprobada fuera del horario (de 15:01 a 06:59 y el fin de semana, por la hora de la aprobación), la solicitud lleva el recargo de `COSTO_FUERA_DE_HORARIO` (B/.20.00, guardado al aprobar). Para cobrarlo:
  - **Quién:** la generan UCVMM, el supervisor de sector, el puesto de control y el Administrador (`puede_gestionar_boleta`). El número de oficio lo escribe el funcionario.
  - **El número:** único entre todas las boletas, anuladas incluidas, sin distinguir mayúsculas (índice sobre `lower(numero_oficio)`). Hasta 40 caracteres, sin espacios de más.
  - **Talonario:** una vigente por solicitud (índice parcial). Una mal hecha se anula con motivo y se genera otra con otro número. No se corrige ni se borra.
  - **Concurrencia:** se bloquea la solicitud (`_para_boleta`, FOR UPDATE): dos generaciones a la vez dejan una sola (`test_dos_generaciones_a_la_vez`).
  - **El PDF** (`informes/boleta_recargo_pdf.py`) no lleva nombres de funcionarios: se entrega a la agencia. La anulada sale con el sello ANULADA. Bitácora: BOLETA_GENERADA, BOLETA_ANULADA y BOLETA_DESCARGADA.
  - **Tipo de operación en casillas, como en papel** (2026-11-16):
    - Lleva los trámites activos, en su orden, con la X en el de la solicitud. Si el trámite ya está inactivo, como Cambio de Puerto, se suma al final, marcado (`casillas_operacion`).
    - Si el trámite pregunta «¿Subir y bajar?», debajo va la respuesta.
- La observación de aprobación es interna: no va en el PDF ni en el correo de aprobación. El PDF no tiene sección de observaciones.
- El PDF de la agencia dice "Aprobada por: Servicio Nacional de Migración" (hasta el 2026-11-11, "UCVMM"), sin el nombre del funcionario: tampoco ve esos nombres en el expediente (decisión del usuario del 2026-10-15). El personal del SNM descarga una copia interna con el nombre de quien aprobó (reunión del 2026-10-30, en docs/HISTORIAL.md).
- `agencia_nombre`, `puesto_nombre` y `puesto_finalizacion_nombre` son una foto (al enviar o al finalizar): renombrar la agencia o el puesto no cambia expedientes viejos.
- Las solicitudes no se eliminan; un usuario (FK RESTRICT), agencia o puesto con solicitudes no se borra (se desactiva).
- El PDF (`informes/autorizacion_pdf.py`, reportlab) lleva un QR a `/verificar/{codigo_verificacion}` (público, con rate limit). Ese código solo verifica: no abre el expediente.
- Bitácora = `audit_logs`. Los valores nuevos de `accionauditoria` se agregan en migración con `ALTER TYPE ... ADD VALUE IF NOT EXISTS` dentro de `op.get_context().autocommit_block()`. Los valores del storage (`TRANSFERENCIA_*`, `DESCARGA_REALIZADA`) se conservan para leer el historial.

### Historia que queda a propósito
Desde el 2026-10-16 todo se llama ARGO NAVIS: la base `argonavis`, los documentos en `storage/documentos` (en Docker, el proyecto `argonavis` y su volumen `documentos`), los respaldos `argonavis_*` y el repositorio `ArgoNavis`. El paso a paso para servidores instalados antes está en el README (Producción). Del storage original quedan, a propósito:
- Los valores `TRANSFERENCIA_*` y `DESCARGA_REALIZADA` de la bitácora, las migraciones viejas de Alembic (no se editan), `test_migraciones.py` (prueba la migración desde el storage) y la prueba de que `/transfers` ya no existe.
- Se quitaron el 2026-11-14 el alias `RATE_LIMIT_DOWNLOADS_PER_MINUTE` (un `.env` que lo traiga ya no lo usa: va `LIMITE_VERIFICACIONES_POR_MINUTO`), la columna `tipos_tramite.formulario` y los nombres `snm_*` de los contenedores (hoy `argonavis_*`).

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
4. Si cambias una regla espejada (backend y frontend), agrega su caso en `backend/tests/espejo/` y corre las dos suites (`pytest` y `npm test`).

### Antes de proponer un cambio grande
Hacé una pregunta corta primero. El proyecto está en producción de un organismo gubernamental, los cambios silenciosos no son gratis.

### Comandos útiles
```bat
:: Backend: validar imports rápido
cd backend && venv\Scripts\python -c "from app.main import aplicacion"

:: Backend: pruebas (BD temporal en el servidor de DATABASE_URL; no envía correos)
cd backend && venv\Scripts\python -m pytest

:: Backend: lint (la CI lo corre antes de las pruebas)
cd backend && venv\Scripts\python -m ruff check .

:: Backend: dependencias (se instalan desde el bloqueo; se edita requirements.txt y se regenera)
cd backend && venv\Scripts\python -m pip install --require-hashes -r requirements.lock
cd backend && venv\Scripts\uv pip compile requirements.txt --universal --python-version 3.12 --generate-hashes -o requirements.lock
cd backend && set PYTHONUTF8=1 && venv\Scripts\python -m pip_audit -r requirements.lock --require-hashes

:: Frontend: typecheck y lint
cd frontend && node node_modules/typescript/bin/tsc -b --noEmit
cd frontend && npm run lint

:: Frontend: pruebas unitarias (Vitest) y recorrido completo en el navegador (Playwright,
:: con su propio backend en 8001 y la BD temporal argonavis_e2e; Chrome o PLAYWRIGHT_CHROMIUM=1)
cd frontend && npm test
cd frontend && npm run test:e2e

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
