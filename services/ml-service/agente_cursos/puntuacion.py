"""
puntuacion.py — Que significa "el mejor curso" para un alumno de REVO.

EL PROBLEMA DE FONDO

"El mejor curso" no existe en abstracto. El mejor curso de ciberseguridad
para un alumno de tercer ciclo en Piura no es el mismo que para un ingeniero
con cinco anos de experiencia y presupuesto de empresa.

Asi que la puntuacion no mide calidad absoluta: mide ENCAJE con el hueco
concreto del roadmap y con el alumno objetivo de REVO.

LOS SEIS COMPONENTES Y POR QUE PESAN LO QUE PESAN

  relevancia  0.30  ¿trata de lo que la rama trata? Sin esto, lo demas da
                    igual: un curso excelente de la rama equivocada es
                    ruido en el roadmap.

  nivel       0.20  ¿encaja con el escalon? Un curso de posgrado en el hueco
                    "Fundamentos" no lo llena: lo bloquea.

  acceso      0.20  gratuito o de pago. No es ideologia: el alumno objetivo
                    es un estudiante universitario peruano, y un curso de
                    400 dolares no es una recomendacion, es una frustracion.

  idioma      0.15  el espanol suma. La mayoria del material bueno esta en
                    ingles, asi que no se exige, pero se prefiere.

  duracion    0.10  ni un video de 8 minutos ni un master de 300 horas. El
                    roadmap pide algo que se pueda terminar en un semestre.

  senales     0.05  vistas, certificado. Van al final a proposito: son las
                    mas faciles de inflar y las que menos dicen del encaje.

POR QUE ESTA ESCRITO ASI Y NO APRENDIDO

Se podria aprender de que cursos aprueba el administrador. Con cero
aprobaciones hasta la fecha, eso seria entrenar sobre nada. Estos pesos son
un punto de partida DECLARADO y discutible; cuando haya un historial de
aprobaciones y rechazos se podran ajustar con datos.

Mientras tanto, cada candidato guarda su desglose. Una nota sin desglose no
se puede discutir, y quien aprueba necesita poder discutirla.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PESOS = {
    "relevancia": 0.30,
    "nivel": 0.20,
    "acceso": 0.20,
    "idioma": 0.15,
    "duracion": 0.10,
    "senales": 0.05,
}

#: Horas ideales por nivel del roadmap. Los rangos salen de lo que un alumno
#: puede terminar en paralelo a sus cursos de la universidad.
HORAS_IDEALES = {
    1: (8, 40),     # Fundamentos: un mes tranquilo
    2: (20, 80),    # Construccion: un semestre a ritmo suave
    3: (40, 150),   # Experto: un compromiso serio
}

#: Palabras que delatan el nivel en el titulo o la descripcion.
#:
#: Se buscan como subcadena, asi que van por RAIZ para cubrir genero y
#: numero: "avanzad" casa con avanzado, avanzada, avanzados y avanzadas.
#: Con la palabra entera, "Ciberseguridad avanzada" no daba senal de nivel
#: y competia por el hueco de Construccion.
SENALES_NIVEL = {
    1: ("introduccion", "introduction", "fundamentos", "fundamentals", "basic",
        "beginner", "principiante", "getting started", "101",
        # "Aprende React Native desde cero" acababa en el nivel Experto.
        "desde cero", "primeros pasos", "iniciacion", "from scratch"),
    3: ("avanzad", "advanced", "graduate", "posgrado", "master", "expert",
        "deep dive", "professional certificate"),
}

#: Terminos que definen cada rama. Se usan para medir relevancia contra el
#: titulo, la descripcion y los temas que declara la fuente.
#:
#: Estan en ingles y espanol porque las fuentes mezclan los dos.
#: Incluyen TECNOLOGIAS CONCRETAS, no solo conceptos.
#:
#: Hueco detectado con datos reales: "Hello Python" (37 000 estrellas, uno de
#: los mejores cursos de programacion en espanol que hay) sacaba relevancia
#: 0.08 para Desarrollo de Software, porque la lista solo tenia palabras
#: abstractas —"programacion", "desarrollo"— y ninguna decia "python".
#:
#: Los cursos reales no se llaman "Curso de desarrollo de software": se
#: llaman "Curso de Python", "Curso de Java desde cero". La lista tiene que
#: parecerse a como la gente nombra las cosas, no a como las nombra un plan
#: de estudios.
TERMINOS_RAMA = {
    1: ("software", "programming", "programacion", "development", "desarrollo",
        "web", "app", "coding", "engineering",
        "python", "java", "javascript", "typescript", "react", "backend",
        "frontend", "api", "poo", "orientada a objetos"),
    2: ("data", "datos", "machine learning", "statistics", "estadistica",
        "analytics", "artificial intelligence", "inteligencia artificial",
        "pandas", "numpy", "deep learning", "redes neuronales", "ciencia de datos"),
    3: ("cloud", "infrastructure", "infraestructura", "network", "redes",
        "devops", "systems", "sistemas", "server", "linux",
        "docker", "kubernetes", "aws", "azure", "servidores", "ccna"),
    4: ("security", "seguridad", "cybersecurity", "ciberseguridad", "crypto",
        "hacking", "forensics", "privacy", "risk",
        "pentesting", "criptografia", "malware", "forense", "owasp"),
    5: ("support", "soporte", "help desk", "operations", "operaciones",
        "troubleshooting", "it service", "hardware",
        "mantenimiento", "mesa de ayuda", "itil", "windows server",
        "sistemas operativos", "active directory", "powershell"),
    6: ("testing", "quality", "calidad", "qa", "verification", "validation",
        "debugging", "reliability",
        "selenium", "cypress", "pruebas", "automation", "tdd", "unit test"),
    7: ("management", "gestion", "product", "producto", "project", "proyecto",
        "leadership", "agile", "scrum", "business",
        "kanban", "pmi", "liderazgo", "metodologias agiles"),
    8: ("design", "diseno", "user experience", "ux", "ui", "interface",
        "usability", "usabilidad", "interaction", "visual",
        "figma", "prototipado", "wireframe", "accesibilidad"),
    9: ("enterprise", "empresarial", "erp", "business process", "procesos",
        "information systems", "sistemas de informacion", "supply chain",
        "sap", "crm", "bpm", "power bi", "gestion empresarial",
        "odoo", "abap", "erpnext", "bpmn", "salesforce", "oracle"),
    10: ("research", "investigacion", "algorithms", "algoritmos", "theory",
         "teoria", "innovation", "innovacion", "computation", "quantum",
         "estructuras de datos", "compiladores", "blockchain", "arduino",
         "iot", "matematicas", "solidity", "embebidos", "realidad virtual",
         "realidad aumentada", "kernel", "ensamblador"),
}


@dataclass(frozen=True)
class Nota:
    """Puntuacion de un candidato, con su desglose."""

    total: float
    desglose: dict[str, float]

    def como_dict(self) -> dict:
        return {"total": round(self.total, 3),
                "desglose": {k: round(v, 3) for k, v in self.desglose.items()}}


def normalizar(texto: str | None) -> str:
    """Minusculas y sin tildes, para que 'diseño' case con 'diseno'."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def relevancia(candidato, specialization_id: int) -> float:
    """
    Cuanto se parece el curso al tema de la rama.

    Se mira titulo, temas y descripcion, con pesos distintos: un termino en
    el TITULO dice mucho mas que el mismo termino perdido en un parrafo de
    descripcion, donde puede aparecer de pasada.

    Cada termino tiene que empezar palabra. Antes se buscaba como subcadena
    y "ux" (Diseno UX/UI) casaba con "linux", "api" con "capitulo": un
    curso de Linux sumaba relevancia para UX/UI. Solo se ancla el PRINCIPIO
    para que "networking", "apis" o "disenador" sigan contando.
    """
    terminos = TERMINOS_RAMA.get(specialization_id, ())
    if not terminos:
        return 0.0

    titulo = normalizar(candidato.titulo)
    temas = normalizar(" ".join(candidato.temas))
    descripcion = normalizar(candidato.descripcion)

    puntos = 0.0
    for termino in terminos:
        patron = re.compile(r"\b" + re.escape(normalizar(termino)))
        if patron.search(titulo):
            puntos += 1.0
        elif patron.search(temas):
            puntos += 0.6
        elif patron.search(descripcion):
            puntos += 0.25

    # Tres coincidencias fuertes ya son relevancia plena: exigir mas
    # penalizaria a los cursos con titulo escueto, que suelen ser los buenos.
    return min(puntos / 3.0, 1.0)


