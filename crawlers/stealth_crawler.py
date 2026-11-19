"""
HumanCrawl - crawler yang dirancang agar tidak terdeteksi sebagai robot.

Modul skema solusi:
  M1 ProfileManager     : satu profil fingerprint yang konsisten (UA, bahasa,
                          viewport, zona waktu) di level HTTP & JavaScript.
  M2 StealthPatch       : menutup "fingerprint surface" otomasi
                          (navigator.webdriver, plugins, window.chrome, dll).
  M3 HumanBehaviour     : gerakan mouse kurva Bezier, scroll bertahap,
                          jeda log-normal (tidak teratur seperti manusia).
  M4 SafeLinkSelector   : patuh robots.txt + hanya mengikuti link yang
                          terlihat (menghindari honeypot).
  M5 AdaptiveRate       : mematuhi Crawl-delay, jeda campuran, self-audit keteraturan
                          (CV) jeda, backoff eksponensial saat 403/429.

Gunakan hanya pada situs milik sendiri / yang memberi izin (lihat bagian etika laporan).
"""
import argparse
import math
import random
import re
import time
import urllib.robotparser as robotparser
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright
from browser import launch



# ---------------- M1: profil fingerprint konsisten ----------------
class ProfileManager:
    PROFILES = [
        {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
         "platform": "Win32", "viewport": {"width": 1366, "height": 768},
         "locale": "id-ID", "langs": ["id-ID", "id", "en-US", "en"],
         "tz": "Asia/Jakarta", "hwc": 8,
         "brands": '"Chromium";v="153", "Google Chrome";v="153", "Not.A/Brand";v="99"'},
        {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
         "platform": "Win32", "viewport": {"width": 1920, "height": 1080},
         "locale": "id-ID", "langs": ["id-ID", "id", "en"],
         "tz": "Asia/Jakarta", "hwc": 12,
         "brands": '"Chromium";v="153", "Google Chrome";v="153", "Not.A/Brand";v="99"'},
    ]

    def pick(self):
        return random.choice(self.PROFILES)


# ---------------- M2: patch fingerprint surface ----------------
def stealth_script(p):
    langs = str(p["langs"]).replace("'", '"')
    return f"""
    Object.defineProperty(Navigator.prototype, 'webdriver', {{get: () => undefined}});
    Object.defineProperty(Navigator.prototype, 'languages', {{get: () => {langs}}});
    Object.defineProperty(Navigator.prototype, 'platform', {{get: () => '{p["platform"]}'}});
    Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {{get: () => {p["hwc"]}}});
    Object.defineProperty(Navigator.prototype, 'plugins', {{get: () => {{
        const arr = [{{name:'PDF Viewer'}}, {{name:'Chrome PDF Viewer'}}, {{name:'Chromium PDF Viewer'}}];
        arr.item = i => arr[i]; arr.namedItem = n => arr.find(x => x.name === n);
        return arr; }} }});
    if (!window.chrome) {{ window.chrome = {{ runtime: {{}}, app: {{ isInstalled: false }} }}; }}
    if (window.outerWidth === 0) {{
        Object.defineProperty(window, 'outerWidth', {{get: () => window.innerWidth}});
        Object.defineProperty(window, 'outerHeight', {{get: () => window.innerHeight + 85}});
    }}
    """


