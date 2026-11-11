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

En pantalla se dice **«pasajeros»** (desde el 2026-11-10; antes «tripulantes»), pero en el código, la API y la BD sigue `tripulante(s)`: es contrato (ver «Sectores, supervisión y pasajeros»).

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
    - Y entra en `_RUTA_DE_ENVIO` (`main.py`) y en el `location` de los envíos de `frontend/nginx.conf`: el resto de la API admite cuerpos de 1 MB (`TopeDelCuerpo`, 2026-11-10).
17. En producción el backend no arranca con una `SECRET_KEY` de menos de 32 caracteres o de ejemplo (validador en `core/config.py`).
18. Los servidores de desarrollo escuchan solo en este equipo (`start-backend.bat` en 127.0.0.1, Vite en `localhost`): no tienen las protecciones de producción. `VITE_HOST=0.0.0.0` solo para probar desde otro equipo, y por un rato.
19. La aplicación entra a PostgreSQL con **su propia cuenta** (`DATABASE_URL`, en Docker `argonavis_app`), no con la dueña de las tablas ni con un superusuario (2026-11-08):
    - La crea y la pone al día `infrastructure/permisos_bd.py` después de cada migración, con la dueña (`MIGRACIONES_DATABASE_URL`, que el entrypoint borra antes de levantar uvicorn).
    - Lee y escribe filas, pero no crea ni cambia tablas ni ejecuta programas del servidor (`COPY ... TO PROGRAM`).
    - `audit_logs` y `solicitud_eventos` son **solo para agregar** (sin UPDATE ni DELETE): la bitácora y el historial no se pueden tapar desde la aplicación. Las FK con `ON DELETE SET NULL` las aplica PostgreSQL con la dueña, así que borrar un usuario funciona igual.
    - No conectes la aplicación como dueña ni le des UPDATE o DELETE sobre esas tablas. Una tabla nueva que necesite otro trato va en `TABLAS_SOLO_AGREGAR` o `TABLAS_SIN_ACCESO`.
    - Lo prueban `tests/test_permisos_bd.py` y el E2E, cuyo backend entra con una cuenta así (`servidor_e2e.py`).

### Errores
- Backend: `HTTPException` con código y `detail` descriptivo. Nunca `except: pass`. Loggear con `logger.warning/.error` con contexto.
- Cada pedido lleva un código (`X-Request-ID`, middleware `CodigoDePedido` en `main.py`, 2026-11-08). Va en cada línea del log (`[%(pedido)s]`, `core/registro.py`), en la respuesta y en el cuerpo de los 5xx (`codigo`), que el frontend agrega al mensaje (`mensajeDeError`). Para un error reportado, busca su código en el log: ahí está la traza. Un error sin controlar lo registra el middleware, con la traza, y responde 500 con el código.
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
  - Modales, resumen de estadísticas y tarjetas sueltas: la franja amarilla arriba. Pestañas como separadores de expediente, con la franja en la activa.
- **Reglas:**
  - El guilloche va solo en lo que identifica a un documento (cabecera, cabeza del expediente, tapa del pasaporte, hoja del login): sobre la carta del fondo, dos texturas juntas ensucian.
  - El amarillo sigue siendo relleno. La única excepción como texto es la tapa del pasaporte: dorado sobre marino, 10:1.
  - Las mayúsculas son siempre de CSS (`text-transform`): el texto leído y los nombres accesibles no cambian, y el E2E los busca tal cual.
- Maquetas y capturas de la elección: en el scratchpad de la sesión (`diseno/`).

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
- Botones (en mayúsculas de Archivo desde el 2026-11-11): principal marino en claro y amarillo en oscuro (`--principal`); secundario con borde de tinta; aprobar con `--exito-fuerte`, denegar/eliminar con `--peligro-fuerte` (o contorno rojo); "Volver" sólido (`--card` con borde: sobre el fondo decorativo, transparente no se leía). Desactivado en gris (`--overlay-2` + `--muted`), no amarillo a media opacidad. En `useConfirmar`, `peligroso` (rojo) o `exito` (verde) según la acción.
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
- Campos con `--input-border` / `--input-bg` (borde de 3:1). Las notas informativas, neutras con borde izquierdo `--acc-blue`.
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
  - Errores y avisos quedan 10 s en pantalla; éxitos e informativos, 4 s (`Notificaciones`).
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
  - El frontend renueva el token mientras hay actividad (`VigilanteSesion` en `App.tsx`).
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
  - Si el SMTP falla, el aviso se reintenta durante unas 24 horas, desde la cola persistente (2026-10-29, ver abajo). Antes eran dos reintentos en memoria (30 s y 2 min), y un reinicio a mitad los perdía.

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

