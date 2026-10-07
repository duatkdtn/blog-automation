# ================================================
# 쇼핑커넥트 자동화 v4.0
# 흐름: 카테고리 → 5개 상품 → Claude 글 작성
#       → 이메일 1통 (네이버 블로그 복붙용)
# ================================================

import os, re, sys, json, random, requests, smtplib
# Windows 콘솔 UTF-8 강제 설정
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timedelta
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

NAVER_CLIENT_ID     = _get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = _get("NAVER_CLIENT_SECRET")
CLAUDE_API_KEY      = _get("CLAUDE_API_KEY")
CLAUDE_MODEL        = _get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GMAIL_ADDRESS       = _get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD  = _get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT     = _get("EMAIL_RECIPIENT", "duatkdtn@gmail.com")
def _refresh_jsessionid(base_cookie):
    """NID_AUT + NID_SES로 브랜드커넥트 접속해서 새 JSESSIONID 자동 발급"""
    try:
        import requests as _req, re as _re
        # NID_AUT, NID_SES, NNB, NAC만 추출 (장기 쿠키)
        keep = ["NID_AUT", "NID_SES", "NNB", "NAC", "NACT", "nid_inf"]
        parts = [p.strip() for p in base_cookie.split(";") if p.strip().split("=")[0].strip() in keep]
        if not parts:
            return base_cookie
        short_cookie = "; ".join(parts)
        r = _req.get(
            "https://brandconnect.naver.com/",
            headers={
                "Cookie": short_cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
            },
            timeout=10,
            allow_redirects=True
        )
        new_cookies = {}
        for sc in r.headers.get("Set-Cookie", "").split(","):
            m = _re.match(r"\s*([^=]+)=([^;]+)", sc.strip())
            if m:
                new_cookies[m.group(1).strip()] = m.group(2).strip()
        # 기존 쿠키에서 JSESSIONID 교체
        existing = {}
        for p in base_cookie.split(";"):
            p = p.strip()
            if "=" in p:
                k, v = p.split("=", 1)
                existing[k.strip()] = v.strip()
        existing.update(new_cookies)
        result = "; ".join(f"{k}={v}" for k, v in existing.items())
        if "JSESSIONID" in new_cookies:
            print(f"   ✅ JSESSIONID 자동 갱신 완료")
        return result
    except Exception as e:
        print(f"   ⚠️ JSESSIONID 갱신 실패: {e}")
        return base_cookie

def _get_naver_cookie_auto():
    """config.py 쿠키 로드 후 JSESSIONID 자동 갱신"""
    base = _get("NAVER_COOKIE", "")
    if not base:
        print("   ⚠️ NAVER_COOKIE 없음 - config.py에 쿠키 입력 필요")
        return ""
    return _refresh_jsessionid(base)

NAVER_COOKIE = _get_naver_cookie_auto()

def refresh_naver_cookie():
    """쿠키 재추출"""
    global NAVER_COOKIE
    NAVER_COOKIE = _get_naver_cookie_auto()
    return bool(NAVER_COOKIE)
NAVER_SPACE_ID      = _get("NAVER_SPACE_ID", "962414636778176")

PUBLISHED_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published_products.txt")
LAST_RUN_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shopping_last_run.txt")
USED_KEYWORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "used_keywords.txt")
NAVER_BLOG_URL = "https://blog.naver.com/janee_item"



# ── 네이버 데이터랩 쇼핑 카테고리 + 세부 키워드 ──
# v6.0: DataLab 실측으로 카테고리 ID 수정 (2026-09-02)
# 실측 결과: 50000007=스포츠/레저, 50000006=식품, 50000003=디지털/가전
#             50000000=패션의류, 50000002=화장품/미용
def _food_keywords():
    """명절 기간엔 선물세트, 나머지엔 일반 식품 키워드 반환"""
    today = datetime.now()
    m, d = today.month, today.day
    # 설날: 1/1 ~ 1/28 (2026 설날 1/29)
    seollal = (m == 1 and d <= 28)
    # 추석: 9/1 ~ 9/21 (2026 추석 9/25, 연휴 9/23~27) ← 9/22 종료
    chuseok = (m == 9 and d <= 21)
    if seollal or chuseok:
        return [
            # 육류
            "한우선물세트", "갈비선물세트", "흑돼지선물세트",
            # 수산물
            "굴비선물세트", "전복선물세트", "새우선물세트", "오징어선물세트", "수산물선물세트",
            # 건강식품
            "홍삼선물세트", "인삼선물세트", "건강즙선물세트", "영양제선물세트",
            # 농산물/전통식품
            "과일선물세트", "꿀선물세트", "버섯선물세트", "한과선물세트",
            "김선물세트", "김치선물세트", "장류선물세트", "참기름선물세트",
            # 가공식품
            "스팸선물세트", "참치선물세트", "식용유선물세트",
            # 음료/기호식품
            "커피선물세트", "차선물세트",
            # 뷰티/생활
            "화장품선물세트",
            # 기타
            "추석선물세트", "건강식품선물세트", "올리브오일선물세트", "와인선물세트",
        ]
    return [
        # 건강식품
        "단백질보충제", "건강즙", "홍삼", "흑마늘즙", "석류즙",
        "유산균", "오메가3", "콜라겐", "비타민C", "마그네슘",
        # 간편식
        "밀키트", "냉동만두", "냉동김밥", "컵밥", "레토르트식품",
        "간편국", "즉석죽", "냉동볶음밥", "냉동피자",
        # 음료/커피
        "커피원두", "캡슐커피", "드립백커피", "콜드브루커피",
        "프로틴음료", "녹즙", "과채주스",
        # 스낵/간식
        "그래놀라", "견과류", "프로틴바", "두유", "냉동과일",
        "다이어트식품", "저칼로리과자", "무설탕젤리",
        # 조미료/소스
        "올리브오일", "참기름", "들기름", "천일염", "유기농설탕",
    ]