# ---------------- M3: perilaku mirip manusia ----------------
class HumanBehaviour:
    def __init__(self, page):
        self.page = page
        self.x, self.y = random.randint(100, 400), random.randint(100, 300)

    @staticmethod
    def human_delay(median=2.6, sigma=0.45):
        """Jeda log-normal: sebagian besar 1.5-5 dtk, sesekali lebih lama."""
        time.sleep(random.lognormvariate(math.log(median), sigma))

    def move_to(self, tx, ty, steps=None):
        """Gerakan mouse mengikuti kurva Bezier kubik + jitter kecil."""
        steps = steps or random.randint(18, 35)
        x0, y0 = self.x, self.y
        c1 = (x0 + (tx - x0) * random.uniform(0.2, 0.4) + random.uniform(-80, 80),
              y0 + (ty - y0) * random.uniform(0.2, 0.4) + random.uniform(-80, 80))
        c2 = (x0 + (tx - x0) * random.uniform(0.6, 0.8) + random.uniform(-60, 60),
              y0 + (ty - y0) * random.uniform(0.6, 0.8) + random.uniform(-60, 60))
        for i in range(1, steps + 1):
            t = i / steps
            t = t * t * (3 - 2 * t)          # ease-in-out
            bx = ((1-t)**3)*x0 + 3*((1-t)**2)*t*c1[0] + 3*(1-t)*(t**2)*c2[0] + (t**3)*tx
            by = ((1-t)**3)*y0 + 3*((1-t)**2)*t*c1[1] + 3*(1-t)*(t**2)*c2[1] + (t**3)*ty
            self.page.mouse.move(bx + random.uniform(-1.5, 1.5), by + random.uniform(-1.5, 1.5))
            time.sleep(random.uniform(0.008, 0.025))
        self.x, self.y = tx, ty

    def read_page(self):
        """Simulasi membaca: gerak mouse acak + scroll bertahap."""
        vp = self.page.viewport_size
        for _ in range(random.randint(1, 3)):
            self.move_to(random.randint(50, vp["width"] - 50), random.randint(50, vp["height"] - 50))
        for _ in range(random.randint(3, 6)):
            self.page.mouse.wheel(0, random.randint(250, 520))
            time.sleep(random.uniform(0.15, 0.6))

    def click(self, locator):
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        tx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        self.move_to(tx, ty)
        time.sleep(random.uniform(0.08, 0.25))
        self.page.mouse.click(tx, ty)


# ---------------- M4: pemilihan link aman ----------------
class SafeLinkSelector:
    def __init__(self, base):
        self.rp = robotparser.RobotFileParser(urljoin(base, "/robots.txt"))
        self.rp.read()
        self.crawl_delay = self.rp.crawl_delay("*") or 0

    def allowed(self, url):
        return self.rp.can_fetch("*", url)

    @staticmethod
    def visible(locator):
        """Honeypot biasanya display:none / ukuran 0 / di luar layar."""
        try:
            if not locator.is_visible():
                return False
            b = locator.bounding_box()
            return b is not None and b["width"] > 1 and b["height"] > 1
        except Exception:
            return False

    def candidate_links(self, page):
        out = []
        for a in page.locator("a[href]").all():
            href = urljoin(page.url, a.get_attribute("href"))
            if urlparse(href).netloc != urlparse(page.url).netloc:
                continue
            if self.allowed(href) and self.visible(a):
                out.append((href, a))
        return out


# ---------------- M5: kontrol laju adaptif + self-audit ----------------
class AdaptiveRate:
    """
    - mematuhi Crawl-delay dari robots.txt (batas bawah jeda)
    - jeda campuran (mixture): normal / "membaca lama" / "klik cepat"
    - SELF-AUDIT: crawler mengukur sendiri koefisien variasi (CV) jeda antar
      navigasi pada jendela geser; bila jeda berikutnya akan membuat pola terlalu
      teratur (CV < TARGET_CV), jeda di-sampling ulang.
    - backoff eksponensial saat diblokir (403/429)
    """
    TARGET_CV = 0.35
    WINDOW = 4

    def __init__(self, crawl_delay):
        self.min_delay = max(crawl_delay, 1.0)
        self.backoff = 1.0
        self.nav_times = []

    def _sample(self):
        d = max(self.min_delay, random.lognormvariate(math.log(self.min_delay * 1.3), 0.4))
        r = random.random()
        if r < 0.25:
            d += random.uniform(5, 12)      # berhenti membaca / berpikir
        elif r < 0.45:
            d = max(self.min_delay, d * random.uniform(0.5, 0.8))  # langsung klik
        return d

    @staticmethod
    def _cv(gaps):
        m = sum(gaps) / len(gaps)
        sd = (sum((g - m) ** 2 for g in gaps) / len(gaps)) ** 0.5
        return sd / m if m else 0

    def wait(self):
        d = self._sample()
        if len(self.nav_times) >= self.WINDOW:
            past = [b - a for a, b in zip(self.nav_times[-self.WINDOW:-1], self.nav_times[-self.WINDOW + 1:])]
            elapsed = time.time() - self.nav_times[-1]
            for _ in range(30):
                if self._cv(past + [elapsed + d]) >= self.TARGET_CV:
                    break
                d = self._sample() + random.uniform(0, 8)
        time.sleep(d * self.backoff)

    def mark_navigation(self):
        self.nav_times.append(time.time())

    def penalise(self):
        self.backoff = min(self.backoff * 2, 16)


