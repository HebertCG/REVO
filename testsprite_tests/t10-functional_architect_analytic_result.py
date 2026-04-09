import asyncio
import json
import re
from playwright import async_api
from test_helpers import start_browser, stop_browser, login, BASE_URL

PHASE2_MOCK_QUESTIONS = [
    {"id": "mock_q1", "text": "Pregunta de profundización 1", "category": "skills", "min_label": "Muy bajo", "max_label": "Excelente"},
    {"id": "mock_q2", "text": "Pregunta de profundización 2", "category": "academic", "min_label": "Muy bajo", "max_label": "Excelente"},
    {"id": "mock_q3", "text": "Pregunta de profundización 3", "category": "interests", "min_label": "Muy bajo", "max_label": "Excelente"},
]

PREDICTION_RESPONSE = {
    "prediction_id": 12345,
    "session_id": 1,
    "primary": {
        "specialization_id": 1,
        "name": "Desarrollo de Software",
        "icon": "💻",
        "color": "#3B82F6",
        "confidence": 0.95,
        "confidence_pct": 95.0
    },
    "top3": [],
    "all_probabilities": {},
    "model_version": "1.0"
}

async def run_test():
    pw = None
    browser = None
    context = None
    page = None
    submit_count = {"count": 0}
    question_get = {"count": 0}

    async def intercept_questions(route, request):
        if request.method == "GET" and request.url.endswith("/questions"):
            question_get["count"] += 1
            if question_get["count"] == 2:
                await route.fulfill(
                    status=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps(PHASE2_MOCK_QUESTIONS)
                )
                return
        await route.continue_()

    async def intercept_submit(route, request):
        if request.method == "POST" and request.url.endswith("/submit_phase"):
            submit_count["count"] += 1
            if submit_count["count"] == 2:
                await route.fulfill(
                    status=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"prediction_id": 12345})
                )
                return
        await route.continue_()

    async def intercept_prediction(route, request):
        await route.fulfill(
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(PREDICTION_RESPONSE)
        )

    try:
        pw, browser, context, page = await start_browser()
        await login(page, "demo@revo.edu", "Demo@1234")
        await page.route("**/api/survey/sessions/*/questions", intercept_questions)
        await page.route("**/api/survey/sessions/*/submit_phase", intercept_submit)
        await page.route("**/api/ml/predict/12345", intercept_prediction)

        await page.goto(f"{BASE_URL}/questionnaire")
        await page.wait_for_selector('button.scale-btn', timeout=15000)

        for _ in range(15):
            await page.locator('button.scale-btn').nth(4).click()
            await page.get_by_role("button", name="Siguiente →").click()

        # Now the page should show phase 2 with our mocked 3 questions
        await page.wait_for_selector('text=Pregunta de profundización 1', timeout=15000)
        for _ in range(3):
            await page.locator('button.scale-btn').nth(4).click()
            await page.get_by_role("button", name="Siguiente →").click()

        # Fase 3
        await page.wait_for_selector('text=Fase 3/3', timeout=15000)
        for _ in range(4):
            await page.locator('button', has_text='A').first.click()
            await page.get_by_role("button", name=re.compile("Siguiente|Ver mi Resultado Completo")).click()

        await page.wait_for_url(f"{BASE_URL}/results/12345", timeout=15000)
        assert await page.locator('text=El Arquitecto Analítico').count() > 0, "Expected the final archetype to be Arquitecto Analítico"
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