### Pruebas del frontend y formulario partido (2026-10-21)
- Las reglas espejadas tienen casos compartidos en `backend/tests/espejo/*.json` (IMO, contraseñas, checklist, tripulantes). Los corren `test_espejo.py` (pytest) y los `*.test.ts` (Vitest); `test_constantes_iguales_en_el_frontend` compara las constantes (formatos, 2 MB, contraseñas, edad, anticipación, adicionales, rangos con libreta).
  - Encontraron una diferencia real: el 29 de febrero el frontend daba 18 años a quien nació el 1 de marzo. Se corrigió en `desplazar` (`validacionFormulario.ts`).
- Pruebas en el navegador (`frontend/e2e/`, Playwright):
  - `flujo-completo.spec.ts`: envío, devolución, corrección, aprobación, PDF y QR, finalización y bitácora.
  - `formulario.spec.ts`: el formulario sin enviar (cambiar de trámite, quitar un tripulante, adicionales).
  - `backend/tests/servidor_e2e.py` levanta la API en 127.0.0.1:8001 con la BD `argonavis_e2e` y una cuenta local por rol que solo existe ahí. La BD se borra al terminar (`e2e/limpiar.ts`).
  - Los `<input type="file">` del checklist llevan `aria-label` («Adjuntar / Reemplazar <documento> de <tripulante>»): los usan los lectores de pantalla y el E2E.
- `PaginaSolicitud` (684 líneas) se partió sin cambiar lo que hace: carga (`useCargaFormulario`), formulario (`FormularioSolicitud`), estado (`useTripulantesFormulario`, `useDocumentosFormulario`), secciones (`DatosTramite`, `ChecklistSolicitud`) y la ida y vuelta sin React (`envioSolicitud.ts`, con sus pruebas: precarga y armado del envío).

### Revisión completa e integración continua (2026-10-27)
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
- **Después de un despliegue,** si falta un archivo de la versión anterior, `main.tsx` recarga la página (`vite:preloadError`, como mucho una vez por minuto).
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

### Puntos de la reunión del 2026-10-30 (revisiones `f7a2c9e4b136` y `b2e7d4c9a160`)
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

### Estadísticas (rediseño del 2026-11-02; menos texto y exportación, 2026-11-10)
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

### Revisión del código del 2026-11-02
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

### Cambios del 2026-11-06 (revisión `d8c3f1a6b294`)
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

### Auditoría de rendimiento y disponibilidad (2026-11-08, revisión `e7b2d5a9c4f1`)
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
  - El servidor de pruebas (192.168.10.75, Rocky 9) no llega a Docker Hub (el firewall corta `auth.docker.io`): usa el espejo `mirror.gcr.io` en `/etc/docker/daemon.json` (`registry-mirrors`).
  - nginx resuelve `backend` en cada petición (`resolver 127.0.0.11` y `proxy_pass $api`): con el nombre fijo lo resolvía una vez al arrancar y, si el backend se recreaba con otra IP, respondía 502 hasta reiniciarlo.
- **Revisado y sin cambios:** LDAP, bcrypt y el PDF ya corren en hilos; las subidas tienen su propio tope de 300 s en el cliente; temporizadores y escuchas del frontend se limpian; las relaciones del ORM cargan en lote (`selectin`), sin N+1 en las bandejas.
- **Documentación de la DTI, juego 0.6:** el 06 (configuración, Docker, salud, índices) y el 08 (evidencias y pendientes) pasan a la 0.6; el 00, a la 0.5, por su tabla de versiones. Los demás no cambian. `v06.py` (scratchpad) hace los reemplazos en los generadores, como `v05.py`.

