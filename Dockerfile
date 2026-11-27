FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD sh -c "gunicorn main:app --bind 0.0.0.0:${PORT:-10000} -k uvicorn.workers.UvicornWorker --workers 2 --timeout 120"
