# ================================================
# 한발뉴스24 - 뉴스 수집 모듈 (hanbal_collector.py)
# Tavily API로 카테고리 12개 × 2개 검색 → 24시간 필터링
# ================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# GitHub Actions 환경변수 우선, 없으면 config.py에서 로드
try:
    from config import TAVILY_API_KEY
except ImportError:
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import time

KST = ZoneInfo("Asia/Seoul")

# ================================================
# 카테고리 12개 × 검색어 2개
# ================================================
CATEGORIES = [
    {
        "id": 1,
        "name": "생활·정책",
        "queries": ["정부 지원금 신청 2026", "생활 제도 변경 정책"]
    },
    {
        "id": 2,
        "name": "건강·의료",
        "queries": ["건강 의료 뉴스 오늘", "질병 예방 건강검진 2026"]
    },
    {
        "id": 3,
        "name": "소비·IT",
        "queries": ["소비자 IT 가전 뉴스", "앱 통신 개인정보 소비"]
    },
    {
        "id": 4,
        "name": "재테크·경제",
        "queries": ["금리 세금 부동산 경제 뉴스", "연금 대출 재테크 2026"]
    },
    {
        "id": 5,
        "name": "여행·레저",
        "queries": ["여행 축제 관광 뉴스", "국내여행 레저 숙박 2026"]
    },
    {
        "id": 6,
        "name": "음식·식습관",
        "queries": ["식품 안전 회수 뉴스", "음식 식문화 가격 뉴스"]
    },
    {
        "id": 7,
        "name": "교육·육아",
        "queries": ["교육 입시 학교 뉴스", "육아 보육 양육 정책 2026"]
    },
    {
        "id": 8,
        "name": "자동차·교통",
        "queries": ["자동차 리콜 교통 뉴스", "대중교통 요금 보험 2026"]
    },
    {
        "id": 9,
        "name": "스포츠",
        "queries": ["스포츠 경기 결과 오늘", "한국 스포츠 선수 뉴스"]
    },
    {
        "id": 10,
        "name": "연예",
        "queries": ["연예 방송 드라마 영화 뉴스", "K팝 아이돌 작품 공식"]
    },
    {
        "id": 11,
        "name": "사회·사건",
        "queries": ["사회 사건 재난 안전 뉴스", "한국 사회 이슈 오늘"]
    },
    {
        "id": 12,
        "name": "트렌드·기술",
        "queries": ["AI 기술 트렌드 신제품 뉴스", "한국 IT 서비스 변화 2026"]
    },
]


def get_time_window():
    """발송 기준 시각 기준 직전 24시간 창 반환 (한국 시간)"""
    now = datetime.now(KST)
    today_5am = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now >= today_5am:
        # 오늘 5시 이후 실행 → 어제 5시 ~ 오늘 5시 기사 수집
        window_end = today_5am
        window_start = today_5am - timedelta(days=1)
    else:
        # 오늘 5시 이전 실행 → 그제 5시 ~ 어제 5시 기사 수집
        yesterday_5am = today_5am - timedelta(days=1)
        window_end = yesterday_5am
        window_start = yesterday_5am - timedelta(days=1)
    return window_start, window_end


def search_tavily(query, days=1):
    """Tavily API로 뉴스 검색"""
    url = "https://api.tavily.com/search"
    headers = {"Authorization": f"Bearer {TAVILY_API_KEY}"}
    payload = {
        "query": query,
        "topic": "news",
        "days": days,
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"  [오류] Tavily 검색 실패: {query} → {e}")
        return []


def parse_published_date(date_str):
    """발행일 문자열을 datetime으로 변환"""
    if not date_str:
        return None

    # Tavily 날짜 형식: "Sun, 04 Oct 2026 16:00:00 GMT"
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(KST)
    except:
        pass

    # ISO 형식들
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(date_str[:19])])
            dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(KST)
            return dt
        except:
            continue
    return None


def collect_news():
    """
    카테고리 12개 뉴스 수집
    반환값: {카테고리명: [기사 목록], ...}
    """
    window_start, window_end = get_time_window()
    today_str = datetime.now(KST).strftime("%Y-%m-%d")

    print(f"\n{'='*50}")
    print(f"[한발뉴스24] 뉴스 수집 시작")
    print(f"수집 기간: {window_start.strftime('%Y-%m-%d %H:%M')} ~ {window_end.strftime('%Y-%m-%d %H:%M')} (KST)")
    print(f"{'='*50}\n")

    result = {}

    for cat in CATEGORIES:
        cat_name = cat["name"]
        print(f"[{cat['id']:02d}] {cat_name} 수집 중...")
        articles = []
        seen_urls = set()

        for query in cat["queries"]:
            time.sleep(0.5)  # API 호출 간격
            raw = search_tavily(query, days=2)

            for item in raw:
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue

                # 발행일 필터링 (24시간 창)
                pub_date = parse_published_date(item.get("published_date", ""))
                if pub_date is None:
                    continue  # 날짜 파싱 실패 → 제외
                if not (window_start <= pub_date <= window_end):
                    continue  # 24시간 창 밖 → 제외

                seen_urls.add(url)
                articles.append({
                    "제목": item.get("title", ""),
                    "본문요약": item.get("content", "")[:300],
                    "언론사": item.get("source", ""),
                    "발행시각": pub_date.strftime("%Y-%m-%d %H:%M"),
                    "url": url,
                })

        result[cat_name] = articles
        print(f"  → {len(articles)}개 기사 수집")

    print(f"\n수집 완료! 총 {sum(len(v) for v in result.values())}개 기사\n")

    return {
        "today": today_str,
        "window_start": window_start.strftime("%Y-%m-%d %H:%M"),
        "window_end": window_end.strftime("%Y-%m-%d %H:%M"),
        "categories": result,
    }


# ================================================
# 단독 테스트 실행
# ================================================
if __name__ == "__main__":
    data = collect_news()
    print("\n[카테고리별 수집 결과]")
    for cat_name, articles in data["categories"].items():
        print(f"  {cat_name}: {len(articles)}개")
        for a in articles[:2]:
            print(f"    - {a['제목'][:40]} ({a['발행시각']})")