### «Vibe coder vs. desarrollador» (2026-11-08)
El usuario pidió revisar el proyecto contra cinco puntos:
- **No se cae con 100 usuarios:** prueba de carga `backend/tests/carga.py` (no la corre pytest). Levanta el backend con 2 procesos contra una BD temporal y pone a N usuarios a pedir algo cada 1 a 3 s.
  - Con 100 usuarios: 2.683 pedidos sin un error; mediana de ~1 s y techo de ~29 pedidos por segundo, con las 30 conexiones al tope (detalle en README → «Capacidad y disponibilidad»).
  - Consultas por pedido (en proceso, sin red): campana 8 a 9, bandejas 11 a 20, expediente 26. De esas, 6 son para saber quién pide.
  - Si un día hace falta más capacidad, ahí está el margen (pendiente 16). No se tocó: es código de autenticación y el uso real (~8 pedidos por segundo con 100 usuarios) está lejos del techo.
- **useEffect:** 34 en toda la app y como mucho 3 por componente. El lint exige las reglas del compilador de React y, además, `no-deriving-state-in-effects` y `void-use-memo` (`eslint.config.js`).
- **Permisos en la BD:** regla 19 de Seguridad.
- **Leer la traza:** el código de pedido (Errores, arriba).
- **Claves en el frontend:** ninguna. El `.env` nunca entró al repositorio (revisado en todo el historial), el frontend solo lee `VITE_API_URL` y ninguna clave del servidor aparece en el paquete compilado.

### Los 20 puntos de «sitio hecho a la carrera» (2026-11-08)
El usuario pidió revisar una lista de señales de sitios web públicos. ARGO NAVIS es un sistema **interno**: lo de buscadores no aplica, y lo de rastreadores aplica al revés.
- **Hecho:** página 404 propia (`PaginaNoEncontrada`; antes una ruta desconocida llevaba a las bandejas sin avisar), `<noscript>`, meta description, `noindex` en tres capas (`robots.txt`, la etiqueta robots de `index.html` y `X-Robots-Tag` en nginx y en `_CABECERAS_SPA`), source maps apagados de forma explícita (`vite.config.ts`) y la vigilancia de la consola en el E2E (`e2e/base.ts`: un `console.error`, un error sin atrapar o un 5xx hacen fallar la prueba; los 4xx no).
- **Ya estaba:** título por página (`useTituloDocumento`), un solo H1 por página, `alt` en las imágenes, `lang="es"`, favicon, paquete inicial partido (357 KB; exceljs y docx-preview se cargan solo al previsualizar).
- **No aplica, a propósito:** sitemap, tag canónico, OG image, datos estructurados y `llms.txt` (son para salir en buscadores y en IA; aquí nada debe indexarse). Vite y React son la decisión del proyecto. **No los agregues.**
- Los avisos que quedan en la consola de Firefox (contraseña en página insegura, `crypto.randomUUID` en su visor de PDF) son por servir en HTTP: los quita el HTTPS (pendiente 1).

### Sectores, supervisión y «pasajeros» (2026-11-10, revisiones `c1f7a3e9d2b6` y `d5b8e2f1a9c3`)
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

### Dependencias: de dónde salen y fijadas (2026-11-10)
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

### Recursos y topes (2026-11-10)
Pedido del usuario: «¿no hay riesgo de sobrecarga de recursos, procesos que afecten la operación?», y después: «¿por qué 200 MB si el máximo es 2 MB por archivo?», «los contenedores deben estar limitados» y «¿el respaldo nocturno ralentiza todo?». Lo prueba `tests/test_recursos.py`.
- **Tope del cuerpo de cada petición** (`TopeDelCuerpo`, `main.py`): 1 MB en la API (`TOPE_CUERPO_MB`) y `TOPE_CUERPO_ENVIO_MB` (283) al crear y corregir una solicitud (`_RUTA_DE_ENVIO`). Es lo más que pesa un envío válido: 30 pasajeros × 4 documentos + 1 de la solicitud + 20 adicionales, de 2 MB, más 1 MB.
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

