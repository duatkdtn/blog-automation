# ================================================
# 쇼핑커넥트 자동화 v4.0
# 흐름: 카테고리 → 5개 상품 → Claude 글 작성
#       → 이메일 1통 (네이버 블로그 복붙용)
# ================================================

import os, re, sys, json, random, requests, smtplib
# Windows 콘솔 UTF-8 강제 설정
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── 환경변수 ──────────────────────────────────────
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    def _get(key, default=None):
        return os.environ.get(key) or getattr(config, key, default)
except Exception:
    def _get(key, default=None):
        return os.environ.get(key, default)

NAVER_CLIENT_ID     = _get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = _get("NAVER_CLIENT_SECRET")
CLAUDE_API_KEY      = _get("CLAUDE_API_KEY")
CLAUDE_MODEL        = _get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GMAIL_ADDRESS       = _get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD  = _get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT     = _get("EMAIL_RECIPIENT", "duatkdtn@gmail.com")
def _refresh_jsessionid(base_cookie):
    """NID_AUT + NID_SES로 브랜드커넥트 접속해서 새 JSESSIONID 자동 발급"""
    try:
        import requests as _req, re as _re
        # NID_AUT, NID_SES, NNB, NAC만 추출 (장기 쿠키)
        keep = ["NID_AUT", "NID_SES", "NNB", "NAC", "NACT", "nid_inf"]
        parts = [p.strip() for p in base_cookie.split(";") if p.strip().split("=")[0].strip() in keep]
        if not parts:
            return base_cookie
        short_cookie = "; ".join(parts)
        r = _req.get(
            "https://brandconnect.naver.com/",
            headers={
                "Cookie": short_cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
            },
            timeout=10,
            allow_redirects=True
        )
        new_cookies = {}
        for sc in r.headers.get("Set-Cookie", "").split(","):
            m = _re.match(r"\s*([^=]+)=([^;]+)", sc.strip())
            if m:
                new_cookies[m.group(1).strip()] = m.group(2).strip()
        # 기존 쿠키에서 JSESSIONID 교체
        existing = {}
        for p in base_cookie.split(";"):
            p = p.strip()
            if "=" in p:
                k, v = p.split("=", 1)
                existing[k.strip()] = v.strip()
        existing.update(new_cookies)
        result = "; ".join(f"{k}={v}" for k, v in existing.items())
        if "JSESSIONID" in new_cookies:
            print(f"   ✅ JSESSIONID 자동 갱신 완료")
        return result
    except Exception as e:
        print(f"   ⚠️ JSESSIONID 갱신 실패: {e}")
        return base_cookie

def _get_naver_cookie_auto():
    """config.py 쿠키 로드 후 JSESSIONID 자동 갱신"""
    base = _get("NAVER_COOKIE", "")
    if not base:
        print("   ⚠️ NAVER_COOKIE 없음 - config.py에 쿠키 입력 필요")
        return ""
    return _refresh_jsessionid(base)

NAVER_COOKIE = _get_naver_cookie_auto()

def refresh_naver_cookie():
    """쿠키 재추출"""
    global NAVER_COOKIE
    NAVER_COOKIE = _get_naver_cookie_auto()
    return bool(NAVER_COOKIE)
NAVER_SPACE_ID      = _get("NAVER_SPACE_ID", "962414636778176")

PUBLISHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published_products.txt")
LAST_RUN_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shopping_last_run.txt")
NAVER_BLOG_URL = "https://blog.naver.com/janee_item"



# ── 네이버 데이터랩 쇼핑 카테고리 + 세부 키워드 ──
# v6.0: DataLab 실측으로 카테고리 ID 수정 (2026-09-02)
# 실측 결과: 50000007=스포츠/레저, 50000006=식품, 50000003=디지털/가전
#             50000000=패션의류, 50000002=화장품/미용
def _food_keywords():
    """명절 기간엔 선물세트, 나머지엔 일반 식품 키워드 반환"""
    today = datetime.now()
    m, d = today.month, today.day
    # 설날: 1/1 ~ 1/28 (2026 설날 1/29)
    seollal = (m == 1 and d <= 28)
    # 추석: 9/1 ~ 9/27 (2026 추석 9/25, 연휴 9/23~27)
    chuseok = (m == 9 and d <= 27)
    if seollal or chuseok:
        return [
            # 육류
            "한우선물세트", "갈비선물세트", "흑돼지선물세트",
            # 수산물
            "굴비선물세트", "전복선물세트", "새우선물세트", "오징어선물세트", "수산물선물세트",
            # 건강식품
            "홍삼선물세트", "인삼선물세트", "건강즙선물세트", "영양제선물세트",
            # 농산물/전통식품
            "과일선물세트", "꿀선물세트", "버섯선물세트", "한과선물세트",
            "김선물세트", "김치선물세트", "장류선물세트", "참기름선물세트",
            # 가공식품
            "스팸선물세트", "참치선물세트", "식용유선물세트",
            # 음료/기호식품
            "커피선물세트", "차선물세트",
            # 뷰티/생활
            "화장품선물세트",
            # 기타
            "추석선물세트", "건강식품선물세트", "올리브오일선물세트", "와인선물세트",
        ]
    return [
        "단백질보충제", "밀키트", "건강즙", "커피원두",
        "냉동과일", "견과류", "홍삼", "다이어트식품",
        "그래놀라", "두유"
    ]

