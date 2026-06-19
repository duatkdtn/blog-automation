# ================================================
# 일일 키워드 추천 이메일 발송 스크립트 v2.0
# 매일 오전 5시 자동 실행 (GitHub Actions)
# - 키워드 10개 추천
# - 베스트 6개 선정 + 발행 시간 표시
# - today_keywords.json 저장 (자동발행 스크립트가 읽어감)
# ================================================

import smtplib
import requests
import json
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import (
        CLAUDE_API_KEY, CLAUDE_MODEL,
        NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
        GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT
    )
except ImportError:
    CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
    CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")
    GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
    EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "duatkdtn@gmail.com")

# 자동 발행 시간 (0시부터 4시간 간격, 6개)
PUBLISH_TIMES = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]


def get_naver_news():
    """네이버 뉴스에서 오늘 이슈 수집"""
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    news_titles = []
    queries = ["오늘", "최신", "화제"]
    for query in queries:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=5&sort=date"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                items = response.json().get("items", [])
                for item in items:
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                    news_titles.append(title)
        except:
            pass
    return news_titles[:15]


def generate_keywords_with_claude(news_titles):
    """Claude로 키워드 10개 생성 + 베스트 6 선정"""

    today = datetime.now().strftime("%Y년 %m월 %d일")
    news_context = "\n".join(news_titles) if news_titles else "오늘 주요 이슈 없음"

    prompt = f"""당신은 한국 블로그 SEO 전문가입니다.

오늘 날짜: {today}
오늘의 뉴스/이슈:
{news_context}

[1단계] 블로그 키워드 10개를 추천해주세요.
조건:
- 타겟: 30~80세대 (건강, 재테크, 생활정보, 음식, 여행, IT 등)
- 숏테일 3개: 24시간 내 트렌드, 검색량 단기 폭발형
- 롱테일 4개: 정보형/교육형, 장기적으로 검색되는 키워드
- 행동형 2개: ~하는 방법, ~추천 등 구매/행동 유도
- 정보형 1개: ~이란, ~뜻, ~차이 등 지식 검색

[2단계] 10개 중 베스트 6개를 선정해주세요.
베스트 6 선정 기준:
- 검색량 잠재력 높음
- 경쟁도 낮음 (틈새 키워드 우선)
- 광고 단가 높음 (건강, 재테크, 보험 등)
- 카테고리 다양성 (숏테일2 + 롱테일2 + 행동형1 + 정보형1)

아래 형식으로 정확히 출력해주세요:

===전체키워드===
---키워드1---
키워드: [키워드]
유형: [숏테일/롱테일/행동형/정보형]
추천제목: [제목 30자 이내]
이유: [선정 이유 한 줄]
---키워드2---
---키워드3---
---키워드4---
---키워드5---
---키워드6---
---키워드7---
---키워드8---
---키워드9---
---키워드10---

===베스트6===
베스트1: [키워드번호]
베스트2: [키워드번호]
베스트3: [키워드번호]
베스트4: [키워드번호]
베스트5: [키워드번호]
베스트6: [키워드번호]
"""

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def parse_keywords_and_best6(raw_text):
    """전체 10개 파싱 + 베스트 6 선정"""
    keywords = []

    # 전체 키워드 파싱
    if "===전체키워드===" in raw_text:
        kw_section = raw_text.split("===전체키워드===")[1]
        if "===베스트6===" in kw_section:
            kw_section = kw_section.split("===베스트6===")[0]
    else:
        kw_section = raw_text

    blocks = kw_section.split("---키워드")
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        kw_data = {}
        for line in lines:
            line = line.strip()
            if line.startswith("키워드:"):
                kw_data["keyword"] = line.replace("키워드:", "").strip()
            elif line.startswith("유형:"):
                kw_data["type"] = line.replace("유형:", "").strip()
            elif line.startswith("추천제목:"):
                kw_data["title"] = line.replace("추천제목:", "").strip()
            elif line.startswith("이유:"):
                kw_data["reason"] = line.replace("이유:", "").strip()
        if kw_data.get("keyword"):
            keywords.append(kw_data)

    keywords = keywords[:10]

    # 베스트 6 인덱스 파싱
    best6_indices = []
    if "===베스트6===" in raw_text:
        best_section = raw_text.split("===베스트6===")[1]
        for line in best_section.strip().split("\n"):
            line = line.strip()
            if line.startswith("베스트"):
                try:
                    num = int(line.split(":")[1].strip()) - 1  # 0-indexed
                    if 0 <= num < len(keywords):
                        best6_indices.append(num)
                except:
                    pass

    # 베스트 6 못 찾으면 앞에서 6개
    if len(best6_indices) < 6:
        best6_indices = list(range(min(6, len(keywords))))

    best6 = [keywords[i] for i in best6_indices[:6]]

    return keywords, best6


def save_today_keywords(best6):
    """자동발행 스크립트가 읽어갈 JSON 저장"""
    today = datetime.now().strftime("%Y-%m-%d")
    data = {
        "date": today,
        "schedule": []
    }
    for i, kw in enumerate(best6):
        data["schedule"].append({
            "time": PUBLISH_TIMES[i],
            "keyword": kw.get("keyword", ""),
            "title": kw.get("title", ""),
            "type": kw.get("type", ""),
            "published": False
        })

    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "today_keywords.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   → today_keywords.json 저장 완료")