### Cambios del 2026-11-11 (revisiones `a8d4f2c6e913` y `c6f1d9a3b724`)
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
- **En las celdas de una tabla, `overflow-wrap: break-word`, no `anywhere`:** con `anywhere` la columna se encoge al mínimo y parte palabras normales («KENSINGTO-N»). `anywhere` sigue siendo lo indicado en los bloques de texto libre.
- **Vitest y la letra de unidad (Windows):** si todas las pruebas fallan con «Cannot read properties of undefined (reading 'config')», la carpeta de trabajo llegó como `c:\…` en minúscula y Vitest cargó dos copias de sí mismo. Se corre desde `C:\…`.

### Lo que sigue pendiente (no urgente)
1. **HTTPS y TLS con el AD** — la configuración está lista (README → "Producción"); falta el certificado del servidor y el del controlador de dominio (infraestructura).
2. **JWT en cookie httpOnly** — actualmente en localStorage, con la CSP como barrera (regla 15). Plan en README → "Decisiones documentadas".
3. **Redis para rate limit** si se escala a varios hosts (en un host con varios workers el límite es por proceso).
4. **Refactor de componentes grandes** — el expediente (2026-10-19) y el formulario (2026-10-21) ya se partieron. Quedan las páginas de administración (`PaginaUsuarios`, `PaginaCatalogos`, ~440 líneas), sin urgencia.
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
17. **Documentación de la DTI, juego 0.7:** `docs/` no tiene todavía la identidad «pase oficial» ni los cambios del 2026-11-11 (documentos de los técnicos, nombre neutro para la agencia, costo fuera del horario y consulta histórica).
18. **Validar con UCVMM, del 2026-11-11:** cómo y dónde paga la agencia el costo migratorio (el sistema solo lo avisa: no dice dónde se paga ni registra el pago), y si el Contrato de Trabajo debe cumplir alguna condición (hoy se pide sin ninguna).

### Flujo actual: Autorizaciones Marítimas (UCVMM)

Basado en el documento de UCVMM "Documentación requerida para las autorizaciones marítimas". Backend: `api/v1/solicitudes.py` → `domain/services/solicitud_service.py` → `domain/repositories/solicitud_repository.py`. Frontend: `modulos/solicitudes/`.

**Roles:**
- **Naviera** (`T-CREAR-BASICA` + `users.agencia_id`) — envía solicitudes de su agencia (`/new`) y corrige las devueltas dentro del plazo. Cualquier usuario de la agencia ve y corrige las de la agencia. Sin agencia no puede enviar; con la agencia desactivada no entra.
- **UCVMM** (`T-PROCESAR-PACIFICO` + asignación en `usuarios_sectores`; el rol se llamaba «Sector Pacífico» hasta el 2026-11-10) — revisa las solicitudes de los puestos de **sus sectores** (ver «Sectores», abajo). Sin sector asignado, su bandeja responde 409:
  - Verifica impedimentos **por pasajero** (`solicitud_tripulantes.con_impedimento`, NULL = sin verificar). Todos marcados es obligatorio para aprobar; con impedimento igual se puede aprobar. El comentario es opcional.
  - Registrada, la verificación queda de solo lectura. Cambiarla es una **corrección**:
    - Exige `motivo_correccion`.
    - Deja un evento `impedimentos_corregidos` (interno, como `impedimentos`) con qué cambió y por qué.
    - Repetirla sin cambios responde 409.
    - `corregir()` de la agencia la reinicia: la siguiente es una verificación nueva, no una corrección.
  - Aprueba, devuelve a corrección o deniega (el estado se muestra como "Denegada"; en la BD y la API sigue siendo `denied` / `/negar`).
- **Puesto de Control** (`T-FINALIZAR-PUERTO` + asignación en `usuarios_puestos`) — ve las aprobadas de sus puestos, verifica los impedimentos en SIMPLUS (obligatoria desde el 2026-11-06, aparte de la de UCVMM) y las finaliza con comentario obligatorio.
  - El comentario sin finalizar (`POST /solicitudes/{id}/comentarios`) se retiró el 2026-10-20: no tenía pantalla. Los eventos `comentario` de antes se siguen mostrando, solo al SNM.
  - Finaliza siempre en el puesto autorizado (reunión del 2026-10-30; antes podía indicar otro). Si la operación se hace en otro puesto, no se finaliza: vence sola y la agencia presenta una nueva solicitud. Las finalizadas en otro puesto antes del cambio se siguen mostrando así en el expediente, el PDF y la verificación pública.
  - El rol se siembra con `es_sistema = false` (el admin puede renombrarlo o borrarlo).