CATEGORIES = [
    {"name": "스포츠/레저", "id": "50000007", "keywords": [
        # fallback용 (DataLab 실패 시 사용)
        "골프채", "골프백", "골프거리측정기", "골프웨어", "골프화",
        "텐트", "캠핑의자", "캠핑버너", "캠핑랜턴", "타프"
    ]},
    {"name": "식품", "id": "50000006", "keywords": []},  # _food_keywords()로 동적 처리
    {"name": "디지털/가전", "id": "50000003", "keywords": [
        # fallback용
        "갤럭시탭", "아이패드", "갤럭시워치", "애플워치", "다이슨청소기",
        "삼성냉장고", "LG냉장고", "에어컨", "맥북", "삼성모니터"
    ]},
    {"name": "생활/건강", "id": "50000008", "keywords": [
        "공기청정기", "안마의자", "건강식품", "유산균", "비타민",
        "정수기", "식기세척기", "음식물처리기", "청소기", "로봇청소기",
        "마사지건", "혈압계", "체중계", "가습기", "제습기",
        "전기요", "족욕기", "안마기", "혈당계", "체온계"
    ]},
    {"name": "가구/인테리어", "id": "50000004", "keywords": [
        "소파", "침대", "식탁", "책상", "옷장",
        "조명", "커튼", "러그", "행거", "화장대",
        "드레스룸", "좌식소파", "책장", "수납박스", "벽시계",
        "아트포스터", "디퓨저", "캔들", "화분", "수납선반"
    ]},
]

# 식품 카테고리 keywords를 실행 시점에 동적으로 채움
for _c in CATEGORIES:
    if _c["name"] == "식품":
        _c["keywords"] = _food_keywords()
        break

NAVER_HEADERS = lambda: {
    "X-Naver-Client-Id":     NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    "Content-Type":          "application/json",
}


# ── 1단계: 데이터랩으로 인기 카테고리 찾기 ───────

def get_trending_category():
    """
    네이버 데이터랩 쇼핑인사이트로 최근 1주 가장 많이 검색된 카테고리 반환
    반환: {"name": "디지털/가전", "id": "50000003"} 또는 None
    """
    today = datetime.now()
    end   = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    body = {
        "startDate": start,
        "endDate":   end,
        "timeUnit":  "date",
        "category":  [{"name": c["name"], "param": [c["id"]]} for c in CATEGORIES],
        "device": "", "ages": [], "gender": ""
    }

    try:
        res = requests.post(
            "https://openapi.naver.com/v1/datalab/shopping/categories",
            headers=NAVER_HEADERS(),
            json=body, timeout=15
        )
        res.raise_for_status()
        results = res.json().get("results", [])

        # 각 카테고리의 최근 ratio 평균 계산
        scores = []
        for r in results:
            data = r.get("data", [])
            if not data:
                continue
            avg = sum(d.get("ratio", 0) for d in data) / len(data)
            scores.append({"name": r["title"], "score": avg})

        if not scores:
            print("⚠️ 데이터랩 응답 없음")
            return None

        # 가장 높은 카테고리 선택
        best = max(scores, key=lambda x: x["score"])
        # CATEGORIES에서 id 찾기
        matched = next((c for c in CATEGORIES if c["name"] == best["name"]), None)
        if matched:
            print(f"📊 인기 카테고리: {matched['name']} (ratio: {best['score']:.1f})")
            return matched

        return None

    except Exception as e:
        print(f"⚠️ 데이터랩 API 오류: {e}")
        return None


# ── 2단계: 네이버 쇼핑 API로 상품 가져오기 ──────

