import { test, expect } from '@playwright/test'

const USUARIO = {
  id: 42,
  email: 'alumna@revo.edu',
  full_name: 'Alumna REVO',
  role: 'student',
  is_active: true,
}

const preguntas = (desde) => [0, 1].map((indice) => ({
  id: desde + indice,
  text: `Pregunta ${desde + indice}`,
  category: 'programming',
  question_type: 'likert',
  min_label: 'Nada',
  max_label: 'Mucho',
  weight: 1,
  order_index: indice + 1,
}))

test('el minijuego aparece una sola vez al inicio de cada fase', async ({ page }) => {
  const preguntasPorFase = [preguntas(1), preguntas(101)]
  let cargaDePreguntas = 0
  let faseEnviada = 0
  const rutasNoSimuladas = []

  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.addInitScript(() => {
    sessionStorage.setItem('revo_token', 'token-de-prueba')
    sessionStorage.setItem('revo_last_minigame', 'arcade')
    Math.random = () => 0.1
  })

  await page.route('**/api/**', async (route, request) => {
    const ruta = new URL(request.url()).pathname
    const metodo = request.method()

    if (ruta === '/api/auth/me' && metodo === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(USUARIO) })
    }
    if (ruta === '/api/sessions/' && metodo === 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 777 }) })
    }
    if (ruta === '/api/sessions/777/questions' && metodo === 'GET') {
      const cuerpo = preguntasPorFase[Math.min(cargaDePreguntas, preguntasPorFase.length - 1)]
      cargaDePreguntas += 1
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(cuerpo) })
    }
    if (ruta === '/api/sessions/777/answers' && metodo === 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ saved: true }) })
    }
    if (ruta === '/api/sessions/777/submit_phase' && metodo === 'POST') {
      faseEnviada += 1
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(faseEnviada === 1
          ? { next_phase: 2 }
          : { prediction_id: 99, primary_specialization: 'Software', primary_specialization_id: 7 }),
      })
    }
    if (ruta === '/api/psychometric/specialization/7' && metodo === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 501,
          question_text: 'Pregunta de perfil 501',
          option_a: 'Opción A',
          option_b: 'Opción B',
          option_c: 'Opción C',
          option_d: 'Opción D',
        }]),
      })
    }

    rutasNoSimuladas.push(`${metodo} ${ruta}`)
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })

  await page.goto('/questionnaire')
  await page.getByRole('button', { name: 'Jugar' }).click()
  await page.getByRole('button', { name: /repartir cartas/i }).click()

  const mano = page.locator('.quiz-robo')
  await expect(mano).toBeVisible()
  await page.locator('.quiz-carta-pregunta').first().click()
  await expect(page.getByRole('heading', { name: 'Pregunta 1' })).toBeVisible()

  await page.locator('.quiz-escala button[data-v="3"]').click()
  await page.getByRole('button', { name: /siguiente pregunta/i }).click()

  await expect(page.getByRole('heading', { name: 'Pregunta 2' })).toBeVisible()
  await expect(mano).toHaveCount(0)

  await page.locator('.quiz-escala button[data-v="4"]').click()
  await page.getByRole('button', { name: /desbloquear fase 2/i }).click()

  await expect(page.locator('.quiz-fases')).toHaveAttribute('aria-label', 'Fase 2 de 3', { timeout: 15_000 })
  await expect(mano).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Pregunta 101' })).toHaveCount(0)

  await page.locator('.quiz-carta-pregunta').first().click()
  await expect(page.getByRole('heading', { name: 'Pregunta 101' })).toBeVisible()
  await page.locator('.quiz-escala button[data-v="2"]').click()
  await page.getByRole('button', { name: /siguiente pregunta/i }).click()

  await expect(page.getByRole('heading', { name: 'Pregunta 102' })).toBeVisible()
  await expect(mano).toHaveCount(0)
  await page.locator('.quiz-escala button[data-v="5"]').click()
  await page.getByRole('button', { name: /ir al perfil profesional/i }).click()

  await expect(page.locator('.quiz-fases')).toHaveAttribute('aria-label', 'Fase 3 de 3', { timeout: 15_000 })
  await expect(mano).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Pregunta de perfil 501' })).toHaveCount(0)
  expect(rutasNoSimuladas).toEqual([])
})
