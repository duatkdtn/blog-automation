import requests

NAVER_CLIENT_ID = "GmBf8vCYZJ_AiqDDmsiU"
NAVER_CLIENT_SECRET = "qA560H5Ktj"

print("=== 네이버 쇼핑 API 테스트 ===\n")

# 1. 쇼핑 검색 API 테스트
print("1) 쇼핑 검색 API (shop.json) 테스트...")
res = requests.get(
    "https://openapi.naver.com/v1/search/shop.json",
    headers={
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    },
    params={"query": "골프채", "display": 3, "sort": "sim"},
    timeout=10
)
print(f"   Status: {res.status_code}")
print(f"   Response: {res.text[:300]}\n")

# 2. 데이터랩 쇼핑인사이트 API 테스트
print("2) 데이터랩 쇼핑인사이트 API 테스트...")
import json
body = {
    "startDate": "2026-08-01",
    "endDate": "2026-08-31",
    "timeUnit": "month",
    "category": [{"name": "골프", "param": ["50000006"]}]
}
res2 = requests.post(
    "https://openapi.naver.com/v1/datalab/shopping/categories",
    headers={
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json",
    },
    data=json.dumps(body),
    timeout=10
)
print(f"   Status: {res2.status_code}")
print(f"   Response: {res2.text[:300]}\n")

print("=== 테스트 완료 ===")
