FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --index-url https://pypi.apple.com/simple --no-cache-dir -r requirements.txt

COPY . .

# Pre-collect static (SPA bundle must be built first — see docker-compose.yml)
RUN python manage.py collectstatic --no-input --clear 2>/dev/null || true

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
