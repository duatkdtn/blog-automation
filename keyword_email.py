# ================================================
# 일일 키워드 추천 이메일 발송 스크립트 v4.0
# 매일 18시 자동 실행 (GitHub Actions)
# - 구글 자동완성 + 구글 트렌드 기반 키워드 수집
# - 블로그스팟용: 구글 상위 결과 참고 제목 생성
# - 네이버 백링크용: 네이버 블로그 상위 제목 참고 + 감성형 별도 생성
# - 발행 비율: 롱테일3 + 행동형2 + 정보형1
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
    return datetime.now(KST)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

# 자동 발행 시간 (0시부터 3시간 간격, 8개)
PUBLISH_TIMES = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 트렌드 수집 함수들
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_google_trends_rss():
    """구글 트렌드 한국 인기 검색어 수집 (RSS)"""
    trends = []
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            titles = re.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', response.text)
            trends = [t for t in titles if t != "Google Trends"][:20]
        print(f"   → 구글 트렌드 {len(trends)}개 수집")
    except Exception as e:
        print(f"   ⚠️ 구글 트렌드 수집 실패: {e}")
    return trends


def get_google_autocomplete(keyword):
    """구글 자동완성으로 연관 키워드 수집"""
    results = []
    try:
        url = f"https://suggestqueries.google.com/complete/search?q={requests.utils.quote(keyword)}&hl=ko&gl=KR&client=firefox"
        response = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1:
                results = data[1][:10]
    except Exception as e:
        pass
    return results


def get_naver_related_keywords(keyword):
    """네이버 연관검색어 수집 (보조용)"""
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


def get_naver_blog_top_titles(keyword):
    """네이버 블로그 상위 1~3위 제목 수집 (네이버 백링크용)"""
    try:
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        url = f"https://openapi.naver.com/v1/search/blog.json?query={requests.utils.quote(keyword)}&display=3&sort=sim"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            items = response.json().get("items", [])
            titles = [item.get("title", "").replace("<b>", "").replace("</b>", "") for item in items]
            return titles
    except:
        pass
    return []


def get_google_top_titles(keyword):
    """구글 검색 상위 결과 제목 수집 (블로그스팟용 - 구글 자동완성 기반)"""
    # 구글 자동완성으로 세부 키워드 파악 후 참고용으로 활용
    autocomplete = get_google_autocomplete(keyword)
    return autocomplete[:5]


