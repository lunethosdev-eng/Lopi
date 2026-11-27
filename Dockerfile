# Usar una imagen oficial de Python ligera
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para compilaciones y lxml/bs4 si fuera necesario
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar los requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente del servidor
COPY . .

# Render asigna dinámicamente un puerto mediante la variable de entorno $PORT. 
# Si se ejecuta localmente sin $PORT, usará por defecto el puerto 10000.
# Usamos -k uvicorn.workers.UvicornWorker porque FastAPI es ASGI.
CMD sh -c "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 2 --threads 4 --timeout 120"