CATEGORIES = [
    {"name": "스포츠/레저", "id": "50000007", "keywords": [
        # 골프
        "골프채", "골프백", "골프거리측정기", "골프웨어", "골프화",
        "골프장갑", "골프공", "골프트롤리", "골프우산", "골프카트",
        "파크골프채", "파크골프백", "파크골프공",
        # 캠핑
        "텐트", "캠핑의자", "캠핑버너", "캠핑랜턴", "타프",
        "캠핑테이블", "침낭", "해먹", "캠핑매트", "캠핑코펠",
        "캠핑그릴", "캠핑쿨러", "캠핑조명", "캠핑도끼", "캠핑선풍기",
        # 등산/아웃도어
        "등산화", "등산배낭", "등산스틱", "등산자켓", "트레킹화",
        "아이젠", "헤드랜턴", "등산양말",
        # 홈트/헬스
        "덤벨", "요가매트", "폼롤러", "점핑줄", "밴드운동",
        "실내자전거", "런닝머신", "철봉", "푸쉬업바", "ab롤러",
        # 수상/레저
        "낚시대", "낚시릴", "낚시가방", "수영복", "서핑보드",
        # 자전거
        "전기자전거", "킥보드", "자전거헬멧", "자전거가방",
    ]},
    {"name": "식품", "id": "50000006", "keywords": []},  # _food_keywords()로 동적 처리
    {"name": "디지털/가전", "id": "50000003", "keywords": [
        # 모바일/태블릿
        "갤럭시탭", "아이패드", "갤럭시워치", "애플워치", "애플워치SE",
        "갤럭시버즈", "에어팟", "블루투스이어폰", "블루투스스피커",
        # PC/노트북
        "맥북", "삼성노트북", "LG그램", "게이밍노트북", "태블릿거치대",
        "삼성모니터", "LG모니터", "게이밍모니터", "웹캠", "기계식키보드",
        "무선마우스", "게이밍마우스", "노트북거치대", "SSD", "외장하드",
        # 생활가전
        "다이슨청소기", "로봇청소기", "스팀청소기", "에어랩",
        "삼성냉장고", "LG냉장고", "에어컨", "제습기", "공기청정기",
        "전기밥솥", "에어프라이어", "전자레인지", "식기세척기", "드럼세탁기",
        # 카메라/영상
        "미러리스카메라", "액션캠", "짐벌", "카메라가방", "삼각대",
        # 스마트홈
        "스마트스피커", "스마트전구", "IP카메라", "로봇청소기",
        "무선충전기", "멀티탭", "보조배터리", "차량용충전기",
        # TV/영상
        "OLED TV", "삼성QLED", "빔프로젝터", "사운드바",
    ]},
    {"name": "생활/건강", "id": "50000008", "keywords": [
        # 건강기기
        "안마의자", "마사지건", "혈압계", "체중계", "혈당계",
        "체온계", "족욕기", "안마기", "목마사지기", "눈마사지기",
        # 건강식품
        "유산균", "비타민", "오메가3", "루테인", "콜라겐",
        "마그네슘", "아연", "칼슘", "프로바이오틱스", "밀크씨슬",
        "L카르니틴", "글루타치온", "코엔자임Q10", "스피루리나",
        # 다이어트
        "단백질보충제", "다이어트보조제", "식이섬유", "저칼로리식품",
        # 생활건강
        "공기청정기", "정수기", "가습기", "제습기", "음이온청정기",
        "헤파필터", "살균소독기", "UV살균기",
        # 청소/위생
        "청소기", "로봇청소기", "물걸레청소기", "음식물처리기",
        "의류건조기", "의류관리기", "스팀다리미",
        # 생활용품
        "전기요", "전기장판", "온열패드", "냉온수매트",
        "미용기기", "피부관리기", "LED마스크", "초음파세안기",
        "두피케어", "탈모샴푸", "탈모영양제",
    ]},
    {"name": "가구/인테리어", "id": "50000004", "keywords": [
        # 가구
        "소파", "침대", "매트리스", "식탁", "책상",
        "옷장", "드레스룸", "좌식소파", "책장", "화장대",
        "서랍장", "행거", "신발장", "TV장식장", "사이드테이블",
        # 조명
        "조명", "스탠드조명", "펜던트조명", "LED조명", "무드등",
        "수면등", "취침등", "데스크조명", "스마트조명",
        # 인테리어 소품
        "커튼", "블라인드", "러그", "카펫", "벽시계",
        "아트포스터", "액자", "쿠션", "담요", "이불",
        # 수납
        "수납박스", "수납선반", "수납바구니", "정리함", "옷걸이",
        "진공압축팩", "모듈선반",
        # 생활소품
        "디퓨저", "캔들", "화분", "인테리어화분", "조화",
        "욕실소품", "주방소품", "테이블웨어", "머그컵세트",
        # 침구
        "이불세트", "베개", "메모리폼베개", "라텍스베개", "토퍼",
    ]},
    {"name": "육아/유아동", "id": "50000005", "keywords": [
        # 유모차/이동
        "유모차", "휴대용유모차", "쌍둥이유모차", "카시트", "아기띠",
        "힙시트", "유아자전거", "킥보드유아",
        # 수유/이유식
        "젖병", "분유", "이유식", "아기과자", "유아음료",
        "수유쿠션", "착유기", "젖병소독기",
        # 위생/기저귀
        "기저귀", "물티슈", "아기로션", "아기샴푸", "아기욕조",
        "기저귀가방", "배변훈련",
        # 장난감/놀이
        "레고", "블록장난감", "인형", "보드게임", "퍼즐",
        "아기체육관", "쏘서", "점퍼루", "모빌",
        # 유아동 의류
        "아기옷", "돌복", "유아상하복", "아기신발", "아기양말",
        # 침구/안전
        "아기침대", "유아침구", "범퍼침대", "안전문", "안전게이트",
        # 교육
        "유아영어", "한글공부", "유아태블릿", "어린이책",
    ]},
]

# 식품 카테고리 keywords를 실행 시점에 동적으로 채움
for _c in CATEGORIES:
    if _c["name"] == "식품":
        _c["keywords"] = _food_keywords()
        break


