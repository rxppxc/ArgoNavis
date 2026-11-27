# ARGO NAVIS · Sistema Interno Marítimo (SNM)

**ARGO NAVIS** es el Sistema Interno Marítimo del **Servicio Nacional de Migración (SNM) de Panamá**; el nombre viene de la constelación *Argo Navis*, «la nave Argo». Hoy cubre las **Autorizaciones Marítimas** de la UCVMM: las agencias navieras envían solicitudes con el expediente de los pasajeros, UCVMM (Sector Pacífico o Atlántico, según el puesto) las revisa y aprueba (o devuelve o deniega), y el puesto de control migratorio registra la operación y la finaliza. La autorización aprobada se descarga en PDF con un código QR verificable.

Nació como una herramienta de *storage* (transferencias de archivos con enlace público) y se adaptó: el almacenamiento pasó a ser la capa documental del expediente de cada solicitud. Ya no hay enlaces públicos de descarga. Antes se llamaba "FileDrop - SNM" y el repositorio, FileTransfer.

---

## Tecnologías

| Capa | Stack |
|---|---|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 async · PostgreSQL · Alembic · LDAP (Active Directory) · JWT · reportlab (PDF + QR) · XlsxWriter (Excel) |
| **Frontend** | React 19 · TypeScript estricto · Vite · CSS Modules · React Router v7 · letras propias en el paquete (Archivo, Public Sans, IBM Plex Mono; `@fontsource`, sin CDN) |
| **Infraestructura** | Docker Compose (nginx + backend + PostgreSQL) o Windows (uvicorn + proxy) · slowapi (rate limit) |

---

## Arranque rápido

### Requisitos
- Python 3.12+ y Node.js 22+
- PostgreSQL 15 o más nueva, con la base de `DATABASE_URL` creada en UTF-8 (usa `pg_trgm`, que viene incluida)
- Acceso a un servidor LDAP / Active Directory (las cuentas locales no lo necesitan)

### Primera vez
```bat
:: Copiar plantilla de entorno y completarla (SECRET_KEY, DATABASE_URL, LDAP_*, MAIL_*...)
copy backend\.env.example backend\.env

:: Backend
cd backend
python -m venv venv
:: Siempre "venv\Scripts\python -m ...": los .exe del venv (pip, uvicorn...) guardan la ruta de la carpeta y fallan si se mueve.
:: Primero las de producción, exactas y con hash (requirements.lock); después, las de desarrollo.
venv\Scripts\python -m pip install --require-hashes -r requirements.lock
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -I -m alembic upgrade head

:: Frontend
cd ..\frontend
npm ci
```

