# ================================================
# 쇼핑커넥트 자동화 v4.0
# 흐름: 카테고리 → 5개 상품 → Claude 글 작성
#       → 이메일 1통 (네이버 블로그 복붙용)
# ================================================

import os, re, sys, json, requests, smtplib
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



# ── 네이버 데이터랩 쇼핑 카테고리 (대분류 고정) ──
CATEGORIES = [
    {"name": "화장품/미용", "id": "50000002"},
    {"name": "디지털/가전", "id": "50000003"},
    {"name": "가구/인테리어","id": "50000004"},
    {"name": "식품",        "id": "50000005"},
    {"name": "스포츠/레저", "id": "50000006"},
    {"name": "생활/건강",   "id": "50000007"},
    {"name": "여가/생활편의","id": "50000008"},
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


# ── 2단계: 네이버 쇼핑 API로 1위 상품 가져오기 ──

def get_top_product(category):
    """
    카테고리 이름으로 네이버 쇼핑 검색 → 인기 상품 상위 10개 반환
    반환: list of product dict
    """
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": category["name"], "display": 10, "sort": "sim"},
            timeout=10
        )
        res.raise_for_status()
        items = res.json().get("items", [])
        # HTML 태그 제거
        for item in items:
            item["title"] = re.sub(r"<[^>]+>", "", item.get("title", ""))
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


