"""Membuka Chrome/Chromium secara portabel (Windows, macOS, Linux).

Urutan:
  1. env CHROME_PATH (path chrome.exe tertentu), jika di-set
  2. Google Chrome yang terpasang di komputer (channel="chrome")
  3. Chromium bawaan Playwright (perlu: playwright install chromium)
"""
import os


def launch(p, headless=True, args=None):
    args = args or []
    path = os.environ.get("CHROME_PATH")
    if path:
        return p.chromium.launch(executable_path=path, headless=headless, args=args)
    try:
        return p.chromium.launch(channel="chrome", headless=headless, args=args)
    except Exception:
        return p.chromium.launch(headless=headless, args=args)
