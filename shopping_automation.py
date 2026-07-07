# ================================================
# 쇼핑커넥트 자동화 v4.0
# 흐름: 카테고리 → 5개 상품 → Claude 글 작성
#       → 이메일 1통 (네이버 블로그 복붙용)
# ================================================

import os, re, sys, json, random, requests, smtplib
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
NAVER_COOKIE        = _get("NAVER_COOKIE", "")
NAVER_SPACE_ID      = _get("NAVER_SPACE_ID", "962414636778176")

PUBLISHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published_products.txt")
NAVER_BLOG_URL = "https://blog.naver.com/janee_item"



# ── 네이버 데이터랩 쇼핑 카테고리 + 세부 키워드 ──
CATEGORIES = [
    {"name": "화장품/미용", "id": "50000002", "keywords": [
        "선크림", "토너패드", "쿠션팩트", "마스카라", "세럼", "클렌징폼",
        "립틴트", "아이크림", "파운데이션", "미스트", "에센스", "립밤", "자외선차단제"
    ]},
    {"name": "디지털/가전", "id": "50000003", "keywords": [
        "무선이어폰", "공기청정기", "로봇청소기", "블루투스스피커", "스마트워치",
        "전동칫솔", "가습기", "선풍기", "전기면도기", "태블릿", "게이밍마우스", "웹캠"
    ]},
    {"name": "가구/인테리어", "id": "50000004", "keywords": [
        "식탁의자", "수납장", "커튼", "카펫", "조명", "책상", "소파",
        "선반", "화분", "무드등", "방향제", "침구세트", "벽시계"
    ]},
    {"name": "식품", "id": "50000005", "keywords": [
        "단백질쉐이크", "견과류", "홍삼", "유산균", "냉동식품", "즉석밥",
        "커피믹스", "비타민", "오메가3", "콜라겐", "프로틴바", "그래놀라"
    ]},
    {"name": "스포츠/레저", "id": "50000006", "keywords": [
        "등산스틱", "요가매트", "헬스글러브", "수영복", "자전거헬멧",
        "등산화", "골프장갑", "캠핑의자", "낚시대", "배드민턴라켓", "폼롤러", "점프줄"
    ]},
    {"name": "생활/건강", "id": "50000007", "keywords": [
        "안마기", "칫솔", "핸드크림", "발열내복", "압박스타킹",
        "체중계", "혈압계", "발마사지기", "족욕기", "허리보호대", "무릎보호대", "냉찜질팩"
    ]},
    {"name": "여가/생활편의", "id": "50000008", "keywords": [
        "여행가방", "우산", "보조배터리", "텀블러", "에코백",
        "파우치", "독서대", "자동차방향제", "차량용충전기", "접이식테이블", "캐리어"
    ]},
    {"name": "출산/육아", "id": "50000009", "keywords": [
        "기저귀", "아기물티슈", "유아매트", "아기띠", "이유식",
        "아기욕조", "장난감", "아기침대", "젖병", "유모차", "아기로션", "치발기"
    ]},
    {"name": "도서", "id": "50000010", "keywords": [
        "자기계발서", "소설", "경제경영서", "어린이책", "영어원서",
        "역사책", "요리책", "그림책", "수험서", "에세이", "만화책"
    ]},
]

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
        res = requests.post(
            "https://datalab.naver.com/shoppingInsight/getKeywordRank.naver",
            headers={
                "Referer":          "https://datalab.naver.com/shoppingInsight/sCategory.naver",
                "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept":           "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            },
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
            result = res.json().get("result", [])
            keywords = [item.get("keyword", "") for item in result if item.get("keyword")]
            if keywords:
                print(f"   📊 DataLab 인기 키워드 {len(keywords)}개 수집")
                return keywords
    except Exception as e:
        print(f"   ℹ️ DataLab 크롤링 실패: {e}")

    return []


def get_top_product(category):
    """
    키워드 선택 순서:
      1순위: DataLab 인기 키워드 TOP 10 중 랜덤
      2순위(fallback): 하드코딩 keywords 중 랜덤
    → 네이버 쇼핑 검색 → 20개 수집 → reviewCount 기준 상위 반환
    반환: list of product dict
    """
    # 키워드 결정
    datalab_kws = get_trending_keywords_from_datalab(category)
    if datalab_kws:
        query = random.choice(datalab_kws[:5])  # 상위 5개 중 랜덤
    else:
        fallback_kws = category.get("keywords", [category["name"]])
        query = random.choice(fallback_kws)
        print(f"   🔀 Fallback 키워드: {query}")

    print(f"   🔍 검색 키워드: {query}")

    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": query, "display": 20, "sort": "sim"},
            timeout=10,
        )
        res.raise_for_status()
        items = res.json().get("items", [])

        # HTML 태그 제거
        for item in items:
            item["title"] = re.sub(r"<[^>]+>", "", item.get("title", ""))

        # 네이버 쇼핑 기본 API는 reviewCount 미제공
        # → 정확도(sim) 상위 10개를 섞어서 반환: 실행마다 다른 상품 선택
        if len(items) > 10:
            pool = items[:10]
            random.shuffle(pool)
            items = pool + items[10:]

        return items

    except Exception as e:
        print(f"⚠️ 쇼핑 API 오류: {e}")
        return []


# ── 3단계: 중복 체크 ──────────────────────────────

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
            selected_product = new_products[0]
            pid = str(selected_product.get("productId", ""))
            print(f"   ✅ 일반 상품 선택: {selected_product.get('title','')[:25]}")

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

        best = max(data, key=bc_score)
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
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
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
        <textarea onclick="this.select()" readonly style="width:100%;height:220px;font-size:14px;line-height:1.9;font-family:맑은고딕,sans-serif;border:2px solid {color};border-radius:4px;padding:10px;box-sizing:border-box;resize:vertical;background:#fff">{post_body}</textarea>
        <div style="background:#f5f5f5;padding:8px;border-radius:4px;margin-top:6px;font-size:12px;color:#888">{hashtags}</div>
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

def main():
    print("=" * 55)
    print("🛒 쇼핑커넥트 자동화 v3 시작 (5개 상품)")
    print("=" * 55)

    # ── 1. 5개 상품 선택 ──
    selected = find_new_products(count=len(CATEGORIES))
    if not selected:
        print("❌ 발행할 상품 없음. 종료.")
        sys.exit(0)

    email_items = []

    for i, (category, product, bc_product) in enumerate(selected):
        print(f"\n{'='*55}")
        print(f"[{i+1}/{len(selected)}] {product.get('title','')[:35]}")
        print(f"{'='*55}")

        product_id   = str(product.get("productId", ""))
        product_name = product.get("title", "")

        # ── 2. 이미지 수집 ──
        print("🖼️ 이미지 수집 중...")
        images = get_product_images(product)

        # ── 3. 글 작성 ──
        print("✍️ Claude 글 작성 중...")
        seo_titles, post_body, hashtags = generate_shopping_post(category, product)
        if not post_body:
            print(f"⚠️ [{i+1}번] 글 작성 실패, 스킵")
            continue

        # ── 4. 발행 기록 저장 ──
        if product_id:
            save_published_product(product_id, product_name)

        pub_times    = ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
        pub_time_str = pub_times[i] if i < len(pub_times) else f"{6 + i*3:02d}:00"
        email_items.append({
            "category":     category,
            "product":      product,
            "bc_product":   bc_product,
            "images":       images,
            "seo_titles":   seo_titles,
            "post_body":    post_body,
            "hashtags":     hashtags,
            "pub_time_str": pub_time_str,
        })
    if email_items:
        print(f"\n📧 이메일 발송 중... ({len(email_items)}개 상품)")
        send_shopping_email_bulk(email_items)
    print(f"\n✅ 완료! {len(email_items)}개 상품 처리")

if __name__ == "__main__":
    main()
