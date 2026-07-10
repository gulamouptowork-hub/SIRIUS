FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

VOLUME ["/app/data"]
EXPOSE 8000

# Default: REST API. The bot service overrides the command (see docker-compose.yml).
CMD ["uvicorn", "sirius.main:app", "--host", "0.0.0.0", "--port", "8000"]