**De dónde salen las librerías.** Con la aplicación instalada, nada se descarga de internet: el frontend lleva sus librerías empaquetadas (sin CDN ni fuentes web, y la CSP solo deja cargar lo del propio servidor) y el backend solo habla con PostgreSQL, el Active Directory y el servidor de correo. Las librerías se descargan una sola vez, al instalar, y siempre las mismas:
- Python: `requirements.lock`, con la versión exacta y el hash de cada una (también las que arrastran las de `requirements.txt`), para Linux y Windows. Si PyPI entregara otro archivo, pip se detiene. Para cambiar una, se edita `requirements.txt` y se regenera el bloqueo con el comando que trae al principio; `tests/test_dependencias.py` falla si los dos no coinciden.
- Node: `package-lock.json`, también con hashes (`npm ci`, nunca `npm install` en un servidor).
- Docker: imágenes base con la versión exacta (`python:3.12.16-slim-trixie`, `node:24.22.2-alpine3.24`, `nginx:1.31.8-alpine`, `postgres:15.20-alpine3.24`). Para actualizarlas, se cambia la etiqueta (y la de PostgreSQL también en `.github/workflows/ci.yml`).

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
venv\Scripts\python -m ruff check .
venv\Scripts\python -m mypy app
venv\Scripts\python -m pytest --cov=app
```
`ruff` revisa el código del backend (`backend/ruff.toml`) y `mypy`, los tipos (`backend/mypy.ini`): un valor que puede venir vacío usado como si no, un argumento del tipo equivocado. La CI corre los dos antes de las pruebas, y las pruebas con la cobertura: si baja del piso de `backend/.coveragerc` (93 %; el 22/11/2026 medía 95 %), falla. Las pruebas crean una base de datos temporal en el servidor de `DATABASE_URL` (o `TEST_DATABASE_URL`), le aplican las migraciones, recorren el flujo completo por la API y la borran al terminar. No envían correos ni tocan la base de desarrollo.

```bat
cd frontend
node node_modules/typescript/bin/tsc -b --noEmit
npm run lint
npm test
npm run build
```
`npm test` corre las pruebas unitarias (Vitest). Las reglas que se validan en pantalla y en el servidor (checklist, pasajeros, IMO, contraseñas, formatos y tamaño) comparten sus casos en `backend/tests/espejo/`: si una cambia de un lado y no del otro, falla pytest o Vitest.

```bat
cd frontend
npm run test:e2e
```
Recorre en el navegador una autorización completa: la agencia la envía, UCVMM la devuelve, la agencia la corrige, UCVMM la aprueba, un tercero verifica el QR, el puesto la finaliza y el Administrador la ve en la bitácora. También prueba el formulario sin enviarlo: cambiar de trámite, quitar un pasajero y los documentos adicionales. Y los sectores: UCVMM del Atlántico no ve una solicitud del Pacífico y el supervisor general tampoco (ve solo el trámite de Técnico). `boleta.spec.ts` genera, descarga y anula la boleta de recargo de una solicitud sembrada, y comprueba que la agencia no la ve. Levanta su propio backend (`backend/tests/servidor_e2e.py`, puerto 8001, con la base temporal `argonavis_e2e`, que borra al terminar) y su propio Vite (puerto 5174): no choca con los de desarrollo. Usa el Chrome instalado; en un equipo sin Chrome, `npx playwright install chromium` y `set PLAYWRIGHT_CHROMIUM=1`. Su backend corre con el Python de `backend\venv`; para probar con otro (p. ej. el 3.12 de producción), `set E2E_PYTHON=<ruta del python.exe>`. Además prueba con el teclado el enlace «Saltar al contenido» y que los controles tengan nombre (`accesibilidad.spec.ts`), y la sesión con dos pestañas abiertas, adelantando el reloj del navegador (`sesion.spec.ts`).

En GitHub, `.github/workflows/ci.yml` corre todo lo anterior en cada push a main, más un análisis de vulnerabilidades en las dependencias, que se repite cada lunes. Una vulnerabilidad nueva deja ese análisis en rojo. Para correrlo en el equipo: en `backend`, `venv\Scripts\python -m pip_audit -r requirements.lock --require-hashes` (con `set PYTHONUTF8=1`), y en `frontend`, `npm audit --omit=dev`. Se audita el bloqueo, no `requirements.txt`: así se revisan también las librerías indirectas (el 10/11/2026, eso encontró avisos en pillow y pyasn1, que con `requirements.txt` no se veían).

### Producción
**Docker** (`docker-compose-prod.yml`): copiar `.env.example` como `.env` en la raíz y completar. El backend aplica las migraciones al arrancar (`docker-entrypoint.sh`) y solo es accesible a través de nginx (`/api/`); su puerto no se publica.
```bash
docker compose -f docker-compose-prod.yml up -d --build
```

El backend corre con `UVICORN_WORKERS` procesos (2 por defecto) y con un usuario sin privilegios (`argonavis`, uid 10001), sin las herramientas de compilación en la imagen. A PostgreSQL entra con su propia cuenta (`argonavis_app`), que no puede cambiar tablas y solo agrega a la bitácora: la crea el backend al arrancar con la clave de `POSTGRES_APP_PASSWORD`, que **hay que agregar al `.env`** (`openssl rand -hex 24`); sin ella, el compose no levanta. Si el firewall no deja llegar a Docker Hub (`auth.docker.io`), usa un espejo: `{ "registry-mirrors": ["https://mirror.gcr.io"] }` en `/etc/docker/daemon.json` y `sudo systemctl restart docker`. El volumen `documentos` de una instalación anterior al 08/11/2026 se creó cuando el contenedor corría como root: pásaselo al usuario una vez, antes de levantar la versión nueva (si no, las subidas fallan por permisos):
```bash
docker run --rm --user root --entrypoint chown -v argonavis_documentos:/app/storage/documentos argonavis-backend:latest -R 10001:10001 /app/storage/documentos
```

> **Contenedores endurecidos** (desde el 22/11/2026). Si alguien logra ejecutar algo dentro de uno, que no le sirva de nada:
> - **Sin root:** PostgreSQL corre con el usuario 70, el backend con el 10001 y nginx con el 101, desde que arrancan. Por eso nginx escucha en el 8080 y el 8443 dentro del contenedor; Docker los publica en el 80 y el 443.
> - **Sin privilegios del sistema** (`cap_drop: ALL`) ni forma de conseguirlos (`no-new-privileges`).
> - **Con la imagen de solo lectura.** Lo que cada uno escribe va aparte: los datos y los documentos en sus volúmenes, y los envíos mientras llegan, en `temporales_nginx` y `temporales_backend`. Esos dos van en el disco y no en un tmpfs, que contaría para la memoria del contenedor (un envío pesa hasta 365 MB).
> - **Redes separadas:** PostgreSQL y el backend comparten la red `datos`; nginx no está en ella, así que no alcanza la base. La red `datos` ocupa un rango chico, `172.31.255.240/28`: si coincide con una red del SNM o de la VPN, se cambia con `RED_DATOS` en el `.env` (y hay que bajar la pila una vez: `docker compose -f docker-compose-prod.yml down` y `up -d`).
>
> Los datos de una instalación anterior sirven sin tocarlos. Lo revisan `verificar-despliegue.sh` en cada servidor y la integración continua, que construye esta misma pila y la levanta sobre una base ya existente, después de un reinicio, desde cero y por HTTPS (con PostgreSQL 15 y con la 18).

Después de cada despliegue, `sudo bash verificar-despliegue.sh` revisa sin cambiar nada los contenedores (y su memoria contra su límite), la salud, las cabeceras de seguridad, los puertos, el HTTPS y su certificado, el esquema, los topes de la base, que cada archivo siga en el disco y sea el original, el Active Directory, el correo, los respaldos, el reloj y los errores del log, y termina con «todo bien» o con la lista de fallas.

> **Recursos de cada contenedor** (desde el 10/11/2026). Cada uno tiene un tope de memoria y de procesos, y el backend además de CPU. Sin topes, uno que se desboca se lleva a los demás: sin memoria, el kernel mata al proceso más grande de la VM, que suele ser PostgreSQL. Con ellos, Docker corta solo dentro del contenedor que se pasó y se levanta solo (uvicorn levanta sus procesos; los contenedores tienen `restart: always`). Se ajustan en el `.env`:
>
> | Variable | Por defecto | Qué es |
> |---|---|---|
> | `POSTGRES_MEMORIA` | `1g` | PostgreSQL (con `shm_size` de 256 MB para sus consultas en paralelo) |
> | `BACKEND_MEMORIA` | `1g` | El backend. Medido con 100 usuarios (`tests/carga.py`): ~410 MB con 2 procesos; ~200 MB más por cada proceso extra |
> | `BACKEND_CPUS` | `2` | Núcleos del backend: tantos como `UVICORN_WORKERS` si la VM tiene más núcleos que procesos; en una de 2 núcleos, `1.5`. Así a PostgreSQL y nginx siempre les queda CPU, aunque el backend esté a tope |
> | `FRONTEND_MEMORIA` | `256m` | nginx |
>
> La suma de los topes debería dejar unos 500 MB libres para el sistema: con los valores por defecto (2,25 GB), una VM de 3 GB o más. `verificar-despliegue.sh` muestra el uso de cada contenedor contra su tope, avisa si alguno pasa del 80 % o si Docker lo cortó, y si se cayó algún proceso de uvicorn en las últimas 24 h.

> **Registros** (desde el 22/11/2026). Además de la salida de Docker (`docker logs`), que se borra cada vez que un despliegue recrea el contenedor, quedan en volúmenes, un archivo por día, con la hora de Panamá, durante `LOG_DIAS` días (90):
> - **El backend:** `docker exec argonavis_backend ls /app/registros`. Para un error reportado con su código: `docker exec argonavis_backend sh -c "grep -A20 <código> /app/registros/argonavis-*.log"`.
> - **Los accesos de nginx** (quién pidió qué y desde dónde, también sin sesión): `docker exec argonavis_frontend ls /var/log/argonavis`.

> **Vigilancia** (`vigilar.py`, desde el 22/11/2026). Avisa por correo cuando algo falla. Corre en el servidor y no en un contenedor: si el backend o Docker se caen, igual avisa. Usa el Python del sistema, sin instalar nada, y el mismo correo de la aplicación.
> - **Cada 5 minutos** mira los contenedores, la aplicación, el certificado HTTPS, la base, los correos que no salen, los respaldos, el disco, la memoria, el reloj y las rachas de errores. Avisa a la segunda falla seguida (en un despliegue los contenedores se reinician), no repite mientras sigue igual, lo recuerda una vez al día y avisa cuando se resuelve.
> - **Cada mañana** corre `verificar-despliegue.sh --diario` y manda el resultado si algo falla. **Los lunes** lo manda siempre, para saber que la vigilancia sigue viva, y además prueba que el último respaldo se puede restaurar.
>
> Para instalarla, una sola vez: los destinatarios en `CORREO_ALERTAS` del `.env`, `sudo python3 -I vigilar.py --probar` para comprobar que el correo llega, y en el cron de root (`sudo crontab -e`):
> ```
> */5 * * * * python3 -I /home/vperez/argonavis/vigilar.py >> /var/log/argonavis-vigilancia.log 2>&1
> 0 7 * * *   python3 -I /home/vperez/argonavis/vigilar.py --diario >> /var/log/argonavis-vigilancia.log 2>&1
> ```
> **Lo que no puede ver:** si se apaga el servidor entero, nadie avisa desde adentro. Para eso, el monitoreo de la DTI tiene que consultar `<APP_URL>/api/health` desde otro equipo (responde 200 si todo está bien y 503 si no).

> **Respaldos** (`backup.sh`, cron de root a las 2 AM; la línea del cron está en el script). Cada noche:
> 1. **La base:** `pg_dump` comprimido en `DIR_BACKUPS/argonavis_bd_FECHA.sql.gz`. PostgreSQL lo saca de una foto consistente sin frenar a nadie: el sistema sigue funcionando mientras tanto.
> 2. **Los documentos:** una copia por día en `DIR_BACKUPS/documentos/FECHA/`, en la que solo se copian los archivos nuevos; los que ya estaban en la copia anterior se enlazan (*hard link*) y no ocupan espacio otra vez. Cada copia se ve completa. Un documento nunca se modifica ni se borra (22/11/2026): si uno falta o cambió en el servidor, la copia conserva el original y lo dice en su registro.
> 3. **Retención, con margen** (todavía no se sabe cuántos años se conservan): las últimas `RETENER_DIAS` noches (14), la primera de los últimos `RETENER_MESES` meses (12) y la primera de los últimos `RETENER_ANIOS` años (10). La base y los documentos, de las mismas noches.
>
> Corre con la prioridad más baja de CPU y de disco, para no frenar a quien trabaje a esa hora (los puestos operan de noche). Hasta el 10/11/2026 empaquetaba todos los documentos en un `.tar.gz` cada noche y guardaba 14: ocupaban 14 veces lo que pesan los documentos y cada noche tardaba más. Esos `.tar.gz` se borran solos a los 14 días.
>
> **¿Sirve el respaldo?** `sudo bash probar-restauracion.sh` carga el último en una base aparte, comprueba que traiga datos y que cada documento esté en la copia de esa noche con su tamaño, y la borra. No toca la base de verdad. La vigilancia lo corre los lunes y la integración continua, en cada push.
>
> **Restaurar:** con la base y los documentos **de la misma noche** (los documentos se copian después de la base, así que están todos los que ella nombra), y el backend detenido. En una VM nueva, primero `docker compose -f docker-compose-prod.yml up -d` una vez: crea la base y la cuenta de la aplicación, a la que el respaldo le devuelve sus permisos.
> ```bash
> docker compose -f docker-compose-prod.yml stop backend
> # La base: se borra y se vuelve a crear vacía antes de cargar el respaldo.
> docker exec argonavis_postgres sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
> gunzip -c ~/backups/argonavis_bd_<FECHA>.sql.gz | docker exec -i argonavis_postgres sh -c 'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
> # Los documentos (a un volumen vacío queda igual a la copia; sobre uno con datos, agrega lo que falte).
> sudo cp -a ~/backups/documentos/<FECHA>/. "$(docker volume inspect argonavis_documentos --format '{{ .Mountpoint }}')/"
> docker compose -f docker-compose-prod.yml start backend   # al arrancar, vuelve a dar los permisos de la cuenta de la app
> ```
> **Un documento suelto** (si la revisión de cada mañana avisa que falta o está incompleto): se copia del respaldo, con la ruta que dice el aviso. Está en la última copia, que conserva el original.
> ```bash
> sudo cp -a ~/backups/documentos/<FECHA>/<ruta> "$(docker volume inspect argonavis_documentos --format '{{ .Mountpoint }}')/<ruta>"
> ```
> Los respaldos quedan en el mismo servidor: si se pierde el disco, se pierden con él. Cópialos a otra máquina con `rsync -aH --delete ~/backups/ usuario@otro-servidor:/ruta/argonavis/` (la `H` conserva los enlaces: sin ella, cada copia de los documentos ocuparía todo).

**Windows**: `APP_ENV=production` y `LOG_CARPETA=logs` en `backend\.env`, `migrate.bat`, compilar el frontend (`npm run build`) y `start-backend-prod.bat` (sirve también `frontend/dist`). Si se olvida `migrate.bat`, el backend lo dice al arrancar («La base de datos no está al día con el código: le falta…») y, hasta correrlo y volver a levantarlo, la API responde 503 con el motivo y `/api/health`, «base de datos sin migrar» (en desarrollo, lo mismo: cuando lleguen migraciones nuevas, `migrate.bat`). Con `LOG_CARPETA`, los logs quedan en `backend\logs\argonavis-AAAA-MM-DD.log`, uno por día, y se borran a los `LOG_DIAS` días (30); sin ella, solo se ven en la consola y se pierden al cerrarla.

> **Al actualizar en Windows**, antes de `migrate.bat`: `venv\Scripts\python -m pip install --require-hashes -r requirements.lock` en `backend` y `npm ci` en `frontend` (luego `npm run build`). Docker lo hace solo al reconstruir. Desde el 27/10/2026 el backend usa PyJWT en lugar de python-jose: sin ese paso no arranca (`No module named 'jwt'`). Desde el 10/11/2026 usa también XlsxWriter (exportar las estadísticas a Excel): sin él, la exportación a Excel responde 500 (el PDF y el CSV siguen). Lo viejo se puede quitar después: `venv\Scripts\python -m pip uninstall python-jose ecdsa rsa`. Las sesiones abiertas siguen valiendo.

> **Servidor sin salida a internet.** Se prepara el paquete en un equipo que sí la tenga y se lleva al servidor:
> - **Docker:** en el equipo con internet y Docker, en el commit que se va a instalar, `bash empaquetar-sin-internet.sh`. Deja en `paquete-sin-internet/` las imágenes ya construidas (backend, frontend y PostgreSQL, con todas las librerías adentro), el código de ese commit y `SHA256SUMS`. En el servidor:
>   ```bash
>   sha256sum -c SHA256SUMS
>   tar xzf argonavis-codigo-<commit>.tar.gz -C ~/argonavis
>   docker load -i argonavis-imagenes-<commit>.tar.gz
>   cd ~/argonavis && docker compose -f docker-compose-prod.yml up -d --no-build --pull never
>   ```
>   El `.env` del servidor no va en el paquete: se conserva el que ya está.
> - **Windows:** en un equipo con internet y la **misma versión de Python** que el servidor, en `backend`: `venv\Scripts\python -m pip download --require-hashes -r requirements.lock -d paquetes-python` y, además, `venv\Scripts\python -m pip download setuptools -d paquetes-python` (una librería, win-unicode-console, viene sin compilar y se arma al instalarla). Compila también el frontend (`npm ci` y `npm run build`). Lleva `backend\paquetes-python` y `frontend\dist` al servidor e instala sin internet: `venv\Scripts\python -m pip install --no-index --find-links paquetes-python --require-hashes -r requirements.lock`.

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
>   docker exec argonavis_postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "ALTER DATABASE filetransfer RENAME TO argonavis"'
>   docker compose -f docker-compose-prod.yml up -d --build
>   ```
>   Actualiza la ruta de `backup.sh` en el cron. Cuando todo funcione, borra los volúmenes viejos y los respaldos `filetransfer_*.gz` (la retención ya solo limpia los `argonavis_*`).
> - **Windows:** detén el backend y corre `migrate.bat` (pasa las rutas a relativas). Después renombra la base (`ALTER DATABASE filetransfer RENAME TO argonavis` desde `psql`, conectado a `postgres`), mueve `backend\storage\transfers` a `backend\storage\documentos` y cambia `DATABASE_URL` y `STORAGE_PATH` en `backend\.env`.