def find_new_products(count=5):
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

    try:
        price_fmt = f"{int(price):,}원" if price else "가격 미정"
    except Exception:
        price_fmt = price or "가격 미정"

    brand_info = brand or maker or "브랜드 미상"

    prompt = f"""너는 네이버 쇼핑 블로그에 제휴 마케팅 상품 추천 글을 쓰는 전문 작가야.

상품 정보:
- 상품명: {name}
- 브랜드: {brand_info}
- 최저가: {price_fmt}
- 카테고리: {cat1} > {cat2}

글쓰기 규칙:
- 너무 어려운 전문 용어나 한자어는 쉬운 말로 바꿀 것
- 예) "A/S 인프라" → "고장 나도 수리받기 쉬워요"
- 예) "섭취 시" → "먹으면"
- ~더라고요, ~이에요, ~해요 톤 유지
- 문장은 짧고 명확하게
- **볼드** 마크다운 절대 사용 금지 (별표 ** 사용하지 말 것)
- [소제목1:], [소제목2:] 같은 대괄호 태그 절대 사용 금지
- 마크다운 기호 (#, ##, **, *, ---, ===) 절대 사용 금지

아래 형식을 정확히 지켜서 써줘:

---SEO_TITLES_START---
1. (정보 검색형 제목 - 카테고리 키워드 중심)
2. (제품명 직접 검색형 - 구매 의도 높은 유저 타겟)
3. (가격/가성비형)
4. (후기/경험형)
5. (감성/공감형)
---SEO_TITLES_END---

---BODY_START---
(공감형 도입부: 이 상품이 왜 필요한지 생활 속 불편함 공감으로 시작, 2~3문단)

가격은 시기에 따라 변동될 수 있습니다.
👇 현재 가격 확인하기
제품 구매하러 가기 → [쇼핑링크]

━━━━━━━━━━━━━━━━━━

✅ (첫 번째 소제목을 여기에 직접 텍스트로 작성 - 대괄호 없이)
(2~3문단)

✅ (두 번째 소제목을 여기에 직접 텍스트로 작성 - 대괄호 없이)
(2~3문단)

✅ (세 번째 소제목을 여기에 직접 텍스트로 작성 - 대괄호 없이)
(2~3문단)

━━━━━━━━━━━━━━━━━━

(마무리: 어떤 사람에게 추천하는지, 1~2문단)

재고와 할인 여부는 아래에서 확인할 수 있습니다.
👇 오늘 최저가 확인하기
제품 구매하러 가기 → [쇼핑링크]
---BODY_END---

---TAGS_START---
#태그1 #태그2 #태그3 #태그4 #태그5 #태그6 #태그7 #태그8
---TAGS_END---"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()

        # SEO 제목 파싱
        titles_match = re.search(r"---SEO_TITLES_START---(.+?)---SEO_TITLES_END---", raw, re.DOTALL)
        seo_titles = titles_match.group(1).strip() if titles_match else ""

        # 본문 파싱
        body_match = re.search(r"---BODY_START---(.+?)---BODY_END---", raw, re.DOTALL)
        post_body = body_match.group(1).strip() if body_match else raw

        # 본문 클린업: 마크다운·태그 자동 제거
        post_body = re.sub(r'\*\*(.+?)\*\*', r'\1', post_body)          # **볼드** → 볼드
        post_body = re.sub(r'\[소제목\d+\s*:\s*([^\]]+)\]', r'\1', post_body)  # [소제목1: 내용] → 내용만
        post_body = re.sub(r'✅\s*\([^)]+\)', '', post_body)              # ✅ (안내문구) 제거
        post_body = re.sub(r'^#+\s*', '', post_body, flags=re.MULTILINE)    # # 마크다운 제거
        post_body = re.sub(r'\n{3,}', '\n\n', post_body).strip()

        # 해시태그 파싱
        tags_match = re.search(r"---TAGS_START---(.+?)---TAGS_END---", raw, re.DOTALL)
        hashtags = tags_match.group(1).strip() if tags_match else ""

        return seo_titles, post_body, hashtags

    except Exception as e:
        print(f"⚠️ Claude 오류: {e}")
        return None, None, None


# ── 6단계: 이메일 발송 ───────────────────────────

def send_shopping_email_bulk(items):
    """
    5개 상품을 하나의 이메일로 발송
    items: list of dict (category, product, bc_product, images, seo_titles, post_body, hashtags, publish_time, blogger_url)
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail 환경변수 없음")
        return
    if not items:
        print("⚠️ 발송할 상품 없음")
        return

    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    colors   = ["#4A90E2", "#7B68EE", "#20B2AA", "#FF8C00", "#DC143C"]

    # ── 상품 카드 HTML 생성 ──
    cards_html = ""
    for i, item in enumerate(items):
        cat        = item["category"]
        product    = item["product"]
        bc_product = item.get("bc_product")
        images     = item.get("images", [])
        seo_titles = item.get("seo_titles", "")
        post_body  = item.get("post_body", "")
        hashtags   = item.get("hashtags", "")
        pub_time   = item.get("publish_time")
        blogger_url= item.get("blogger_url", "")

        color   = colors[i % len(colors)]
        num     = i + 1
        name    = product.get("title", "")
        price   = product.get("lprice", "")
        link    = product.get("link", "")
        brand   = product.get("brand", "") or product.get("maker", "")


        try:
            price_fmt = f"{int(price):,}원" if price else "가격 미정"
        except Exception:
            price_fmt = price or "가격 미정"

        # SEO 제목 첫 번째 추출
        title_lines = [l.strip() for l in seo_titles.strip().split("\n") if l.strip()]
        main_title  = re.sub(r"^[1-5][.)\s]+", "", title_lines[0]).strip() if title_lines else name

        # 링크 안내
        if bc_product:
            bc_url   = bc_product.get("shortUrl", "") or bc_product.get("productUrl", "")
            bc_rate  = bc_product.get("commissionRate", 0)
            bc_rv    = bc_product.get("reviewInfo", {})
            bc_cnt   = bc_rv.get("totalReviewCount", 0)
            bc_score = bc_rv.get("averageReviewScore", 0)
            try:
                bc_price_fmt = f"{int(bc_product.get('salePrice', 0)):,}원"
            except Exception:
                bc_price_fmt = price_fmt
            link_box = f"""
<div style="background:#e8f5e9;border:1px solid #4caf50;padding:12px;border-radius:6px;margin:10px 0;font-size:13px">
  ✅ <strong>브랜드커넥트</strong> | 수수료 <strong style="color:#e53935">{bc_rate}%</strong> | ⭐{bc_score} ({bc_cnt:,}개)<br>
  쇼핑링크: <a href="{bc_url}" style="color:#0066cc;word-break:break-all">{bc_url}</a>
</div>"""
        elif link:
            link_box = f"""
<div style="background:#fff3cd;border:1px solid #ffc107;padding:12px;border-radius:6px;margin:10px 0;font-size:13px">
  🔗 쇼핑커넥트 등록 필요<br>
  원본 URL: <a href="{link}" style="color:#0066cc;word-break:break-all">{link}</a>
</div>"""
        else:
            link_box = ""

        # 이미지 (첫 번째만)
        img_html = ""
        if images:
            img_html = f'<img src="{images[0]}" style="max-width:100%;max-height:180px;border-radius:6px;margin:8px 0;display:block" alt="상품이미지">'


        # 본문 (처음 300자 미리보기)
        body_preview = post_body[:300].replace("\n", " ") + "..." if len(post_body) > 300 else post_body.replace("\n", " ")

        # SEO 제목 전체
        titles_html = ""
        for j, line in enumerate(title_lines[:5]):
            clean = re.sub(r"^[1-5][.)\s]+", "", line).strip()
            titles_html += f'<div style="margin:3px 0;font-size:13px">• {clean}</div>'

        cards_html += f"""
<div style="border:2px solid {color};border-radius:10px;margin:16px 0;overflow:hidden">
  <!-- 헤더 -->
  <div style="background:{color};color:white;padding:12px 16px">
    <span style="background:white;color:{color};padding:2px 8px;border-radius:10px;font-weight:bold;font-size:13px">{num}번</span>
    &nbsp;&nbsp;<strong style="font-size:15px">{name[:35]}</strong>
  </div>
  <!-- 본문 -->
  <div style="padding:14px 16px;background:#fff">
    {img_html}
    <div style="font-size:13px;color:#555;margin:6px 0">
      카테고리: {cat['name']} | 최저가: {price_fmt}
    </div>
    {link_box}
    <div style="margin-top:10px">
      <strong style="font-size:13px">📌 SEO 제목 (하나 선택)</strong>
      {titles_html}
    </div>
    <details style="margin-top:10px">
      <summary style="cursor:pointer;font-size:13px;color:#4A90E2;font-weight:bold">✍️ 본문 보기 (클릭해서 펼치기)</summary>
      <div style="background:#f9f9f9;padding:12px;border-radius:4px;margin-top:8px;font-size:13px;line-height:1.8;white-space:pre-line">{post_body}</div>
      <div style="background:#f0f0f0;padding:8px;border-radius:4px;margin-top:6px;font-size:12px;color:#666">{hashtags}</div>
    </details>
  </div>
</div>
"""

    # ── 전체 이메일 ──
    email_html = f"""<html><body style="font-family:맑은고딕,sans-serif;max-width:720px;margin:0 auto;padding:20px;background:#f5f5f5">

<div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);color:white;padding:20px;border-radius:12px;margin-bottom:20px;text-align:center">
  <h2 style="margin:0 0 6px 0;font-size:22px">🛒 네이버 블로그 발행용</h2>
  <p style="margin:0;opacity:0.85;font-size:14px">{today_str} | 총 {len(items)}개 상품</p>
</div>

<div style="background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:16px;font-size:13px">
  <strong>📋 사용 방법</strong><br>
  1️⃣ SEO 제목 중 1개 선택<br>
  2️⃣ 브랜드커넥트 링크로 본문 [쇼핑링크] 두 곳 교체<br>
  3️⃣ 네이버 블로그에 번호 순서대로 복붙 발행
</div>

{cards_html}

<p style="text-align:center;font-size:12px;color:#999;margin-top:20px">쇼핑 자동화 v3 · {now_str}</p>
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


def send_shopping_email(category, product, images, seo_titles, post_body, hashtags, bc_product=None):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail 환경변수 없음")
        return

    name  = product.get("title", "")
    price = product.get("lprice", "")
    link  = product.get("link", "")
    brand = product.get("brand", "") or product.get("maker", "")

    try:
        price_fmt = f"{int(price):,}원" if price else "가격 미정"
    except Exception:
        price_fmt = price or "가격 미정"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 이미지 HTML
    images_html = ""
    for i, url in enumerate(images):
        images_html += f'<img src="{url}" style="max-width:100%;border-radius:8px;margin:6px 0;display:block" alt="상품이미지{i+1}"><br>\n'

    # SEO 제목 HTML
    title_lines = [l.strip() for l in seo_titles.strip().split("\n") if l.strip()]
    titles_html_inner = ""
    colors = ["#4A90E2","#7B68EE","#20B2AA","#FF8C00","#DC143C"]
    for i, line in enumerate(title_lines[:5]):
        clean = re.sub(r"^[1-5][.)]\s*", "", line).strip()
        color = colors[i] if i < len(colors) else "#333"
        titles_html_inner += f'<div style="margin-bottom:10px"><span style="background:{color};color:white;padding:2px 8px;border-radius:8px;font-size:11px;margin-right:6px">{i+1}번</span><strong>{clean}</strong></div>\n'

    # 본문 줄바꿈 → HTML
    body_html = post_body.replace("\n", "<br>\n")

    # 해시태그 HTML
    tags_html = f'<div style="background:#f0f0f0;padding:12px;border-radius:6px;margin-top:20px;font-size:14px;color:#555">{hashtags}</div>' if hashtags else ""

    # 브랜드커넥트 or 쇼핑커넥트 링크 안내
    if bc_product:
        bc_url   = bc_product.get("shortUrl", "") or bc_product.get("productUrl", "")
        bc_rate  = bc_product.get("commissionRate", 0)
        bc_name  = bc_product.get("productName", name)
        bc_price = bc_product.get("salePrice", 0)
        bc_rv    = bc_product.get("reviewInfo", {})
        bc_cnt   = bc_rv.get("totalReviewCount", 0)
        bc_score = bc_rv.get("averageReviewScore", 0)
        try:
            bc_price_fmt = f"{int(bc_price):,}원"
        except Exception:
            bc_price_fmt = str(bc_price)
        link_guide = f"""
