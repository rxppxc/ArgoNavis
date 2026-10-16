FROM python:3.12-slim
# fonts-dejavu-core: fuente Unicode para el PDF de la autorización (nombres con ş, ł, ğ…)
RUN apt-get update && apt-get install -y libmagic1 libpq-dev build-essential fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
