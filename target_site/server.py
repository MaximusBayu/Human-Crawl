"""
Situs target LAB ("Toko Lab") dengan sistem deteksi bot berlapis.
Dipakai HANYA sebagai lingkungan uji untuk proof of concept.

Lapisan deteksi (diadaptasi dari literatur):
  L1  Analisis header HTTP  : User-Agent mencurigakan, header browser yang hilang
      (Doran & Gokhale 2011; Li et al. 2021)
  L2  Fingerprint JavaScript: navigator.webdriver, HeadlessChrome, plugins,
      window.chrome, inkonsistensi (Jonker et al. 2019; Vastel et al. 2020)
  L3  Perilaku / navigasi   : laju request, keteraturan jeda waktu,
      interaksi mouse/scroll, honeypot link tersembunyi
      (Tan & Kumar 2002; Iliou et al. 2021)

Setiap sesi memiliki skor risiko. Skor >= BLOCK_THRESHOLD -> HTTP 403.
"""
import json
import statistics
import time
import uuid
from collections import defaultdict

from flask import Flask, request, make_response, jsonify

app = Flask(__name__)

BLOCK_THRESHOLD = 10
TOTAL_PAGES = 15
BAD_UA_TOKENS = ["python-requests", "curl", "wget", "scrapy", "httpx",
                 "headlesschrome", "phantomjs", "bot", "spider", "crawler"]

# state per sesi
SESS = defaultdict(lambda: {"score": 0, "reasons": [], "times": [],
                            "interacted": set(), "fp_ok": False,
                            "blocked": False, "pages": 0,
                            # Sinyal LANJUTAN: diukur, TIDAK dihitung ke skor blokir.
                            # Dipakai sebagai kontrol agar lab tidak hanya menguji
                            # sinyal yang bisa dikalahkan HumanCrawl.
                            "adv_automation": False, "adv_reason": ""})


def sid():
    return request.cookies.get("sid")


def flag(s, pts, reason):
    if reason not in s["reasons"]:
        s["score"] += pts
        s["reasons"].append(reason)
    if s["score"] >= BLOCK_THRESHOLD:
        s["blocked"] = True


def blocked_response(s):
    body = ("<h1>403 - Akses ditolak</h1><p>Aktivitas Anda terdeteksi sebagai bot.</p>"
            f"<!-- score={s['score']} reasons={'; '.join(s['reasons'])} -->")
    return make_response(body, 403)


# ---------------- L1: header HTTP ----------------
def check_headers(s):
    ua = request.headers.get("User-Agent", "").lower()
    if not ua:
        flag(s, 10, "L1: User-Agent kosong")
    for t in BAD_UA_TOKENS:
        if t in ua:
            flag(s, 10, f"L1: User-Agent mengandung '{t}'")
            break
    if "Accept-Language" not in request.headers:
        flag(s, 4, "L1: tidak ada Accept-Language")
    if "Sec-Fetch-Mode" not in request.headers:
        flag(s, 3, "L1: tidak ada header Sec-Fetch-* (bukan browser modern)")
    # inkonsistensi: mengaku Chrome tapi tidak mengirim client hints
    if "chrome/" in ua and "Sec-Ch-Ua" not in request.headers:
        flag(s, 3, "L1: mengaku Chrome tanpa Sec-CH-UA")


# ---------------- L3: perilaku ----------------
def check_behaviour(s, page):
    now = time.time()
    s["times"].append(now)
    recent = [t for t in s["times"] if now - t < 10]
    if len(recent) > 6:
        flag(s, 10, "L3: laju request > 6 per 10 detik")
    if len(s["times"]) >= 5:
        gaps = [b - a for a, b in zip(s["times"][-5:-1], s["times"][-4:])]
        mean = statistics.mean(gaps)
        if mean > 0 and statistics.pstdev(gaps) / mean < 0.15:
            flag(s, 6, "L3: jeda antar-request terlalu teratur (CV < 0.15)")
    # halaman sebelumnya harus punya interaksi manusia (mouse/scroll)
    if page > 1 and (page - 1) not in s["interacted"]:
        flag(s, 4, f"L3: tidak ada interaksi mouse/scroll di halaman {page-1}")


PAGE_JS = """
<script>
(function(){
  // --- L2: fingerprint ---
  var fp = {
    webdriver: navigator.webdriver === true,
    ua: navigator.userAgent,
    plugins: navigator.plugins ? navigator.plugins.length : 0,
    languages: navigator.languages ? navigator.languages.length : 0,
    chromeObj: typeof window.chrome !== 'undefined',
    outerW: window.outerWidth, outerH: window.outerHeight,
    hwc: navigator.hardwareConcurrency || 0
  };
  // Sinyal lanjutan: renderer WebGL. Headless/VM memakai software rendering
  // (SwiftShader / llvmpipe), bukan GPU asli. HumanCrawl tidak menyamarkan ini.
  try {
    var cv = document.createElement('canvas');
    var gl = cv.getContext('webgl') || cv.getContext('experimental-webgl');
    var dbg = gl.getExtension('WEBGL_debug_renderer_info');
    fp.webglRenderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : '';
  } catch (e) { fp.webglRenderer = ''; }
  fetch('/fp', {method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify(fp), credentials:'same-origin'})
    .then(function(){ document.cookie = 'js_ok=1; path=/'; });
  // --- L3: interaksi ---
  var moves = 0, scrolls = 0, sent = false;
  function report(){
    if (sent) return;
    if (moves >= 5 || scrolls >= 1) {
      sent = true;
      navigator.sendBeacon('/beh', JSON.stringify({page: PAGE_NO, moves: moves, scrolls: scrolls}));
    }
  }
  document.addEventListener('mousemove', function(){ moves++; report(); });
  window.addEventListener('scroll', function(){ scrolls++; report(); });
})();
</script>
"""


