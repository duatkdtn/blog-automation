# ================================================
# 일일 키워드 추천 이메일 발송 스크립트 v3.0
# 매일 오전 5시 자동 실행 (GitHub Actions)
# - 다중 소스 트렌드 수집 (네이버뉴스/DataLab/구글트렌드/다음/연관검색어)
# - 저경쟁 연관검색어 공략 키워드 선정
# - 네이버 블로그 상위 1~3위 제목 참고해서 제목 생성
# - 메인키워드 + 연관검색어 + 클릭유도형 제목 (30자 이내, 숫자 포함)
# - today_keywords.json 저장 (자동발행 스크립트가 읽어감)
# ================================================

import smtplib
import requests
import json
import os
import sys
import re
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
import anthropic

# 한국시간 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

def now_kst():
    """현재 한국 시간 반환"""
    return datetime.now(KST)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# GitHub Actions 환경에서 config.py 임시 생성
def setup_env():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
    if not os.path.exists(config_path):
        env_map = {
            "CLAUDE_API_KEY": os.environ.get("CLAUDE_API_KEY", ""),
            "CLAUDE_MODEL": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            "NAVER_CLIENT_ID": os.environ.get("NAVER_CLIENT_ID", ""),
            "NAVER_CLIENT_SECRET": os.environ.get("NAVER_CLIENT_SECRET", ""),
            "GMAIL_ADDRESS": os.environ.get("GMAIL_ADDRESS", ""),
            "GMAIL_APP_PASSWORD": os.environ.get("GMAIL_APP_PASSWORD", ""),
            "EMAIL_RECIPIENT": os.environ.get("EMAIL_RECIPIENT", "duatkdtn@gmail.com"),
        }
        with open(config_path, "w", encoding="utf-8") as f:
            for key, val in env_map.items():
                f.write(f'{key} = "{val}"\n')

setup_env()

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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 트렌드 수집 함수들
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_naver_news():
    """네이버 뉴스에서 오늘 이슈 수집"""
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    news_titles = []
    queries = ["오늘", "최신", "화제", "이슈"]
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
    print(f"   → 네이버 뉴스 {len(news_titles)}개 수집")
    return news_titles[:20]


def get_naver_datalab_trends():
    """네이버 DataLab에서 인기 검색어 트렌드 수집"""
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    # 주요 카테고리별 트렌드 조회
    categories = ["건강", "재테크", "생활정보", "음식", "여행"]
    trends = []
    today = now_kst().strftime("%Y-%m-%d")

    for cat in categories:
        try:
            body = {
                "startDate": today,
                "endDate": today,
                "timeUnit": "date",
                "keywordGroups": [{"groupName": cat, "keywords": [cat]}]
            }
            response = requests.post(url, headers=headers, json=body, timeout=5)
            if response.status_code == 200:
                trends.append(f"{cat} 카테고리 트렌드 활성")
        except:
            pass

    print(f"   → 네이버 DataLab {len(trends)}개 카테고리 트렌드 수집")
    return trends


def get_naver_related_keywords(keyword):
    """네이버 연관검색어 수집 (자동완성 API)"""
    try:
        url = f"https://ac.search.naver.com/nx/ac?q={requests.utils.quote(keyword)}&st=100&frm=nx&r_format=json&r_enc=UTF-8&q_enc=UTF-8&t_koreng=1&ans=2&run=2&rev=4"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [[]])[0] if data.get("items") else []
            keywords = [item[0] for item in items[:10] if item]
            return keywords
    except:
        pass
    return []


def get_google_trends():
    """구글 트렌드 한국 인기 검색어 수집"""
    trends = []
    try:
        # 구글 트렌드 RSS 피드 (API 키 불필요)
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            # XML에서 제목 추출
            titles = re.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', response.text)
            trends = [t for t in titles if t != "Google Trends"][:15]
        print(f"   → 구글 트렌드 {len(trends)}개 수집")
    except Exception as e:
        print(f"   ⚠️ 구글 트렌드 수집 실패: {e}")
    return trends


def get_daum_realtime_issues():
    """다음 실시간 이슈 수집"""
    issues = []
    try:
        url = "https://apis.daum.net/contents/issue/MAIN?code=MAIN&limit=10"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("data", {}).get("list", [])[:10]:
                keyword = item.get("keyword", "")
                if keyword:
                    issues.append(keyword)
    except:
        pass

    # 백업: 다음 뉴스 RSS
    if not issues:
        try:
            url = "https://news.daum.net/rss/main"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                titles = re.findall(r'<title>(.+?)</title>', response.text)
                issues = [t for t in titles if len(t) > 2 and "다음" not in t][:10]
        except:
            pass

    print(f"   → 다음 이슈 {len(issues)}개 수집")
    return issues


