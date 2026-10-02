"""
python -m agente_cursos — Lanza una pasada del agente de cursos.

    python -m agente_cursos --simular             busca y muestra; no escribe
    python -m agente_cursos --simular --ramas 3 6
    python -m agente_cursos                       busca y propone en la BD

En Docker corre en SU PROPIO contenedor, no dentro de ml-service:

    docker compose --profile tareas run --rm agente-cursos

POR QUE NO DENTRO DE ml-service

Se intento, y fallo la primera pasada real: ml-service vive en una red sin
salida a internet (revo_interna, `internal: true`) y no resolvia ni
api.github.com. Esa red existe para que un servicio comprometido no pueda
sacar datos de alumnos, asi que abrirla no era la solucion. El agente tiene
su contenedor con salida y su rol, revo_agente, que solo alcanza sus dos
tablas (database/33_rol_agente_cursos.sql).

EN EL VPS, UNA VEZ AL DIA

No hace falta mas: los cursos no cambian de un dia para otro, y la fuente
sin clave da 10 busquedas por minuto. Una linea de cron basta:

    0 4 * * *  cd /opt/revo && docker compose --profile tareas run --rm agente-cursos

A las 4:00 no hay alumnos en el sistema. El codigo de salida es 1 si la
pasada fallo —incluido no poder llegar a la fuente—, para que cron lo avise.

POR QUE EXISTE --simular

Para ver que propondria el agente sin tocar la tabla de revision. Con el se
descubrio que Infraestructura y QA salian vacias; sin el, la unica forma de
verlo era escribir en la BD y consultarla despues.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from agente_cursos.agente import ejecutar, recorrer_huecos
from agente_cursos.fuentes.base import Fuente, FuenteNoDisponible
from agente_cursos.fuentes.github import GitHub
from agente_cursos.fuentes.mit_learn import MITLearn

RAMAS = range(1, 11)

NOMBRES_NIVEL = {1: "Fundamentos", 2: "Construccion", 3: "Experto"}


def analizar_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m agente_cursos",
        description="Busca cursos gratuitos en espanol y los propone para revision.",
    )
    parser.add_argument(
        "--simular", action="store_true",
        help="muestra lo que propondria, sin escribir en la base de datos",
    )
    parser.add_argument(
        "--ramas", type=int, nargs="+", choices=RAMAS, metavar="N",
        help="solo estas ramas (1-10); por defecto todas",
    )
    return parser.parse_args(argv)


def fuentes_por_defecto() -> list[Fuente]:
    """
    GitHub (espanol, los tres niveles) y el MIT (ingles, solo Experto).

    El MIT entra desde que el autor admitio ingles en el nivel Experto
    (2026-09-21): es material universitario abierto, justo lo que faltaba
    en ese escalon.
    """
    return [GitHub(), MITLearn()]


def simular(fuente: Fuente, ramas: list[int] | None = None) -> dict:
    """Busca, puntua e imprime. No toca la base de datos."""
    print(f"\n=== {fuente.nombre} ===")
    propuestas = recorrer_huecos(fuente, ramas)

    for (rama, nivel), lista in sorted(propuestas.items()):
        print(f"\nRama {rama} - {NOMBRES_NIVEL[nivel]}")
        if not lista:
            print("   (sin candidatos)")
        for candidato, nota in lista:
            print(f"   {nota.total:.3f}  [{candidato.idioma or '?'}]  {candidato.titulo[:80]}")
            print(f"          {candidato.url}")

    vacios = sum(1 for lista in propuestas.values() if not lista)
    print(f"\n{len(propuestas) - vacios} de {len(propuestas)} huecos con candidatos.")
    return propuestas


def abrir_sesion():
    """
    Conexion propia, como revo_agente, SIN contexto RLS.

    No se usa la sesion de ml-service. Antes se hacia, y arrastraba dos
    cosas que el agente no necesita: la aplicacion web entera (con su Redis
    y su configuracion) y el contexto RLS de servicio, que da lectura al
    dataset completo de los alumnos. Sus dos tablas no tienen RLS y no lee
    datos personales: sin contexto le basta, y es lo minimo.
    """
    # Import tardio: --simular no necesita base de datos y no deberia
    # depender de que este configurada.
    from revo_comun.basedatos.motor import crear_fabrica_sesiones, crear_motor

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit(
            "Falta DATABASE_URL. Lanzalo con "
            "`docker compose --profile tareas run --rm agente-cursos`, "
            "que conecta como revo_agente."
        )
    motor = crear_motor(
        url,
        application_name="revo-agente-cursos",
        pool_size=1,
        max_overflow=0,
        require_ssl=os.environ.get("DB_REQUIRE_SSL", "false").lower() == "true",
    )
    return crear_fabrica_sesiones(motor)()


def proponer(fuente: Fuente, ramas: list[int] | None = None) -> int:
    """Una pasada real: escribe en `curso_candidatos` para que alguien apruebe."""
    db = abrir_sesion()
    try:
        resultado = ejecutar(db, fuente, ramas)
    finally:
        db.close()

    print(f"Fuente     : {resultado.fuente}")
    print(f"Propuestos : {resultado.propuestos}")
    if resultado.error:
        print(f"ERROR      : {resultado.error}")
        return 1
    return 0


def main(argv: list[str] | None = None, fuentes: list[Fuente] | None = None) -> int:
    # En una consola de Windows la salida es cp1252, y un titulo con un
    # emoji o un simbolo raro tumbaba la ejecucion entera al imprimirlo.
    # Mejor un '?' en pantalla que perder la pasada.
    sys.stdout.reconfigure(errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    argumentos = analizar_argumentos(argv)

    # Cada fuente por separado: que una falle no impide que las demas hagan
    # su pasada, pero el codigo de salida lo refleja para que cron avise.
    codigo = 0
    for fuente in fuentes or fuentes_por_defecto():
        if argumentos.simular:
            try:
                simular(fuente, argumentos.ramas)
            except FuenteNoDisponible as exc:
                print(f"ERROR      : {exc}")
                codigo = 1
        else:
            codigo = max(codigo, proponer(fuente, argumentos.ramas))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
