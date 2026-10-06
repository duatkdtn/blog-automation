# ================================================
# 한발뉴스24 - 이메일 발송 모듈 (hanbal_email.py)
# AI 분류 결과 → HTML 이메일 생성 → Gmail 발송
# ================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# GitHub Actions 환경변수 우선, 없으면 config.py에서 로드
try:
    from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT
except ImportError:
    GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
    EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "")
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 카테고리별 이모지 (워드프레스 카테고리와 동일)
CATEGORY_EMOJI = {
    "생활·정책": "🏛️",
    "건강·의료": "🏥",
    "재테크·금융": "💰",
    "부동산": "🏠",
    "교육·육아": "📚",
    "자동차·교통": "🚗",
    "음식·건강식": "🍽️",
    "여행·나들이": "✈️",
    "디지털·IT": "📱",
    "법률·생활법": "⚖️",
    "노약자·시니어": "👴",
    "연예·문화": "🎬",
    "트렌드·사회": "💡",
}

# 적합도별 색상
GRADE_COLOR = {
    "상": "#27ae60",
    "중": "#f39c12",
    "하": "#e74c3c",
}


def build_html(result):
    """AI 결과 → HTML 이메일 본문 생성"""

    today = result.get("생성일", datetime.now(KST).strftime("%Y-%m-%d"))
    window_start = result.get("기간", {}).get("시작", "")
    window_end = result.get("기간", {}).get("끝", "")
    items = result.get("항목", [])

    # 선정된 항목만
    selected = [i for i in items if i.get("상태") == "선정"]
    skipped = [i for i in items if i.get("상태") == "해당없음"]

    # 카드 HTML 생성
    cards_html = ""
    for item in selected:
        cat = item.get("카테고리", "")
        emoji = CATEGORY_EMOJI.get(cat, "📌")
        title = item.get("제목", "")
        summary = item.get("한줄요약", "")
        facts = item.get("핵심사실", [])
        keywords = item.get("키워드후보", [])
        grade = item.get("블로그적합도", {}).get("등급", "중")
        grade_score = item.get("블로그적합도", {}).get("점수", "")
        grade_detail = item.get("블로그적합도", {}).get("항목별점수", {})
        grade_reason = item.get("블로그적합도", {}).get("이유", "")
        source = item.get("출처", "")
        pub_date = item.get("기사날짜", "")
        link = item.get("링크", "#")
        deadline = item.get("시행_마감일", None)
        confirmed = item.get("확정여부", "")
        caution = item.get("주의", [])
        sensitive = item.get("민감도", "보통")
        grade_color = GRADE_COLOR.get(grade, "#f39c12")

        # D-day 계산
        dday_html = ""
        if deadline and deadline != "null":
            try:
                dl = datetime.strptime(deadline, "%Y-%m-%d")
                today_dt = datetime.strptime(today, "%Y-%m-%d")
                diff = (dl - today_dt).days
                if diff == 0:
                    dday_html = f'<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;">D-DAY</span>'
                elif diff > 0:
                    dday_html = f'<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;">D-{diff}</span>'
                else:
                    dday_html = f'<span style="background:#95a5a6;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">마감됨</span>'
            except:
                pass

        # 핵심사실 목록
        facts_html = ""
        for f in facts[:3]:
            if f:
                facts_html += f'<li style="margin:3px 0;color:#2c3e50;">{f}</li>'

        # 키워드 태그
        kw_html = ""
        for kw in keywords[:3]:
            if kw:
                kw_html += f'<span style="background:#eaf4fb;color:#2980b9;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;display:inline-block;">{kw}</span>'

        # 주의사항
        caution_html = ""
        if caution:
            caution_items = "".join([f'<li style="color:#e74c3c;font-size:13px;">{c}</li>' for c in caution if c])
            if caution_items:
                caution_html = f'<ul style="margin:8px 0;padding-left:18px;">{caution_items}</ul>'

        # 민감도 표시
        sensitive_badge = ""
        if sensitive == "주의":
            sensitive_badge = '<span style="background:#fdf2f8;color:#8e44ad;border:1px solid #d2b4de;padding:1px 6px;border-radius:4px;font-size:11px;margin-left:6px;">⚠️ 주의</span>'

        cards_html += f"""
<div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:20px;margin-bottom:16px;border-left:4px solid {grade_color};">
  <div style="display:flex;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px;">
    <span style="background:#eaf4fb;color:#2980b9;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:bold;">{emoji} {cat}</span>
    <span style="background:{grade_color};color:#fff;padding:3px 8px;border-radius:12px;font-size:12px;">적합도 {grade}{f" ({grade_score}점)" if grade_score else ""}</span>
    {f'<span style="background:#f8f9fa;color:#555;padding:3px 8px;border-radius:12px;font-size:12px;">{confirmed}</span>' if confirmed else ''}
    {dday_html}
    {sensitive_badge}
  </div>

  <h3 style="margin:0 0 8px 0;color:#2c3e50;font-size:17px;line-height:1.4;">
    <a href="{link}" style="color:#2c3e50;text-decoration:none;" target="_blank">{title}</a>
  </h3>

  <p style="margin:0 0 12px 0;color:#555;font-size:14px;line-height:1.6;">{summary}</p>

  {f'<ul style="margin:0 0 12px 0;padding-left:18px;background:#f8f9fa;border-radius:6px;padding:10px 10px 10px 28px;">{facts_html}</ul>' if facts_html else ''}

  <div style="margin-bottom:10px;">{kw_html}</div>

  {f'<div style="background:#fff8e1;border-left:3px solid #f39c12;padding:8px 12px;border-radius:4px;margin-bottom:10px;">{caution_html}</div>' if caution_html else ''}

  <div style="font-size:12px;color:#999;border-top:1px solid #f0f0f0;padding-top:8px;margin-top:8px;">
    📰 {source} &nbsp;|&nbsp; 🕐 {pub_date} &nbsp;|&nbsp;
    <a href="{link}" style="color:#2980b9;" target="_blank">기사 보기 →</a>
  </div>
</div>
"""

    # 해당없음 목록
    skipped_html = ""
    if skipped:
        skip_list = "".join([f'<span style="color:#999;font-size:13px;">• {i.get("카테고리","")} &nbsp;</span>' for i in skipped])
        skipped_html = f'<p style="color:#999;font-size:13px;margin-top:8px;">❌ 해당없음: {skip_list}</p>'

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f6fa;font-family:'Apple SD Gothic Neo','맑은 고딕',sans-serif;">

