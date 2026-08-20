export function buildHistorySeries(history, formatDate = (value) => value) {
  return [...history].reverse().map((item, index) => ({
    id: item.prediction_id,
    n: index + 1,
    confidence: Number(item.confidence_pct) || 0,
    specialization: item.specialization,
    createdAt: item.created_at,
    date: formatDate(item.created_at),
  }))
}

export function buildHistorySummary(history) {
  if (!history.length) {
    return {
      total: 0,
      average: 0,
      latestConfidence: 0,
      delta: 0,
      trend: 'steady',
    }
  }

  const confidenceValues = history.map((item) => Number(item.confidence_pct) || 0)
  const latestConfidence = confidenceValues[0]
  const oldestConfidence = confidenceValues.at(-1)
  const delta = Number((latestConfidence - oldestConfidence).toFixed(1))

  return {
    total: history.length,
    average: Math.round(
      confidenceValues.reduce((total, value) => total + value, 0) / history.length,
    ),
    latestConfidence,
    delta,
    trend: delta > 0 ? 'up' : delta < 0 ? 'down' : 'steady',
  }
}
