FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Instalación autocontenida: no depende de que requirements.txt esté en la raíz
# configurada por Render. El archivo requirements.txt se conserva para otros despliegues.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      "fastapi==0.115.6" \
      "uvicorn[standard]==0.34.0" \
      "cloudscraper==1.2.71" \
      "beautifulsoup4==4.12.3" \
      "requests==2.32.3" \
      "gunicorn==23.0.0"

COPY . .
EXPOSE 10000
CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 2 --timeout 90 --access-logfile -"]
