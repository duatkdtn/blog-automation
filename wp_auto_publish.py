# ================================================
# wp_auto_publish.py
# 한발뉴스24 상등급 기사 → Claude Sonnet 4.6 → WordPress 자동 발행
# 실행: python wp_auto_publish.py
# ================================================

import json, os, sys, time, io, re, smtplib, base64, pickle
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from requests.auth import HTTPBasicAuth
import anthropic

# ── 설정 로드 ──────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config import (CLAUDE_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT,
                        WP_URL, WP_USER, WP_PASS)
except ImportError:
    CLAUDE_API_KEY     = os.environ.get("CLAUDE_API_KEY", "")
    GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
    EMAIL_RECIPIENT    = os.environ.get("EMAIL_RECIPIENT", "")
    WP_URL  = os.environ.get("WP_URL",  "https://hijaneeinfo.com")
    WP_USER = os.environ.get("WP_USER", "duatkdtn@gmail.com")
    WP_PASS = os.environ.get("WP_PASS", "")

KST  = ZoneInfo("Asia/Seoul")
AUTH = HTTPBasicAuth(WP_USER, WP_PASS)
BASE = os.path.dirname(os.path.abspath(__file__))

MAX_POSTS      = 8   # 최대 발행 개수
INTERVAL_HOURS = 3   # 발행 간격 (시간)

# 카테고리명 → WordPress 카테고리 ID
CAT_MAP = {
    "생활·정책":    207, "건강·의료":    208, "재테크·금융":  209,
    "부동산":        210, "교육·육아":    211, "자동차·교통":  212,
    "음식·건강식":  213, "여행·나들이":  214, "디지털·IT":   215,
    "법률·생활법":  216, "노약자·시니어":217, "연예·문화":   218,
    "트렌드·사회":  219,
}

# 카테고리별 추천 계산기 (글에 포함)
CALC_LINKS = {
    "재테크·금융": ("연봉 실수령액 계산기", "https://www.hijanee.com/p/blog-page.html"),
    "생활·정책":   ("근로장려금 계산기",    "https://www.hijanee.com/p/blog-page_10.html"),
    "노약자·시니어":("국민연금 예상수령액 계산기","https://www.hijanee.com/p/blog-page_15.html"),
    "부동산":       ("취득세 계산기",        "https://www.hijanee.com/p/blog-page_758.html"),
    "교육·육아":    ("만 나이 계산기",       "https://www.hijanee.com/p/blog-page_12.html"),
}

# ================================================
# 1. 한발뉴스 결과 로드 + 상 등급 추출
# ================================================

def load_top_articles():
    """오늘 한발뉴스 결과에서 상 등급 기사 추출 (점수 높은 순, 최대 MAX_POSTS개)"""
    today_file = datetime.now(KST).strftime("%Y%m%d")
    json_path  = os.path.join(BASE, f"hanbal_result_{today_file}.json")

    if not os.path.exists(json_path):
        print(f"❌ 결과 파일 없음: {json_path}")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        result = json.load(f)

    items = result.get("항목", [])
    top = [
        i for i in items
        if i.get("상태") == "선정"
        and i.get("블로그적합도", {}).get("등급") == "상"
    ]
    top.sort(key=lambda x: x.get("블로그적합도", {}).get("점수", 0), reverse=True)
    return top[:MAX_POSTS]


# ================================================
# 2. Claude API로 WordPress 글 생성
# ================================================

