import pickle, json, os, urllib.request
from google.auth.transport.requests import Request

base = os.path.dirname(os.path.abspath(__file__))
token_path = os.path.join(base, 'token.pickle')

with open(token_path, 'rb') as f:
    creds = pickle.load(f)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(token_path, 'wb') as f:
        pickle.dump(creds, f)

with open(os.path.join(base, 'pyeong-calculator.html'), 'r', encoding='utf-8') as f:
    html = f.read()

BLOG_ID = "7703234808905245526"
url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages"

data = json.dumps({"title": "평수 계산기", "content": html, "status": "live"}).encode('utf-8')
req = urllib.request.Request(url, data=data, method='POST')
req.add_header('Authorization', f'Bearer {creds.token}')
req.add_header('Content-Type', 'application/json')

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    print("✅ 평수 계산기 페이지 발행 성공!")
    print(f"URL: {result.get('url')}")
    print(f"ID : {result.get('id')}")
    print(f"\n▶ blog_automation.py에 등록할 URL:\n   {result.get('url')}")
except Exception as e:
    print(f"❌ 오류: {e}")

input("\n엔터를 누르면 창이 닫힙니다...")
