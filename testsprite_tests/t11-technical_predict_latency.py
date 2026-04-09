import asyncio
from playwright import async_api
from test_helpers import start_browser, stop_browser, login, BASE_URL

async def run_test():
    pw = None
    browser = None
    context = None
    page = None
    try:
        pw, browser, context, page = await start_browser()
        await login(page, "demo@revo.edu", "Demo@1234")
        await page.goto(f"{BASE_URL}/dashboard")

        result = await page.evaluate("async () => {\n            const token = window.localStorage.getItem('revo_token');\n            const body = {\n                session_id: 1,\n                user_id: 1,\n                feature_vector: {\n                    aff_1: 5, aff_2: 5, aff_3: 5, aff_4: 5, aff_5: 5,\n                    aff_6: 5, aff_7: 5, aff_8: 5, aff_9: 5, aff_10: 5\n                }\n            };\n            const start = performance.now();\n            const response = await fetch('/api/ml/predict/', {\n                method: 'POST',\n                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },\n                body: JSON.stringify(body),\n            });\n            const end = performance.now();\n            const data = await response.json();\n            return { ok: response.ok, ms: end - start, status: response.status, data };\n        }")

        assert result["ok"], f"Predict endpoint should respond successfully, got {result['status']}"
        assert result["ms"] < 1500, f"Predict latency exceeded 1.5s: {result['ms']} ms"
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
