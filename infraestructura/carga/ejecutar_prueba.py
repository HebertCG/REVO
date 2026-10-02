"""
ejecutar_prueba.py — Prueba de carga por ciclos, midiendo recursos reales.

Responde a una pregunta concreta: que VPS minimo necesita REVO. Para eso no
basta con latencias; hay que medir lo que el sistema CONSUME:

    CPU        segundos de CPU de cada contenedor, leidos del contador del
               kernel (cgroup cpu.stat). Es la cifra que se traslada a otra
               maquina: "X segundos de CPU por alumno" no depende de cuantos
               nucleos tenga esta.
    RAM        pico de memoria de cada contenedor, muestreado cada ~2 s con
               `docker stats`, y el pico absoluto del cgroup (memory.peak).
    DISCO      tamano de la base antes y despues, por tabla: cuantos bytes
               deja cada alumno en cada ciclo.

ESCENARIOS

    pico     K aulas de 45 alumnos haciendo el test A LA VEZ, alumnos nuevos
             (registro incluido). Es la hora punta: varios profesores diciendo
             "abran REVO" en la misma franja. K sube hasta ver degradacion.
    ciclos   los mismos alumnos vuelven ciclo tras ciclo: inicio de sesion,
             test, historial. Mide cuanto crece la base por alumno y ciclo, y
             si el historial se vuelve lento al acumularse.

Uso (con la pila de produccion levantada como proyecto aparte):
    python infraestructura/carga/ejecutar_prueba.py --proyecto revo-carga \\
        --pico 1,3,6,10 --ciclos 2,3,4 --aulas-ciclos 6
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CONTENEDORES = ["revo_postgres", "revo_redis", "revo_auth", "revo_survey",
                "revo_ml", "revo_pasarela"]
ALUMNOS_POR_AULA = 45
IMAGEN_AULA = "python:3.11-alpine"

#: Red propia para las aulas, con subred fija para poder dar a cada aula una
#: IP UNICA en toda la prueba.
#:
#: DEFECTO DE LA PRIMERA PASADA: las aulas usaban la red de la pasarela y
#: Docker reasignaba las IP de los contenedores ya terminados. La misma IP
#: acumulaba las altas de varias aulas de escenarios distintos y chocaba con
#: el limite de 80 altas cada 10 minutos: 19 alumnos "no pudieron entrar" por
#: un artefacto de la prueba, no del sistema. En la vida real cada salon sale
#: por su propio router.
RED_AULAS = "revo-carga_aulas"
SUBRED_AULAS = "10.77.0.0/16"


# ── Docker ───────────────────────────────────────────────────
def docker(*args: str, tolerar: bool = False) -> str:
    r = subprocess.run(["docker", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 and not tolerar:
        raise RuntimeError(f"docker {' '.join(args[:3])}: {r.stderr.strip()[:300]}")
    return r.stdout


def sql(consulta: str) -> str:
    return docker("exec", "revo_postgres", "sh", "-c",
                  f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -F "|" -c "{consulta}"').strip()


# ── Mediciones puntuales ─────────────────────────────────────
def cpu_usec(contenedor: str) -> int:
    """CPU consumida por el contenedor desde que arranco, en microsegundos."""
    texto = docker("exec", contenedor, "cat", "/sys/fs/cgroup/cpu.stat")
    return int(re.search(r"usage_usec (\d+)", texto).group(1))


def memoria_pico_cgroup(contenedor: str) -> int | None:
    texto = docker("exec", contenedor, "cat", "/sys/fs/cgroup/memory.peak", tolerar=True)
    return int(texto) if texto.strip().isdigit() else None


def foto_base() -> dict:
    """Tamano de la base y de sus tablas, y filas de las que crecen."""
    tablas = {}
    for fila in sql(
        "SELECT relname, pg_total_relation_size(c.oid) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r'"
    ).splitlines():
        nombre, tamano = fila.split("|")
        tablas[nombre] = int(tamano)
    filas = {}
    for tabla in ("users", "questionnaire_sessions", "answers", "predictions",
                  "prediction_feedbacks", "ml_training_data", "user_consents",
                  "model_training_logs"):
        filas[tabla] = int(sql(f"SELECT count(*) FROM {tabla}"))
    return {
        "base_bytes": int(sql("SELECT pg_database_size(current_database())")),
        "pgdata_kb": int(docker("exec", "revo_postgres", "sh", "-c",
                                "du -sk $PGDATA | cut -f1").strip()),
        "modelos_kb": int(docker("exec", "revo_ml", "sh", "-c",
                                 "du -sk /app/model/saved | cut -f1").strip()),
        "tablas": tablas,
        "filas": filas,
    }


def foto_cpu() -> dict[str, int]:
    return {c: cpu_usec(c) for c in CONTENEDORES}


# ── Muestreo continuo de RAM y CPU ───────────────────────────
UNIDADES = {"B": 1, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3}


def a_bytes(texto: str) -> int:
    m = re.match(r"([\d.]+)\s*([KMG]iB|B)", texto.strip())
    return int(float(m.group(1)) * UNIDADES[m.group(2)]) if m else 0


class Muestreo(threading.Thread):
    """`docker stats` en bucle: pico de RAM por contenedor y de CPU total."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.parar = threading.Event()
        self.ram_pico: dict[str, int] = {}
        self.cpu_pico: dict[str, float] = {}
        self.cpu_total_pico = 0.0
        self.ram_total_pico = 0
        self.muestras = 0

    def run(self) -> None:
        while not self.parar.is_set():
            salida = docker("stats", "--no-stream", "--format",
                            "{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}", *CONTENEDORES,
                            tolerar=True)
            total_cpu, total_ram = 0.0, 0
            for linea in salida.splitlines():
                nombre, memoria, cpu = linea.split("|")
                ram = a_bytes(memoria.split("/")[0])
                porcentaje = float(cpu.strip().rstrip("%") or 0)
                self.ram_pico[nombre] = max(self.ram_pico.get(nombre, 0), ram)
                self.cpu_pico[nombre] = max(self.cpu_pico.get(nombre, 0.0), porcentaje)
                total_cpu += porcentaje
                total_ram += ram
            self.cpu_total_pico = max(self.cpu_total_pico, total_cpu)
            self.ram_total_pico = max(self.ram_total_pico, total_ram)
            self.muestras += 1


