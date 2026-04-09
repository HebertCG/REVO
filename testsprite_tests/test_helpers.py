import asyncio
from playwright import async_api

BASE_URL = "http://localhost:5173"
DEMO_USER = {"email": "demo@revo.edu", "password": "Demo@1234"}
ADMIN_USER = {"email": "admin@revo.edu", "password": "Admin@1234"}

async def start_browser():
    pw = await async_api.async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--window-size=1280,720",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]
    )
    context = await browser.new_context()
    page = await context.new_page()
    return pw, browser, context, page

async def stop_browser(pw, browser, context):
    if context:
        await context.close()
    if browser:
        await browser.close()
    if pw:
        await pw.stop()

async def login(page, email, password, expected_url="/dashboard"):
    await page.goto(f"{BASE_URL}/login")
    await page.locator('input[placeholder="tu@email.com"]').fill(email)
    await page.locator('input[placeholder="••••••••"]').fill(password)
    await page.get_by_role("button", name="Iniciar Sesión →").click()
    await page.wait_for_url(f"{BASE_URL}{expected_url}", timeout=15000)
