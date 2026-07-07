# ================================================
# 브랜드커넥트 API 테스트 스크립트
# 1. 상품 검색
# 2. 링크 자동 발급
# ================================================

import requests
import json

# ★★★ 여기에 메모장의 쿠키 전체 붙여넣기 ★★★
COOKIE = "NAC=ZBzHBARAj4C9; NNB=RTEFQDROQ6XWS; ASID=d3cac9be0000019cd70c26ed00000021; _fbp=fb.1.1773134426029.81653091529076788; nstore_session=uvH8U9mW39VPp59Ftdv+xDyw; nstore_pagesession=jl52LsqWvXAfMlsLvKV-242181; NACT=1; page_uid=jCVZYsqXKZEdkq02HqN-498693; nid_inf=-1274501785; NID_AUT=TFuamUQvU7Lj36inD0DNWdHFP6ZCzgrN2YCOzn8WOhJ/uXhjMTvjHrNwbPmUS0RF; cto_bundle=UQUuM19FRGN3THhzZmlYeVg3U3BiZWNteDZWcWlCOWEyeURyVXhDUUVuMDl2N09adVp3OEN4ZU5GeGpqMkY2TmJWeUg3clc1WlRmcUhwbkw4Y2NiU0RLYUpIV1RtOEpkeTZqdXg5Rno1YTY0NFlETndXc1UzdFM5MWdxJTJGZmQlMkZhT2piZll4WkpnUlVWVCUyQkM3OGRlTW4lMkI0TnZ2ZyUzRCUzRA; NID_SES=AAABrxlqo4tXtSNEYE2zRHyF3RejOH3Knfv6v8pX/Niit46AgGV6qK32H4kkz5vNY7g1aFrdk35P6zEI0kp/Vln3loqGSBnqbhK41M+PWBrXIoe1P1+y3cAiHUI7MRB/FxVeyBm+ZmEz115exHb94RVzNF2wErk0XpTU/p65jRpUSJtI4m/2bwvd72K6/R8xldqkCTyTRaa0Zfvo3eCMYTeCjaA9vjXP9gjgcD7Nd7pNNZvLznxfvu68XLAj/DVE1CIiH7NMfiYYbRw93vDt9NUBlZZIJfSbvif7Aic1HKPIEhvy7/o5V89PaCN+V/5vCdZ+iThQxLXiJ0nfXuNBd8l6xx4Bq4gm97qKcwtB/7P2hKV/8ZeParKxcxLL4Kd8nih5miFxqciVOi3td59jXHMjudtDrYrbUGAFm14bumJXfDeTMdgSgkexORWFCOoLcSpCGrffDA8FwE/QHWBtImtW9QwSQ+tieDp8TDSxB7xUCAN879wujb3r8ogvORFz/2ijmwjDDAceJWQ0Rqcng6Dyo7BrGD6Inoi1VNz2qe+mCbd2PazUaqQikR6M4CiPS3B9Nw==; BUC=2AFnD1TuxDzNnfqkIk1A5BdoAMBntG5wqnlh3c6blcg=; JSESSIONID=D6790F252048356B163742F2CC495FFB"

# ★★★ 검색할 상품명 ★★★
SEARCH_QUERY = "에어컨"

# ─────────────────────────────────────────────────

HEADERS = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Referer": "https://brandconnect.naver.com/",
    "Accept": "application/json, text/plain, */*",
    "x-space-id": "962414636778176",
    "Origin": "https://brandconnect.naver.com",
}


def search_products(query):
    """브랜드커넥트 상품 검색"""
    print(f"\n🔍 '{query}' 검색 중...")
    res = requests.get(
        "https://gw-brandconnect.naver.com/affiliate/query/affiliate-products/search-by-query",
        headers=HEADERS,
        params={"query": query, "limit": 10},
        timeout=10
    )
    if res.status_code == 401:
        print("❌ 쿠키 만료! 브랜드커넥트 재로그인 후 쿠키 다시 복사하세요.")
        return []
    if res.status_code != 200:
        print(f"❌ 검색 실패: {res.status_code}")
        return []

    data = res.json().get("data", [])
    print(f"✅ 검색 결과: {len(data)}개")
    return data


def issue_link(affiliate_product_id):
    """링크 자동 발급"""
    print(f"\n🔗 링크 발급 중... (상품ID: {affiliate_product_id})")
    res = requests.post(
        "https://gw-brandconnect.naver.com/affiliate/command/affiliate-urls",
        headers={**HEADERS, "Content-Type": "application/json"},
        params={"affiliateProductId": affiliate_product_id},
        json={},
        timeout=10
    )
    if res.status_code == 401:
        print("❌ 쿠키 만료!")
        return None
    if res.status_code != 200:
        print(f"❌ 링크 발급 실패: {res.status_code} - {res.text}")
        return None

    result = res.json()
    url = result.get("url", "")
    print(f"✅ 링크 발급 성공!")
    print(f"   발급된 URL: {url}")
    return url


def main():
    if not COOKIE:
        print("❌ COOKIE가 비어있어요! 위에 쿠키를 붙여넣으세요.")
        return

    # ── 1. 상품 검색 ──────────────────────────────
    products = search_products(SEARCH_QUERY)
    if not products:
        return

    print("\n" + "="*60)
    print("📦 검색된 상품 목록:")
    print("="*60)
    for i, p in enumerate(products[:5]):
        name  = p.get("productName", "")
        price = p.get("salePrice", 0)
        rate  = p.get("commissionRate", 0)
        pid   = p.get("id", "")
        print(f"\n[{i+1}번] {name}")
        print(f"     가격: {int(price):,}원 | 수수료: {rate}% | ID: {pid}")

    # ── 2. 전체 응답 필드 확인 (첫 번째 상품) ────
    print("\n" + "="*60)
    print("🔎 첫 번째 상품 전체 데이터 (필드 확인용):")
    print("="*60)
    print(json.dumps(products[0], ensure_ascii=False, indent=2))

    # ── 3. 1번 상품 링크 발급 ─────────────────────
    print("\n" + "="*60)
    print("🔗 1번 상품 링크 발급 테스트:")
    print("="*60)
    pid = products[0].get("id", "")
    url1 = issue_link(pid)

    # ── 4. 2번 상품 링크 발급 (동일 상품 재발급 테스트) ──
    print("\n" + "="*60)
    print("🔄 1번 상품 링크 재발급 테스트 (같은 링크 나오는지):")
    print("="*60)
    url2 = issue_link(pid)

    # ── 5. 결과 비교 ──────────────────────────────
    print("\n" + "="*60)
    if url1 and url2:
        if url1 == url2:
            print("✅ 동일 링크 확인! → 자동화 가능!")
        else:
            print("⚠️ 링크가 달라요 → 확인 필요")
        print(f"   1차: {url1}")
        print(f"   2차: {url2}")
    print("="*60)


if __name__ == "__main__":
    main()