def build_post_prompt(article, today_str):
    cat       = article.get("카테고리", "")
    title_h   = article.get("제목", "")
    summary   = article.get("한줄요약", "")
    facts     = article.get("핵심사실", [])
    keywords  = article.get("키워드후보", [])
    link      = article.get("링크", "")
    source    = article.get("출처", "")
    confirmed = article.get("확정여부", "")

    facts_text   = "\n".join([f"- {f}" for f in facts])
    keywords_str = ", ".join(keywords)

    calc_hint = ""
    if cat in CALC_LINKS:
        c_name, c_url = CALC_LINKS[cat]
        calc_hint = f'\n- 계산기 버튼 포함: <a href="{c_url}" target="_blank" rel="noopener" style="display:inline-block;background:#2980b9;color:#fff;padding:12px 28px;border-radius:6px;font-size:16px;font-weight:bold;text-decoration:none;">👉 {c_name} 바로 가기</a>'

    system = "당신은 한국어 생활정보 블로그 전문 작가입니다. 워드프레스 HTML 글을 작성합니다. JSON만 출력합니다."

    user = f"""아래 뉴스 소재로 워드프레스 블로그 글을 HTML로 완전하게 작성해주세요.

[소재 정보]
카테고리: {cat}
기사 요약 제목: {title_h}
한줄 요약: {summary}
핵심 사실:
{facts_text}
키워드 후보: {keywords_str}
확정 여부: {confirmed}
출처: {source}
원본 링크: {link}
오늘 날짜: {today_str}

[글 작성 원칙]
- 5,000자 이상 작성
- inline style만 사용 (style 태그 금지)
- 외부 링크: target="_blank" rel="noopener" 필수
- "마치며" 섹션 쓰지 않기
- 파트너스 활동 안내 박스 쓰지 않기
- 면책문구 포함 (글 맨 아래)
- 본문에 날짜 기준 문구 넣지 않기

[글 구조 - 이 순서 반드시 지키기]
① 파란 핵심 요약 박스 (background:#eaf4fb;border:2px solid #2980b9) - ✅ 5개 항목으로 이 글의 핵심 요약
② 목차 (background:#f8f9fa;border-left:4px solid #2980b9) - h2 id와 연결
③ 도입부: 경험담 느낌으로 (~더라고요, ~이에요, ~해요), 2~3 문단
④ 본문: 표 최소 2개 (thead background:#2980b9, 파란색), 리스트 박스 포함
⑤ 단계별 설명 (해당 시): ol 태그, 각 단계 쉽게 설명
⑥ 오해/주의사항: background:#fdf2f8;border:1px solid #d2b4de (보라색), ❌ 기호
⑦ FAQ 최소 5개: background:#f8f9fa;border-left:4px solid #2980b9
⑧ 이런 분들 해당: background:#eaf4fb;border:1px solid #aed6f1 - 👉 체크리스트 5개
{calc_hint}
⑨ 결론: background:#2980b9 파란 배경, 흰 글씨, CTA + 관련글 유도 + 댓글 유도
⑩ 내부링크 박스: background:#eaf4fb;border:1px solid #aed6f1 - "📌 함께 읽으면 좋은 글" + 같은 주제 관련 글 3개 (URL은 / 로만 표기)
⑪ 외부버튼: 관련 공식 사이트 파란 버튼 (target="_blank" rel="noopener noreferrer")
⑫ 면책문구: background:#f8f9fa;border:1px solid #dee2e6

[말투]
✅ ~더라고요, ~이에요, ~해요 (친근한 존댓말)
✅ 어려운 용어는 쉬운 말로
✅ 예시/계산 예시 포함
❌ ~습니다 금지
❌ 전문 용어 그대로 쓰기 금지

[제목 공식]
메인키워드(앞에) + 연관검색어 + 클릭유도형
→ 30자 이내, 숫자 포함

[출력 형식]
반드시 아래 JSON만 출력하세요. 코드블록(```), 설명 텍스트 없이 JSON만:
{{
  "wp_title": "워드프레스 글 제목 (30자 이내)",
  "wp_slug": "영문-슬러그-최대-6단어",
  "focus_keyword": "포커스 키워드 (검색량 높은 표현)",
  "meta_description": "메타 설명 (120자 이내, 핵심 정보 포함)",
  "tags": ["태그1", "태그2", "태그3"],
  "html_content": "완전한 HTML 본문 (5000자 이상, inline style만)"
}}"""

    return system, user


