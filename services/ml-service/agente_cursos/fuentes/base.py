"""
base.py — Contrato que toda fuente de cursos tiene que cumplir.

POR QUE EXISTE ESTE CONTRATO

El proyecto ya aprendio esta leccion una vez: la tabla `jobs` se retiro
porque Remotive ofrece API oficial y raspar HTML era peor en todo —fragil
ante cualquier rediseno, contra los terminos de servicio, y lento.

Para que esa leccion no se pierda, aqui no se puede anadir una fuente sin
declarar TRES cosas:

    nombre        como se identifica en la base de datos
    base_legal    por que se puede usar: licencia, API oficial, robots.txt
    buscar()      como se le piden cursos

`base_legal` no es documentacion decorativa: viaja a la columna
`curso_candidatos.base_legal`, que es NOT NULL. Una fuente que no pueda
declararlo no llega a producir un candidato — la base de datos lo impide.

SOBRE EL RASPADO DE HTML

No esta prohibido aqui, pero es la ultima opcion y tiene que declararse como
tal. `RespetaRobots` da el minimo exigible: leer robots.txt, identificarse
con un User-Agent honesto y esperar entre peticiones.

Una fuente que necesite saltarse robots.txt no es una fuente: es un problema
legal esperando a que alguien pregunte en una sustentacion.
"""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger("revo.agente.fuentes")

#: Identificacion honesta. Un User-Agent que finge ser un navegador es una
#: forma de decir que sabes que no deberias estar ahi.
USER_AGENT = "REVO-tesis/1.0 (proyecto academico UTP; +https://github.com/HebertCG/REVO)"

#: Segundos entre peticiones a la misma fuente. No es un limite tecnico: es
#: no cargarle el servidor a quien nos esta dando los datos gratis.
ESPERA_ENTRE_PETICIONES_S = 1.0


class FuenteNoDisponible(Exception):
    """
    La fuente no respondio: sin red, DNS, limite de peticiones o error suyo.

    Existe para separar dos cosas que antes se confundian: "no hay cursos"
    (lista vacia) y "no se pudo preguntar" (esto). Cuando todo devolvia
    lista vacia, una pasada sin salida a internet terminaba "bien", con 0
    propuestas y sin error registrado.
    """


@dataclass(frozen=True)
class CursoCandidato:
    """Un curso propuesto, antes de puntuarlo."""

    titulo: str
    url: str
    descripcion: str | None = None
    idioma: str | None = None
    duracion_horas: float | None = None
    gratuito: bool | None = None
    certificado: bool | None = None
    vistas: int | None = None
    id_externo: str | None = None
    #: Lo que la fuente diga del tema. Se usa para casar con la rama.
    temas: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ValueError("Un curso sin titulo no se puede proponer")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"URL no valida: {self.url!r}")


class Fuente(ABC):
    """
    Una fuente de cursos.

    Subclasear esto obliga a declarar la base legal: es un atributo
    abstracto, asi que una fuente que no lo defina no se puede instanciar.
    """

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Identificador corto, el que va a la columna `fuente`."""

    @property
    @abstractmethod
    def base_legal(self) -> str:
        """
        Por que se puede usar esta fuente.

        Tiene que ser concreto y comprobable: "API publica sin clave,
        robots.txt permite /" sirve; "es publico" no.
        """

    #: Idioma de TODO el catalogo, si lo tiene. None = mezclado o
    #: desconocido (GitHub). Decide a que niveles del roadmap puede aportar
    #: la fuente: ver `agente.niveles_para`.
    idioma_catalogo: str | None = None

    @abstractmethod
    def buscar(self, consulta: str, limite: int = 20) -> list[CursoCandidato]:
        """
        Cursos que casan con la consulta.

        Lista vacia SOLO si la fuente respondio que no hay nada. Si no se
        pudo preguntar, lanza `FuenteNoDisponible`: callarlo es lo que
        dejaba pasadas enteras sin resultados y sin error.
        """

    def __repr__(self) -> str:
        return f"<Fuente {self.nombre}>"


class RespetaRobots:
    """
    Comprueba robots.txt y espacia las peticiones.

    Se cachea por dominio: pedir robots.txt antes de cada peticion
    multiplicaria por dos la carga que se le hace al servidor, que es lo
    contrario de lo que robots.txt intenta conseguir.

    Si robots.txt no se puede leer, se asume PROHIBIDO. Es la direccion
    segura: ante la duda, no molestar. La alternativa —asumir permitido— es
    la que produce los incidentes.
    """

    def __init__(
        self,
        user_agent: str = USER_AGENT,
        espera_s: float = ESPERA_ENTRE_PETICIONES_S,
        dormir=time.sleep,
    ) -> None:
        """
        `espera_s` es por fuente, no global.

        Cada servicio publica su propio limite y son muy distintos: GitHub
        sin clave da 10 busquedas por MINUTO, o sea una cada 6 segundos. Con
        la espera por defecto de 1 s se hacen 60 por minuto y la API empieza
        a devolver 403 a mitad de la pasada, dejando ramas enteras sin
        candidatos. Eso se vio en la primera ejecucion real.
        """
        self.user_agent = user_agent
        self.espera_s = espera_s
        self.dormir = dormir
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._ultima_peticion: dict[str, float] = {}

    def permitido(self, url: str) -> bool:
        dominio = urlparse(url).netloc
        if dominio not in self._cache:
            self._cache[dominio] = self._leer_robots(url)

        lector = self._cache[dominio]
        if lector is None:
            return False
        return lector.can_fetch(self.user_agent, url)

    def _leer_robots(self, url: str):
        partes = urlparse(url)
        lector = urllib.robotparser.RobotFileParser()
        lector.set_url(f"{partes.scheme}://{partes.netloc}/robots.txt")
        try:
            lector.read()
            return lector
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "No se pudo leer robots.txt de %s (%s): se asume prohibido",
                partes.netloc, exc,
            )
            return None

    def esperar_turno(self, url: str) -> None:
        """Espacia las peticiones al mismo dominio."""
        dominio = urlparse(url).netloc
        ultima = self._ultima_peticion.get(dominio)
        if ultima is not None:
            transcurrido = time.monotonic() - ultima
            if transcurrido < self.espera_s:
                self.dormir(self.espera_s - transcurrido)
        self._ultima_peticion[dominio] = time.monotonic()