def get_trending_keywords_from_datalab(category):
    """
    DataLab 쇼핑인사이트에서 카테고리 인기 검색어 TOP 10 크롤링
    반환: list of keyword strings, 또는 [] (실패 시)
    """
    today = datetime.now()
    end   = (today - timedelta(days=1)).strftime("%Y%m%d")
    start = (today - timedelta(days=7)).strftime("%Y%m%d")

    try:
        _dl_headers = {
            "Referer":          "https://datalab.naver.com/shoppingInsight/sCategory.naver",
            "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept":           "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        if NAVER_COOKIE:
            _dl_headers["Cookie"] = NAVER_COOKIE
        res = requests.post(
            "https://datalab.naver.com/shoppingInsight/getKeywordRank.naver",
            headers=_dl_headers,
            data={
                "cid":       category["id"],
                "timeUnit":  "date",
                "startDate": start,
                "endDate":   end,
                "age":       "",
                "sex":       "",
                "device":    "",
                "topN":      "10",
            },
            timeout=10,
        )
        if res.status_code == 200:
            try:
                data = res.json()
                if isinstance(data, list):
                    data = data[0] if data else {}
                result = data.get("ranks", [])
                keywords = [item.get("keyword", "") for item in result if item.get("keyword")]
                if keywords:
                    return keywords
            except Exception as je:
                print(f"   ℹ️ DataLab JSON 파싱 실패: {je} / 응답: {res.text[:200]}")
    except Exception as e:
        print(f"   ℹ️ DataLab 크롤링 실패: {e}")

    return []


def get_top_product(category, specific_keyword=None):
    """
    Brand Connect API로 상품 검색 → 반환
    specific_keyword: 지정하면 해당 키워드만 사용 (키워드 순환용)
    반환: list of product dict
    """
    if specific_keyword:
        keywords_to_try = [specific_keyword]
    else:
        keywords_to_try = category.get("keywords", [category["name"]])[:]
        random.shuffle(keywords_to_try)

    if not NAVER_COOKIE:
        print("   NAVER_COOKIE 없음 - 빈 결과 반환")
        return []

    bc_headers = {
        "Cookie": NAVER_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://brandconnect.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://brandconnect.naver.com",
        "x-space-id": NAVER_SPACE_ID,
    }

    items = []
    for query in keywords_to_try[:3]:  # 최대 3개 키워드 시도
        print(f"   Brand Connect 검색: {query}")
        try:
            res = requests.get(
                "https://gw-brandconnect.naver.com/affiliate/query/affiliate-products/search-by-query",
                headers=bc_headers,
                params={"query": query, "limit": 20},
                timeout=10,
            )
            if res.status_code == 200:
                data = res.json().get("data", [])
                for p in data:
                    name  = p.get("productName", "")
                    price = str(p.get("discountedSalePrice", 0) or p.get("salePrice", 0))
                    link  = p.get("productUrl", "") or p.get("url", "")
                    img   = p.get("representativeProductImageUrl", "") or p.get("imageUrl", "") or p.get("thumbnailUrl", "")
                    pid   = str(p.get("id", "") or p.get("productNo", "") or p.get("productId", ""))
                    rate  = p.get("commissionRate", 0)
                    review = p.get("reviewInfo", {})
                    price_val = int(p.get("discountedSalePrice", 0) or p.get("salePrice", 0) or 0)
                    if name and price_val >= 30000 and float(rate) >= 10:
                        items.append({
                            "title":          name,
                            "lprice":         price,
                            "link":           link,
                            "image":          img,
                            "productId":      pid,
                            "commissionRate": rate,
                            "reviewCount":    review.get("totalReviewCount", 0),
                            "reviewScore":    review.get("averageReviewScore", 0),
                            "keyword":        query,
                        })
                if items:
                    print(f"   Brand Connect {len(items)}개 수집")
                    break
            elif res.status_code == 401:
                print("   Brand Connect 쿠키 만료")
                break
            elif res.status_code == 403:
                print("   Brand Connect 쿠키 만료 → F12에서 쿠키 갱신 필요")
                break
        except Exception as e:
            print(f"   Brand Connect 오류: {e}")

    return items


# ── 3단계: 중복 체크 ──────────────────────────────

def check_already_ran_today():
    """오늘 이미 실행됐는지 확인"""
    from datetime import date
    try:
        with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
            last = f.read().strip()
        return last == str(date.today())
    except:
        return False

def save_run_today():
    """오늘 실행 기록 저장"""
    from datetime import date
    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        f.write(str(date.today()))

def load_published_ids():
    if not os.path.exists(PUBLISHED_FILE):
        return set()
    ids = set()
    with open(PUBLISHED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if parts:
                ids.add(parts[0].strip())
    return ids


def save_published_product(product_id, product_name):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(PUBLISHED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{product_id}|{product_name}|{today}\n")
    print(f"✅ 발행 기록 저장: {product_name}")





def find_new_product():
    """
    데이터랩 인기 카테고리 → 쇼핑 검색 → 브랜드커넥트 우선 선택
    반환: (category, product, bc_product) 또는 (None, None, None)
    """
    published_ids = load_published_ids()
    print(f"📋 발행된 상품 수: {len(published_ids)}개")

    # 인기 카테고리 먼저 시도, 실패하면 순서대로
    trending = get_trending_category()
    category_order = ([trending] if trending else []) + \
                     [c for c in CATEGORIES if not trending or c["id"] != trending["id"]]

    for category in category_order:
        print(f"🔍 카테고리 검색: {category['name']}")
        products = get_top_product(category)

        # 미발행 상품만 필터링
        new_products = []
        for product in products:
            pid = str(product.get("productId", ""))
            if pid and pid not in published_ids:
                new_products.append(product)
            else:
                print(f"   └ 이미 발행됨: {product.get('title','')[:20]}")

        if not new_products:
            continue

        print(f"   └ 미발행 상품 {len(new_products)}개 → 브랜드커넥트 검색 중...")

        # 브랜드커넥트 우선 선택
        if NAVER_COOKIE:
            bc_product, bc_info = find_best_brandconnect(new_products)
            if bc_product:
                print(f"✅ 브랜드커넥트 상품 선택: {bc_product['title'][:30]}")
                return category, bc_product, bc_info

        # 브랜드커넥트 없으면 첫 번째 미발행 상품
        product = new_products[0]
        print(f"✅ 일반 상품 선택: {product['title'][:30]}")
        return category, product, None

    print("⚠️ 새 상품 없음")
    return None, None, None


def find_new_products(count=9):
    """
    여러 카테고리에서 미발행 상품 최대 count개 반환
    반환: list of (category, product, bc_product)
    """
    published_ids = load_published_ids()
    print(f"📋 발행된 상품 수: {len(published_ids)}개")

    trending = get_trending_category()
    category_order = ([trending] if trending else []) + \
                     [c for c in CATEGORIES if not trending or c["id"] != trending["id"]]

    results = []
    used_ids = set(published_ids)  # 이번 실행 중 선택된 것도 중복 방지

    for category in category_order:
        if len(results) >= count:
            break

        print(f"\n🔍 [{len(results)+1}/{count}] 카테고리: {category['name']}")
        products = get_top_product(category)

        new_products = []
        for product in products:
            pid = str(product.get("productId", ""))
            if pid and pid not in used_ids:
                new_products.append(product)
            else:
                print(f"   └ 스킵: {product.get('title','')[:20]}")

        if not new_products:
            print("   └ 미발행 상품 없음, 다음 카테고리로")
            continue

        # 브랜드커넥트 우선
        selected_product = None
        selected_bc = None

        if NAVER_COOKIE:
            print(f"   └ 브랜드커넥트 검색 중...")
            bc_product, bc_info = find_best_brandconnect(new_products)
            if bc_product:
                selected_product = bc_product
                selected_bc = bc_info
                pid = str(selected_product.get("productId", ""))
                print(f"   ✅ 브랜드커넥트 선택: {selected_product.get('title','')[:25]}")

        if not selected_product:
            print(f"   ⚠️ 브랜드코넥트 상품 없음 - 카테고리 스킵")
            continue

        used_ids.add(pid)
        results.append((category, selected_product, selected_bc))

    print(f"\n📦 총 {len(results)}개 상품 선택 완료")
    return results


# ── 3.5단계: 브랜드커넥트 상품 검색 ────────────────

def check_brandconnect(product_name):
    """
    브랜드커넥트 내부 API로 상품 검색
    반환: 수수료율 가장 높은 상품 dict 또는 None
    """
    cookie = NAVER_COOKIE
    if not cookie:
        print("   ℹ️ NAVER_COOKIE 없음 - 브랜드커넥트 스킵")
        return None

    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Referer": "https://brandconnect.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://brandconnect.naver.com",
        "x-space-id": NAVER_SPACE_ID,
    }

    try:
        res = requests.get(
            "https://gw-brandconnect.naver.com/affiliate/query/affiliate-products/search-by-query",
            headers=headers,
            params={"query": product_name, "limit": 100},
            timeout=10
        )
        if res.status_code == 401:
            print("   ⚠️ 브랜드커넥트 쿠키 만료 (재로그인 필요)")
            return None
        if res.status_code == 403:
            print("   ℹ️ 브랜드커넥트 접근 불가 (해외 IP 차단) - 스킵")
            return None
        res.raise_for_status()

        data = res.json().get("data", [])
        if not data:
            print(f"   └ 브랜드커넥트 결과 없음")
            return None

        # 가중치 점수로 최적 상품 선택 (수수료 50% + 리뷰수 30% + 별점 20%)
        def bc_score(p):
            rate     = float(p.get("commissionRate", 0))
            review   = p.get("reviewInfo", {})
            cnt      = min(float(review.get("totalReviewCount", 0)), 10000) / 10000
            score_rv = float(review.get("averageReviewScore", 0)) / 5.0
            return rate * 0.5 + cnt * 30 * 0.3 + score_rv * 100 * 0.2

        # 수수료 10% 이상만 선택
        high_commission = [p for p in data if float(p.get("commissionRate", 0)) >= 10]
        if not high_commission:
            print(f"   └ 수수료 10% 이상 상품 없음 - 스킵")
            return None
        # 리뷰 1개 이상인 상품 우선 선택, 없으면 수수료 10%+ 전체에서 선택
        reviewed = [p for p in high_commission if p.get("reviewInfo", {}).get("totalReviewCount", 0) > 0]
        pool = reviewed if reviewed else high_commission

        best = max(pool, key=bc_score)
        rate   = float(best.get("commissionRate", 0))
        review = best.get("reviewInfo", {})
        cnt    = review.get("totalReviewCount", 0)
        score  = review.get("averageReviewScore", 0)
        print(f"   └ ✅ 브랜드커넥트 발견: {best.get('productName','')[:30]}")
        print(f"      수수료 {rate}% | 리뷰 {cnt}개 | 별점 {score}")
        return best

    except Exception as e:
        print(f"   ⚠️ 브랜드커넥트 오류: {e}")
        return None


def find_best_brandconnect(products):
    """
    상품 리스트에서 브랜드커넥트에 있는 것 중 수수료율 가장 높은 것 반환
    반환: (product, bc_product) 또는 (None, None)
    """
    best_pair = None
    best_rate = -1

    for product in products:
        name = product.get("title", "")
        bc = check_brandconnect(name)
        if bc:
            rate = float(bc.get("commissionRate", 0))
            if rate > best_rate:
                best_rate = rate
                best_pair = (product, bc)

    return best_pair if best_pair else (None, None)


# ── 4단계: 이미지 수집 (최대 4장) ────────────────

def get_product_images(product):
    """
    상품 이미지 최대 4장 수집
    - 1장: 네이버 쇼핑 API 상품 썸네일
    - 나머지: 네이버 이미지 검색으로 추가 수집
    반환: list of image URLs (최대 4개)
    """
    images = []

    # 1장: 쇼핑 API 썸네일
    thumb = product.get("image", "")
    if thumb:
        images.append(thumb)

    # 나머지: 네이버 이미지 검색
    product_name = product.get("title", "")
    if product_name and len(images) < 4:
        try:
            res = requests.get(
                "https://openapi.naver.com/v1/search/image",
                headers={
                    "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                },
                params={"query": product_name, "display": 6, "sort": "sim", "filter": "large"},
                timeout=10
            )
            res.raise_for_status()
            items = res.json().get("items", [])
            for item in items:
                url = item.get("link", "")
                if url and url not in images:
                    images.append(url)
                if len(images) >= 4:
                    break
        except Exception as e:
            print(f"⚠️ 이미지 검색 오류: {e}")

    print(f"🖼️ 이미지 {len(images)}장 수집")
    return images[:4]


# ── 5단계: Claude로 글 작성 ──────────────────────

def generate_shopping_post(category, product):
    """
    Claude Haiku로 샘플 형식에 맞는 쇼핑 추천 글 작성
    반환: (seo_titles, post_body, hashtags) 또는 (None, None, None)
    """
    if not CLAUDE_API_KEY:
        print("⚠️ Claude API 키 없음")
        return None, None, None

    name  = product.get("title", "")
    brand = product.get("brand", "")
    maker = product.get("maker", "")
    price = product.get("lprice", "")
    cat1  = product.get("category1", category["name"])
    cat2  = product.get("category2", "")

    brand_info = brand or maker or "브랜드 미상"

    prompt = f"""너는 네이버 쇼핑 블로그에 제휴 마케팅 상품 추천 글을 쓰는 전문 작가야.

상품 정보:
- 상품명: {name}
- 브랜드: {brand_info}
- 카테고리: {cat1} > {cat2}

글쓰기 규칙:
- ~더라고요, ~이에요, ~해요 톤 유지 (친근하고 자연스럽게)
- 마크다운 기호 (#, ##, **, *, ---, ===) 절대 사용 금지
- [소제목1:] 같은 대괄호 태그 절대 사용 금지
- 소제목은 이모지 없이 텍스트만 작성
- 소제목 아래 내용은 반드시 3문단으로 작성
- 각 문단은 3~4문장으로 충분히 상세하게 작성

아래 형식을 정확히 지켜서 써줘:

---SEO_TITLES_START---
1. [구매확률↑↑] (제품명 직접 검색형 - 구매 결정 직전 유저 타겟, 제품명+구매/추천/필독 포함)
2. [구매확률↑] (가격/가성비 비교형 - 최저가·가성비 키워드 포함)
3. [후기형] (사용 후기/경험형 - 실사용 느낌·솔직한 후기 키워드)
4. [정보형] (정보 탐색형 - 카테고리 키워드 중심, 유입량 높음)
5. [감성형] (감성/공감형 - 생활 공감 스토리 키워드)
---SEO_TITLES_END---

---BODY_START---
이 포스팅은 제휴 마케팅 활동의 일환으로, 판매 발생 시 수수료를 제공받습니다.

(공감형 도입부: 이 상품이 왜 필요한지 생활 속 불편함 공감으로 시작, 2~3문단)

가격은 시기에 따라 변동될 수 있습니다.
👇 현재 가격 확인하기
━━━━━━━━━━━━━━━━━━

(첫 번째 소제목 텍스트만 - 이모지/대괄호 없이)
(3문단, 각 문단 3~4문장)

(두 번째 소제목 텍스트만 - 이모지/대괄호 없이)
(3문단, 각 문단 3~4문장)

(세 번째 소제목 텍스트만 - 이모지/대괄호 없이)
(3문단, 각 문단 3~4문장)

━━━━━━━━━━━━━━━━━━

(마무리: 어떤 사람에게 추천하는지 구체적으로, 1~2문단)

재고와 할인 여부는 아래에서 확인할 수 있습니다.
👇 오늘 최저가 확인하기
---BODY_END---

---TAGS_START---
#태그1 #태그2 #태그3 #태그4 #태그5 #태그6 #태그7 #태그8
---TAGS_END---"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY, timeout=120)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()

        # SEO 제목 파싱
        titles_match = re.search(r"---SEO_TITLES_START---(.+?)---SEO_TITLES_END---", raw, re.DOTALL)
        seo_titles = titles_match.group(1).strip() if titles_match else ""

        # 본문 파싱 (BODY_END 없으면 TAGS_START 전까지)
        body_match = re.search(r"---BODY_START---(.+?)---BODY_END---", raw, re.DOTALL)
        if not body_match:
            body_match = re.search(r"---BODY_START---(.+?)---TAGS_START---", raw, re.DOTALL)
        post_body = body_match.group(1).strip() if body_match else ""

        # 본문 클린업: 마크다운·태그 자동 제거
        post_body = re.sub(r'\*\*(.+?)\*\*', r'\1', post_body)          # **볼드** → 볼드
        post_body = re.sub(r'\[소제목\d+\s*:\s*([^\]]+)\]', r'\1', post_body)  # [소제목1: 내용] → 내용만
        post_body = re.sub(r'✅\s*\([^)]+\)', '', post_body)              # ✅ (안내문구) 제거
        post_body = re.sub(r'^#+\s*', '', post_body, flags=re.MULTILINE)    # # 마크다운 제거
        post_body = re.sub(r'\n{3,}', '\n\n', post_body).strip()

        if not post_body:
            print(f"⚠️ 파싱 실패 - raw 앞부분: {raw[:300]}")

        # 해시태그 파싱
        tags_match = re.search(r"---TAGS_START---(.+?)---TAGS_END---", raw, re.DOTALL)
        hashtags = tags_match.group(1).strip() if tags_match else ""

        return seo_titles, post_body, hashtags

    except Exception as e:
        print(f"⚠️ Claude 오류: {e}")
        return None, None, None


# ── 6단계: 이메일 발송 ───────────────────────────

def send_shopping_email_bulk(items):
    """5개 상품을 하나의 이메일로 발송 (네이버 블로그 복붙용)"""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail 환경변수 없음")
        return
    if not items:
        print("⚠️ 발송할 상품 없음")
        return

    kst       = datetime.utcnow() + timedelta(hours=9)
    today_str = kst.strftime("%Y년 %m월 %d일")
    now_str   = kst.strftime("%Y-%m-%d %H:%M")
    colors    = ["#3F51B5", "#7B1FA2", "#00796B", "#E65100", "#C62828", "#1565C0", "#558B2F", "#6A1B9A", "#AD1457"]

    cards_html = ""
    for i, item in enumerate(items):
        cat          = item["category"]
        product      = item["product"]
        bc_product   = item.get("bc_product")
        images       = item.get("images", [])
        seo_titles   = item.get("seo_titles", "")
        post_body    = item.get("post_body", "")
        hashtags     = item.get("hashtags", "")
        pub_time_str = item.get("pub_time_str", f"{6 + i*3:02d}:00")

        color = colors[i % len(colors)]
        num   = i + 1
        name  = product.get("title", "")
        price = product.get("lprice", "")
        try:
            price_fmt = f"{int(price):,}원" if price else "가격 미정"
        except Exception:
            price_fmt = price or "가격 미정"

        post_body_html = "".join(f"<div style='margin:0 0 12px 0'>{line}</div>" for line in post_body.split("\n") if line.strip())
        title_lines = [l.strip() for l in seo_titles.strip().split("\n") if l.strip()]
        titles_html = ""
        for j, line in enumerate(title_lines[:5]):
            clean = re.sub(r"^[1-5][.)\s]+", "", line).strip()
            titles_html += f'<div style="margin:4px 0;padding:5px 10px;background:#f8f8f8;border-radius:4px;font-size:13px">{j+1}. {clean}</div>'

        img_parts = []
        for img_url in images[:4]:
            img_parts.append(f'<img src="{img_url}" style="width:calc(50% - 4px);max-height:130px;object-fit:cover;border-radius:6px;display:inline-block;vertical-align:top" alt="상품이미지">')
        img_html = f'<div style="margin:8px 0;display:flex;flex-wrap:wrap;gap:4px">{" ".join(img_parts)}</div>' if img_parts else ""

        cards_html += f"""
<div style="border-left:4px solid {color};background:#fff;margin:14px 0;overflow:hidden;border:1px solid #e0e0e0;border-left:4px solid {color}">
  <div style="background:{color};color:white;padding:10px 16px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <span style="background:rgba(255,255,255,0.2);padding:2px 10px;border-radius:12px;font-weight:bold;font-size:13px">{num}번</span>
      &nbsp;<strong style="font-size:14px">{name[:42]}</strong>
    </div>
    <div style="font-size:12px;opacity:0.85;white-space:nowrap">📅 {pub_time_str} 발행</div>
  </div>
  <div style="padding:12px 16px">
    {img_html}
    <div style="font-size:12px;color:#777;margin-bottom:8px">카테고리: {cat['name']} | 최저가: {price_fmt}</div>
    <div style="margin:10px 0">
      <div style="font-size:12px;font-weight:bold;color:#333;margin-bottom:5px">📌 SEO 제목 (하나 선택)</div>
      {titles_html}
    </div>
    <details style="margin-top:10px">
      <summary style="cursor:pointer;font-size:13px;color:{color};font-weight:bold;padding:4px 0">✍️ 본문 펼치기 (복붙용)</summary>
      <div style="background:#fafafa;border:1px solid #eee;padding:12px;border-radius:4px;margin-top:8px;font-size:15px;line-height:1.9">{post_body_html}</div>
      <div style="margin-top:10px">
        <div style="font-size:12px;color:#555;font-weight:bold;margin-bottom:4px">📋 네이버 복붙용 (클릭 후 Ctrl+A → Ctrl+C → 네이버에 붙여넣기)</div>
        <textarea onclick="this.select()" readonly style="width:100%;height:220px;font-size:14px;line-height:1.9;font-family:맑은고딕,sans-serif;border:2px solid {color};border-radius:4px;padding:10px;box-sizing:border-box;resize:vertical;background:#fff">{post_body}

{hashtags}</textarea>
      </div>
    </details>
  </div>
</div>
"""

    email_html = f"""<html><body style="font-family:맑은고딕,sans-serif;max-width:680px;margin:0 auto;padding:20px;background:#f0f2f5">

<div style="background:#1a237e;color:white;padding:18px 20px;border-radius:10px;margin-bottom:14px;text-align:center">
  <div style="font-size:12px;opacity:0.7;margin-bottom:4px">🛒 쇼핑 자동화 · 네이버 블로그 전용</div>
  <div style="font-size:20px;font-weight:bold">{today_str} · 총 {len(items)}개 상품</div>
  <div style="font-size:12px;opacity:0.65;margin-top:4px">브랜드커넥트 링크를 [쇼핑링크] 자리에 직접 삽입하세요</div>
</div>

<div style="background:#fff;border-radius:8px;padding:12px 16px;margin-bottom:14px;font-size:13px;border:1px solid #ddd">
  <strong>📋 사용 방법</strong><br>
  1️⃣ SEO 제목 1개 선택 &nbsp; 2️⃣ 본문 펼쳐서 복붙 &nbsp; 3️⃣ [쇼핑링크] 자리에 브랜드커넥트 링크 교체 후 발행<br>
  <span style="color:#1a237e;font-size:12px">⏰ 권장 시간: 06:00 / 09:00 / 12:00 / 15:00 / 18:00</span>
</div>

{cards_html}

<p style="text-align:center;font-size:11px;color:#aaa;margin-top:20px">쇼핑 자동화 v4 · {now_str}</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[쇼핑발행] {today_str} · {len(items)}개 상품"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())

    print(f"✅ 이메일 발송 완료 ({len(items)}개 상품) → {EMAIL_RECIPIENT}")



# ── 메인 ──────────────────────────────────────────

def run_shopping_task(category_ids=None, count=5, send_email_flag=True,
                      log_fn=print, force=False):
    """
    GUI / 자동실행 모두에서 호출 가능한 핵심 함수
    category_ids : None이면 전체, 리스트면 해당 id만 사용
    count        : 상품 개수 (1~10)
    send_email_flag : False면 이메일 발송 생략
    log_fn       : GUI 로그창 콜백 (기본=print)
    force        : True면 오늘 이미 실행됐어도 강제 실행
    반환: {"success": bool, "count": int, "datalab_used": bool}
    """
    from datetime import datetime as _dt, timezone
    _tz = timezone(timedelta(hours=9))

    if not force and check_already_ran_today():
        log_fn("⏭️  오늘 이미 실행됨. 건너뜀 (강제실행: force=True)")
        return {"success": False, "count": 0, "datalab_used": False, "skipped": True}

    log_fn("=" * 50)
    log_fn(f"🛒 쇼핑AI 시작  [{_dt.now(_tz).strftime('%H:%M')}]")
    log_fn("=" * 50)

    # 카테고리 필터
    cats = CATEGORIES
    if category_ids:
        cats = [c for c in CATEGORIES if c["id"] in category_ids]
    if not cats:
        cats = CATEGORIES

    # DataLab 상태 추적
    datalab_used = False
    _orig_datalab = get_trending_keywords_from_datalab

    def _tracked_datalab(cat):
        nonlocal datalab_used
        result = _orig_datalab(cat)
        if result:
            datalab_used = True
        return result

    # 임시로 패치
    import shopping_automation as _self
    _self.get_trending_keywords_from_datalab = _tracked_datalab

    # 상품 선택 (카테고리 필터 적용)
    selected = []
    selected_ids = set()  # 이미 선택된 상품 ID 추적

    def bc_score(p):
        rate  = float(p.get("commissionRate", 0))
        cnt   = min(float(p.get("reviewCount", 0)), 10000) / 10000
        score = float(p.get("reviewScore", 0)) / 5.0
        return rate * 0.5 + cnt * 30 * 0.3 + score * 100 * 0.2

    # 키워드 순환: 카테고리 키워드를 순서대로 1개씩 사용 (다양성 보장)
    # 카테고리가 1개이고 키워드가 많은 경우(식품 등) 키워드마다 1개씩 배정
    published = load_published_ids()

    # 키워드 풀 구성: 카테고리 × 키워드 순환
    # 카테고리별 키워드 라운드로빈 배치 (같은 카테고리 중복 방지)
    cat_kw_lists = []
    for cat in cats:
        kws = cat.get("keywords", [cat["name"]])[:]
        random.shuffle(kws)  # 카테고리 내 키워드는 랜덤
        cat_kw_lists.append([(cat, kw) for kw in kws])

    # 라운드로빈: cat1_kw1, cat2_kw1, cat3_kw1, ..., cat1_kw2, cat2_kw2, ...
    keyword_pool = []
    max_len = max((len(lst) for lst in cat_kw_lists), default=1)
    for i in range(max_len):
        for lst in cat_kw_lists:
            if i < len(lst):
                keyword_pool.append(lst[i])

    # count * 2 미만이면 반복 보충
    while len(keyword_pool) < count * 2:
        keyword_pool += keyword_pool

    attempt = 0
    kw_idx = 0
    while len(selected) < count and attempt < count * 3 and kw_idx < len(keyword_pool):
        cat, kw = keyword_pool[kw_idx]
        kw_idx += 1
        attempt += 1

        products = get_top_product(cat, specific_keyword=kw)
        if not products:
            continue
        new_products = [
            p for p in products
            if str(p.get("productId","")) not in published
            and str(p.get("productId","")) not in selected_ids
        ]
        if not new_products:
            continue

        selected_product = max(new_products, key=bc_score)
        pid = str(selected_product.get("productId",""))
        selected_ids.add(pid)
        selected_bc = selected_product
        selected.append((cat, selected_product, selected_bc))

    if not selected:
        log_fn("❌ 발행할 상품 없음.")
        return {"success": False, "count": 0, "datalab_used": datalab_used}

    email_items = []
    pub_times = ["06:00","09:00","12:00","15:00","18:00"]

    for i, (category, product, bc_product) in enumerate(selected):
        log_fn(f"\n[{i+1}/{len(selected)}] {product.get('title','')[:40]}")
        product_id   = str(product.get("productId",""))
        product_name = product.get("title","")

        # 선택 즉시 발행 기록 저장 (중복 방지 - 중간에 끊겨도 재선택 안 됨)
        if product_id:
            save_published_product(product_id, product_name)

        log_fn("  🖼️ 이미지 수집 중...")
        images = get_product_images(product)

        log_fn("  ✍️ Claude 글 작성 중...")
        seo_titles, post_body, hashtags = generate_shopping_post(category, product)
        if not post_body:
            log_fn(f"  ⚠️ 글 작성 실패, 스킵")
            continue

        pub_time_str = pub_times[i] if i < len(pub_times) else f"{6+i*2:02d}:00"
        email_items.append({
            "category": category, "product": product, "bc_product": bc_product,
            "images": images, "seo_titles": seo_titles, "post_body": post_body,
            "hashtags": hashtags, "pub_time_str": pub_time_str,
            "product_id": product_id, "product_name": product_name,
        })

    if email_items and send_email_flag:
        log_fn(f"\n📧 이메일 발송 중... ({len(email_items)}개 상품)")
        send_shopping_email_bulk(email_items)
        save_run_today()
        log_fn(f"✅ 완료! {len(email_items)}개 상품 이메일 발송")
    elif email_items:
        log_fn(f"\n✅ 완료! {len(email_items)}개 상품 (이메일 발송 OFF)")
    else:
        log_fn("❌ 처리된 상품 없음.")

    datalab_status = "DataLab ✅" if datalab_used else "fallback ⚠️"
    log_fn(f"📊 키워드 소스: {datalab_status}")

    return {"success": bool(email_items), "count": len(email_items),
            "datalab_used": datalab_used}


def main():
    run_shopping_task(count=5, force=False)

if __name__ == "__main__":
    main()