def generate_wp_post(article, today_str):
    """Claude Sonnet 4.6으로 WordPress 글 생성"""
    system, user = build_post_prompt(article, today_str)

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user}]
    )

    raw = msg.content[0].text.strip()
    # 혹시 코드블록 있으면 제거
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    raw = raw.strip()

    return json.loads(raw)


# ================================================
# 3. 썸네일 생성 (Pillow)
# ================================================

def make_thumbnail(title, category, today_str):
    """1200×630 WebP 썸네일 생성"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  ⚠️ Pillow 없음 - 썸네일 생성 건너뜀")
        return None

    W, H = 1200, 630
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # 그라디언트 배경 (파란색 계열)
    for y in range(H):
        t = y / H
        r = int(26  + (41  - 26)  * t)
        g = int(82  + (128 - 82)  * t)
        b = int(118 + (185 - 118) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # 폰트 로드 (여러 경로 시도)
    def load_font(size):
        paths = [
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "C:/Windows/Fonts/malgunbd.ttf",
            "C:/Windows/Fonts/NanumGothicBold.ttf",
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except:
                    continue
        return ImageFont.load_default()

    font_title = load_font(52)
    font_cat   = load_font(30)
    font_date  = load_font(22)

    # 카테고리 배지 (상단 왼쪽)
    badge_text = f"  {category}  "
    draw.rounded_rectangle([(50, 50), (50 + len(badge_text) * 18, 100)],
                           radius=8, fill="#1a5276")
    draw.text((55, 60), badge_text.strip(), fill="white", font=font_cat)

    # 제목 텍스트 (중앙, 최대 2줄)
    max_chars = 18
    if len(title) <= max_chars:
        lines = [title]
    elif len(title) <= max_chars * 2:
        lines = [title[:max_chars], title[max_chars:]]
    else:
        lines = [title[:max_chars], title[max_chars:max_chars*2] + "…"]

    total_h = len(lines) * 75
    y_start = (H - total_h) // 2 - 20
    for line in lines:
        # 텍스트 경계 계산
        bbox  = draw.textbbox((0, 0), line, font=font_title)
        tw    = bbox[2] - bbox[0]
        x_pos = (W - tw) // 2
        # 그림자
        draw.text((x_pos + 2, y_start + 2), line, fill=(0, 0, 0, 100), font=font_title)
        draw.text((x_pos, y_start), line, fill="white", font=font_title)
        y_start += 75

    # 사이트 & 날짜 (하단 중앙)
    foot_text = f"hijanee.com  |  {today_str}"
    bbox  = draw.textbbox((0, 0), foot_text, font=font_date)
    tw    = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H - 60), foot_text, fill="#aed6f1", font=font_date)

    # WebP 저장
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=90)
    buf.seek(0)
    return buf.read()


# ================================================
# 4. WordPress REST API
# ================================================

def upload_media(img_bytes, slug_hint):
    """썸네일을 WordPress 미디어 라이브러리에 업로드"""
    if not img_bytes:
        return None
    ts       = datetime.now(KST).strftime("%Y%m%d%H%M%S")
    filename = f"wp-auto-{slug_hint[:20]}-{ts}.webp"
    res = requests.post(
        f"{WP_URL}/wp-json/wp/v2/media",
        auth=AUTH,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type":        "image/webp",
        },
        data=img_bytes,
        timeout=30,
    )
    if res.status_code in (200, 201):
        return res.json()["id"]
    print(f"  ❌ 미디어 업로드 실패: {res.status_code} {res.text[:150]}")
    return None


def get_or_create_tag(tag_name):
    """태그 ID 조회 또는 생성"""
    tag_name = tag_name.strip()
    if not tag_name:
        return None
    # 검색
    r = requests.get(
        f"{WP_URL}/wp-json/wp/v2/tags",
        auth=AUTH,
        params={"search": tag_name, "per_page": 5},
        timeout=10,
    )
    if r.status_code == 200:
        for t in r.json():
            if t["name"] == tag_name:
                return t["id"]
    # 없으면 생성
    r2 = requests.post(
        f"{WP_URL}/wp-json/wp/v2/tags",
        auth=AUTH,
        json={"name": tag_name},
        timeout=10,
    )
    if r2.status_code in (200, 201):
        return r2.json()["id"]
    return None


def publish_post(post_data, media_id, tag_ids, cat_id, publish_dt):
    """WordPress에 글 발행 (즉시 또는 예약)"""
    status = "publish" if publish_dt is None else "future"

    payload = {
        "title":          post_data["wp_title"],
        "slug":           post_data.get("wp_slug", ""),
        "content":        post_data["html_content"],
        "status":         status,
        "categories":     [cat_id],
        "tags":           tag_ids,
        "featured_media": media_id or 0,
        "meta": {
            "rank_math_focus_keyword": post_data.get("focus_keyword", ""),
            "rank_math_description":   post_data.get("meta_description", ""),
        },
    }
    if publish_dt:
        # WordPress는 KST 기준 날짜를 받음 (사이트 타임존이 서울로 설정된 경우)
        payload["date"] = publish_dt.strftime("%Y-%m-%dT%H:%M:%S")

    res = requests.post(
        f"{WP_URL}/wp-json/wp/v2/posts",
        auth=AUTH,
        json=payload,
        timeout=30,
    )
    if res.status_code in (200, 201):
        data = res.json()
        return data["id"], data.get("link", "")
    print(f"  ❌ 발행 실패: {res.status_code} {res.text[:300]}")
    return None, None


# ================================================
# 5. Google 색인 요청
# ================================================

def request_google_indexing(post_url):
    """Google Indexing API로 색인 요청"""
    try:
        # GitHub Actions: token.pickle을 환경변수에서 복원
        token_b64 = os.environ.get("GOOGLE_TOKEN", "")
        token_path = os.path.join(BASE, "token.pickle")
        if token_b64 and not os.path.exists(token_path):
            with open(token_path, "wb") as f:
                f.write(base64.b64decode(token_b64))

        if not os.path.exists(token_path):
            print(f"  ⚠️ token.pickle 없음 - 색인 요청 건너뜀")
            return False

        from google.auth.transport.requests import Request as GRequest

        with open(token_path, "rb") as f:
            creds = pickle.load(f)

        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)

        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type":  "application/json",
        }
        body = {"url": post_url, "type": "URL_UPDATED"}
        resp = requests.post(
            "https://indexing.googleapis.com/v3/urlNotifications:publish",
            json=body,
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            print(f"  ✅ 색인 요청 성공: {post_url}")
            return True
        else:
            print(f"  ⚠️ 색인 요청 실패 ({resp.status_code}): {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"  ⚠️ 색인 요청 오류: {e}")
        return False


# ================================================
# 6. 완료 이메일 발송
# ================================================

def send_result_email(results, today_str):
    """발행 결과 이메일 발송"""
    success_list = [r for r in results if r.get("wp_id")]

    cards_html = ""
    for r in results:
        ok        = bool(r.get("wp_id"))
        color     = "#27ae60" if ok else "#e74c3c"
        status_lbl = "✅ 발행 완료" if ok else "❌ 실패"
        sched     = r.get("schedule_dt", "즉시")
        link_html = (f'<br><a href="{r["wp_link"]}" target="_blank" style="color:#2980b9;font-size:13px;">글 보기 →</a>'
                     if r.get("wp_link") else "")
        cards_html += f"""
