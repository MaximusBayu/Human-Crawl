"""
Uji HumanCrawl terhadap halaman deteksi bot PUBLIK yang memang dibuat untuk pengujian:
  1. bot.sannysoft.com              - daftar tes fingerprint headless (passed/failed)
  2. arh.antoinevastel.com          - "Are you headless?" (Antoine Vastel, penulis FP-Crawlers)
  3. FingerprintJS BotD (demo)      - library deteksi bot open-source

Membandingkan mode "naive" (Playwright headless default) vs "stealth" (modul M1-M3 HumanCrawl).
Hasil: real_results.json, real_results.md, dan screenshot di folder screenshots/.

Pakai:
  pip install playwright && playwright install chromium
  python real_site_test.py                 # pakai Chromium bawaan Playwright
  python real_site_test.py --chrome "C:/Program Files/Google/Chrome/Application/chrome.exe"
"""
import argparse
import json
import os
import platform
import re
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "crawlers"))
from stealth_crawler import HumanBehaviour, stealth_script  # noqa: E402

SITES = [
    ("sannysoft", "https://bot.sannysoft.com/"),
    ("areyouheadless", "https://arh.antoinevastel.com/bots/areyouheadless"),
    ("botd", "https://fingerprintjs.github.io/BotD/main/"),
]


def host_profile(major):
    """Profil yang konsisten dengan OS asli mesin (hindari inkonsistensi OS/WebGL/font)."""
    sysname = platform.system()
    if sysname == "Windows":
        osua, plat, chplat = "Windows NT 10.0; Win64; x64", "Win32", '"Windows"'
    elif sysname == "Darwin":
        osua, plat, chplat = "Macintosh; Intel Mac OS X 10_15_7", "MacIntel", '"macOS"'
    else:
        osua, plat, chplat = "X11; Linux x86_64", "Linux x86_64", '"Linux"'
    return {
        "ua": f"Mozilla/5.0 ({osua}) AppleWebKit/537.36 (KHTML, like Gecko) "
              f"Chrome/{major}.0.0.0 Safari/537.36",
        "platform": plat, "chplat": chplat,
        "viewport": {"width": 1366, "height": 768},
        "locale": "id-ID", "langs": ["id-ID", "id", "en-US", "en"],
        "tz": "Asia/Jakarta", "hwc": os.cpu_count() or 8,
        "brands": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not.A/Brand";v="99"',
    }


def evaluate(name, page):
    text = page.inner_text("body")
    if name == "sannysoft":
        failed = page.locator("td.failed").count()
        warn = page.locator("td.warn").count()
        passed = page.locator("td.passed").count()
        return {"verdict": "LOLOS" if failed == 0 else "TERDETEKSI",
                "detail": f"passed={passed}, warn={warn}, failed={failed}"}
    if name == "areyouheadless":
        m = re.search(r"You are (not )?Chrome headless", text, re.I)
        if not m:
            return {"verdict": "?", "detail": text[:120].replace("\n", " ")}
        return {"verdict": "LOLOS" if m.group(1) else "TERDETEKSI", "detail": m.group(0)}
    if name == "botd":
        m = re.search(r'"bot"\s*:\s*(true|false)', text)
        kind = re.search(r'"botKind"\s*:\s*"([^"]+)"', text)
        if not m:
            return {"verdict": "?", "detail": text[:160].replace("\n", " ")}
        return {"verdict": "TERDETEKSI" if m.group(1) == "true" else "LOLOS",
                "detail": f'bot={m.group(1)}' + (f', kind={kind.group(1)}' if kind else "")}
    return {"verdict": "?", "detail": ""}


def run(mode, chrome, headless):
    out = []
    with sync_playwright() as p:
        args = ["--no-sandbox"]
        if mode == "stealth":
            args.append("--disable-blink-features=AutomationControlled")
        kw = {"headless": headless, "args": args}
        if chrome:
            kw["executable_path"] = chrome
        b = p.chromium.launch(**kw)
        major = b.version.split(".")[0]
        ctx_kw = {}
        prof = host_profile(major)
        if mode == "stealth":
            ctx_kw = dict(user_agent=prof["ua"], viewport=prof["viewport"], locale=prof["locale"],
                          timezone_id=prof["tz"],
                          extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                                              "Sec-CH-UA": prof["brands"], "Sec-CH-UA-Mobile": "?0",
                                              "Sec-CH-UA-Platform": prof["chplat"]})
        ctx = b.new_context(**ctx_kw)
        if mode == "stealth":
            ctx.add_init_script(stealth_script(prof))
        page = ctx.new_page()
        os.makedirs(os.path.join(HERE, "screenshots"), exist_ok=True)
        for name, url in SITES:
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
                if mode == "stealth":
                    HumanBehaviour(page).read_page()
                    page.mouse.wheel(0, -5000)
                time.sleep(4)  # beri waktu skrip deteksi selesai
                res = evaluate(name, page)
                page.screenshot(path=os.path.join(HERE, "screenshots", f"{mode}_{name}.png"), full_page=True)
            except Exception as e:
                res = {"verdict": "ERROR", "detail": str(e)[:120]}
            res.update(mode=mode, site=name, browser=b.version, headless=headless)
            print(json.dumps(res, ensure_ascii=False))
            out.append(res)
        b.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", default=None, help="path Chrome; kosong = Chromium Playwright")
    ap.add_argument("--headed", action="store_true", help="tampilkan jendela browser")
    a = ap.parse_args()
    results = run("naive", a.chrome, not a.headed) + run("stealth", a.chrome, not a.headed)
    with open(os.path.join(HERE, "real_results.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    with open(os.path.join(HERE, "real_results.md"), "w") as f:
        f.write("| Situs uji | Mode | Hasil | Detail |\n|---|---|---|---|\n")
        for r in sorted(results, key=lambda r: (r["site"], r["mode"])):
            f.write(f"| {r['site']} | {r['mode']} | {r['verdict']} | {r['detail']} |\n")
    print(open(os.path.join(HERE, "real_results.md")).read())