# ── 시즌 키워드 ──────────────────────────────────
SEASON_KEYWORDS = {
    "발렌타인": {
        "months_days": [(2, 1, 2, 14)],
        "keywords": [
            "초콜릿선물", "발렌타인초콜릿", "커플선물", "발렌타인선물",
            "수제초콜릿", "와인선물", "꽃다발", "향수선물", "커플반지",
        ]
    },
    "봄": {
        "months_days": [(3, 1, 5, 31)],
        "keywords": [
            "봄패션", "봄자켓", "봄원피스", "봄신발", "봄야외활동",
            "캠핑용품", "봄나들이", "자전거", "등산화", "봄이불",
            "공기청정기", "황사마스크", "알레르기약", "봄청소용품",
        ]
    },
    "어린이날어버이날": {
        "months_days": [(5, 1, 5, 8)],
        "keywords": [
            "어린이선물", "장난감", "레고선물", "어린이날선물",
            "어버이날선물", "부모님선물", "카네이션", "효도선물",
            "건강식품선물", "안마기선물",
        ]
    },
    "여름": {
        "months_days": [(6, 1, 8, 31)],
        "keywords": [
            "수영복", "래쉬가드", "선크림", "여름샌들", "슬리퍼",
            "휴대용선풍기", "아이스박스", "물놀이용품", "여름이불",
            "냉감패드", "에어컨", "제습기", "여름원피스", "반바지",
        ]
    },
    "핼러윈": {
        "months_days": [(10, 15, 10, 31)],
        "keywords": [
            "핼러윈용품", "핼러윈코스튬", "핼러윈파티용품",
            "핼러윈과자", "핼러윈데코", "공포소품", "마녀의상",
        ]
    },
    "빼빼로데이": {
        "months_days": [(11, 1, 11, 11)],
        "keywords": [
            "빼빼로선물세트", "빼빼로", "과자선물세트", "사탕선물",
            "커플선물", "친구선물", "초콜릿과자",
        ]
    },
    "김장철": {
        "months_days": [(11, 1, 11, 30)],
        "keywords": [
            "김치냉장고", "김장용품", "절임배추", "고춧가루",
            "김장비닐", "김장장갑", "젓갈", "새우젓",
        ]
    },
    "크리스마스": {
        "months_days": [(12, 1, 12, 25)],
        "keywords": [
            "크리스마스선물", "크리스마스트리", "크리스마스데코",
            "산타의상", "크리스마스케이크", "연말선물", "트리장식",
            "크리스마스양말", "루돌프인형",
        ]
    },
    "겨울": {
        "months_days": [(12, 1, 2, 28)],
        "keywords": [
            "패딩", "겨울코트", "목도리", "장갑", "핫팩",
            "전기장판", "전기요", "온열매트", "보온텀블러",
            "겨울부츠", "기모레깅스", "방한용품", "누빔이불",
        ]
    },
    "설날": {
        "months_days": [(1, 1, 1, 28)],
        "keywords": [
            "설날선물세트", "명절선물세트", "한우선물세트",
            "홍삼선물세트", "과일선물세트", "스팸선물세트",
            "참기름선물세트", "설날용품",
        ]
    },
    "추석": {
        "months_days": [(9, 1, 9, 21)],
        "keywords": [
            "추석선물세트", "추석선물", "명절선물세트",
            "굴비선물세트", "전복선물세트", "건강식품선물세트",
            "추석용품", "차례상용품",
        ]
    },
}

def get_current_season():
    """현재 날짜에 맞는 시즌 이름과 키워드 반환 (없으면 None, [])"""
    today = datetime.now()
    m, d = today.month, today.day

    for season_name, info in SEASON_KEYWORDS.items():
        for (sm, sd, em, ed) in info["months_days"]:
            # 연도 걸치는 시즌 처리 (예: 겨울 12~2월)
            if sm <= em:
                if (m == sm and d >= sd) or (sm < m < em) or (m == em and d <= ed):
                    return season_name, info["keywords"]
            else:
                # 연도 넘기는 경우 (12월~2월)
                if (m == sm and d >= sd) or (m > sm) or (m < em) or (m == em and d <= ed):
                    return season_name, info["keywords"]
    return None, []


NAVER_HEADERS = lambda: {
    "X-Naver-Client-Id":     NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    "Content-Type":          "application/json",
}


# ── 1단계: 데이터랩으로 인기 카테고리 찾기 ───────

def get_trending_category():
    """
    네이버 데이터랩 쇼핑인사이트로 최근 1주 가장 많이 검색된 카테고리 반환
    반환: {"name": "디지털/가전", "id": "50000003"} 또는 None
    """
    today = datetime.now()
    end   = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    body = {
        "startDate": start,
        "endDate":   end,
        "timeUnit":  "date",
        "category":  [{"name": c["name"], "param": [c["id"]]} for c in CATEGORIES],
        "device": "", "ages": [], "gender": ""
    }

    try:
        res = requests.post(
            "https://openapi.naver.com/v1/datalab/shopping/categories",
            headers=NAVER_HEADERS(),
            json=body, timeout=15
        )
        res.raise_for_status()
        results = res.json().get("results", [])

        # 각 카테고리의 최근 ratio 평균 계산
        scores = []
        for r in results:
            data = r.get("data", [])
            if not data:
                continue
            avg = sum(d.get("ratio", 0) for d in data) / len(data)
            scores.append({"name": r["title"], "score": avg})

        if not scores:
            print("⚠️ 데이터랩 응답 없음")
            return None

        # 가장 높은 카테고리 선택
        best = max(scores, key=lambda x: x["score"])
        # CATEGORIES에서 id 찾기
        matched = next((c for c in CATEGORIES if c["name"] == best["name"]), None)
        if matched:
            print(f"📊 인기 카테고리: {matched['name']} (ratio: {best['score']:.1f})")
            return matched

        return None

    except Exception as e:
        print(f"⚠️ 데이터랩 API 오류: {e}")
        return None


# ── 2단계: 네이버 쇼핑 API로 상품 가져오기 ──────

