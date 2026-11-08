# ── Dependencias: se instalan (y, si alguna no trae binario, se compilan) aquí ──
FROM python:3.12-slim AS dependencias
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Imagen final: sin compiladores y sin root ──────────────────────────────────
# Antes llevaba build-essential (unos 250 MB) y corría como root: un fallo en la
# app, o en una librería que lee lo que suben las agencias, tenía root en el
# contenedor y un compilador a mano.
FROM python:3.12-slim
# libmagic1: python-magic (el control cruzado del tipo de archivo).
# fonts-dejavu-core: fuente Unicode para el PDF de la autorización (nombres con ş, ł, ğ…).
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 argonavis \
    && useradd --system --uid 10001 --gid argonavis --home-dir /app --shell /usr/sbin/nologin argonavis
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=dependencias /opt/venv /opt/venv
WORKDIR /app
COPY . .
# - Sin los CR de un clon hecho en Windows antes del .gitattributes: con CRLF, el
#   contenedor no arranca («bash\r: No such file or directory»).
# - El bytecode se compila aquí: el usuario de la app no puede escribir en /app.
# - La carpeta de los documentos es del usuario de la app. Un volumen nuevo la
#   copia con ese dueño; uno creado antes, cuando el contenedor corría como root,
#   hay que pasárselo una vez (README → Producción → Docker).
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh \
    && python -m compileall -q app alembic \
    && mkdir -p /app/storage/documentos && chown -R argonavis:argonavis /app/storage
USER argonavis
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
