# ================================================
# 쇼핑커넥트 블로그 자동화 v1.0
# 네이버 쇼핑 API → 인기 상품 → Claude 글 작성 → 이메일 발송
# ================================================

import os
import re
import sys
import requests
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── 환경변수 ──────────────────────────────────────
NAVER_CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")
CLAUDE_API_KEY      = os.environ.get("CLAUDE_API_KEY")
CLAUDE_MODEL        = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GMAIL_ADDRESS       = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT     = os.environ.get("EMAIL_RECIPIENT", "duatkdtn@gmail.com")

# config.py 가 있으면 불러오기 (로컬 실행용)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    NAVER_CLIENT_ID     = NAVER_CLIENT_ID     or getattr(config, "NAVER_CLIENT_ID", None)
    NAVER_CLIENT_SECRET = NAVER_CLIENT_SECRET or getattr(config, "NAVER_CLIENT_SECRET", None)
    CLAUDE_API_KEY      = CLAUDE_API_KEY      or getattr(config, "CLAUDE_API_KEY", None)
    CLAUDE_MODEL        = CLAUDE_MODEL        or getattr(config, "CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    GMAIL_ADDRESS       = GMAIL_ADDRESS       or getattr(config, "GMAIL_ADDRESS", None)
    GMAIL_APP_PASSWORD  = GMAIL_APP_PASSWORD  or getattr(config, "GMAIL_APP_PASSWORD", None)
    EMAIL_RECIPIENT     = getattr(config, "EMAIL_RECIPIENT", EMAIL_RECIPIENT)
except Exception:
    pass

# ── 상수 ──────────────────────────────────────────
PUBLISHED_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published_products.txt")
NAVER_BLOG_URL   = "https://blog.naver.com/janee_item"

# 순환 검색 키워드 목록 (순서대로 돌면서 새 상품 찾음)
SHOPPING_KEYWORDS = [
    # 가전
    "제습기", "공기청정기", "선풍기", "에어컨", "로봇청소기", "식기세척기", "전기밥솥",
    "전기포트", "전자레인지", "무선청소기",
    # 뷰티/헬스
    "선크림", "마스크팩", "에센스", "세럼", "비타민", "홍삼",
    # 생활
    "침구세트", "수납함", "텀블러", "캔들", "디퓨저",
    # 스포츠/야외
    "요가매트", "아령", "러닝화", "물통",
    # 식품
    "단백질쉐이크", "그래놀라", "견과류",
    # 반려동물
    "강아지사료", "고양이간식",
    # 육아
    "유아물티슈", "아기로션",
]


# ── 발행 기록 관리 ────────────────────────────────

def load_published_ids():
    """이미 발행된 상품 ID 목록 반환"""
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
    """발행된 상품을 기록 파일에 추가"""
    today = datetime.now().strftime("%Y-%m-%d")
    with open(PUBLISHED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{product_id}|{product_name}|{today}\n")
    print(f"✅ 발행 기록 저장: {product_name} ({product_id})")


# ── 네이버 쇼핑 API ───────────────────────────────

def get_top_product(keyword):
    """
    네이버 쇼핑 검색 API로 키워드의 인기 상품 1위 반환
    반환: dict {productId, title, brand, lprice, image, link, category1} 또는 None
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("⚠️ 네이버 API 키 없음")
        return None

    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query":   keyword,
        "display": 5,       # 상위 5개 가져와서 1위 선택
        "sort":    "sim",   # 정확도(인기)순
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        items = res.json().get("items", [])
        if not items:
            return None

        # HTML 태그 제거 후 1위 반환
        item = items[0]
        item["title"] = re.sub(r"<[^>]+>", "", item.get("title", ""))
        return item

    except Exception as e:
        print(f"⚠️ 네이버 쇼핑 API 오류 ({keyword}): {e}")
        return None


def find_new_product():
    """
    SHOPPING_KEYWORDS를 순서대로 검색해서
    아직 발행하지 않은 상품을 찾아 반환
    반환: (keyword, product_dict) 또는 (None, None)
    """
    published_ids = load_published_ids()
    print(f"📋 이미 발행된 상품 수: {len(published_ids)}개")

    for keyword in SHOPPING_KEYWORDS:
        print(f"🔍 검색 중: {keyword}")
        product = get_top_product(keyword)
        if not product:
            continue

        product_id = str(product.get("productId", ""))
        if product_id and product_id not in published_ids:
            print(f"✅ 새 상품 발견: {product['title']} (키워드: {keyword})")
            return keyword, product
        else:
            print(f"   └ 이미 발행된 상품, 건너뜀")

    print("⚠️ 모든 키워드에서 새 상품을 찾지 못함")
    return None, None


# ── Claude 글 작성 ────────────────────────────────

def generate_shopping_post(keyword, product):
    """
    Claude Haiku로 상품 추천 블로그 글 작성
    반환: (title, content) 또는 (None, None)
    """
    if not CLAUDE_API_KEY:
        print("⚠️ Claude API 키 없음")
        return None, None

    title_str    = product.get("title", keyword)
    brand_str    = product.get("brand", "")
    price_str    = product.get("lprice", "")
    category_str = product.get("category1", "")

    # 가격 포맷팅 (숫자만 있을 경우)
    try:
        price_fmt = f"{int(price_str):,}원" if price_str else "가격 미정"
    except Exception:
        price_fmt = price_str or "가격 미정"

    prompt = f"""너는 네이버 블로그에 쇼핑 상품을 추천하는 글을 쓰는 작가야.

아래 상품 정보를 바탕으로 블로그 추천 글을 써줘.

상품 정보:
- 상품명: {title_str}
- 브랜드: {brand_str}
- 최저가: {price_fmt}
- 카테고리: {category_str}
- 검색 키워드: {keyword}

글쓰기 규칙:
- 초등학생이나 70대 할머니도 바로 이해할 수 있는 쉬운 말로 쓸 것
- 전문 용어, 어려운 한자어 절대 쓰지 말 것
- 나쁜 예: "심폐지구력", "효능 및 효과", "섭취 시" / 좋은 예: "숨이 덜 차요", "이런 점이 좋아요", "먹으면"
- 문장은 짧게. 한 문장에 한 가지 내용만
- 길이: 600~800자

글 구성:
1. 공감 도입부 (이 상품이 왜 필요한지 생활 속 상황)
2. 이 상품의 좋은 점 3가지 (번호 없이 자연스럽게)
3. 가격 언급 (부담 없다는 식으로)
4. 마무리 + 구매 링크 안내

마지막 문장 뒤에 반드시 이 두 줄을 그대로 넣어:
👉 지금 바로 확인해보세요: [쇼핑링크]
📌 다른 추천 상품도 구경하세요: {NAVER_BLOG_URL}

제목도 같이 만들어줘. 제목 형식:
제목: (여기에 제목)

그리고 본문을 이어서 써줘."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()

        # 제목 추출
        title_match = re.search(r"^제목[:：]\s*(.+)$", raw, re.MULTILINE)
        post_title = title_match.group(1).strip() if title_match else f"{keyword} 추천 1위"

        # 본문 추출 (제목 줄 이후)
        if title_match:
            post_content = raw[title_match.end():].strip()
        else:
            post_content = raw

        return post_title, post_content

    except Exception as e:
        print(f"⚠️ Claude 글 생성 오류: {e}")
        return None, None


# ── 이메일 발송 ───────────────────────────────────

def send_shopping_email(keyword, product, post_title, post_content):
    """쇼핑 추천 글을 이메일로 발송"""

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail 환경변수 없음 - 이메일 전송 건너뜀")
        return

    product_name  = product.get("title", keyword)
    product_image = product.get("image", "")
    product_link  = product.get("link", "")
    product_price = product.get("lprice", "")
    product_brand = product.get("brand", "")

    try:
        price_fmt = f"{int(product_price):,}원" if product_price else "가격 미정"
    except Exception:
        price_fmt = product_price or "가격 미정"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 본문 줄바꿈 → HTML
    content_html = post_content.replace("\n", "<br>\n")

    # 이미지 HTML
    image_html = ""
    if product_image:
        image_html = f'<img src="{product_image}" style="max-width:100%;border-radius:8px;margin:10px 0" alt="{product_name}"><br>'

    # 네이버 쇼핑 링크 (쇼핑커넥트용 원본 URL)
    shopping_link_html = ""
    if product_link:
        shopping_link_html = f"""
<div style="background:#fff3cd;border:1px solid #ffc107;padding:15px;border-radius:8px;margin:20px 0">
  <strong>🔗 쇼핑커넥트 링크 만들기</strong><br><br>
  아래 URL을 쇼핑커넥트에 등록해서 링크를 만드세요 (5분 소요):<br><br>
  <a href="{product_link}" style="color:#0066cc;word-break:break-all">{product_link}</a><br><br>
  링크 만들고 나서 본문의 <strong>[쇼핑링크]</strong> 자리에 붙여넣으세요.
</div>
"""

    email_html = f"""
<html><body style="font-family:맑은고딕,sans-serif;max-width:700px;margin:0 auto;padding:20px">

<div style="background:#f0f7ff;border-left:4px solid #4A90E2;padding:15px;margin-bottom:20px;border-radius:4px">
  <h2 style="margin:0 0 8px 0;color:#333">🛒 쇼핑커넥트 블로그 발행용</h2>
  <p style="margin:0;color:#666">{now_str} | 키워드: {keyword}</p>
</div>

<div style="background:#e8f5e9;border:1px solid #4caf50;padding:15px;border-radius:8px;margin-bottom:20px">
  <strong>📦 오늘의 추천 상품</strong><br><br>
  {image_html}
  <strong>상품명:</strong> {product_name}<br>
  <strong>브랜드:</strong> {product_brand or "정보 없음"}<br>
  <strong>최저가:</strong> {price_fmt}
</div>

{shopping_link_html}

<div style="background:#fff;border:1px solid #ddd;padding:12px;border-radius:4px;margin-bottom:20px">
  <strong>📋 사용 방법:</strong><br>
  1. 위 URL로 쇼핑커넥트 링크 생성<br>
  2. 아래 본문에서 <strong>[쇼핑링크]</strong> 찾아서 교체<br>
  3. 네이버 블로그에 복붙 + 상품 이미지 첨부
</div>

<hr style="border:2px solid #333;margin:20px 0">
<h2 style="font-size:20px;color:#111">✍️ 본문 (복붙용)</h2>
<div style="background:#f9f9f9;padding:10px;border-radius:4px;margin-bottom:10px">
  <strong>제목:</strong> {post_title}
</div>
<hr style="border:1px solid #ddd;margin:20px 0">

<div style="line-height:1.9;font-size:15px;color:#222">
{content_html}
</div>

<hr style="border:2px solid #333;margin:30px 0">
<p style="font-size:13px;color:#999;text-align:center">쇼핑 자동화 시스템 · {now_str}</p>

</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[쇼핑발행용] {post_title}"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())

    print(f"✅ 쇼핑 이메일 발송 완료 → {EMAIL_RECIPIENT}")


# ── 메인 ──────────────────────────────────────────

def main():
    print("=" * 50)
    print("🛒 쇼핑커넥트 자동화 시작")
    print("=" * 50)

    # 1. 새 상품 찾기
    keyword, product = find_new_product()
    if not product:
        print("❌ 발행할 새 상품이 없습니다. 종료합니다.")
        sys.exit(0)

    product_name = product.get("title", keyword)
    product_id   = str(product.get("productId", ""))

    # 2. 글 작성
    print(f"\n✍️ 글 작성 중: {product_name}")
    post_title, post_content = generate_shopping_post(keyword, product)
    if not post_title or not post_content:
        print("❌ 글 작성 실패. 종료합니다.")
        sys.exit(1)

    print(f"📝 제목: {post_title}")

    # 3. 이메일 발송
    print("\n📧 이메일 발송 중...")
    send_shopping_email(keyword, product, post_title, post_content)

    # 4. 발행 기록 저장
    if product_id:
        save_published_product(product_id, product_name)

    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
