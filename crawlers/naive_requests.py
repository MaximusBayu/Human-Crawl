"""Baseline 1: crawler konvensional berbasis HTTP library (python-requests)."""
import re
import sys
import requests


def crawl(base, max_pages=15):
    s = requests.Session()
    got, blocked_at, reason = 0, None, ""
    for n in range(1, max_pages + 1):
        r = s.get(f"{base}/produk/{n}", timeout=10)
        if r.status_code != 200:
            blocked_at = n
            m = re.search(r"reasons=(.*?) -->", r.text)
            reason = m.group(1) if m else r.text[:80]
            break
        got += 1
    return {"crawler": "naive_requests", "pages_ok": got,
            "blocked_at": blocked_at, "reason": reason}


if __name__ == "__main__":
    print(crawl(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"))