# ── Aulas ────────────────────────────────────────────────────
def preparar_red_aulas() -> None:
    """Crea la red de aulas y conecta la pasarela con el alias `pasarela`."""
    if RED_AULAS not in docker("network", "ls", "--format", "{{.Name}}").split():
        docker("network", "create", "--subnet", SUBRED_AULAS, RED_AULAS)
    conectados = docker("network", "inspect", RED_AULAS, "--format",
                        "{{range .Containers}}{{.Name}} {{end}}")
    if "revo_pasarela" not in conectados:
        docker("network", "connect", "--alias", "pasarela", RED_AULAS, "revo_pasarela")


def ip_de_aula(aula: int) -> str:
    """Una IP fija por aula, que ninguna otra aula reutiliza."""
    return f"10.77.{aula // 200}.{aula % 200 + 10}"


def lanzar_aula(red: str, aula: int, ciclo: int, escala: float, llegada: float) -> dict:
    fuente = str(AQUI / "aula.py")
    salida = docker(
        "run", "--rm", "--network", RED_AULAS, "--ip", ip_de_aula(aula),
        "--mount", f"type=bind,source={fuente},target=/aula.py,readonly",
        "-e", "API=http://pasarela/api", "-e", f"AULA={aula}",
        "-e", f"ALUMNOS={ALUMNOS_POR_AULA}", "-e", f"CICLO={ciclo}",
        "-e", f"ESCALA_TIEMPO={escala}", "-e", f"LLEGADA_S={llegada}",
        IMAGEN_AULA, "python", "/aula.py",
    )
    return json.loads(salida.strip().splitlines()[-1])


