| Crawler | Halaman berhasil (dari 15) | Diblokir di halaman | Skor risiko | Alasan deteksi | Waktu (dtk) |
|---|---|---|---|---|---|
| naive_requests | 0 | 1 | 27 | L1: User-Agent mengandung 'python-requests'; L1: tidak ada Accept-Language; L1: tidak ada header Sec-Fetch-* (bukan browser modern); L2: JS challenge tidak dijalankan (cookie js_ok tidak ada) | 0.0 |
| naive_headless | 0 | 1 | 20 | L1: User-Agent mengandung 'headlesschrome'; L2: JS challenge tidak dijalankan (cookie js_ok tidak ada) | 1.5 |
| stealth_fp_only | 3 | 4 | 12 | L3: tidak ada interaksi mouse/scroll di halaman 1; L3: tidak ada interaksi mouse/scroll di halaman 2; L3: tidak ada interaksi mouse/scroll di halaman 3 | 2.4 |
| stealth_behaviour_only | 0 | beranda | 10 | L1: User-Agent mengandung 'headlesschrome' | 0.7 |
| stealth_full | 15 | - | 0 | - | 134.7 |
| stealth_full | 15 | - | 0 | - | 161.4 |
| stealth_full | 15 | - | 0 | - | 155.2 |
