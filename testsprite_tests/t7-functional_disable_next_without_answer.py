import asyncio
from playwright import async_api
from playwright.async_api import expect
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
        next_btn = page.get_by_role("button", name="Siguiente →")
        await expect(next_btn).to_be_disabled()
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