def get_naver_news_for_context():
    """보조용: 네이버 뉴스로 오늘 이슈 파악"""
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    news_titles = []
    queries = ["오늘", "최신이슈", "화제"]
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
    print(f"   → 네이버 뉴스 {len(news_titles)}개 수집 (보조)")
    return news_titles[:15]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Claude로 키워드 + 제목 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_keywords_with_claude(google_trends, naver_news):
    """Claude로 키워드 10개 생성 + 베스트 6 선정 (구글 기반)"""

    today = now_kst().strftime("%Y년 %m월 %d일")
    google_context = "\n".join(google_trends) if google_trends else "없음"
    news_context = "\n".join(naver_news) if naver_news else "없음"

    prompt = f"""당신은 구글 SEO 전문가이자 한국 블로그 수익화 전문가입니다.

오늘 날짜: {today}

=== 수집된 트렌드 데이터 ===
[구글 트렌드 한국 인기 검색어 - 메인 소스]
{google_context}

[네이버 뉴스 오늘 이슈 - 보조 소스]
{news_context}

=== 키워드 선정 기준 ===
플랫폼: 블로그스팟 (구글 검색 노출 최적화)
타겟 독자: 30~60대 한국인

유형별 구성 (반드시 지킬 것):
- 롱테일 3개: 구글에서 "~비용", "~방법", "~후기", "~얼마" 형태로 검색되는 정보형 키워드
- 행동형 2개: "~하는 법", "~추천", "~비교" 등 해결책을 찾는 키워드
- 정보형 1개: "~뜻", "~이란", "~차이점" 등 개념 설명 키워드
※ 숏테일 키워드(단어 1~2개) 절대 금지 - 대형 사이트와 경쟁 불가

핵심 전략:
- 구글에서 한국어로 검색하는 사람이 찾는 키워드
- 반드시 하위 세분화 키워드 (상위 주제 절대 금지)
  * 금지: "보험", "건강", "재테크" (너무 광범위)
  * 권장: "실비보험 청구 거절 이유 2026", "40대 종합건강검진 비용 차이", "직장인 ISA계좌 단점"
- 카테고리 다양성 필수: 6개 중 1개만 고단가(보험/대출/법률/금융), 나머지 5개는 트렌드 기반으로 육아, 여행, 부동산, 건강, 취업, 자동차, 반려동물, IT, 생활정보 등 다양한 카테고리에서 골고루 선정
- 연도/나이/상황 붙여 세분화: "2026", "30대", "직장인", "초보자", "비용", "후기"
- 구글 자동완성에 실제로 뜨는 형태의 키워드

[1단계] 구글 기반 블로그 키워드 10개 추천 (카테고리 중복 최소화)
[2단계] 베스트 6개 선정 (롱테일3 + 행동형2 + 정보형1, 반드시 고단가 1개 + 다양한 카테고리 5개)

아래 형식으로 정확히 출력해주세요:

===전체키워드===
---키워드1---
키워드: [메인 키워드]
유형: [롱테일/행동형/정보형]
연관검색어: [구글 자동완성에 뜰 법한 세부 키워드 2~3개, 쉼표로 구분]
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
    import time as _time
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            if "529" in str(e) or "overloaded" in str(e).lower():
                wait = 30 * (attempt + 1)
                print(f"⚠️ Claude API 과부하 - {wait}초 후 재시도 ({attempt+1}/5)...")
                _time.sleep(wait)
            else:
                raise
    raise Exception("Claude API 5회 재시도 실패")


def generate_blogspot_title(keyword, kw_type, related_keywords, google_autocomplete):
    """블로그스팟용 제목 생성 (구글 검색 최적화)"""
    autocomplete_text = "\n".join([f"- {t}" for t in google_autocomplete]) if google_autocomplete else "없음"
    related_text = ", ".join(related_keywords) if related_keywords else "없음"

    prompt = f"""당신은 구글 SEO 블로그 제목 전문가입니다.

키워드: {keyword}
키워드 유형: {kw_type}
저경쟁 연관검색어: {related_text}

구글 자동완성 연관 검색어 (참고용):
{autocomplete_text}

블로그스팟(구글 검색 노출)용 제목을 1개 만들어주세요.

제목 작성 규칙:
1. 형식: 메인키워드 + 저경쟁 연관검색어 + 클릭유도형 표현 조합
2. 30자 이내
3. 숫자 선택적 포함 (자연스러울 때만)
4. 클릭유도 표현: 총정리, 완벽정리, 핵심만, 한눈에, 꼭 알아야 할
5. 구글에서 검색하는 사람의 의도를 정확히 반영
6. 정보형/명확한 설명체 문체

제목만 출력하세요. 설명 없이 제목 텍스트만."""

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    import time as _time
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip().strip('"').strip("'").strip()
        except Exception as e:
            if "529" in str(e) or "overloaded" in str(e).lower():
                wait = 30 * (attempt + 1)
                print(f"⚠️ Claude API 과부하 - {wait}초 후 재시도 ({attempt+1}/5)...")
                _time.sleep(wait)
            else:
                raise
    return keyword  # 실패 시 키워드 그대로 반환


def generate_naver_title(keyword, related_keywords, naver_top_titles):
    """네이버 백링크용 제목 생성 (네이버 블로그 상위 제목 참고 + 감성형)"""
    naver_titles_text = "\n".join([f"- {t}" for t in naver_top_titles]) if naver_top_titles else "없음"
    related_text = ", ".join(related_keywords) if related_keywords else "없음"

    prompt = f"""당신은 네이버 블로그 SEO 전문가입니다.

