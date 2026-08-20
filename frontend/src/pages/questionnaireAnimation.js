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
