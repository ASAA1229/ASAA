# ASAA API image. Build context: apps/ap-api.  docker build -t asaa-api:local apps/ap-api
FROM python:3.12-slim AS runtime

# BAD_RELEASE=1 builds a deliberately broken image used only by deploy/rehearsal.sh to rehearse rollback.
ARG BAD_RELEASE=0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
RUN if [ "$BAD_RELEASE" = "1" ]; then echo "raise RuntimeError('simulated bad release')" >> src/asaa_ap/__init__.py; fi \
 && pip install .

RUN useradd --system --uid 10001 --no-create-home asaa
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "asaa_ap.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
