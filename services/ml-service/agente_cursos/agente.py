"""
agente.py — Busca cursos, los puntua y los propone. No decide nada.

QUE HACE, EN UNA FRASE

Recorre los 30 huecos del roadmap (10 ramas x 3 niveles), pide candidatos a
cada fuente, los puntua, descarta los malos y deja los buenos en
`curso_candidatos` para que un administrador decida.

QUE NO HACE, Y ES LO IMPORTANTE

No escribe en `courses`. El permiso no lo tiene: corre como `revo_agente`,
que solo alcanza `curso_candidatos` y `agente_cursos_ejecuciones`, y la
migracion 33 comprueba contra todo el esquema que no alcance nada mas.

Es deliberado. Una mala recomendacion de curso le cuesta al alumno tiempo y
dinero, y un proceso automatico no deberia poder incurrir en eso sin que
nadie lo mire. El agente hace el trabajo pesado —buscar, filtrar, ordenar,
detectar enlaces muertos— y la responsabilidad editorial sigue siendo
humana.

POR QUE SE REGISTRA CADA EJECUCION

Un agente en segundo plano que falla en silencio es peor que no tenerlo: el
roadmap se queda desactualizado y nadie se entera hasta que un alumno hace
clic en un enlace muerto. `agente_cursos_ejecuciones` guarda que se consulto,
cuanto se propuso y que fallo. Mismo motivo que `model_training_logs`.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from agente_cursos.fuentes.base import CursoCandidato, Fuente, FuenteNoDisponible
from agente_cursos.puntuacion import normalizar, puntuar

logger = logging.getLogger("revo.agente")

#: Por debajo de esta nota no se propone. Un candidato flojo en la tabla de
#: revision es ruido que le hace perder tiempo a quien aprueba, y el coste
#: de revisar es lo que limita cuanto puede crecer el roadmap.
NOTA_MINIMA = 0.45

#: Relevancia minima, como CONDICION NECESARIA y no como un sumando mas.
#:
#: DEFECTO QUE ESTO CORRIGE, VISTO EN DATOS REALES: un curso puede sacar
#: buena nota total sin tener casi nada que ver con la rama, porque el resto
#: de componentes son faciles de cumplir. Medido con GitHub:
#:
#:     "Hello python"  relevancia 0.08  ->  nota total 0.681  ->  el primero
#:
#: Con la media ponderada sola, un curso de reposteria gratuito y en espanol
#: sacaria una nota parecida: gratis (1.0), espanol (1.0), nivel (0.5),
#: duracion (0.5). La relevancia pesa 0.30 y no basta para hundirlo.
#:
#: Un curso que no trata de la rama no es un curso peor para ese hueco: es
#: un curso equivocado. Eso no se expresa con un peso, se expresa con un
#: filtro.
RELEVANCIA_MINIMA = 0.25

#: Encaje de nivel minimo, como CONDICION NECESARIA.
#:
#: `encaje_de_nivel` da 0.1 a un curso avanzado en Fundamentos y 0.2 a uno
#: introductorio en Experto: son los unicos valores por debajo de esto, y
#: solo salen cuando el propio curso DECLARA el nivel contrario. Lo que no
#: declara nivel (0.5) pasa a cualquier hueco.
#:
#: DEFECTO QUE ESTO CORRIGE: con el reparto entre niveles, "Curso de
#: Introduccion al Hacking" acabo en Experto. Llenaba la ultima plaza y su
#: nota total (0.523) superaba la minima pese a ese 0.2.
ENCAJE_NIVEL_MINIMO = 0.3

#: Que idiomas se admiten en cada escalon del roadmap. Condicion NECESARIA,
#: como la gratuidad.
#:
#: Espanol en los tres. Ingles SOLO en Experto: decision del autor
#: (2026-09-21), porque el material avanzado gratuito esta casi todo en
#: ingles y en espanol cinco ramas se quedaban sin nada en ese nivel. En
#: Fundamentos y Construccion no: quien empieza necesita entender sin
#: traducir. Portugues en ninguno.
#:
#: El idioma sigue puntuando (0.15), asi que en Experto un curso en espanol
#: gana a uno en ingles equivalente: el ingles rellena, no desplaza.
IDIOMAS_ADMITIDOS = {
    1: frozenset({"es"}),
    2: frozenset({"es"}),
    3: frozenset({"es", "en"}),
}

#: Cuantos candidatos se proponen por hueco. Tres da alternativa real al
#: administrador sin convertir la revision en una tarea interminable.
POR_HUECO = 3

NIVELES = (1, 2, 3)

#: Que se busca para cada rama. VARIAS consultas por rama, cada una de una
#: o dos palabras, no una frase larga.
#:
#: MOTIVO, COMPROBADO CONTRA LA API DEL MIT: la busqueda usa semantica AND,
#: asi que exige que TODOS los terminos aparezcan. Medido:
#:
#:     "cybersecurity"                     -> 7 resultados
#:     "cybersecurity information security" -> 0 resultados
#:
#: Una frase de tres palabras devuelve cero y el agente se queda sin
#: candidatos sin que nada falle: el peor tipo de fallo, porque parece que
#: la fuente no tiene cursos de esa rama.
#:
#: Esta separado de TERMINOS_RAMA de puntuacion.py a proposito: estos son
#: para BUSCAR (pocos y precisos) y aquellos para MEDIR relevancia (muchos
#: y amplios).
CONSULTAS = {
    1: ("programming", "software engineering", "web development"),
    2: ("data science", "machine learning", "statistics"),
    3: ("cloud computing", "networks", "systems administration"),
    4: ("cybersecurity", "cryptography", "information security"),
    5: ("computer support", "operations management", "hardware"),
    6: ("software testing", "quality assurance", "verification"),
    7: ("project management", "product management", "leadership"),
    8: ("user experience", "interface design", "usability"),
    9: ("information systems", "business process", "enterprise"),
    10: ("algorithms", "computer science", "research methods"),
}

#: Las mismas ramas, para las fuentes en espanol. ELEGIDAS MIDIENDO: se
#: probaron 97 consultas contra GitHub y se quedo, por rama, la combinacion
#: de tres que mas cursos DISTINTOS en espanol dejaba pasar.
#:
#: Tres lecciones de esa medicion:
#:
#:   1. Frases cortas. "curso de linux administracion" solo casaba con
#:      repositorios de alumnos, ninguno con 15 estrellas: Infraestructura y
#:      QA se quedaban a cero sin que nada fallara.
#:
#:   2. Una palabra que el portugues escribe distinto hace de filtro de
#:      idioma, porque GitHub no ignora las tildes:
#:          "curso java"          -> 15 de 31 en portugues
#:          "curso programación"  -> 31 de 31 en espanol
#:      Por eso van con tilde, y por eso "ciberseguridad" o "sistemas
#:      operativos" funcionan sin "curso": no existen en portugues. Pasaron
#:      de 2 y 0 cursos utiles a 19 y 9.
#:
#:   3. Anadir "espanol" a la consulta no sirve: casi nadie lo escribe en la
#:      descripcion. 12 de 13 consultas asi devolvieron cero.
#:
#: La rama 9 (ERP, CRM) no tiene material en espanol en GitHub: lo que hay
#: de SAP, Odoo o Power BI esta en ingles o es software. Se mantienen sus
#: consultas para que aparezca en cuanto exista, pero ese hueco necesita otra
#: fuente o curacion manual.
#:
#: Que fuente usa que tabla lo decide `consultas_para`, no la fuente: asi una
#: fuente nueva no tiene que traer sus propias consultas.
CONSULTAS_ES = {
    1: ("curso programación", "curso python", "curso react"),
    2: ("curso machine learning", "curso ciencia datos",
        "curso inteligencia artificial"),
    3: ("curso docker", "curso linux", "curso kubernetes"),
    4: ("ciberseguridad", "curso hacking", "curso criptografía"),
    5: ("sistemas operativos", "soporte técnico", "mantenimiento computadoras"),
    6: ("curso testing", "curso pruebas", "curso selenium"),
    7: ("gestión proyectos", "metodologías ágiles", "curso agile"),
    8: ("curso ux", "diseño web", "curso figma"),
    9: ("odoo", "curso sap", "curso power bi"),
    10: ("curso algoritmos", "estructuras datos", "curso arduino"),
}

#: Fuentes cuyo catalogo esta en espanol y esperan consultas en espanol.
FUENTES_EN_ESPANOL = {"github", "wikiversidad"}


def consultas_para(fuente: Fuente, rama: int) -> tuple[str, ...]:
    """
    Que se le pregunta a esta fuente para esta rama.

    La decision vive aqui y no en la fuente para que anadir una fuente nueva
    no obligue a escribir un juego de consultas: basta con decir si espera
    espanol o ingles.
    """
    tabla = CONSULTAS_ES if fuente.nombre in FUENTES_EN_ESPANOL else CONSULTAS
    return tabla.get(rama, ())


@dataclass
class Resultado:
    """Lo que dejo una ejecucion."""

    fuente: str
    consultados: int = 0
    propuestos: int = 0
    descartados: int = 0
    error: str | None = None


#: Una ejecucion abierta desde hace mas de esto no esta en curso: su proceso
#: murio. Una pasada completa dura unos 4 minutos.
#:
#: DEFECTO QUE ESTO CORRIGE: Docker se detuvo a mitad de una pasada y su
#: fila quedo con `terminado_en` vacio, aparentando estar en curso. Paso tres
#: veces en un mismo dia. Nada la iba a cerrar nunca.
SENTENCIA_CERRAR_ABANDONADAS = text("""
    UPDATE agente_cursos_ejecuciones
       SET terminado_en = NOW(),
           error = 'No termino: el proceso se interrumpio (reinicio de '
                   'Docker, falta de memoria o parada a mano)'
     WHERE terminado_en IS NULL
       AND iniciado_en < NOW() - INTERVAL '30 minutes'
