"""
mit_learn.py — Cursos del catalogo abierto del MIT.

POR QUE ESTA ES LA PRIMERA FUENTE

Cumple las tres condiciones que el contrato de `base.py` exige, y las
cumple de forma comprobable:

  * API oficial en JSON, sin clave: api.learn.mit.edu/api/v1/
  * robots.txt de learn.mit.edu permite `/` al User-Agent generico
    (solo prohibe /dashboard/, /cart/ y similares)
  * El material es abierto por diseno: MIT OpenCourseWare existe
    precisamente para que se use

O sea: no hay que raspar nada ni pedir permiso a nadie. Es el tipo de fuente
que el proyecto debe preferir, por el mismo motivo por el que la tabla
`jobs` se cambio por la API de Remotive.

LIMITACION QUE HAY QUE DECIR
--------------------------------------------------------------------
El catalogo del MIT esta EN INGLES y es de nivel universitario
estadounidense. Para un alumno de tercer ciclo en Piura, un curso de MIT
xPRO puede quedarle grande o ser inaccesible por idioma.

Por eso el agente puntua el idioma y el coste (ver puntuacion.py), y por eso
esta fuente NO puede ser la unica: hace falta al menos una en espanol. Se
implementa primero porque es la que se puede verificar hoy sin gestionar
claves de API, no porque sea la mas adecuada para el alumno objetivo.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import requests

from agente_cursos.fuentes.base import (
    USER_AGENT,
    CursoCandidato,
    Fuente,
    FuenteNoDisponible,
    RespetaRobots,
)

logger = logging.getLogger("revo.agente.mit")

BASE_URL = "https://api.learn.mit.edu/api/v1/learning_resources_search/"

#: Un timeout explicito y corto. El agente corre en segundo plano, pero una
#: peticion colgada bloquearia la ejecucion entera sin decir por que.
TIMEOUT_S = 20

#: Tope por consulta. Mas resultados no mejoran el roadmap: el agente solo
#: promueve los mejores de cada hueco, y pedir de mas carga al servidor de
#: quien nos da los datos gratis.
LIMITE_POR_DEFECTO = 20

_ETIQUETAS_HTML = re.compile(r"<[^>]+>")


class MITLearn(Fuente):
    """Catalogo abierto del MIT (OpenCourseWare, xPRO, MITx)."""

    #: Todo en ingles, y de nivel universitario: por eso solo alimenta el
    #: nivel Experto (ver agente.IDIOMAS_ADMITIDOS).
    idioma_catalogo = "en"

    @property
    def nombre(self) -> str:
        return "mit_learn"

    @property
    def base_legal(self) -> str:
        return (
            "API publica oficial (api.learn.mit.edu/api/v1) sin clave de "
            "acceso. robots.txt de learn.mit.edu permite '/' al User-Agent "
            "generico. Material publicado por el MIT para uso abierto; el "
            "campo license_cc indica la licencia de cada recurso."
        )

    def __init__(self, sesion: requests.Session | None = None) -> None:
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.robots = RespetaRobots()

    def buscar(self, consulta: str, limite: int = LIMITE_POR_DEFECTO) -> list[CursoCandidato]:
        if not self.robots.permitido(BASE_URL):
            # Incluye no poder leer robots.txt, que se trata como prohibido.
            # Sin red, eso es lo primero que falla.
            raise FuenteNoDisponible(
                f"robots.txt no permite {BASE_URL}, o no se pudo leer"
            )

        self.robots.esperar_turno(BASE_URL)
        try:
            respuesta = self.sesion.get(
                BASE_URL,
                params={"q": consulta, "limit": limite, "resource_type": "course"},
                timeout=TIMEOUT_S,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
        except (requests.RequestException, ValueError) as exc:
            # Antes se devolvia lista vacia con un comentario que decia que el
            # fallo quedaba en la tabla de ejecuciones. No quedaba: la fila de
            # la primera pasada real dice 0 consultados y ningun error.
            raise FuenteNoDisponible(f"MIT Learn no respondio a '{consulta}': {exc}") from exc

        candidatos = []
        for fila in datos.get("results", []):
            candidato = self._convertir(fila)
            if candidato is not None:
                candidatos.append(candidato)
        return candidatos

    def _convertir(self, fila: dict[str, Any]) -> CursoCandidato | None:
        """
        Pasa un registro de la API al formato del agente.

        Devuelve None en vez de lanzar cuando la fila no sirve: la API
        evoluciona y un campo que cambia de nombre no debe tumbar la
        ejecucion entera por un solo registro.
        """
        url = fila.get("url") or fila.get("learn_url")
        titulo = (fila.get("title") or "").strip()
        if not url or not titulo:
            return None

        try:
            return CursoCandidato(
                titulo=titulo,
                url=url,
                descripcion=self._limpiar(fila.get("description")),
                idioma=self._idioma(fila),
                duracion_horas=self._horas(fila),
                gratuito=fila.get("free"),
                certificado=fila.get("certification"),
                vistas=fila.get("views"),
                id_externo=str(fila.get("readable_id") or fila.get("id") or ""),
                temas=tuple(
                    t["name"] for t in (fila.get("topics") or []) if t.get("name")
                ),
            )
        except ValueError as exc:
            logger.debug("Fila descartada (%s): %s", exc, titulo[:60])
            return None

    @staticmethod
    def _limpiar(texto: str | None) -> str | None:
        """
        Quita el HTML de la descripcion.

        La API lo devuelve con etiquetas. Guardarlo tal cual significaria
        que el frontend tendria que pintarlo como HTML, y ahi es donde
        aparecen los agujeros de XSS. Texto plano y se acabo.
        """
        if not texto:
            return None
        limpio = _ETIQUETAS_HTML.sub(" ", texto)
        return " ".join(limpio.split())[:1000] or None

    @staticmethod
    def _idioma(fila: dict) -> str | None:
        idiomas = fila.get("languages")
        if isinstance(idiomas, list) and idiomas:
            return str(idiomas[0])[:8]
        # El catalogo del MIT es mayoritariamente ingles y el campo suele
        # venir nulo. Suponerlo es mas util que dejarlo vacio, porque el
        # idioma pesa en la puntuacion.
        return "en"

    @staticmethod
    def _horas(fila: dict) -> float | None:
        """Estimacion de horas a partir de semanas x horas semanales."""
        semanas = fila.get("max_weeks") or fila.get("min_weeks")
        por_semana = fila.get("max_weekly_hours") or fila.get("min_weekly_hours")
        try:
            if semanas and por_semana:
                return round(float(semanas) * float(por_semana), 1)
        except (TypeError, ValueError):
            pass
        return None