def encaje_de_nivel(candidato, nivel: int) -> float:
    """
    ¿El curso corresponde a este escalon del roadmap?

    EL TITULO MANDA SOBRE LA DESCRIPCION

    Un curso puede llamarse "Advanced cryptography" y decir en la
    descripcion "cubrimos los fundamentos de...". Mirando el texto entero
    aparecen las dos senales, y quedarse con la primera que coincide da un
    encaje perfecto para el hueco de Fundamentos a un curso de posgrado.

    Ese fallo se detecto en pruebas y era real: el alumno se habria
    estrellado en el primer escalon de su roadmap.

    Ahora el titulo decide, y la descripcion solo se consulta cuando el
    titulo no dice nada. Es el mismo criterio que en `relevancia`: lo que
    esta en el titulo describe el curso; lo que esta en la descripcion puede
    aparecer de pasada.

    Sin senales en ninguno de los dos devuelve 0.5, no 0: la mayoria de los
    cursos no declaran su nivel, y castigarlos por eso dejaria fuera
    material perfectamente valido.
    """
    def senales_en(texto: str) -> tuple[bool, bool]:
        t = normalizar(texto)
        return (
            any(normalizar(s) in t for s in SENALES_NIVEL[1]),
            any(normalizar(s) in t for s in SENALES_NIVEL[3]),
        )

    basico, avanzado = senales_en(candidato.titulo)
    if not (basico or avanzado):
        basico, avanzado = senales_en(candidato.descripcion or "")

    # Las dos a la vez es ambiguo: ni se premia ni se castiga. Afirmar un
    # nivel cuando el propio curso se describe de las dos formas seria
    # inventarse una certeza.
    if basico and avanzado:
        return 0.5

    if nivel == 1:
        if basico:
            return 1.0
        # Un curso de posgrado en el hueco "Fundamentos" no lo llena: lo
        # bloquea, y el alumno se estrella en el primer escalon.
        return 0.1 if avanzado else 0.5

    if nivel == 3:
        if avanzado:
            return 1.0
        return 0.2 if basico else 0.5

    # Nivel 2 es el intermedio: cualquiera de los dos extremos encaja peor
    # que algo sin etiquetar.
    return 0.4 if (basico or avanzado) else 0.8


