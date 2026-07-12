import pickle, json, sys, os

# HTML 내용 읽기
html_path = os.path.join(os.path.dirname(__file__), 'blogger_paste.txt')
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# 인증
token_path = os.path.join(os.path.dirname(__file__), 'token.pickle')
with open(token_path, 'rb') as f:
    creds = pickle.load(f)

if creds.expired and creds.refresh_token:
    from google.auth.transport.requests import Request
    creds.refresh(Request())
    with open(token_path, 'wb') as f:
        pickle.dump(creds, f)

# Blogger Pages API 호출
import urllib.request
BLOG_ID = "7703234808905245526"
url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages"

data = json.dumps({
    "title": "연봉 실수령액 계산기",
    "content": html_content,
    "status": "live"
}).encode('utf-8')

req = urllib.request.Request(url, data=data, method='POST')
req.add_header('Authorization', f'Bearer {creds.token}')
req.add_header('Content-Type', 'application/json')

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    print("✅ 페이지 발행 성공!")
    print(f"URL: {result.get('url')}")
    print(f"ID: {result.get('id')}")
except Exception as e:
    print(f"❌ 오류: {e}")

input("\n엔터를 누르면 창이 닫힙니다...")