> **HTTPS** (listo para activar desde el 22/11/2026; falta el certificado). Sin él, la contraseña de cada login viaja en claro del navegador al servidor. Se activa en el `.env`, sin tocar el código:
> 1. **El nombre y el certificado, con la DTI.** Un nombre propio (p. ej. `argonavis.migracion.gob.pa`) que lleve a la IP del servidor, también para quien entra por la VPN, y un certificado para ese nombre **de una autoridad pública** (el comodín `*.migracion.gob.pa` sirve): los equipos de las agencias no conocen la CA interna del SNM y verían una advertencia. Los públicos duran como mucho 200 días (100 desde marzo de 2027), así que cambiarlo es rutina (punto 4). Para que la clave privada no salga del servidor, la solicitud se hace ahí y a la DTI solo se le manda `argonavis.csr`:
>    ```bash
>    sudo openssl req -new -newkey rsa:2048 -nodes -subj "/C=PA/O=Servicio Nacional de Migracion/CN=<nombre>" -addext "subjectAltName=DNS:<nombre>" -keyout certificados/https/argonavis.key -out argonavis.csr
>    ```
>    Si en cambio entrega un `.pfx`, que trae la clave adentro (pide su contraseña; después se borra del servidor):
>    ```bash
>    sudo openssl pkcs12 -in argonavis.pfx -nocerts -nodes -out certificados/https/argonavis.key
>    sudo sh -c '(openssl pkcs12 -in argonavis.pfx -clcerts -nokeys; openssl pkcs12 -in argonavis.pfx -cacerts -nokeys) > certificados/https/argonavis.crt'
>    ```
>    (Si dice «unsupported», con `-legacy` en las tres.)
> 2. **En el servidor**, en `certificados/https` (no va al repositorio): `argonavis.crt`, el certificado y, detrás, los intermedios; y `argonavis.key`, la clave sin contraseña, que solo lee nginx (corre con el usuario 101):
>    ```bash
>    sudo chown 101:101 certificados/https/argonavis.key && sudo chmod 400 certificados/https/argonavis.key
>    ```
> 3. **Activarlo:** en el `.env`, `USAR_HTTPS=true` y `APP_URL=https://<nombre>`; después, `docker compose -f docker-compose-prod.yml up -d` y `sudo bash verificar-despliegue.sh`. Si falta algo, nginx no arranca y `docker logs argonavis_frontend` dice qué. Desde ahí, el 80 solo lleva a `https://<nombre>` (también a quien entre por la IP) y todos vuelven a entrar una vez: la sesión es de cada dirección. **El navegador que ya entró por HTTPS no vuelve a HTTP por ese nombre durante un año** (`Strict-Transport-Security`): volver a `USAR_HTTPS=false` solo sirve entrando por la IP.
> 4. **Cambiarlo, antes de que venza:** se reemplazan los dos archivos y `sudo docker exec argonavis_frontend nginx -s reload`, sin cortar a nadie; si el nuevo tiene un error, nginx sigue con el anterior y lo dice. La vigilancia avisa 21 días antes y `verificar-despliegue.sh` revisa el nombre, la fecha, los intermedios y los permisos de la clave. Vencido, con el nombre no entra nadie: de emergencia, `https://<IP>` y aceptar la advertencia.
>
> En Windows, el certificado va en el proxy que esté delante de uvicorn.