""")

SENTENCIA_INSERTAR = text("""
    INSERT INTO curso_candidatos (
        specialization_id, nivel, titulo, url, descripcion, idioma,
        duracion_horas, fuente, id_externo, base_legal,
        gratuito, certificado, vistas, puntuacion, desglose
    ) VALUES (
        :specialization_id, :nivel, :titulo, :url, :descripcion, :idioma,
        :duracion_horas, :fuente, :id_externo, :base_legal,
        :gratuito, :certificado, :vistas, :puntuacion, CAST(:desglose AS jsonb)
    )
    ON CONFLICT (specialization_id, nivel, url) DO UPDATE
       SET puntuacion  = EXCLUDED.puntuacion,
           desglose    = EXCLUDED.desglose,
           recogido_en = NOW(),
           estado      = 'propuesto'
     WHERE curso_candidatos.estado IN ('propuesto', 'retirado')
""")

#: Antes de guardar una rama, lo que ESTA fuente propuso para ella pasa a
#: 'retirado'; lo que vuelve a proponer revive en el INSERT de arriba.
#:
#: POR QUE: el agente corre cada dia y la tabla acumula pasadas. El reparto
#: evita repetidos dentro de una pasada, pero si manana un curso cae en otro
#: nivel quedaria propuesto en dos a la vez, y la cola del administrador se
#: llenaria de propuestas que el agente ya no sostiene. No se borra: queda el
#: historial de que se propuso y cuando dejo de proponerse.
#:
#: Solo esta fuente: otra no tiene por que perder sus propuestas porque esta
#: haya cambiado de opinion.
SENTENCIA_RETIRAR = text("""
    UPDATE curso_candidatos
       SET estado = 'retirado'
     WHERE specialization_id = :rama
       AND fuente = :fuente
       AND estado = 'propuesto'
