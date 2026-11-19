| Crawler | Halaman berhasil (dari 15) | Diblokir di halaman | Skor risiko | Sinyal lanjutan (WebGL) | Alasan deteksi | Waktu (dtk) |
|---|---|---|---|---|---|---|
| naive_requests | 0 | 1 | 27 | - | L1: User-Agent mengandung 'python-requests'; L1: tidak ada Accept-Language; L1: tidak ada header Sec-Fetch-* (bukan browser modern); L2: JS challenge tidak dijalankan (cookie js_ok tidak ada) | 0.0 |
| naive_headless | 0 | 1 | 20 | - | L1: User-Agent mengandung 'headlesschrome'; L2: JS challenge tidak dijalankan (cookie js_ok tidak ada) | 1.6 |
| stealth_fp_only | 3 | 4 | 12 | TERDETEKSI | L3: tidak ada interaksi mouse/scroll di halaman 1; L3: tidak ada interaksi mouse/scroll di halaman 2; L3: tidak ada interaksi mouse/scroll di halaman 3 | 2.4 |
| stealth_behaviour_only | 0 | beranda | 10 | - | L1: User-Agent mengandung 'headlesschrome' | 0.6 |
| stealth_full | 15 | - | 0 | TERDETEKSI | - | 144.9 |
| stealth_full | 15 | - | 0 | TERDETEKSI | - | 138.9 |
| stealth_full | 15 | - | 0 | TERDETEKSI | - | 133.7 |