> **TLS con el Active Directory y con el correo** (pendiente de la DTI). Sin él, la contraseña de cada login viaja en claro del backend al controlador de dominio (LDAP 389). La CA interna que firma sus certificados se pone en `certificados/ca` (PEM); dentro del contenedor es `/certificados/ca/<archivo>.pem`.
> - **Active Directory:** `LDAP_USAR_SSL=true` y `LDAP_PORT=636` (o `LDAP_STARTTLS=true` sobre el 389), con `LDAP_CA_CERT=/certificados/ca/<archivo>.pem`. `LDAP_HOST` debe ser el nombre que trae el certificado (no la IP). Probarlo primero en desarrollo. Si la CA no está, el backend no arranca y lo dice.
> - **Correo:** si el SMTP pide usuario y contraseña (`MAIL_USERNAME` / `MAIL_PASSWORD`), activar `MAIL_STARTTLS=true` (587 o 25) o `MAIL_USAR_SSL=true` (465); si no, viajan en claro, y el backend lo advierte al arrancar. Como con el AD: `MAIL_HOST` con el nombre del certificado y `MAIL_CA_CERT=/certificados/ca/<archivo>.pem` (la vigilancia usa la misma). Sin TLS (lo de siempre), ni siquiera se intenta STARTTLS.

> **PostgreSQL 18** (22/11/2026). Los servidores de hoy usan la 15.20, que se queda sin soporte en noviembre de 2027; la integración continua prueba todo con las dos. Sin tocar el `.env`, un despliegue no cambia la versión.
> - **En un servidor nuevo**, antes del primer arranque: las dos líneas de `.env.example` (`POSTGRES_IMAGEN` y `POSTGRES_VOLUMEN`). Van juntas, porque la imagen de la 18 guarda los datos en otra carpeta; `verificar-despliegue.sh` comprueba que estén en su volumen. Sin salida a internet, `POSTGRES_IMAGEN=postgres:18.7-alpine3.24 bash empaquetar-sin-internet.sh`.
> - **Pasar un servidor de la 15 a la 18** (una vez, con el sistema detenido unos minutos). La 18 no abre los datos de la 15: se pasan con un respaldo, en un volumen nuevo. El de la 15 queda intacto; para volver, se quitan las dos líneas del `.env` y `up -d`.
>   ```bash
>   docker compose -f docker-compose-prod.yml stop frontend backend
>   sudo DIR_BACKUPS=$HOME/backups bash backup.sh && sudo DIR_BACKUPS=$HOME/backups bash probar-restauracion.sh
>   # En el .env, las dos líneas. Después, la base nueva y vacía, con la cuenta de la aplicación:
>   docker compose -f docker-compose-prod.yml up -d postgres_db backend
>   ```
>   Y lo de «Restaurar» (arriba) con la base de ese respaldo; los documentos no se tocan. Al final, `docker compose -f docker-compose-prod.yml up -d` y `sudo bash verificar-despliegue.sh`.

