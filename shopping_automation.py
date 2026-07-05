# ================================================
# 쇼핑커넥트 블로그 자동화 v2.0
# 흐름: 데이터랩 인기 카테고리 → 네이버 쇼핑 1위 상품
#       → 이미지 4장 → Claude 글 작성 → 이메일 발송
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

PUBLISHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published_products.txt")
NAVER_BLOG_URL = "https://blog.naver.com/janee_item"

# ── 네이버 데이터랩 쇼핑 카테고리 (대분류 고정) ──
CATEGORIES = [
    {"name": "패션의류",    "id": "50000000"},
    {"name": "패션잡화",    "id": "50000001"},
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
    데이터랩 인기 카테고리 → 쇼핑 검색 → 아직 발행 안 한 상품 반환
    반환: (category, product) 또는 (None, None)
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

        for product in products:
            pid = str(product.get("productId", ""))
            if pid and pid not in published_ids:
                print(f"✅ 새 상품: {product['title']}")
                return category, product
            else:
                print(f"   └ 이미 발행됨, 다음으로")

    print("⚠️ 새 상품 없음")
    return None, None


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

[소제목1: (첫 번째 소제목 내용에 맞게 작성)]
(2~3문단)

[소제목2: (두 번째 소제목)]
(2~3문단)

[소제목3: (세 번째 소제목)]
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

        # 해시태그 파싱
        tags_match = re.search(r"---TAGS_START---(.+?)---TAGS_END---", raw, re.DOTALL)
        hashtags = tags_match.group(1).strip() if tags_match else ""

        return seo_titles, post_body, hashtags

    except Exception as e:
        print(f"⚠️ Claude 오류: {e}")
        return None, None, None


# ── 6단계: 이메일 발송 ───────────────────────────

def send_shopping_email(category, product, images, seo_titles, post_body, hashtags):
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

    # 쇼핑커넥트 링크 안내
    link_guide = f"""
<div style="background:#fff3cd;border:1px solid #ffc107;padding:15px;border-radius:8px;margin:20px 0">
  <strong>🔗 쇼핑커넥트 링크 만들기 (5분 소요)</strong><br><br>
  아래 URL을 쇼핑커넥트에 등록하세요:<br><br>
  <a href="{link}" style="color:#0066cc;word-break:break-all">{link}</a><br><br>
  링크 만들고 본문의 <strong>[쇼핑링크]</strong> 두 곳에 붙여넣으세요.
</div>
""" if link else ""

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
    print("=" * 50)
    print("🛒 쇼핑커넥트 자동화 v2 시작")
    print("=" * 50)

    # 1. 새 상품 찾기
    category, product = find_new_product()
    if not product:
        print("❌ 새 상품 없음. 종료.")
        sys.exit(0)

    product_id   = str(product.get("productId", ""))
    product_name = product.get("title", "")

    # 2. 이미지 수집
    print(f"\n🖼️ 이미지 수집 중...")
    images = get_product_images(product)

    # 3. 글 작성
    print(f"\n✍️ Claude 글 작성 중...")
    seo_titles, post_body, hashtags = generate_shopping_post(category, product)
    if not post_body:
        print("❌ 글 작성 실패. 종료.")
        sys.exit(1)

    # 4. 이메일 발송
    print(f"\n📧 이메일 발송 중...")
    send_shopping_email(category, product, images, seo_titles, post_body, hashtags)

    # 5. 발행 기록 저장
    if product_id:
        save_published_product(product_id, product_name)

    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
