# ================================================
# 쇼핑커넥트 자동화 v5.0 (쿠팡 파트너스)
# 흐름: 카테고리 → 5개 상품 → Claude 글 작성
#       → 이메일 1통 (네이버 블로그 복붙용)
# ================================================

import os, re, sys, json, random, requests, smtplib, hmac, hashlib, time
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
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

COUPANG_ACCESS_KEY  = _get("COUPANG_ACCESS_KEY", "")
COUPANG_SECRET_KEY  = _get("COUPANG_SECRET_KEY", "")
NAVER_CLIENT_ID     = _get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = _get("NAVER_CLIENT_SECRET")
CLAUDE_API_KEY      = _get("CLAUDE_API_KEY")
CLAUDE_MODEL        = _get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GMAIL_ADDRESS       = _get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD  = _get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT     = _get("EMAIL_RECIPIENT", "duatkdtn@gmail.com")

PUBLISHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published_products.txt")
LAST_RUN_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shopping_last_run.txt")


# ── 카테고리 (쿠팡 검색 키워드) ──
CATEGORIES = [
    {"name": "디지털 가전",   "id": "cat1"},
    {"name": "가구 인테리어", "id": "cat2"},
    {"name": "식품",         "id": "cat3"},
    {"name": "출산 육아",    "id": "cat4"},
]

# ── 시즌 키워드 (월별 자동 적용) ──
def get_season_keyword():
    month = datetime.now().month
    season_map = {
        (3, 4, 5):   ["봄청소용품", "입학선물", "미세먼지마스크", "봄이불"],
        (6, 7, 8):   ["선풍기", "냉풍기", "물놀이용품", "냉감침구"],
        (9, 10, 11): ["전기장판", "핫팩", "추석선물세트", "가을이불"],
        (12, 1, 2):  ["크리스마스선물", "가습기", "방한용품", "전기방석"],
    }
    for months, keywords in season_map.items():
        if month in months:
            return random.choice(keywords)
    return "인기상품"


# ── 쿠팡 파트너스 API ──────────────────────────────

def _coupang_header(method, base_path, query_string):
    """HMAC-SHA256 인증 헤더 (공식 문서: path+query 사이 ? 없이 서명, UTC 사용)"""
    dt      = time.strftime('%y%m%d', time.gmtime()) + 'T' + time.strftime('%H%M%S', time.gmtime()) + 'Z'
    message = dt + method + base_path + query_string
    sig     = hmac.new(COUPANG_SECRET_KEY.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Authorization": f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, signed-date={dt}, signature={sig}",
        "Content-type":  "application/json;charset=UTF-8",
    }

def get_coupang_products(keyword, limit=10):
    """쿠팡 상품 검색 → 제휴 링크 포함 상품 리스트 반환"""
    base_path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
    query     = urlencode({"keyword": keyword, "limit": limit, "subId": ""})

    try:
        res = requests.get(
            f"https://api-gateway.coupang.com{base_path}?{query}",
            headers=_coupang_header("GET", base_path, query),
            timeout=10
        )
        res.raise_for_status()
        items = res.json().get("data", {}).get("productData", [])

        result = []
        for p in items:
            result.append({
                "productId": str(p.get("productId", "")),
                "title":     p.get("productName", ""),
                "lprice":    str(p.get("productPrice", "")),
                "image":     p.get("productImage", ""),
                "link":      p.get("productUrl", ""),   # 이미 제휴 링크!
                "brand":     p.get("vendorName", ""),
                "category1": keyword,
                "category2": "",
            })
        print(f"✅ 쿠팡 '{keyword}' → {len(result)}개 상품")
        return result
    except Exception as e:
        print(f"⚠️ 쿠팡 API 오류 ({keyword}): {e}")
        return []


# ── 중복 체크 ──────────────────────────────────────

def check_already_ran_today():
    from datetime import date
    try:
        with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() == str(date.today())
    except:
        return False

def save_run_today():
    from datetime import date
    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        f.write(str(date.today()))