> **Verificación pública del QR** (14/11/2026, para la DTI). Quien escanea el QR del PDF ve si la autorización es auténtica y si sigue vigente, y con «Ver autorización (PDF)» abre el PDF en su celular, sin cuenta: la copia de la agencia (sin nombres de funcionarios), mientras valga y hasta `DIAS_PDF_PUBLICO` (30) días después de la operación. Si ya no se puede ver así, la página dice por qué; los documentos del expediente nunca salen por ahí.
> - **Hoy el QR solo funciona dentro de la red del SNM.** Desde un celular sin VPN solo se llega a lo que está en internet. Para eso, la DTI publica **solo la verificación** con un nombre propio y HTTPS (sin HTTPS no: el PDF lleva los datos de los pasajeros). La plantilla del proxy está en `frontend/nginx-verificacion-publica.conf`: deja pasar la página `/verificar/{código}`, lo que esa página carga y dos rutas de solo lectura de la API (`GET /api/v1/verificacion/{código}` y su `/autorizacion.pdf`). Todo lo demás (el login, las bandejas, los documentos, el resto de la API) responde 404 desde internet.
> - En el nginx interno, confiar en ese proxy para la IP real del cliente (`set_real_ip_from <IP del proxy>; real_ip_header X-Real-IP;`, ver el comentario en `frontend/nginx.conf`): sin eso, la bitácora y el tope por IP verían a todos como el proxy.
> - En el `.env`: `URL_VERIFICACION_PUBLICA=https://<el nombre publicado>` y reiniciar el backend. Los PDF que se descarguen desde entonces llevan el QR a esa dirección; los ya impresos siguen con la interna (se vuelven a descargar). `verificar-despliegue.sh` avisa mientras falte.
> - Ya en la aplicación: el código del QR es aleatorio (192 bits), el PDF tiene tope por IP (`LIMITE_PDF_PUBLICO_POR_MINUTO`, 10), cada vista queda en la bitácora (con la IP) y la respuesta no se guarda en caché ni se indexa.

> **Al migrar un servidor que venía del storage** (revisión `d4f1a8c27e90`): las transferencias sueltas que existan se **eliminan**, en la base y en disco. Si alguna hace falta, descárgala antes de actualizar.

> **Primer SysAdmin** (desde la revisión `c7a2e94b1f30`): usuarios, roles y permisos los gestionan el SysAdmin y el Administrador, y la migración no le asigna esos roles a nadie. Después de migrar, nómbralo desde la consola del servidor (queda en la bitácora). En una instalación nueva no hay usuarios: agrega `--crear-ad` para darlo de alta desde el Active Directory, o `--crear-local` para una cuenta local con contraseña temporal (se muestra una vez):
> ```bat
> cd backend
> venv\Scripts\python -m app.infrastructure.asignar_rol <usuario> SysAdmin --crear-ad
> ```
> Con Docker: `docker compose -f docker-compose-prod.yml exec backend python -m app.infrastructure.asignar_rol <usuario> SysAdmin`. El mismo comando sirve para recuperar el acceso si se pierde.

---

## Estructura

```
ArgoNavis/
├─ backend/
│  ├─ app/
│  │  ├─ main.py               # arma la aplicación: ciclo de vida, middlewares, rutas, salud, frontend compilado
│  │  ├─ api/
│  │  │  ├─ v1/                # endpoints: solo orquestan (auth, solicitudes, catálogos, admin, bitácora...)
│  │  │  ├─ manejadores.py     # respuestas a los errores que no son HTTPException (BD caída, 429, 409)
│  │  │  └─ middleware.py      # tope del cuerpo de cada petición y código de pedido
│  │  ├─ core/                 # transversal: config, contraseñas y JWT, LDAP, correos, rate limit, horario, identidad
│  │  ├─ domain/
│  │  │  ├─ models/            # ORM: solicitud, tramite, catalogo, user, rol, audit_log
│  │  │  ├─ schemas/           # contratos Pydantic de la API
│  │  │  ├─ repositories/      # acceso a BD, uno por agregado
│  │  │  └─ services/          # reglas: solicitud, tramite (checklist), usuarios, roles, catálogos, notificacion (correos), pendientes (la campana), auth
│  │  ├─ informes/             # PDF de la autorización; estadísticas en Excel, PDF y CSV; consulta histórica en Excel
│  │  └─ infrastructure/
│  │     ├─ database.py        # motor async y sesión por request
│  │     ├─ almacenamiento.py  # validación y guardado de documentos (carpeta por solicitud)
│  │     ├─ revision_office.py # Word y Excel: formato, macros y tamaño, sin abrirlos con una librería
│  │     ├─ tareas.py          # vencimientos, con un solo ejecutor entre workers
│  │     └─ asignar_rol.py     # nombra el primer SysAdmin desde la consola
│  ├─ alembic/versions/        # el esquema completo vive aquí
│  ├─ tests/                   # pytest sobre BD temporal; espejo/: casos compartidos con el frontend;
│  │                           #   entorno_pruebas.py: lo común a las pruebas, al backend del E2E y a la prueba de carga
│  └─ storage/documentos/      # documentos de los expedientes (NO versionar)
│
├─ docs/                       # línea base funcional y técnica: Word, BPMN y diagramas (ver docs/README.md)
│
├─ frontend/e2e/               # recorrido completo en el navegador (Playwright)
│
└─ frontend/src/
   ├─ App.tsx                  # rutas y proveedores (tema, sesión, permisos, avisos); guardias en components/RutasProtegidas
   ├─ api/                     # cliente axios + un módulo por dominio
   ├─ components/              # UI reutilizable (MarcoPagina, ModalPreview, Iconos...)
   ├─ context/                 # proveedores: tema, autenticación, permisos, notificaciones (pendientes)
   ├─ hooks/                   # useAutenticacion, usePermisos, usePendientes
   ├─ pruebas/                 # ayudas de las pruebas unitarias (cada *.test.ts va junto a su módulo)
   └─ modulos/
      ├─ autenticacion/        # login y cambio de contraseña
      ├─ solicitudes/          # formulario/, expediente/, bandejas/, historico/, verificacion/ y lo compartido
      └─ administracion/       # usuarios, roles, catálogos, trámites, estadísticas, bitácora
```

---

## El flujo

