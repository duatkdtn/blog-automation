"""
근로장려금 계산기 페이지를 Blogger에 업데이트 (PUT)
기존 페이지를 수정하므로 URL이 그대로 유지됩니다.
"""
import pickle, json, os, urllib.request

from google.auth.transport.requests import Request

base = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(base, 'earned_income_calculator.html')
token_path = os.path.join(base, 'token.pickle')
BLOG_ID = "7703234808905245526"

# 토큰 로드
with open(token_path, 'rb') as f:
    creds = pickle.load(f)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(token_path, 'wb') as f:
        pickle.dump(creds, f)

headers = {
    'Authorization': f'Bearer {creds.token}',
    'Content-Type': 'application/json'
}

# ── 1. 기존 페이지 목록에서 ID 찾기 ─────────────────────────────────────────
print("📋 페이지 목록 조회 중...")
list_url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages?status=live"
req = urllib.request.Request(list_url)
req.add_header('Authorization', f'Bearer {creds.token}')

with urllib.request.urlopen(req) as resp:
    pages = json.loads(resp.read())

page_id = None
for page in pages.get('items', []):
    print(f"  - {page['title']} → {page['url']}")
    if '근로장려금' in page['title'] or 'earned-income' in page.get('url', ''):
        page_id = page['id']
        print(f"    ✅ 대상 페이지 발견! ID: {page_id}")

if not page_id:
    print("❌ 근로장려금 계산기 페이지를 찾지 못했습니다.")
    input("\n엔터를 누르면 창이 닫힙니다...")
    exit()

# ── 2. HTML 읽기 ─────────────────────────────────────────────────────────────
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

print(f"\n📄 HTML 크기: {len(html):,} bytes")

# ── 3. 페이지 업데이트 (PUT) ─────────────────────────────────────────────────
print("\n🔄 페이지 업데이트 중...")
update_url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{page_id}"

data = json.dumps({
    "kind": "blogger#page",
    "id": page_id,
    "title": "근로장려금 계산기",
    "content": html,
    "status": "live"
}).encode('utf-8')

req = urllib.request.Request(update_url, data=data, method='PUT')
req.add_header('Authorization', f'Bearer {creds.token}')
req.add_header('Content-Type', 'application/json')

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    print("✅ 업데이트 성공!")
    print(f"URL: {result.get('url')}")
    print(f"\n👉 브라우저에서 확인: https://www.hijanee.com/p/earned-income-calculator.html")
except Exception as e:
    print(f"❌ 오류: {e}")

input("\n엔터를 누르면 창이 닫힙니다...")