<div style="background:#e8f5e9;border:1px solid #4caf50;padding:15px;border-radius:8px;margin:20px 0">
  <strong>✅ 브랜드커넥트 상품 발견! (링크 바로 사용 가능)</strong><br><br>
  <table style="width:100%;border-collapse:collapse">
    <tr><td style="padding:4px 0;color:#555;width:80px">상품명</td><td><strong>{bc_name}</strong></td></tr>
    <tr><td style="padding:4px 0;color:#555">판매가</td><td><strong>{bc_price_fmt}</strong></td></tr>
    <tr><td style="padding:4px 0;color:#555">수수료율</td><td><strong style="color:#e53935">{bc_rate}%</strong></td></tr>
    <tr><td style="padding:4px 0;color:#555">리뷰</td><td>⭐ {bc_score} ({bc_cnt:,}개)</td></tr>
  </table>
  <br>
  본문의 <strong>[쇼핑링크]</strong> 두 곳을 아래 URL로 교체하세요:<br><br>
  <a href="{bc_url}" style="color:#0066cc;word-break:break-all">{bc_url}</a>
</div>
"""
    elif link:
        link_guide = f"""
<div style="background:#fff3cd;border:1px solid #ffc107;padding:15px;border-radius:8px;margin:20px 0">
  <strong>🔗 쇼핑커넥트 링크 만들기 (5분 소요)</strong><br><br>
  아래 URL을 쇼핑커넥트에 등록하세요:<br><br>
  <a href="{link}" style="color:#0066cc;word-break:break-all">{link}</a><br><br>
  링크 만들고 본문의 <strong>[쇼핑링크]</strong> 두 곳에 붙여넣으세요.
