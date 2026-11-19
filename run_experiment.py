"""
Menjalankan eksperimen PoC: setiap crawler diuji terhadap instance situs target
yang baru (state deteksi bersih), lalu hasilnya ditulis ke results.json & results.md.
"""
import json
import os
import subprocess
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "crawlers"))
import naive_requests, naive_headless, stealth_crawler  # noqa: E402

REPEAT_FULL = int(os.environ.get("REPEAT_FULL", "1"))
RUNS = [
    ("naive_requests", lambda b: naive_requests.crawl(b)),
    ("naive_headless", lambda b: naive_headless.crawl(b)),
    ("stealth_fp_only", lambda b: stealth_crawler.crawl(b, behaviour=False)),
    ("stealth_behaviour_only", lambda b: stealth_crawler.crawl(b, fingerprint=False)),
] + [("stealth_full", lambda b: stealth_crawler.crawl(b))] * REPEAT_FULL


def start_server(port):
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "target_site", "server.py"), str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            requests.get(f"http://127.0.0.1:{port}/robots.txt", timeout=0.5)
            return proc
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("server gagal start")


def main():
    only = sys.argv[1:]
    results = []
    for i, (name, fn) in enumerate(RUNS):
        if only and name not in only:
            continue
        port = 5100 + i
        srv = start_server(port)
        t0 = time.time()
        try:
            r = fn(f"http://127.0.0.1:{port}")
            st = requests.get(f"http://127.0.0.1:{port}/_stats").json()
            main_s = max(st.values(), key=lambda v: (v["pages"], v["score"])) if st else {}
            r["risk_score"] = main_s.get("score", 0)
            r["all_flags"] = main_s.get("reasons", [])
        finally:
            srv.terminate()
        r["seconds"] = round(time.time() - t0, 1)
        results.append(r)
        print(json.dumps(r, ensure_ascii=False))

    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    with open(os.path.join(HERE, "results.md"), "w") as f:
        f.write("| Crawler | Halaman berhasil (dari 15) | Diblokir di halaman | Skor risiko | Alasan deteksi | Waktu (dtk) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['crawler']} | {r['pages_ok']} | {r['blocked_at'] or '-'} | {r['risk_score']} | "
                    f"{r['reason'] or '-'} | {r['seconds']} |\n")


if __name__ == "__main__":
    main()