키워드: {keyword}
저경쟁 연관검색어: {related_text}

네이버 블로그 현재 상위 노출 제목 (참고용):
{naver_titles_text}

네이버 블로그용 제목을 1개 만들어주세요.

제목 작성 규칙:
1. 형식: 메인키워드 + 저경쟁 연관검색어 + 네이버 상위 제목 스타일 참고해서 조합
2. 30자 이내
3. 숫자 선택적 포함
4. 감성형/경험담 문체 ("직접 알아봤어요", "솔직후기", "경험담", "꿀팁")
5. 네이버 사용자 감성에 맞는 친근한 표현
6. 상위 제목과 차별화하되 클릭하고 싶은 제목

제목만 출력하세요. 설명 없이 제목 텍스트만."""

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    import time as _time
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip().strip('"').strip("'").strip()
        except Exception as e:
            if "529" in str(e) or "overloaded" in str(e).lower():
                wait = 30 * (attempt + 1)
                print(f"⚠️ Claude API 과부하 - {wait}초 후 재시도 ({attempt+1}/5)...")
                _time.sleep(wait)
            else:
                raise
    return keyword  # 실패 시 키워드 그대로 반환


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

    # 경쟁강도 필터: 높음 제외, 낮음 우선 정렬
    def competition_score(kw):
        comp = kw.get("competition", "중간")
        if "낮음" in comp: return 0
        if "중간" in comp: return 1
        return 2  # 높음

    best6_sorted = sorted(best6, key=competition_score)
    # 높음 경쟁강도 키워드 제외 (낮음+중간만 유지, 최소 3개 보장)
    filtered = [kw for kw in best6_sorted if competition_score(kw) < 2]
    if len(filtered) >= 3:
        best6 = filtered[:6]
    else:
        best6 = best6_sorted[:6]  # 필터 후 3개 미만이면 그냥 정렬만

    print(f"   📊 경쟁강도 필터 적용: {[kw.get('keyword','') + '(' + kw.get('competition','?') + ')' for kw in best6]}")

    # 이메일 표시 순서(keywords 리스트 순서)대로 발행시간 배정되도록 정렬
    keyword_order = {kw.get("keyword"): i for i, kw in enumerate(keywords)}
    best6 = sorted(best6, key=lambda kw: keyword_order.get(kw.get("keyword"), 999))
    return keywords, best6


def enrich_keywords_with_titles(keywords, best6):
    """각 키워드에 블로그스팟용 + 네이버용 제목 각각 생성"""
    best6_kw_names = [kw.get("keyword") for kw in best6]

    for kw in keywords:
        keyword = kw.get("keyword", "")
        kw_type = kw.get("type", "")
        is_best = keyword in best6_kw_names

        print(f"   📝 '{keyword}' 제목 생성 중...")

        # 구글 자동완성으로 연관 키워드 수집
        google_auto = get_google_autocomplete(keyword)
        time.sleep(0.2)

        # 네이버 연관검색어 (보조)
        naver_related = get_naver_related_keywords(keyword)
        all_related = list(set(kw.get("related", []) + naver_related))[:5]
        kw["related"] = all_related

        # 블로그스팟용 제목 (구글 최적화)
        blogspot_title = generate_blogspot_title(keyword, kw_type, all_related, google_auto)
        kw["title"] = blogspot_title  # 자동발행에 사용되는 제목

        # 네이버 백링크용 제목 (베스트 6만 생성, API 절약)
        if is_best:
            naver_top = get_naver_blog_top_titles(keyword)
            naver_title = generate_naver_title(keyword, all_related, naver_top)
            kw["naver_title"] = naver_title
            kw["naver_top_titles"] = naver_top
            time.sleep(0.3)

        time.sleep(0.3)

    return keywords, best6



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 정부지원금 키워드 생성 (중복 방지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_gov_keyword():
    """매일 새로운 정부지원금 키워드 1개 생성 (중복 방지)"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    used_path = os.path.join(base_dir, "used_gov_keywords.txt")

    # 기존 사용 목록 읽기
    used = []
    if os.path.exists(used_path):
        with open(used_path, "r", encoding="utf-8") as f:
            used = [line.strip() for line in f if line.strip()]

    used_list_str = "\n".join(used[-60:]) if used else "없음"  # 최근 60개만 전달

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        prompt = f"""오늘 날짜: {now_kst().strftime("%Y년 %m월 %d일")}

대한민국 정부지원금/복지혜택 중에서 블로그 글 키워드로 좋은 것 1개를 추천해줘.

조건:
- 구체적인 지원금 이름 (예: "청년월세지원금 신청 방법 2026", "소상공인 전기요금 지원 신청")
- 검색량 있고 실용적인 정보성 키워드
- 아래 이미 사용한 목록에 없는 것
- 키워드만 한 줄로 출력 (설명 없이)

이미 사용한 키워드:
{used_list_str}"""

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        gov_kw = message.content[0].text.strip().strip('"').strip("'")

        # 사용 목록에 추가
        used.append(gov_kw)
        with open(used_path, "w", encoding="utf-8") as f:
            f.write("\n".join(used))

        print(f"   🏛️ 정부지원금 키워드: {gov_kw}")
        return {
            "keyword": gov_kw,
            "type": "정보형",
            "competition": "낮음",
            "ad_price": "높음",
            "related": [],
            "reason": "정부지원금 고정 슬롯"
        }
    except Exception as e:
        print(f"   ⚠️ 정부지원금 키워드 생성 실패: {e}")
        return None


