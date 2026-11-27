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

# Copiar e instalar los requerimientos de forma explícita
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código fuente del servidor
COPY . .

# Comando para ejecutar la aplicación con Gunicorn y UvicornWorker adaptado a FastAPI y el puerto de Render
CMD sh -c "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 2 --threads 4 --timeout 120"
