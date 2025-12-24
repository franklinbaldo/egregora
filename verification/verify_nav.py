
import asyncio
import re
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to the home page
            await page.goto("http://localhost:8000")

            # Verify the About page
            about_link = page.get_by_role("link", name="About")
            await about_link.click()
            await expect(page).to_have_title(re.compile(r".*About.*"))
            await page.screenshot(path="verification/about_page.png")

            # Go back to home and verify the Media page
            await page.goto("http://localhost:8000")
            media_link = page.get_by_role("link", name="Media", exact=True)
            await media_link.click()
            await expect(page).to_have_title(re.compile(r".*Media.*"))
            await page.screenshot(path="verification/media_page.png")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
