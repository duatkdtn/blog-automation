import pickle, json, os, urllib.request
from google.auth.transport.requests import Request

base = os.path.dirname(__file__)
html_path = os.path.join(base, 'salary_calculator.html')
token_path = os.path.join(base, 'token.pickle')

with open(token_path, 'rb') as f:
    creds = pickle.load(f)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(token_path, 'wb') as f:
        pickle.dump(creds, f)

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

BLOG_ID = "7703234808905245526"
PAGE_ID = "5898536972465973565"
url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{PAGE_ID}"
data = json.dumps({"title": "연봉 실수령액 계산기", "content": html, "status": "live"}).encode('utf-8')
req = urllib.request.Request(url, data=data, method='PUT')
req.add_header('Authorization', f'Bearer {creds.token}')
req.add_header('Content-Type', 'application/json')
with urllib.request.urlopen(req) as resp:
    print("OK", resp.status)