<div style="border:1px solid #e0e0e0;border-radius:8px;padding:14px;margin:6px 0;border-left:4px solid {color};">
  <span style="font-weight:bold;color:{color};">{status_lbl}</span>&nbsp;&nbsp;
  <span style="color:#2c3e50;">{r.get('title','')}</span><br>
  <small style="color:#888;">카테고리: {r.get('cat','')} | 발행: {sched}</small>
  {link_html}
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f6fa;font-family:'맑은 고딕',sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#2980b9,#1a5276);border-radius:12px;padding:24px;margin-bottom:16px;text-align:center;">
    <h1 style="margin:0;color:#fff;font-size:22px;">🚀 워드프레스 자동 발행 결과</h1>
    <p style="margin:6px 0 0;color:#aed6f1;font-size:14px;">{today_str} · 발행 {len(success_list)}/{len(results)}개</p>
  </div>
  {cards_html}
  <div style="text-align:center;padding:16px;color:#bbb;font-size:12px;border-top:1px solid #e0e0e0;margin-top:10px;">
    한발뉴스24 × WordPress 자동 발행 시스템
  </div>
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[워프 자동발행] {today_str} {len(success_list)}개 완료"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())
        print(f"  ✅ 이메일 발송 완료 → {EMAIL_RECIPIENT}")
    except Exception as e:
        print(f"  ❌ 이메일 발송 실패: {e}")


