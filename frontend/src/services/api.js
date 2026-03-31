import axios from 'axios'

const getToken = () => localStorage.getItem('revo_token')
const authHeader = () => ({ Authorization: `Bearer ${getToken()}` })

// ── Auth Service ──────────────────────────────────────────
export const authApi = {
  register: (data) => axios.post('/api/auth/auth/register', data),
  login:    (data) => axios.post('/api/auth/auth/login', data),
  me:       ()     => axios.get('/api/auth/auth/me', { headers: authHeader() }),
  verify:   ()     => axios.get('/api/auth/auth/verify', { headers: authHeader() }),
}

// ── Survey Service ────────────────────────────────────────
export const surveyApi = {
  getQuestions:         ()          => axios.get('/api/survey/questions/'),
  getSessionQuestions:  (sid)       => axios.get(`/api/survey/sessions/${sid}/questions`, { headers: authHeader() }),
  getCategories:        ()          => axios.get('/api/survey/questions/categories/list'),
  createSession:        ()          => axios.post('/api/survey/sessions/', {}, { headers: authHeader() }),
  saveAnswers:          (sid, body) => axios.post(`/api/survey/sessions/${sid}/answers`, body, { headers: authHeader() }),
  submitPhase:          (sid)       => axios.post(`/api/survey/sessions/${sid}/submit_phase`, {}, { headers: authHeader() }),
  getHistory:           ()          => axios.get('/api/survey/sessions/', { headers: authHeader() }),
  getSession:           (sid)       => axios.get(`/api/survey/sessions/${sid}`, { headers: authHeader() }),
}

// ── ML Service ────────────────────────────────────────────
export const mlApi = {
  predict:       (body)  => axios.post('/api/ml/predict/', body, { headers: authHeader() }),
  getPrediction: (id)    => axios.get(`/api/ml/predict/${id}`, { headers: authHeader() }),
  getHistory:    (uid)   => axios.get(`/api/ml/predict/user/${uid}/history`, { headers: authHeader() }),
  importances:   ()      => axios.get('/api/ml/predict/model/importances', { headers: authHeader() }),
  treeViz:       ()      => axios.get('/api/ml/predict/model/tree', { headers: authHeader() }),
  overview:      ()      => axios.get('/api/ml/stats/overview'),
  trainingHistory:()     => axios.get('/api/ml/stats/training-history'),
  retrain:       ()      => axios.post('/api/ml/stats/train', {}, { headers: authHeader() }),
}
