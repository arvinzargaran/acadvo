# Pinned by digest, not just tag: `python:3.12-slim` is a moving target that
# silently changes content between builds, so the image CI audited is not
# necessarily the image that ships. Refresh deliberately (pull the tag, read the
# new digest) rather than drifting by accident.
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user. This process parses attacker-supplied PDFs and
# spreadsheets through pdfplumber/openpyxl — memory-unsafe territory where a
# parser bug is a plausible RCE — so it should not be root inside the container.
# The app never writes to its own source tree, so ownership stays with root and
# the runtime user gets read-only access to the code.
RUN useradd --system --create-home --uid 10001 app \
    && chown -R root:root /app \
    && chmod -R a-w /app

USER app

EXPOSE 8000

# Readiness, not liveness. `/health` answers 200 as soon as uvicorn binds a
# socket, so gating on it marks a container healthy while its database
# credentials are wrong — and Caddy's `depends_on: condition: service_healthy`
# then opens the door to traffic that can only 500. `/health/ready` runs a real
# query, so this gate means what the compose file says it means.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4).status == 200 else 1)"
