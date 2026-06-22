import requests

keyword = "손예진"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

urls = [
    ("A", "https://ac.search.naver.com/nx/ac", {"q": keyword, "q_enc": "UTF-8", "st": "11", "frm": "nv", "r_format": "json", "r_enc": "UTF-8"}),
    ("B", "https://ac.search.naver.com/nx/ac", {"q": keyword, "q_enc": "UTF-8", "st": "100", "frm": "nv", "r_format": "json", "r_enc": "UTF-8", "con": "1"}),
    ("C", "https://ac.naver.com/ac", {"q": keyword, "q_enc": "UTF-8", "st": "11", "frm": "nv", "r_format": "json", "r_enc": "UTF-8"}),
]

for name, url, params in urls:
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        print(f"[{name}] STATUS: {r.status_code} | 응답: {repr(r.text[:200])}")
    except Exception as e:
        print(f"[{name}] 실패: {e}")
