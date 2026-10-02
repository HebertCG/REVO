"""
github.py — Cursos en espanol, gratuitos y sin clave de API.

POR QUE ESTA FUENTE

Se necesitaba material EN ESPANOL, GRATUITO y accesible SIN REGISTRO. Se
probaron las alternativas y se descartaron con datos, no por intuicion:

  UNED Abierta (iedra.uned.es)  API abierta y 105 cursos, pero el catalogo
                                es alfabetizacion digital, bilinguismo y
                                ciencias sociales. Ni un curso de las diez
                                ramas. Ademas ignora `search_term`.
  MexicoX, Miriadax, learn.lat,
  openedx.upm.es, cursos.uc3m   no exponen el catalogo publico de Open edX
  edx.org/api/v1/catalog        404
  YouTube Data API v3           funciona, pero exige clave y cuenta de
                                Google Cloud. Descartada por peticion
                                expresa: la fuente tiene que ser libre sin
                                tramite.

GitHub cumple las tres condiciones a la vez:

  * API publica sin clave (10 busquedas/minuto sin autenticar)
  * Hay cientos de cursos en espanol: "curso ciberseguridad" devuelve 386
    repositorios
  * Un repositorio es gratuito por definicion

Y trae algo que las plataformas de cursos no dan: SENALES DE CALIDAD
COMPROBABLES. Estrellas, si esta archivado, cuando se toco por ultima vez y
con que licencia. Eso permite distinguir un curso vivo de uno abandonado, y
en tecnologia esa diferencia es lo que separa lo util de lo obsoleto.

QUE SE FILTRA Y POR QUE

  archivados   su autor declaro que ya no lo mantiene
  forks        son copias; el original es el que tiene la comunidad
  sin estrellas  nadie lo ha revisado nunca
  muy antiguos   un curso de Angular de 2018 ensena una version que ya no
                 existe
  no formativos  un modulo de Odoo o un "toolkit" de pentesting es software,
                 no un curso, aunque trate del tema de la rama
  de pago        el codigo de un curso de Platzi o Udemy es gratis, pero las
                 clases no: se marca `gratuito=False` y el agente lo descarta

LIMITE SIN CLAVE

10 busquedas por minuto. Una pasada completa son 10 ramas x 3 consultas =
30 busquedas, o sea ~3 minutos con la espera puesta. Para un trabajo de
fondo que corre una vez al dia es de sobra, y evita tener que gestionar
credenciales.
"""
from __future__ import annotations

import logging
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from agente_cursos.fuentes.base import (
    USER_AGENT,
    CursoCandidato,
    Fuente,
    FuenteNoDisponible,
    RespetaRobots,
)
from agente_cursos.idioma import detectar

logger = logging.getLogger("revo.agente.github")

BUSQUEDA_URL = "https://api.github.com/search/repositories"
TIMEOUT_S = 20

#: Sin clave, GitHub da 10 busquedas por minuto. `RespetaRobots` ya espacia
#: las peticiones; esto documenta el techo para que nadie suba el ritmo sin
#: saber que existe.
LIMITE_POR_MINUTO = 10

#: Segundos entre busquedas: 60 / 10 + margen. Sin esto la API devuelve 403
#: a mitad de la pasada y ramas enteras se quedan sin candidatos, que es
#: exactamente lo que paso en la primera ejecucion real.
ESPERA_S = 6.5

#: Espera maxima para que GitHub reabra el cupo antes de reintentar. El
#: cupo sin clave es por minuto, asi que en condiciones normales reabre en
#: menos de esto. Si pide mas, algo raro pasa y es mejor fallar la consulta
#: que dejar el proceso colgado.
ESPERA_MAXIMA_LIMITE_S = 65

#: Minimo de estrellas. Cero significa que nadie lo ha mirado nunca, y en un
#: roadmap que se le ofrece a un alumno eso no basta.
ESTRELLAS_MINIMAS = 15