# ================================================
# 메인
# ================================================

def main():
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"[WordPress 자동발행] {today_str}")
    print(f"{'='*55}")

    # 상 등급 기사 로드
    top_articles = load_top_articles()
    n = len(top_articles)
    print(f"\n상 등급 기사: {n}개 (최대 {MAX_POSTS}개 발행)")

    if n == 0:
        print("발행할 상 등급 기사 없음. 종료합니다.")
        sys.exit(0)

    # 발행 시간 계획
    now = datetime.now(KST)
    schedule_times = [None] + [now + timedelta(hours=INTERVAL_HOURS * i) for i in range(1, n)]

    results = []

    for idx, article in enumerate(top_articles):
        cat        = article.get("카테고리", "")
        cat_id     = CAT_MAP.get(cat, 207)
        sched_dt   = schedule_times[idx]
        sched_label = "즉시" if sched_dt is None else sched_dt.strftime("%Y-%m-%d %H:%M")

        print(f"\n[{idx+1}/{n}] {article.get('제목','')}")
        print(f"  카테고리: {cat} (ID={cat_id}) | 발행: {sched_label}")

        r = {
            "cat":         cat,
            "title":       article.get("제목", ""),
            "wp_id":       None,
            "wp_link":     None,
            "schedule_dt": sched_label,
        }

        try:
            # ① 글 생성
            print("  📝 글 생성 중 (Claude Sonnet 4.6)...")
            post_data = generate_wp_post(article, today_str)
            r["title"] = post_data.get("wp_title", r["title"])
            print(f"     제목: {r['title']}")

            # ② 썸네일 생성
            print("  🖼️ 썸네일 생성 중...")
            thumb_bytes = make_thumbnail(post_data["wp_title"], cat, today_str)

            # ③ 썸네일 업로드
            print("  ⬆️ 썸네일 업로드 중...")
            media_id = upload_media(thumb_bytes, post_data.get("wp_slug", "post"))

            # ④ 태그 처리
            tag_ids = []
            for tag_name in post_data.get("tags", [])[:3]:
                tid = get_or_create_tag(tag_name)
                if tid:
                    tag_ids.append(tid)
                    time.sleep(0.3)
            print(f"     태그 ID: {tag_ids}")

            # ⑤ 발행
            print("  🚀 WordPress 발행 중...")
            wp_id, wp_link = publish_post(post_data, media_id, tag_ids, cat_id, sched_dt)

            if wp_id:
                r["wp_id"]   = wp_id
                r["wp_link"] = wp_link
                print(f"  ✅ 완료! WP ID={wp_id}")
                print(f"     링크: {wp_link}")

                # ⑥ 즉시 발행 글만 색인 요청
                if sched_dt is None and wp_link:
                    request_google_indexing(wp_link)

        except Exception as e:
            import traceback
            print(f"  ❌ 오류 발생: {e}")
            traceback.print_exc()

        results.append(r)

        # API 호출 간격
        if idx < n - 1:
            print("  ⏳ 3초 대기...")
            time.sleep(3)

    # ⑦ 결과 이메일
    print(f"\n{'='*55}")
    print("이메일 발송 중...")
    send_result_email(results, today_str)

    success = len([r for r in results if r.get("wp_id")])
    print(f"\n🎉 완료! 발행 성공 {success}/{len(results)}개")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
