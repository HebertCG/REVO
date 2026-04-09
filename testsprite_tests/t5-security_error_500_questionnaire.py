import asyncio
import json
from playwright import async_api
from test_helpers import start_browser, stop_browser, login, BASE_URL

async def run_test():
    pw = None
    browser = None
    context = None
    page = None
    request_count = {"q_get": 0}

    async def intercept_questions(route, request):
        if "/api/survey/sessions/" in request.url and request.url.endswith("/questions"):
            request_count["q_get"] += 1
            if request_count["q_get"] == 2:
                await route.fulfill(
                    status=500,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"detail": "Error del servidor"})
                )
                return
        await route.continue_()

    try:
        pw, browser, context, page = await start_browser()
        await login(page, "demo@revo.edu", "Demo@1234")
        await page.route("**/api/survey/sessions/*/questions", intercept_questions)
        await page.goto(f"{BASE_URL}/questionnaire")

        # Responder las preguntas de Fase 1 hasta que falle la carga de Fase 2.
        for _ in range(15):
            await page.locator('button.scale-btn').nth(4).click()
            next_btn = page.get_by_role("button", name="Siguiente →")
            await next_btn.click()
            if await page.locator('text=Error al cargar preguntas avanzadas.').count():
                break

        assert await page.locator('text=Error al cargar preguntas avanzadas.').count() > 0, "Debe mostrarse un mensaje amigable de error"
        content = await page.content()
        assert "Traceback" not in content and ".py" not in content, "No debe mostrarse stack trace o rutas de servidor"
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