- **Supervisor de sector** (`T-SUPERVISAR-SECTOR` + `usuarios_sectores`) y **Supervisor general** (`T-SUPERVISAR-TODO`; UCVMM en Tocumen) — solo lectura (2026-11-10): la bandeja «Supervisión» (`GET /solicitudes/supervision`), los expedientes con sus documentos (cada apertura queda en la bitácora), el PDF de la autorización (copia interna) y las estadísticas de su alcance, con exportación. Ningún botón de decisión (`acciones` todo en falso) y sin campana. El de sector ve las de sus sectores; el general, las de los dos, y el uso del sistema.
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
- `valida_vigencia` está activa en **todos** los trámites: un pasaporte o seamanbook que vence antes del día de la operación no deja enviar. Los rangos distintos de "marino" no portan seamanbook.
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
  - **Cuatro excepciones decididas por el usuario** sobre la lectura literal:
    - La vigencia se valida en los 8 trámites, no solo en los 3 que la mencionan (2026-10-14).
    - La libreta de Embarque se pide a todo Marino (`siempre`), no solo a los panameños. La condición `solo_panamenos` queda en el enum sin uso (2026-10-14).
    - A los rangos distintos de Marino solo se les piden las Generales de pasaporte y el boleto aéreo, en todos los trámites (reunión del 2026-10-30, `tramite_documentos.rangos`), salvo lo de la cuarta.
    - A los técnicos, supernumerarios y superintendentes, en Desembarque: Carta de Responsabilidad, Generales de pasaporte, Contrato de Trabajo y, opcional, el boleto aéreo. En Embarque, lo mismo sin el boleto (2026-11-11, `tramite_documentos.rangos_opcional`). El militar sigue con Generales y boleto.
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
- Lo interno no le llega a la agencia. Lo filtra el backend (`ContextoAcceso.es_personal_snm`, `evento_para` en `solicitud_service.py`, que usan también las novedades de la campana), no la vista:
  - Los eventos de las verificaciones de impedimentos (de UCVMM y del puesto, con sus correcciones) y `comentario`.
  - El texto de `aprobada` y `finalizada`.
  - `observacion_aprobacion`, `comentario_finalizacion`, `aprobada_por`, `finalizada_por`, `con_impedimento`, `con_impedimento_puesto` y los `impedimentos_puesto_*`.
  - Los nombres de los funcionarios: el autor sale como «Servicio Nacional de Migración» (hasta el 2026-11-11, "UCVMM") o "Puesto de control". Tampoco se le nombran las unidades internas (UCVMM, los sectores).
  - Los motivos de devolución y de negación **sí** los ve.
  - Desde el 2026-11-11 **sí** ve si se aprobó fuera del horario y su costo (`fuera_de_horario`, `costo_fuera_de_horario`).
- La observación de aprobación es interna: no va en el PDF ni en el correo de aprobación. El PDF no tiene sección de observaciones.
- El PDF de la agencia dice "Aprobada por: Servicio Nacional de Migración" (hasta el 2026-11-11, "UCVMM"), sin el nombre del funcionario: tampoco ve esos nombres en el expediente (decisión del usuario del 2026-10-15). El personal del SNM descarga una copia interna con el nombre de quien aprobó (reunión del 2026-10-30, ver arriba).
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
4. Si cambias una regla espejada (backend y frontend), agrega su caso en `backend/tests/espejo/` y corre las dos suites (`pytest` y `npm test`).

### Antes de proponer un cambio grande
Hacé una pregunta corta primero. El proyecto está en producción de un organismo gubernamental, los cambios silenciosos no son gratis.

### Comandos útiles
```bat
:: Backend: validar imports rápido
cd backend && venv\Scripts\python -c "from app.main import aplicacion"

:: Backend: pruebas (BD temporal en el servidor de DATABASE_URL; no envía correos)
cd backend && venv\Scripts\python -m pytest

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