def load_published_ids():
    if not os.path.exists(PUBLISHED_FILE):
        return set()
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    ids = set()
    with open(PUBLISHED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                if parts[2].strip() >= cutoff:
                    ids.add(parts[0].strip())
            elif parts:
                ids.add(parts[0].strip())
    return ids

def save_published_product(product_id, product_name):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(PUBLISHED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{product_id}|{product_name}|{today}\n")
    print(f"✅ 발행 기록: {product_name}")


# ── 5개 상품 선택 ──────────────────────────────────

def find_new_products(count=5):
    """4개 카테고리 각 1개 + 시즌 1개 = 총 5개"""
    published_ids = load_published_ids()
    print(f"📋 30일 이내 발행: {len(published_ids)}개")

    results  = []
    used_ids = set(published_ids)

    # 1~4: 고정 카테고리 각 1개
    for category in CATEGORIES:
        print(f"\n🔍 [{len(results)+1}/5] {category['name']}")
        products = get_coupang_products(category["name"])

        for p in products:
            pid = p.get("productId", "")
            if not pid or pid in used_ids:
                continue
            used_ids.add(pid)
            results.append((category, p))
            print(f"   ✅ {p['title'][:35]}")
            break
        else:
            print(f"   ⚠️ 미발행 상품 없음")

    # 5: 시즌 상품
    season_kw  = get_season_keyword()
    season_cat = {"name": f"시즌({season_kw})", "id": "season"}
    print(f"\n🌿 [5/5] 시즌: '{season_kw}'")
    for p in get_coupang_products(season_kw):
        pid = p.get("productId", "")
        if not pid or pid in used_ids:
            continue
        used_ids.add(pid)
        results.append((season_cat, p))
        print(f"   ✅ {p['title'][:35]}")
        break

    print(f"\n📦 총 {len(results)}개 선택")
    return results


# ── 이미지 수집 (최대 4장) ────────────────────────

def get_product_images(product):
    """쿠팡 기본 이미지 + 네이버 이미지 검색으로 최대 4장"""
    images = []

    # 1장: 쿠팡 상품 이미지
    thumb = product.get("image", "")
    if thumb:
        images.append(thumb)

    # 나머지: 네이버 이미지 검색 (blog.json과 동일한 검색 API - 정상 작동)
    name = product.get("title", "")
    if name and len(images) < 4 and NAVER_CLIENT_ID:
        try:
            res = requests.get(
                "https://openapi.naver.com/v1/search/image",
                headers={
                    "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                },
                params={"query": name, "display": 6, "sort": "sim", "filter": "large"},
                timeout=10
            )
            res.raise_for_status()
            for item in res.json().get("items", []):
                url = item.get("link", "")
                if url and url not in images:
                    images.append(url)
                if len(images) >= 4:
                    break
        except Exception as e:
            print(f"⚠️ 이미지 검색 오류: {e}")

    print(f"🖼️ 이미지 {len(images)}장 수집")
    return images[:4]


# ── Claude 글 작성 ─────────────────────────────────

def generate_shopping_post(category, product):
    if not CLAUDE_API_KEY:
        print("⚠️ Claude API 키 없음")
        return None, None, None

    name  = product.get("title", "")
    brand = product.get("brand", "") or "브랜드 미상"
    cat1  = product.get("category1", category["name"])

    prompt = f"""너는 네이버 쇼핑 블로그에 제휴 마케팅 상품 추천 글을 쓰는 전문 작가야.

상품 정보:
- 상품명: {name}
- 브랜드: {brand}
- 카테고리: {cat1}

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
이 포스팅은 쿠팡 파트너스 활동의 일환으로, 일정액의 수수료를 제공받습니다.

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

        titles_m = re.search(r"---SEO_TITLES_START---(.+?)---SEO_TITLES_END---", raw, re.DOTALL)
        seo_titles = titles_m.group(1).strip() if titles_m else ""

        body_m = re.search(r"---BODY_START---(.+?)---BODY_END---", raw, re.DOTALL)
        if not body_m:
            body_m = re.search(r"---BODY_START---(.+?)---TAGS_START---", raw, re.DOTALL)
        post_body = body_m.group(1).strip() if body_m else ""

        post_body = re.sub(r'\*\*(.+?)\*\*', r'\1', post_body)
        post_body = re.sub(r'\[소제목\d+\s*:\s*([^\]]+)\]', r'\1', post_body)
        post_body = re.sub(r'^#+\s*', '', post_body, flags=re.MULTILINE)
        post_body = re.sub(r'\n{3,}', '\n\n', post_body).strip()

        tags_m = re.search(r"---TAGS_START---(.+?)---TAGS_END---", raw, re.DOTALL)
        hashtags = tags_m.group(1).strip() if tags_m else ""

        return seo_titles, post_body, hashtags
    except Exception as e:
        print(f"⚠️ Claude 오류: {e}")
        return None, None, None


# ── 이메일 발송 ────────────────────────────────────

def send_shopping_email_bulk(items):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not items:
        return

    kst       = datetime.utcnow() + timedelta(hours=9)
    today_str = kst.strftime("%Y년 %m월 %d일")
    now_str   = kst.strftime("%Y-%m-%d %H:%M")
    colors    = ["#3F51B5", "#7B1FA2", "#00796B", "#E65100", "#C62828"]

    cards_html = ""
    for i, item in enumerate(items):
        cat        = item["category"]
        product    = item["product"]
        images     = item.get("images", [])
        seo_titles = item.get("seo_titles", "")
        post_body  = item.get("post_body", "")
        hashtags   = item.get("hashtags", "")
        pub_time   = item.get("pub_time_str", f"{6+i*3:02d}:00")
        link       = product.get("link", "")

        color = colors[i % len(colors)]
        name  = product.get("title", "")
        price = product.get("lprice", "")
        try:
            price_fmt = f"{int(price):,}원" if price else "가격 미정"
        except:
            price_fmt = price or "가격 미정"

        # 본문에 실제 쿠팡 링크 삽입
        body_with_link = post_body
        if link:
            body_with_link = body_with_link.replace(
                "👇 현재 가격 확인하기\n━━━━━━━━━━━━━━━━━━",
                f"👇 현재 가격 확인하기\n{link}\n━━━━━━━━━━━━━━━━━━"
            ).replace(
                "👇 오늘 최저가 확인하기",
                f"👇 오늘 최저가 확인하기\n{link}"
            )

        body_html = "".join(
            f"<div style='margin:0 0 12px 0'>{line}</div>"
            for line in body_with_link.split("\n") if line.strip()
        )
        title_lines = [l.strip() for l in seo_titles.strip().split("\n") if l.strip()]
        titles_html = "".join(
            f'<div style="margin:4px 0;padding:5px 10px;background:#f8f8f8;border-radius:4px;font-size:13px">{j+1}. {re.sub(r"^[1-5][.)\\s]+","",l).strip()}</div>'
            for j, l in enumerate(title_lines[:5])
        )

        img_parts = [
            f'<img src="{u}" style="width:calc(50% - 4px);max-height:130px;object-fit:cover;border-radius:6px;display:inline-block;vertical-align:top" alt="상품이미지">'
            for u in images[:4]
        ]
        img_html = f'<div style="margin:8px 0;display:flex;flex-wrap:wrap;gap:4px">{"".join(img_parts)}</div>' if img_parts else ""

        link_html = f'<div style="margin:8px 0"><a href="{link}" style="background:#e8274b;color:white;padding:6px 14px;border-radius:4px;text-decoration:none;font-size:13px;font-weight:bold">🛒 쿠팡 링크 열기</a></div>' if link else ""

        cards_html += f"""
<div style="border:1px solid #e0e0e0;border-left:4px solid {color};background:#fff;margin:14px 0;overflow:hidden">
  <div style="background:{color};color:white;padding:10px 16px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <span style="background:rgba(255,255,255,0.2);padding:2px 10px;border-radius:12px;font-weight:bold;font-size:13px">{i+1}번</span>
      &nbsp;<strong style="font-size:14px">{name[:42]}</strong>
    </div>
    <div style="font-size:12px;opacity:0.85;white-space:nowrap">📅 {pub_time} 발행</div>
  </div>
  <div style="padding:12px 16px">
    {img_html}
    <div style="font-size:12px;color:#777;margin-bottom:8px">카테고리: {cat['name']} &nbsp;|&nbsp; 최저가: {price_fmt}</div>
    {link_html}
    <div style="margin:10px 0">
      <div style="font-size:12px;font-weight:bold;color:#333;margin-bottom:5px">📌 SEO 제목 (하나 선택)</div>
      {titles_html}
    </div>
    <details style="margin-top:10px">
      <summary style="cursor:pointer;font-size:13px;color:{color};font-weight:bold;padding:4px 0">✍️ 본문 펼치기 (복붙용)</summary>
      <div style="background:#fafafa;border:1px solid #eee;padding:12px;border-radius:4px;margin-top:8px;font-size:15px;line-height:1.9">{body_html}</div>
      <div style="margin-top:10px">
        <div style="font-size:12px;color:#555;font-weight:bold;margin-bottom:4px">📋 복붙용 텍스트 (클릭 → Ctrl+A → Ctrl+C → 네이버 붙여넣기)</div>
        <textarea onclick="this.select()" readonly style="width:100%;height:220px;font-size:14px;line-height:1.9;font-family:맑은고딕,sans-serif;border:2px solid {color};border-radius:4px;padding:10px;box-sizing:border-box;resize:vertical;background:#fff">{body_with_link}</textarea>
        <div style="background:#f5f5f5;padding:8px;border-radius:4px;margin-top:6px;font-size:12px;color:#888">{hashtags}</div>
      </div>
    </details>
  </div>
</div>
"""

    email_html = f"""<html><body style="font-family:맑은고딕,sans-serif;max-width:680px;margin:0 auto;padding:20px;background:#f0f2f5">

<div style="background:#e8274b;color:white;padding:18px 20px;border-radius:10px;margin-bottom:14px;text-align:center">
  <div style="font-size:12px;opacity:0.7;margin-bottom:4px">🛒 쇼핑AI · 쿠팡 파트너스 · 네이버 블로그 전용</div>
  <div style="font-size:20px;font-weight:bold">{today_str} · 총 {len(items)}개 상품</div>
  <div style="font-size:12px;opacity:0.65;margin-top:4px">쿠팡 링크가 본문에 자동 삽입되어 있습니다</div>
</div>

<div style="background:#fff;border-radius:8px;padding:12px 16px;margin-bottom:14px;font-size:13px;border:1px solid #ddd">
  <strong>📋 사용 방법</strong><br>
  1️⃣ SEO 제목 1개 선택 &nbsp; 2️⃣ 본문 펼쳐서 복붙 &nbsp; 3️⃣ 그대로 발행 (쿠팡 링크 자동 포함!)<br>
  <span style="color:#e8274b;font-size:12px">⏰ 권장 발행 시간: 06:00 / 09:00 / 12:00 / 15:00 / 18:00</span>
</div>

{cards_html}

<p style="text-align:center;font-size:11px;color:#aaa;margin-top:20px">쇼핑 자동화 v5 (쿠팡 파트너스) · {now_str}</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[쇼핑발행] {today_str} · {len(items)}개 상품"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())

    print(f"✅ 이메일 발송 완료 ({len(items)}개) → {EMAIL_RECIPIENT}")


# ── 메인 ──────────────────────────────────────────

def run_shopping_task(category_ids=None, count=5, send_email_flag=True,
                      log_fn=print, force=False):
    from datetime import datetime as _dt, timezone
    _tz = timezone(timedelta(hours=9))

    if not force and check_already_ran_today():
        log_fn("⏭️  오늘 이미 실행됨 (force=True로 강제 실행)")
        return {"success": False, "count": 0, "skipped": True}

    log_fn("=" * 50)
    log_fn(f"🛒 쇼핑AI 시작 [{_dt.now(_tz).strftime('%H:%M')}]")
    log_fn("=" * 50)

    selected = find_new_products()

    if not selected:
        log_fn("❌ 발행할 상품 없음")
        return {"success": False, "count": 0}

    email_items = []
    pub_times   = ["06:00", "09:00", "12:00", "15:00", "18:00"]

    for i, (category, product) in enumerate(selected):
        log_fn(f"\n[{i+1}/{len(selected)}] {product.get('title','')[:40]}")

        log_fn("  🖼️ 이미지 수집 중...")
        images = get_product_images(product)

        log_fn("  ✍️ Claude 글 작성 중...")
        seo_titles, post_body, hashtags = generate_shopping_post(category, product)
        if not post_body:
            log_fn("  ⚠️ 글 작성 실패, 스킵")
            continue

        pid = product.get("productId", "")
        if pid:
            save_published_product(pid, product.get("title", ""))

        email_items.append({
            "category":     category,
            "product":      product,
            "images":       images,
            "seo_titles":   seo_titles,
            "post_body":    post_body,
            "hashtags":     hashtags,
            "pub_time_str": pub_times[i] if i < len(pub_times) else f"{6+i*3:02d}:00",
        })

    if email_items and send_email_flag:
        log_fn(f"\n📧 이메일 발송 중... ({len(email_items)}개)")
        send_shopping_email_bulk(email_items)
        if not force:
            save_run_today()
        log_fn(f"✅ 완료! {len(email_items)}개 상품")
    elif email_items:
        log_fn(f"\n✅ 완료! {len(email_items)}개 (이메일 생략)")
    else:
        log_fn("❌ 처리된 상품 없음")

    return {"success": bool(email_items), "count": len(email_items)}


def main():
    run_shopping_task(force=False)

if __name__ == "__main__":
    main()
