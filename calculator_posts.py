# ================================================
# 계산기 전용 포스팅 자동발행 스크립트
# GitHub Actions에서 하루 1개씩 자동 발행
# ================================================

import os, json, pickle, urllib.request, urllib.error, sys, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    def _get(key, default=None):
        return os.environ.get(key) or getattr(config, key, default)
except Exception:
    def _get(key, default=None):
        return os.environ.get(key, default)

def restore_token():
    """GitHub Actions: GOOGLE_TOKEN 환경변수로 token.pickle 복원"""
    import base64
    token_b64 = os.environ.get("GOOGLE_TOKEN")
    if token_b64:
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.pickle")
        padding = 4 - len(token_b64) % 4
        if padding != 4:
            token_b64 += "=" * padding
        with open(token_path, "wb") as f:
            f.write(base64.b64decode(token_b64))


GMAIL_ADDRESS    = _get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = _get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT  = _get("EMAIL_RECIPIENT", "duatkdtn@gmail.com")
BLOG_ID          = "7703234808905245526"

# 발행 순서대로 10개 계산기 정의
CALCULATOR_POSTS = [
    {
        "order": 1,
        "title": "퇴직금 계산기 2026 – 내 퇴직금 얼마인지 바로 계산해보세요",
        "calc_title": "퇴직금 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page_11.html",
        "keywords": ["퇴직금 계산기", "퇴직금 계산 방법", "퇴직금 얼마"],
        "intro": """퇴직금은 1년 이상 근무한 직장인이라면 누구나 받을 수 있는 중요한 돈입니다.
하지만 실제로 내 퇴직금이 얼마인지 정확히 아는 사람은 많지 않아요.
계산 공식이 복잡하게 느껴지기 때문이죠. 아래 퇴직금 계산기를 이용하면
근무기간과 평균 임금만 입력하면 바로 예상 퇴직금을 확인할 수 있습니다.

<b>퇴직금 계산 공식</b>
퇴직금 = 1일 평균임금 × 30일 × (재직일수 ÷ 365)

평균임금은 퇴직 전 3개월간 받은 총 임금을 그 기간의 총 날수로 나눈 금액이에요.
아래 계산기에 숫자만 입력하면 자동으로 계산됩니다.""",
        "tips": """<b>퇴직금 관련 꼭 알아둘 점</b>
• 퇴직금은 퇴직일로부터 14일 이내에 지급해야 합니다
• 1년 미만 근무자는 퇴직금이 지급되지 않습니다
• 연봉에 퇴직금이 포함된 경우(포괄산정) 별도 확인이 필요합니다
• 퇴직금을 못 받았다면 고용노동부 신고가 가능합니다""",
        "hashtags": ["퇴직금계산기", "퇴직금계산", "퇴직금", "직장인", "퇴직"]
    },
    {
        "order": 2,
        "title": "실업급여 계산기 2026 – 나는 얼마나 받을 수 있을까?",
        "calc_title": "실업급여 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page_91.html",
        "keywords": ["실업급여 계산기", "실업급여 금액", "실업급여 얼마"],
        "intro": """갑작스러운 실직, 혹은 계획된 퇴직 후 실업급여를 받을 수 있는지 궁금하신가요?
실업급여는 고용보험에 가입되어 있던 직장인이 비자발적으로 퇴직했을 때
일정 기간 동안 받을 수 있는 생활 안정 지원금입니다.

<b>실업급여 수급 조건</b>
• 퇴직 전 18개월 중 고용보험 가입 기간이 180일 이상
• 비자발적 퇴직 (권고사직, 계약만료, 회사 폐업 등)
• 적극적으로 재취업 활동을 할 의사와 능력이 있을 것

아래 계산기에 입력하면 예상 수령액과 기간을 바로 확인할 수 있습니다.""",
        "tips": """<b>실업급여 신청 방법</b>
• 퇴직 후 빠를수록 좋아요 (수급 가능 기간이 줄어들 수 있음)
• 고용보험 홈페이지(ei.go.kr) 또는 워크넷에서 온라인 신청 가능
• 거주지 관할 고용센터 방문 신청도 가능합니다
• 수급 기간 중 주 1회 이상 구직활동 실적 제출 필요""",
        "hashtags": ["실업급여계산기", "실업급여", "실업급여계산", "고용보험", "퇴직후지원금"]
    },
    {
        "order": 3,
        "title": "취득세 계산기 2026 – 부동산 살 때 세금 얼마나 낼까?",
        "calc_title": "취득세 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page_758.html",
        "keywords": ["취득세 계산기", "취득세 얼마", "부동산 취득세"],
        "intro": """아파트나 주택을 구입할 때 집값 외에 꼭 챙겨야 하는 게 바로 취득세입니다.
취득세는 부동산을 취득할 때 내야 하는 세금으로, 집값의 1~12%까지
보유 주택 수와 가격에 따라 크게 달라집니다.

<b>2026년 취득세율 기준</b>
• 1주택자 (6억 이하): 1%
• 1주택자 (6억~9억): 1~3% (비례 적용)
• 1주택자 (9억 초과): 3%
• 2주택자: 8%
• 3주택자 이상: 12%

아래 계산기에 집값과 주택 보유 수를 입력하면 예상 취득세를 바로 확인할 수 있습니다.""",
        "tips": """<b>취득세 절세 팁</b>
• 생애최초 주택 구입 시 200만 원 한도로 취득세 감면 혜택 있음
• 신혼부부는 추가 감면 혜택 확인 필수
• 취득세는 취득일로부터 60일 이내에 신고·납부해야 합니다
• 미납 시 가산세(20%) 부과되니 주의하세요""",
        "hashtags": ["취득세계산기", "취득세", "부동산세금", "아파트취득세", "주택취득세"]
    },
    {
        "order": 4,
        "title": "BMI 계산기 2026 – 내 체중, 정상 범위인지 바로 확인",
        "calc_title": "BMI 계산기",
        "calc_url": "https://www.hijanee.com/p/bmi.html",
        "keywords": ["BMI 계산기", "체질량지수 계산", "비만도 계산기"],
        "intro": """BMI(체질량지수)는 자신의 체중이 건강한 범위에 있는지 빠르게 확인하는 방법이에요.
키와 몸무게만 입력하면 바로 계산됩니다.

<b>BMI 판정 기준 (한국 기준)</b>
• 18.5 미만: 저체중
• 18.5 ~ 22.9: 정상
• 23.0 ~ 24.9: 과체중
• 25.0 ~ 29.9: 비만
• 30 이상: 고도비만

BMI는 참고 지표이며, 근육량이 많은 경우 실제 체지방과 차이가 날 수 있습니다.
아래 계산기에 키와 몸무게를 입력해보세요.""",
        "tips": """<b>건강 체중 유지 팁</b>
• BMI 정상 범위 유지 시 당뇨·고혈압·심혈관 질환 위험 감소
• 주 150분 이상 중강도 유산소 운동 권장
• 과도한 다이어트보다 꾸준한 습관이 중요합니다
• 체성분 검사를 통한 근육량·체지방률 확인도 권장""",
        "hashtags": ["BMI계산기", "체질량지수", "비만도계산기", "건강체중", "체중관리"]
    },
    {
        "order": 5,
        "title": "국민연금 수령액 계산기 2026 – 내가 받을 연금 미리 확인하기",
        "calc_title": "국민연금 예상수령액 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page_15.html",
        "keywords": ["국민연금 수령액 계산기", "국민연금 얼마", "연금 예상액"],
        "intro": """노후 준비에서 가장 기본이 되는 국민연금, 내가 얼마나 받을 수 있는지 아시나요?
가입 기간과 소득에 따라 수령액이 크게 달라지기 때문에
미리 확인하고 대비하는 것이 중요합니다.

<b>국민연금 수령액 계산 핵심 요소</b>
• 가입 기간 (길수록 많이 받음)
• 소득 수준 (납부한 보험료 기준)
• 수령 시작 나이 (일찍 받으면 감액, 늦추면 증액)

아래 계산기에 가입 기간과 월 소득을 입력하면 예상 수령액을 확인할 수 있습니다.""",
        "tips": """<b>국민연금 수령액 늘리는 방법</b>
• 임의가입: 전업주부, 학생도 자발적으로 가입 가능
• 추납제도: 과거 납부 못한 기간을 나중에 납부 가능
• 연기연금: 수령을 1년 늦출 때마다 7.2% 증액
• 조기수령: 최대 5년 일찍 받되 최대 30% 감액""",
        "hashtags": ["국민연금계산기", "국민연금수령액", "노후준비", "연금계산", "국민연금"]
    },
    {
        "order": 6,
        "title": "만나이 계산기 2026 – 내 만 나이 바로 확인하는 법",
        "calc_title": "만나이 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page_12.html",
        "keywords": ["만나이 계산기", "만 나이 계산", "나이 계산기"],
        "intro": """2023년부터 한국도 공식적으로 만 나이를 사용하게 됐습니다.
법적·행정적 나이 기준이 모두 만 나이로 통일됐는데, 아직 헷갈리시는 분들이 많아요.

<b>만 나이 계산법</b>
• 올해 생일이 지났으면: 올해 연도 - 태어난 연도
• 올해 생일이 아직 안 지났으면: 올해 연도 - 태어난 연도 - 1

예를 들어 1980년 12월생이라면
2026년 7월 기준 만 나이 = 2026 - 1980 - 1 = 만 45세

아래 계산기에 생년월일을 입력하면 정확한 만 나이를 바로 확인할 수 있습니다.""",
        "tips": """<b>만 나이 관련 주의사항</b>
• 의료·법률·계약서 등에서 모두 만 나이 적용
• 주민등록증 나이, 학교 입학 기준 등도 만 나이 기준
• 병역의무, 선거권 등도 만 나이 적용
• 취업 연령 제한도 만 나이 기준으로 확인하세요""",
        "hashtags": ["만나이계산기", "만나이", "나이계산기", "만나이계산", "한국나이"]
    },
    {
        "order": 7,
        "title": "평수 계산기 2026 – 평수와 제곱미터(㎡) 바로 변환하기",
        "calc_title": "평수 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page_92.html",
        "keywords": ["평수 계산기", "평수 변환", "평 제곱미터 변환"],
        "intro": """부동산 매물을 볼 때 '33평', '84㎡' 이런 숫자가 헷갈리시죠?
평수와 제곱미터는 다른 단위이기 때문에 서로 환산하는 법을 알아두면 편리합니다.

<b>평수 ↔ 제곱미터 변환 공식</b>
• 1평 = 약 3.3058㎡
• 1㎡ = 약 0.3025평

예시:
• 25평 = 82.6㎡ (약 83㎡)
• 33평 = 109㎡
• 84㎡ = 약 25.4평

직접 계산하기 어렵다면 아래 계산기를 이용해보세요.""",
        "tips": """<b>부동산에서 평수 관련 꼭 알 것</b>
• 아파트 분양면적 = 전용면적 + 공용면적 (실거주 공간은 전용면적)
• 전용면적 84㎡ = 약 25평 (실제 사용 가능 공간)
• 공급면적 = 전용 + 주거공용 (복도, 계단 등 포함)
• 계약서는 반드시 ㎡ 기준으로 확인하세요""",
        "hashtags": ["평수계산기", "평수변환", "제곱미터변환", "부동산평수", "아파트평수"]
    },
    {
        "order": 8,
        "title": "연봉 실수령액 계산기 2026 – 세후 월급 얼마나 받을까?",
        "calc_title": "연봉 실수령액 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page.html",
        "keywords": ["연봉 실수령액 계산기", "세후 월급 계산", "연봉 실수령"],
        "intro": """연봉 협상할 때 '연봉 5000만 원'이면 월급이 얼마나 들어올까요?
세금과 4대보험을 떼고 나면 생각보다 훨씬 적을 수 있어요.

<b>연봉에서 공제되는 항목</b>
• 국민연금: 4.5%
• 건강보험: 3.545%
• 장기요양보험: 건강보험의 12.95%
• 고용보험: 0.9%
• 소득세 + 지방소득세: 과세표준에 따라 다름

공제 후 실수령액은 연봉의 약 75~85% 수준이에요.
아래 계산기에 연봉을 입력하면 세후 실수령액을 바로 확인할 수 있습니다.""",
        "tips": """<b>실수령액 관련 알아두면 좋은 것</b>
• 부양가족 수에 따라 소득세 공제 금액이 달라집니다
• 비과세 항목(식대, 차량유지비 등)이 있으면 실수령액이 올라갑니다
• 연말정산으로 납부한 세금 일부를 돌려받을 수 있어요
• 연봉 외 상여금·인센티브는 별도 과세됩니다""",
        "hashtags": ["연봉실수령액", "세후월급계산기", "연봉계산기", "실수령액계산", "월급계산기"]
    },
    {
        "order": 9,
        "title": "4대보험 계산기 2026 – 직장인 4대보험료 얼마나 낼까?",
        "calc_title": "4대보험 계산기",
        "calc_url": "https://www.hijanee.com/p/4.html",
        "keywords": ["4대보험 계산기", "4대보험료 계산", "4대보험 얼마"],
        "intro": """직장인이라면 매달 급여에서 4대보험료가 공제됩니다.
국민연금, 건강보험, 고용보험, 산재보험이 4대보험인데
정확히 얼마가 빠져나가는지 알고 계신가요?

<b>2026년 4대보험 요율 (근로자 부담분)</b>
• 국민연금: 4.5% (회사 4.5% 추가 부담)
• 건강보험: 3.545% (회사 3.545% 추가 부담)
• 장기요양보험: 건강보험료의 12.95%
• 고용보험: 0.9% (회사 1.15% 추가 부담)
• 산재보험: 전액 회사 부담 (근로자 부담 없음)

아래 계산기에 월급을 입력하면 4대보험료를 바로 계산할 수 있습니다.""",
        "tips": """<b>4대보험 관련 알아두면 좋은 것</b>
• 두루누리 지원사업: 소규모 사업장 저임금 근로자 4대보험료 일부 지원
• 보험료는 매년 요율이 변동되니 최신 요율 확인 필요
• 프리랜서·개인사업자는 지역가입자로 납부 (전액 본인 부담)
• 육아휴직 중에도 4대보험 가입 유지됩니다""",
        "hashtags": ["4대보험계산기", "4대보험료", "국민연금계산기", "건강보험계산기", "직장인보험"]
    },
    {
        "order": 10,
        "title": "근로장려금 계산기 2026 – 내가 받을 수 있는 금액은?",
        "calc_title": "근로장려금 계산기",
        "calc_url": "https://www.hijanee.com/p/blog-page_10.html",
        "keywords": ["근로장려금 계산기", "근로장려금 얼마", "장려금 계산"],
        "intro": """일은 하고 있지만 소득이 적어서 생활이 빠듯하신가요?
근로장려금은 일하는 저소득 가구를 지원하는 제도로
신청만 하면 최대 330만 원까지 받을 수 있습니다.

<b>2026년 근로장려금 지급 기준</b>
• 단독가구: 총소득 2,200만 원 미만, 최대 165만 원
• 홑벌이가구: 총소득 3,200만 원 미만, 최대 285만 원
• 맞벌이가구: 총소득 3,800만 원 미만, 최대 330만 원
• 재산 요건: 가구원 전체 재산 합계 2.4억 원 미만

아래 계산기에 소득과 가구 형태를 입력하면 예상 지급액을 확인할 수 있습니다.""",
        "tips": """<b>근로장려금 신청 시 주의사항</b>
• 신청 기간: 5월 1일~31일 (정기), 9월 반기 신청도 가능
• 홈택스(hometax.go.kr) 또는 손택스 앱에서 신청 가능
• 국세청에서 안내문이 왔다면 반드시 확인하세요
• 자녀장려금과 함께 신청하면 더 많이 받을 수 있어요""",
        "hashtags": ["근로장려금계산기", "근로장려금", "장려금신청", "저소득지원", "세금환급"]
    },
]

PUBLISHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calc_posts_published.txt")


def load_published_orders():
    if not os.path.exists(PUBLISHED_FILE):
        return set()
    with open(PUBLISHED_FILE, "r", encoding="utf-8") as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())


def save_published_order(order):
    with open(PUBLISHED_FILE, "a", encoding="utf-8") as f:
        f.write(str(order) + "\n")


def get_next_post():
    published = load_published_orders()
    for post in CALCULATOR_POSTS:
        if post["order"] not in published:
            return post
    return None


def build_post_content(post):
    hashtag_str = " ".join(["#" + t for t in post["hashtags"]])
    calc_section = """
<div style="margin:40px 0;padding:24px;background:#f0f7ff;border-radius:14px;border:2px solid #c8e0ff;text-align:center;">
<p style="font-size:20px;font-weight:700;color:#1a5fb4;margin:0 0 16px 0;">&#128161; 지금 바로 계산해보세요!</p>
<iframe src="{calc_url}" width="100%" height="700" style="border:none;border-radius:10px;display:block;margin:0 auto;" loading="lazy" title="{calc_title}"></iframe>
<p style="margin:14px 0 0 0;font-size:13px;color:#888;">&#128279; <a href="{calc_url}" target="_blank" rel="noopener">{calc_title} 새 창에서 열기</a></p>
</div>""".format(calc_url=post["calc_url"], calc_title=post["calc_title"])

    content = """<div style="font-family:'Noto Sans KR',sans-serif;line-height:1.8;color:#333;max-width:800px;margin:0 auto;">

<p style="font-size:16px;">{intro}</p>

{calc_section}

<div style="margin:30px 0;padding:20px;background:#fff9e6;border-radius:10px;border-left:4px solid #f0a500;">
{tips}
</div>

<p style="margin-top:30px;color:#888;font-size:14px;">{hashtags}</p>

<p style="font-size:12px;color:#aaa;margin-top:20px;">이 포스팅은 정보 제공을 목적으로 작성되었으며, 실제 금액은 개인 상황에 따라 다를 수 있습니다.</p>
</div>""".format(
        intro=post["intro"].replace("\n", "<br>"),
        calc_section=calc_section,
        tips=post["tips"].replace("\n", "<br>"),
        hashtags=hashtag_str
    )
    return content


