export const MINI_GAMES = {
  CARDS: 'cards',
  ROAD: 'road',
}

export const ROAD_CHECKPOINT_PROGRESS = 84
export const ROAD_ACCELERATION_STEP = 14

export function chooseQuestionnaireMiniGame(randomValue = Math.random(), previousGame = null) {
  const selected = randomValue < .5 ? MINI_GAMES.CARDS : MINI_GAMES.ROAD
  if (selected !== previousGame) return selected
  return selected === MINI_GAMES.CARDS ? MINI_GAMES.ROAD : MINI_GAMES.CARDS
}

export function resolveQuestionnaireEntryView({ stage, miniGame, loading, hasQuestion }) {
  if (stage === 'selecting' || !miniGame) return 'selector'
  if (stage === 'selected' || loading) return 'selected'
  if (!hasQuestion) return 'error'
  if (stage === 'intro') return 'intro'
  return 'game'
}

export function getRoadTargetLane(questionIndex) {
  return Math.max(0, questionIndex) % 3
}

export function createRoadState() {
  return {
    lane: 1,
    progress: 0,
    blocked: false,
    completed: false,
  }
}

export function advanceRoadState(state, action, targetLane) {
  if (state.completed) return state

  if (action === 'left' || action === 'right') {
    const direction = action === 'left' ? -1 : 1
    return {
      ...state,
      lane: Math.min(2, Math.max(0, state.lane + direction)),
      blocked: false,
    }
  }

  if (action !== 'accelerate') return state

  const nextProgress = Math.min(100, state.progress + ROAD_ACCELERATION_STEP)
  if (nextProgress > ROAD_CHECKPOINT_PROGRESS && state.lane !== targetLane) {
    return {
      ...state,
      progress: ROAD_CHECKPOINT_PROGRESS,
      blocked: true,
    }
  }

  return {
    ...state,
    progress: nextProgress,
    blocked: false,
    completed: nextProgress === 100,
  }
}