def crawl(base, max_pages=15, fingerprint=True, behaviour=True, seed=None):
    random.seed(seed)
    links = SafeLinkSelector(base)
    rate = AdaptiveRate(links.crawl_delay)
    prof = ProfileManager().pick()
    data, got, blocked_at, reason = [], 0, None, ""
    name = "stealth_full" if (fingerprint and behaviour) else (
        "stealth_fp_only" if fingerprint else "stealth_behaviour_only")

    with sync_playwright() as p:
        args = ["--no-sandbox"]
        if fingerprint:
            args.append("--disable-blink-features=AutomationControlled")
        b = launch(p, headless=True, args=args)
        ctx_kw = {}
        if fingerprint:
            ctx_kw = dict(user_agent=prof["ua"], viewport=prof["viewport"],
                          locale=prof["locale"], timezone_id=prof["tz"],
                          extra_http_headers={
                              "Accept-Language": ",".join(
                                  f"{l};q={1 - i*0.1:.1f}" if i else l
                                  for i, l in enumerate(prof["langs"])),
                              "Sec-CH-UA": prof["brands"],
                              "Sec-CH-UA-Mobile": "?0",
                              "Sec-CH-UA-Platform": '"Windows"'})
        ctx = b.new_context(**ctx_kw)
        if fingerprint:
            ctx.add_init_script(stealth_script(prof))
        page = ctx.new_page()
        human = HumanBehaviour(page)

        page.goto(base + "/")
        if "Akses ditolak" in page.content():
            m = re.search(r"reasons=(.*?) -->", page.content())
            b.close()
            return {"crawler": name, "pages_ok": 0, "blocked_at": "beranda",
                    "reason": m.group(1) if m else "", "items_collected": 0, "sample": []}
        if behaviour:
            human.read_page()
            rate.wait()
            with page.expect_navigation():
                human.click(page.locator("#next"))
            rate.mark_navigation()
        else:
            page.wait_for_timeout(500)
            page.goto(base + "/produk/1")
        page.wait_for_load_state("domcontentloaded")

        for n in range(1, max_pages + 1):
            if "403" in (page.title() or "") or "Akses ditolak" in page.content():
                blocked_at = n
                m = re.search(r"reasons=(.*?) -->", page.content())
                reason = m.group(1) if m else ""
                rate.penalise()
                break
            data += [li.inner_text() for li in page.locator("li.produk").all()]
            got += 1
            if n == max_pages:
                break
            if behaviour:
                human.read_page()
                rate.wait()
                cands = [l for h, l in links.candidate_links(page) if "/produk/" in h]
                if not cands:
                    break
                with page.expect_navigation():
                    human.click(cands[-1])
                rate.mark_navigation()
            else:
                page.wait_for_timeout(300)
                page.goto(f"{base}/produk/{n+1}")
            page.wait_for_load_state("domcontentloaded")
        b.close()
    return {"crawler": name, "pages_ok": got, "blocked_at": blocked_at,
            "reason": reason, "items_collected": len(data),
            "sample": data[:3]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://127.0.0.1:5000")
    ap.add_argument("--no-fingerprint", action="store_true")
    ap.add_argument("--no-behaviour", action="store_true")
    ap.add_argument("--pages", type=int, default=15)
    a = ap.parse_args()
    print(crawl(a.base, a.pages, not a.no_fingerprint, not a.no_behaviour))
