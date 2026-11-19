# PoC HumanCrawl: crawler yang tidak terdeteksi sebagai robot

Proof of concept untuk Tantangan 1 (Crawling System, Framework OSINT).

## Struktur
```
target_site/server.py        situs target LAB dengan deteksi bot 3 lapis (L1 header, L2 fingerprint JS, L3 perilaku + honeypot)
crawlers/naive_requests.py   baseline 1: crawler python-requests
crawlers/naive_headless.py   baseline 2: Playwright headless default
crawlers/stealth_crawler.py  solusi HumanCrawl (M1-M5)
run_experiment.py            menjalankan semua crawler terhadap instance target yang bersih
results.json / results.md    hasil akhir
results_iterasi1.*           hasil iterasi 1 (sebelum perbaikan modul M5)
```

## Menjalankan
```bash
pip install flask requests playwright
playwright install chromium          # atau pakai Chrome yang sudah terpasang
# sesuaikan CHROME di crawlers/*.py (mis. "C:/Program Files/Google/Chrome/Application/chrome.exe"),
# atau hapus argumen executable_path agar memakai Chromium bawaan Playwright
python target_site/server.py 5000    # terminal 1 (opsional, untuk uji manual)
python crawlers/stealth_crawler.py http://127.0.0.1:5000
REPEAT_FULL=3 python run_experiment.py   # eksperimen lengkap
```
Lihat skor/alasan deteksi per sesi di `http://127.0.0.1:5000/_stats`.

## Etika
Hanya untuk diuji pada situs target lab ini atau situs yang memberi izin.
Crawler mematuhi robots.txt dan Crawl-delay secara default.