| Rol | Permiso | Qué hace |
|---|---|---|
| **Naviera** (usuario de una agencia) | `T-CREAR-BASICA` | Envía solicitudes de su agencia y las corrige cuando UCVMM las devuelve. Todos los usuarios de la agencia comparten sus solicitudes. |
| **UCVMM** | `T-PROCESAR-PACIFICO` + sector asignado | Revisa las solicitudes de su sector (Pacífico o Atlántico): verifica impedimentos tripulante por tripulante (obligatorio para aprobar), aprueba, devuelve a corrección o deniega. No ve las del otro sector. Tiene la consulta histórica. |
| **Supervisor de sector** | `T-SUPERVISAR-SECTOR` + sector asignado | Solo lectura: ve las solicitudes de su sector (expedientes, documentos, autorizaciones, estadísticas y consulta histórica), sin decidir nada. |
| **Supervisor general** (UCVMM en Tocumen) | `T-SUPERVISAR-TODO` | Solo lectura del trámite de Técnico, Superintendente o Supernumerario, de los dos sectores (16/11/2026). Sin estadísticas ni consulta histórica. |
| **Puesto de Control** | `T-FINALIZAR-PUERTO` + puestos asignados | Ve las aprobadas de sus puestos, de cualquier año, en su bandeja; verifica impedimentos tripulante por tripulante (obligatorio para finalizar, aparte de la de UCVMM) y las finaliza con un comentario. Se finaliza en el puesto autorizado: si la operación se hace en otro, la agencia presenta una nueva solicitud. |
| **Administrador** | todos los `T-*` | Acceso total: bandejas y expedientes de los dos sectores, catálogo de trámites, agencias, puestos, sectores, nacionalidades restringidas, estadísticas, bitácora, usuarios y roles. |
| **SysAdmin** | ninguno | Rol técnico: usuarios, roles (con los permisos fijos del sistema) y bitácora. No ve solicitudes ni expedientes. |

Administrador y SysAdmin se reconocen por el nombre del rol (`rol_personalizado.nombre`): no se pueden renombrar y sus permisos son fijos. Nadie cambia su propio rol. El último SysAdmin activo no se puede desactivar, borrar ni cambiar de rol.

**Estados:** `review` → `approved` → `finalized`; `review` → `returned` → (corrige) `review`; `review` → `denied`. Una aprobada sin finalizar a tiempo (`DIAS_GRACIA_FINALIZACION`: hasta las 23:59 del segundo día después de la operación, 72 h desde que empieza ese día), o una devuelta sin corregir en el plazo (`PLAZO_CORRECCION_DIAS`: 72 h desde la devolución), pasa a `expired`.

**Reglas que conviene conocer:**
- El checklist de documentos de cada trámite vive en BD (`tipos_tramite`, `documentos_requeridos`, `tramite_documentos`). Las condiciones se resuelven en `ServicioTramite.construir_casillas`, espejado en `frontend/src/modulos/solicitudes/checklist.ts`.
- Fechas del formulario:
  - La operación va de hoy hasta `DIAS_MAXIMOS_ANTICIPACION` (365) días.
  - Cada pasajero debe tener 18 años cumplidos y haber nacido desde 1900.
  - El pasaporte y el seamanbook tienen que vencer después del nacimiento.
- En ningún trámite se puede enviar la solicitud si el pasaporte vence antes de 3 meses después de la operación; el seamanbook vencido solo se avisa (13/11/2026). Solo el rango Marino porta seamanbook; en Embarque se le pide la libreta sin importar la nacionalidad.
- El catálogo sigue tal cual los documentos:
  - Los documentos de cada trámite son los del Formulario No. 3 oficial.
  - Todos se suben por pasajero, salvo la Lista de Tripulantes (su nombre oficial en el Form. 3) y el Formulario No. 3, que van a la solicitud.
  - Excepción (30/10/2026): a los rangos distintos de Marino solo se les piden las Generales de pasaporte y el boleto aéreo (`tramite_documentos.rangos`).
  - Excepción (11/11/2026): a los técnicos, supernumerarios y superintendentes se les piden, en Desembarque, la Carta de Responsabilidad, las Generales de pasaporte, el Contrato de Trabajo y, opcional, el boleto aéreo; en Embarque, lo mismo sin el boleto (`tramite_documentos.rangos_opcional`). Un documento opcional se puede dejar sin adjuntar.
  - Excepción (13/11/2026): el Formulario No. 3 se adjunta en todos los trámites, uno por solicitud y para cualquier rango.
  - Rango Pasajero (13/11/2026): se le piden los documentos del Marino, salvo la Libreta. Embarque y Desembarque admiten solo Marino, Pasajero y Militar; los técnicos, supernumerarios y superintendentes van por el trámite de Técnico.
  - Vigencia (13/11/2026): el pasaporte tiene que vencer al menos 3 meses después de la operación (13/11 → 13/02 o después). El seamanbook vencido no impide enviar: se avisa y queda señalado en el expediente.
  - Panameños (14/11/2026): no se les pide visa ni boleto aéreo en Embarque y Desembarque, ni la Visa Especial de Marino en Cambio de nave (condición `solo_extranjeros`). El marino panameño presenta Generales de pasaporte y Libreta; el pasajero y el militar, solo Generales.
  - Sellado de Shore Pass (14/11/2026): solo el rango Marino.
- Subir y bajar (16/11/2026): en Embarque y Desembarque la agencia responde «¿Subir y bajar?» (Sí / No). Con «Sí», cada pasajero adjunta además la Carta de Responsabilidad (Form. No. 7).
- La ocupación del pasajero ya no se pide (16/11/2026). Las solicitudes de antes la siguen mostrando.
- Cambio de puerto (13/11/2026): no es un trámite aparte. En Embarque y Desembarque la agencia indica si hay cambio de puerto y elige el nuevo puesto de control, de cualquier sector desde el 18/11/2026 (antes, solo del mismo). La revisa UCVMM del sector del primer puesto y la ve y la finaliza el puesto nuevo; el primero no la ve desde el 22/11/2026.
- Una solicitud admite hasta 30 pasajeros.
- Nacionalidad restringida:
  - En todos los trámites y rangos se le pide la Visa (14/11/2026), además de lo que pida el trámite: en Embarque y Cambio de nave, al marino y al pasajero, también la Visa Especial de Marino. El formulario y el expediente lo señalan.
  - En Desembarque se exige el Formulario No. 6 de custodia por pasajero.
  - En Desembarque, Urgencias, Renovación y Shore Pass, al aprobar se avisa a la agencia que debe realizar el trámite de solicitud de custodia (`tipos_tramite.aviso_custodia`).
  - La lista de nacionalidades restringidas la marca el admin; no viene ninguna sembrada.
- El trámite de Técnico, Superintendente o Supernumerario solo admite pasajeros con esos rangos, y el Sellado de Shore Pass solo al Marino (`tipos_tramite.rangos_permitidos`).
- `backend/tests/test_documento_ucvmm.py` tiene la lectura del Formulario No. 3 y del documento de UCVMM trámite por trámite (campos, documentos, vigencias, custodia): si el catálogo se aparta de él, la prueba falla.
- Además del checklist, se pueden adjuntar hasta 20 documentos adicionales por solicitud.
- Lo interno no le llega a la agencia, porque el backend lo filtra, no solo la vista:
  - La verificación de impedimentos (por pasajero).
  - La observación de aprobación.
  - El comentario de cierre del puesto de control.
  - Los nombres de los funcionarios: en su historial ve «Servicio Nacional de Migración» o "Puesto de control".
  - Sí ve los motivos de devolución y de negación.
