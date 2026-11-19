"""Baseline 2: headless browser default (Playwright + Chrome) tanpa penyamaran."""
import re
import sys
from playwright.sync_api import sync_playwright

CHROME = "/usr/bin/google-chrome"


def crawl(base, max_pages=15):
    got, blocked_at, reason = 0, None, ""
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
        page = b.new_page()
        page.goto(base + "/")              # jalankan JS challenge di beranda
        page.wait_for_timeout(500)
        for n in range(1, max_pages + 1):
            r = page.goto(f"{base}/produk/{n}")
            page.wait_for_timeout(300)     # jeda tetap, tanpa interaksi
            if r.status != 200:
                blocked_at = n
                m = re.search(r"reasons=(.*?) -->", page.content())
                reason = m.group(1) if m else ""
                break
            got += 1
        b.close()
    return {"crawler": "naive_headless", "pages_ok": got,
            "blocked_at": blocked_at, "reason": reason}


if __name__ == "__main__":
    print(crawl(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"))
