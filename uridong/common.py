# -*- coding: utf-8 -*-
"""공통 설정·도구. 키·비밀번호는 환경변수(Secrets)에서만 읽는다. 코드에 쓰지 않는다."""
import os, json, re, datetime
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
KST = ZoneInfo("Asia/Seoul")

WP_URL = os.environ.get("WP_URL", "https://uridongneyoyangwon.com").rstrip("/")
WP_USER = os.environ.get("URI_WP_USER", "")
WP_APP_PASSWORD = os.environ.get("URI_WP_APP_PASSWORD", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "duatkdtn01@gmail.com")
# 기존 쟈늬 워크플로의 CLAUDE_MODEL(공유 Secret)은 쓰지 않는다.
MODEL = os.environ.get("URI_MODEL", "claude-haiku-4-5-20251001")
POSTS_PER_RUN = int(os.environ.get("URI_POSTS_PER_RUN", "4"))
INTERVAL_HOURS = int(os.environ.get("URI_INTERVAL_HOURS", "3"))
DRY_RUN = os.environ.get("URI_DRY_RUN", "0") == "1"   # 1이면 워드프레스에 쓰지 않고 파일로만 저장

CATEGORIES = {  # 실제 확인된 카테고리 ID (2026-10-13)
    "nursing-home-cost": 3, "care-grade": 4, "subsidy": 5, "nursing-home-guide": 6,
    "compare": 7, "senior-welfare": 8, "monthly-report": 9,
}
CALC = {
    "copayment": "https://uridongneyoyangwon.com/calculator/copayment/",
    "care-grade": "https://uridongneyoyangwon.com/calculator/care-grade/",
}
ALLOWED_DOMAINS = [
    "longtermcare.or.kr", "nhis.or.kr", "mohw.go.kr", "bokjiro.go.kr", "hira.or.kr",
    "law.go.kr", "gov.kr", "nid.or.kr", "data.go.kr", "kosis.kr", "kostat.go.kr",
]
# 출처 박스에 쓸 수 있는 기관 이름(글의 근거로 쓴 것만 AI가 고른다)
AGENCIES = [
    "국민건강보험공단", "건강보험심사평가원", "보건복지부 고시", "법제처 국가법령정보센터",
    "중앙치매센터", "치매안심센터 안내", "복지로", "정부24", "통계청",
]
HOT = {  # 기관별 대표 공식 주소(외부 버튼 후보)
    "longtermcare": ("🔗 국민건강보험공단 장기요양 바로가기", "https://www.longtermcare.or.kr"),
    "bokjiro": ("🔗 복지로 서비스 신청 바로가기", "https://www.bokjiro.go.kr"),
    "law": ("🔗 국가법령정보센터 바로가기", "https://www.law.go.kr"),
    "nid": ("🔗 중앙치매센터 바로가기", "https://www.nid.or.kr"),
    "nhis": ("🔗 국민건강보험공단 바로가기", "https://www.nhis.or.kr"),
}

def now_kst():
    return datetime.datetime.now(KST)

def today_label(dt=None):
    dt = dt or now_kst()
    return f"{dt.year}년 {dt.month:02d}월"

def load_json(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def save_json(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

def strip_html(h):
    from bs4 import BeautifulSoup
    return BeautifulSoup(h, "html.parser").get_text(" ", strip=True)

def log(*a):
    print(*a, flush=True)