def get_naver_blog_top_titles(keyword):
    """네이버 블로그 상위 1~3위 제목 수집"""
    try:
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        url = f"https://openapi.naver.com/v1/search/blog.json?query={requests.utils.quote(keyword)}&display=3&sort=sim"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            items = response.json().get("items", [])
            titles = []
            for item in items:
                title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                titles.append(title)
            return titles
    except:
        pass
    return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Claude로 키워드 + 제목 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_keywords_with_claude(news_titles, google_trends, daum_issues, datalab_trends):
    """Claude로 키워드 10개 생성 + 베스트 6 선정"""

    today = now_kst().strftime("%Y년 %m월 %d일")

    news_context = "\n".join(news_titles) if news_titles else "없음"
    google_context = "\n".join(google_trends) if google_trends else "없음"
    daum_context = "\n".join(daum_issues) if daum_issues else "없음"

    prompt = f"""당신은 한국 블로그 SEO 전문가입니다.

오늘 날짜: {today}

=== 수집된 트렌드 데이터 ===
[네이버 뉴스 최신 이슈]
{news_context}

[구글 트렌드 인기 검색어]
{google_context}

[다음 실시간 이슈]
{daum_context}

=== 키워드 선정 기준 ===
타겟: 30~80세대 (건강, 재테크, 생활정보, 음식, 여행, IT 등)
유형별 구성:
- 숏테일 3개: 24시간 내 트렌드, 검색량 단기 폭발형
- 롱테일 4개: 정보형/교육형, 장기적으로 검색되는 키워드
- 행동형 2개: ~하는 방법, ~추천 등 구매/행동 유도
- 정보형 1개: ~이란, ~뜻, ~차이 등 지식 검색

핵심 전략:
- 반드시 하위 키워드로 세분화할 것 (상위 주제 키워드는 절대 금지)
  * 금지 예시: "보험", "건강", "재테크", "대출" (너무 상위 주제)
  * 권장 예시: "치아보험 후기 2026", "30대 건강검진 항목", "신용대출 한도 올리는 법", "간병인 자격증 비용"
- 고단가 카테고리 우선 (보험, 대출, 법률, 영어공부, 자격증, 건강검진, 의료, 금융)
- 검색량은 있지만 상위 블로그가 적은 틈새 키워드 공략
- 연도/나이/상황을 붙여 세분화: "2026년", "30대", "직장인", "초보자", "비용", "후기", "방법"

[1단계] 블로그 키워드 10개 추천
[2단계] 베스트 6개 선정 (숏테일2 + 롱테일2 + 행동형1 + 정보형1)

아래 형식으로 정확히 출력해주세요:

===전체키워드===
---키워드1---
키워드: [메인 키워드]
유형: [숏테일/롱테일/행동형/정보형]
연관검색어: [이 키워드의 저경쟁 연관검색어 2~3개, 쉼표로 구분]
경쟁강도: [낮음/중간/높음]
광고단가: [낮음/중간/높음]
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
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def generate_title_with_claude(keyword, kw_type, related_keywords, top_blog_titles):
    """네이버 상위 블로그 제목 참고해서 최적 제목 생성"""

    blog_titles_text = "\n".join([f"- {t}" for t in top_blog_titles]) if top_blog_titles else "없음"
    related_text = ", ".join(related_keywords) if related_keywords else "없음"

    prompt = f"""당신은 한국 블로그 SEO 제목 전문가입니다.

키워드: {keyword}
키워드 유형: {kw_type}
저경쟁 연관검색어: {related_text}

네이버 블로그 현재 상위 노출 제목 (참고용):
{blog_titles_text}

위 정보를 바탕으로 클릭률 높은 블로그 제목을 1개 만들어주세요.

제목 작성 규칙:
1. 형식: 메인키워드 + 저경쟁 연관검색어 + 클릭유도형 표현
2. 30자 이내 (반드시 지킬 것)
3. 숫자 포함 필수 (예: 3가지, 7단계, 2024년 등)
4. 클릭유도 표현 사용 (총정리, 완벽정리, 핵심만, 쉽게 설명, 꼭 알아야 할)
5. 상위 블로그와 차별화된 제목
6. 검색자의 의도를 정확히 반영

