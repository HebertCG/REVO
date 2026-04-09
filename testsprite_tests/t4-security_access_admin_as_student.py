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
        await page.goto(f"{BASE_URL}/admin")
        await page.wait_for_url(f"{BASE_URL}/dashboard", timeout=10000)
        assert page.url.startswith(f"{BASE_URL}/dashboard"), "Student user should be redirected away from /admin"
    finally:
        await stop_browser(pw, browser, context)

asyncio.run(run_test())
