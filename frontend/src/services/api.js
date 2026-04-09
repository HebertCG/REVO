import axios from 'axios'

const getToken = () => localStorage.getItem('revo_token')
const authHeader = () => ({ Authorization: `Bearer ${getToken()}` })

// En Desarrollo, usa el Proxy de Vite. En Producción, usa las variables VITE_* de Vercel/Render.
const authAxios = axios.create({ baseURL: import.meta.env.VITE_AUTH_URL || '/api/auth' })
const surveyAxios = axios.create({ baseURL: import.meta.env.VITE_SURVEY_URL || '/api/survey' })
const mlAxios = axios.create({ baseURL: import.meta.env.VITE_ML_URL || '/api/ml' })

// ── Auth Service ──────────────────────────────────────────
export const authApi = {
  register: (data) => authAxios.post('/auth/register', data),
  login:    (data) => authAxios.post('/auth/login', data),
  me:       ()     => authAxios.get('/auth/me', { headers: authHeader() }),
  verify:   ()     => authAxios.get('/auth/verify', { headers: authHeader() }),
}

// ── Survey Service ────────────────────────────────────────
export const surveyApi = {
  getQuestions:         ()          => surveyAxios.get('/questions/'),
  getSessionQuestions:  (sid)       => surveyAxios.get(`/sessions/${sid}/questions`, { headers: authHeader() }),
  getCategories:        ()          => surveyAxios.get('/questions/categories/list'),
  createSession:        ()          => surveyAxios.post('/sessions/', {}, { headers: authHeader() }),
  saveAnswers:          (sid, body) => surveyAxios.post(`/sessions/${sid}/answers`, body, { headers: authHeader() }),
  submitPhase:          (sid)       => surveyAxios.post(`/sessions/${sid}/submit_phase`, {}, { headers: authHeader() }),
  getHistory:           ()          => surveyAxios.get('/sessions/', { headers: authHeader() }),
  getSession:           (sid)       => surveyAxios.get(`/sessions/${sid}`, { headers: authHeader() }),
  getRecommendedCourses:(specId)    => surveyAxios.get(`/courses/specialization/${specId}`),
  getRecommendedJobs:   (specId)    => surveyAxios.get(`/jobs/specialization/${specId}`),
}

// ── ML Service ────────────────────────────────────────────
export const mlApi = {
  predict:       (body)  => mlAxios.post('/predict/', body, { headers: authHeader() }),
  getPrediction: (id)    => mlAxios.get(`/predict/${id}`, { headers: authHeader() }),
  getHistory:    (uid)   => mlAxios.get(`/predict/user/${uid}/history`, { headers: authHeader() }),
  importances:   ()      => mlAxios.get('/predict/model/importances', { headers: authHeader() }),
  treeViz:       ()      => mlAxios.get('/predict/model/tree', { headers: authHeader() }),
  overview:      ()      => mlAxios.get(`/stats/overview?t=${new Date().getTime()}`),
  trainingHistory:()     => mlAxios.get(`/stats/training-history?t=${new Date().getTime()}`),
  retrain:       ()      => mlAxios.post('/stats/train', {}, { headers: authHeader() }),
}