- **Nombre neutro para la agencia (11/11/2026):** en lo que ve la agencia (pantallas, correos y PDF) no se nombran las unidades internas (UCVMM, los sectores): dice «Servicio Nacional de Migración». Las pantallas y los informes del SNM no cambian.
- El PDF de la autorización no lleva observaciones. El de la agencia dice "Aprobada por: Servicio Nacional de Migración"; el personal del SNM descarga una copia interna con el nombre de quien aprobó y, ya finalizada, el de quien finalizó (14/11/2026). Quien escanea el QR ve la de la agencia.
- Las autorizaciones que UCVMM aprueba antes de las 07:00, desde las 15:01 o en fin de semana (hora de Panamá) cuentan como fuera del horario laboral. Lo muestran las estadísticas y una insignia en las bandejas y en el expediente.
  - Desde el 11/11/2026 lo ve también la agencia, con el recargo por atención fuera del horario laboral (`COSTO_FUERA_DE_HORARIO`, B/.20.00): en su bandeja, en el expediente, en el correo de aprobación y en el PDF.
  - El recargo se guarda en la solicitud al aprobar: cambiar el monto no toca lo ya aprobado.
  - **Boleta de recargo (16/11/2026):** UCVMM, el supervisor de sector o el puesto de control la generan desde el expediente con el número de oficio, que no se repite. Una mal hecha se anula con motivo y se genera otra, como en un talonario. La agencia no la ve: la imprime el SNM y se la entrega. El formato de hoy es un borrador.
- **Estadísticas exportables:** Excel, PDF o CSV del periodo elegido, con el escudo del SNM, el logo de ARGO NAVIS, quién lo generó y «Uso interno del SNM» (`GET /api/v1/solicitudes/estadisticas/exportar`).
- **Consulta histórica (11/11/2026):** UCVMM, el supervisor de sector y el Administrador buscan solicitudes de cualquier año en «Consulta histórica» (menú, o el botón de las bandejas). El puesto de control no la tiene desde el 22/11/2026: consulta las suyas en su bandeja, como cada agencia.
  - Filtros: texto, tripulante (nombre, pasaporte o seamanbook), agencia, puesto, trámite, estado, fecha de envío o de la operación (con un atajo por año) y «solo aprobadas fuera del horario».
  - **«Autorizadas» (22/11/2026):** las que se aprobaron alguna vez: vigentes, finalizadas y vencidas sin finalizar. El estado «Aprobada» dura unos días.
  - La búsqueda no distingue tildes ni mayúsculas y admite las palabras en cualquier orden («nunez jose» encuentra a José Ángel Núñez). Al buscar un tripulante, dice cuál es.
  - Cada uno ve lo mismo que en los expedientes, y los archivos se abren en cualquier estado. El PDF de una que venció sin finalizarse lo descarga el SNM, con el sello EXPIRADA.
  - Exporta a Excel lo que cumple los filtros, hasta 5000 filas (`POST /api/v1/solicitudes/historico` y `/historico/exportar`: los filtros van en el cuerpo, para que el tripulante no quede en la URL ni en los logs).
- **Historial completo (22/11/2026):** en el expediente, para UCVMM, los supervisores y el Administrador.
  - Al corregir una devuelta se guarda lo que la agencia había enviado, quién la devolvió y por qué, y qué cambió. Los documentos que reemplaza se conservan.
  - Cada archivo lleva su huella (SHA-256), que se comprueba al abrirlo: si alguien lo cambió, no se muestra.
  - El PDF de la autorización se guarda tal como se emitió, al aprobar y al finalizar: es el que reciben la agencia y quien escanea el QR.
  - En la base, la aplicación no puede borrar documentos ni tocar lo guardado.
- **Notificaciones internas:** la campana de la cabecera muestra lo que le toca hacer a cada rol (por revisar, por corregir, por finalizar) y las novedades de sus solicitudes. Consulta `GET /api/v1/pendientes` cada minuto con la pestaña a la vista.
- **Separación de funciones:** nadie revisa una solicitud que creó o que es de su propia agencia.
- **Sectores:** cada puesto de control es del Sector Pacífico o del Atlántico (Catálogos → Sectores). UCVMM y el supervisor de sector ven solo las solicitudes de su sector; el aviso de cada solicitud nueva va al correo de su sector. Una ya revisada se queda en el sector que la revisó aunque el puesto cambie (22/11/2026): el expediente dice los dos.
- Cada transición bloquea la fila de la solicitud: dos revisores no pueden aprobar y negar la misma a la vez.
- Las solicitudes no se borran. Un usuario, agencia o puesto con solicitudes se desactiva en lugar de eliminarse.
- El QR del PDF lleva a `/verificar/{codigo}`, una página pública que solo muestra lo necesario para verificar la autorización (pasaportes enmascarados).

**Avisos por correo** (en segundo plano, después de guardar): a UCVMM (`CORREO_UCVMM`) cuando llega o se corrige una solicitud; a la agencia (su buzón y sus usuarios) cuando se aprueba, devuelve, deniega o expira; al puesto de control (su buzón y sus funcionarios) cuando se aprueba. El asunto es `Autorizaciones Marítimas · AM-2026-000011 · Aprobada`; el cuerpo es un "pase marítimo" con el logo de ARGO NAVIS incrustado (se ve aunque el cliente bloquee las imágenes externas), y el correo lleva versión en texto plano. El remitente sale de `MAIL_FROM_NAME`. Cada aviso se guarda en una cola (tabla `correos_salida`) junto con la operación: si el servidor de correo falla, se reintenta durante unas 24 horas, aunque el backend se reinicie; agotados los intentos, queda como fallido en el log.

**Documentos del expediente:** se ven y descargan solo con sesión y acceso a la solicitud (`GET /api/v1/solicitudes/{id}/documentos/{doc}`). Cada vista y cada descarga queda en la bitácora con el usuario. **Se aceptan PDF, Word y Excel** (.pdf, .doc, .docx, .xls y .xlsx). Al subirse se validan:
- la extensión y el tamaño;
- que el contenido sea de verdad de ese formato (un archivo renombrado no pasa);
- que los de Word y Excel no traigan macros y que abiertos no ocupen más de 50 MB;
- el tipo real del contenido.

La vista previa muestra PDF, .docx y .xlsx; los .doc y .xls del formato viejo se descargan.

### Puesta en marcha
1. **Usuarios** (Administrador o SysAdmin, en `/admin`): agrega los del Active Directory o crea cuentas locales para los usuarios externos, y asigna su rol (Naviera, Sector Pacífico, Puesto de Control, Administrador o SysAdmin). El primer SysAdmin se nombra desde la consola (ver *Producción*).
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
- Con varias pestañas abiertas, la inactividad es la de todas: mientras se trabaja en una, las demás no avisan ni cierran la sesión. Salir en una pestaña saca a las demás.
- Cerrar sesión, cambiar la contraseña o que un Administrador o SysAdmin la restablezca invalida los tokens ya emitidos de esa cuenta (en cualquier navegador).
- Si se pide una página sin sesión (p. ej. el enlace de un correo), tras el login se vuelve a ella.

