FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

# Install OS packages required by Chromium, FFmpeg and Node.js.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm ffmpeg chromium \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies directly so the build does not depend on COPYing
# requirements.txt or package.json (the files missing in the reported build).
RUN python -m pip install --upgrade pip \
    && pip install \
      fastapi==0.115.6 \
      'uvicorn[standard]==0.34.0' \
      beautifulsoup4==4.12.3 \
      requests==2.32.3 \
      gunicorn==23.0.0 \
    && npm install --no-save --omit=dev playwright@1.56.1

# Copy the application after dependencies are installed.
COPY . .

EXPOSE 10000
CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 1 --timeout 180 --access-logfile -"]
