"""Capture real screenshots of the running app with headless Chromium (Playwright).

Usage (backend must be running and serving the built frontend on :8000):
    python scripts/screenshots.py [--base http://127.0.0.1:8000] [--out ../docs/screenshots]

Also records browser console errors and fails loudly if any appear.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "screenshots"))
    ap.add_argument("--only", default="", help="comma-separated shot names to capture")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, args.only.split(",")))
    errors: list[str] = []

    def shot(page, name, full=False):
        if only and name not in only:
            return
        page.wait_for_timeout(900)  # let entrance animations settle
        page.screenshot(path=str(out / f"{name}.png"), full_page=full)
        print("saved", name)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport=DESKTOP, device_scale_factor=1, color_scheme=theme)
            ctx.add_init_script(f"localStorage.setItem('qs-theme', '{theme}')")
            page = ctx.new_page()
            page.on("console", lambda m: m.type == "error" and errors.append(f"{m.text}"))
            page.on("pageerror", lambda e: errors.append(str(e)))

            page.goto(args.base + "/")
            page.wait_for_selector("text=pages indexed")
            page.wait_for_function("!document.querySelector('.skeleton')")
            shot(page, f"home-{theme}")

            # Type into the search box to show autocomplete
            page.fill("input[role=combobox]", "data str")
            page.wait_for_selector("[role=listbox] li")
            shot(page, f"autocomplete-{theme}")

            page.goto(args.base + "/search?q=write%20ahead%20log")
            page.wait_for_selector("article")
            shot(page, f"results-{theme}")
            if theme == "light":
                page.click("text=Why this result? >> nth=0")
                page.wait_for_timeout(400)
                shot(page, "results-explain-light")
                page.goto(args.base + "/search?q=databse")
                page.wait_for_selector("text=Did you mean")
                shot(page, "results-empty-light")

            page.goto(args.base + "/dashboard")
            page.wait_for_selector("text=Index analytics")
            page.wait_for_selector(".recharts-surface")
            shot(page, f"dashboard-{theme}")
            shot(page, f"dashboard-full-{theme}", full=True)
            ctx.close()

        ctx = browser.new_context(viewport=MOBILE, device_scale_factor=2, color_scheme="light", is_mobile=True, has_touch=True)
        ctx.add_init_script("localStorage.setItem('qs-theme', 'light')")
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.base + "/")
        page.wait_for_selector("text=pages indexed")
        page.wait_for_function("!document.querySelector('.skeleton')")
        shot(page, "mobile-home", full=True)
        page.goto(args.base + "/search?q=bm25%20ranking")
        page.wait_for_selector("article")
        shot(page, "mobile-results")
        page.goto(args.base + "/dashboard")
        page.wait_for_selector(".recharts-surface")
        shot(page, "mobile-dashboard")
        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        if overflow:
            errors.append("Horizontal overflow on mobile dashboard")
        browser.close()

    if errors:
        print("BROWSER ERRORS:", *errors, sep="\n  ")
        return 1
    print("No browser console errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
