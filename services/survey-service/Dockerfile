# ============================================================
# REVO — survey-service
# ============================================================
# El contexto de build es ./services (no ./services/survey-service), para poder
# copiar tambien ./comun, que es la libreria compartida.
#
#   docker build -f services/survey-service/Dockerfile services/
#
# Dos etapas: la de construccion trae el compilador y las cabeceras de
# PostgreSQL; la final no. Un compilador dentro de un contenedor en
# produccion es una herramienta lista para quien consiga ejecutar algo ahi.
# ============================================================

# ── Etapa 1: dependencias ────────────────────────────────────
FROM python:3.11-slim AS construccion

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /construccion

COPY survey-service/requirements.txt ./requirements.txt
RUN pip install --prefix=/instalado -r requirements.txt

COPY comun/ ./comun/
RUN pip install --prefix=/instalado ./comun


# ── Etapa 2: imagen final ────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# libpq5 es la biblioteca en tiempo de ejecucion; libpq-dev y gcc se quedan
# en la etapa anterior.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios. Por defecto los contenedores corren como root, y
# entonces una ejecucion remota de codigo empieza siendo root dentro del
# contenedor en vez de un usuario sin permisos.
RUN useradd --create-home --uid 10001 revo

COPY --from=construccion /instalado /usr/local

WORKDIR /app
COPY --chown=revo:revo survey-service/ /app/

USER revo

EXPOSE 8002

# El comando real lo pone docker-compose (con --no-server-header y
# --proxy-headers). Este es el arranque por defecto si se corre suelto.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--no-server-header"]
