"""
Uji HumanCrawl terhadap situs NYATA.

Dua kegunaan:
  1. Tanpa argumen: uji 3 halaman deteksi bot publik (sannysoft, areyouheadless, BotD).
  2. Dengan --url: uji URL apa pun (mis. halaman latihan scraping), deteksi otomatis
     apakah crawler lolos / diblokir / kena challenge, dan (opsional) ekstrak data ke CSV.

Membandingkan mode "naive" (browser default) vs "stealth" (modul M1-M3 HumanCrawl).

ETIKA: pakai hanya pada situs milik sendiri atau situs yang memang disediakan untuk
latihan scraping (mis. scrapingcourse.com, trekky-reviews.com) atau halaman tes bot di atas.
Jangan dipakai untuk menembus proteksi situs pihak ketiga tanpa izin.

Contoh:
  python real_site_test.py                        # 3 halaman tes bot (headless)
  python real_site_test.py --headful              # idem, tapi jendela browser nyata
  python real_site_test.py --url https://www.scrapingcourse.com/antibot-challenge --headful
  python real_site_test.py --url https://www.scrapingcourse.com/ecommerce/ --extract --headful

Hasil: real_results.json, real_results.md, CSV data (jika --extract), screenshot di screenshots/.
"""
import argparse
import csv
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
from browser import launch  # noqa: E402

# Halaman deteksi bot publik yang memang untuk pengujian (dipakai jika tanpa --url)
DETECTOR_SITES = [
    ("sannysoft", "https://bot.sannysoft.com/"),
    ("areyouheadless", "https://arh.antoinevastel.com/bots/areyouheadless"),
    ("botd", "https://fingerprintjs.github.io/BotD/main/"),
]

# Kata kunci yang menandakan halaman block / challenge / CAPTCHA
BLOCK_HINTS = [
    "just a moment", "checking your browser", "verifying you are human",
    "attention required", "access denied", "cf-challenge", "cf-turnstile",
    "please enable javascript and cookies", "ddos protection by", "are you a robot",
    "unusual traffic", "captcha",
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


def evaluate_detector(name, page):
    """Verdict untuk 3 halaman deteksi bot yang sudah dikenal."""
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


def evaluate_generic(page, status):
    """Verdict untuk URL sembarang: cek status HTTP, teks challenge, lalu isi."""
    if status and status >= 400:
        return {"verdict": "DIBLOKIR", "detail": f"HTTP {status}"}
    try:
        text = page.inner_text("body").lower()
    except Exception:
        text = ""
    for hint in BLOCK_HINTS:
        if hint in text:
            return {"verdict": "CHALLENGE/CAPTCHA", "detail": f"halaman menampilkan '{hint}'"}
    # Turnstile / reCAPTCHA iframe
    if page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='recaptcha']").count():
        return {"verdict": "CHALLENGE/CAPTCHA", "detail": "iframe challenge terdeteksi"}
    title = (page.title() or "").strip()
    return {"verdict": "LOLOS", "detail": f'HTTP {status}, judul: "{title[:60]}"'}


def extract_products(page):
    """Ekstrak produk dari halaman mirip WooCommerce (mis. scrapingcourse.com/ecommerce)."""
    items = []
    cards = page.locator("li.product, .product")
    n = cards.count()
    for i in range(n):
        c = cards.nth(i)
        name = ""
        for sel in [".product-name", ".woocommerce-loop-product__title", "h2", "h3", "a"]:
            loc = c.locator(sel)
            if loc.count():
                name = loc.first.inner_text().strip()
                if name:
                    break
        price = ""
        pl = c.locator(".price")
        if pl.count():
            price = pl.first.inner_text().strip().replace("\n", " ")
        if name:
            items.append({"name": name, "price": price})
    return items


def run(mode, sites, chrome, headless, extract):
    out = []
    with sync_playwright() as p:
        if chrome:
            os.environ["CHROME_PATH"] = chrome
        args = ["--no-sandbox"]
        if mode == "stealth":
            args.append("--disable-blink-features=AutomationControlled")
        b = launch(p, headless=headless, args=args)
        major = b.version.split(".")[0]
        prof = host_profile(major)
        ctx_kw = {}
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
        for name, url, kind in sites:
            res = {"mode": mode, "site": name, "browser": b.version, "headless": headless}
            try:
                resp = page.goto(url, wait_until="networkidle", timeout=45000)
                status = resp.status if resp else None
                if mode == "stealth":
                    HumanBehaviour(page).read_page()
                    page.mouse.wheel(0, -5000)
                time.sleep(4)  # beri waktu skrip deteksi / challenge selesai
                if kind == "detector":
                    res.update(evaluate_detector(name, page))
                else:
                    res.update(evaluate_generic(page, status))
                    if extract and res["verdict"] == "LOLOS":
                        items = extract_products(page)
                        res["items_collected"] = len(items)
                        res["sample"] = [f"{it['name']} {it['price']}".strip() for it in items[:3]]
                        if items:
                            csv_path = os.path.join(HERE, f"data_{mode}_{name}.csv")
                            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                                w = csv.DictWriter(f, fieldnames=["name", "price"])
                                w.writeheader()
                                w.writerows(items)
                            res["csv"] = os.path.basename(csv_path)
                page.screenshot(path=os.path.join(HERE, "screenshots", f"{mode}_{name}.png"),
                                full_page=True)
            except Exception as e:
                res.update(verdict="ERROR", detail=str(e)[:140])
            print(json.dumps(res, ensure_ascii=False))
            out.append(res)
        b.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="Uji HumanCrawl terhadap situs nyata.")
    ap.add_argument("--url", default=None,
                    help="URL target (mis. halaman latihan scraping). Kosong = 3 halaman tes bot.")
    ap.add_argument("--name", default="target", help="Label untuk URL target (untuk nama file).")
    ap.add_argument("--extract", action="store_true",
                    help="Ekstrak produk (WooCommerce) dan simpan ke CSV jika lolos.")
    ap.add_argument("--headful", action="store_true",
                    help="Jalankan dengan jendela browser nyata (bukan headless).")
    ap.add_argument("--chrome", default=None, help="Path Chrome; kosong = Chrome terpasang.")
    a = ap.parse_args()

    if a.url:
        sites = [(a.name, a.url, "generic")]
    else:
        sites = [(n, u, "detector") for n, u in DETECTOR_SITES]

    headless = not a.headful
    results = run("naive", sites, a.chrome, headless, a.extract) + \
        run("stealth", sites, a.chrome, headless, a.extract)

    with open(os.path.join(HERE, "real_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    with open(os.path.join(HERE, "real_results.md"), "w", encoding="utf-8") as f:
        f.write(f"Mode browser: {'headful (jendela nyata)' if a.headful else 'headless'}\n\n")
        f.write("| Situs uji | Mode | Hasil | Detail |\n|---|---|---|---|\n")
        for r in sorted(results, key=lambda r: (r["site"], r["mode"])):
            extra = ""
            if "items_collected" in r:
                extra = f" ({r['items_collected']} item, CSV: {r.get('csv', '-')})"
            f.write(f"| {r['site']} | {r['mode']} | {r['verdict']} | {r.get('detail', '')}{extra} |\n")
    print("\n" + open(os.path.join(HERE, "real_results.md"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
