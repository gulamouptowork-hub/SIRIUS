# ── Stage 1: build dependencies ─────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install third-party dependencies first (cached until pyproject.toml changes).
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# Then install Sirius itself (cheap layer, changes with every code edit).
COPY README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps --prefix=/install .

# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 sirius

WORKDIR /app
COPY --from=builder /install /usr/local

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

RUN mkdir -p /app/data && chown -R sirius:sirius /app
USER sirius

VOLUME ["/app/data"]
EXPOSE 8000

# Local health probe (stdlib only — no curl in slim images).
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8).status==200 else 1)"

# API + Telegram bot + scheduler in one supervised process.
CMD ["python", "-m", "sirius.run"]