</div>
"""
    else:
        link_guide = ""

    email_html = f"""
<html><body style="font-family:맑은고딕,sans-serif;max-width:700px;margin:0 auto;padding:20px">

<div style="background:#f0f7ff;border-left:4px solid #4A90E2;padding:15px;margin-bottom:20px;border-radius:4px">
  <h2 style="margin:0 0 8px 0;color:#333">🛒 쇼핑커넥트 발행용</h2>
  <p style="margin:0;color:#666">{now_str} | 카테고리: {category['name']}</p>
</div>

<div style="background:#e8f5e9;border:1px solid #4caf50;padding:15px;border-radius:8px;margin-bottom:20px">
  <strong>📦 오늘의 추천 상품</strong><br><br>
  <strong>상품명:</strong> {name}<br>
  <strong>브랜드:</strong> {brand or "정보 없음"}<br>
  <strong>최저가:</strong> {price_fmt}
</div>

{link_guide}

<div style="background:#f8f8f8;border:1px solid #ddd;padding:15px;border-radius:6px;margin-bottom:20px">
  <strong>📌 SEO 제목 5가지 (하나 선택하세요)</strong><br><br>
  {titles_html_inner}
</div>

<div style="background:#fff;border:1px solid #ddd;padding:12px;border-radius:4px;margin-bottom:20px">
  <strong>📋 사용 방법</strong><br>
  1️⃣ 위 URL로 쇼핑커넥트 링크 생성<br>
  2️⃣ 제목 5개 중 1개 선택<br>
  3️⃣ 본문 [쇼핑링크] 두 곳에 링크 교체<br>
  4️⃣ 네이버 블로그 복붙 + 이미지 첨부
