# Usar una imagen oficial de Python ligera
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para compilaciones y lxml/bs4
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar las librerías directamente sin depender de requirements.txt
RUN pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn==0.28.0 \
    cloudscraper==1.2.71 \
    beautifulsoup4==4.12.3 \
    requests==2.31.5 \
    pydantic==2.6.4 \
    gunicorn==21.2.0

# Copiar todo el código fuente del servidor
COPY . .

# Comando para ejecutar la aplicación con Gunicorn y UvicornWorker
CMD sh -c "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 2 --threads 4 --timeout 120"
