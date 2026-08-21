"""
servicio_revo.py — Instancia unica de ServicioREVO para el auth-service.

Vive en su propio modulo para que los routers puedan importarla sin crear un
ciclo con main.py.
"""
from config import settings
from politicas import POLITICAS
from revo_comun.servicio import ServicioREVO

servicio = ServicioREVO(settings, politicas=POLITICAS)
