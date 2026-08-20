export const ARCADE_COLUMNS = 5
export const ARCADE_ROWS = 4
export const ARCADE_TARGET_SCORE = 12
export const ARCADE_PULSE_COOLDOWN = 5
export const ARCADE_MIN_PLAY_MS = 12000

const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value))

export function getArcadeRemainingPlayMs(elapsedMs) {
  return Math.max(0, ARCADE_MIN_PLAY_MS - Math.max(0, elapsedMs))
}

export function createArcadeState() {
  return {
    column: 2,
    row: 3,
    score: 0,
    shield: 3,
    hits: 0,
    assist: false,
    pulseCooldown: 0,
    pulseActive: false,
    hit: false,
    completed: false,
  }
}

export function moveArcadeShip(state, action) {
  if (state.completed) return state

  const horizontal = action === 'left' ? -1 : action === 'right' ? 1 : 0
  const vertical = action === 'up' ? -1 : action === 'down' ? 1 : 0
  if (!horizontal && !vertical) return state

  return {
    ...state,
    column: clamp(state.column + horizontal, 0, ARCADE_COLUMNS - 1),
    row: clamp(state.row + vertical, 0, ARCADE_ROWS - 1),
    hit: false,
  }
}

export function getArcadeThreats(questionIndex, tick) {
  const patternOffset = (Math.max(0, questionIndex) * 2 + Math.max(0, tick)) % ARCADE_COLUMNS
  return [
    { column: patternOffset, row: 2 + (tick % 2) },
    { column: (patternOffset + 2) % ARCADE_COLUMNS, row: 1 + ((tick + 1) % 3) },
  ]
}

export function activateArcadePulse(state) {
  if (state.completed || state.pulseCooldown > 0) return state
  return {
    ...state,
    pulseActive: true,
    pulseCooldown: ARCADE_PULSE_COOLDOWN,
    hit: false,
  }
}

export function advanceArcadeWave(state, threats) {
  if (state.completed) return state

  const collided = !state.pulseActive && threats.some((threat) => (
    threat.column === state.column && threat.row === state.row
  ))
  const nextScore = Math.min(ARCADE_TARGET_SCORE, state.score + 1)
  const needsAssist = collided && state.shield <= 1

  return {
    ...state,
    score: nextScore,
    shield: collided ? Math.max(1, state.shield - 1) : state.shield,
    hits: state.hits + (collided ? 1 : 0),
    assist: state.assist || needsAssist,
    pulseCooldown: Math.max(0, state.pulseCooldown - 1),
    pulseActive: false,
    hit: collided,
    completed: nextScore === ARCADE_TARGET_SCORE,
  }
}