제목만 출력하세요. 설명 없이 제목 텍스트만."""

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )
    title = response.content[0].text.strip()
    # 따옴표 제거
    title = title.strip('"').strip("'").strip()
    return title


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 파싱 및 저장
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_keywords_and_best6(raw_text):
    """전체 10개 파싱 + 베스트 6 선정"""
    keywords = []

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
            elif line.startswith("연관검색어:"):
                related = line.replace("연관검색어:", "").strip()
                kw_data["related"] = [r.strip() for r in related.split(",") if r.strip()]
            elif line.startswith("경쟁강도:"):
                kw_data["competition"] = line.replace("경쟁강도:", "").strip()
            elif line.startswith("광고단가:"):
                kw_data["ad_price"] = line.replace("광고단가:", "").strip()
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
                    num = int(line.split(":")[1].strip()) - 1
                    if 0 <= num < len(keywords):
                        best6_indices.append(num)
                except:
                    pass

    if len(best6_indices) < 6:
        best6_indices = list(range(min(6, len(keywords))))

    best6 = [keywords[i] for i in best6_indices[:6]]
    return keywords, best6


def enrich_keywords_with_titles(keywords, best6):
    """각 키워드에 네이버 연관검색어 + 상위 블로그 제목 참고해서 최적 제목 생성"""
    best6_kw_names = [kw.get("keyword") for kw in best6]

    for kw in keywords:
        keyword = kw.get("keyword", "")
        kw_type = kw.get("type", "")

        print(f"   📝 '{keyword}' 제목 생성 중...")

        # 네이버 연관검색어 실시간 수집
        naver_related = get_naver_related_keywords(keyword)
        if naver_related:
            # Claude가 이미 제안한 연관검색어 + 네이버 실제 연관검색어 합치기
            claude_related = kw.get("related", [])
            all_related = list(set(claude_related + naver_related))[:5]
            kw["related"] = all_related

        # 네이버 블로그 상위 제목 수집 (베스트 6만, API 호출 최소화)
        top_titles = []
        if keyword in best6_kw_names:
            top_titles = get_naver_blog_top_titles(keyword)
            time.sleep(0.3)  # API 과부하 방지

        # Claude로 최적 제목 생성
        title = generate_title_with_claude(
            keyword, kw_type, kw.get("related", []), top_titles
        )
        kw["title"] = title
        kw["top_blog_titles"] = top_titles
        time.sleep(0.3)

    return keywords, best6


def save_today_keywords(keywords, best6):
    """자동발행 스크립트가 읽어갈 JSON 저장"""
    today = now_kst().strftime("%Y-%m-%d")
    data = {
        "date": today,
        "schedule": []
    }
    # best6의 제목 업데이트 (enrich 후 title이 갱신됐으므로)
    best6_keywords_map = {kw.get("keyword"): kw for kw in keywords}

    for i, kw in enumerate(best6):
        keyword = kw.get("keyword", "")
        # keywords 리스트에서 최신 title 가져오기
        updated_kw = best6_keywords_map.get(keyword, kw)
        data["schedule"].append({
            "time": PUBLISH_TIMES[i],
            "keyword": keyword,
            "title": updated_kw.get("title", ""),
            "type": kw.get("type", ""),
            "published": False
        })

    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "today_keywords.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   → today_keywords.json 저장 완료")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 이메일 HTML 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_email_html(keywords, best6, today_str):
    """이메일 HTML 생성 - 전체 10개 (베스트 6에 발행시간 표시)"""

    type_emoji = {"숏테일": "🔥", "롱테일": "📈", "행동형": "💡", "정보형": "📚"}
    type_color = {"숏테일": "#ff4757", "롱테일": "##2ed573", "행동형": "#ffa502", "정보형": "#1e90ff"}
    competition_color = {"낮음": "#2ed573", "중간": "#ffa502", "높음": "#ff4757"}

    # 베스트 6 키워드 → 발행시간 매핑
    best6_time = {}
    for i, kw in enumerate(best6):
        best6_time[kw.get("keyword")] = PUBLISH_TIMES[i]

    all_rows = ""
    for i, kw in enumerate(keywords, 1):
        kw_type = kw.get("type", "")
        emoji = type_emoji.get(kw_type, "📌")
        color = type_color.get(kw_type, "#666")
        kw_name = kw.get("keyword", "")
        is_best = kw_name in best6_time
        bg = "#fff9e6" if is_best else "white"
        competition = kw.get("competition", "")
        ad_price = kw.get("ad_price", "")
        comp_color = competition_color.get(competition, "#999")
        related = kw.get("related", [])
        related_text = " · ".join(related[:3]) if related else ""

        # 발행 시간 뱃지
        time_badge = ""
        if is_best:
            time_badge = f'<span style="background:#764ba2; color:white; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold; margin-left:6px;">⏰ {best6_time[kw_name]} 발행</span>'

        # 경쟁강도 뱃지
        comp_badge = f'<span style="background:{comp_color}; color:white; padding:1px 6px; border-radius:8px; font-size:10px;">경쟁 {competition}</span>' if competition else ""
        ad_badge = f'<span style="background:#ff6b81; color:white; padding:1px 6px; border-radius:8px; font-size:10px; margin-left:3px;">단가 {ad_price}</span>' if ad_price else ""

        all_rows += f"""
        <tr style="border-bottom:1px solid #eee; background:{bg};">
            <td style="padding:10px 12px; font-weight:bold; color:#333; width:25px; vertical-align:top;">{i}</td>
            <td style="padding:10px 12px;">
                <span style="background:{color}; color:white; padding:2px 7px; border-radius:10px; font-size:11px;">{emoji} {kw_type}</span>
                {comp_badge}{ad_badge}{time_badge}<br>
                <strong style="font-size:15px; color:#222;">{kw_name}</strong><br>
                <span style="color:#555; font-size:13px;">📝 {kw.get('title', '')}</span><br>
                {f'<span style="color:#888; font-size:11px;">🔗 연관: {related_text}</span><br>' if related_text else ''}
                <span style="color:#999; font-size:11px;">💬 {kw.get('reason', '')}</span>
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
        <p style="color:rgba(255,255,255,0.7); margin:4px 0 0; font-size:12px;">네이버뉴스 · 구글트렌드 · 다음이슈 · DataLab 분석</p>
    </div>

    <!-- 전체 키워드 10개 -->
    <div style="background:white; padding:20px; margin-top:2px;">
        <h2 style="color:#333; font-size:17px; margin:0 0 15px;">
            📋 전체 추천 키워드 10개
            <span style="font-size:12px; color:#764ba2;">⏰ = 자동 발행 시간</span>
        </h2>
        <table style="width:100%; border-collapse:collapse;">
            {all_rows}
        </table>
    </div>

    <!-- 범례 -->
    <div style="background:white; padding:15px 20px; margin-top:4px; border-top:1px solid #eee;">
        <p style="color:#999; font-size:11px; margin:0;">
            🟢 경쟁 낮음 = 상위노출 유리 &nbsp;|&nbsp;
            🔴 단가 높음 = 광고수익 우수 &nbsp;|&nbsp;
            ⏰ = 오늘 자동 발행 예정
        </p>
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 이메일 발송
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. 메인 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    today_str = now_kst().strftime("%Y년 %m월 %d일 (%A)")
    today_short = now_kst().strftime("%m/%d")

    print(f"\n{'='*50}")
    print(f"📊 일일 키워드 추천 시작 - {today_str}")
    print(f"{'='*50}\n")

    # 1. 다중 소스 트렌드 수집
    print("📰 트렌드 데이터 수집 중...")
    news_titles = get_naver_news()
    google_trends = get_google_trends()
    daum_issues = get_daum_realtime_issues()
    datalab_trends = get_naver_datalab_trends()

    # 2. Claude로 키워드 10개 + 베스트 6 생성
    print("\n🤖 Claude가 키워드 분석 중...")
    raw_text = generate_keywords_with_claude(news_titles, google_trends, daum_issues, datalab_trends)

    # 3. 파싱
    keywords, best6 = parse_keywords_and_best6(raw_text)
    print(f"   → 전체 {len(keywords)}개 키워드 생성")
    print(f"   → 베스트 6개 선정: {[kw['keyword'] for kw in best6]}")

    # 4. 연관검색어 + 상위 블로그 제목 참고해서 최적 제목 생성
    print("\n🔍 연관검색어 수집 + 최적 제목 생성 중...")
    keywords, best6 = enrich_keywords_with_titles(keywords, best6)

    # 5. JSON 저장
    print("\n💾 오늘의 발행 스케줄 저장 중...")
    save_today_keywords(keywords, best6)

    # 6. 이메일 발송
    html = build_email_html(keywords, best6, today_str)
    subject = f"📊 [{today_short}] 키워드 추천 10개 + 오늘 자동발행 6개"
    print(f"\n📧 이메일 발송 중... → {EMAIL_RECIPIENT}")
    send_email(subject, html)

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