def esperar_calma(segundos_max: int = 180) -> float:
    """
    Espera a que ml-service termine lo que dejo en segundo plano.

    El reentrenamiento corre DESPUES de responder al alumno. Si se midiera la
    CPU nada mas terminar las aulas, su coste quedaria fuera del escenario
    que lo provoco.
    """
    inicio = time.time()
    tranquilas = 0
    while time.time() - inicio < segundos_max:
        antes = cpu_usec("revo_ml")
        time.sleep(2)
        uso = (cpu_usec("revo_ml") - antes) / 2e6   # nucleos en esos 2 s
        tranquilas = tranquilas + 1 if uso < 0.05 else 0
        if tranquilas >= 3:
            break
    return time.time() - inicio


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(p / 100 * (len(ordenados) - 1))))]


def escenario(nombre: str, red: str, aulas: list[int], ciclo: int,
              escala: float, llegada: float) -> dict:
    print(f"\n=== {nombre}: {len(aulas)} aulas x {ALUMNOS_POR_AULA} alumnos, ciclo {ciclo} ===",
          flush=True)
    base_antes, cpu_antes = foto_base(), foto_cpu()
    muestreo = Muestreo()
    muestreo.start()

    inicio = time.time()
    with ThreadPoolExecutor(max_workers=len(aulas)) as pool:
        resultados = list(pool.map(
            lambda a: lanzar_aula(red, a, ciclo, escala, llegada), aulas))
    duracion_carga = time.time() - inicio

    calma = esperar_calma()
    muestreo.parar.set()
    muestreo.join(timeout=10)
    cpu_despues, base_despues = foto_cpu(), foto_base()

    latencias: dict[str, list[float]] = {}
    errores: dict[str, dict[str, int]] = {}
    fallos: dict[str, int] = {}
    completos = 0
    for r in resultados:
        completos += r["completos"]
        for motivo, n in r["fallos"].items():
            fallos[motivo] = fallos.get(motivo, 0) + n
        for etapa, valores in r["latencias"].items():
            latencias.setdefault(etapa, []).extend(valores)
        for etapa, por_estado in r["errores"].items():
            destino = errores.setdefault(etapa, {})
            for estado, n in por_estado.items():
                destino[estado] = destino.get(estado, 0) + n

    cpu_s = {c: (cpu_despues[c] - cpu_antes[c]) / 1e6 for c in CONTENEDORES}
    peticiones = sum(len(v) for v in latencias.values())
    todas = [x for v in latencias.values() for x in v]
    informe = {
        "nombre": nombre, "aulas": len(aulas), "alumnos": len(aulas) * ALUMNOS_POR_AULA,
        "ciclo": ciclo, "escala_tiempo": escala,
        "duracion_carga_s": round(duracion_carga, 1), "calma_s": round(calma, 1),
        "completos": completos, "fallos": fallos, "errores": errores,
        "peticiones": peticiones,
        "peticiones_por_s": round(peticiones / duracion_carga, 2),
        "latencia_global": {"p50": percentil(todas, 50), "p95": percentil(todas, 95),
                            "p99": percentil(todas, 99), "max": max(todas, default=0)},
        "latencia_por_etapa": {
            e: {"n": len(v), "p50": percentil(v, 50), "p95": percentil(v, 95),
                "p99": percentil(v, 99), "max": max(v)} for e, v in sorted(latencias.items())},
        "cpu_segundos": {c: round(s, 2) for c, s in cpu_s.items()},
        "cpu_segundos_total": round(sum(cpu_s.values()), 2),
        "cpu_segundos_por_alumno": round(sum(cpu_s.values()) / max(completos, 1), 3),
        "nucleos_medios": round(sum(cpu_s.values()) / duracion_carga, 2),
        "nucleos_pico": round(muestreo.cpu_total_pico / 100, 2),
        "ram_pico_bytes": muestreo.ram_pico,
        "ram_total_pico_bytes": muestreo.ram_total_pico,
        "memoria_peak_cgroup": {c: memoria_pico_cgroup(c) for c in CONTENEDORES},
        "muestras_stats": muestreo.muestras,
        "base_antes": base_antes, "base_despues": base_despues,
        "base_crecimiento_bytes": base_despues["base_bytes"] - base_antes["base_bytes"],
        "reentrenamientos": (base_despues["filas"]["model_training_logs"]
                             - base_antes["filas"]["model_training_logs"]),
    }
    mib = lambda b: f"{b / 1024 ** 2:.0f} MiB"   # noqa: E731
    pred = informe["latencia_por_etapa"].get("prediccion", {})
    print(f"  completos {completos}/{informe['alumnos']}  fallos {fallos or '-'}  "
          f"errores HTTP {sum(sum(d.values()) for d in errores.values())}")
    print(f"  {peticiones} peticiones en {duracion_carga:.0f} s ({informe['peticiones_por_s']}/s) | "
          f"latencia p50 {informe['latencia_global']['p50']:.3f} s, p95 {informe['latencia_global']['p95']:.3f} s | "
          f"prediccion p95 {pred.get('p95', 0):.3f} s")
    print(f"  CPU {informe['cpu_segundos_total']} s ({informe['cpu_segundos_por_alumno']} s/alumno) | "
          f"nucleos medios {informe['nucleos_medios']}, pico {informe['nucleos_pico']} | "
          f"RAM total pico {mib(muestreo.ram_total_pico)} | reentrenamientos {informe['reentrenamientos']}")
    print(f"  base +{informe['base_crecimiento_bytes'] / 1024:.0f} KiB "
          f"({informe['base_crecimiento_bytes'] / max(completos, 1) / 1024:.1f} KiB por alumno-ciclo)",
          flush=True)
    return informe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proyecto", default="revo-carga")
    parser.add_argument("--pico", default="1,3,6,10", help="aulas simultaneas por escenario")
    parser.add_argument("--ciclos", default="2,3,4", help="ciclos de vuelta")
    parser.add_argument("--aulas-ciclos", type=int, default=6)
    parser.add_argument("--escala", type=float, default=0.2)
    parser.add_argument("--llegada", type=float, default=60)
    parser.add_argument("--primera-aula", type=int, default=1,
                        help="numero de la primera aula; alumnos nuevos en cada prueba")
    parser.add_argument("--etiqueta", default="", help="se anade al nombre del informe")
    args = parser.parse_args()
    red = f"{args.proyecto}_revo_publica"
    preparar_red_aulas()

    informe = {
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
        "maquina": docker("info", "--format", "{{.NCPU}} CPU, {{.MemTotal}} B RAM").strip(),
        "reposo": {"base": foto_base(),
                   "ram": {c: a_bytes(docker("stats", "--no-stream", "--format",
                                             "{{.MemUsage}}", c).split("/")[0])
                           for c in CONTENEDORES}},
        "escenarios": [],
    }

    siguiente_aula = args.primera_aula
    aulas_para_ciclos: list[int] = []
    for k in [int(x) for x in args.pico.split(",") if x]:
        aulas = list(range(siguiente_aula, siguiente_aula + k))
        siguiente_aula += k
        informe["escenarios"].append(
            escenario(f"pico-{k}", red, aulas, 1, args.escala, args.llegada))
        if k == args.aulas_ciclos:
            aulas_para_ciclos = aulas

    for ciclo in [int(x) for x in args.ciclos.split(",") if x]:
        informe["escenarios"].append(
            escenario(f"ciclo-{ciclo}", red, aulas_para_ciclos, ciclo, args.escala, args.llegada))

    sufijo = f"_{args.etiqueta}" if args.etiqueta else ""
    destino = AQUI / "resultados" / f"carga_{time.strftime('%Y%m%d_%H%M')}{sufijo}.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(informe, indent=1), encoding="utf-8")
    print(f"\nInforme completo: {destino}")


if __name__ == "__main__":
    main()