def render_page(n):
    items = "".join(
        f"<li class='produk'><b>Produk {n}-{i}</b> &mdash; Rp{(n*7+i)*1000:,}</li>"
        for i in range(1, 6))
    nxt = (f"<a id='next' href='/produk/{n+1}'>Halaman berikutnya &raquo;</a>"
           if n < TOTAL_PAGES else "<p>Halaman terakhir.</p>")
    # honeypot: link yang tidak terlihat manusia
    trap = "<a href='/admin-export' style='display:none'>export semua data</a>"
    filler = "<div style='height:1400px'></div>"
    return (f"<html><head><title>Toko Lab - Halaman {n}</title></head><body>"
            f"<h1>Katalog Produk - Halaman {n}</h1><ul>{items}</ul>{trap}{filler}{nxt}"
            f"<script>var PAGE_NO={n};</script>{PAGE_JS}</body></html>")


@app.before_request
def ensure_session():
    if not sid():
        request.new_sid = uuid.uuid4().hex
    else:
        request.new_sid = None


@app.after_request
def set_sid(resp):
    if getattr(request, "new_sid", None):
        resp.set_cookie("sid", request.new_sid)
    return resp


def current_session():
    return SESS[sid() or request.new_sid]


@app.route("/robots.txt")
def robots():
    return ("User-agent: *\nDisallow: /admin-export\nCrawl-delay: 2\n",
            200, {"Content-Type": "text/plain"})


@app.route("/")
def home():
    s = current_session()
    check_headers(s)
    if s["blocked"]:
        return blocked_response(s)
    return ("<html><body><h1>Toko Lab</h1>"
            "<a id='next' href='/produk/1'>Lihat katalog</a>"
            "<script>var PAGE_NO=0;</script>" + PAGE_JS + "</body></html>")


@app.route("/produk/<int:n>")
def produk(n):
    s = current_session()
    check_headers(s)
    # L2: halaman data hanya diberikan jika JS challenge sudah dijalankan
    if not request.cookies.get("js_ok"):
        flag(s, 10, "L2: JS challenge tidak dijalankan (cookie js_ok tidak ada)")
    if not s["fp_ok"] and request.cookies.get("js_ok"):
        flag(s, 10, "L2: fingerprint tidak pernah dikirim")
    check_behaviour(s, n)
    if s["blocked"]:
        return blocked_response(s)
    s["pages"] += 1
    return render_page(n)


@app.route("/fp", methods=["POST"])
def fp():
    s = current_session()
    d = request.get_json(force=True, silent=True) or {}
    if d.get("webdriver"):
        flag(s, 10, "L2: navigator.webdriver = true")
    if "headless" in str(d.get("ua", "")).lower():
        flag(s, 10, "L2: UA JavaScript mengandung HeadlessChrome")
    if d.get("plugins", 0) == 0:
        flag(s, 2, "L2: navigator.plugins kosong")
    if d.get("languages", 0) == 0:
        flag(s, 2, "L2: navigator.languages kosong")
    if "chrome" in str(d.get("ua", "")).lower() and not d.get("chromeObj"):
        flag(s, 3, "L2: mengaku Chrome tapi window.chrome tidak ada")
    if d.get("outerW", 0) == 0:
        flag(s, 3, "L2: window.outerWidth = 0 (ciri headless)")
    # inkonsistensi UA HTTP vs UA JavaScript (Vastel et al. FP-Scanner)
    if d.get("ua") and d.get("ua") != request.headers.get("User-Agent"):
        flag(s, 5, "L2: UA HTTP != UA JavaScript (inkonsisten)")
    # SINYAL LANJUTAN (tidak dihitung ke skor): software rendering = indikasi
    # headless/VM. Ini sinyal yang TIDAK ditangani HumanCrawl, dipakai sebagai
    # kontrol bias; sejalan dengan deteksi otomasi oleh detektor kelas industri.
    renderer = str(d.get("webglRenderer", "")).lower()
    if any(t in renderer for t in ("swiftshader", "llvmpipe", "software")):
        s["adv_automation"] = True
        s["adv_reason"] = "renderer WebGL = software rendering (indikasi headless/VM)"
    s["fp_ok"] = True
    return jsonify(ok=True)


@app.route("/beh", methods=["POST"])
def beh():
    s = current_session()
    try:
        d = json.loads(request.get_data(as_text=True) or "{}")
        s["interacted"].add(int(d.get("page", -1)))
    except Exception:
        pass
    return ("", 204)


@app.route("/admin-export")
def honeypot():
    s = current_session()
    flag(s, 20, "L3: mengakses honeypot link tersembunyi /admin-export")
    return blocked_response(s)


@app.route("/_stats")
def stats():
    return jsonify({k: {kk: (list(vv) if isinstance(vv, set) else vv)
                        for kk, vv in v.items() if kk != "times"}
                    for k, v in SESS.items()})


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host="127.0.0.1", port=port, threaded=True)