def generate_policy_keyword():
    """매일 새로운 정부정책자금 키워드 1개 생성 (중복 방지)"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    used_path = os.path.join(base_dir, "used_policy_keywords.txt")

    used = []
    if os.path.exists(used_path):
        with open(used_path, "r", encoding="utf-8") as f:
            used = [line.strip() for line in f if line.strip()]

    used_list_str = "\n".join(used[-60:]) if used else "없음"

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        prompt = f"""오늘 날짜: {now_kst().strftime("%Y년 %m월 %d일")}

대한민국 정부정책자금/저금리 대출 중에서 블로그 글 키워드로 좋은 것 1개를 추천해줘.

조건:
- 구체적인 정책자금 이름 (예: "소상공인 정책자금 대출 신청 방법", "청년 창업 저금리 대출 조건")
- 갚아야 하는 융자/대출 상품 (정부지원금/보조금과 다름)
- 검색량 있고 실용적인 정보성 키워드
- 아래 이미 사용한 목록에 없는 것
- 키워드만 한 줄로 출력 (설명 없이)

이미 사용한 키워드:
{used_list_str}"""

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        policy_kw = message.content[0].text.strip().strip('"').strip("'")

        used.append(policy_kw)
        with open(used_path, "w", encoding="utf-8") as f:
            f.write("\n".join(used))

        print(f"   💰 정부정책자금 키워드: {policy_kw}")
        return {
            "keyword": policy_kw,
            "type": "정보형",
            "competition": "낮음",
            "ad_price": "높음",
            "related": [],
            "reason": "정부정책자금 고정 슬롯"
        }
    except Exception as e:
        print(f"   ⚠️ 정부정책자금 키워드 생성 실패: {e}")
        return None

def save_today_keywords(keywords, best6):
    """자동발행 스크립트가 읽어갈 JSON 저장"""
    from datetime import timedelta
    tomorrow = (now_kst() + timedelta(days=1)).strftime("%Y-%m-%d")
    best6_keywords_map = {kw.get("keyword"): kw for kw in keywords}

    data = {
        "date": tomorrow,
        "schedule": []
    }

    for i, kw in enumerate(best6):
        keyword = kw.get("keyword", "")
        updated_kw = best6_keywords_map.get(keyword, kw)
        data["schedule"].append({
            "time": PUBLISH_TIMES[i],
            "keyword": keyword,
            "title": updated_kw.get("title", ""),           # 블로그스팟용 제목
            "naver_title": updated_kw.get("naver_title", ""),  # 네이버용 제목
            "type": kw.get("type", ""),
            "related_keywords": updated_kw.get("related", []),
            "naver_top_titles": updated_kw.get("naver_top_titles", []),
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
    type_emoji = {"롱테일": "📈", "행동형": "💡", "정보형": "📚", "숏테일": "🔥"}
    type_color = {"롱테일": "#2ed573", "행동형": "#ffa502", "정보형": "#1e90ff", "숏테일": "#ff4757"}
    competition_color = {"낮음": "#2ed573", "중간": "#ffa502", "높음": "#ff4757"}

    best6_time = {}
    for i, kw in enumerate(best6):
        best6_time[kw.get("keyword")] = PUBLISH_TIMES[i]

    # 이메일 표시 순서: 베스트6 → 정부지원금(7번) → 정부정책자금(8번) → 나머지 추천
    gov_kws = [kw for kw in keywords if kw.get("reason") == "정부지원금 고정 슬롯"]
    policy_kws = [kw for kw in keywords if kw.get("reason") == "정부정책자금 고정 슬롯"]
    gov_policy_names = {kw.get("keyword") for kw in gov_kws + policy_kws}
    best6_names = {kw.get("keyword") for kw in best6}
    regular_best6 = [kw for kw in best6 if kw.get("keyword") not in gov_policy_names][:6]
    remaining = [kw for kw in keywords if kw.get("keyword") not in best6_names and kw.get("keyword") not in gov_policy_names]
    display_order = regular_best6 + gov_kws + policy_kws + remaining

    all_rows = ""
    for i, kw in enumerate(display_order, 1):
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

        time_badge = ""
        gov_badge = ""
        policy_badge = ""
        if kw.get("reason") == "정부지원금 고정 슬롯":
            gov_badge = '<span style="background:#e67e22; color:white; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold; margin-left:6px;">🏛️ 정부지원금</span>'
        if kw.get("reason") == "정부정책자금 고정 슬롯":
            policy_badge = '<span style="background:#2980b9; color:white; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold; margin-left:6px;">💰 정부정책자금</span>'
        if is_best:
            from datetime import timedelta
            slot_time = best6_time[kw_name]
            tomorrow = now_kst() + timedelta(days=1)
            pub_date = tomorrow.strftime("%m월%d일").lstrip("0").replace("월0", "월")
            time_badge = f'<span style="background:#764ba2; color:white; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold; margin-left:6px;">⏰ {pub_date} {slot_time} 발행</span>'

        comp_badge = f'<span style="background:{comp_color}; color:white; padding:1px 6px; border-radius:8px; font-size:10px;">경쟁 {competition}</span>' if competition else ""
        ad_badge = f'<span style="background:#ff6b81; color:white; padding:1px 6px; border-radius:8px; font-size:10px; margin-left:3px;">단가 {ad_price}</span>' if ad_price else ""

        naver_title = kw.get("naver_title", "")
        naver_row = f'<span style="color:#03c75a; font-size:12px;">🟢 네이버용: {naver_title}</span><br>' if naver_title else ""

        all_rows += f"""
        <tr style="border-bottom:1px solid #eee; background:{bg};">
            <td style="padding:10px 12px; font-weight:bold; color:#333; width:25px; vertical-align:top;">{i}</td>
            <td style="padding:10px 12px;">
                <span style="background:{color}; color:white; padding:2px 7px; border-radius:10px; font-size:11px;">{emoji} {kw_type}</span>
                {comp_badge}{ad_badge}{gov_badge}{policy_badge}{time_badge}<br>
                <strong style="font-size:15px; color:#222;">{kw_name}</strong><br>
                <span style="color:#555; font-size:13px;">🌐 블로그스팟: {kw.get('title', '')}</span><br>
                {naver_row}
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

    <div style="background:linear-gradient(135deg,#667eea,#764ba2); padding:30px; text-align:center; border-radius:12px 12px 0 0;">
        <h1 style="color:white; margin:0; font-size:22px;">📊 오늘의 블로그 키워드 추천</h1>
        <p style="color:rgba(255,255,255,0.85); margin:8px 0 0; font-size:14px;">{today_str}</p>
        <p style="color:rgba(255,255,255,0.7); margin:4px 0 0; font-size:12px;">구글 트렌드 기반 · 블로그스팟 SEO 최적화</p>
    </div>

    <div style="background:white; padding:20px; margin-top:2px;">
        <h2 style="color:#333; font-size:17px; margin:0 0 15px;">
            📋 전체 추천 키워드 10개
            <span style="font-size:12px; color:#764ba2;">⏰ = 자동 발행 시간</span>
        </h2>
        <table style="width:100%; border-collapse:collapse;">
            {all_rows}
        </table>
    </div>

    <div style="background:white; padding:15px 20px; margin-top:4px; border-top:1px solid #eee;">
        <p style="color:#999; font-size:11px; margin:0;">
            🌐 블로그스팟용 = 구글 SEO 최적화 제목 &nbsp;|&nbsp;
            🟢 네이버용 = 감성형 제목 (백링크용) &nbsp;|&nbsp;
            ⏰ = 오늘 자동 발행 예정
        </p>
    </div>

    <div style="background:#f8f8f8; padding:15px; text-align:center; border-radius:0 0 12px 12px; border-top:1px solid #eee;">
        <p style="color:#aaa; font-size:11px; margin:0;">비니 (Bini) 블로그 자동화 | 매일 밤 11시 자동 발송</p>
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

    # 1. 트렌드 수집 (구글 메인, 네이버 보조)
    print("📰 트렌드 데이터 수집 중...")
    google_trends = get_google_trends_rss()
    naver_news = get_naver_news_for_context()

    # 2. Claude로 키워드 10개 + 베스트 6 생성
    print("\n🤖 Claude가 키워드 분석 중...")
    raw_text = generate_keywords_with_claude(google_trends, naver_news)

    # 3. 파싱
    keywords, best6 = parse_keywords_and_best6(raw_text)
    print(f"   → 전체 {len(keywords)}개 키워드 생성")
    print(f"   → 베스트 6개 선정: {[kw['keyword'] for kw in best6]}")

    # 4. 블로그스팟용 + 네이버용 제목 각각 생성
    print("\n🔍 제목 생성 중 (블로그스팟용 + 네이버용)...")
    keywords, best6 = enrich_keywords_with_titles(keywords, best6)

    # 5. 정부지원금 키워드를 7번째 슬롯(18:00)에 추가
    print("\n🏛️ 정부지원금 키워드 생성 중...")
    gov_kw = generate_gov_keyword()
    if gov_kw:
        best6.append(gov_kw)  # 7번째 슬롯(18:00)
        if not any(kw.get("keyword") == gov_kw["keyword"] for kw in keywords):
            keywords.append(gov_kw)

    # 6. 정부정책자금 키워드를 8번째 슬롯(21:00)에 추가
    print("\n💰 정부정책자금 키워드 생성 중...")
    policy_kw = generate_policy_keyword()
    if policy_kw:
        best6.append(policy_kw)  # 8번째 슬롯(21:00)
        if not any(kw.get("keyword") == policy_kw["keyword"] for kw in keywords):
            keywords.append(policy_kw)

    # 7. JSON 저장
    print("\n💾 오늘의 발행 스케줄 저장 중...")
    save_today_keywords(keywords, best6)

    # 8. 이메일 발송
    html = build_email_html(keywords, best6, today_str)
    subject = f"📊 [{today_short}] 키워드 추천 10개 + 오늘 자동발행 8개"
    print(f"\n📧 이메일 발송 중... → {EMAIL_RECIPIENT}")
    send_email(subject, html)

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