def get_trending_keywords_from_datalab(category):
    """
    DataLab 쇼핑인사이트에서 카테고리 인기 검색어 TOP 10 크롤링
    반환: list of keyword strings, 또는 [] (실패 시)
    """
    today = datetime.now()
    end   = (today - timedelta(days=1)).strftime("%Y%m%d")
    start = (today - timedelta(days=7)).strftime("%Y%m%d")

    try:
        _dl_headers = {
            "Referer":          "https://datalab.naver.com/shoppingInsight/sCategory.naver",
            "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept":           "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        if NAVER_COOKIE:
            _dl_headers["Cookie"] = NAVER_COOKIE
        res = requests.post(
            "https://datalab.naver.com/shoppingInsight/getKeywordRank.naver",
            headers=_dl_headers,
            data={
                "cid":       category["id"],
                "timeUnit":  "date",
                "startDate": start,
                "endDate":   end,
                "age":       "",
                "sex":       "",
                "device":    "",
                "topN":      "10",
            },
            timeout=10,
        )
        if res.status_code == 200:
            try:
                data = res.json()
                if isinstance(data, list):
                    data = data[0] if data else {}
                result = data.get("ranks", [])
                keywords = [item.get("keyword", "") for item in result if item.get("keyword")]
                if keywords:
                    return keywords
            except Exception as je:
                print(f"   ℹ️ DataLab JSON 파싱 실패: {je} / 응답: {res.text[:200]}")
    except Exception as e:
        print(f"   ℹ️ DataLab 크롤링 실패: {e}")

    return []


def get_top_product(category, specific_keyword=None):
    """
    Brand Connect API로 상품 검색 → 반환
    specific_keyword: 지정하면 해당 키워드만 사용 (키워드 순환용)
    반환: list of product dict
    """
    if specific_keyword:
        keywords_to_try = [specific_keyword]
    else:
        all_keywords = category.get("keywords", [category["name"]])[:]
        # 7일 이내 사용된 키워드 제외
        recent_keywords = load_used_keywords(days=7)
        filtered = [k for k in all_keywords if k not in recent_keywords]
        if not filtered:
            print(f"   ⚠️ 7일 이내 모든 키워드 사용됨 → 전체 키워드에서 선택")
            filtered = all_keywords
        else:
            print(f"   📌 키워드 {len(all_keywords)}개 중 {len(filtered)}개 사용 가능 (7일 중복 제외)")
        keywords_to_try = filtered
        random.shuffle(keywords_to_try)

    if not NAVER_COOKIE:
        print("   NAVER_COOKIE 없음 - 빈 결과 반환")
        return []

    bc_headers = {
        "Cookie": NAVER_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://brandconnect.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://brandconnect.naver.com",
        "x-space-id": NAVER_SPACE_ID,
    }

    items = []
    for query in keywords_to_try[:3]:  # 최대 3개 키워드 시도
        print(f"   Brand Connect 검색: {query}")
        try:
            res = requests.get(
                "https://gw-brandconnect.naver.com/affiliate/query/affiliate-products/search-by-query",
                headers=bc_headers,
                params={"query": query, "limit": 100},
                timeout=10,
            )
            if res.status_code == 200:
                data = res.json().get("data", [])
                for p in data:
                    name  = p.get("productName", "")
                    price = str(p.get("discountedSalePrice", 0) or p.get("salePrice", 0))
                    link  = p.get("productUrl", "") or p.get("url", "")
                    img   = p.get("representativeProductImageUrl", "") or p.get("imageUrl", "") or p.get("thumbnailUrl", "")
                    pid   = str(p.get("id", "") or p.get("productNo", "") or p.get("productId", ""))
                    rate  = p.get("commissionRate", 0)
                    review = p.get("reviewInfo", {})
                    price_val = int(p.get("discountedSalePrice", 0) or p.get("salePrice", 0) or 0)
                    _min_rate = 5 if __import__('datetime').date.today() <= __import__('datetime').date(2026, 9, 20) else 10
                    if name and price_val >= 30000 and float(rate) >= _min_rate:
                        items.append({
                            "title":          name,
                            "lprice":         price,
                            "link":           link,
                            "image":          img,
                            "productId":      pid,
                            "commissionRate": rate,
                            "reviewCount":    review.get("totalReviewCount", 0),
                            "reviewScore":    review.get("averageReviewScore", 0),
                            "keyword":        query,
                        })
                if items:
                    print(f"   Brand Connect {len(items)}개 수집")
                    break
            elif res.status_code == 401:
                print("   Brand Connect 쿠키 만료")
                break
            elif res.status_code == 403:
                print("   Brand Connect 쿠키 만료 → F12에서 쿠키 갱신 필요")
                break
        except Exception as e:
            print(f"   Brand Connect 오류: {e}")

    return items


# ── 3단계: 중복 체크 ──────────────────────────────

def check_already_ran_today():
    """오늘 이미 실행됐는지 확인"""
    from datetime import date
    try:
        with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
            last = f.read().strip()
        return last == str(date.today())
    except:
        return False

def save_run_today():
    """오늘 실행 기록 저장"""
    from datetime import date
    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        f.write(str(date.today()))

def load_published_ids():
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


def load_used_keywords(days=7):
    """7일 이내 사용된 키워드 목록 반환"""
    if not os.path.exists(USED_KEYWORDS_FILE):
        return set()
    cutoff = datetime.now() - timedelta(days=days)
    used = set()
    with open(USED_KEYWORDS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                keyword = parts[0].strip()
                try:
                    used_date = datetime.strptime(parts[1].strip(), "%Y-%m-%d")
                    if used_date >= cutoff:
                        used.add(keyword)
                except:
                    pass
    return used


def save_used_keyword(keyword):
    """사용된 키워드를 날짜와 함께 저장"""
    today = datetime.now().strftime("%Y-%m-%d")
    with open(USED_KEYWORDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{keyword}|{today}\n")


def cleanup_used_keywords(days=7):
    """7일 지난 키워드 항목 정리"""
    if not os.path.exists(USED_KEYWORDS_FILE):
        return
    cutoff = datetime.now() - timedelta(days=days)
    kept = []
    with open(USED_KEYWORDS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                try:
                    used_date = datetime.strptime(parts[1].strip(), "%Y-%m-%d")
                    if used_date >= cutoff:
                        kept.append(line)
                except:
                    kept.append(line)
    with open(USED_KEYWORDS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + ("\n" if kept else ""))


def save_published_product(product_id, product_name):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(PUBLISHED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{product_id}|{product_name}|{today}\n")
    print(f"✅ 발행 기록 저장: {product_name}")





def find_new_product():
    """
    데이터랩 인기 카테고리 → 쇼핑 검색 → 브랜드커넥트 우선 선택
    반환: (category, product, bc_product) 또는 (None, None, None)
    """
    published_ids = load_published_ids()
    print(f"📋 발행된 상품 수: {len(published_ids)}개")

    # 인기 카테고리 먼저 시도, 실패하면 순서대로
    trending = get_trending_category()
    category_order = ([trending] if trending else []) + \
                     [c for c in CATEGORIES if not trending or c["id"] != trending["id"]]

    for category in category_order:
        print(f"🔍 카테고리 검색: {category['name']}")
        products = get_top_product(category)

        # 미발행 상품만 필터링
        new_products = []
        for product in products:
            pid = str(product.get("productId", ""))
            if pid and pid not in published_ids:
                new_products.append(product)
            else:
                print(f"   └ 이미 발행됨: {product.get('title','')[:20]}")

        if not new_products:
            continue

        print(f"   └ 미발행 상품 {len(new_products)}개 → 브랜드커넥트 검색 중...")

        # 브랜드커넥트 우선 선택
        if NAVER_COOKIE:
            bc_product, bc_info = find_best_brandconnect(new_products)
            if bc_product:
                print(f"✅ 브랜드커넥트 상품 선택: {bc_product['title'][:30]}")
                return category, bc_product, bc_info

        # 브랜드커넥트 없으면 첫 번째 미발행 상품
        product = new_products[0]
        print(f"✅ 일반 상품 선택: {product['title'][:30]}")
        return category, product, None

    print("⚠️ 새 상품 없음")
    return None, None, None


def find_new_products(count=9):
    """
    여러 카테고리에서 미발행 상품 최대 count개 반환
    반환: list of (category, product, bc_product)
    """
    published_ids = load_published_ids()
    print(f"📋 발행된 상품 수: {len(published_ids)}개")

    trending = get_trending_category()
    category_order = ([trending] if trending else []) + \
                     [c for c in CATEGORIES if not trending or c["id"] != trending["id"]]

    results = []
    used_ids = set(published_ids)  # 이번 실행 중 선택된 것도 중복 방지

    # 7일 지난 키워드 기록 정리
    cleanup_used_keywords(days=7)

    for category in category_order:
        if len(results) >= count:
            break

        print(f"\n🔍 [{len(results)+1}/{count}] 카테고리: {category['name']}")
        products = get_top_product(category)

        new_products = []
        for product in products:
            pid = str(product.get("productId", ""))
            if pid and pid not in used_ids:
                new_products.append(product)
            else:
                print(f"   └ 스킵: {product.get('title','')[:20]}")

        if not new_products:
            print("   └ 미발행 상품 없음, 다음 카테고리로")
            continue

        # 브랜드커넥트 우선
        selected_product = None
        selected_bc = None

        if NAVER_COOKIE:
            print(f"   └ 브랜드커넥트 검색 중...")
            bc_product, bc_info = find_best_brandconnect(new_products)
            if bc_product:
                selected_product = bc_product
                selected_bc = bc_info
                pid = str(selected_product.get("productId", ""))
                print(f"   ✅ 브랜드커넥트 선택: {selected_product.get('title','')[:25]}")

        if not selected_product:
            print(f"   ⚠️ 브랜드코넥트 상품 없음 - 카테고리 스킵")
            continue

        used_ids.add(pid)
        # 사용된 키워드 저장 (7일 중복 방지용)
        used_kw = selected_product.get("keyword", "")
        if used_kw:
            save_used_keyword(used_kw)
            print(f"   📝 키워드 기록: {used_kw}")
        results.append((category, selected_product, selected_bc))

    print(f"\n📦 총 {len(results)}개 상품 선택 완료")
    return results


# ── 3.5단계: 브랜드커넥트 상품 검색 ────────────────

def check_brandconnect(product_name):
    """
    브랜드커넥트 내부 API로 상품 검색
    반환: 수수료율 가장 높은 상품 dict 또는 None
    """
    cookie = NAVER_COOKIE
    if not cookie:
        print("   ℹ️ NAVER_COOKIE 없음 - 브랜드커넥트 스킵")
        return None

    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Referer": "https://brandconnect.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://brandconnect.naver.com",
        "x-space-id": NAVER_SPACE_ID,
    }

    try:
        res = requests.get(
            "https://gw-brandconnect.naver.com/affiliate/query/affiliate-products/search-by-query",
            headers=headers,
            params={"query": product_name, "limit": 100},
            timeout=10
        )
        if res.status_code == 401:
            print("   ⚠️ 브랜드커넥트 쿠키 만료 (재로그인 필요)")
            return None
        if res.status_code == 403:
            print("   ℹ️ 브랜드커넥트 접근 불가 (해외 IP 차단) - 스킵")
            return None
        res.raise_for_status()

        data = res.json().get("data", [])
        if not data:
            print(f"   └ 브랜드커넥트 결과 없음")
            return None

        # 가중치 점수로 최적 상품 선택 (수수료 50% + 리뷰수 30% + 별점 20%)
        def bc_score(p):
            rate     = float(p.get("commissionRate", 0))
            review   = p.get("reviewInfo", {})
            cnt      = min(float(review.get("totalReviewCount", 0)), 10000) / 10000
            score_rv = float(review.get("averageReviewScore", 0)) / 5.0
            return rate * 0.5 + cnt * 30 * 0.3 + score_rv * 100 * 0.2

        # 수수료 필터 (추석 시즌 ~9/22: 5%, 이후: 10%)
        from datetime import date as _date
        _min_rate = 5 if _date.today() <= _date(2026, 9, 20) else 10
        high_commission = [p for p in data if float(p.get("commissionRate", 0)) >= _min_rate]
        if not high_commission:
            print(f"   └ 수수료 {_min_rate}% 이상 상품 없음 - 스킵")
            return None
        # 리뷰 1개 이상인 상품 우선 선택, 없으면 수수료 10%+ 전체에서 선택
        reviewed = [p for p in high_commission if p.get("reviewInfo", {}).get("totalReviewCount", 0) > 0]
        pool = reviewed if reviewed else high_commission

        best = max(pool, key=bc_score)
        rate   = float(best.get("commissionRate", 0))
        review = best.get("reviewInfo", {})
        cnt    = review.get("totalReviewCount", 0)
        score  = review.get("averageReviewScore", 0)
        print(f"   └ ✅ 브랜드커넥트 발견: {best.get('productName','')[:30]}")
        print(f"      수수료 {rate}% | 리뷰 {cnt}개 | 별점 {score}")
        return best

    except Exception as e:
        print(f"   ⚠️ 브랜드커넥트 오류: {e}")
        return None


def find_best_brandconnect(products):
    """
    상품 리스트에서 브랜드커넥트에 있는 것 중 수수료율 가장 높은 것 반환
    반환: (product, bc_product) 또는 (None, None)
    """
    best_pair = None
    best_rate = -1

    for product in products:
        name = product.get("title", "")
        bc = check_brandconnect(name)
        if bc:
            rate = float(bc.get("commissionRate", 0))
            if rate > best_rate:
                best_rate = rate
                best_pair = (product, bc)

    return best_pair if best_pair else (None, None)


# ── 4단계: 이미지 수집 (최대 4장) ────────────────

def get_product_images(product):
    """
    상품 이미지 최대 4장 수집
    - 1장: 네이버 쇼핑 API 상품 썸네일
    - 나머지: 네이버 이미지 검색으로 추가 수집
    반환: list of image URLs (최대 4개)
    """
    images = []

    # 1장: 쇼핑 API 썸네일
    thumb = product.get("image", "")
    if thumb:
        images.append(thumb)

    # 나머지: 네이버 이미지 검색
    product_name = product.get("title", "")
    if product_name and len(images) < 4:
        try:
            res = requests.get(
                "https://openapi.naver.com/v1/search/image",
                headers={
                    "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                },
                params={"query": product_name, "display": 8, "sort": "sim", "filter": "large"},
                timeout=10
            )
            res.raise_for_status()
            items = res.json().get("items", [])
            for item in items:
                url = item.get("link", "")
                if url and url not in images:
                    images.append(url)
                if len(images) >= 5:
                    break
        except Exception as e:
            print(f"⚠️ 이미지 검색 오류: {e}")

    print(f"🖼️ 이미지 {len(images)}장 수집")
    return images[:5]


# ── 5단계: Claude로 글 작성 ──────────────────────

def generate_shopping_post(category, product):
    """
    Claude Haiku로 샘플 형식에 맞는 쇼핑 추천 글 작성
    반환: (seo_titles, post_body, hashtags) 또는 (None, None, None)
    """
    if not CLAUDE_API_KEY:
        print("⚠️ Claude API 키 없음")
        return None, None, None

    name  = product.get("title", "")
    brand = product.get("brand", "")
    maker = product.get("maker", "")
    price = product.get("lprice", "")
    cat1  = product.get("category1", category["name"])
    cat2  = product.get("category2", "")

    brand_info = brand or maker or "브랜드 미상"

    prompt = f"""너는 네이버 쇼핑 블로그에 제휴 마케팅 상품 추천 글을 쓰는 전문 작가야.

상품 정보:
- 상품명: {name}
- 브랜드: {brand_info}
- 카테고리: {cat1} > {cat2}

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
이 포스팅은 제휴 마케팅 활동의 일환으로, 판매 발생 시 수수료를 제공받습니다.

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
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY, timeout=120)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()

        # SEO 제목 파싱
        titles_match = re.search(r"---SEO_TITLES_START---(.+?)---SEO_TITLES_END---", raw, re.DOTALL)
        seo_titles = titles_match.group(1).strip() if titles_match else ""

        # 본문 파싱 (BODY_END 없으면 TAGS_START 전까지)
        body_match = re.search(r"---BODY_START---(.+?)---BODY_END---", raw, re.DOTALL)
        if not body_match:
            body_match = re.search(r"---BODY_START---(.+?)---TAGS_START---", raw, re.DOTALL)
        post_body = body_match.group(1).strip() if body_match else ""

        # 본문 클린업: 마크다운·태그 자동 제거
        post_body = re.sub(r'\*\*(.+?)\*\*', r'\1', post_body)          # **볼드** → 볼드
        post_body = re.sub(r'\[소제목\d+\s*:\s*([^\]]+)\]', r'\1', post_body)  # [소제목1: 내용] → 내용만
        post_body = re.sub(r'✅\s*\([^)]+\)', '', post_body)              # ✅ (안내문구) 제거
        post_body = re.sub(r'^#+\s*', '', post_body, flags=re.MULTILINE)    # # 마크다운 제거
        post_body = re.sub(r'\n{3,}', '\n\n', post_body).strip()

        if not post_body:
            print(f"⚠️ 파싱 실패 - raw 앞부분: {raw[:300]}")

        # 해시태그 파싱
        tags_match = re.search(r"---TAGS_START---(.+?)---TAGS_END---", raw, re.DOTALL)
        hashtags = tags_match.group(1).strip() if tags_match else ""

        return seo_titles, post_body, hashtags

    except Exception as e:
        print(f"⚠️ Claude 오류: {e}")
        return None, None, None


# ── 6단계: 이메일 발송 ───────────────────────────

def send_shopping_email_bulk(items, label=""):
    """5개 상품을 하나의 이메일로 발송 (네이버 블로그 복붙용)"""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail 환경변수 없음")
        return
    if not items:
        print("⚠️ 발송할 상품 없음")
        return

    kst       = datetime.utcnow() + timedelta(hours=9)
    today_str = kst.strftime("%Y년 %m월 %d일")
    now_str   = kst.strftime("%Y-%m-%d %H:%M")
    colors    = ["#3F51B5", "#7B1FA2", "#00796B", "#E65100", "#C62828", "#1565C0", "#558B2F", "#6A1B9A", "#AD1457"]

    cards_html = ""
    for i, item in enumerate(items):
        cat          = item["category"]
        product      = item["product"]
        bc_product   = item.get("bc_product")
        images       = item.get("images", [])
        seo_titles   = item.get("seo_titles", "")
        post_body    = item.get("post_body", "")
        hashtags     = item.get("hashtags", "")
        pub_time_str = item.get("pub_time_str", f"{6 + i*3:02d}:00")

        color = colors[i % len(colors)]
        num   = i + 1
        name  = product.get("title", "")
        price = product.get("lprice", "")
        try:
            price_fmt = f"{int(price):,}원" if price else "가격 미정"
        except Exception:
            price_fmt = price or "가격 미정"

        post_body_html = "".join(f"<div style='margin:0 0 12px 0'>{line}</div>" for line in post_body.split("\n") if line.strip())
        title_lines = [l.strip() for l in seo_titles.strip().split("\n") if l.strip()]
        titles_html = ""
        for j, line in enumerate(title_lines[:5]):
            clean = re.sub(r"^[1-5][.)\s]+", "", line).strip()
            titles_html += f'<div style="margin:4px 0;padding:5px 10px;background:#f8f8f8;border-radius:4px;font-size:13px">{j+1}. {clean}</div>'

        img_parts = []
        for idx, img_url in enumerate(images[:5], 1):
            img_parts.append(
                f'<div style="width:calc(50% - 4px);display:inline-block;vertical-align:top;margin-bottom:4px;text-align:center">'
                f'<a href="{img_url}" target="_blank" style="display:block">'
                f'<img src="{img_url}" style="width:100%;max-height:130px;object-fit:cover;border-radius:6px;display:block" alt="상품이미지{idx}">'
                f'</a>'
                f'<a href="{img_url}" target="_blank" download style="font-size:11px;color:#2980b9;text-decoration:none;display:block;margin-top:2px">⬇ 이미지{idx} 저장</a>'
                f'</div>'
            )
        img_html = f'<div style="margin:8px 0;display:flex;flex-wrap:wrap;gap:4px">{" ".join(img_parts)}</div>' if img_parts else ""

        cards_html += f"""
<div style="border-left:4px solid {color};background:#fff;margin:14px 0;overflow:hidden;border:1px solid #e0e0e0;border-left:4px solid {color}">
  <div style="background:{color};color:white;padding:10px 16px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <span style="background:rgba(255,255,255,0.2);padding:2px 10px;border-radius:12px;font-weight:bold;font-size:13px">{num}번</span>
      &nbsp;<strong style="font-size:14px">{name[:42]}</strong>
    </div>
    <div style="font-size:12px;opacity:0.85;white-space:nowrap">📅 {pub_time_str} 발행</div>
  </div>
  <div style="padding:12px 16px">
    {img_html}
    <div style="font-size:12px;color:#777;margin-bottom:8px">카테고리: {cat['name']} | 최저가: {price_fmt}</div>
    <div style="margin:10px 0">
      <div style="font-size:12px;font-weight:bold;color:#333;margin-bottom:5px">📌 SEO 제목 (하나 선택)</div>
      {titles_html}
    </div>
    <details style="margin-top:10px">
      <summary style="cursor:pointer;font-size:13px;color:{color};font-weight:bold;padding:4px 0">✍️ 본문 펼치기 (복붙용)</summary>
      <div style="background:#fafafa;border:1px solid #eee;padding:12px;border-radius:4px;margin-top:8px;font-size:15px;line-height:1.9">{post_body_html}</div>
      <div style="margin-top:10px">
        <div style="font-size:12px;color:#555;font-weight:bold;margin-bottom:4px">📋 네이버 복붙용 (클릭 후 Ctrl+A → Ctrl+C → 네이버에 붙여넣기)</div>
        <textarea onclick="this.select()" readonly style="width:100%;height:220px;font-size:14px;line-height:1.9;font-family:맑은고딕,sans-serif;border:2px solid {color};border-radius:4px;padding:10px;box-sizing:border-box;resize:vertical;background:#fff">{post_body}

{hashtags}</textarea>
      </div>
    </details>
  </div>
</div>
"""

    email_html = f"""<html><body style="font-family:맑은고딕,sans-serif;max-width:680px;margin:0 auto;padding:20px;background:#f0f2f5">

<div style="background:#1a237e;color:white;padding:18px 20px;border-radius:10px;margin-bottom:14px;text-align:center">
  <div style="font-size:12px;opacity:0.7;margin-bottom:4px">🛒 쇼핑 자동화 · 네이버 블로그 전용</div>
  <div style="font-size:20px;font-weight:bold">{today_str} · 총 {len(items)}개 상품</div>
  <div style="font-size:12px;opacity:0.65;margin-top:4px">브랜드커넥트 링크를 [쇼핑링크] 자리에 직접 삽입하세요</div>
</div>

<div style="background:#fff;border-radius:8px;padding:12px 16px;margin-bottom:14px;font-size:13px;border:1px solid #ddd">
  <strong>📋 사용 방법</strong><br>
  1️⃣ SEO 제목 1개 선택 &nbsp; 2️⃣ 본문 펼쳐서 복붙 &nbsp; 3️⃣ [쇼핑링크] 자리에 브랜드커넥트 링크 교체 후 발행<br>
  <span style="color:#1a237e;font-size:12px">⏰ 권장 시간: 06:00 / 09:00 / 12:00 / 15:00 / 18:00</span>
</div>

{cards_html}

<p style="text-align:center;font-size:11px;color:#aaa;margin-top:20px">쇼핑 자동화 v4 · {now_str}</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    label_str = f" · {label}" if label else ""
    msg["Subject"] = f"[쇼핑발행] {today_str} · {len(items)}개 상품{label_str}"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())

    print(f"✅ 이메일 발송 완료 ({len(items)}개 상품) → {EMAIL_RECIPIENT}")



# ── 메인 ──────────────────────────────────────────

def run_shopping_task(category_ids=None, count=5, send_email_flag=True,
                      log_fn=print, force=False, label=""):
    """
    GUI / 자동실행 모두에서 호출 가능한 핵심 함수
    category_ids : None이면 전체, 리스트면 해당 id만 사용
    count        : 상품 개수 (1~10)
    send_email_flag : False면 이메일 발송 생략
    log_fn       : GUI 로그창 콜백 (기본=print)
    force        : True면 오늘 이미 실행됐어도 강제 실행
    반환: {"success": bool, "count": int, "datalab_used": bool}
    """
    from datetime import datetime as _dt, timezone
    _tz = timezone(timedelta(hours=9))

    if not force and check_already_ran_today():
        log_fn("⏭️  오늘 이미 실행됨. 건너뜀 (강제실행: force=True)")
        return {"success": False, "count": 0, "datalab_used": False, "skipped": True}

    log_fn("=" * 50)
    log_fn(f"🛒 쇼핑AI 시작  [{_dt.now(_tz).strftime('%H:%M')}]")
    log_fn("=" * 50)

    # 카테고리 필터
    cats = CATEGORIES
    if category_ids:
        cats = [c for c in CATEGORIES if c["id"] in category_ids]
    if not cats:
        cats = CATEGORIES

    # DataLab 상태 추적
    datalab_used = False
    _orig_datalab = get_trending_keywords_from_datalab

    def _tracked_datalab(cat):
        nonlocal datalab_used
        result = _orig_datalab(cat)
        if result:
            datalab_used = True
        return result

    # 임시로 패치
    import shopping_automation as _self
    _self.get_trending_keywords_from_datalab = _tracked_datalab

    # 상품 선택 (카테고리 필터 적용)
    selected = []
    selected_ids = set()  # 이미 선택된 상품 ID 추적

    def bc_score(p):
        rate  = float(p.get("commissionRate", 0))
        cnt   = min(float(p.get("reviewCount", 0)), 10000) / 10000
        score = float(p.get("reviewScore", 0)) / 5.0
        return rate * 0.5 + cnt * 30 * 0.3 + score * 100 * 0.2

    # 키워드 순환: 카테고리 키워드를 순서대로 1개씩 사용 (다양성 보장)
    # 카테고리가 1개이고 키워드가 많은 경우(식품 등) 키워드마다 1개씩 배정
    published = load_published_ids()

    # ── 시즌 상품 1개 먼저 확보 ──────────────────────
    season_name, season_kws = get_current_season()
    if season_name and season_kws:
        log_fn(f"🎄 현재 시즌: {season_name} → 시즌 상품 1개 먼저 확보")
        season_cat = {"name": f"시즌({season_name})", "id": "50000006", "keywords": season_kws}
        random.shuffle(season_kws)
        for skw in season_kws[:5]:
            s_products = get_top_product(season_cat, specific_keyword=skw)
            if not s_products:
                continue
            s_new = [p for p in s_products
                     if str(p.get("productId","")) not in published
                     and str(p.get("productId","")) not in selected_ids]
            if not s_new:
                continue
            s_best = max(s_new, key=bc_score)
            pid = str(s_best.get("productId",""))
            selected_ids.add(pid)
            selected.append((season_cat, s_best, s_best))
            log_fn(f"   ✅ 시즌 상품 확보: {s_best.get('title','')[:30]}")
            break
        else:
            log_fn(f"   ⚠️ 시즌 상품 없음 - 일반 상품으로 대체")

    # 키워드 풀 구성: 카테고리 × 키워드 순환
    # 7일 이내 사용된 키워드 먼저 로드
    recent_kws = load_used_keywords(days=7)
    cleanup_used_keywords(days=7)
    if recent_kws:
        log_fn(f"🚫 7일 이내 사용 키워드 {len(recent_kws)}개 제외")

    # 카테고리별 키워드 라운드로빈 배치 (같은 카테고리 중복 방지)
    cat_kw_lists = []
    for cat in cats:
        all_kws = cat.get("keywords", [cat["name"]])[:]
        # 7일 이내 사용 키워드 제외
        kws = [k for k in all_kws if k not in recent_kws]
        if not kws:
            kws = all_kws  # 모두 사용됐으면 전체에서 선택
        random.shuffle(kws)
        cat_kw_lists.append([(cat, kw) for kw in kws])

    # 라운드로빈: cat1_kw1, cat2_kw1, cat3_kw1, ..., cat1_kw2, cat2_kw2, ...
    keyword_pool = []
    max_len = max((len(lst) for lst in cat_kw_lists), default=1)
    for i in range(max_len):
        for lst in cat_kw_lists:
            if i < len(lst):
                keyword_pool.append(lst[i])

    # count * 5 미만이면 반복 보충
    while len(keyword_pool) < count * 5:
        keyword_pool += keyword_pool

    attempt = 0
    kw_idx = 0
    while len(selected) < count and attempt < count * 5 and kw_idx < len(keyword_pool):
        cat, kw = keyword_pool[kw_idx]
        kw_idx += 1
        attempt += 1

        products = get_top_product(cat, specific_keyword=kw)
        if not products:
            continue
        new_products = [
            p for p in products
            if str(p.get("productId","")) not in published
            and str(p.get("productId","")) not in selected_ids
        ]
        if not new_products:
            continue

        selected_product = max(new_products, key=bc_score)
        pid = str(selected_product.get("productId",""))
        selected_ids.add(pid)
        selected_bc = selected_product
        # 사용된 키워드 저장 (7일 중복 방지)
        save_used_keyword(kw)
        selected.append((cat, selected_product, selected_bc))

    if not selected:
        log_fn("❌ 발행할 상품 없음.")
        return {"success": False, "count": 0, "datalab_used": datalab_used}

    email_items = []
    pub_times = ["06:00","09:00","12:00","15:00","18:00"]

    for i, (category, product, bc_product) in enumerate(selected):
        log_fn(f"\n[{i+1}/{len(selected)}] {product.get('title','')[:40]}")
        product_id   = str(product.get("productId",""))
        product_name = product.get("title","")

        # 선택 즉시 발행 기록 저장 (중복 방지 - 중간에 끊겨도 재선택 안 됨)
        if product_id:
            save_published_product(product_id, product_name)

        log_fn("  🖼️ 이미지 수집 중...")
        images = get_product_images(product)

        log_fn("  ✍️ Claude 글 작성 중...")
        seo_titles, post_body, hashtags = generate_shopping_post(category, product)
        if not post_body:
            log_fn(f"  ⚠️ 글 작성 실패, 스킵")
            continue

        pub_time_str = pub_times[i] if i < len(pub_times) else f"{6+i*2:02d}:00"
        email_items.append({
            "category": category, "product": product, "bc_product": bc_product,
            "images": images, "seo_titles": seo_titles, "post_body": post_body,
            "hashtags": hashtags, "pub_time_str": pub_time_str,
            "product_id": product_id, "product_name": product_name,
        })

    if email_items and send_email_flag:
        log_fn(f"\n📧 이메일 발송 중... ({len(email_items)}개 상품)")
        send_shopping_email_bulk(email_items, label=label)
        save_run_today()
        log_fn(f"✅ 완료! {len(email_items)}개 상품 이메일 발송")
    elif email_items:
        log_fn(f"\n✅ 완료! {len(email_items)}개 상품 (이메일 발송 OFF)")
    else:
        log_fn("❌ 처리된 상품 없음.")

    datalab_status = "DataLab ✅" if datalab_used else "fallback ⚠️"
    log_fn(f"📊 키워드 소스: {datalab_status}")

    return {"success": bool(email_items), "count": len(email_items),
            "datalab_used": datalab_used}


CHUSEOK_CATEGORIES = [
    {"name": "추석선물", "id": "50000006", "keywords": [
        "추석선물세트", "추석선물", "명절선물세트", "명절선물",
        "한우선물세트", "홍삼선물세트", "과일선물세트", "굴비선물세트",
        "전복선물세트", "건강식품선물세트", "참기름선물세트", "버섯선물세트",
        "햄선물세트", "스팸선물세트", "올리브유선물세트", "견과류선물세트",
        "사과선물세트", "배선물세트", "샴푸선물세트", "화장품선물세트",
        "추석용품", "차례상용품", "전통주선물", "꿀선물세트",
        "잡곡선물세트", "김선물세트", "참치선물세트", "커피선물세트",
        "녹차선물세트", "수건선물세트", "양말선물세트", "속옷선물세트",
    ]},
]

def main():
    from datetime import date
    # 오늘 이미 실행됐는지 확인
    if check_already_ran_today():
        print("⏭️  오늘 이미 실행됨. 건너뜀 (강제실행: force=True)")
        return

    # 추석 기간(~9월 22일)이면 추석 카테고리로 교체
    today = date.today()
    if today <= date(2026, 9, 20):
        print("🎑 추석 시즌 - 추석/명절 선물 키워드로 실행")
        global CATEGORIES
        _orig_categories = CATEGORIES
        CATEGORIES = CHUSEOK_CATEGORIES
    else:
        _orig_categories = None

    try:
        # 블로그1: 8개 수집 → 메일 발송
        print("\n" + "="*50)
        print("📧 [블로그1] 상품 수집 및 메일 발송...")
        result1 = run_shopping_task(count=8, send_email_flag=True, force=True, label="블로그1")

        # 블로그2: 8개 수집 → 메일 발송 (블로그1 발행 상품 자동 제외)
        print("\n" + "="*50)
        print("📧 [블로그2] 상품 수집 및 메일 발송...")
        result2 = run_shopping_task(count=8, send_email_flag=True, force=True, label="블로그2")
    finally:
        if _orig_categories is not None:
            CATEGORIES = _orig_categories

    save_run_today()
    print(f"\n✅ 완료! 블로그1: {result1.get('count',0)}개 / 블로그2: {result2.get('count',0)}개")

if __name__ == "__main__":
    main()
