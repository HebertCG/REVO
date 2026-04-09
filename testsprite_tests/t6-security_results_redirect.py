import asyncio
from playwright import async_api
from test_helpers import start_browser, stop_browser, BASE_URL

async def run_test():
    pw = None
    browser = None
    context = None
    page = None
    try:
        pw, browser, context, page = await start_browser()
        await page.goto(BASE_URL)
        await page.evaluate("() => localStorage.removeItem('revo_token')")
        await page.goto(f"{BASE_URL}/results/1")
        await page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        assert page.url.startswith(f"{BASE_URL}/login"), "Unauthenticated users should be redirected to /login"
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
