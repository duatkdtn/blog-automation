# ================================================
# wp_auto_publish.py
# SEO 키워드 자동수집 → Claude Sonnet 4.6 → WordPress 자동 발행
# 실행: python wp_auto_publish.py
# ================================================

import json, os, sys, time, io, re, smtplib, base64, pickle
from urllib.parse import urlparse
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

MAX_POSTS      = 4   # 최대 발행 개수
INTERVAL_HOURS = 3   # 발행 간격 (시간)

USED_WP_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "used_wp_keywords.txt")
DEDUP_DAYS     = 7   # 중복 금지 기간 (일)


def load_used_wp_keywords():
    """7일 이내 발행된 키워드 목록 로드"""
    if not os.path.exists(USED_WP_FILE):
        return set()
    cutoff = datetime.now(KST) - timedelta(days=DEDUP_DAYS)
    used = set()
    with open(USED_WP_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                try:
                    dt = datetime.fromisoformat(parts[0]).replace(tzinfo=KST)
                    if dt >= cutoff:
                        used.add(parts[1].lower())
                except Exception:
                    pass
    return used


def save_wp_keywords(keywords):
    """발행 성공한 키워드를 날짜와 함께 저장"""
    now_str = datetime.now(KST).isoformat()
    with open(USED_WP_FILE, "a", encoding="utf-8") as f:
        for kw in keywords:
            f.write(f"{now_str}\t{kw.lower()}\n")


def is_duplicate_article(article, used_keywords):
    """기사의 키워드후보 중 하나라도 7일 이내 발행됐으면 True"""
    candidates = article.get("키워드후보", [])
    title = article.get("제목", "").lower()
    for kw in candidates:
        if kw.lower() in used_keywords:
            return True, kw
    # 제목 자체도 체크 (키워드후보 없을 때 대비)
    for kw in used_keywords:
        if kw and kw in title:
            return True, kw
    return False, None

# 카테고리명 → WordPress 카테고리 ID
CAT_MAP = {
    "생활·정책":    207, "건강·의료":    208, "재테크·금융":  209,
    "부동산":        210, "교육·육아":    211, "자동차·교통":  212,
    "음식·건강식":  213, "여행·나들이":  214, "디지털·IT":   215,
    "법률·생활법":  216, "노약자·시니어":217, "연예·문화":   218,
    "트렌드·사회":  219,
}

# 카테고리별 실제 URL (내부링크용)
CATEGORY_URLS = {
    "생활·정책":    "https://hijaneeinfo.com/category/life-policy/",
    "건강·의료":    "https://hijaneeinfo.com/category/health-medical/",
    "재테크·금융":  "https://hijaneeinfo.com/category/finance/",
    "부동산":        "https://hijaneeinfo.com/category/realestate/",
    "교육·육아":    "https://hijaneeinfo.com/category/education/",
    "자동차·교통":  "https://hijaneeinfo.com/category/car-traffic/",
    "음식·건강식":  "https://hijaneeinfo.com/category/food/",
    "여행·나들이":  "https://hijaneeinfo.com/category/travel/",
    "디지털·IT":   "https://hijaneeinfo.com/category/digital-it/",
    "법률·생활법":  "https://hijaneeinfo.com/category/law/",
    "노약자·시니어":"https://hijaneeinfo.com/category/senior/",
    "연예·문화":   "https://hijaneeinfo.com/category/entertainment/",
    "트렌드·사회": "https://hijaneeinfo.com/category/trend/",
}

# 카테고리별 추천 계산기 (글에 포함) — hijaneeinfo.com 워프 전용
CALC_LINKS = {
    "재테크·금융":   ("연봉 실수령액 계산기",      "https://hijaneeinfo.com/salary-calculator/"),
    "생활·정책":     ("근로장려금 계산기",          "https://hijaneeinfo.com/earned-income-calculator/"),
    "노약자·시니어": ("국민연금 예상수령액 계산기", "https://hijaneeinfo.com/pension-calculator/"),
    "부동산":        ("취득세 계산기",              "https://hijaneeinfo.com/realestate-tax-calculator/"),
    "교육·육아":     ("만 나이 계산기",             "https://hijaneeinfo.com/age-calculator/"),
    "건강·의료":     ("BMI 계산기",                 "https://hijaneeinfo.com/bmi-calculator/"),
    "법률·생활법":   ("근로장려금 계산기",          "https://hijaneeinfo.com/earned-income-calculator/"),
}

# ================================================
# 1. SEO 키워드 자동 수집 (한발뉴스 대체)
# ================================================

# 시드 키워드 풀 (30~70대 타겟, 네이버 검색 최적화)
SEED_KEYWORDS = [
    # 정책·지원금
    "실업급여", "청년 지원금", "소상공인 지원금", "기초연금", "아동수당",
    "청년내일채움공제", "육아휴직 급여", "출산지원금", "장애인 연금", "한부모 지원금",
    "에너지 바우처", "주거급여", "생계급여", "복지로 신청", "긴급복지 지원",
    # 세금·금융
    "종합소득세 신고", "연말정산 방법", "퇴직금 계산", "건강보험료", "국민연금 수령",
    "ISA 계좌 혜택", "주택청약 조건", "전세대출 조건", "신용대출 금리", "대출 한도",
    "근로장려금 신청", "자녀장려금",
    # 건강·의료
    "건강검진 항목", "국가암검진 대상", "독감 예방접종 무료", "치매 검사 방법",
    "실비보험 청구 방법", "요양원 비용", "노인복지관 이용", "치매안심센터",
    "당뇨 초기 증상", "고혈압 관리법", "콜레스테롤 낮추는 방법", "영양제 추천",
    # 부동산·임대
    "전세 계약 주의사항", "월세 세액공제", "임대차보호법", "취득세 계산",
    "재산세 납부", "양도소득세 계산", "공인중개사 수수료", "전입신고 방법",
    # 생활·소비
    "자동차 리콜 확인", "통신비 지원", "전기세 절약 방법", "수도요금 감면",
    "소비자 보호 신청", "자동차보험 비교",
    # 취업·노무
    "퇴직금 지급 기준", "연차 계산법", "최저임금 2026", "4대보험 계산",
    "실업급여 신청 조건", "육아휴직 신청 방법", "근로계약서 작성법", "해고 예고수당",
    # 육아·교육
    "아이돌봄 서비스 신청", "영유아 건강검진 시기", "어린이집 비용 지원",
    "초등학교 입학 준비", "학원비 세액공제", "교육비 환급",
    # 노후·연금
    "국민연금 수령 나이", "기초연금 신청 조건", "노인 일자리 신청", "요양보호사 자격증",
    "연금저축 세액공제", "IRP 계좌 혜택", "노후 준비 방법",
    # 여행·나들이
    "국내여행 추천 2026", "가족여행 코스", "당일치기 여행지", "주말여행 명소",
    "제주 여행 코스", "겨울 여행지 추천",
    # 음식·건강식
    "다이어트 음식 추천", "혈당 낮추는 음식", "면역력 높이는 음식",
    "단백질 많은 음식", "칼로리 낮은 음식",
]


def collect_seo_keywords(used_keywords, max_count=4):
    """SEO 키워드 수집 → article 형식 리스트 반환 (한발뉴스 대체)"""
    import random

    print("  🔍 SEO 키워드 수집 중...")

    # 최근 발행 키워드와 겹치지 않는 시드 필터링
    available = [s for s in SEED_KEYWORDS
                 if not any(u in s or s in u for u in used_keywords if len(u) > 1)]
    if len(available) < 8:
        available = SEED_KEYWORDS[:]

    seed_sample = random.sample(available, min(14, len(available)))
    print(f"  시드 샘플: {seed_sample[:4]}...")

    # 자동완성으로 연관 후보 수집
    all_candidates = set()
    for seed in seed_sample[:10]:
        terms = get_naver_autocomplete(seed, max_results=5)
        for t in terms:
            all_candidates.add(t)
        if not terms:
            all_candidates.add(seed)

    candidates_list = list(all_candidates)[:30]
    if not candidates_list:
        candidates_list = seed_sample[:20]

    # Claude로 오늘 최적 키워드 4개 선정 + 핵심사실 생성
    used_str = "\n".join(list(used_keywords)[-20:]) if used_keywords else "없음"
    candidates_str = "\n".join(f"- {k}" for k in candidates_list)

    cat_list = "/".join(CAT_MAP.keys())
    prompt = f"""다음 키워드 후보 중에서 오늘 워드프레스 블로그에 발행할 최적 키워드 {max_count}개를 선정하고,
각 키워드로 5,000자 이상 정보성 블로그 글을 쓸 때 필요한 핵심 정보 포인트를 5개씩 정리해주세요.

[키워드 후보]
{candidates_str}

[최근 발행 키워드 (유사 주제 제외)]
{used_str}

[선정 기준]
- 30~70대 한국인이 네이버에서 실제로 많이 검색하는 실용적 정보성 키워드
- 롱테일 형태 (2~4단어 조합) 우선
- 최근 발행 주제와 겹치지 않을 것
- 4개 분야가 최대한 다양하게 (같은 대분류 2개 이상 금지)
- 신청방법, 조건, 혜택, 비교, 계산법 등 실용 정보성 글로 쓸 수 있는 것

[카테고리 목록] (반드시 이 중에서 선택)
{cat_list}

[출력 형식] (정확히 이 형식, 코드블록·설명 없이)
키워드1: 선정키워드|카테고리|한줄요약|핵심정보1,핵심정보2,핵심정보3,핵심정보4,핵심정보5
키워드2: 선정키워드|카테고리|한줄요약|핵심정보1,핵심정보2,핵심정보3,핵심정보4,핵심정보5
키워드3: 선정키워드|카테고리|한줄요약|핵심정보1,핵심정보2,핵심정보3,핵심정보4,핵심정보5
키워드4: 선정키워드|카테고리|한줄요약|핵심정보1,핵심정보2,핵심정보3,핵심정보4,핵심정보5"""

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        print(f"  Claude 키워드 선정 완료")

        articles = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            # "키워드1: 실업급여 신청방법|생활·정책|설명|사실1,사실2,..."
            if ":" not in line:
                continue
            colon_idx = line.index(":")
            content = line[colon_idx + 1:].strip()
            parts = content.split("|")
            if len(parts) < 4:
                continue

            keyword = parts[0].strip()
            cat     = parts[1].strip()
            summary = parts[2].strip()
            facts   = [f.strip() for f in parts[3].split(",") if f.strip()]

            # 카테고리 유효성 검사
            if cat not in CAT_MAP:
                cat = "생활·정책"

            # 연관 검색어 (자동완성)
            related = get_naver_autocomplete(keyword, max_results=5)
            keywords_list = [keyword] + related[:4]

            articles.append({
                "제목":      keyword,
                "카테고리":  cat,
                "한줄요약":  summary,
                "핵심사실":  facts,
                "키워드후보": keywords_list,
                "링크":      "",
                "출처":      "",
                "확정여부":  "Y",
                "_is_seo":   True,
            })
            print(f"  ✅ [{cat}] {keyword}")

        return articles[:max_count]

    except Exception as e:
        print(f"  ❌ SEO 키워드 수집 실패: {e}")
        return []


# ================================================
# 2. Claude API로 WordPress 글 생성
# ================================================

def _get_article_base(article, today_str):
    """기사 공통 정보 추출"""
    cat          = article.get("카테고리", "")
    title_h      = article.get("제목", "")
    summary      = article.get("한줄요약", "")
    facts        = article.get("핵심사실", [])
    keywords     = article.get("키워드후보", [])
    link         = article.get("링크", "")
    source       = article.get("출처", "")
    confirmed    = article.get("확정여부", "")
    facts_text   = "\n".join([f"- {f}" for f in facts])
    keywords_str = ", ".join(keywords)
    return cat, title_h, summary, facts_text, keywords_str, link, source, confirmed


def get_naver_autocomplete(keyword, max_results=8):
    """
    네이버 자동완성 API로 연관 검색어 수집 (무료, 인증 불필요)
    반환: list of str (예: ["실업급여 신청방법", "실업급여 계산기", ...])
    """
    try:
        url = "https://ac.search.naver.com/nx/ac"
        params = {
            "q": keyword,
            "st": "100",
            "frm": "nv",
            "r_format": "json",
            "r_enc": "UTF-8",
            "r_unicode": "0",
            "t_koreng": "1",
            "ans": "2",
            "run": "2",
            "rev": "4",
            "con": "1",
        }
        res = requests.get(url, params=params, timeout=5,
                           headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            data = res.json()
            # 응답 형식: {"items": [["키워드1", 0], ["키워드2", 0], ...]}
            items = data.get("items", [[]])
            if items and isinstance(items[0], list):
                suggestions = [item[0] for item in items[0] if isinstance(item, list) and item]
            else:
                suggestions = [item[0] if isinstance(item, list) else item for item in items]
            result = [s for s in suggestions if isinstance(s, str) and s.strip()][:max_results]
            if result:
                print(f"     🔍 자동완성: {result[:4]}")
            return result
    except Exception as e:
        print(f"     ℹ️ 자동완성 실패: {e}")
    return []


def _call_sonnet(system, user, max_tokens=512):
    """Sonnet 호출 — 제목 생성 전용"""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return msg.content[0].text


def _call_haiku(system, user, max_tokens=1024):
    """Haiku 호출 공통 함수"""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return msg.content[0].text.strip()


def generate_wp_post(article, today_str):
    """2단계 Haiku 호출로 WordPress 글 생성 (비용 절감)"""
    cat, title_h, summary, facts_text, keywords_str, link, source, confirmed = \
        _get_article_base(article, today_str)

    calc_hint = ""
    if cat in CALC_LINKS:
        c_name, c_url = CALC_LINKS[cat]
        calc_hint = f'계산기 버튼 포함: {c_name} → {c_url}'

    # ── 1단계: 네이버 자동완성으로 연관 검색어 수집 ──
    main_keyword = keywords_str.split(",")[0].strip() if keywords_str else title_h[:10]
    autocomplete_list = get_naver_autocomplete(main_keyword)
    autocomplete_hint = ""
    if autocomplete_list:
        autocomplete_hint = f"\n[네이버 실제 자동완성 검색어 (이 단어들을 제목에 자연스럽게 조합할 것)]\n" + \
                            "\n".join(f"- {s}" for s in autocomplete_list)

    # ── 1단계: 제목·슬러그·태그·메타·구조 생성 (짧은 JSON, 토큰 부담 없음) ──
    sys1 = "한국어 블로그 전문 작가. JSON만 출력. 절대 코드블록 사용 금지."
    usr1 = f"""아래 SEO 키워드 기반 소재로 워드프레스 블로그 글의 메타 정보를 작성하세요.

[소재]
카테고리: {cat}
제목: {title_h}
요약: {summary}
핵심사실:
{facts_text}
키워드: {keywords_str}
출처: {source}
{autocomplete_hint}

[규칙]
- wp_title: 메인키워드(맨 앞) + 위 [네이버 실제 자동완성 검색어] 중 1~2개 단어 반드시 포함 + 정보성 마무리 문구, 30자 이내
  → 자동완성 검색어가 제공된 경우 반드시 그 단어들을 활용해 제목 구성 (사람들이 실제로 검색하는 말)
  → 자동완성이 없으면 키워드에서 파생된 세부 검색어(신청방법·조건·대상·혜택 등)를 삽입
  → 숫자 반드시 포함 (연도·금액·비율·기간 중 하나)
  → 정책·제도·신청·혜택 글: 연도(2026) + "신청방법", "조건 정리", "혜택 총정리" 등 정보성 문구로 마무리
  → 리콜·회수·안전 글: 구체적 수치 + "대상 확인", "신청방법", "제품 목록" 등으로 마무리
  → 부동산·금융·경제 글: 수치 + "분석", "동향", "가이드" 등으로 마무리
  → 여행·축제·이벤트 글: 날짜·장소 + "추천", "코스", "일정" 등으로 마무리
  → 뉴스 헤드라인 스타일 절대 금지: "~왜?", "~하나?", "~가능?", "~확인하세요", "지금이 기회인가" 금지
  → 좋은 예: "통합돌봄 신청방법 2026 – 대상 조건·서비스 종류 완전 정리"
  → 좋은 예: "서울 아파트 매매 동향 2026 – 54% 신고가 지역별 가격 분석"
  → 나쁜 예: "서울 아파트 54% 최고가 경신 – 지금이 최적기?" (뉴스 헤드라인 스타일)
- focus_keyword: wp_title 맨 앞에 오는 핵심 키워드와 정확히 동일한 문구
- meta_description: focus_keyword로 시작, 120자 이내
- tags: 2~3개만, 카테고리명({cat})과 절대 겹치지 않게, 포커스키워드 파생 개념으로
- wp_slug: 영어만, 6단어 이내, 한글 절대 금지

[출력] JSON만, 코드블록 없이:
{{
  "wp_title": "메인키워드 맨앞 + 신청방법/조건/분석/추천 등 정보성 마무리 + 30자이내",
  "wp_slug": "english-slug-max-6-words",
  "focus_keyword": "wp_title 맨 앞 키워드와 정확히 동일",
  "meta_description": "포커스키워드로 시작하는 120자 이내 설명",
  "tags": ["태그1","태그2"]
}}"""

    raw1 = _call_sonnet(sys1, usr1, max_tokens=512)  # 제목은 Sonnet 전용
    raw1 = re.sub(r"```json\s*", "", raw1)
    raw1 = re.sub(r"```\s*", "", raw1).strip()
    meta = json.loads(raw1)
    print(f"     1단계 완료: {meta.get('wp_title','')}")

    # ── 2단계: 본문 앞부분 (요약박스·도입부·본문·오해주의) ──
    sys2 = "한국어 블로그 전문 작가. HTML 본문만 출력. JSON·마크다운·코드블록 감싸기 절대 금지."
    usr2 = f"""아래 정보로 워드프레스 블로그 HTML 본문 앞부분을 작성하세요.

[글 정보]
제목: {meta.get('wp_title', title_h)}
포커스키워드: {meta.get('focus_keyword', '')}
카테고리: {cat}
핵심사실:
{facts_text}
원본링크: {link}
오늘날짜: {today_str}

[작성할 섹션 - 이 4개만 작성]
① 파란 핵심 요약 박스 (background:#eaf4fb;border:2px solid #2980b9) - ✅ 5개 항목
   ※ 목차 직접 삽입 절대 금지 (플러그인이 자동 생성함)
② 도입부: ~더라고요, ~이에요 말투, 2~3문단
   → 도입부 마지막 바로 아래 미니박스 추가:
   <div style="background:#f8f9fa;border:1px solid #dee2e6;padding:15px 20px;margin:20px 0;border-radius:6px;">
   <strong>🙋 이런 분들이 꼭 읽어보세요</strong><br>
   · 체크항목1<br>· 체크항목2<br>· 체크항목3
   </div>
③ 본문: h2 6~10개 범위, 표 최소 2개 (thead background:#2980b9;color:white), 리스트 박스
   - h2 안에 자연스럽게 나뉘는 소주제는 h3로 세분화
   - 포커스키워드를 본문 전체에 자연스럽게 6~9회 분산
   - 행 번갈아: background:#fff / #f8f9fa
   - 본문 중간 자연스러운 문장 안에 공식 출처 인라인 링크 1~2개 삽입
     예: <a href="{link}" target="_blank" rel="noopener">공식 발표 내용</a>
     앵커텍스트는 키워드 포함한 구체적인 단어 사용 ("여기 클릭", "바로가기" 금지)
④ 오해/주의사항 섹션 (h2 제목 포함)
   - 박스 스타일: background:#fdf2f8;border:1px solid #d2b4de;padding:20px;margin:20px 0
   - ❌ 기호로 잘못된 생각, ✅ 기호로 올바른 내용

[언어 수준]
- 초등학생·70~80대도 이해할 수 있는 쉬운 단어
- 어려운 단어는 바로 뒤 괄호로 풀어서 쓸 것
- 문장은 짧게. 한 문장에 한 가지 내용만.

[원칙]
- inline style만 (style태그 금지)
- 종결어미는 자연스럽게 다양하게 혼용: 입니다, 이죠, 하죠, ~까요?, 됩니다, 인데요, 겠죠, 데요, 이에요, 더라고요 등
- 한 가지 종결어미만 반복 금지 (강제 풀백 방식 금지) — 글의 온도 조절이 필요함
- "마치며", "정리하며", "마무리하며", "마무리", "총정리" 같은 마무리 성격의 별도 섹션 생성 절대 금지
- AI생성표시 박스 절대 금지 / 정보출처 별도 섹션 생성 금지
- HTML만 출력 (코드블록 감싸기 금지)"""

    html_part1 = _call_haiku(sys2, usr2, max_tokens=8192)
    html_part1 = re.sub(r"```html\s*", "", html_part1)
    html_part1 = re.sub(r"```\s*", "", html_part1).strip()
    print(f"     2단계 완료: HTML {len(html_part1)}자")

    # ── 3단계: 본문 뒷부분 (FAQ·요약박스·이런분들·CTA·링크·면책) ──
    focus_kw = meta.get('focus_keyword', meta.get('wp_title', title_h))

    # 카테고리 URL 목록 텍스트 생성
    cat_url_list = "\n".join([f"   · {k}: {v}" for k, v in CATEGORY_URLS.items()])

    # 외부버튼용 출처 레이블 (source 없으면 링크 도메인 자동 추출)
    source_label = source if source else (urlparse(link).netloc.replace('www.', '') if link else '공식 사이트')

    # 면책문구용 년월 (일 제외)
    month_str = datetime.now(KST).strftime("%Y년 %m월")

    sys3 = "한국어 블로그 전문 작가. HTML만 출력. 코드블록·마크다운 절대 금지."
    usr3 = f"""아래 정보로 워드프레스 블로그 HTML 본문 뒷부분을 작성하세요.

[글 정보]
제목: {meta.get('wp_title', title_h)}
포커스키워드: {focus_kw}
카테고리: {cat}
핵심사실:
{facts_text}
원본링크: {link}
출처: {source}
오늘날짜: {today_str}
{f'계산기: {calc_hint}' if calc_hint else ''}

[작성할 섹션 - 이 순서대로 모두 작성]
① FAQ 섹션 (h2 제목 "자주 묻는 질문" 포함)
   - 질문 5개 이상, 각 질문은 h3 태그로 감싸기
   형식:
   <div style="background:#f8f9fa;border-left:4px solid #2980b9;padding:15px 20px;margin-bottom:10px;border-radius:4px;">
   <h3 style="margin:0 0 8px 0;font-size:1em;color:#2c3e50;">Q. 질문 내용</h3>
   <p style="margin:0;">A. 답변 내용</p>
   </div>

② 이런분들 해당 섹션 (h2 제목 "✅ 이런 분들 꼭 확인해보세요!" 포함)
   - background:#eaf4fb;border:1px solid #aed6f1;padding:20px;margin:20px 0
   - 👉 기호로 체크리스트 5개 이상
{f"③ 계산기 버튼 섹션: {calc_hint}" if calc_hint else ""}
③ 결론 CTA 섹션 (background:#2980b9;color:white;padding:30px;margin:20px 0;border-radius:8px;text-align:center)
   - <strong style="font-size:1.2em;color:white;">핵심 행동 촉구 문구</strong>
   - 글 요약 + 행동 독려 (흰 글씨)
   - "비슷한 주제로 [관련키워드]도 정리해뒀으니 함께 참고해보세요!" (흰 글씨)
   - "궁금한 점은 댓글로 남겨주세요 :)" (흰 글씨)

④ 내부링크박스 (h2 제목 "📌 함께 읽으면 좋은 글" 포함)
   - background:#eaf4fb;border:1px solid #aed6f1;padding:20px;margin:20px 0
   - 아래 실제 카테고리 URL 목록에서만 골라서 3~4개 삽입 (추측 슬러그 절대 금지)
   - 현재 글 카테고리({cat}) 포함 관련 카테고리 위주로 선택
   [실제 카테고리 URL 목록]
{cat_url_list}
   - 형태: 👉 <a href="카테고리URL" style="color:#2980b9;">카테고리명 관련 글 모아보기</a>

⑤ 외부버튼: 공식 사이트 링크 (원본: {link}, 출처: {source_label})
   형식: <div style="text-align:center;margin:30px 0;">
   <a href="{link}" target="_blank" rel="noopener noreferrer"
      style="display:inline-block;background:#2980b9;color:white;padding:15px 40px;border-radius:6px;font-size:1.1em;font-weight:bold;text-decoration:none;">
   🔗 {source_label} 바로가기</a></div>

⑥ 면책문구
   - background:#f8f9fa;border:1px solid #dee2e6;padding:15px 20px;margin:30px 0;font-size:0.9em;color:#666
   - 내용: "{month_str} 기준 작성. 실제 신청·이용 전 공식 사이트에서 최신 정보를 반드시 확인하세요. 이 글은 정보 제공 목적으로 작성되었으며, 법적 효력이 없습니다."

[언어 수준]
- 초등학생·70~80대도 이해할 수 있는 쉬운 단어
- 문장은 짧게. 한 문장에 한 가지 내용만.

[원칙]
- inline style만 (style태그 금지)
- 종결어미는 자연스럽게 다양하게 혼용: 입니다, 이죠, 하죠, ~까요?, 됩니다, 인데요, 겠죠, 데요, 이에요, 더라고요 등
- 한 가지 종결어미만 반복 금지 (강제 풀백 방식 금지) — 글의 온도 조절이 필요함
- "마치며", "정리하며", "마무리하며", "마무리", "총정리" 같은 마무리 성격의 별도 섹션 생성 절대 금지
- AI생성표시 박스 절대 금지 / 정보출처 별도 섹션 생성 금지
- 내부링크박스(④)는 반드시 위에 제공된 [실제 카테고리 URL 목록]에 있는 URL만 사용 — 목록에 없는 URL, 글 제목 링크, 추측 URL 절대 금지
- HTML만 출력 (코드블록 감싸기 금지)"""

    html_part2 = _call_haiku(sys3, usr3, max_tokens=4096)
    html_part2 = re.sub(r"```html\s*", "", html_part2)
    html_part2 = re.sub(r"```\s*", "", html_part2).strip()
    print(f"     3단계 완료: HTML {len(html_part2)}자")

    html_content = html_part1 + "\n\n" + html_part2
    print(f"     전체 HTML: {len(html_content)}자")

    meta["html_content"] = html_content
    return meta


# ================================================
# 3. 썸네일 생성 (Pillow)
# ================================================

def make_thumbnail(title, category, today_str=None):
    """키워드 기반 썸네일 생성 (1200×630 WebP) — regen_thumbnails 테마 시스템 활용"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  ⚠️ Pillow 없음 - 썸네일 생성 건너뜀")
        return None

    try:
        import regen_thumbnails as rt
        W, H = 1200, 630
        accent_color, icon_type = rt.get_theme(title)
        bg = rt.accent_to_bg(accent_color)

        img  = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(img)

        f_badge = rt.load_font(27)
        f_sub   = rt.load_font(29, bold=False)
        f_logo  = rt.load_font(21, bold=False)

        # 카테고리 배지
        badge = f" {category} "
        bb  = draw.textbbox((0, 0), badge, font=f_badge)
        bw  = bb[2] - bb[0] + 24
        bh  = bb[3] - bb[1] + 12
        draw.rounded_rectangle([44, 40, 44 + bw, 40 + bh], radius=7, fill=accent_color)
        draw.text((56, 46), badge.strip(), font=f_badge, fill="white")

        # 후킹 문구 생성 (Claude Haiku)
        hook1, hook2, sub1, sub2 = rt.generate_hook_text(title)

        MAX_TW = 720

        def fit_font(text, start_size=82):
            for sz in range(start_size, 48, -3):
                f = rt.load_font(sz)
                bb2 = draw.textbbox((0, 0), text, font=f)
                if (bb2[2] - bb2[0]) <= MAX_TW:
                    return f, sz
            return rt.load_font(52), 52

        f_title,  _ = fit_font(hook1)
        f_accent, _ = fit_font(hook2)

        # 줄1 (진한 다크)
        y = 118
        draw.text((48, y), hook1, font=f_title, fill=(28, 28, 28))
        b1 = draw.textbbox((48, y), hook1, font=f_title)
        y += b1[3] - b1[1] + 6

        # 줄2 (강조색 + 밑줄)
        draw.text((48, y), hook2, font=f_accent, fill=accent_color)
        b2 = draw.textbbox((48, y), hook2, font=f_accent)
        draw.line([(48, b2[3] + 5), (b2[2], b2[3] + 5)], fill=accent_color, width=4)
        y += b2[3] - b2[1] + 30

        # 구분선
        div_color = tuple(int(c * 0.5 + bg[i] * 0.5) for i, c in enumerate(accent_color))
        draw.line([(48, y), (700, y)], fill=div_color, width=2)
        y += 20

        # 부제목
        gray = (85, 85, 85)
        if sub1:
            draw.text((48, y), sub1, font=f_sub, fill=gray)
            y += 40
        if sub2:
            draw.text((48, y), sub2, font=f_sub, fill=gray)

        # 로고 박스 (왼쪽 하단)
        draw.rounded_rectangle([40, H - 72, 248, H - 32], radius=7, fill="white")
        draw.text((54, H - 62), "하이자니 정보마당", font=f_logo, fill=(70, 70, 70))

        # 오른쪽 컬러 일러스트
        rt.draw_icon(draw, icon_type, 970, H // 2 + 20, 200, accent_color)

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=92)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        print(f"  ⚠️ 썸네일 생성 오류 ({e}) - 기본 썸네일로 대체")
        # 폴백: 단순 파란 그라디언트
        try:
            from PIL import Image, ImageDraw
            W, H = 1200, 630
            img  = Image.new("RGB", (W, H))
            draw = ImageDraw.Draw(img)
            for y in range(H):
                t = y / H
                r = int(26  + (41  - 26)  * t)
                g = int(82  + (128 - 82)  * t)
                b = int(118 + (185 - 118) * t)
                draw.line([(0, y), (W, y)], fill=(r, g, b))
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=90)
            buf.seek(0)
            return buf.read()
        except Exception:
            return None


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
# 6. 전날 발행 글 색인 요청
# ================================================

def request_yesterday_indexing():
    """어제 WordPress에 발행된 글들을 Google 색인 요청"""
    yesterday = datetime.now(KST) - timedelta(days=1)
    after  = yesterday.replace(hour=0,  minute=0,  second=0).strftime("%Y-%m-%dT%H:%M:%S")
    before = yesterday.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%dT%H:%M:%S")

    print(f"\n[색인 요청] 어제({yesterday.strftime('%Y-%m-%d')}) 발행 글 조회 중...")

    try:
        res = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts",
            auth=AUTH,
            params={"after": after, "before": before, "per_page": 20, "status": "publish"},
            timeout=15,
        )
        if res.status_code != 200:
            print(f"  ❌ 글 목록 조회 실패: {res.status_code}")
            return []

        posts = res.json()
        print(f"  어제 발행 글 {len(posts)}개 발견")

        indexed = []
        for post in posts:
            url = post.get("link", "")
            if url:
                ok = request_google_indexing(url)
                if ok:
                    indexed.append(url)
                time.sleep(0.5)

        return indexed
    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return []


# ================================================
# 7. 완료 이메일 발송
# ================================================

def send_result_email(results, today_str, indexed_urls=None):
    """발행 결과 이메일 발송"""
    success_list = [r for r in results if r.get("wp_id")]
    indexed_urls = indexed_urls or []

    # 색인 요청 섹션
    index_html = ""
    if indexed_urls:
        links = "".join([f'<li style="font-size:13px;color:#2980b9;margin:3px 0;">{u}</li>' for u in indexed_urls])
        index_html = f"""
<div style="background:#eafaf1;border:1px solid #a9dfbf;border-radius:8px;padding:14px;margin:10px 0;">
  <strong style="color:#27ae60;">🔍 어제 발행 글 색인 요청 완료 ({len(indexed_urls)}개)</strong>
  <ul style="margin:8px 0;padding-left:18px;">{links}</ul>
</div>"""
    elif indexed_urls is not None:
        index_html = '<div style="background:#f8f9fa;border-radius:8px;padding:10px;margin:10px 0;color:#888;font-size:13px;">🔍 어제 발행 글 없음 (색인 요청 건너뜀)</div>'

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
  {index_html}
  <div style="text-align:center;padding:16px;color:#bbb;font-size:12px;border-top:1px solid #e0e0e0;margin-top:10px;">
    SEO 키워드 자동수집 × WordPress 자동 발행 시스템
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

    # 7일 이내 발행 키워드 로드 (키워드 수집 전에 먼저)
    used_keywords = load_used_wp_keywords()
    print(f"  📋 7일 이내 발행 키워드: {len(used_keywords)}개")

    # SEO 키워드 자동 수집 (한발뉴스 대체)
    top_articles = collect_seo_keywords(used_keywords, max_count=MAX_POSTS)
    n = len(top_articles)
    print(f"\nSEO 키워드 수집: {n}개 (최대 {MAX_POSTS}개 발행)")

    if n == 0:
        print("발행할 키워드 없음. 종료합니다.")
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

        print(f"\n[{idx+1}/{n}] 키워드: {article.get('제목','')}")

        # 중복 체크
        dup, dup_kw = is_duplicate_article(article, used_keywords)
        if dup:
            print(f"  ⏭️ 스킵 (7일 이내 중복 키워드: '{dup_kw}')")
            continue
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

                # ⑥ 발행 키워드 저장 (7일 중복 방지)
                kw_to_save = article.get("키워드후보", [])
                if not kw_to_save:
                    kw_to_save = [article.get("제목", "")]
                save_wp_keywords(kw_to_save)
                used_keywords.update(k.lower() for k in kw_to_save)

                # ⑦ 즉시 발행 글만 색인 요청
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

    # ⑦ 전날 발행 글 색인 요청
    indexed_urls = request_yesterday_indexing()

    # ⑧ 결과 이메일
    print(f"\n{'='*55}")
    print("이메일 발송 중...")
    send_result_email(results, today_str, indexed_urls)

    success = len([r for r in results if r.get("wp_id")])
    print(f"\n🎉 완료! 발행 성공 {success}/{len(results)}개")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
