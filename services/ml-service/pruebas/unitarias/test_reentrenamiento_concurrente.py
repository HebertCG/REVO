"""
Un solo reentrenamiento a la vez, entre workers y entre procesos.

DEFECTO REAL, prueba de carga del 2026-09-21: con 3 aulas (135 alumnos) a la
vez hubo 12 reentrenamientos en un solo escenario. Cada prediccion programa
check_and_retrain en segundo plano; en cuanto hay 50 nuevas, TODAS las
siguientes ven el umbral superado y arrancan su propio entrenamiento hasta
que el primero termina y lo registra. Resultado medido: la CPU por alumno
paso de 0,8 s a 4,2 s, la maquina llego a 16 nucleos al 100 % y la
prediccion tardo 8,9 s en el percentil 95.
"""
import threading

import pytest

from routers import predict as ruta


class Conexion:
    """Conexion falsa: responde al cerrojo consultivo como se le diga."""

    def __init__(self, libre: bool):
        self.libre = libre
        self.sentencias = []

    def execute(self, sentencia, parametros=None):
        texto = str(sentencia)
        self.sentencias.append(texto)

        class R:
            def __init__(s, v):
                s.v = v

            def scalar(s):
                return s.v
        return R(self.libre if "pg_try_advisory_lock" in texto else True)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def entrenamientos(monkeypatch):
    llamadas = []
    monkeypatch.setattr(ruta, "_reentrenar_si_toca", lambda: llamadas.append(1))
    return llamadas


def usar_conexion(monkeypatch, conexion):
    class Motor:
        def connect(self):
            return conexion
    monkeypatch.setattr(ruta.servicio, "motor", Motor())


def test_con_el_cerrojo_libre_entrena_y_lo_suelta(monkeypatch, entrenamientos):
    conexion = Conexion(libre=True)
    usar_conexion(monkeypatch, conexion)

    ruta.check_and_retrain()

    assert entrenamientos == [1]
    assert any("pg_advisory_unlock" in s for s in conexion.sentencias)


def test_si_otro_worker_tiene_el_cerrojo_no_entrena(monkeypatch, entrenamientos):
    usar_conexion(monkeypatch, Conexion(libre=False))

    ruta.check_and_retrain()

    assert entrenamientos == []


def test_dentro_del_mismo_proceso_no_se_solapan(monkeypatch, entrenamientos):
    conexion = Conexion(libre=True)
    usar_conexion(monkeypatch, conexion)

    with ruta._reentrenando:              # otro hilo de este proceso entrenando
        ruta.check_and_retrain()

    assert entrenamientos == []
    assert conexion.sentencias == []      # ni siquiera pregunto a la base


def test_si_el_entrenamiento_falla_el_cerrojo_se_suelta(monkeypatch):
    conexion = Conexion(libre=True)
    usar_conexion(monkeypatch, conexion)

    def falla():
        raise RuntimeError("fallo a mitad")
    monkeypatch.setattr(ruta, "_reentrenar_si_toca", falla)

    ruta.check_and_retrain()              # no propaga: corre en segundo plano

    assert any("pg_advisory_unlock" in s for s in conexion.sentencias)
    assert ruta._reentrenando.acquire(blocking=False)   # el de proceso tambien
    ruta._reentrenando.release()