""")

#: Lo que un humano ya decidio en esta rama, en CUALQUIER nivel. No se
#: vuelve a proponer: un curso rechazado que reaparece en otro hueco es ruido,
#: y uno aprobado propuesto otra vez seria un duplicado.
SENTENCIA_DECIDIDAS = text("""
    SELECT url FROM curso_candidatos
     WHERE specialization_id = :rama
       AND estado IN ('aprobado', 'rechazado', 'enlace_roto')
""")


def seleccionar(
    candidatos: list[CursoCandidato],
    specialization_id: int,
    nivel: int,
    cuantos: int = POR_HUECO,
    nota_minima: float = NOTA_MINIMA,
    relevancia_minima: float = RELEVANCIA_MINIMA,
    solo_gratuitos: bool = True,
    idiomas: frozenset[str] | None = None,
) -> list[tuple[CursoCandidato, object]]:
    """
    Puntua, filtra y ordena. Funcion pura: no toca la base de datos.

    Separarla del guardado es lo que permite probarla sin PostgreSQL, y lo
    que deja ver de un vistazo que criterio se esta aplicando.

    Cinco filtros, y los cuatro primeros son condiciones NECESARIAS que
    ninguna media ponderada puede compensar:

      relevancia   un curso que no trata de la rama no es peor: es el
                   equivocado
      gratuito     el alumno objetivo es un estudiante universitario
                   peruano
      idioma       el del escalon (IDIOMAS_ADMITIDOS). Como sumando no
                   bastaba: un curso brasileno quedo PRIMERO en
                   Infraestructura nivel 3 con 0.766, porque el idioma pesa
                   0.15 y el portugues solo le restaba 0.105
      nivel        un curso que se declara introductorio no va a Experto,
                   ni uno avanzado a Fundamentos
      nota total   entre los que cumplen lo anterior, los mejores
    """
    puntuados = []
    for candidato in candidatos:
        # Un curso de pago no es "menos bueno" para quien no puede pagarlo:
        # es inaccesible. `False` se descarta; `None` (desconocido) pasa y se
        # penaliza en la puntuacion, porque descartar lo desconocido
        # eliminaria fuentes enteras que no declaran precio.
        if solo_gratuitos and candidato.gratuito is False:
            continue

        # Mismo criterio que con el precio: se descarta lo que se SABE que
        # no esta en un idioma admitido para este escalon. Lo desconocido
        # pasa y puntua 0.5, porque un titulo escueto no declara su idioma.
        admitidos = IDIOMAS_ADMITIDOS[nivel] if idiomas is None else idiomas
        codigo = (candidato.idioma or "")[:2].lower()
        if codigo and codigo not in admitidos:
            continue

        nota = puntuar(candidato, specialization_id, nivel)
        if nota.desglose["relevancia"] < relevancia_minima:
            continue
        if nota.desglose["nivel"] < ENCAJE_NIVEL_MINIMO:
            continue
        if nota.total >= nota_minima:
            puntuados.append((candidato, nota))

    # Desempate por URL para que dos ejecuciones con los mismos datos
    # propongan lo mismo en el mismo orden.
    puntuados.sort(key=lambda par: (-par[1].total, par[0].url))
    return puntuados[:cuantos]


def repartir(
    candidatos: list[CursoCandidato],
    specialization_id: int,
    niveles: tuple[int, ...] = NIVELES,
    cuantos: int = POR_HUECO,
) -> dict[int, list[tuple[CursoCandidato, object]]]:
    """
    Reparte los candidatos de una rama entre sus niveles, sin repetir.

    DEFECTO QUE ESTO CORRIGE, visto en la primera pasada completa: cada
    nivel se elegia por separado, y como el encaje de nivel solo pesa 0.20,
    los mismos cursos ganaban en los tres. "Python web" era a la vez
    Fundamentos, Construccion y Experto; Gestion tenia un unico curso
    repetido en los tres huecos. La cobertura decia 27 de 30, pero un
    roadmap con el mismo curso en cada escalon no es un roadmap.

    Ahora cada curso va a UN nivel: se ordenan todos los pares (curso,
    nivel) por nota y se asignan de mayor a menor, saltando el curso ya
    colocado o el nivel ya lleno. No busca el optimo global; busca un
    criterio que se explica en una frase: cada curso va donde mejor encaja,
    mientras quede sitio.

    Tampoco se colocan dos cursos con el MISMO TITULO: en el MIT, "Advanced
    Topics in Cryptography" salia dos veces, dos ediciones con URL distinta.
    Para el alumno es el mismo curso. Como los pares van de mayor a menor
    nota, se queda la edicion mejor puntuada.

    Consecuencia buscada: un hueco puede quedarse vacio. Es la verdad —no
    hay cursos distintos para ese escalon— y es lo que el administrador
    necesita ver.
    """
    pares = []
    for nivel in niveles:
        for candidato, nota in seleccionar(
            candidatos, specialization_id, nivel, cuantos=len(candidatos),
        ):
            pares.append((nota.total, candidato.url, nivel, candidato, nota))

    # Desempate por URL y nivel para que dos ejecuciones con los mismos
    # datos repartan igual.
    pares.sort(key=lambda par: (-par[0], par[1], par[2]))

    por_nivel: dict[int, list] = {nivel: [] for nivel in niveles}
    colocados: set[str] = set()
    titulos: set[str] = set()
    for _, url, nivel, candidato, nota in pares:
        titulo = " ".join(normalizar(candidato.titulo).split())
        if url in colocados or titulo in titulos or len(por_nivel[nivel]) >= cuantos:
            continue
        por_nivel[nivel].append((candidato, nota))
        colocados.add(url)
        titulos.add(titulo)
    return por_nivel


def niveles_para(fuente: Fuente) -> tuple[int, ...]:
    """
    A que escalones puede aportar una fuente, segun el idioma de su catalogo.

    Un catalogo entero en ingles (el del MIT) solo alimenta Experto: buscar
    en el para Fundamentos seria gastar consultas en cursos que el filtro de
    idioma descartaria todos. Uno mezclado (GitHub) aporta a los tres, y el
    filtro decide curso a curso.
    """
    idioma = fuente.idioma_catalogo
    if idioma is None:
        return NIVELES
    return tuple(n for n in NIVELES if idioma in IDIOMAS_ADMITIDOS[n])


def recorrer_huecos(
    fuente: Fuente,
    ramas: list[int] | None = None,
    niveles: tuple[int, ...] | None = None,
) -> dict[tuple[int, int], list[tuple[CursoCandidato, object]]]:
    """
    Busca candidatos para cada hueco del roadmap.

    Se hace UNA consulta por rama, no una por hueco: la fuente devuelve lo
    mismo para los tres niveles de una rama, y pedirlo tres veces seria
    triplicar la carga al servidor para nada. El nivel se aplica despues,
    al puntuar.
    """
    ramas = ramas or list(CONSULTAS)
    niveles = niveles or niveles_para(fuente)
    propuestas = {}
    if not niveles:
        logger.warning("%s no puede aportar a ningun nivel; se salta", fuente.nombre)
        return propuestas
    hechas = fallidas = 0
    ultima_causa: FuenteNoDisponible | None = None

    for rama in ramas:
        consultas = consultas_para(fuente, rama)
        if not consultas:
            logger.warning("La rama %s no tiene consultas definidas; se salta", rama)
            continue

        # Varias consultas cortas y se fusiona, porque la busqueda es AND:
        # una frase larga devuelve cero. La deduplicacion es por URL, que es
        # lo que identifica un curso entre fuentes distintas; el id interno
        # no serviria para eso.
        por_url: dict[str, CursoCandidato] = {}
        fallidas_rama = 0
        for consulta in consultas:
            hechas += 1
            try:
                resultados = fuente.buscar(consulta)
            except FuenteNoDisponible as exc:
                # Un fallo suelto (un 403 puntual) no tumba la pasada.
                fallidas += 1
                fallidas_rama += 1
                ultima_causa = exc
                logger.warning("No se pudo consultar '%s': %s", consulta, exc)
                continue
            for candidato in resultados:
                por_url.setdefault(candidato.url, candidato)

        if fallidas_rama == len(consultas):
            # No es que no haya cursos: es que no se pudo preguntar. Si la
            # rama entrara en las propuestas, `guardar` retiraria lo que ya
            # tenia, y un 403 borraria trabajo bueno.
            logger.warning("Rama %s: ninguna consulta respondio; se deja como estaba", rama)
            continue

        encontrados = list(por_url.values())
        logger.info(
            "Rama %s: %s candidatos unicos de %s (%s consultas)",
            rama, len(encontrados), fuente.nombre, len(consultas),
        )

        for nivel, lista in repartir(encontrados, rama, niveles).items():
            propuestas[(rama, nivel)] = lista

    # Si NINGUNA consulta llego, la pasada no "encontro cero cursos": no
    # pudo preguntar. Eso es un fallo y tiene que constar como tal en la
    # tabla de ejecuciones y en el codigo de salida, o nadie se entera.
    if hechas and fallidas == hechas:
        raise FuenteNoDisponible(
            f"Ninguna de las {hechas} consultas llego a {fuente.nombre}. "
            f"Ultima causa: {ultima_causa}"
        )
    return propuestas


def guardar(db: Session, fuente: Fuente, propuestas: dict) -> int:
    """
    Escribe una pasada en la tabla de revision.

    Por cada rama: retira lo que esta fuente propuso antes, salta lo que un
    humano ya decidio, e inserta o revive lo de hoy. Todo en una sola
    transaccion: quien mire la tabla ve la pasada anterior o la nueva, nunca
    media.
    """
    guardados = 0
    for rama in sorted({rama for rama, _ in propuestas}):
        db.execute(SENTENCIA_RETIRAR, {"rama": rama, "fuente": fuente.nombre})
        decididas = set(db.execute(SENTENCIA_DECIDIDAS, {"rama": rama}).scalars().all())

        for nivel in sorted(n for r, n in propuestas if r == rama):
            for candidato, nota in propuestas[(rama, nivel)]:
                if candidato.url in decididas:
                    continue
                db.execute(SENTENCIA_INSERTAR, _fila(fuente, rama, nivel, candidato, nota))
                guardados += 1

    db.commit()
    return guardados


def _fila(fuente: Fuente, rama: int, nivel: int, candidato: CursoCandidato, nota) -> dict:
    """Parametros de SENTENCIA_INSERTAR para un candidato."""
    return {
        "specialization_id": rama,
        "nivel": nivel,
        "titulo": candidato.titulo[:500],
        "url": candidato.url,
        "descripcion": candidato.descripcion,
        "idioma": candidato.idioma,
        "duracion_horas": candidato.duracion_horas,
        "fuente": fuente.nombre,
        "id_externo": (candidato.id_externo or "")[:120] or None,
        "base_legal": fuente.base_legal,
        "gratuito": candidato.gratuito,
        "certificado": candidato.certificado,
        "vistas": candidato.vistas,
        "puntuacion": round(nota.total, 3),
        "desglose": json.dumps(nota.como_dict()["desglose"]),
    }


def ejecutar(db: Session, fuente: Fuente, ramas: list[int] | None = None) -> Resultado:
    """
    Una pasada completa del agente sobre una fuente.

    Registra la ejecucion pase lo que pase: si falla a mitad, la fila queda
    con el error, que es justo cuando hace falta saberlo.
    """
    resultado = Resultado(fuente=fuente.nombre)

    abandonadas = db.execute(SENTENCIA_CERRAR_ABANDONADAS).rowcount
    if abandonadas:
        logger.warning("Se cerraron %s ejecuciones abandonadas", abandonadas)

    fila_id = db.execute(
        text("INSERT INTO agente_cursos_ejecuciones (fuente) VALUES (:f) RETURNING id"),
        {"f": fuente.nombre},
    ).scalar()
    db.commit()

    try:
        propuestas = recorrer_huecos(fuente, ramas)
        resultado.consultados = sum(len(v) for v in propuestas.values())
        resultado.propuestos = guardar(db, fuente, propuestas)
    except Exception as exc:  # noqa: BLE001
        resultado.error = str(exc)[:500]
        logger.error("El agente fallo con %s: %s", fuente.nombre, exc, exc_info=True)
    finally:
        db.execute(text("""
            UPDATE agente_cursos_ejecuciones
               SET terminado_en = NOW(), consultados = :c,
                   propuestos = :p, error = :e
             WHERE id = :id
        """), {
            "id": fila_id, "c": resultado.consultados,
            "p": resultado.propuestos, "e": resultado.error,
        })
        db.commit()

    return resultado
