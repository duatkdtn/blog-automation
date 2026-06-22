import hmac, hashlib, base64, time, requests
from config import NAVER_AD_CUSTOMER_ID, NAVER_AD_ACCESS_LICENSE, NAVER_AD_SECRET_KEY

BASE_URL = "https://api.naver.com"
uri = "/keywordstool"

x_timestamp = str(round(time.time() * 1000))
method = "GET"

# 공식 샘플과 동일: secret_key.encode() (base64 디코딩 X)
sign = "%s.%s.%s" % (x_timestamp, method, uri)
signature_encrypted = hmac.new(
    NAVER_AD_SECRET_KEY.encode(),
    sign.encode(),
    hashlib.sha256
).digest()
x_signature = base64.b64encode(signature_encrypted).decode()

headers = {
    "X-API-KEY": NAVER_AD_ACCESS_LICENSE,
    "X-CUSTOMER": str(NAVER_AD_CUSTOMER_ID),   # 대문자!
    "X-Timestamp": x_timestamp,
    "X-Signature": x_signature,
}

params = {"hintKeywords": "정부지원금", "showDetail": "1"}
r = requests.get(BASE_URL + uri, headers=headers, params=params)
print("STATUS:", r.status_code)
print("RESPONSE:", r.text[:500])