def publish_to_blogger(post, content):
    token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.pickle")
    if not os.path.exists(token_path):
        print("token.pickle 없음 - GitHub Actions 환경에서는 restore_token() 필요")
        return None

    from google.auth.transport.requests import Request
    with open(token_path, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    url = "https://www.googleapis.com/blogger/v3/blogs/" + BLOG_ID + "/posts"
    data = json.dumps({
        "title": post["title"],
        "content": content,
        "labels": ["계산기", post["calc_title"]],
        "status": "live"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + creds.token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        return result.get("url", "")
    except Exception as e:
        print("발행 실패: " + str(e))
        return None


def send_naver_email(post, post_url, content_html):
    """네이버 블로그 복붙용 이메일 발송"""
    # 자격증명을 함수 안에서 직접 로드 (환경변수 우선)
    gmail_address = os.environ.get("GMAIL_ADDRESS") or GMAIL_ADDRESS or ""
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD") or GMAIL_APP_PASSWORD or ""
    email_recipient = os.environ.get("EMAIL_RECIPIENT") or EMAIL_RECIPIENT or "duatkdtn@gmail.com"
    # 빈 문자열 방지 (GitHub Secrets 미설정 시 빈 문자열로 들어옴)
    email_recipient = email_recipient.strip() or "duatkdtn@gmail.com"

    print(f"이메일 발송 시도: {gmail_address} → {email_recipient}")
    if not gmail_address or not gmail_password:
        print("Gmail 설정 없음 - 이메일 스킵")
        return

    subject = "[계산기 포스팅] " + post["title"]

    # 네이버용 본문 (HTML 태그 제거 버전)
    import re
    plain = re.sub(r'<[^>]+>', '', content_html)
    plain = plain.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#128161;', '💡').replace('&#128279;', '🔗')

    html_body = """
<html><body style="font-family:sans-serif;max-width:700px;margin:0 auto;">
<h2 style="color:#1a5fb4;">📝 {title}</h2>
<p><b>블로그 발행 URL:</b> <a href="{post_url}">{post_url}</a></p>
<hr>
<h3>네이버 블로그 복붙용 내용</h3>
<div style="background:#f8f9fa;padding:15px;border-radius:8px;white-space:pre-wrap;">{plain}</div>
<hr>
<p><b>계산기 링크:</b> <a href="{calc_url}">{calc_title}</a></p>
<p style="color:#888;font-size:12px;">하이쟈늬 블로그 자동화 시스템</p>
</body></html>
""".format(
        title=post["title"],
        post_url=post_url or "발행 실패",
        plain=plain[:3000],
        calc_url=post["calc_url"],
        calc_title=post["calc_title"]
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = email_recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_address, gmail_password)
        smtp.sendmail(gmail_address, email_recipient, msg.as_string())
    print("이메일 발송 완료: " + email_recipient)


def main():
    restore_token()
    post = get_next_post()
    if not post:
        print("모든 계산기 포스팅 발행 완료!")
        return

    print("발행 시작: " + post["title"])
    content = build_post_content(post)
    post_url = publish_to_blogger(post, content)

    if post_url:
        save_published_order(post["order"])
        print("발행 성공: " + post_url)
        send_naver_email(post, post_url, content)
    else:
        print("발행 실패 - 다음 실행 시 재시도됩니다")


if __name__ == "__main__":
    main()
