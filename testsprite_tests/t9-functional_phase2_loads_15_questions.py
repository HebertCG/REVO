import asyncio
import json
from playwright import async_api
from test_helpers import start_browser, stop_browser, login, BASE_URL

async def run_test():
    pw = None
    browser = None
    context = None
    page = None
    question_get = {"count": 0, "phase2_length": None}

    async def intercept_questions(route, request):
        question_get["count"] += 1
        response = await route.fetch()
        if request.method == "GET" and request.url.endswith("/questions") and question_get["count"] == 2:
            data = await response.json()
            question_get["phase2_length"] = len(data)
        body = await response.body()
        await route.fulfill(
            status=response.status,
            headers={k: v for k, v in response.headers.items() if k.lower() != 'content-encoding'},
            body=body,
        )

    try:
        pw, browser, context, page = await start_browser()
        await login(page, "demo@revo.edu", "Demo@1234")
        await page.route("**/api/survey/sessions/*/questions", intercept_questions)
        await page.goto(f"{BASE_URL}/questionnaire")
        await page.wait_for_selector('button.scale-btn', timeout=15000)

        for _ in range(30):
            await page.locator('button.scale-btn').nth(4).click()
            await page.get_by_role("button", name="Siguiente →").click()
            if await page.locator('text=¡Fase 2 Desbloqueada!').count() > 0:
                break

        assert question_get["phase2_length"] == 15, f"Phase 2 should load 15 questions, got {question_get['phase2_length']}"
        await page.wait_for_selector('text=¡Fase 2 Desbloqueada!', timeout=10000)
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