#: Anos desde el ultimo cambio a partir de los cuales se descarta. En
#: tecnologia, un curso sin tocar en cuatro anos ensena versiones que ya no
#: existen.
ANTIGUEDAD_MAXIMA_ANOS = 4

#: Estimacion de horas segun el tamano del repositorio en KB. Es una
#: aproximacion burda y esta declarada como tal: sirve para distinguir un
#: repositorio de apuntes sueltos de un curso completo, no para prometer una
#: duracion exacta.
KB_POR_HORA = 900

#: Senales de que un repositorio es MATERIAL FORMATIVO y no software.
#:
#: DEFECTO QUE ESTO CORRIGE: buscando "odoo" salieron 17 candidatos y los 17
#: eran modulos ("Odoo Warehouse Management Addons"); buscando
#: "ciberseguridad" se colo un "Pentesting toolkit". Mientras las consultas
#: llevaban "curso" esto se cumplia de rebote. Al quitarlo para ganar
#: cobertura dejo de cumplirse, y la relevancia no lo ve: un modulo de Odoo
#: trata de ERP tanto como un curso de Odoo.
#:
#: Se buscan como PALABRA COMPLETA, con plural opcional: "curso" y "cursos"
#: cuentan, "Cursor" no. Esa confusion trajo un repositorio en chino.
MARCADORES_FORMATIVOS = (
    "curso", "course", "tutorial", "aprende", "aprender", "learn",
    "apuntes", "clase", "taller", "workshop", "ejercicio", "exercise",
    "leccion", "lesson", "guia", "formacion", "introduccion", "fundamentos",
    "bootcamp", "roadmap", "certificacion", "material", "desde cero",
    "educacion", "education", "asignatura",
)

_FORMATIVO = re.compile(
    r"\b(?:" + "|".join(re.escape(m) for m in MARCADORES_FORMATIVOS) + r")(?:s|es)?\b"
)

#: Plataformas cuyos cursos son de pago. Un repositorio que las menciona
#: suele ser el CODIGO FINAL de un curso suyo: el repositorio es gratis,
#: pero las clases no. Caso real: "Contenido del Curso de React Avanzado
#: para Platzi". Para el alumno eso no es un curso gratuito, es un anuncio.
#:
#: Solo las que son de pago sin excepcion. Coursera o edX no entran: se
#: pueden cursar gratis en modo oyente.
#:
#: Se mira tambien el DUENO del repositorio: `platzi/curso-kubernetes` se
#: colo como gratuito porque su descripcion no nombra la plataforma. Cod3r,
#: academia brasilena de pago, se anadio por el mismo caso.
PLATAFORMAS_DE_PAGO = (
    "platzi", "udemy", "domestika", "crehana", "alura", "edteam",
    "pluralsight", "linkedin learning", "cod3r",
)