def acceso(candidato) -> float:
    """
    Gratuito frente a pago.

    No es ideologia: el alumno objetivo es un estudiante universitario
    peruano. Un curso de 400 dolares no es una recomendacion, es una
    frustracion con formato de recomendacion.

    Un curso de pago no se descarta —puede ser el mejor del hueco— pero
    parte con desventaja.
    """
    if candidato.gratuito is True:
        return 1.0
    if candidato.gratuito is False:
        return 0.35
    return 0.6   # desconocido: ni premio ni castigo


def idioma(candidato) -> float:
    """
    El espanol suma, el ingles no resta del todo.

    La mayor parte del material bueno esta en ingles, asi que exigir espanol
    dejaria el roadmap vacio. Pero entre dos cursos equivalentes, el que el
    alumno puede seguir sin traducir mentalmente es mejor.
    """
    codigo = (candidato.idioma or "").lower()[:2]
    if codigo == "es":
        return 1.0
    if codigo == "en":
        return 0.55
    if not codigo:
        return 0.5
    return 0.3   # otro idioma: poco util aqui


def duracion(candidato, nivel: int) -> float:
    """
    Ni un video suelto ni un master.

    Sin dato devuelve 0.5: no saber cuanto dura no es lo mismo que durar
    mal, y penalizarlo eliminaria fuentes enteras que no publican duracion.
    """
    horas = candidato.duracion_horas
    if horas is None or horas <= 0:
        return 0.5

    minimo, maximo = HORAS_IDEALES[nivel]
    if minimo <= horas <= maximo:
        return 1.0
    if horas < minimo:
        # Demasiado corto para llenar un escalon del roadmap.
        return max(0.2, horas / minimo)
    # Demasiado largo: decae, pero no a cero. Un curso largo y bueno sigue
    # siendo util si el alumno se compromete.
    return max(0.2, maximo / horas)


def senales(candidato) -> float:
    """
    Popularidad y certificado.

    Peso bajo a proposito: son las senales mas faciles de inflar y las que
    menos dicen sobre si el curso encaja en ESTE hueco para ESTE alumno.
    """
    puntos = 0.0
    vistas = candidato.vistas or 0
    if vistas > 0:
        # Escala logaritmica: la diferencia entre 100 y 1 000 vistas importa
        # mucho mas que entre 100 000 y 101 000.
        import math
        puntos += min(math.log10(vistas + 1) / 5.0, 1.0) * 0.6
    if candidato.certificado:
        puntos += 0.4
    return min(puntos, 1.0)


def puntuar(candidato, specialization_id: int, nivel: int) -> Nota:
    """Nota agregada 0..1, con el desglose que la justifica."""
    if nivel not in HORAS_IDEALES:
        raise ValueError(f"Nivel {nivel} fuera del roadmap (1..3)")

    componentes = {
        "relevancia": relevancia(candidato, specialization_id),
        "nivel": encaje_de_nivel(candidato, nivel),
        "acceso": acceso(candidato),
        "idioma": idioma(candidato),
        "duracion": duracion(candidato, nivel),
        "senales": senales(candidato),
    }
    total = sum(valor * PESOS[nombre] for nombre, valor in componentes.items())
    return Nota(total=total, desglose=componentes)