</div>

<hr style="border:2px solid #333;margin:20px 0">
<h2 style="font-size:18px">✍️ 본문 (복붙용)</h2>
<hr style="border:1px solid #ddd;margin:15px 0">

<div style="margin-bottom:15px">
<strong>📸 상품 이미지 ({len(images)}장)</strong><br>
{images_html}
</div>

<div style="background:#fffbe6;border:1px solid #ffe082;padding:10px;border-radius:4px;margin-bottom:15px;font-size:13px">
  이 포스팅은 제휴 마케팅 활동의 일환으로, 판매 발생 시 수수료를 제공받습니다.
</div>

<div style="line-height:1.9;font-size:15px;color:#222">
{body_html}
</div>

{tags_html}

<hr style="border:2px solid #333;margin:30px 0">
<p style="font-size:12px;color:#999;text-align:center">쇼핑 자동화 · {now_str}</p>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[쇼핑발행용] {name[:30]}"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())

    print(f"✅ 이메일 발송 완료 → {EMAIL_RECIPIENT}")


# ── 메인 ──────────────────────────────────────────

def main():
    print("=" * 55)
    print("🛒 쇼핑커넥트 자동화 v3 시작 (5개 상품)")
    print("=" * 55)

    # ── 1. 5개 상품 선택 ──
    selected = find_new_products(count=5)
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

        email_items.append({
            "category":   category,
            "product":    product,
            "bc_product": bc_product,
            "images":     images,
            "seo_titles": seo_titles,
            "post_body":  post_body,
            "hashtags":   hashtags,
        })

    # ── 6. 이메일 1통으로 발송 ──
    if email_items:
        print(f"\n📧 이메일 발송 중... ({len(email_items)}개 상품)")
        send_shopping_email_bulk(email_items)

    print(f"\n✅ 완료! {len(email_items)}개 상품 처리")


if __name__ == "__main__":
    main()
