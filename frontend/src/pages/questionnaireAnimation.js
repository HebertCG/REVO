export const PHASE_TRANSITION_MIN_MS = 2600

export function getRemainingPhaseTransitionMs(elapsedMs) {
  const safeElapsedMs = Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs) : 0
  return Math.max(0, PHASE_TRANSITION_MIN_MS - safeElapsedMs)
}

export function shouldStartQuestionShuffle({
  loading,
  submitting,
  transitioning,
  questionId,
  answered,
}) {
  return Boolean(questionId)
    && !loading
    && !submitting
    && !transitioning
    && !answered
}