class GitHub(Fuente):
    """Cursos publicados como repositorios, en espanol y gratuitos."""

    @property
    def nombre(self) -> str:
        return "github"

    @property
    def base_legal(self) -> str:
        return (
            "API de busqueda publica de GitHub (api.github.com/search), sin "
            "clave ni registro, 10 peticiones/minuto. Se consultan metadatos "
            "publicos (nombre, descripcion, estrellas, licencia) y se enlaza "
            "al repositorio: no se descarga ni se redistribuye contenido. "
            "Cada repositorio conserva su propia licencia, que se guarda."
        )

    def __init__(
        self,
        sesion: requests.Session | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        })
        # Inyectable para que las pruebas del reintento no esperen de verdad.
        self.dormir = dormir
        self.robots = RespetaRobots(espera_s=ESPERA_S, dormir=dormir)

    def buscar(self, consulta: str, limite: int = 20) -> list[CursoCandidato]:
        datos = self._pedir(consulta, limite)

        candidatos = []
        for repositorio in datos.get("items", []):
            candidato = self._convertir(repositorio)
            if candidato is not None:
                candidatos.append(candidato)

        logger.debug(
            "'%s': %s de %s repositorios pasaron el filtro",
            consulta, len(candidatos), len(datos.get("items", [])),
        )
        return candidatos

    def _pedir(self, consulta: str, limite: int) -> dict:
        """
        Una busqueda, con UN reintento si el cupo por minuto esta agotado.

        DEFECTO QUE ESTO CORRIGE: al relanzar una pasada justo despues de
        otra, las dos compartieron la ventana de 10 busquedas por minuto y
        "curso docker" devolvio 403: la rama 3 perdio una consulta. GitHub
        dice en las cabeceras cuando reabre el cupo, asi que se espera ese
        tiempo y se reintenta. Una sola vez: si vuelve a fallar, no es el
        cupo de este minuto y no tiene sentido insistir.
        """
        for intento in (1, 2):
            self.robots.esperar_turno(BUSQUEDA_URL)
            try:
                respuesta = self.sesion.get(BUSQUEDA_URL, timeout=TIMEOUT_S, params={
                    # `in:name,description` evita que coincida con cualquier
                    # mencion perdida dentro del README, que mete mucho ruido.
                    "q": f"{consulta} in:name,description",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": min(limite, 50),
                })
            except requests.RequestException as exc:
                raise FuenteNoDisponible(f"GitHub no respondio a '{consulta}': {exc}") from exc

            if respuesta.status_code != 403:
                break
            espera = self._espera_por_limite(respuesta)
            if intento == 2 or espera is None or espera > ESPERA_MAXIMA_LIMITE_S:
                raise FuenteNoDisponible(
                    f"GitHub devolvio 403 en '{consulta}': probablemente el "
                    f"limite de {LIMITE_POR_MINUTO} busquedas/minuto"
                )
            logger.info("Cupo de GitHub agotado: se esperan %.0f s y se reintenta", espera)
            self.dormir(espera)

        try:
            respuesta.raise_for_status()
            return respuesta.json()
        except (requests.RequestException, ValueError) as exc:
            raise FuenteNoDisponible(f"GitHub no respondio a '{consulta}': {exc}") from exc

    @staticmethod
    def _espera_por_limite(respuesta: requests.Response) -> float | None:
        """Segundos hasta que GitHub reabra el cupo, o None si el 403 es por otra cosa."""
        cabeceras = respuesta.headers
        try:
            if cabeceras.get("retry-after"):
                return float(cabeceras["retry-after"])
            if cabeceras.get("x-ratelimit-remaining") == "0":
                reinicio = float(cabeceras.get("x-ratelimit-reset", "0"))
                # Un segundo de margen: el reloj de GitHub y el nuestro no
                # coinciden al milisegundo.
                return max(reinicio - time.time(), 0.0) + 1.0
        except ValueError:
            return None
        return None

    def _convertir(self, repo: dict[str, Any]) -> CursoCandidato | None:
        """
        Pasa un repositorio al formato del agente, o lo descarta.

        Devuelve None en los cinco casos que no sirven para un roadmap. Se
        descarta AQUI y no en la puntuacion porque no son cuestion de grado:
        un repositorio archivado no es un curso peor, es un curso muerto.
        """
        if repo.get("archived"):
            return None
        if repo.get("fork"):
            # Una copia. El original es el que tiene la comunidad detras.
            return None
        if (repo.get("stargazers_count") or 0) < ESTRELLAS_MINIMAS:
            return None
        if self._anos_desde(repo.get("pushed_at")) > ANTIGUEDAD_MAXIMA_ANOS:
            return None
        if not self._es_formativo(repo):
            # Software, no un curso. Tampoco es cuestion de grado.
            return None

        titulo = self._titulo(repo)
        url = repo.get("html_url")
        if not titulo or not url:
            return None

        try:
            return CursoCandidato(
                titulo=titulo,
                url=url,
                descripcion=(repo.get("description") or "").strip()[:1000] or None,
                idioma=self._idioma(titulo, repo.get("description")),
                duracion_horas=self._horas(repo.get("size")),
                # Un repositorio publico es gratuito, salvo que sea el
                # codigo de un curso que se vende en otra parte.
                gratuito=not self._de_plataforma_de_pago(titulo, repo),
                certificado=False,
                vistas=repo.get("stargazers_count"),
                id_externo=repo.get("full_name"),
                temas=self._temas(repo),
            )
        except ValueError as exc:
            logger.debug("Repositorio descartado (%s): %s", exc, titulo[:50])
            return None

    @staticmethod
    def _titulo(repo: dict) -> str:
        """
        Titulo legible.

        El nombre del repositorio suele ser 'curso-python-2024', que no se
        lee bien en una tarjeta. Si hay descripcion corta se usa esa, que es
        lo que el autor escribio para humanos.
        """
        descripcion = (repo.get("description") or "").strip()
        if 15 <= len(descripcion) <= 120:
            return descripcion

        nombre = (repo.get("name") or "").replace("-", " ").replace("_", " ")
        return nombre.strip().capitalize()

    @staticmethod
    def _idioma(titulo: str, descripcion: str | None) -> str | None:
        """
        En que lengua esta el repositorio. La logica vive en `idioma.py`.

        Antes el adaptador ponia `idioma="es"` fijo, razonando que si se
        busca en espanol lo que vuelve esta en espanol. Falso: "curso" se
        escribe igual en portugues y vuelve mucho material brasileno.
        """
        return detectar(titulo, descripcion)

    @staticmethod
    def _es_formativo(repo: dict) -> bool:
        """¿Dice el repositorio, en algun sitio, que es para aprender?"""
        texto = " ".join([
            repo.get("name") or "", repo.get("description") or "",
            " ".join(repo.get("topics") or []),
        ]).replace("-", " ").replace("_", " ").lower()
        sin_tildes = "".join(
            c for c in unicodedata.normalize("NFKD", texto)
            if not unicodedata.combining(c)
        )
        return bool(_FORMATIVO.search(sin_tildes))

    @staticmethod
    def _de_plataforma_de_pago(titulo: str, repo: dict) -> bool:
        """¿Es el material de un curso que se vende en otra plataforma?"""
        texto = " ".join([
            titulo, repo.get("full_name") or "", repo.get("description") or "",
            " ".join(repo.get("topics") or []),
        ]).lower()
        return any(plataforma in texto for plataforma in PLATAFORMAS_DE_PAGO)

    @staticmethod
    def _temas(repo: dict) -> tuple[str, ...]:
        """Etiquetas y lenguaje, que alimentan el calculo de relevancia."""
        temas = list(repo.get("topics") or [])
        if repo.get("language"):
            temas.append(repo["language"])
        return tuple(temas[:12])

    @staticmethod
    def _anos_desde(marca_iso: str | None) -> float:
        """Anos desde una fecha ISO. Sin fecha devuelve infinito: se descarta."""
        if not marca_iso:
            return float("inf")
        try:
            fecha = datetime.fromisoformat(marca_iso.replace("Z", "+00:00"))
        except ValueError:
            return float("inf")
        return (datetime.now(timezone.utc) - fecha).days / 365.25

    @staticmethod
    def _horas(tamano_kb: int | None) -> float | None:
        """
        Estimacion MUY burda de duracion a partir del tamano.

        Se declara burda a proposito. Un repositorio grande puede serlo por
        llevar videos dentro, y uno pequeno puede ser un temario denso. Sirve
        para distinguir apuntes sueltos de un curso completo; no para
        prometerle horas a nadie.
        """
        if not tamano_kb or tamano_kb <= 0:
            return None
        horas = tamano_kb / KB_POR_HORA
        # Se acota: por debajo de 2 h no es un curso y por encima de 120 el
        # tamano casi seguro viene de ficheros binarios, no de contenido.
        return round(min(max(horas, 2.0), 120.0), 1)

    @staticmethod
    def licencia_de(repo: dict) -> str | None:
        """Licencia declarada, si la tiene."""
        return (repo.get("license") or {}).get("spdx_id")
