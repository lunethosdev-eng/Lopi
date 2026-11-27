FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Dependencias declaradas aquí para que Render no dependa de la ruta/nombre
# de requirements.txt durante el build. COPY . . evita el fallo anterior.
RUN python -m pip install --upgrade pip && \
    python -m pip install \
      "fastapi==0.115.6" \
      "uvicorn[standard]==0.34.0" \
      "cloudscraper==1.2.71" \
      "beautifulsoup4==4.12.3" \
      "requests==2.32.3" \
      "gunicorn==23.0.0"

COPY . .
EXPOSE 10000
CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 2 --timeout 120 --access-logfile -"]
