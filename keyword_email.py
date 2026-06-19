# ================================================
# 일일 키워드 추천 이메일 발송 스크립트
# 매일 오전 5시 자동 실행 (GitHub Actions)
# ================================================

import smtplib
import requests
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import anthropic

# config.py에서 설정 불러오기
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import (
        CLAUDE_API_KEY, CLAUDE_MODEL,
        NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
        GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT
    )
except ImportError:
    # GitHub Actions 환경변수에서 불러오기
    CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
    CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")
    GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
    EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "duatkdtn@gmail.com")


def get_naver_trending_keywords():
    """네이버 실시간 급상승 검색어 수집"""
    trending = []

    # 네이버 뉴스에서 오늘 핫한 키워드 수집
    categories = ["100", "101", "102", "103", "104", "105"]  # 정치, 경제, 사회, 생활, IT, 연예
    category_names = ["정치", "경제", "사회", "생활/문화", "IT/과학", "연예"]

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }

    news_titles = []
    for cat_id, cat_name in zip(categories[:3], category_names[:3]):  # 상위 3개 카테고리
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query=오늘&display=5&sort=date"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                items = response.json().get("items", [])
                for item in items:
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                    news_titles.append(title)
        except:
            pass

    return news_titles[:15]  # 최대 15개


def get_naver_related_keywords(keyword):
    """네이버 연관 검색어 수집"""
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }

    related = []
    try:
        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=3&sort=date"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            items = response.json().get("items", [])
            for item in items:
                title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                related.append(title[:30])
    except:
        pass

    return related


def generate_keywords_with_claude(news_titles):
    """Claude로 키워드 10개 + 추천 제목 생성"""

    today = datetime.now().strftime("%Y년 %m월 %d일")
    news_context = "\n".join(news_titles) if news_titles else "오늘 주요 이슈 없음"

    prompt = f"""당신은 한국 블로그 SEO 전문가입니다.

오늘 날짜: {today}
오늘의 뉴스/이슈:
{news_context}

위 정보를 참고해서 블로그 키워드 10개를 추천해주세요.

조건:
- 타겟: 30~80세대 (건강, 재테크, 생활정보, 음식, 여행, IT 등)
- 숏테일 3개: 24시간 내 이슈/트렌드 기반, 검색량 단기 폭발형
- 롱테일 4개: 정보형/교육형, 장기적으로 검색되는 키워드
- 행동형 2개: ~하는 방법, ~하려면, ~추천 등 구매/행동 유도
- 정보형 1개: ~이란, ~뜻, ~차이 등 지식 검색

각 키워드마다:
1. 키워드
2. 키워드 유형 (숏테일/롱테일/행동형/정보형)
3. 추천 블로그 제목 (30자 이내, 클릭 유도 문구 포함)
4. 선정 이유 (한 줄)

아래 형식으로 정확히 출력해주세요:

---키워드1---
키워드: [키워드]
유형: [유형]
추천제목: [제목]
이유: [이유]
---키워드2---
...
---키워드10---
"""

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def parse_keywords(raw_text):
    """Claude 응답을 파싱해서 구조화"""
    keywords = []
    blocks = raw_text.split("---키워드")

    for block in blocks[1:]:  # 첫 번째 빈 블록 제외
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

    return keywords[:10]


def build_email_html(keywords, today_str):
    """이메일 HTML 생성"""

    type_emoji = {
        "숏테일": "🔥",
        "롱테일": "📈",
        "행동형": "💡",
        "정보형": "📚"
    }

    type_color = {
        "숏테일": "#ff4757",
        "롱테일": "#2ed573",
        "행동형": "#ffa502",
        "정보형": "#1e90ff"
    }

    rows = ""
    for i, kw in enumerate(keywords, 1):
        kw_type = kw.get("type", "")
        emoji = type_emoji.get(kw_type, "📌")
        color = type_color.get(kw_type, "#666")

        rows += f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 12px; font-size: 16px; font-weight: bold; color: #333; width: 30px;">{i}</td>
            <td style="padding: 12px;">
                <span style="background:{color}; color:white; padding:2px 8px; border-radius:10px; font-size:12px;">{emoji} {kw_type}</span><br>
                <strong style="font-size:16px; color:#222;">{kw.get('keyword', '')}</strong><br>
                <span style="color:#555; font-size:14px;">📝 {kw.get('title', '')}</span><br>
                <span style="color:#888; font-size:12px;">💬 {kw.get('reason', '')}</span>
            </td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: 'Apple SD Gothic Neo', '맑은 고딕', sans-serif; background:#f5f5f5; margin:0; padding:20px;">
    <div style="max-width:600px; margin:0 auto; background:white; border-radius:12px; overflow:hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">

        <!-- 헤더 -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align:center;">
            <h1 style="color:white; margin:0; font-size:24px;">📊 오늘의 블로그 키워드 추천</h1>
            <p style="color:rgba(255,255,255,0.85); margin:8px 0 0 0; font-size:15px;">{today_str}</p>
        </div>

        <!-- 키워드 테이블 -->
        <div style="padding: 20px;">
            <table style="width:100%; border-collapse:collapse;">
                {rows}
            </table>
        </div>

        <!-- 푸터 -->
        <div style="background:#f8f8f8; padding:20px; text-align:center; border-top:1px solid #eee;">
            <p style="color:#aaa; font-size:12px; margin:0;">블로그 자동화 시스템 | 매일 오전 5시 자동 발송</p>
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

    part = MIMEText(html_content, "html", "utf-8")
    msg.attach(part)

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
    news_titles = get_naver_trending_keywords()
    print(f"   → {len(news_titles)}개 뉴스 수집 완료")

    # 2. Claude로 키워드 생성
    print("\n🤖 Claude가 키워드 분석 중...")
    raw_keywords = generate_keywords_with_claude(news_titles)

    # 3. 파싱
    keywords = parse_keywords(raw_keywords)
    print(f"   → {len(keywords)}개 키워드 생성 완료")

    # 4. 이메일 HTML 생성
    html = build_email_html(keywords, today_str)
    subject = f"📊 [{today_short}] 오늘의 블로그 키워드 추천 10개"

    # 5. 발송
    print(f"\n📧 이메일 발송 중... → {EMAIL_RECIPIENT}")
    send_email(subject, html)

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
