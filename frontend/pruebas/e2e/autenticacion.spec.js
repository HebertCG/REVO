import { test, expect } from '@playwright/test'

const USUARIO = {
  id: 2,
  email: 'demo@revo.edu',
  full_name: 'Estudiante Demo',
  role: 'student',
}

const campoClave = (page) => page.locator('input[type="password"]')
const botonEnviar = (page) => page.locator('form button[type="submit"]')

test('login acepta claves existentes cortas y registro conserva su minimo', async ({ page }) => {
  const solicitudes = []

  await page.route('**/api/**', async (route, request) => {
    const ruta = new URL(request.url()).pathname
    solicitudes.push({ metodo: request.method(), ruta })

    if (ruta === '/api/auth/login' && request.method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: 'token-prueba', user: USUARIO }),
      })
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })

  await page.goto('/login')
  await expect(campoClave(page)).not.toHaveAttribute('minlength')
  await page.getByRole('textbox', { name: /correo institucional/i }).fill(USUARIO.email)
  await campoClave(page).fill('Demo@1234')
  await botonEnviar(page).click()

  await expect(page).toHaveURL(/\/dashboard$/)
  expect(solicitudes).toContainEqual({ metodo: 'POST', ruta: '/api/auth/login' })

  await page.goto('/register')
  await expect(campoClave(page)).toHaveAttribute('minlength', '10')
})

test('credenciales incorrectas no se presentan como sesion expirada', async ({ page }) => {
  await page.route('**/api/auth/login', (route) => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'Correo o contrasena incorrectos' }),
  }))

  await page.goto('/login')
  await page.getByRole('textbox', { name: /correo institucional/i }).fill('nadie@revo.edu')
  await campoClave(page).fill('ClaveIncorrecta123!')
  await botonEnviar(page).click()

  await expect(page.getByRole('alert')).toContainText('Correo o contrasena incorrectos')
  await expect(page).toHaveURL(/\/login$/)
})
