export const ARCADE_COLUMNS = 5
export const ARCADE_ROWS = 4
export const ARCADE_ENEMY_COUNT = 6
export const ARCADE_TARGET_SCORE = ARCADE_ENEMY_COUNT
export const ARCADE_SHOT_COOLDOWN = 2
export const ARCADE_MIN_PLAY_MS = 12000

const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value))

const createArcadeEnemies = () => [0, 1].flatMap((row) => (
  [1, 2, 3].map((column) => ({ id: `enemy-${row}-${column}`, column, row }))
))

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
    completed: false,
    tick: 0,
    enemies: createArcadeEnemies(),
    enemyDirection: 1,
    enemyShots: [],
    shotsFired: 0,
    shotCooldown: 0,
    lastShot: null,
    explosion: null,
    hit: false,
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
    row: clamp(state.row + vertical, 2, ARCADE_ROWS - 1),
    hit: false,
  }
}

export function fireArcadeShot(state) {
  if (state.completed || state.shotCooldown > 0) return state

  const target = state.enemies
    .filter((enemy) => enemy.column === state.column && enemy.row < state.row)
    .sort((first, second) => second.row - first.row)[0]
  const remainingEnemies = target
    ? state.enemies.filter((enemy) => enemy.id !== target.id)
    : state.enemies
  const nextScore = state.score + (target ? 1 : 0)
  const shotsFired = state.shotsFired + 1

  return {
    ...state,
    enemies: remainingEnemies,
    score: nextScore,
    shotsFired,
    shotCooldown: ARCADE_SHOT_COOLDOWN,
    lastShot: { id: `player-${shotsFired}`, column: state.column, fromRow: state.row },
    explosion: target ? { id: target.id, column: target.column, row: target.row } : null,
    hit: false,
    completed: remainingEnemies.length === 0,
  }
}

export function advanceArcadeWave(state) {
  if (state.completed) return state

  const nextTick = state.tick + 1
  const reachesEdge = state.enemies.some((enemy) => (
    enemy.column + state.enemyDirection < 0
    || enemy.column + state.enemyDirection >= ARCADE_COLUMNS
  ))
  const nextDirection = reachesEdge ? -state.enemyDirection : state.enemyDirection
  const movedEnemies = state.enemies.map((enemy) => ({
    ...enemy,
    column: enemy.column + nextDirection,
  }))

  const movedEnemyShots = state.enemyShots
    .map((shot) => ({ ...shot, row: shot.row + 1 }))
    .filter((shot) => shot.row < ARCADE_ROWS)
  const collided = movedEnemyShots.some((shot) => (
    shot.column === state.column && shot.row === state.row
  ))
  const survivingShots = collided
    ? movedEnemyShots.filter((shot) => shot.column !== state.column || shot.row !== state.row)
    : movedEnemyShots

  if (nextTick % 2 === 0 && movedEnemies.length > 0) {
    const shooter = movedEnemies[nextTick % movedEnemies.length]
    survivingShots.push({
      id: `enemy-shot-${nextTick}`,
      column: shooter.column,
      row: shooter.row,
    })
  }

  const needsAssist = collided && state.shield <= 1
  return {
    ...state,
    tick: nextTick,
    enemies: movedEnemies,
    enemyDirection: nextDirection,
    enemyShots: survivingShots,
    shield: collided ? Math.max(1, state.shield - 1) : state.shield,
    hits: state.hits + (collided ? 1 : 0),
    assist: state.assist || needsAssist,
    shotCooldown: Math.max(0, state.shotCooldown - 1),
    lastShot: null,
    explosion: null,
    hit: collided,
  }
}
