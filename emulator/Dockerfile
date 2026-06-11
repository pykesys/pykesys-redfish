FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8888

HEALTHCHECK --interval=5s --timeout=3s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8888/healthz')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888", "--log-level", "warning"]