### Seguridad
Las agencias entran por la VPN, pero no son del SNM: ARGO NAVIS las trata como usuarios no confiables.
- **Archivos:** PDF, Word y Excel de hasta 2 MB cada uno, comprobados por su contenido; los de Office con macros se rechazan. El backend no los abre con una librería: los recorre de a trozos, con tope de memoria y de tamaño, así que uno muy comprimido no lo puede tumbar. La vista previa del Word va en un marco aislado (sin scripts, sin enlaces, sin acceso a la sesión).
- **Navegador:** Content-Security-Policy (solo código propio de ARGO NAVIS), `X-Frame-Options: DENY` y `nosniff`, en nginx y en el backend cuando sirve el frontend.
- **Topes:** login por IP (10 por minuto), por cuenta y por hora los envíos (`LIMITE_ENVIOS_POR_HORA`, 30), las exportaciones de las estadísticas (`LIMITE_EXPORTACIONES_POR_HORA`, 30) y las descargas del PDF (`LIMITE_PDF_POR_HORA`, 120), y 2 MB por archivo, en cualquier formato. Se cuentan en memoria, por proceso: con varios workers, cada uno lleva su cuenta.
- **Tamaño de cada petición:** 1 MB en la API y, al crear o corregir una solicitud (todos los archivos van juntos), 365 MB: lo más que pesa un envío válido (30 tripulantes × 5 documentos + 12 de la solicitud, con la Form. 7 de hasta 10 archivos, + 20 adicionales, de 2 MB). nginx y el backend cortan lo que pase de ahí sin leerlo; antes nginx aceptaba 200 MB en cualquier ruta, también en el login, y el backend los leía enteros antes de comprobar la sesión.
- **Rutas sin sesión:** solo el login, la verificación del QR (con el PDF de la agencia desde el 14/11/2026) y el health check; una prueba falla si aparece otra.
- **Producción:** no arranca con una `SECRET_KEY` corta o de ejemplo.

### Tareas de fondo
Cada `VENCIMIENTOS_INTERVALO_MINUTOS` se expiran las solicitudes con plazos vencidos y se avisa a la agencia. Con varios workers, un *advisory lock* de PostgreSQL deja que una sola vuelta haga el trabajo. Si una vuelta falla, el error queda en el log y la tarea sigue con la siguiente.

### Capacidad y disponibilidad
- **Conexiones con PostgreSQL:** cada proceso abre hasta `BD_POOL` + `BD_POOL_EXTRA` (5 + 10). Con los 4 workers de `start-backend-prod.bat` son 60, por debajo de las 100 que admite PostgreSQL por defecto. Si se suben los workers, hay que bajar el pool (o subir `max_connections`).
- **Topes por conexión:** una consulta se cancela a los `BD_TIEMPO_MAXIMO_CONSULTA` segundos (60) y una transacción abierta sin actividad se cierra a los `BD_TIEMPO_MAXIMO_INACTIVA` (300). Así una petición colgada no retiene la conexión ni los bloqueos de fila.
- **Con la base caída, lenta o sin conexiones libres** (más de `BD_POOL_ESPERA` segundos esperando), la API responde 503 con el motivo, y el frontend lo muestra; antes era un 500 sin explicación.
- **`/api/health`** comprueba la base: con la base caída responde 503 y Docker marca el servicio como no sano. Reusa la respuesta 5 segundos, para no cargar la base.
- **Correos:** un solo despacho a la vez en cada proceso, y cada envío espera al servidor de correo como mucho `MAIL_TIEMPO_ESPERA` segundos (20).
- **Trabajos pesados** (exportar las estadísticas, el PDF de una autorización): cada proceso arma como mucho `TRABAJOS_PESADOS_A_LA_VEZ` (2) a la vez y el resto espera su turno, sin retener la conexión a la base. El peor caso, el PDF de las estadísticas, son ~0,6 s de CPU y ~10 MB.
- **Subidas:** cada archivo pasa al disco temporal desde los 64 KB (Starlette los dejaba en memoria hasta 1 MB): un envío grande ocupa ~9 MB de memoria en vez de ~140. Con menos de `ESPACIO_MINIMO_LIBRE_MB` (1024) libres en el disco de los documentos, no se reciben archivos (507, «avisa a la DTI») y queda un error en el log: que las subidas no llenen el disco que comparten la base y los respaldos.
- **Memoria y CPU de cada contenedor:** topes en el compose (ver *Producción → Recursos*).
- **nginx** resuelve el nombre del backend en cada petición (el DNS de Docker): si el contenedor del backend se recrea con otra IP, sigue funcionando sin reiniciar nginx.
- **Código de cada pedido** (`X-Request-ID`): va en cada línea del log y en los errores 5xx que ve el usuario («… (código 3f2a1b9c0d4e)»). Con ese código se encuentra su traza en el log.
- **Prueba de carga** (`backend/tests/carga.py`; no la corre pytest):
  ```bat
  cd backend
  venv\Scripts\python tests\carga.py --usuarios 100 --segundos 90
  ```
  Levanta el backend con 2 procesos contra una base temporal y pone a N usuarios a pedir algo cada 1 a 3 segundos, de 5 a 10 veces más que el uso real. El 08/11/2026, en un equipo de desarrollo de 4 núcleos con PostgreSQL y el generador de carga en la misma máquina, con 100 usuarios durante 90 s:
  - 2.683 pedidos y **ningún error**.
  - La mitad respondió en 1 s o menos, el 95 % en menos de 4 s, y las 30 conexiones a la base llegaron al tope.
  - El techo fue de unos 29 pedidos por segundo. Como referencia, 100 usuarios reales piden unos 8 por segundo: una acción cada 10 a 30 s, más la campana cada minuto.
  - Para más capacidad: un proceso por núcleo (`UVICORN_WORKERS`), sin pasar el tope de conexiones de PostgreSQL.

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
- HTTPS en el servidor, y TLS con el Active Directory y con el correo: ya se activan en el `.env` (ver *Producción*); faltan el nombre y los certificados, que da la DTI.
- Edición del catálogo de trámites desde la interfaz.
- Envío por partes para tripulaciones muy grandes: un envío lleva todos sus archivos juntos (hasta 365 MB), y por una VPN lenta uno así puede pasar los 5 minutos que espera el navegador.
- Política de retención de datos personales (Ley 81 de 2019) y copia de los respaldos fuera del servidor.
- Solicitud de Custodia y Solicitud de Transbordos (el documento de UCVMM dice que faltan por levantar).
- Segundo factor (código TOTP) para las cuentas de las agencias: decidido para más adelante.
- Antivirus (ClamAV) para los archivos que suben las agencias: por ahora no; necesita el servicio en el servidor.
- Feriados en el horario laboral de las estadísticas y notificación de Windows en la campana: decididos para más adelante (reunión del 30/10/2026).
- Confirmar con UCVMM si el aviso de custodia al aprobar aplica también a los rangos distintos de Marino.
