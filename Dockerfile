FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies during build time (no runtime downloads)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and bundled fixtures
COPY . /app/

EXPOSE 8080

ENTRYPOINT ["python", "docker-entrypoint.py"]
