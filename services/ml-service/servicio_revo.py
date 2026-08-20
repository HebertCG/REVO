"""Instancia unica de ServicioREVO para el ml-service."""
from config import settings
from revo_comun.servicio import ServicioREVO

servicio = ServicioREVO(settings)
