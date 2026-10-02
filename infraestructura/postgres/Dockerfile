# ============================================================
# PostgreSQL 16 (Alpine) + pgvector
# ============================================================
# pgvector anade a PostgreSQL un tipo de columna, `vector`, y los indices
# para buscar por parecido (HNSW, IVFFlat). La base sigue siendo relacional:
# RLS, roles por servicio y claves ajenas funcionan igual.
#
# POR QUE UNA IMAGEN PROPIA Y NO pgvector/pgvector:pg16
#
# La imagen oficial de pgvector es Debian (glibc) y la que ya usaba REVO es
# Alpine (musl). Cambiar de libc sobre un volumen con datos puede cambiar como
# se ordena el texto (la collation), y un indice construido con un orden y
# leido con otro devuelve resultados incorrectos SIN dar error. Compilar
# pgvector sobre la misma imagen de siempre evita ese riesgo por completo.
#
# LAS DOS BANDERAS DEL make
#
#   with_llvm=no  la imagen Alpine de Postgres se compilo con JIT, y sin esto
#                 el make exige clang/llvm de la version exacta. pgvector no
#                 necesita JIT.
#   OPTFLAGS=""   por defecto pgvector compila con -march=native: el binario
#                 quedaria atado a la CPU de la maquina que construyo la
#                 imagen y podria fallar en el VPS.
# ============================================================
FROM postgres:16-alpine AS construccion

# Version fijada: una imagen que se reconstruye con "la ultima" puede cambiar
# de comportamiento sin que nadie haya tocado el proyecto.
ARG PGVECTOR_VERSION=v0.8.6

RUN apk add --no-cache git build-base

RUN git clone --branch "${PGVECTOR_VERSION}" --depth 1 \
        https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make with_llvm=no OPTFLAGS="" \
    && make install with_llvm=no


# La imagen final no contiene git, compiladores ni el codigo fuente.
FROM postgres:16-alpine

COPY --from=construccion /usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/vector.so
COPY --from=construccion /usr/local/share/postgresql/extension/vector* /usr/local/share/postgresql/extension/