<div style="max-width:680px;margin:0 auto;padding:20px;">

  <!-- 헤더 -->
  <div style="background:linear-gradient(135deg,#2980b9,#1a5276);border-radius:12px;padding:28px;margin-bottom:20px;text-align:center;">
    <h1 style="margin:0;color:#fff;font-size:26px;letter-spacing:-0.5px;">📰 한발뉴스24</h1>
    <p style="margin:8px 0 0 0;color:#aed6f1;font-size:14px;">{today} · 오늘의 이슈 뉴스 {len(selected)}개</p>
    <p style="margin:4px 0 0 0;color:#7fb3d3;font-size:12px;">수집 기간: {window_start} ~ {window_end}</p>
  </div>

  <!-- 안내 문구 -->
  <div style="background:#fff8e1;border:1px solid #f9ca24;border-radius:8px;padding:12px 16px;margin-bottom:20px;font-size:13px;color:#856404;">
    ⚠️ AI가 요약한 소재 후보예요. 글 작성 전 반드시 원본 기사에서 사실을 확인해주세요.<br>
    예약 발행 글·임시글은 중복 확인이 되지 않아요.
  </div>

  <!-- 뉴스 카드 -->
  {cards_html}

  <!-- 해당없음 -->
  {skipped_html}

  <!-- 푸터 -->
  <div style="text-align:center;padding:20px;color:#bbb;font-size:12px;border-top:1px solid #e0e0e0;margin-top:10px;">
    한발뉴스24 · 매일 새벽 5시 자동 발송<br>
    이 메일은 자동으로 생성된 소재 후보 목록입니다.
  </div>

</div>
</body>
</html>"""

    return html


def send_email(result):
    """이메일 발송"""

    today = result.get("생성일", datetime.now(KST).strftime("%Y-%m-%d"))
    selected_count = len([i for i in result.get("항목", []) if i.get("상태") == "선정"])

    subject = f"[한발뉴스24] {today} 오늘의 이슈 뉴스 {selected_count}개"
    html_body = build_html(result)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        print(f"[한발뉴스24] 이메일 발송 중... → {EMAIL_RECIPIENT}")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())
        print(f"  ✅ 발송 완료! 제목: {subject}")
        return True
    except Exception as e:
        print(f"  ❌ 발송 실패: {e}")
        return False


# ================================================
# 단독 테스트 실행
# ================================================
if __name__ == "__main__":
    import json

    # 오늘 저장된 JSON 결과 파일 읽기
    today = datetime.now(KST).strftime("%Y%m%d")
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"hanbal_result_{today}.json")

    if not os.path.exists(json_path):
        print(f"결과 파일 없음: {json_path}")
        print("먼저 py hanbal_ai.py 를 실행해주세요.")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    print(f"결과 파일 로드: {json_path}")
    send_email(result)
