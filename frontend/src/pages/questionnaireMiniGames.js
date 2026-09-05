export const MINI_GAMES = {
  CARDS: 'cards',
  ROAD: 'road',
  ARCADE: 'arcade',
}

const QUESTIONNAIRE_MINI_GAMES = [MINI_GAMES.CARDS, MINI_GAMES.ROAD, MINI_GAMES.ARCADE]

export const ROAD_CHECKPOINT_PROGRESS = 84
export const ROAD_ACCELERATION_STEP = 8
export const ROAD_REVERSE_STEP = 6

const ROAD_OBSTACLE_PATTERNS = [
  [{ progress: 24, lane: 1 }, { progress: 48, lane: 0 }, { progress: 72, lane: 2 }],
  [{ progress: 24, lane: 2 }, { progress: 48, lane: 1 }, { progress: 72, lane: 0 }],
  [{ progress: 24, lane: 0 }, { progress: 48, lane: 2 }, { progress: 72, lane: 1 }],
]

export function chooseQuestionnaireMiniGame(randomValue = Math.random(), previousGame = null) {
  const selectedIndex = Math.min(
    QUESTIONNAIRE_MINI_GAMES.length - 1,
    Math.floor(Math.max(0, randomValue) * QUESTIONNAIRE_MINI_GAMES.length),
  )
  const selected = QUESTIONNAIRE_MINI_GAMES[selectedIndex]
  if (selected !== previousGame) return selected
  return QUESTIONNAIRE_MINI_GAMES[(selectedIndex + 1) % QUESTIONNAIRE_MINI_GAMES.length]
}

/**
 * Decide que pantalla de entrada se pinta.
 *
 * El orden importa y antes estaba mal. La vista de error se comprobaba
 * despues del sorteo del minijuego, y a las dos ramas anteriores se llega
 * siempre que la partida no arranco: con un fallo al crear la sesion el
 * alumno se quedaba en el selector con el boton apagado, y con una sesion
 * sin preguntas se quedaba para siempre ante un boton que decia "Preparando
 * preguntas...". La pantalla de error existia, estaba maquetada, y no habia
 * forma de llegar a ella.
 *
 * Ahora el error va primero, con dos excepciones que van antes que el:
 *
 * - `busy` (enviando respuestas o cambiando de fase) pinta su propia
 *   pantalla y usa `error` para avisos temporales de reintento
 *   ("Reintentando en 10s"), que no son un final de partida.
 * - Mientras `loading` siga en pie no hay fallo que declarar: todavia no ha
 *   llegado la respuesta.
 */
export function resolveQuestionnaireEntryView({
  stage, miniGame, loading, hasQuestion, error = '', busy = false,
}) {
  if (busy) return 'ocupado'
  if (error || (!loading && !hasQuestion)) return 'error'
  if (stage === 'selecting' || !miniGame) return 'selector'
  if (stage === 'selected' || loading) return 'selected'
  if (stage === 'intro') return 'intro'
  return 'game'
}

export function getRoadTargetLane(questionIndex) {
  return Math.max(0, questionIndex) % 3
}

export function getRoadObstacles(questionIndex) {
  const pattern = ROAD_OBSTACLE_PATTERNS[Math.max(0, questionIndex) % ROAD_OBSTACLE_PATTERNS.length]
  return pattern.map((obstacle, index) => ({ ...obstacle, id: `${questionIndex}-${index}` }))
}

export function createRoadState() {
  return {
    lane: 1,
    progress: 0,
    blocked: false,
    collision: false,
    hits: 0,
    completed: false,
  }
}

export function advanceRoadState(state, action, targetLane, obstacles = []) {
  if (state.completed) return state

  if (action === 'up' || action === 'down') {
    const direction = action === 'up' ? -1 : 1
    return {
      ...state,
      lane: Math.min(2, Math.max(0, state.lane + direction)),
      blocked: false,
      collision: false,
    }
  }

  if (action === 'left' || action === 'reverse') {
    return {
      ...state,
      progress: Math.max(0, state.progress - ROAD_REVERSE_STEP),
      blocked: false,
      collision: false,
    }
  }

  if (action !== 'right' && action !== 'accelerate') return state

  const nextProgress = Math.min(100, state.progress + ROAD_ACCELERATION_STEP)
  const obstacle = obstacles.find((item) => (
    item.lane === state.lane
    && item.progress > state.progress
    && item.progress <= nextProgress
  ))
  if (obstacle) {
    return {
      ...state,
      progress: Math.max(0, obstacle.progress - 12),
      blocked: false,
      collision: true,
      hits: state.hits + 1,
    }
  }

  if (nextProgress > ROAD_CHECKPOINT_PROGRESS && state.lane !== targetLane) {
    return {
      ...state,
      progress: ROAD_CHECKPOINT_PROGRESS,
      blocked: true,
      collision: false,
    }
  }

  return {
    ...state,
    progress: nextProgress,
    blocked: false,
    collision: false,
    completed: nextProgress === 100,
  }
}
