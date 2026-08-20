import { useState, useEffect, useRef, useEffectEvent, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { surveyApi } from '../services/api'
import personaCelularGaming from '../assets/persona-celular-gaming.png'
import personaDiferenciaGaming from '../assets/persona-diferencia-gaming.png'
import personaRepartiendoGaming from '../assets/persona-repartiendo-gaming.png'
import manoRepartiendoRevo from '../assets/mano-repartiendo-revo.png'
import manoSueltaRevo from '../assets/mano-suelta-revo.png'
import cartaRevoExplora from '../assets/carta-revo-explora.png'
import cartaRevoConecta from '../assets/carta-revo-conecta.png'
import cartaRevoAnaliza from '../assets/carta-revo-analiza.png'
import cartaRevoConstruye from '../assets/carta-revo-construye.png'
import cartaRevoVision from '../assets/carta-revo-vision.png'
import personaSelectorMinijuego from '../assets/persona-selector-minijuego.png'
import personaRutaGaming from '../assets/persona-ruta-gaming.png'
import carritoRevo from '../assets/carrito-revo.png'
import {
  getRemainingPhaseTransitionMs,
  shouldStartQuestionShuffle,
} from './questionnaireAnimation'
import {
  MINI_GAMES,
  advanceRoadState,
  chooseQuestionnaireMiniGame,
  createRoadState,
  getRoadObstacles,
  getRoadTargetLane,
  resolveQuestionnaireEntryView,
} from './questionnaireMiniGames'
import '../theme/app.css'
import './Questionnaire.css'

// Cada categoria trae su propio color de ambiente. Solo se ve una a la
// vez, asi que no compiten entre si: el cambio de color es lo que hace
// que 25 preguntas no se sientan iguales.
const CATEGORIAS = {
  academic:    { label: 'Académico',    icon: 'AC', color: '#5BB8FF' },
  skills:      { label: 'Habilidades',  icon: 'HB', color: '#79D89B' },
  interests:   { label: 'Intereses',    icon: 'IN', color: '#FF756A' },
  personality: { label: 'Personalidad', icon: 'PR', color: '#D9B35B' },
}
const COLOR_BASE = '#5BB8FF'
const CARGA_INICIAL_MIN_MS = 3200
const MotionDiv = motion.div

const FASES = [
  { n: 1, nombre: 'Explora', detalle: 'Calibración' },
  { n: 2, nombre: 'Afina', detalle: 'Profundización' },
  { n: 3, nombre: 'Revela', detalle: 'Perfil profesional' },
]

// Etiquetas de la escala. Van sobre el propio botón, no en una fila
// aparte: antes había que cruzar la mirada entre el número y su
// significado, que es justo lo que hace lento un test de 25 preguntas.
// El circulo crece con el valor, asi que la escala se entiende antes
// de leer: el tamano comunica la intensidad y la palabra la confirma.
const ESCALA = [
  { v: 1, corta: 'Para nada',  larga: 'No tiene nada que ver conmigo' },
  { v: 2, corta: 'Poco',       larga: 'Me representa poco' },
  { v: 3, corta: 'A medias',   larga: 'Ni sí ni no' },
  { v: 4, corta: 'Bastante',   larga: 'Me representa bastante' },
  { v: 5, corta: 'Totalmente', larga: 'Soy exactamente así' },
]

// Reserva local por si la base de datos no responde. La fuente real
// son las 40 preguntas de psychometric_questions.
const FASE3_RESERVA = [
  {
    id: 'p3_fb_1',
    question: 'Acabas de terminar un módulo de trabajo. ¿Cuál es tu reacción natural?',
    options: [
      { key: 'A', text: 'Lo reviso buscando posibles errores antes de entregarlo' },
      { key: 'B', text: 'Lo entrego y si hay correcciones, las ajusto sobre la marcha' },
      { key: 'C', text: 'Lo comparto con mi equipo para recibir retroalimentación primero' },
      { key: 'D', text: 'Lo optimizo para que sea más limpio y eficiente antes de entregarlo' },
    ],
  },
  {
    id: 'p3_fb_2',
    question: 'Un proceso falla inesperadamente. ¿Qué haces primero?',
    options: [
      { key: 'A', text: 'Construyo un diagnóstico completo antes de intervenir' },
      { key: 'B', text: 'Implemento una solución temporal y luego investigo la causa raíz' },
      { key: 'C', text: 'Escalo al líder del equipo de inmediato' },
      { key: 'D', text: 'No actúo hasta tener certeza sobre la causa exacta' },
    ],
  },
  {
    id: 'p3_fb_3',
    question: '¿Cómo prefieres aprender algo nuevo en tu área?',
    options: [
      { key: 'A', text: 'Con documentación oficial, paso a paso y de forma estructurada' },
      { key: 'B', text: 'Construyendo un proyecto real desde el primer día' },
      { key: 'C', text: 'En equipo, con mentores o grupos de estudio colaborativos' },
      { key: 'D', text: 'Con materiales curados y tomando notas detalladas para repasar' },
    ],
  },
  {
    id: 'p3_fb_4',
    question: 'Descríbete en un equipo de trabajo:',
    options: [
      { key: 'A', text: 'El estratega: diseño la estructura general antes de ejecutar' },
      { key: 'B', text: 'El ejecutor: soy el primero en tener resultados en mano' },
      { key: 'C', text: 'El conector: facilito la comunicación y coordinación del equipo' },
      { key: 'D', text: 'El revisor: nada sale sin que yo lo haya validado previamente' },
    ],
  },
]

function calcArchetype(answers) {
  const cuenta = { A: 0, B: 0, C: 0, D: 0 }
  Object.values(answers).forEach((v) => { if (cuenta[v] !== undefined) cuenta[v]++ })
  const max = Math.max(...Object.values(cuenta))
  const ganadores = Object.entries(cuenta).filter(([, c]) => c === max).map(([k]) => k)
  return ganadores[Math.floor(Math.random() * ganadores.length)]
}

function Ambiente() {
  return (
    <div className="quiz-ambiente" aria-hidden="true">
      <span className="quiz-tinta quiz-tinta-1" />
      <span className="quiz-tinta quiz-tinta-2" />
      <span className="quiz-grano" />
      <span className="quiz-orbita quiz-orbita-1" />
      <span className="quiz-orbita quiz-orbita-2" />
    </div>
  )
}

function FaseHud({ fase, actual, total, miniGame }) {
  const esRuta = miniGame === MINI_GAMES.ROAD
  return (
    <header className="quiz-hud">
      <div className="quiz-partida">
        <span className="quiz-partida-marca" aria-hidden="true">R</span>
        <span>
          <strong>Partida de afinidad</strong>
          <small>{esRuta ? 'Tu perfil avanza parada a parada' : 'Tu perfil se construye carta a carta'}</small>
        </span>
      </div>

      <ol className="quiz-fases" aria-label={`Fase ${fase} de 3`}>
        {FASES.map((item) => (
          <li
            key={item.n}
            className={item.n === fase ? 'activa' : item.n < fase ? 'superada' : ''}
            aria-current={item.n === fase ? 'step' : undefined}
          >
            <span>{item.n}</span>
            <div><strong>{item.nombre}</strong><small>{item.detalle}</small></div>
          </li>
        ))}
      </ol>

      <div className="quiz-marcador" aria-label={`${esRuta ? 'Parada' : 'Carta'} ${actual} de ${total}`}>
        <small>{esRuta ? 'Parada' : 'Carta'}</small>
        <strong>{String(actual).padStart(2, '0')}</strong>
        <span>/ {String(total).padStart(2, '0')}</span>
      </div>
    </header>
  )
}

function PanelMazo({ fase, items, respuestas, actual, miniGame }) {
  const total = items.length
  const resueltas = items.filter((item) => respuestas[item.id] !== undefined).length
  const jugadas = items.filter((item, i) => respuestas[item.id] !== undefined && i !== actual)
  const porcentaje = total ? Math.round((resueltas / total) * 100) : 0
  const textos = {
    1: 'Prueba distintos territorios. No hay respuestas correctas, solo señales.',
    2: 'El mazo se concentra en las áreas donde mostraste más afinidad.',
    3: 'Tus elecciones finales revelan cómo trabajas cuando toca decidir.',
  }

  const esRuta = miniGame === MINI_GAMES.ROAD

  return (
    <aside className={`quiz-panel ${esRuta ? 'quiz-panel-ruta' : ''}`}>
      <figure className="quiz-panel-visual">
        <img src={esRuta ? personaRutaGaming : personaDiferenciaGaming} alt="" decoding="async" />
      </figure>
      <span className="quiz-ronda">Ronda {fase}</span>
      <h2>{FASES[fase - 1].nombre}</h2>
      <p>{esRuta ? 'Conduce hasta cada parada. Cada meta abre una nueva señal.' : textos[fase]}</p>

      <div
        className="quiz-mini-mazo"
        role="progressbar"
        aria-label={esRuta ? 'Paradas superadas' : 'Cartas resueltas'}
        aria-valuemin="0"
        aria-valuemax={total}
        aria-valuenow={resueltas}
      >
        <div className="quiz-mini-pila" aria-hidden="true">
          {jugadas.length === 0 && <i className="vacia" />}
          {jugadas.slice(-8).map((item, i, cartas) => (
            <i
              key={item.id}
              className={i === cartas.length - 1 ? 'nueva' : ''}
              style={{ '--pila': i, '--giro-pila': `${(i % 3 - 1) * 2.2}deg` }}
            />
          ))}
        </div>
        <span className="quiz-mini-etiqueta">{esRuta ? 'Paradas superadas' : 'Cartas jugadas'}</span>
        <strong>{jugadas.length} {esRuta ? 'en la ruta' : 'en el mazo'}</strong>
      </div>

      <div className="quiz-panel-datos">
        <span><small>Resueltas</small><strong>{resueltas}/{total}</strong></span>
        <span><small>Avance</small><strong>{porcentaje}%</strong></span>
      </div>
    </aside>
  )
}

/** Pantalla completa para esperas y transiciones. */
function Pantalla({ titulo, texto, aviso, imagen = personaRepartiendoGaming, etiqueta = 'Preparando la partida' }) {
  return (
    <div className="rv quiz-espera">
      <Ambiente />
      <div className="quiz-espera-tablero">
        <figure className="quiz-espera-visual">
          <img src={imagen} alt="Personaje de REVO preparando las cartas del cuestionario" decoding="async" />
        </figure>
        <div className="quiz-espera-caja" role="status" aria-live="polite">
          <span className="quiz-espera-etiq">{etiqueta}</span>
          <h2>{titulo}</h2>
          <p>{texto}</p>
          {aviso && <p className="quiz-aviso">{aviso}</p>}
          <div className="quiz-cargando" aria-hidden="true">
            <span /><span /><span /><span /><span />
          </div>
        </div>
      </div>
    </div>
  )
}

const DATOS_MINIJUEGO = {
  [MINI_GAMES.CARDS]: {
    numero: '01',
    etiqueta: 'Mano de señales',
    titulo: 'Elige la carta que abrirá cada pregunta',
    texto: 'Cinco cartas llegan a la mesa. Confía en tu primera elección para revelar la siguiente señal.',
    instrucciones: ['Elige una carta de la mano', 'Responde la pregunta que guarda', 'Juega la carta para avanzar'],
    control: 'Teclado 1–5 o toca una carta',
    accion: 'Repartir cartas',
    imagen: personaRepartiendoGaming,
  },
  [MINI_GAMES.ROAD]: {
    numero: '02',
    etiqueta: 'Ruta de afinidad',
    titulo: 'Conduce hasta la próxima parada',
    texto: 'Recorre la pista horizontal, esquiva las barreras y llega por el carril iluminado para desbloquear cada pregunta.',
    instrucciones: ['Sube y baja para cambiar de carril', 'Derecha acelera; izquierda frena', 'Esquiva las barreras y cruza la meta'],
    control: 'Cuatro flechas o WASD · cruceta táctil en celular',
    accion: 'Comenzar recorrido',
    imagen: personaRutaGaming,
  },
}

function SelectorMinijuego({ reduceMotion, miniGame, loading, ready, error, onPlay }) {
  const seleccionado = miniGame ? DATOS_MINIJUEGO[miniGame] : null
  const puedeJugar = !!miniGame && !loading && ready && !error

  return (
    <div className={`rv quiz-selector ${miniGame ? `quiz-selector-elegido quiz-selector-elegido-${miniGame}` : 'quiz-selector-sorteando'}`}>
      <Ambiente />
      <div className="quiz-selector-lienzo" role="status" aria-live="polite">
        <div className="quiz-selector-copy">
          <span className="quiz-selector-etiq">{seleccionado ? 'Desafío seleccionado' : 'REVO está eligiendo'}</span>
          <h1>{seleccionado ? seleccionado.etiqueta : '¿Qué desafío te toca hoy?'}</h1>
          <p>{seleccionado
            ? `¡Listo! REVO eligió ${seleccionado.etiqueta}. Presiona Jugar para conocer la dinámica.`
            : 'Observa el sorteo: las cartas compiten contra el carrito por ser tu desafío de hoy.'}</p>
          <div className="quiz-selector-opciones" aria-hidden="true">
            <span className={`quiz-selector-opcion cartas ${miniGame === MINI_GAMES.CARDS ? 'ganadora' : ''}`}>
              <b>01</b>
              <i><img src={cartaRevoExplora} alt="" /></i>
              <em>Mano de señales</em>
            </span>
            <span className={`quiz-selector-opcion ruta ${miniGame === MINI_GAMES.ROAD ? 'ganadora' : ''}`}>
              <b>02</b>
              <i><img src={carritoRevo} alt="" /></i>
              <em>Ruta de afinidad</em>
            </span>
          </div>

          {seleccionado && (
            <button
              type="button"
              className="quiz-selector-jugar"
              onClick={onPlay}
              disabled={!puedeJugar}
            >
              {error ? 'No se pudo preparar' : loading || !ready ? 'Preparando preguntas…' : 'Jugar'}
              {!loading && ready && !error && <span aria-hidden="true">→</span>}
            </button>
          )}
        </div>

        <MotionDiv
          className="quiz-selector-personaje"
          initial={{ opacity: 0, y: reduceMotion ? 0 : 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduceMotion ? .1 : .55, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="quiz-selector-halo" aria-hidden="true" />
          <img src={personaSelectorMinijuego} alt="Personaje de REVO pensando qué minijuego elegir" />
          <span className="quiz-selector-pensamiento" aria-hidden="true"><i /><i /><b>?</b></span>
        </MotionDiv>

        <div className="quiz-selector-ruleta" aria-hidden="true">
          <span className="cartas"><img src={cartaRevoExplora} alt="" /></span>
          <i>VS</i>
          <span className="ruta"><img src={carritoRevo} alt="" /></span>
        </div>
        <p className="quiz-selector-estado">{seleccionado ? `${seleccionado.etiqueta} elegido` : 'Sorteando desafío…'}</p>
      </div>
    </div>
  )
}

function IntroduccionMinijuego({ miniGame, onStart, reduceMotion }) {
  const datos = DATOS_MINIJUEGO[miniGame]

  return (
    <div className={`rv quiz-intro quiz-intro-${miniGame}`}>
      <Ambiente />
      <MotionDiv
        className="quiz-intro-tablero"
        initial={{ opacity: 0, scale: reduceMotion ? 1 : .975 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: reduceMotion ? .1 : .45, ease: [0.22, 1, 0.36, 1] }}
      >
        <figure className="quiz-intro-visual">
          <img src={datos.imagen} alt={`Personaje de REVO presentando ${datos.etiqueta}`} />
          <figcaption>Minijuego {datos.numero}</figcaption>
        </figure>

        <section className="quiz-intro-copy">
          <span className="quiz-intro-etiq">Desafío seleccionado · {datos.etiqueta}</span>
          <h1>{datos.titulo}</h1>
          <p>{datos.texto}</p>
          <ol className="quiz-intro-pasos">
            {datos.instrucciones.map((paso, indice) => (
              <li key={paso}><b>0{indice + 1}</b><span>{paso}</span></li>
            ))}
          </ol>
          <p className="quiz-intro-control"><span aria-hidden="true">⌁</span>{datos.control}</p>
          <button type="button" className="quiz-intro-boton" onClick={onStart}>
            {datos.accion}<span aria-hidden="true">→</span>
          </button>
        </section>
      </MotionDiv>
    </div>
  )
}

function RutaPreguntas({ questionIndex, fase, onLlegar, reduceMotion }) {
  const [estado, setEstado] = useState(createRoadState)
  const driveTimerRef = useRef(null)
  const targetLane = getRoadTargetLane(questionIndex)
  const obstacles = useMemo(() => getRoadObstacles(questionIndex), [questionIndex])
  const nombresCarril = ['izquierdo', 'central', 'derecho']

  const conducir = useCallback((accion) => {
    setEstado((actual) => advanceRoadState(actual, accion, targetLane, obstacles))
  }, [obstacles, targetLane])
  const notificarLlegada = useEffectEvent(() => onLlegar())

  const detenerControl = () => {
    clearInterval(driveTimerRef.current)
    driveTimerRef.current = null
  }

  const iniciarControl = (accion) => {
    detenerControl()
    conducir(accion)
    if (accion === 'right' || accion === 'left') {
      driveTimerRef.current = setInterval(() => conducir(accion), 145)
    }
  }

  useEffect(() => {
    const manejarTeclaRuta = (event) => {
      if (event.target.matches('input, textarea, select')) return
      const teclas = {
        ArrowLeft: 'left', a: 'left', A: 'left',
        ArrowRight: 'right', d: 'right', D: 'right',
        ArrowUp: 'up', w: 'up', W: 'up',
        ArrowDown: 'down', s: 'down', S: 'down',
      }
      const accion = teclas[event.key]
      if (!accion) return
      event.preventDefault()
      conducir(accion)
    }
    window.addEventListener('keydown', manejarTeclaRuta)
    return () => window.removeEventListener('keydown', manejarTeclaRuta)
  }, [conducir])

  useEffect(() => {
    if (!estado.completed) return undefined
    detenerControl()
    const timer = setTimeout(notificarLlegada, reduceMotion ? 100 : 700)
    return () => clearTimeout(timer)
  }, [estado.completed, reduceMotion])

  useEffect(() => () => detenerControl(), [])

  const avanceHorizontal = `${estado.progress * .86}cqw`
  const estadoTexto = estado.completed
    ? 'Parada alcanzada. Abriendo pregunta…'
    : estado.collision
      ? `¡Choque! Esquiva el obstáculo cambiando al carril ${estado.lane === 0 ? 'central o inferior' : estado.lane === 2 ? 'central o superior' : 'superior o inferior'}.`
    : estado.blocked
      ? `La parada está en el carril ${nombresCarril[targetLane]}. Cambia de carril.`
      : `Esquiva los obstáculos y llega al carril ${nombresCarril[targetLane]}.`

  return (
    <MotionDiv
      key="ruta-preguntas"
      className="quiz-ruta"
      initial={{ opacity: 0, y: reduceMotion ? 0 : 18 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: reduceMotion ? 1 : .985 }}
      transition={{ duration: reduceMotion ? .1 : .38, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="quiz-ruta-cab">
        <span>Minijuego 02 · Ronda {fase}</span>
        <strong>Parada {String(questionIndex + 1).padStart(2, '0')}</strong>
      </div>
      <h1>Conduce hasta tu próxima pregunta</h1>
      <p>Avanza hacia la derecha, cambia de carril y esquiva cada obstáculo hasta la meta.</p>

      <div className={`quiz-pista quiz-pista-horizontal ${estado.blocked ? 'bloqueada' : ''} ${estado.collision ? 'colision' : ''} ${estado.completed ? 'completada' : ''}`}>
        <div className="quiz-pista-cielo" aria-hidden="true"><i /><i /><i /></div>
        <div className="quiz-carretera" aria-hidden="true">
          <span className="quiz-carril quiz-carril-1" />
          <span className="quiz-carril quiz-carril-2" />
          {obstacles.map((obstacle, index) => (
            <span
              key={obstacle.id}
              className={`quiz-obstaculo-ruta obstaculo-${index + 1} carril-${obstacle.lane} ${estado.progress > obstacle.progress ? 'superado' : ''}`}
              style={{ '--obstaculo-x': `${4 + obstacle.progress * .86}%` }}
            >
              <i /><b>{index % 2 === 0 ? '⚠' : '×'}</b><i />
            </span>
          ))}
          <span className={`quiz-meta-ruta carril-${targetLane}`}><i /><b>META</b></span>
          <span
            className={`quiz-auto-ruta carril-${estado.lane}`}
            style={{ '--auto-x': avanceHorizontal }}
          >
            <i className="quiz-auto-estela" />
            <img src={carritoRevo} alt="Auto REVO" />
          </span>
        </div>
        <div
          className="quiz-ruta-progreso"
          role="progressbar"
          aria-label="Avance de la ruta"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={estado.progress}
        >
          <span><i style={{ width: `${estado.progress}%` }} /></span>
          <b>{estado.progress}%</b>
        </div>
        <div className="quiz-impactos-ruta" aria-label={`${estado.hits} choques`}>
          <span>Impactos</span><b>{estado.hits}</b>
        </div>
      </div>

      <div className="quiz-controles-ruta" role="group" aria-label="Controles del auto">
        <button
          type="button"
          className="arriba"
          onClick={() => conducir('up')}
          aria-label="Mover al carril superior"
        >
          ↑<small>Subir</small>
        </button>
        <button
          type="button"
          className="frenar"
          onPointerDown={() => iniciarControl('left')}
          onPointerUp={detenerControl}
          onPointerCancel={detenerControl}
          onPointerLeave={detenerControl}
          onClick={(event) => { if (event.detail === 0) conducir('left') }}
          aria-label="Frenar o retroceder"
        >
          ←<small>Frenar</small>
        </button>
        <button
          type="button"
          className="acelerar"
          onPointerDown={() => iniciarControl('right')}
          onPointerUp={detenerControl}
          onPointerCancel={detenerControl}
          onPointerLeave={detenerControl}
          onClick={(event) => { if (event.detail === 0) conducir('right') }}
          aria-label="Acelerar hacia la meta"
        >
          →<small>Acelerar</small>
        </button>
        <button type="button" className="abajo" onClick={() => conducir('down')} aria-label="Mover al carril inferior">↓<small>Bajar</small></button>
      </div>
      <p className="quiz-ruta-estado" role="status" aria-live="polite">{estadoTexto}</p>
      <p className="quiz-ruta-teclas">Teclado: <kbd>←</kbd><kbd>↑</kbd><kbd>↓</kbd><kbd>→</kbd> o <kbd>WASD</kbd></p>
    </MotionDiv>
  )
}

const CARTAS_DE_LA_MANO = [
  { arte: cartaRevoExplora, nombre: 'Explora' },
  { arte: cartaRevoConecta, nombre: 'Conecta' },
  { arte: cartaRevoAnaliza, nombre: 'Analiza' },
  { arte: cartaRevoConstruye, nombre: 'Construye' },
  { arte: cartaRevoVision, nombre: 'Imagina' },
]
const RECURSOS_MINIJUEGO = [
  manoRepartiendoRevo,
  manoSueltaRevo,
  personaSelectorMinijuego,
  personaRutaGaming,
  carritoRevo,
  ...CARTAS_DE_LA_MANO.map((carta) => carta.arte),
]

function ManoPreguntas({ estado, elegida, onElegir, fase, reduceMotion }) {
  const lista = estado === 'barajando'
    ? 'Barajando las próximas señales'
    : estado === 'revelando'
      ? `Revelando la carta ${elegida + 1}`
      : 'La mano está lista. Elige una carta'

  return (
    <MotionDiv
      key="mano-preguntas"
      className="quiz-robo"
      initial={{ opacity: 0, y: reduceMotion ? 0 : 18 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: reduceMotion ? 0 : -14, scale: reduceMotion ? 1 : .98 }}
      transition={{ duration: reduceMotion ? .1 : .35, ease: [0.22, 1, 0.36, 1] }}
    >
      <span className="quiz-robo-ronda">Minijuego 01 · Ronda {fase}</span>
      <h1>Elige tu próxima pregunta</h1>
      <p>Cada carta guarda una señal diferente. Confía en tu primera elección.</p>

      <div
        className={`quiz-mano ${estado}`}
        role="group"
        aria-label="Mano de cinco cartas de preguntas"
      >
        <span className="quiz-mano-real" aria-hidden="true">
          <img className="quiz-mano-con-cartas" src={manoRepartiendoRevo} alt="" decoding="async" />
          <img className="quiz-mano-suelta" src={manoSueltaRevo} alt="" decoding="async" />
        </span>

        {CARTAS_DE_LA_MANO.map((carta, i) => (
          <button
            key={carta.nombre}
            type="button"
            className={`quiz-carta-pregunta ${elegida === i ? 'elegida' : ''}`}
            style={{
              '--i': i,
              '--abanico': `${(i - 2) * 5.5}deg`,
              '--alto-mano': `${Math.abs(i - 2) * 8}px`,
              '--apila-x': `${(2 - i) * 94}%`,
              '--apila-giro': `${(i - 2) * .8}deg`,
            }}
            disabled={estado !== 'lista'}
            onClick={() => onElegir(i)}
            aria-label={`Elegir carta ${i + 1}, ${carta.nombre}`}
          >
            <span className="quiz-reverso-carta" aria-hidden="true">
              <img src={carta.arte} alt="" decoding="async" />
              <i />
              <b>R</b>
              <small>{carta.nombre}</small>
            </span>
          </button>
        ))}
      </div>

      <p className="quiz-robo-estado" role="status" aria-live="polite">{lista}</p>
    </MotionDiv>
  )
}

export default function Questionnaire() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [answers, setAnswers] = useState({})
  const [current, setCurrent] = useState(0)
  const [phase, setPhase] = useState(1)
  const [phase3Answers, setPhase3Answers] = useState({})
  const [phase3Current, setPhase3Current] = useState(0)
  const [phase3Questions, setPhase3Questions] = useState(FASE3_RESERVA)

  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  const [error, setError] = useState('')
  const [manoEstado, setManoEstado] = useState('barajando')
  const [manoElegida, setManoElegida] = useState(null)
  const [manoPreguntaId, setManoPreguntaId] = useState(null)
  const [miniGame, setMiniGame] = useState(null)
  const [miniGameStage, setMiniGameStage] = useState('selecting')
  const [rutaPreguntaId, setRutaPreguntaId] = useState(null)
  const cardRef = useRef(null)
  const questionHeadingRef = useRef(null)
  const shuffleTimerRef = useRef(null)
  const revealTimerRef = useRef(null)
  const miniGameTimerRef = useRef(null)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    const precargas = RECURSOS_MINIJUEGO.map((src) => {
      const imagen = new Image()
      imagen.src = src
      return imagen
    })
    return () => precargas.forEach((imagen) => { imagen.src = '' })
  }, [])

  useEffect(() => {
    if (!user) return

    let active = true
    const minimumDelay = new Promise((resolve) => setTimeout(resolve, CARGA_INICIAL_MIN_MS))

    const iniciarPartida = async () => {
      try {
        const sRes = await surveyApi.createSession()
        if (!active) return

        const sid = sRes.data.id
        setSessionId(sid)
        const qRes = await surveyApi.getSessionQuestions(sid)
        if (active) setQuestions(qRes.data)
      } catch {
        if (active) setError('No se pudo iniciar el cuestionario. Revisa tu conexión.')
      } finally {
        await minimumDelay
        if (active) setLoading(false)
      }
    }

    iniciarPartida()
    return () => { active = false }
  }, [user])

  useEffect(() => {
    clearTimeout(miniGameTimerRef.current)
    if (miniGameStage !== 'selecting') return undefined

    miniGameTimerRef.current = setTimeout(() => {
      const previousGame = sessionStorage.getItem('revo_last_minigame')
      const selectedGame = chooseQuestionnaireMiniGame(Math.random(), previousGame)
      sessionStorage.setItem('revo_last_minigame', selectedGame)
      setMiniGame(selectedGame)
      setMiniGameStage('selected')
    }, reduceMotion ? 350 : 3200)

    return () => clearTimeout(miniGameTimerRef.current)
  }, [miniGameStage, reduceMotion])

  const loadPhase2 = async (sid) => {
    const transitionStartedAt = Date.now()
    setTransitioning(true)
    try {
      const qRes = await surveyApi.getSessionQuestions(sid)
      setQuestions(qRes.data)
      setCurrent(0)
      setPhase(2)
    } catch {
      setError('Error al cargar las preguntas de la fase 2.')
    } finally {
      const remainingMs = getRemainingPhaseTransitionMs(Date.now() - transitionStartedAt)
      if (remainingMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, remainingMs))
      }
      setTransitioning(false)
    }
  }

  const triggerPhase3 = async (specName, specId) => {
    let qs = null
    if (specId) {
      try {
        const res = await surveyApi.getPsychometricQuestions(specId)
        if (res.data && res.data.length > 0) {
          qs = res.data.map((q) => ({
            id: `p3_db_${q.id}`,
            question: q.question_text,
            options: [
              { key: 'A', text: q.option_a },
              { key: 'B', text: q.option_b },
              { key: 'C', text: q.option_c },
              { key: 'D', text: q.option_d },
            ],
          }))
        }
      } catch (e) {
        console.warn('Preguntas psicométricas no disponibles, usando la reserva local', e)
      }
    }
    if (!qs) qs = FASE3_RESERVA
    setPhase3Questions(qs)
    setPhase(3)
    setPhase3Current(0)
    setPhase3Answers({})
  }

  const q = questions[current]
  const total = questions.length
  const isAnswered = q && answers[q.id] !== undefined
  const isLast = current === total - 1
  const preguntaFase3 = phase3Questions[phase3Current]
  const preguntaActivaId = phase === 3 ? preguntaFase3?.id : q?.id
  const preguntaActivaRespondida = phase === 3
    ? preguntaFase3 && phase3Answers[preguntaFase3.id] !== undefined
    : q && answers[q.id] !== undefined
  const estadoActivoMano = manoPreguntaId === preguntaActivaId
    ? manoEstado
    : preguntaActivaRespondida ? 'pregunta' : 'barajando'
  const manoElegidaActiva = manoPreguntaId === preguntaActivaId ? manoElegida : null
  const rutaActivaCompletada = rutaPreguntaId === preguntaActivaId || preguntaActivaRespondida
  const preguntaVisible = miniGame === MINI_GAMES.ROAD
    ? rutaActivaCompletada
    : estadoActivoMano === 'pregunta'

  useEffect(() => {
    clearTimeout(shuffleTimerRef.current)
    clearTimeout(revealTimerRef.current)
    if (miniGame !== MINI_GAMES.CARDS || miniGameStage !== 'playing') return undefined
    if (!shouldStartQuestionShuffle({
      loading,
      submitting,
      transitioning,
      questionId: preguntaActivaId,
      answered: preguntaActivaRespondida,
    })) return

    shuffleTimerRef.current = setTimeout(
      () => {
        setManoPreguntaId(preguntaActivaId)
        setManoElegida(null)
        setManoEstado('lista')
      },
      reduceMotion ? 80 : 1350,
    )

    return () => {
      clearTimeout(shuffleTimerRef.current)
      clearTimeout(revealTimerRef.current)
    }
  }, [loading, miniGame, miniGameStage, preguntaActivaId, preguntaActivaRespondida, reduceMotion, submitting, transitioning])

  const elegirCartaPregunta = (indice) => {
    if (miniGame !== MINI_GAMES.CARDS || miniGameStage !== 'playing') return
    if (estadoActivoMano !== 'lista' || !preguntaActivaId) return
    clearTimeout(revealTimerRef.current)
    setManoPreguntaId(preguntaActivaId)
    setManoElegida(indice)
    setManoEstado('revelando')
    revealTimerRef.current = setTimeout(() => {
      setManoEstado('pregunta')
      requestAnimationFrame(() => questionHeadingRef.current?.focus())
    }, reduceMotion ? 100 : 720)
  }

  const completarRutaPregunta = (questionId) => {
    if (!questionId) return
    setRutaPreguntaId(questionId)
    requestAnimationFrame(() => questionHeadingRef.current?.focus())
  }

  const setAnswer = (val) => setAnswers((a) => ({ ...a, [q.id]: val }))

  const next = async () => {
    if (!isAnswered) return
    surveyApi.saveAnswers(sessionId, {
      answers: [{ question_id: q.id, value: answers[q.id] }],
    }).catch(console.error)

    if (isLast) {
      setSubmitting(true)
      setError('')
      try {
        const todas = questions.map((q2) => ({ question_id: q2.id, value: answers[q2.id] || 3 }))
        await surveyApi.saveAnswers(sessionId, { answers: todas })
      } catch (e) {
        console.warn('El guardado masivo falló, se continúa con el envío', e)
      }

      const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

      const submitWithRetry = async (maxRetries = 3) => {
        for (let intento = 1; intento <= maxRetries; intento++) {
          try {
            const { data: t } = await surveyApi.submitPhase(sessionId)

            if (t.next_phase === 2) {
              setSubmitting(false)
              loadPhase2(sessionId)
              return
            }
            if (t.prediction_id) {
              setSubmitting(false)
              sessionStorage.setItem('revo_pending_result', t.prediction_id)
              sessionStorage.setItem('revo_winning_spec', t.primary_specialization || '')
              triggerPhase3(t.primary_specialization || '', t.primary_specialization_id || null)
              return
            }
            if (t.error && intento < maxRetries) {
              const s = intento * 10
              setError(`El servicio está despertando. Reintentando en ${s}s (${intento}/${maxRetries})`)
              await sleep(s * 1000)
              setError('')
            } else if (t.error) {
              setError('')
              setSubmitting(false)
              sessionStorage.removeItem('revo_pending_result')
              triggerPhase3('', null)
              return
            } else {
              setError('Respuesta inesperada del servidor. Intenta de nuevo.')
              setSubmitting(false)
              return
            }
          } catch {
            if (intento < maxRetries) {
              const s = intento * 10
              setError(`Conexión lenta. Reintentando en ${s}s (${intento}/${maxRetries})`)
              await sleep(s * 1000)
              setError('')
            } else {
              setError('No se pudo conectar. Comprueba que los servicios estén corriendo.')
              setSubmitting(false)
            }
          }
        }
      }
      await submitWithRetry()
    } else {
      if (cardRef.current) cardRef.current.dataset.saliendo = 'si'
      setTimeout(() => {
        setCurrent((c) => c + 1)
        if (cardRef.current) delete cardRef.current.dataset.saliendo
      }, 160)
    }
  }

  const prev = () => { if (current > 0) setCurrent((c) => c - 1) }

  // ── Atajos de teclado ────────────────────────────────────
  // Con 25 preguntas, responder con el teclado ahorra minutos
  // frente a apuntar y hacer clic en cada una.
  const enFase12 = !loading && !submitting && !transitioning && phase !== 3 && !!q
  const manejarTecla = useEffectEvent((e) => {
    if (loading || submitting || transitioning || miniGameStage !== 'playing' || !preguntaActivaId) return
    if (e.target.matches('input, textarea, select')) return

    if (!preguntaVisible) {
      if (miniGame === MINI_GAMES.CARDS && estadoActivoMano === 'lista' && e.key >= '1' && e.key <= '5') {
        e.preventDefault()
        elegirCartaPregunta(Number(e.key) - 1)
      }
      return
    }

    if (!enFase12) return

    if (e.key >= '1' && e.key <= '5') {
      e.preventDefault()
      setAnswers((a) => ({ ...a, [q.id]: Number(e.key) }))
    } else if (e.key === 'ArrowRight' || e.key === 'Enter') {
      if (answers[q.id] !== undefined) { e.preventDefault(); next() }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault(); prev()
    }
  })

  useEffect(() => {
    const onKeyDown = (event) => manejarTecla(event)
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const entryView = resolveQuestionnaireEntryView({
    stage: miniGameStage,
    miniGame,
    loading,
    hasQuestion: phase === 3 ? !!preguntaFase3 : !!q,
  })

  // ── Pantallas de espera ──────────────────────────────────
  if (entryView === 'selector' || entryView === 'selected') {
    return (
      <SelectorMinijuego
        reduceMotion={reduceMotion}
        miniGame={miniGame}
        loading={loading}
        ready={phase === 3 ? !!preguntaFase3 : !!q}
        error={error}
        onPlay={() => setMiniGameStage('intro')}
      />
    )
  }

  if (entryView === 'intro') {
    return (
      <IntroduccionMinijuego
        miniGame={miniGame}
        reduceMotion={reduceMotion}
        onStart={() => setMiniGameStage('playing')}
      />
    )
  }

  if (submitting) {
    const textos = {
      1: ['Analizando tus respuestas', 'Buscamos las tres ramas que mejor encajan contigo.'],
      2: ['Calculando tu perfil', 'Combinamos todo lo que respondiste para generar la recomendación.'],
      3: ['Cerrando tu resultado', 'Un momento más.'],
    }
    const [t, s] = textos[phase] || textos[2]
    return <Pantalla titulo={t} texto={s} aviso={error}
      imagen={miniGame === MINI_GAMES.ROAD ? personaRutaGaming : personaDiferenciaGaming}
      etiqueta={miniGame === MINI_GAMES.ROAD ? 'Leyendo tu recorrido' : 'Leyendo tu jugada'} />
  }

  if (transitioning) {
    return <Pantalla titulo="Nueva ronda desbloqueada"
      texto={miniGame === MINI_GAMES.ROAD
        ? 'Ya encontramos señal. La siguiente etapa abre una ruta hacia tus tres ramas más prometedoras.'
        : 'Ya encontramos señal. Ahora el mazo se concentra en tus tres ramas más prometedoras.'}
      imagen={miniGame === MINI_GAMES.ROAD ? personaRutaGaming : personaCelularGaming}
      etiqueta="Fase 2: Afina" />
  }

  if (entryView === 'error' || (phase !== 3 && !q)) {
    return <Pantalla titulo="No pudimos repartir las cartas"
      texto="Revisa tu conexión y vuelve a cargar la página para intentarlo otra vez."
      aviso={error || 'El cuestionario no recibió preguntas.'}
      imagen={personaDiferenciaGaming} etiqueta="Partida interrumpida" />
  }

  // ── FASE 3: perfil profesional ───────────────────────────
  if (phase === 3) {
    const p3q = preguntaFase3
    const p3Sel = phase3Answers[p3q?.id]
    const p3Total = phase3Questions.length
    const p3Ultima = phase3Current === p3Total - 1

    const elegir = (key) => setPhase3Answers((prev) => ({ ...prev, [p3q.id]: key }))

    const siguienteP3 = () => {
      if (!p3Sel) return
      if (p3Ultima) {
        setSubmitting(true)
        const finales = { ...phase3Answers, [p3q.id]: p3Sel }
        sessionStorage.setItem('revo_archetype', JSON.stringify(calcArchetype(finales)))
        const pendiente = sessionStorage.getItem('revo_pending_result')
        setTimeout(() => navigate(`/results/${pendiente}`), 3500)
      } else {
        setPhase3Current((c) => c + 1)
      }
    }

    return (
      <div className="rv quiz" style={{ '--cat': '#D9B35B' }}>
        <Ambiente />
        <div className="quiz-lienzo">
          <FaseHud fase={3} actual={phase3Current + 1} total={p3Total} miniGame={miniGame} />

          <main className="quiz-mesa">
            <PanelMazo fase={3} items={phase3Questions} respuestas={phase3Answers} actual={phase3Current} miniGame={miniGame} />

            {p3q && (
              <section key={p3q.id} className="quiz-carta quiz-carta-final rv-entra" style={{ animationDelay: '.05s' }}>
                <div className="quiz-carta-borde" aria-hidden="true" />
                <AnimatePresence mode="wait" initial={false}>
                  {!preguntaVisible ? (
                    miniGame === MINI_GAMES.ROAD ? (
                      <RutaPreguntas
                        key={`ruta-${p3q.id}`}
                        questionIndex={phase3Current}
                        fase={3}
                        reduceMotion={reduceMotion}
                        onLlegar={() => completarRutaPregunta(p3q.id)}
                      />
                    ) : (
                      <ManoPreguntas
                        key={`mano-${p3q.id}`}
                        estado={estadoActivoMano}
                        elegida={manoElegidaActiva}
                        onElegir={elegirCartaPregunta}
                        fase={3}
                        reduceMotion={reduceMotion}
                      />
                    )
                  ) : (
                    <MotionDiv
                      key={`pregunta-${p3q.id}`}
                      className="quiz-contenido-pregunta"
                      initial={{ opacity: 0, y: reduceMotion ? 0 : 18, scale: reduceMotion ? 1 : .985 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: reduceMotion ? .1 : .38, ease: [0.22, 1, 0.36, 1] }}
                    >
                      <div className="quiz-carta-cab">
                        <span className="quiz-sello"><b>PR</b> Perfil profesional</span>
                        <span className="quiz-instruccion">Elige una carta</span>
                      </div>

                      <h1 ref={questionHeadingRef} tabIndex="-1" className="quiz-pregunta">{p3q.question}</h1>

                      <div className="quiz-ops" role="radiogroup" aria-label="Opciones de perfil profesional">
                        {p3q.options.map((opt, i) => (
                          <button key={opt.key} type="button" role="radio"
                            aria-checked={p3Sel === opt.key}
                            onClick={() => elegir(opt.key)}
                            style={{ '--i': i }}
                            className={`quiz-op ${p3Sel === opt.key ? 'sel' : ''}`}>
                            <span className="quiz-op-letra" aria-hidden="true">{opt.key}</span>
                            <span className="quiz-op-txt">{opt.text}</span>
                            <span className="quiz-op-confirmacion" aria-hidden="true">Elegida</span>
                          </button>
                        ))}
                      </div>

                      <nav className="quiz-nav" aria-label="Navegación del cuestionario">
                        <button onClick={() => phase3Current > 0 && setPhase3Current((c) => c - 1)}
                          disabled={phase3Current === 0} className="quiz-btn quiz-btn-sec">
                          <span aria-hidden="true">←</span> Anterior
                        </button>
                        <button onClick={siguienteP3} disabled={!p3Sel} className="quiz-btn quiz-btn-pri">
                          {p3Ultima ? 'Revelar mi perfil' : miniGame === MINI_GAMES.ROAD ? 'Continuar la ruta' : 'Jugar esta carta'} <span aria-hidden="true">→</span>
                        </button>
                      </nav>
                    </MotionDiv>
                  )}
                </AnimatePresence>
              </section>
            )}
          </main>
        </div>
      </div>
    )
  }

  // ── FASES 1 y 2 ──────────────────────────────────────────
  const cat = CATEGORIAS[q?.category] || {}
  const color = cat.color || COLOR_BASE

  return (
    <div className="rv quiz" style={{ '--cat': color }}>
      <Ambiente />

      <div className="quiz-lienzo">
        <FaseHud fase={phase} actual={current + 1} total={total} miniGame={miniGame} />

        <main className="quiz-mesa">
          <PanelMazo fase={phase} items={questions} respuestas={answers} actual={current} miniGame={miniGame} />

        {q && (
          <section ref={cardRef} className="quiz-carta" key={q.id}>
            <div className="quiz-carta-borde" aria-hidden="true" />
            <AnimatePresence mode="wait" initial={false}>
              {!preguntaVisible ? (
                miniGame === MINI_GAMES.ROAD ? (
                  <RutaPreguntas
                    key={`ruta-${q.id}`}
                    questionIndex={current}
                    fase={phase}
                    reduceMotion={reduceMotion}
                    onLlegar={() => completarRutaPregunta(q.id)}
                  />
                ) : (
                  <ManoPreguntas
                    key={`mano-${q.id}`}
                    estado={estadoActivoMano}
                    elegida={manoElegidaActiva}
                    onElegir={elegirCartaPregunta}
                    fase={phase}
                    reduceMotion={reduceMotion}
                  />
                )
              ) : (
                <MotionDiv
                  key={`pregunta-${q.id}`}
                  className="quiz-contenido-pregunta"
                  initial={{ opacity: 0, y: reduceMotion ? 0 : 18, scale: reduceMotion ? 1 : .985 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: reduceMotion ? .1 : .38, ease: [0.22, 1, 0.36, 1] }}
                >
                  <div className="quiz-carta-cab">
                  {cat.label && (
                    <span className="quiz-sello">
                      <b aria-hidden="true">{cat.icon}</b> {cat.label}
                    </span>
                  )}
                    <span className="quiz-instruccion">Elige tu nivel</span>
                  </div>

                  <h1 ref={questionHeadingRef} tabIndex="-1" className="quiz-pregunta">{q.text}</h1>

                  {error && <p className="quiz-error" role="alert">{error}</p>}

                  <div className="quiz-escala" role="radiogroup" aria-label="Qué tanto te representa">
                    {ESCALA.map(({ v, corta, larga }, i) => (
                      <button key={v} type="button" role="radio" data-v={v}
                        aria-checked={answers[q.id] === v}
                        aria-label={`${v} de 5: ${larga}`}
                        onClick={() => setAnswer(v)}
                        style={{
                          '--i': i,
                          '--spread': `${Math.abs(2 - i) * 4}px`,
                          '--rotation': `${(i - 2) * 1.6}deg`,
                        }}
                        className={`quiz-op-esc ${answers[q.id] === v ? 'sel' : ''}`}>
                        <span className="quiz-esc-num" aria-hidden="true">0{v}</span>
                        <span className="quiz-arte" aria-hidden="true"><i /><i /><i /></span>
                        <span className="quiz-esc-txt"><strong>{corta}</strong><small>{larga}</small></span>
                        <span className="quiz-op-confirmacion" aria-hidden="true">Elegida</span>
                      </button>
                    ))}
                  </div>

                  <nav className="quiz-nav" aria-label="Navegación del cuestionario">
                    <button onClick={prev} disabled={current === 0} className="quiz-btn quiz-btn-sec">
                      <span aria-hidden="true">←</span> Anterior
                    </button>
                    <button onClick={next} disabled={!isAnswered} className="quiz-btn quiz-btn-pri">
                      {isLast
                        ? (phase === 1 ? 'Desbloquear fase 2' : 'Ir al perfil profesional')
                        : miniGame === MINI_GAMES.ROAD ? 'Continuar la ruta' : 'Jugar esta carta'} <span aria-hidden="true">→</span>
                    </button>
                  </nav>

                  <p className="quiz-atajos">
                    Teclado: <kbd>1</kbd><span>-</span><kbd>5</kbd> para elegir, <kbd>Enter</kbd> para jugar
                  </p>
                </MotionDiv>
              )}
            </AnimatePresence>
          </section>
        )}
        </main>
      </div>
    </div>
  )
}
