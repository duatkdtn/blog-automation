import sys, os, hmac, hashlib, time
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, requests

ACCESS_KEY = config.COUPANG_ACCESS_KEY
SECRET_KEY = config.COUPANG_SECRET_KEY

print("COUPANG_ACCESS_KEY:", ACCESS_KEY[:6] + "***")

keyword = "무선이어폰"
method  = "GET"
path    = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
query   = urlencode({"keyword": keyword, "limit": 3, "subId": ""})

# 공식 문서 방식: datetime + method + path + query (? 없이!)
dt      = time.strftime('%y%m%d', time.gmtime()) + 'T' + time.strftime('%H%M%S', time.gmtime()) + 'Z'
message = dt + method + path + query

print("서명 메시지:", message[:90] + "...")

sig  = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={dt}, signature={sig}"

url = f"https://api-gateway.coupang.com{path}?{query}"
res = requests.get(
    url,
    headers={"Authorization": auth, "Content-type": "application/json;charset=UTF-8"},
    timeout=10
)

print("상태코드:", res.status_code)
print("응답내용:", res.text[:500])