def build_email_html(keywords, best6, today_str):
    """이메일 HTML 생성 - 전체 10개 + 베스트 6 발행 스케줄"""

    type_emoji = {"숏테일": "🔥", "롱테일": "📈", "행동형": "💡", "정보형": "📚"}
    type_color = {"숏테일": "#ff4757", "롱테일": "#2ed573", "행동형": "#ffa502", "정보형": "#1e90ff"}

    best6_keywords = [kw.get("keyword") for kw in best6]

    # 전체 키워드 목록
    all_rows = ""
    for i, kw in enumerate(keywords, 1):
        kw_type = kw.get("type", "")
        emoji = type_emoji.get(kw_type, "📌")
        color = type_color.get(kw_type, "#666")
        is_best = kw.get("keyword") in best6_keywords
        bg = "#fff9e6" if is_best else "white"
        star = " ⭐" if is_best else ""

        all_rows += f"""
        <tr style="border-bottom:1px solid #eee; background:{bg};">
            <td style="padding:10px 12px; font-weight:bold; color:#333; width:25px;">{i}</td>
            <td style="padding:10px 12px;">
                <span style="background:{color}; color:white; padding:2px 7px; border-radius:10px; font-size:11px;">{emoji} {kw_type}</span>{star}<br>
                <strong style="font-size:15px; color:#222;">{kw.get('keyword', '')}</strong><br>
                <span style="color:#555; font-size:13px;">📝 {kw.get('title', '')}</span><br>
                <span style="color:#999; font-size:11px;">💬 {kw.get('reason', '')}</span>
            </td>
        </tr>
        """

    # 베스트 6 발행 스케줄
    schedule_rows = ""
    for i, kw in enumerate(best6):
        kw_type = kw.get("type", "")
        color = type_color.get(kw_type, "#666")
        schedule_rows += f"""
        <tr style="border-bottom:1px solid #eee;">
            <td style="padding:10px 15px; font-size:18px; font-weight:bold; color:#764ba2; width:60px;">{PUBLISH_TIMES[i]}</td>
            <td style="padding:10px 12px;">
                <span style="background:{color}; color:white; padding:2px 7px; border-radius:10px; font-size:11px;">{kw_type}</span><br>
                <strong style="font-size:15px; color:#222;">{kw.get('keyword', '')}</strong><br>
                <span style="color:#555; font-size:13px;">📝 {kw.get('title', '')}</span>
            </td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:'맑은 고딕',sans-serif; background:#f5f5f5; margin:0; padding:20px;">
<div style="max-width:620px; margin:0 auto;">

    <!-- 헤더 -->
    <div style="background:linear-gradient(135deg,#667eea,#764ba2); padding:30px; text-align:center; border-radius:12px 12px 0 0;">
        <h1 style="color:white; margin:0; font-size:22px;">📊 오늘의 블로그 키워드 추천</h1>
        <p style="color:rgba(255,255,255,0.85); margin:8px 0 0; font-size:14px;">{today_str}</p>
    </div>

    <!-- 자동 발행 스케줄 -->
    <div style="background:white; padding:20px; margin-top:2px;">
        <h2 style="color:#764ba2; font-size:17px; margin:0 0 15px;">🚀 오늘 자동 발행 예정 (베스트 6)</h2>
        <table style="width:100%; border-collapse:collapse;">
            {schedule_rows}
        </table>
    </div>

    <!-- 전체 키워드 10개 -->
    <div style="background:white; padding:20px; margin-top:8px;">
        <h2 style="color:#333; font-size:17px; margin:0 0 15px;">📋 전체 추천 키워드 10개 <span style="font-size:12px; color:#999;">(⭐ = 자동발행 선택)</span></h2>
        <table style="width:100%; border-collapse:collapse;">
            {all_rows}
        </table>
    </div>

    <!-- 푸터 -->
    <div style="background:#f8f8f8; padding:15px; text-align:center; border-radius:0 0 12px 12px; border-top:1px solid #eee;">
        <p style="color:#aaa; font-size:11px; margin:0;">블로그 자동화 시스템 | 매일 오전 5시 자동 발송</p>
    </div>

</div>
</body>
</html>
    """
    return html


def send_email(subject, html_content):
    """Gmail SMTP로 이메일 발송"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())
    print(f"✅ 이메일 발송 완료! → {EMAIL_RECIPIENT}")


def main():
    today_str = datetime.now().strftime("%Y년 %m월 %d일 (%A)")
    today_short = datetime.now().strftime("%m/%d")

    print(f"\n{'='*50}")
    print(f"📊 일일 키워드 추천 시작 - {today_str}")
    print(f"{'='*50}\n")

    # 1. 네이버 뉴스 수집
    print("📰 오늘의 뉴스 수집 중...")
    news_titles = get_naver_news()
    print(f"   → {len(news_titles)}개 뉴스 수집 완료")

    # 2. Claude로 키워드 10개 + 베스트 6 생성
    print("\n🤖 Claude가 키워드 분석 중...")
    raw_text = generate_keywords_with_claude(news_titles)

    # 3. 파싱
    keywords, best6 = parse_keywords_and_best6(raw_text)
    print(f"   → 전체 {len(keywords)}개 키워드 생성")
    print(f"   → 베스트 6개 선정: {[kw['keyword'] for kw in best6]}")

    # 4. JSON 저장 (자동발행 스크립트용)
    print("\n💾 오늘의 발행 스케줄 저장 중...")
    save_today_keywords(best6)

    # 5. 이메일 발송
    html = build_email_html(keywords, best6, today_str)
    subject = f"📊 [{today_short}] 키워드 추천 10개 + 오늘 자동발행 6개"
    print(f"\n📧 이메일 발송 중... → {EMAIL_RECIPIENT}")
    send_email(subject, html)

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
