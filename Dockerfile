FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm ffmpeg chromium \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 libgtk-3-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt package.json ./
RUN python -m pip install --upgrade pip && pip install -r requirements.txt && npm install --omit=dev
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
COPY . .
EXPOSE 10000
CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 1 --timeout 180 --access-logfile -"]
