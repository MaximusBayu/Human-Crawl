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

## Menjalankan (Windows / macOS / Linux)
```bash
pip install -r requirements.txt
playwright install chromium      # cadangan jika Google Chrome tidak ditemukan

python run_experiment.py         # eksperimen lengkap (1x stealth_full, ~3 menit)
# PowerShell, 3x stealth_full:   $env:REPEAT_FULL=3; python run_experiment.py
```
Crawler otomatis memakai Google Chrome yang terpasang; set `CHROME_PATH` untuk memakai browser lain.

## Uji terhadap situs nyata (real_site_test.py)

Membandingkan mode naive vs stealth terhadap situs nyata, dengan deteksi otomatis
apakah crawler lolos / diblokir / kena challenge.

```bash
# 3 halaman tes bot publik (sannysoft, areyouheadless, BotD)
python real_site_test.py --headful

# URL apa pun (mis. halaman latihan scraping)
python real_site_test.py --url https://www.scrapingcourse.com/antibot-challenge --headful

# ekstrak data produk ke CSV (halaman mirip WooCommerce)
python real_site_test.py --url https://www.scrapingcourse.com/ecommerce/ --extract --headful
```
`--headful` membuka jendela browser nyata (bukan headless); sering membuat crawler lolos
di detektor yang mendeteksi mode headless. Hasil: `real_results.md`, `data_*.csv`, dan
screenshot di `screenshots/`.

ETIKA: pakai hanya pada situs milik sendiri atau situs yang disediakan untuk latihan
scraping (scrapingcourse.com, trekky-reviews.com) atau halaman tes bot di atas. Jangan
menembus proteksi situs pihak ketiga tanpa izin.

Uji manual: jalankan `python target_site/server.py 5000`, lalu di terminal lain
`python crawlers/stealth_crawler.py http://127.0.0.1:5000`. Skor/alasan deteksi per sesi: `http://127.0.0.1:5000/_stats`.

## Etika
Hanya untuk diuji pada situs target lab ini atau situs yang memberi izin.
Crawler mematuhi robots.txt dan Crawl-delay secara default.
