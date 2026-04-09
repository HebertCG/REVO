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
        await page.goto(f"{BASE_URL}/questionnaire")
        await page.wait_for_selector('button.scale-btn', timeout=15000)

        for _ in range(5):
            await page.locator('button.scale-btn').nth(4).click()
            await page.get_by_role("button", name="Siguiente →").click()

        await page.evaluate("() => window.location.reload()")
        await page.wait_for_selector('button.scale-btn', timeout=15000)
        selected_count = await page.locator('button.scale-btn.selected').count()
        assert selected_count >= 5, f"Expected persisted answers after refresh, found {selected_count} selected buttons"
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
