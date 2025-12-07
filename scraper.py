import argparse
import asyncio
import csv
import os
import random
import re
import time
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

STEALTH_SCRIPT = """
// Basic stealth tweaks
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {} };
"""

SEARCH_URL = "https://www.google.com/maps"
MAX_RESULTS_CAP = 200
SCROLL_TIMEOUT_SECONDS = 90
STALE_SCROLL_LIMIT = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Maps dentist scraper")
    parser.add_argument(
        "--city",
        type=str,
        default="Istanbul",
        help="City to search, e.g., 'Istanbul'",
    )
    return parser.parse_args()


def clean_phone(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.replace("Phone:", "").replace("\u202a", "").replace("\u202c", "").strip()


def parse_rating_and_reviews(raw: str | None) -> tuple[str, str]:
    if not raw:
        return "", ""
    # Examples: "4.5 stars 127 reviews", "4.3 stars", "4,8 \u2014 56 avis"
    # Extract rating (float) and reviews (int) if present
    rating_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
    reviews_match = re.search(
        r"([0-9][0-9,\.]*)\s*(?:reviews|avis|recenzii|bewertung|bewertung(en)?|review)", raw, re.IGNORECASE)
    rating = rating_match.group(1) if rating_match else ""
    reviews = reviews_match.group(1).replace(",", "") if reviews_match else ""
    return rating, reviews


async def robust_goto(page, url: str, max_retries: int = 2, timeout: int = 30000) -> bool:
    for attempt in range(max_retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            if attempt == max_retries - 1:
                return False
            await page.wait_for_timeout(1000 * (attempt + 1))
        except Exception:
            if attempt == max_retries - 1:
                return False
            await page.wait_for_timeout(1500)
    return False


async def search_google_maps(page, city: str) -> bool:
    ok = await robust_goto(page, SEARCH_URL, max_retries=2, timeout=30000)
    if not ok:
        return False

    try:
        search_input = page.locator("input#searchboxinput")
        await search_input.wait_for(state="visible", timeout=15000)
        await search_input.fill(f"Dentist in {city}")
        await page.locator("button#searchbox-searchbutton").click()
        await page.wait_for_selector("div[role='feed']", state="visible", timeout=15000)
        return True
    except Exception:
        return False


async def scroll_results(page) -> int:
    feed = page.locator("div[role='feed']")
    await feed.wait_for(state="visible", timeout=15000)

    previous_count = 0
    stale_scrolls = 0
    start_time = time.time()

    while True:
        current_count = await page.locator("div[role='article']").count()
        if current_count >= MAX_RESULTS_CAP:
            break

        if current_count == previous_count:
            stale_scrolls += 1
        else:
            stale_scrolls = 0
        previous_count = current_count

        if stale_scrolls >= STALE_SCROLL_LIMIT:
            break

        if time.time() - start_time > SCROLL_TIMEOUT_SECONDS:
            break

        await feed.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        await page.wait_for_timeout(random.uniform(1500, 3500))
        try:
            await page.wait_for_load_state("networkidle", timeout=3000)
        except PlaywrightTimeoutError:
            pass

    final_count = await page.locator("div[role='article']").count()
    return final_count


async def extract_business_from_detail(page, fallback_name: str) -> dict:
    # Name
    name = ""
    for selector in ["div[role='main'] h1", "h1.DUwDvf", "h1.fontHeadlineLarge", "div[role='main'] [aria-level='1']"]:
        handle = page.locator(selector).first
        try:
            text = await handle.text_content(timeout=3000)
            if text:
                name = text.strip()
                break
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    if not name:
        name = fallback_name

    # Phone
    phone = ""
    phone_locators = [
        "button[aria-label*='Phone']",
        "button[data-item-id^='phone:']",
        "div[role='main'] a[href^='tel:']",
    ]
    for selector in phone_locators:
        handle = page.locator(selector).first
        try:
            value = await handle.get_attribute("aria-label")
            if not value:
                value = await handle.text_content()
            if value:
                phone = clean_phone(value)
                break
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    # Website
    website = ""
    website_locators = [
        "a[aria-label*='Website']",
        "a[data-item-id='authority']",
        "a[data-tooltip='Open website']",
    ]
    for selector in website_locators:
        handle = page.locator(selector).first
        try:
            href = await handle.get_attribute("href")
            if href and href.startswith("http"):
                website = href
                break
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    # Rating + Reviews
    rating_val = ""
    reviews_val = ""
    rating_locators = [
        "span[role='img'][aria-label*='star']",
        "div[role='main'] span[aria-label*='star']",
    ]
    for selector in rating_locators:
        handle = page.locator(selector).first
        try:
            raw = await handle.get_attribute("aria-label")
            if not raw:
                raw = await handle.text_content()
            if raw:
                rating_val, reviews_val = parse_rating_and_reviews(raw)
                break
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    return {
        "Business Name": name or "",
        "Phone Number": phone,
        "Website URL": website,
        "Rating": rating_val,
        "Review Count": reviews_val,
    }


async def extract_all_businesses(page) -> list[dict]:
    data: list[dict] = []
    cards = page.locator("div[role='article']")
    total = await cards.count()

    for idx in range(total):
        card = cards.nth(idx)
        try:
            # Fallback name from list card
            fallback_name = ""
            try:
                fallback_name = await card.locator("a.hfpxzc").first.text_content()
                if fallback_name:
                    fallback_name = fallback_name.strip()
            except Exception:
                fallback_name = ""

            await card.scroll_into_view_if_needed()
            await card.click()
            await page.wait_for_timeout(random.uniform(800, 1600))

            # Wait briefly for detail panel; continue even if timeout
            try:
                await page.wait_for_selector("div[role='main']", timeout=5000)
            except PlaywrightTimeoutError:
                pass

            business = await extract_business_from_detail(page, fallback_name)
            data.append(business)
        except Exception:
            # Skip problematic cards and continue
            continue
    return data


def save_to_csv(rows: list[dict], filepath: Path) -> None:
    if not rows:
        return

    file_exists = filepath.exists()
    with filepath.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Business Name", "Phone Number",
                        "Website URL", "Rating", "Review Count"],
        )
        if not file_exists or filepath.stat().st_size == 0:
            writer.writeheader()
        writer.writerows(rows)


async def run(city: str) -> int:
    ua = random.choice(USER_AGENTS)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="Europe/Istanbul",
            geolocation={"latitude": 41.0082, "longitude": 28.9784},
            permissions=["geolocation"],
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        # Try search with one retry on failure
        for attempt in range(2):
            ok = await search_google_maps(page, city)
            if ok:
                break
            if attempt == 1:
                print("Search failed after retry. Exiting.")
                await context.close()
                await browser.close()
                return 1

        await page.wait_for_timeout(random.uniform(2000, 4000))
        await scroll_results(page)
        rows = await extract_all_businesses(page)

        save_to_csv(rows, Path("leads.csv"))
        print(f"Scraped {len(rows)} rows.")

        await context.close()
        await browser.close()
    return 0


def main() -> None:
    args = parse_args()
    try:
        exit_code = asyncio.run(run(args.city))
    except KeyboardInterrupt:
        print("Interrupted by user.")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
