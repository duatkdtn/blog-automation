# -*- coding: utf-8 -*-
"""
regen_thumbnails.py
WordPress 전체 글 썸네일 재생성
- 제목 키워드 기반으로 아이콘 + 색상 결정 (글마다 다름)
- 왼쪽 텍스트 / 오른쪽 아이콘 레이아웃
- Claude Haiku로 글마다 다른 후킹문구 4줄 생성
"""

import requests, time, io, os
import anthropic
from datetime import datetime
from requests.auth import HTTPBasicAuth
from PIL import Image, ImageDraw, ImageFont

# ── 설정 ────────────────────────────────────────────────
WP_URL = "https://hijaneeinfo.com"
AUTH   = HTTPBasicAuth("duatkdtn@gmail.com", "TO18 KpNd 3xkN x1cf 7REu ZIWi")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

CAT_NAMES = {
    207: "생활·정책",   208: "건강·의료",  209: "재테크·금융",
    210: "부동산",      211: "교육·육아",  212: "자동차·교통",
    213: "음식·건강식", 214: "여행·나들이", 215: "디지털·IT",
    216: "법률·생활법", 217: "노약자·시니어", 218: "연예·문화",
    219: "트렌드·사회",
}

# ── 키워드 → 테마 (오른쪽색, 강조색, 아이콘) ────────────
# ※ 순서 중요: 위에서부터 매칭 → 더 구체적인 것을 먼저!
KEYWORD_THEMES = [
    # 연금·저축·노후준비 (보라빛 파랑) ← money보다 먼저!
    (["국민연금","연금저축","IRP","퇴직연금","개인연금","연금보험",
      "추납","연금수령","노후준비","연금개혁","연금크레딧","기초연금"],
     (108, 92, 231), "pension"),

    # 보험 (남색) ← money보다 먼저!
    (["실손보험","생명보험","보험료","보험금","보험가입",
      "보험청구","암보험","종신보험","실비보험",
      "보험료인상","보험료할인","보험료환급","5세대실손"],
     (30, 60, 160), "insurance"),

    # 명절·전통·차례 ← festival 먼저!
    (["추석","명절","차례","제사","성묘","벌초","상차림","차례상",
      "설날","추석선물","명절선물","제수용품","기제사","기일","차례음식",
      "고사","시제","차례절차","지방쓰는"],
     (204, 102, 0), "festival"),

    # 공휴일·휴가·연휴 ← calendar 먼저!
    (["연휴","공휴일","대체공휴일","개천절","한글날","광복절","현충일",
      "크리스마스","연차","휴가","징검다리","황금연휴","샌드위치연휴"],
     (52, 120, 200), "calendar"),

    # 지원금·혜택·바우처 ← benefit 먼저!
    (["민생지원금","긴급복지","긴급지원","생활지원금","에너지바우처","문화누리",
      "온누리상품권","지역사랑상품권","소비쿠폰","페이백","바우처","복지혜택",
      "생계급여","의료급여","주거급여","복지포인트"],
     (0, 150, 100), "benefit"),

    # 전화·상담·민원 (하늘파랑)
    (["전화상담","콜센터","민원전화","고객센터","ARS","민원","상담전화",
      "문의전화","신고전화","긴급전화","1588","1577","1544"],
     (41, 182, 246), "phone"),

    # 자격증·증명서 (금색)
    (["자격증","면허증","증명서","인증서","수료증","면허취득","시험합격",
      "국가자격","기사자격","산업기사","기능사","공인자격","자격시험"],
     (180, 140, 0), "certificate"),

    # 귀농·농업·텃밭 (흙색)
    (["귀농","농업","텃밭","농지","농촌","작물","수확","귀촌","팜","농막",
      "주말농장","유기농","농산물","귀농지원","도시농업"],
     (100, 70, 20), "farm"),

    # 수리·AS·공사 (회색)
    (["수리비","AS","하자","리모델링","수선","인테리어","견적","공사비",
      "도배","바닥재","타일","배관","전기공사","에어컨청소","세탁기청소"],
     (100, 100, 120), "repair"),

    # 의류·패션·세탁 (보라)
    (["의류","패션","옷","코디","세탁","드라이클리닝","옷관리","의상",
      "유행","트렌드","스타일","패딩","코트","니트","청바지"],
     (130, 60, 180), "clothes"),

    # 청구서·고지서·영수증
    (["청구서","고지서","영수증","명세서","납부서","요금청구","요금고지",
      "전기요금","가스요금","수도요금","관리비","통신요금"],
     (180, 100, 30), "receipt"),

    # 뉴스·공지·소식
    (["공지","발표","보도","알림","뉴스속보","긴급공지","새소식",
      "개정안","시행안","입법예고","고시","행정예고","공고"],
     (50, 80, 140), "news"),

    # 여름휴가·방학·피서
    (["방학","피서","바캉스","해수욕","해변","여름휴가","피서지",
      "워터파크","수상스포츠","물놀이","여름철","폭염대피"],
     (30, 170, 210), "vacation"),

    # 취미·그림·예술
    (["취미","그림","공예","전시회","미술관","독서모임","사진","수채화",
      "캘리그라피","도예","자수","뜨개질","플리마켓","핸드메이드"],
     (180, 80, 160), "art"),

    # 청소·정리·환경
    (["청소","대청소","정리수납","분리수거","재활용","환경정리","청소용품",
      "청소업체","입주청소","이사청소","곰팡이제거","세균"],
     (30, 160, 160), "clean"),

    # 게임·오락 (진보라)
    (["게임","오락","스마트폰게임","온라인게임","모바일게임","게임머니",
      "게임아이템","e스포츠","스트리밍","게임중독"],
     (90, 50, 180), "game"),

    # 독서·도서·출판 (브라운)
    (["독서","베스트셀러","책추천","서평","도서추천","출판","북클럽",
      "도서관이용","전자책","오디오북","독서모임","인문학"],
     (120, 80, 40), "book"),

    # 지도·경로·길찾기
    (["지도앱","길찾기","네비게이션","경로","대중교통경로","환승","도보",
      "카카오맵","네이버지도","티맵","경로안내","실시간교통"],
     (0, 130, 120), "map"),

    # 선물·기념일·이벤트 ← benefit과 다른 스타일
    (["선물","기념일","생일선물","크리스마스선물","졸업선물","취업선물",
      "결혼선물","돌잔치선물","어버이날선물","스승의날선물"],
     (200, 60, 120), "gift"),

    # 주식·투자 (진초록) ← money보다 먼저!
    (["주식","투자","펀드","ETF","코스피","코스닥","배당","채권",
      "해외주식","달러","환율","금투자","원자재","크립토","가상화폐"],
     (34, 139, 34), "invest"),

    # 운동·헬스 ← medical(다이어트 포함)보다 먼저!
    (["운동","헬스","피트니스","요가","수영","러닝","마라톤",
      "헬스장","PT","트레이닝","근육","체력","유산소","스쿼트"],
     (231, 76, 60), "health"),

    # 교육·학습 ← child(교육 포함)보다 먼저!
    (["공부","독서","도서관","수험","논술","독학","어학",
      "공무원시험","시험준비","토익","토플","고시","검정고시"],
     (52, 152, 219), "education"),

    # 반려동물 (주황)
    (["반려동물","강아지","고양이","펫","동물병원","사료","반려견",
      "반려묘","반려동물분양","동물등록","펫보험","중성화"],
     (243, 156, 18), "pet"),

    # 쇼핑·할인 (보라)
    (["쇼핑","할인","세일","특가","쿠폰","캐시백","직구",
      "해외직구","공동구매","백화점","아울렛","포인트적립"],
     (142, 68, 173), "shopping"),

    # 배달·택배 (진오렌지)
    (["택배","배달","배송","퀵","우편","등기","소포","우체국",
      "쿠팡로켓","반품","교환","CJ대한통운","한진","롯데택배"],
     (211, 84, 0), "delivery"),

    # 결혼·웨딩 (딥레드)
    (["결혼","웨딩","신혼","예물","예식","청첩장","허니문",
      "혼수","드레스","스드메","부케","결혼준비","예단"],
     (180, 30, 80), "wedding"),

    # 지역·동네 (청록)
    (["동네","주민","구청","시청","읍면동","행정복지센터",
      "동주민센터","지자체","지방자치","지역화폐","지역축제"],
     (26, 188, 156), "local"),

    # 은행·금융기관 (다크블루) ← money보다 먼저!
    (["은행","통장","ATM","계좌","이체","송금","저축은행",
      "신협","새마을금고","카카오뱅크","토스뱅크","케이뱅크","인터넷은행"],
     (25, 50, 140), "bank"),

    # 자연·환경·날씨 (깊은초록)
    (["환경","기후","날씨","정원","식물","텃밭","미세먼지",
      "황사","태풍","폭염","한파","탄소","친환경","재활용"],
     (46, 125, 50), "nature"),

    # 돈·세금·금융 (파란색)
    (["퇴직금","월급","연봉","급여","임금","장려금",
      "수령","소득","재테크","절세","세금","환급","공제","재산","청약저축",
      "대출","금리","이자","DSR","LTV","DTI","신용","카드","예금","적금",
      "세액","납부","부과","과태료","범칙금","과징금","납세","국세","지방세",
      "근로장려금","자녀장려금","기초생활",
      "두루누리","고용촉진","산재","실업급여","육아휴직급여","출산급여"],
     (41, 128, 185), "money"),

    # 병원 건물·시설 (빨강) ← medical보다 먼저!
    (["병원비","입원","응급실","종합병원","의원","보건소","치과","한의원비",
      "병원예약","진료비","수납","건강검진센터","건강검진비"],
     (192, 57, 43), "hospital"),

    # 약·처방전 ← medical보다 먼저!
    (["처방약","약봉지","복약","복용","투약","약처방","약제","의약품",
      "영양제","비타민","보충제","약복용","상비약","진통제","해열제"],
     (39, 174, 96), "medicine"),

    # 건강·의료 (초록색)
    (["건강보험","의료","병원","접종","백신","암검진","치매","틀니","백내장",
      "수술","진료","건강","독감","예방","약국","처방","질환","당뇨","혈압",
      "암","한방","침","뇌졸중","심장","폐","간","위","대장","갑상선",
      "비만","다이어트","영양","보충제","건강식품","한의원"],
     (39, 174, 96), "medical"),

    # 부동산·주택 (빨간색)
    (["부동산","주택","아파트","전세","월세","임대","매매","취득세","입주",
      "분양","주거","등기","재개발","재건축","청약","오피스텔","빌라","원룸",
      "공시가격","공동주택","단독주택","임대차","전월세","보증금","대항력",
      "임대인","임차인","집주인","세입자","중개수수료","부동산중개"],
     (192, 57, 43), "house"),

    # 자동차·교통 (주황빨간)
    (["자동차","차량","면허","자동차세","의무보험","자동차보험","차량등록",
      "전기차","하이브리드","중고차","신차","튜닝","정비","엔진오일",
      "운전","교통위반","과속","주정차","견인","번호판","검사","폐차",
      "대중교통","버스","지하철","KTX","기차","고속도로","통행료","하이패스"],
     (231, 76, 60), "car"),

    # 신생아·태아·임신 ← child보다 먼저!
    (["신생아","태아","임신초기","임신중기","임신말기","출산준비","태동",
      "분만","제왕절개","조기출산","태아보험","임산부영양","태교"],
     (255, 182, 193), "baby"),

    # 학교·학교생활 ← child보다 먼저!
    (["초등학교","중학교","고등학교","개학","방과후","돌봄교실","학교급식",
      "학교폭력","전학","학교생활","교복","졸업식","입학식"],
     (52, 120, 200), "school"),

    # 교육·육아·가족 (하늘색)
    (["교육","학교","육아","아이","자녀","출산","임신","보육","어린이","유치원",
      "아동수당","양육","입학","수능","대학","학원","과외","유학","장학금",
      "어린이집","산후조리","모유","분유","기저귀","이유식","성장","발달",
      "아기","신생아","태아","임산부","출산지원","다둥이","다자녀"],
     (52, 152, 219), "child"),

    # 회사·사무실 ← work보다 먼저!
    (["회사","사무실","직장인","출퇴근","재택근무","사무용품","연차신청",
      "출장","야근","주5일","사규","인사규정","직원복지","사원"],
     (52, 73, 94), "office"),

    # 취업·일자리·직장 (주황)
    (["취업","일자리","고용","직장","실업","구직","채용","근로","고용보험",
      "청년","채용지원","아르바이트","알바","인턴","경력","이력서","면접",
      "최저임금","주휴수당","야간수당","초과근무","해고","권고사직","퇴직",
      "직업훈련","내일배움카드","국비지원","직업능력","자격증","워크넷"],
     (230, 126, 34), "work"),

    # 노인·시니어·복지 (노란주황)
    (["노인","시니어","노약자","요양","경로","어르신","기초연금","노령",
      "장기요양","요양병원","요양원","실버","경로당","노인정","치매안심",
      "노인일자리","활기찬여가","노인복지","장애인","장애","복지카드",
      "한부모","사회복지","복지관","돌봄서비스","방문요양"],
     (243, 156, 18), "elderly"),

    # 법률·계약·권리 (보라)
    (["법률","계약","소송","권리","분쟁","임차","층간소음","법원","판결","위반",
      "고소","고발","형사","민사","가처분","가압류","채권","채무","파산",
      "상속","유언","증여","이혼","양육권","친권","위자료","재판","조정",
      "법적","불법","위법","규정","조례","시행령","개정","시행"],
     (142, 68, 173), "law"),

    # 여행·나들이·축제 (청록)
    (["여행","나들이","관광","단풍","꽃놀이","가볼만한",
      "캠핑","글램핑","펜션","호텔","리조트","해외여행","국내여행","제주",
      "경주","강릉","속초","부산","봄꽃","벚꽃","핫플","데이트코스",
      "명소","드라이브","트레킹","등산","축제장","여행지","관광지"],
     (26, 188, 156), "travel"),

    # 음식·요리·식재료·식품안전 (주황-따뜻)
    (["음식","요리","식품","건강식","영양","요리법","맛집","레시피","식재료",
      "쌀","고기","채소","과일","생선","김치","된장","간장","조미료",
      "냉동식품","간식","빵","카페","디저트","커피","술","소주","맥주",
      "지방","단백질","탄수화물","칼로리","식단","먹방",
      "황새치","참치","고등어","명태","수산물","해산물","육류","농산물",
      "메틸수은","살충제","농약","식품안전","회수","리콜","기준치","초과",
      "식약처","식품의약품","첨가물","방부제","위생"],
     (211, 84, 0), "food"),

    # 연예·문화·스포츠 (보라-핑크)
    (["연예","배우","가수","아이돌","드라마","영화","뮤지컬","공연","콘서트",
      "결별","열애","이별","연애","사귀","커플","스캔들","루머","확인",
      "데뷔","은퇴","컴백","신곡","앨범","팬","팬클럽","아이돌","그룹",
      "시상식","수상","연기","노래","가요","K-POP","케이팝","스포","주연",
      "스타","셀럽","모델","MC","방송인","코미디언","웹툰","만화","소설",
      "스포츠","야구","축구","농구","올림픽","선수","감독","챔피언","우승"],
     (142, 68, 173), "entertainment"),

    # IT·디지털·앱 (다크)
    (["IT","디지털","앱","스마트폰","인터넷","컴퓨터","AI","프로그램",
      "ChatGPT","인공지능","빅데이터","클라우드","보안","해킹","피싱",
      "OTP","공인인증서","공동인증서","사이버","온라인","플랫폼","SNS",
      "유튜브","인스타","카카오","네이버","쿠팡","배달","키오스크"],
     (52, 73, 94), "tech"),

]

# 매칭 안 될 때 제목 해시로 다양한 기본 테마 선택
FALLBACK_THEMES = [
    ((44, 62, 80),    "document"),
    ((100, 60, 160),  "law"),
    ((0, 120, 100),   "travel"),
    ((52, 73, 94),    "tech"),
    ((160, 60, 40),   "food"),
    ((30, 100, 170),  "work"),
]


# ── 아이콘별 색상 변형 3가지 (해시로 선택 → 같은 카테고리도 3가지 색) ──
COLOR_VARIANTS = {
    "money":         [(41,128,185),  (22,160,133),  (52,73,94)],
    "medical":       [(39,174,96),   (26,188,156),  (41,128,185)],
    "entertainment": [(142,68,173),  (192,57,43),   (211,84,0)],
    "house":         [(192,57,43),   (211,84,0),    (142,68,173)],
    "car":      [(231,76,60),   (41,128,185),  (52,73,94)],
    "child":    [(52,152,219),  (39,174,96),   (243,156,18)],
    "work":     [(230,126,34),  (41,128,185),  (39,174,96)],
    "elderly":  [(243,156,18),  (39,174,96),   (52,152,219)],
    "law":      [(142,68,173),  (192,57,43),   (52,73,94)],
    "travel":   [(26,188,156),  (41,128,185),  (39,174,96)],
    "food":     [(211,84,0),    (231,76,60),   (243,156,18)],
    "tech":     [(52,73,94),    (41,128,185),  (142,68,173)],
    "document": [(44,62,80),    (41,128,185),  (100,60,160)],
    "pension":  [(108,92,231),  (142,68,173),  (52,73,94)],
    "insurance":[(30,60,160),   (52,73,94),    (108,92,231)],
    "festival": [(204,102,0),   (192,57,43),   (142,68,173)],
    "calendar": [(52,120,200),  (39,174,96),   (231,76,60)],
    "benefit":  [(0,150,100),   (39,174,96),   (243,156,18)],
    "invest":   [(34,139,34),   (22,160,133),  (41,128,185)],
    "health":   [(231,76,60),   (39,174,96),   (243,156,18)],
    "education":[(52,152,219),  (142,68,173),  (39,174,96)],
    "pet":      [(243,156,18),  (211,84,0),    (39,174,96)],
    "shopping": [(142,68,173),  (231,76,60),   (243,156,18)],
    "delivery": [(211,84,0),    (231,76,60),   (52,73,94)],
    "wedding":  [(180,30,80),   (142,68,173),  (231,76,60)],
    "local":    [(26,188,156),  (41,128,185),  (39,174,96)],
    "bank":     [(25,50,140),   (41,128,185),  (52,73,94)],
    "nature":   [(46,125,50),   (26,188,156),  (211,84,0)],
    "hospital": [(192,57,43),   (231,76,60),   (180,30,30)],
    "medicine": [(39,174,96),   (26,188,156),  (41,128,185)],
    "baby":     [(255,105,135), (243,156,18),  (52,152,219)],
    "school":   [(52,120,200),  (39,174,96),   (231,76,60)],
    "office":   [(52,73,94),    (41,128,185),  (100,60,160)],
    "phone":    [(41,182,246),  (41,128,185),  (26,188,156)],
    "certificate":[(180,140,0), (211,84,0),    (39,174,96)],
    "farm":     [(100,70,20),   (46,125,50),   (211,84,0)],
    "repair":   [(100,100,120), (52,73,94),    (180,140,0)],
    "clothes":  [(130,60,180),  (180,30,80),   (41,128,185)],
    "receipt":  [(180,100,30),  (211,84,0),    (41,128,185)],
    "news":     [(50,80,140),   (52,73,94),    (192,57,43)],
    "vacation": [(30,170,210),  (41,128,185),  (39,174,96)],
    "art":      [(180,80,160),  (130,60,180),  (211,84,0)],
    "clean":    [(30,160,160),  (26,188,156),  (41,128,185)],
    "game":     [(90,50,180),   (52,73,94),    (192,57,43)],
    "book":     [(120,80,40),   (100,60,160),  (41,128,185)],
    "map":      [(0,130,120),   (26,188,156),  (41,128,185)],
    "gift":     [(200,60,120),  (180,30,80),   (142,68,173)],
}


def accent_to_bg(accent):
    """강조색 → 연한 파스텔 배경 자동 생성"""
    return tuple(int(c * 0.10 + 255 * 0.90) for c in accent)


def get_theme(title):
    import hashlib
    h = int(hashlib.md5(title.encode("utf-8")).hexdigest(), 16)
    for keywords, color, icon in KEYWORD_THEMES:
        for kw in keywords:
            if kw in title:
                variants = COLOR_VARIANTS.get(icon, [color])
                accent = variants[h % len(variants)]
                return accent, icon
    # 키워드 미매칭 → 제목 해시로 다양한 기본 테마 + 색상 변형
    _, icon = FALLBACK_THEMES[h % len(FALLBACK_THEMES)]
    variants = COLOR_VARIANTS.get(icon, [(44, 62, 80)])
    accent = variants[h % len(variants)]
    return accent, icon


def load_font(size, bold=True):
    paths = [
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]
    if not bold:
        paths = ["C:/Windows/Fonts/malgun.ttf",
                 "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"] + paths
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                continue
    return ImageFont.load_default()


def draw_icon(draw, icon_type, cx, cy, size, accent):
    """카테고리별 풍부한 컬러 일러스트 (여러 오브젝트)"""
    s = size  # ~220

    if icon_type == "money":
        # 초록 지폐 3장 겹치기
        bill_colors = [(39, 174, 96), (46, 204, 113), (88, 214, 141)]
        for i, bc in enumerate(bill_colors):
            ox, oy = i * 18, i * 14
            draw.rounded_rectangle([cx - s//2 + ox, cy - s//4 + oy,
                                     cx + s//2 + ox, cy + s//4 + oy],
                                    radius=12, fill=bc)
            draw.text((cx + ox, cy + oy), "₩", font=load_font(36), fill=(255,255,255), anchor="mm")
        # 계산기 (아이보리+파란버튼)
        draw.rounded_rectangle([cx - s//2, cy + s//5, cx - s//5, cy + s//2 + 10],
                                radius=8, fill=(245, 245, 240))
        for row in range(2):
            for col in range(2):
                bx = cx - s//2 + 10 + col * 22
                by = cy + s//5 + 18 + row * 20
                draw.rounded_rectangle([bx, by, bx + 15, by + 12], radius=3,
                                       fill=(41, 128, 185))
        # 신용카드
        draw.rounded_rectangle([cx + s//10, cy + s//3, cx + s//2 + 10, cy + s//2 + 10],
                                radius=8, fill=(41, 128, 185))
        draw.rectangle([cx + s//10 + 6, cy + s//3 + 14, cx + s//10 + 26, cy + s//3 + 26],
                       fill=(255, 215, 0))
        draw.text((cx + s//3, cy + s//2 - 2), "CARD", font=load_font(14, bold=False),
                  fill=(255,255,255), anchor="mm")

    elif icon_type == "medical":
        # 표적 동심원
        tcy = cy - s // 10
        for r, col in [(s*3//4, (50,110,185)), (s//2, (255,255,255)),
                       (s//3, (50,110,185)), (s//7, (255,255,255))]:
            draw.ellipse([cx - r, tcy - r, cx + r, tcy + r], fill=col)
        # 십자선
        draw.line([cx - s - 10, tcy, cx + s + 10, tcy], fill=(50,110,185), width=4)
        draw.line([cx, tcy - s - 10, cx, tcy + s + 10], fill=(50,110,185), width=4)
        # 주사기 (우하향)
        sx1, sy1 = cx - s // 3, tcy - s // 4
        draw.rounded_rectangle([sx1, sy1 - 10, sx1 + s*2//3, sy1 + 10], radius=8,
                                fill=(70, 130, 200))
        draw.polygon([(sx1 - 20, sy1 - 6), (sx1 - 20, sy1 + 6), (sx1, sy1)],
                     fill=(70, 130, 200))
        draw.rectangle([sx1 + s//4, sy1 - 7, sx1 + s//4 + 6, sy1 + 7],
                       fill=(255, 255, 255))
        # 체크리스트
        clx, cly = cx - s // 3, cy + s // 4
        draw.rounded_rectangle([clx, cly, clx + s*3//4, cly + s//2],
                                radius=8, fill=(255, 255, 255))
        draw.rounded_rectangle([clx + 8, cly - 14, clx + s//2, cly + 10],
                                radius=4, fill=(50,110,185))
        draw.text((clx + s//4, cly - 2), "진찰결과", font=load_font(15, bold=False),
                  fill=(255,255,255), anchor="mm")
        for i in range(3):
            draw.rounded_rectangle([clx + 10, cly + 16 + i*20, clx + s*3//4 - 10, cly + 28 + i*20],
                                   radius=3, fill=(200, 215, 230))
        # 체크 원 2개
        for i, (ox, chcol) in enumerate([(cx + s//4, (76,175,80)), (cx + s//2, (255,152,0))]):
            chy = cy - s*3//4
            draw.ellipse([ox - 20, chy - 20, ox + 20, chy + 20], fill=chcol)
            draw.line([ox - 10, chy, ox - 3, chy + 8], fill=(255,255,255), width=4)
            draw.line([ox - 3, chy + 8, ox + 10, chy - 8], fill=(255,255,255), width=4)

    elif icon_type == "house":
        # 잔디
        gy = cy + s * 7 // 10
        draw.rectangle([cx - s, gy, cx + s, gy + 30], fill=(34, 139, 34))
        # 집 벽
        hx1, hx2 = cx - s*3//5, cx + s*3//5
        hy1 = cy + s // 10
        draw.rectangle([hx1, hy1, hx2, gy], fill=(248, 243, 230))
        # 지붕
        draw.polygon([(hx1 - 25, hy1), (cx, cy - s*4//5), (hx2 + 25, hy1)],
                     fill=(185, 50, 30))
        # 굴뚝
        chx = cx + s // 3
        draw.rectangle([chx, cy - s*4//5 + 15, chx + 32, hy1], fill=(185, 50, 30))
        # 연기
        for ox, oy, r in [(chx+10, cy-s*4//5, 14), (chx+18, cy-s*4//5-18, 11), (chx+5, cy-s*4//5-28, 9)]:
            draw.ellipse([ox-r+2, oy-r+2, ox+r, oy+r], fill=(190, 190, 190))
        # 문
        dx1, dx2 = cx - s//10, cx + s//10
        draw.rectangle([dx1, hy1 + s//3, dx2, gy], fill=(130, 78, 35))
        draw.ellipse([dx2 - 12, gy - s//4, dx2 - 2, gy - s//4 + 10], fill=(200, 160, 50))
        # 창문 2개
        for wx in [hx1 + 12, cx + s//5]:
            wy1, wy2 = hy1 + 18, hy1 + 18 + s//5
            draw.rectangle([wx, wy1, wx + s//5, wy2], fill=(155, 215, 245))
            draw.line([wx + s//10, wy1, wx + s//10, wy2], fill=(100, 170, 210), width=3)
            draw.line([wx, wy1 + s//10, wx + s//5, wy1 + s//10], fill=(100, 170, 210), width=3)
        # 열쇠+링
        kx, ky = cx + s*7//8, cy + s//5
        kr = s // 5
        draw.ellipse([kx - kr, ky - kr, kx + kr, ky + kr], fill=(255, 210, 20))
        draw.ellipse([kx - kr + 12, ky - kr + 12, kx + kr - 12, ky + kr - 12], fill=(200, 155, 10))
        # 열쇠 손잡이
        draw.rectangle([kx + kr - 5, ky - 8, kx + kr + s//4, ky + 8], fill=(255, 210, 20))
        draw.rectangle([kx + kr + s//6, ky + 8, kx + kr + s//6 + 14, ky + 22], fill=(255, 210, 20))
        draw.rectangle([kx + kr + s//4 - 6, ky + 8, kx + kr + s//4 + 6, ky + 18], fill=(255, 210, 20))

    elif icon_type == "car":
        # 자동차 - 차체(파란색) + 창문(하늘) + 바퀴(검정) + 라이트(노랑)
        carcol = (41, 128, 185)
        winy = cy - s // 6
        # 차체
        draw.rounded_rectangle([cx - s*2//3, cy - s//8, cx + s*2//3, cy + s//4],
                                radius=16, fill=carcol)
        # 지붕
        draw.rounded_rectangle([cx - s//2 + 10, winy, cx + s//2 - 10, cy - s//8 + 8],
                                radius=12, fill=carcol)
        # 창문 (하늘색)
        draw.rounded_rectangle([cx - s//3, winy + 8, cx - 10, cy - s//8 + 4],
                                radius=6, fill=(155, 215, 245))
        draw.rounded_rectangle([cx + 10, winy + 8, cx + s//3, cy - s//8 + 4],
                                radius=6, fill=(155, 215, 245))
        # 바퀴 2개
        for wx in [cx - s//2 + 10, cx + s//2 - 10]:
            draw.ellipse([wx - 32, cy + s//8, wx + 32, cy + s//4 + 32],
                         fill=(50, 50, 50))
            draw.ellipse([wx - 18, cy + s//8 + 14, wx + 18, cy + s//4 + 18],
                         fill=(120, 120, 120))
        # 헤드라이트
        draw.ellipse([cx + s*2//3 - 18, cy - 6, cx + s*2//3 + 2, cy + 10],
                     fill=(255, 230, 50))
        # 배기가스 연기
        for i, r in enumerate([8, 6, 5]):
            draw.ellipse([cx - s*2//3 - 30 - i*18, cy - i*10,
                          cx - s*2//3 - 30 - i*18 + r*2, cy - i*10 + r*2],
                         fill=(200, 200, 200))

    elif icon_type == "child":
        # 어린이 + 아기병 + 하트
        # 아이 (초록 옷)
        hr = s // 7
        draw.ellipse([cx - s//4 - hr, cy - s//2 - hr, cx - s//4 + hr, cy - s//2 + hr],
                     fill=(255, 220, 177))  # 살색 머리
        draw.rounded_rectangle([cx - s//4 - hr + 6, cy - s//2 + hr,
                                 cx - s//4 + hr - 6, cy + s//4], radius=8,
                                fill=(76, 175, 80))  # 초록 몸
        # 팔다리
        draw.line([cx - s//4 - hr + 4, cy - s//4, cx - s//2, cy + s//8], fill=(76,175,80), width=10)
        draw.line([cx - s//4 + hr - 4, cy - s//4, cx, cy + s//8], fill=(76,175,80), width=10)
        draw.line([cx - s//4 - 6, cy + s//4, cx - s//3, cy + s//2], fill=(100,100,200), width=10)
        draw.line([cx - s//4 + 6, cy + s//4, cx - s//8, cy + s//2], fill=(100,100,200), width=10)
        # 아기 우유병
        draw.rounded_rectangle([cx + s//5, cy - s//4, cx + s//2, cy + s//3],
                                radius=14, fill=(255, 255, 255))
        draw.rounded_rectangle([cx + s//5 + 10, cy - s//4 - 18, cx + s//2 - 10, cy - s//4 + 5],
                                radius=6, fill=(230, 230, 230))
        draw.rectangle([cx + s//5, cy - s//6, cx + s//2, cy + s//10],
                       fill=(144, 213, 255))
        # 하트
        hx, hy, hhr = cx + s*3//5, cy - s//3, s//9
        draw.ellipse([hx - hhr, hy - hhr, hx, hy], fill=(231, 76, 60))
        draw.ellipse([hx, hy - hhr, hx + hhr, hy], fill=(231, 76, 60))
        draw.polygon([(hx - hhr, hy), (hx + hhr, hy), (hx, hy + hhr + 8)], fill=(231, 76, 60))

    elif icon_type == "work":
        # 사람 2명 + 서류가방
        for i, (px, pcol) in enumerate([(cx - s//4, (41,128,185)), (cx + s//5, (39,174,96))]):
            phr = s // 7 - i * 5
            py = cy - s // 2 + i * 20
            draw.ellipse([px - phr, py - phr, px + phr, py + phr], fill=(255, 220, 177))
            draw.rounded_rectangle([px - phr + 5, py + phr, px + phr - 5, cy + s//4],
                                   radius=8, fill=pcol)
            draw.line([px - phr + 3, py + phr + 20, px - phr - 20, cy + s//4], fill=pcol, width=9)
            draw.line([px + phr - 3, py + phr + 20, px + phr + 20, cy + s//4], fill=pcol, width=9)
        # 서류가방
        bx, by = cx - s//8, cy + s//5
        draw.rounded_rectangle([bx, by, bx + s*2//3, by + s//3], radius=10, fill=(192, 57, 43))
        draw.rounded_rectangle([bx + s//5, by - 14, bx + s*2//5, by + 4], radius=5,
                                fill=(192, 57, 43), outline=(255,255,255), width=3)
        draw.line([bx, by + s//6, bx + s*2//3, by + s//6], fill=(255,200,200), width=3)

    elif icon_type == "elderly":
        # 노인 (베이지 옷) + 복지카드
        hr = s // 7
        # 머리 (흰 머리카락 표현)
        draw.ellipse([cx - s//3 - hr, cy - s//2 - hr, cx - s//3 + hr, cy - s//2 + hr],
                     fill=(240, 240, 240))
        # 몸
        draw.rounded_rectangle([cx - s//3 - hr + 6, cy - s//2 + hr,
                                 cx - s//3 + hr - 6, cy + s//4], radius=8,
                                fill=(100, 180, 150))  # 민트 옷
        # 팔다리
        draw.line([cx - s//3 - hr + 4, cy - s//4, cx - s//2, cy + s//8], fill=(100,180,150), width=9)
        draw.line([cx - s//3 + hr - 4, cy - s//4, cx - s//12, cy + s//8], fill=(100,180,150), width=9)
        draw.line([cx - s//3 - 6, cy + s//4, cx - s//2, cy + s//2 + 10], fill=(80,80,120), width=9)
        draw.line([cx - s//3 + 6, cy + s//4, cx - s//5, cy + s//2 + 10], fill=(80,80,120), width=9)
        # 지팡이
        draw.line([cx - s//6, cy - s//8, cx - s//6, cy + s//2 + 10], fill=(180,140,100), width=8)
        draw.arc([cx - s//6 - 16, cy - s//8 - 16, cx - s//6 + 16, cy - s//8 + 16],
                 180, 360, fill=(180,140,100), width=8)
        # 복지카드 (초록 카드)
        draw.rounded_rectangle([cx + s//10, cy - s//6, cx + s*3//4, cy + s//5],
                                radius=10, fill=(39, 174, 96))
        draw.text((cx + s*2//5, cy - s//6 + 20), "복지카드", font=load_font(20),
                  fill=(255,255,255), anchor="mm")
        draw.text((cx + s*2//5, cy - s//6 + 46), "혜택 조회", font=load_font(17, bold=False),
                  fill=(200,255,220), anchor="mm")
        # 화살표 장식 2개
        for i, (ax, ay, acol) in enumerate([(cx + s*2//5, cy - s*3//5, (231,76,60)),
                                             (cx + s*3//5, cy - s//2, (243,156,18))]):
            draw.polygon([(ax-12, ay), (ax, ay-18), (ax+12, ay), (ax+6, ay), (ax+6, ay+16),
                          (ax-6, ay+16), (ax-6, ay)], fill=acol)

    elif icon_type == "law":
        # 저울 + 법전
        # 저울 기둥
        draw.rounded_rectangle([cx - 6, cy - s*3//4, cx + 6, cy + s//2], radius=4,
                                fill=(180, 140, 100))
        draw.rounded_rectangle([cx - s//2, cy + s//2 - 8, cx + s//2, cy + s//2 + 8],
                                radius=4, fill=(180, 140, 100))
        # 가로대
        draw.rounded_rectangle([cx - s*3//5, cy - s*3//4 - 4, cx + s*3//5, cy - s*3//4 + 4],
                                radius=2, fill=(180, 140, 100))
        # 줄
        draw.line([cx - s*2//5, cy - s*3//4, cx - s*2//5, cy - s//4], fill=(180,140,100), width=4)
        draw.line([cx + s*2//5, cy - s*3//4, cx + s*2//5, cy - s//4], fill=(180,140,100), width=4)
        # 접시 2개 (반원)
        for sign, col in [(-1, (231,76,60)), (1, (41,128,185))]:
            px = cx + sign * s*2//5
            draw.chord([px - s//4, cy - s//4, px + s//4, cy - s//4 + s//3],
                       0, 180, fill=col)
        # 법전 (빨간 책)
        draw.rounded_rectangle([cx - s//4, cy + s//8, cx + s//4, cy + s//2],
                                radius=5, fill=(192, 57, 43))
        draw.rectangle([cx - s//4 + 8, cy + s//8 + 6, cx + s//4 - 8, cy + s//8 + 12],
                       fill=(255, 200, 200))
        draw.text((cx, cy + s//3), "法", font=load_font(36), fill=(255,255,255), anchor="mm")

    elif icon_type == "travel":
        # 비행기 + 구름 + 태양
        # 태양
        draw.ellipse([cx + s//3, cy - s*3//4, cx + s*3//4, cy - s//4], fill=(255, 210, 50))
        for angle in range(0, 360, 45):
            import math
            sx = cx + s*7//12 + int(math.cos(math.radians(angle)) * (s//4 + 15))
            sy = cy - s//2 + int(math.sin(math.radians(angle)) * (s//4 + 15))
            draw.line([cx + s*7//12, cy - s//2, sx, sy], fill=(255,210,50), width=5)
        # 구름 2개
        for i, (clx, cly, scl) in enumerate([(cx - s//5, cy - s//3, 1.0), (cx + s//8, cy - s//6, 0.7)]):
            for ox, oy, r in [(clx, cly, int(28*scl)), (clx+int(26*scl), cly-int(8*scl), int(22*scl)),
                              (clx-int(22*scl), cly-int(6*scl), int(20*scl)), (clx+int(50*scl), cly, int(22*scl))]:
                draw.ellipse([ox-r, oy-r, ox+r, oy+r], fill=(255,255,255))
        # 비행기
        px, py = cx - s//3, cy + s//4
        # 동체
        draw.ellipse([px, py - 14, px + s*2//3, py + 14], fill=(41,128,185))
        # 날개
        draw.polygon([(px + s//4, py - 8), (px + s//4 - 20, py - s//3),
                      (px + s//2, py - 8)], fill=(100, 160, 220))
        draw.polygon([(px + s//4, py + 8), (px + s//4 - 20, py + s//4),
                      (px + s//2, py + 8)], fill=(100, 160, 220))
        # 꼬리
        draw.polygon([(px, py - 8), (px - s//6, py - s//4), (px, py)], fill=(100,160,220))

    elif icon_type == "food":
        # 그릇 + 젓가락 + 음식
        # 그릇
        draw.chord([cx - s*2//3, cy - s//8, cx + s*2//3, cy + s*3//4], 0, 180, fill=(240,210,180))
        draw.ellipse([cx - s*2//3, cy - s//8 - 15, cx + s*2//3, cy - s//8 + 15], fill=(230,195,160))
        # 음식 (밥/반찬)
        draw.ellipse([cx - s//3, cy - s//5, cx + s//3, cy + s//10], fill=(255,255,255))
        # 젓가락 2개
        draw.line([cx + s//6, cy - s//2, cx + s//3, cy - s//8], fill=(180,120,60), width=6)
        draw.line([cx + s//3, cy - s//2, cx + s//2, cy - s//8], fill=(180,120,60), width=6)
        # 당근
        draw.ellipse([cx - s//5, cy - s//8, cx - s//5 + 28, cy - s//8 + 28],
                     fill=(230, 120, 30))
        # 브로콜리
        for bx, bby in [(cx + s//10, cy - s//10), (cx + s//5, cy - s//10 - 12),
                        (cx + s//4, cy - s//10 + 5)]:
            draw.ellipse([bx - 14, bby - 14, bx + 14, bby + 14], fill=(39,174,96))
        # 접시 테두리 (선)
        draw.arc([cx - s*2//3, cy - s//8 - 15, cx + s*2//3, cy + s*3//4],
                 180, 360, fill=(200,170,140), width=4)

    elif icon_type == "tech":
        # 스마트폰 + 와이파이 + AI 별
        # 폰
        draw.rounded_rectangle([cx - s//3, cy - s//2, cx + s//3, cy + s*3//5],
                                radius=20, fill=(50, 60, 80))
        draw.rounded_rectangle([cx - s//3 + 8, cy - s//2 + 8, cx + s//3 - 8, cy + s*3//5 - 20],
                                radius=14, fill=(100, 150, 220))
        # 폰 화면 - 앱 아이콘들
        for row in range(2):
            for col in range(3):
                ax = cx - s//4 + col * (s//6 + 4)
                ay = cy - s//4 + row * (s//6 + 4)
                appcols = [(231,76,60),(41,128,185),(39,174,96),(243,156,18),(142,68,173),(26,188,156)]
                draw.rounded_rectangle([ax, ay, ax + s//6, ay + s//6], radius=8,
                                       fill=appcols[row*3+col])
        # 홈버튼
        draw.ellipse([cx - 12, cy + s*2//5, cx + 12, cy + s*2//5 + 24], fill=(70,80,100))
        # 와이파이 (오른쪽 위)
        wx, wy = cx + s*3//5, cy - s//3
        for r in [s//4, s//3, s*5//12]:
            draw.arc([wx - r, wy - r, wx + r, wy + r], 210, 330, fill=(41,128,185), width=5)
        draw.ellipse([wx - 8, wy + 12, wx + 8, wy + 28], fill=(41,128,185))
        # 별 장식
        for sx, sy in [(cx - s*2//3, cy - s//3), (cx + s*2//3, cy + s//4)]:
            draw.text((sx, sy), "✦", font=load_font(30), fill=(255,220,50), anchor="mm")

    elif icon_type == "entertainment":
        # 마이크 + 별 + 하트 (연예·문화)
        # 마이크 몸통
        draw.rounded_rectangle([cx - s//8, cy - s//2, cx + s//8, cy + s//8],
                                radius=s//7, fill=(142, 68, 173))
        draw.rounded_rectangle([cx - s//8 + 6, cy - s//2 + 6, cx + s//8 - 6, cy + s//8 - 6],
                                radius=s//8, fill=(192, 108, 213))
        # 마이크 줄기
        draw.rectangle([cx - 6, cy + s//8, cx + 6, cy + s//3], fill=(80, 50, 100))
        draw.rectangle([cx - s//5, cy + s//3, cx + s//5, cy + s//3 + 10], fill=(80, 50, 100))
        # 음표 (왼쪽)
        draw.text((cx - s*2//3, cy - s//4), "♪", font=load_font(48), fill=(255, 180, 255), anchor="mm")
        # 별 (오른쪽 위)
        draw.text((cx + s*2//3, cy - s//2), "★", font=load_font(44), fill=(255, 220, 50), anchor="mm")
        # 하트 (오른쪽 아래)
        draw.text((cx + s*3//5, cy + s//4), "♥", font=load_font(40), fill=(255, 80, 120), anchor="mm")

    elif icon_type in ("document", None):  # document (default)
        # 서류 + 펜 + 체크
        draw.rounded_rectangle([cx - s//3, cy - s*3//5, cx + s//3, cy + s//2],
                                radius=14, fill=(255, 255, 255))
        # 모서리 접힘
        fold = s // 5
        draw.polygon([(cx + s//3 - fold, cy - s*3//5),
                      (cx + s//3, cy - s*3//5 + fold),
                      (cx + s//3, cy - s*3//5)], fill=(200, 215, 235))
        draw.polygon([(cx + s//3 - fold, cy - s*3//5),
                      (cx + s//3, cy - s*3//5 + fold),
                      (cx + s//3 - fold, cy - s*3//5 + fold)], fill=(220, 230, 245))
        # 내용 줄
        for i, ly in enumerate([cy - s//3, cy - s//8, cy + s//10, cy + s//3]):
            w = s*2//3 - i * 20
            draw.rounded_rectangle([cx - s//4, ly, cx - s//4 + w, ly + 10],
                                   radius=4, fill=(200, 215, 230))
        # 파란 헤더 바
        draw.rounded_rectangle([cx - s//3 + 6, cy - s*3//5 + 8,
                                 cx + s//3 - fold - 4, cy - s*3//5 + 30],
                                radius=5, fill=(41, 128, 185))
        # 체크마크 (초록)
        draw.ellipse([cx + s//10, cy + s//5, cx + s//2, cy + s//2],
                     fill=(39, 174, 96))
        draw.line([cx + s//5, cy + s//3, cx + s//4 + 8, cy + s*5//12],
                  fill=(255,255,255), width=6)
        draw.line([cx + s//4 + 8, cy + s*5//12, cx + s*2//5, cy + s//4 + 5],
                  fill=(255,255,255), width=6)
        # 펜
        draw.polygon([(cx - s//5, cy + s//4), (cx - s//6, cy + s*7//12),
                      (cx - s//8, cy + s//4 + 8)], fill=(180, 140, 100))
        draw.polygon([(cx - s//5, cy + s//4), (cx + s//6, cy - s//4),
                      (cx + s//6 + 14, cy - s//4 + 14), (cx - s//8, cy + s//4 + 8)],
                    fill=(41, 128, 185))

    elif icon_type == "pension":
        # 돼지저금통 (분홍) + 동전 + ₩ 표시
        # 돼지 몸통
        draw.ellipse([cx - s*3//5, cy - s//3, cx + s*3//5, cy + s//2],
                     fill=(255, 182, 193))
        # 돼지 머리
        draw.ellipse([cx + s//3, cy - s*2//3, cx + s*3//4, cy - s//5],
                     fill=(255, 182, 193))
        # 코
        draw.ellipse([cx + s*9//16, cy - s//2, cx + s*3//4 - 8, cy - s//3],
                     fill=(255, 150, 160))
        draw.ellipse([cx + s*9//16 + 6, cy - s*5//12, cx + s*9//16 + 16, cy - s*5//12 + 10],
                     fill=(220, 100, 120))
        draw.ellipse([cx + s*9//16 + 22, cy - s*5//12, cx + s*9//16 + 32, cy - s*5//12 + 10],
                     fill=(220, 100, 120))
        # 귀
        draw.ellipse([cx + s//3 + 5, cy - s*3//4, cx + s//2, cy - s*2//3 + 5],
                     fill=(255, 150, 170))
        # 눈
        draw.ellipse([cx + s*7//12, cy - s*7//12, cx + s*7//12 + 10, cy - s*7//12 + 10],
                     fill=(80, 50, 50))
        # 동전 슬롯
        draw.rounded_rectangle([cx - s//8, cy - s//3 - 8, cx + s//8, cy - s//3 + 4],
                                radius=3, fill=(200, 140, 140))
        # 금색 동전들
        for i, (ox, oy, r) in enumerate([(cx - s//3, cy - s*2//3, 28),
                                          (cx - s//5, cy - s*3//5 - 15, 22),
                                          (cx, cy - s*3//4, 20)]):
            draw.ellipse([ox-r, oy-r, ox+r, oy+r], fill=(255, 215, 50))
            draw.ellipse([ox-r+5, oy-r+5, ox+r-5, oy+r-5], fill=(220, 180, 30))
        # ₩ 표시
        draw.text((cx - s//3 + 2, cy - s*2//3), "₩", font=load_font(22),
                  fill=(255,255,255), anchor="mm")
        # 발
        for fx in [cx - s//3, cx, cx + s//3]:
            draw.ellipse([fx - 14, cy + s//2 - 5, fx + 14, cy + s//2 + 18],
                         fill=(255, 160, 170))

    elif icon_type == "insurance":
        # 우산 (남색) + 빗방울 + 방패
        # 우산 캐노피
        draw.chord([cx - s*3//4, cy - s*3//4, cx + s*3//4, cy + s//8],
                   180, 360, fill=(30, 60, 160))
        # 우산 테두리
        draw.arc([cx - s*3//4, cy - s*3//4, cx + s*3//4, cy + s//8],
                 180, 360, fill=(50, 100, 220), width=6)
        # 살 (리브)
        for angle_deg in [-60, -30, 0, 30, 60]:
            import math
            rad = math.radians(angle_deg)
            ex = cx + int(math.sin(rad) * s*3//4)
            ey = cy + s//8 - int((1 - abs(math.cos(rad))) * s*7//8)
            draw.line([cx, cy - s//4, ex, ey], fill=(50, 100, 220), width=3)
        # 손잡이
        draw.line([cx, cy + s//8, cx, cy + s//2], fill=(30, 60, 160), width=8)
        draw.arc([cx - s//5, cy + s//3, cx + s//5, cy + s*3//4],
                 0, 180, fill=(30, 60, 160), width=8)
        # 빗방울
        for rx, ry in [(cx - s*2//3, cy + s//4), (cx - s//2, cy + s//3 + 10),
                        (cx + s//2, cy + s//5), (cx + s*2//3, cy + s//3),
                        (cx - s//3, cy + s//2), (cx + s//3, cy + s*2//5)]:
            draw.polygon([(rx, ry - 14), (rx - 8, ry + 8), (rx + 8, ry + 8)],
                         fill=(100, 150, 230))
        # 방패 (오른쪽 하단)
        sx, sy = cx + s*2//5, cy + s//4
        draw.polygon([(sx, sy - 30), (sx - 24, sy - 16), (sx - 24, sy + 10),
                      (sx, sy + 30), (sx + 24, sy + 10), (sx + 24, sy - 16)],
                     fill=(255, 210, 30))
        draw.text((sx, sy), "✓", font=load_font(28), fill=(30,60,160), anchor="mm")

    elif icon_type == "festival":
        # 추석 / 명절 — 한복 캐릭터 + 달 + 송편
        # 보름달
        draw.ellipse([cx + s//4, cy - s*3//4, cx + s*3//4, cy - s//4],
                     fill=(255, 220, 80))
        draw.ellipse([cx + s*3//8, cy - s*5//8, cx + s*5//8, cy - s*3//8],
                     fill=(240, 195, 60))
        # 한복 캐릭터 (머리+몸)
        hr = s // 7
        draw.ellipse([cx - s//4 - hr, cy - s//2 - hr, cx - s//4 + hr, cy - s//2 + hr],
                     fill=(255, 220, 177))
        # 한복 (빨간색 치마)
        draw.polygon([(cx - s//4 - hr, cy - s//2 + hr),
                      (cx - s//4 - s//3, cy + s//2),
                      (cx - s//4 + s//3, cy + s//2),
                      (cx - s//4 + hr, cy - s//2 + hr)], fill=(210, 40, 40))
        # 저고리 (흰색)
        draw.polygon([(cx - s//4 - hr + 4, cy - s//2 + hr),
                      (cx - s//4 - hr - 10, cy - s//8),
                      (cx - s//4 + hr + 10, cy - s//8),
                      (cx - s//4 + hr - 4, cy - s//2 + hr)], fill=(245, 245, 245))
        # 팔
        draw.line([cx - s//4 - hr - 2, cy - s//8, cx - s//2, cy + s//8],
                  fill=(245, 245, 245), width=14)
        draw.line([cx - s//4 + hr + 2, cy - s//8, cx, cy + s//8],
                  fill=(245, 245, 245), width=14)
        # 송편 3개
        for i, (px, py, col) in enumerate([
            (cx + s//5, cy + s//8, (154, 205, 50)),
            (cx + s*2//5, cy + s//5, (255, 182, 193)),
            (cx + s//5, cy + s//3, (210, 180, 140))]):
            draw.ellipse([px - 22, py - 14, px + 22, py + 14], fill=col)
            draw.arc([px - 14, py - 6, px + 14, py + 6], 0, 180, fill=(100,80,60), width=3)
        # 바구니
        draw.rounded_rectangle([cx + s//10, cy + s*2//5, cx + s*2//3, cy + s*2//3],
                                radius=10, fill=(180, 140, 80))
        for lx in range(cx + s//10 + 12, cx + s*2//3, 18):
            draw.line([lx, cy + s*2//5, lx, cy + s*2//3], fill=(140, 100, 50), width=3)

    elif icon_type == "calendar":
        # 달력 + 빨간 동그라미 날짜 + 별표
        # 달력 본체
        draw.rounded_rectangle([cx - s*3//5, cy - s*3//5, cx + s*3//5, cy + s//2],
                                radius=14, fill=(255, 255, 255))
        # 달력 헤더 (파란색)
        draw.rounded_rectangle([cx - s*3//5, cy - s*3//5, cx + s*3//5, cy - s//4],
                                radius=14, fill=(52, 120, 200))
        draw.rectangle([cx - s*3//5, cy - s//3, cx + s*3//5, cy - s//4],
                        fill=(52, 120, 200))
        # 달력 링
        for rx in [cx - s//3, cx, cx + s//3]:
            draw.rectangle([rx - 6, cy - s*3//5 - 14, rx + 6, cy - s*3//5 + 10],
                           fill=(80, 80, 80))
            draw.rounded_rectangle([rx - 6, cy - s*3//5 - 20, rx + 6, cy - s*3//5 - 4],
                                   radius=3, fill=(80, 80, 80))
        # 헤더 텍스트
        draw.text((cx, cy - s*5//12), "10월", font=load_font(28), fill=(255,255,255), anchor="mm")
        # 날짜 그리드
        days = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21]
        highlight = [3, 4, 5, 9, 10]  # 빨간 동그라미
        for i, d in enumerate(days[:21]):
            row, col = i // 7, i % 7
            dx = cx - s//2 + col * (s*6//35) + s*3//35
            dy = cy - s//6 + row * (s//5)
            if d in highlight:
                draw.ellipse([dx - 14, dy - 14, dx + 14, dy + 14], fill=(231, 76, 60))
                draw.text((dx, dy), str(d), font=load_font(18), fill=(255,255,255), anchor="mm")
            else:
                draw.text((dx, dy), str(d), font=load_font(16, bold=False),
                          fill=(80,80,80), anchor="mm")
        # 별 장식
        draw.text((cx + s*2//3, cy - s*2//3), "★", font=load_font(36),
                  fill=(255, 200, 30), anchor="mm")

    elif icon_type == "benefit":
        # 선물 박스 + 리본 + 별 + 동전
        # 박스 몸통 (빨간)
        draw.rounded_rectangle([cx - s//2, cy - s//6, cx + s//2, cy + s//2],
                                radius=12, fill=(220, 50, 50))
        # 박스 뚜껑
        draw.rounded_rectangle([cx - s*3//5, cy - s//3, cx + s*3//5, cy - s//6],
                                radius=8, fill=(180, 30, 30))
        # 리본 세로
        draw.rectangle([cx - s//10, cy - s//3, cx + s//10, cy + s//2],
                       fill=(255, 215, 0))
        # 리본 가로
        draw.rectangle([cx - s*3//5, cy - s//4, cx + s*3//5, cy - s//6 + s//10],
                       fill=(255, 215, 0))
        # 리본 매듭 (원)
        draw.ellipse([cx - s//6, cy - s//3 - 20, cx + s//6, cy - s//3 + 20],
                     fill=(255, 215, 0))
        # 리본 끝 2개
        draw.polygon([(cx - s//6, cy - s//3), (cx - s*2//5, cy - s*3//5),
                      (cx - s//4, cy - s//3 + 5)], fill=(255, 215, 0))
        draw.polygon([(cx + s//6, cy - s//3), (cx + s*2//5, cy - s*3//5),
                      (cx + s//4, cy - s//3 + 5)], fill=(255, 215, 0))
        # 별 장식들
        for sx, sy, sc in [(cx - s*2//3, cy - s//4, 28),
                            (cx + s*2//3, cy - s//3, 22),
                            (cx - s*3//5, cy + s//3, 18)]:
            draw.text((sx, sy), "★", font=load_font(sc), fill=(255,215,0), anchor="mm")
        # 동전 (오른쪽 아래)
        for i, (ox, oy) in enumerate([(cx + s*2//5, cy + s//5),
                                       (cx + s//2, cy + s//3),
                                       (cx + s*2//5 + 10, cy + s*2//5)]):
            draw.ellipse([ox - 18, oy - 18, ox + 18, oy + 18], fill=(255, 210, 30))
            draw.text((ox, oy), "₩", font=load_font(16), fill=(180,130,0), anchor="mm")

    elif icon_type == "invest":
        # 주식 차트 (상승 바) + 동전 + 화살표
        # 배경 차트 판
        draw.rounded_rectangle([cx - s*3//5, cy - s//2, cx + s*3//5, cy + s//2],
                                radius=14, fill=(255, 255, 255))
        # 막대 5개 (상승 트렌드)
        bar_heights = [s//5, s//3, s//4, s*2//5, s//2]
        bar_colors  = [(231,76,60),(39,174,96),(231,76,60),(39,174,96),(39,174,96)]
        for i, (bh, bc) in enumerate(zip(bar_heights, bar_colors)):
            bx = cx - s*2//5 + i * (s//5 + 4)
            draw.rounded_rectangle([bx, cy + s//2 - bh - 10, bx + s//5, cy + s//2 - 10],
                                   radius=5, fill=bc)
        # 상승 화살표 (오른쪽 상단)
        ax, ay = cx + s*3//5 + 10, cy - s*2//5
        draw.polygon([(ax - 14, ay + 20), (ax + 14, ay + 20), (ax, ay - 10)],
                     fill=(39, 174, 96))
        draw.line([ax, ay + 20, ax, ay + 45], fill=(39, 174, 96), width=8)
        # 금화 3개
        for i, (ox, oy) in enumerate([(cx - s*3//4, cy - s//3),
                                       (cx - s*3//4 + 12, cy - s//3 - 22),
                                       (cx - s*3//4 - 8, cy - s//3 - 40)]):
            draw.ellipse([ox - 20, oy - 20, ox + 20, oy + 20], fill=(255, 215, 30))
            draw.text((ox, oy), "₩", font=load_font(18), fill=(180,130,0), anchor="mm")

    elif icon_type == "health":
        # 덤벨 + 하트 + 달리는 사람
        # 덤벨
        for ox in [cx - s*2//5, cx + s*2//5]:
            draw.ellipse([ox - 28, cy - 28, ox + 28, cy + 28], fill=accent)
            draw.ellipse([ox - 22, cy - 20, ox + 22, cy + 20], fill=(200, 60, 50) if accent==(231,76,60) else (41,128,185))
        draw.rounded_rectangle([cx - s*2//5 + 24, cy - 14, cx + s*2//5 - 24, cy + 14],
                                radius=6, fill=(180, 180, 180))
        # 하트
        hx, hy, hhr = cx, cy - s*2//5, s//8
        draw.ellipse([hx - hhr, hy - hhr, hx, hy], fill=(231, 76, 60))
        draw.ellipse([hx, hy - hhr, hx + hhr, hy], fill=(231, 76, 60))
        draw.polygon([(hx - hhr, hy), (hx + hhr, hy), (hx, hy + hhr + 6)], fill=(231, 76, 60))
        # 달리는 사람 (오른쪽)
        px, py = cx + s*3//5, cy + s//10
        draw.ellipse([px - 14, py - s//2 - 14, px + 14, py - s//2 + 14],
                     fill=(255, 220, 177))
        draw.line([px, py - s//2 + 14, px - 10, py + 10], fill=(41,128,185), width=9)
        draw.line([px - 10, py + 10, px + 18, py + 30], fill=(41,128,185), width=9)
        draw.line([px - 10, py + 10, px - 22, py + 32], fill=(100,100,200), width=9)
        draw.line([px, py - s//4, px + 22, py - s//12], fill=(41,128,185), width=9)

    elif icon_type == "education":
        # 책 3권 + 졸업모자
        # 책 3권 쌓기
        book_data = [(cx - s//4, cy + s//4, (41,128,185)),
                     (cx - s//6, cy + s//8, (231,76,60)),
                     (cx - s//8, cy,        (39,174,96))]
        for bx, by, bc in book_data:
            draw.rounded_rectangle([bx, by - s//3, bx + s*2//5, by],
                                   radius=5, fill=bc)
            draw.rectangle([bx + 8, by - s//3, bx + 16, by], fill=(255,255,255,100))
        # 연필
        draw.polygon([(cx + s*2//5, cy + s//3), (cx + s*2//5 + 12, cy + s//2 + 10),
                      (cx + s//2, cy + s//3 + 8)], fill=(255, 215, 0))
        draw.polygon([(cx + s*2//5, cy + s//3), (cx + s*7//10, cy - s//6),
                      (cx + s*7//10 + 14, cy - s//6 + 14), (cx + s//2, cy + s//3 + 8)],
                     fill=(255, 215, 0))
        draw.line([cx + s*7//10, cy - s//6, cx + s*7//10 + 14, cy - s//6 + 14],
                  fill=(180, 120, 60), width=5)
        # 졸업 모자 (오른쪽 상단)
        draw.polygon([(cx + s//8, cy - s*3//5), (cx + s*3//4, cy - s*3//5),
                      (cx + s*7//12, cy - s*3//4), (cx + s//4, cy - s*3//4)],
                     fill=(30, 30, 80))
        draw.rectangle([cx + s*5//16, cy - s*3//4 - 8, cx + s*5//16 + s//5, cy - s*3//4],
                       fill=(30, 30, 80))
        draw.ellipse([cx + s*7//16 - 10, cy - s*3//4 - 24,
                      cx + s*7//16 + 10, cy - s*3//4 - 4], fill=(30, 30, 80))
        draw.text((cx + s*7//16, cy - s*5//8), "★", font=load_font(22),
                  fill=(255, 215, 0), anchor="mm")

    elif icon_type == "pet":
        # 강아지 얼굴 + 발자국 + 하트
        # 얼굴
        draw.ellipse([cx - s//2, cy - s//2, cx + s//2, cy + s//3],
                     fill=(210, 170, 110))
        # 귀 2개
        draw.ellipse([cx - s//2 - 10, cy - s//2, cx - s//8, cy - s//8],
                     fill=(185, 140, 80))
        draw.ellipse([cx + s//8, cy - s//2, cx + s//2 + 10, cy - s//8],
                     fill=(185, 140, 80))
        # 눈
        for ex in [cx - s//6, cx + s//6]:
            draw.ellipse([ex - 14, cy - s//4 - 14, ex + 14, cy - s//4 + 14],
                         fill=(50, 30, 10))
            draw.ellipse([ex + 4, cy - s//4 - 8, ex + 10, cy - s//4 - 2],
                         fill=(255, 255, 255))
        # 코
        draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 10], fill=(80, 50, 30))
        # 입
        draw.arc([cx - 20, cy, cx + 20, cy + 28], 0, 180, fill=(80,50,30), width=4)
        # 발자국 (왼쪽 하단)
        for px, py in [(cx - s*3//5, cy + s*2//5), (cx - s*2//5, cy + s//2)]:
            draw.ellipse([px-12, py-8, px+12, py+8], fill=(185,140,80))
            for dx, dy in [(-10,-14),(0,-18),(10,-14)]:
                draw.ellipse([px+dx-6, py+dy-6, px+dx+6, py+dy+6], fill=(185,140,80))
        # 하트
        hx, hy, hhr = cx + s*2//5, cy - s*2//5, s//10
        draw.ellipse([hx - hhr, hy - hhr, hx, hy], fill=(231, 76, 60))
        draw.ellipse([hx, hy - hhr, hx + hhr, hy], fill=(231, 76, 60))
        draw.polygon([(hx-hhr, hy), (hx+hhr, hy), (hx, hy+hhr+5)], fill=(231,76,60))

    elif icon_type == "shopping":
        # 쇼핑카트 + 상품 + 가격표
        # 카트 바구니
        draw.rounded_rectangle([cx - s*2//5, cy - s//4, cx + s*2//5, cy + s//3],
                                radius=10, fill=(255, 255, 255))
        draw.rectangle([cx - s*2//5, cy, cx + s*2//5, cy + s//3], fill=(240, 240, 245))
        # 카트 손잡이
        draw.arc([cx - s//2, cy - s*2//3, cx + s//4, cy - s//4],
                 270, 360, fill=(80, 80, 80), width=8)
        draw.line([cx + s//4, cy - s*5//12, cx + s//4, cy - s//4],
                  fill=(80,80,80), width=8)
        # 바퀴
        for wx in [cx - s//4, cx + s//4]:
            draw.ellipse([wx - 14, cy + s//3 - 4, wx + 14, cy + s//3 + 24],
                         fill=(80, 80, 80))
        # 상품 (카트 안)
        for px, pby, pc in [(cx - s//5, cy, (231,76,60)),
                             (cx + s//10, cy - s//10, (39,174,96)),
                             (cx + s//4 - 5, cy + s//10, (41,128,185))]:
            draw.rounded_rectangle([px - 18, pby - 20, px + 18, pby + 10],
                                   radius=5, fill=pc)
        # 가격표 (오른쪽 상단)
        draw.rounded_rectangle([cx + s//3, cy - s*3//5, cx + s*4//5, cy - s//4],
                                radius=8, fill=(231, 76, 60))
        draw.ellipse([cx + s//3, cy - s*7//12, cx + s//3 + 16, cy - s*7//12 + 16],
                     fill=(255, 255, 255))
        draw.text((cx + s*7//12, cy - s*5//12), "SALE", font=load_font(20),
                  fill=(255,255,255), anchor="mm")

    elif icon_type == "delivery":
        # 택배 박스 + 배달 오토바이
        # 박스
        draw.rounded_rectangle([cx - s*2//5, cy - s//8, cx + s*2//5, cy + s*2//5],
                                radius=10, fill=(210, 170, 80))
        # 박스 뚜껑선
        draw.line([cx - s*2//5, cy - s//8 + s//6, cx + s*2//5, cy - s//8 + s//6],
                  fill=(180, 140, 50), width=4)
        # 박스 테이프
        draw.line([cx, cy - s//8, cx, cy + s*2//5], fill=(100, 160, 220), width=6)
        draw.line([cx - s*2//5, cy - s//8 + s//6 - 3,
                   cx + s*2//5, cy - s//8 + s//6 - 3], fill=(100,160,220), width=6)
        # 배달 오토바이 (오른쪽)
        # 몸체
        draw.rounded_rectangle([cx + s//3, cy + s//10, cx + s*4//5, cy + s//3],
                                radius=10, fill=(50, 60, 80))
        # 바퀴 2개
        draw.ellipse([cx + s//3 - 4, cy + s//4, cx + s//3 + 30, cy + s//4 + 30],
                     fill=(40, 40, 40))
        draw.ellipse([cx + s*4//5 - 12, cy + s//4, cx + s*4//5 + 18, cy + s//4 + 30],
                     fill=(40, 40, 40))
        # 화살표 (배달 이동 중)
        draw.polygon([(cx - s*3//5, cy + s//8), (cx - s*3//5 - 16, cy + s//8 - 12),
                      (cx - s*3//5 - 16, cy + s//8 + 12)], fill=(39, 174, 96))

    elif icon_type == "wedding":
        # 반지 2개 + 하트 + 꽃다발
        # 반지 2개 (겹치게)
        for ox, oc in [(cx - s//8, (255, 215, 50)), (cx + s//8, (220, 220, 240))]:
            # 바깥 원 → 안쪽 원 순서로 그려서 "링" 모양
            draw.ellipse([ox - s//5, cy - s//3, ox + s//5, cy + s//4], fill=oc)
            draw.ellipse([ox - s//5 + 14, cy - s//3 + 14,
                          ox + s//5 - 14, cy + s//4 - 14],
                         fill=(255, 245, 220))
            # 보석
            draw.polygon([(ox, cy - s//3 - 4), (ox - 10, cy - s//3 + 8),
                          (ox + 10, cy - s//3 + 8)], fill=(100, 180, 255))
        # 큰 하트 (위)
        hx, hy, hhr = cx, cy - s*2//3, s//6
        draw.ellipse([hx - hhr, hy - hhr, hx, hy], fill=(231, 76, 60))
        draw.ellipse([hx, hy - hhr, hx + hhr, hy], fill=(231, 76, 60))
        draw.polygon([(hx-hhr, hy), (hx+hhr, hy), (hx, hy+hhr+8)], fill=(231,76,60))
        # 꽃다발 (왼쪽 하단)
        for px, py, pc in [(cx - s*2//5, cy + s//4, (231,76,60)),
                            (cx - s*3//5, cy + s//6, (255,182,193)),
                            (cx - s//2, cy + s*2//5, (255,150,150))]:
            draw.ellipse([px - 18, py - 18, px + 18, py + 18], fill=pc)
        draw.line([cx - s//2, cy + s*2//5, cx - s*2//5, cy + s*2//3],
                  fill=(39,174,96), width=8)
        # 작은 별 장식
        for sx, sy in [(cx + s*3//5, cy - s*2//5), (cx + s*4//5, cy)]:
            draw.text((sx, sy), "✦", font=load_font(26), fill=(255,215,50), anchor="mm")

    elif icon_type == "local":
        # 지도 핀 + 건물 + 지도
        # 지도 배경
        draw.rounded_rectangle([cx - s*3//5, cy - s//4, cx + s*2//5, cy + s*2//5],
                                radius=10, fill=(200, 230, 200))
        # 도로
        draw.rectangle([cx - s*3//5, cy + s//10, cx + s*2//5, cy + s//5],
                       fill=(220, 220, 220))
        draw.line([cx - s*3//5, cy + s//8, cx + s*2//5, cy + s//8],
                  fill=(255,255,150), width=3)
        # 건물 2채
        for bx, bh, bc in [(cx - s//3, s//3, (180,200,220)),
                             (cx - s//8, s//4, (200,210,200))]:
            draw.rectangle([bx, cy + s//10 - bh, bx + s//6, cy + s//10], fill=bc)
            for wy in range(cy + s//10 - bh + 5, cy + s//10, 15):
                draw.rectangle([bx + 4, wy, bx + 10, wy + 8], fill=(150,180,210))
        # 큰 핀 (오른쪽)
        draw.ellipse([cx + s//4, cy - s*3//4, cx + s*4//5, cy - s//5],
                     fill=accent)
        draw.polygon([(cx + s*13//32, cy - s//5),
                      (cx + s*19//32, cy - s//5),
                      (cx + s*8//16, cy + s//10)],
                     fill=accent)
        # 핀 안 원
        draw.ellipse([cx + s*3//8, cy - s*5//8, cx + s*19//32, cy - s*3//8],
                     fill=(255, 255, 255))

    elif icon_type == "bank":
        # 은행 건물 + ATM + 동전
        # 건물 본체
        draw.rectangle([cx - s//2, cy - s//3, cx + s//2, cy + s//2],
                       fill=(245, 245, 240))
        # 기둥 3개
        for col in [-s//4, 0, s//4]:
            draw.rectangle([cx + col - 8, cy - s//3, cx + col + 8, cy + s//2],
                           fill=(220, 215, 200))
        # 지붕 (삼각형 + 수평선)
        draw.polygon([(cx - s*3//5, cy - s//3), (cx, cy - s*3//4),
                      (cx + s*3//5, cy - s//3)], fill=(180, 170, 150))
        draw.rectangle([cx - s*3//5, cy - s//3 - 6, cx + s*3//5, cy - s//3 + 6],
                       fill=(150, 140, 120))
        # ATM 기기 (오른쪽)
        draw.rounded_rectangle([cx + s//3, cy - s//6, cx + s*4//5, cy + s//3],
                                radius=8, fill=(50, 60, 80))
        draw.rounded_rectangle([cx + s//3 + 6, cy - s//6 + 8,
                                 cx + s*4//5 - 6, cy + s//20],
                                radius=5, fill=(100, 150, 220))
        draw.rounded_rectangle([cx + s//3 + 10, cy + s//12,
                                 cx + s*4//5 - 10, cy + s//5],
                                radius=3, fill=(220, 220, 220))
        # ₩ 표시
        draw.text((cx - s//8, cy + s//10), "₩", font=load_font(48),
                  fill=accent, anchor="mm")

    elif icon_type == "nature":
        # 나무 + 꽃 + 해
        # 태양
        draw.ellipse([cx + s//3, cy - s*3//4, cx + s*3//4, cy - s//4],
                     fill=(255, 220, 50))
        # 나무 줄기
        draw.rectangle([cx - s//16, cy + s//10, cx + s//16, cy + s//2],
                       fill=(120, 80, 40))
        # 나무 잎 (3층)
        for layer, (lcy, lr, lc) in enumerate([
            (cy + s//10, s*2//5, (56,142,50)),
            (cy - s//8,  s//3,   (76,175,50)),
            (cy - s*3//8, s//5,  (102,187,106))]):
            draw.ellipse([cx - lr, lcy - lr, cx + lr, lcy + lr], fill=lc)
        # 꽃 3송이 (왼쪽)
        for fx, fy, fc in [(cx - s*3//5, cy + s//4, (231,76,60)),
                            (cx - s*2//5, cy + s*2//5, (255,182,193)),
                            (cx - s*3//4, cy + s*2//5, (255,152,0))]:
            for angle in range(0, 360, 72):
                import math
                px = fx + int(math.cos(math.radians(angle)) * 14)
                py = fy + int(math.sin(math.radians(angle)) * 14)
                draw.ellipse([px-8, py-8, px+8, py+8], fill=fc)
            draw.ellipse([fx-7, fy-7, fx+7, fy+7], fill=(255,230,50))
            draw.line([fx, fy+8, fx, fy+30], fill=(56,142,50), width=5)

    elif icon_type == "hospital":
        # 병원 건물 + 빨간 십자 + 앰뷸런스
        draw.rectangle([cx - s//2, cy - s//3, cx + s//2, cy + s//2], fill=(245,245,245))
        draw.rectangle([cx - s//2, cy - s//2, cx + s//2, cy - s//3], fill=accent)
        draw.text((cx, cy - s*5//12), "병원", font=load_font(24), fill=(255,255,255), anchor="mm")
        draw.rectangle([cx - 10, cy - s//5, cx + 10, cy + s//8], fill=accent)
        draw.rectangle([cx - s//5, cy - s//16, cx + s//5, cy + s//16], fill=accent)
        for wx in [cx - s//3, cx + s//10]:
            draw.rectangle([wx, cy - s//8, wx + s//6, cy + s//10], fill=(155,215,245))
        draw.rounded_rectangle([cx - s*3//5, cy + s//5, cx - s//10, cy + s//2],
                                radius=6, fill=(255,255,255))
        draw.rectangle([cx - s*3//5, cy + s//5, cx - s//4, cy + s*2//5], fill=accent)
        draw.text((cx - s*7//16, cy + s*7//20), "+", font=load_font(20),
                  fill=(255,255,255), anchor="mm")
        for wx in [cx - s*2//5, cx - s//5]:
            draw.ellipse([wx - 4, cy + s*2//5, wx + 18, cy + s*2//5 + 22], fill=(40,40,40))

    elif icon_type == "medicine":
        # 약봉지 + 알약 + 처방전
        draw.rounded_rectangle([cx - s//3, cy - s//3, cx + s//3, cy + s*2//5],
                                radius=10, fill=(255,255,255))
        draw.rounded_rectangle([cx - s//3, cy - s//3, cx + s//3, cy - s//6],
                                radius=10, fill=accent)
        draw.rectangle([cx - s//3, cy - s//4, cx + s//3, cy - s//6], fill=accent)
        draw.text((cx, cy - s*5//24), "처방약", font=load_font(18),
                  fill=(255,255,255), anchor="mm")
        for px, py, pc in [(cx - s//6, cy + s//12, (231,76,60)),
                            (cx + s//6, cy + s//12, (41,128,185)),
                            (cx, cy + s//4, (39,174,96))]:
            draw.ellipse([px - 18, py - 10, px + 18, py + 10], fill=pc)
            draw.line([px, py - 10, px, py + 10], fill=(255,255,255), width=3)
        draw.rounded_rectangle([cx + s//4, cy - s//2, cx + s*3//4, cy + s//8],
                                radius=6, fill=(255,252,240))
        draw.text((cx + s//2, cy - s*3//8), "Rx", font=load_font(28),
                  fill=(41,128,185), anchor="mm")

    elif icon_type == "baby":
        # 아기 요람 + 젖병 + 별
        draw.chord([cx - s//2, cy, cx + s//2, cy + s*2//3], 0, 180, fill=(255,220,200))
        draw.ellipse([cx - s//5, cy - s//5, cx + s//5, cy + s//5],
                     fill=(255,220,177))
        for ex in [cx - s//10, cx + s//20]:
            draw.ellipse([ex, cy - s//10, ex + 8, cy - s//10 + 8], fill=(80,50,30))
        draw.arc([cx - s//8, cy, cx + s//8, cy + s//8], 0, 180, fill=(200,100,100), width=3)
        draw.chord([cx - s//2 + 5, cy + 5, cx + s//2 - 5, cy + s*2//3 - 5],
                   0, 180, fill=(200,230,255))
        draw.rounded_rectangle([cx + s//3, cy - s//2, cx + s*3//5, cy + s//8],
                                radius=10, fill=(255,255,255))
        draw.rounded_rectangle([cx + s*3//8, cy - s*5//8, cx + s*8//16, cy - s//2 + 5],
                                radius=5, fill=(230,230,230))
        draw.rectangle([cx + s//3, cy - s//3, cx + s*3//5, cy - s//8], fill=(200,235,255))
        for sx, sy in [(cx - s*2//3, cy - s//3), (cx - s//2, cy - s*3//5)]:
            draw.text((sx, sy), "★", font=load_font(22), fill=(255,215,50), anchor="mm")

    elif icon_type == "school":
        # 학교 건물 + 시계 + 별
        draw.rectangle([cx - s*3//4, cy + s*2//5, cx + s*3//4, cy + s*3//5],
                       fill=(34,139,34))
        draw.rectangle([cx - s//2, cy - s//3, cx + s//2, cy + s*2//5],
                       fill=(220,200,170))
        draw.polygon([(cx - s*3//5, cy - s//3), (cx, cy - s*3//4), (cx + s*3//5, cy - s//3)],
                     fill=accent)
        for wx in [cx - s//3, cx - s//10, cx + s//8]:
            draw.rectangle([wx, cy - s//5, wx + s//8, cy + s//10], fill=(155,215,245))
        draw.rectangle([cx - s//8, cy + s//8, cx + s//8, cy + s*2//5], fill=(120,78,35))
        draw.ellipse([cx - 20, cy - s*11//16, cx + 20, cy - s*7//16], fill=(255,255,255))
        draw.line([cx, cy - s*9//16, cx, cy - s*11//16 + 20], fill=(50,50,50), width=3)
        draw.line([cx, cy - s*9//16, cx + 12, cy - s*9//16 - 4], fill=(50,50,50), width=3)
        draw.text((cx + s//2 + 10, cy - s//2), "★", font=load_font(28),
                  fill=(255,215,50), anchor="mm")

    elif icon_type == "office":
        # 빌딩 2동 + 명함
        draw.rectangle([cx + s//8, cy - s*3//4, cx + s*3//4, cy + s//2],
                       fill=(180,200,220))
        for row in range(5):
            for col in range(3):
                wx = cx + s//8 + 10 + col * (s//6)
                wy = cy - s*3//4 + 10 + row * (s//5)
                draw.rectangle([wx, wy, wx + s//8, wy + s//8], fill=(155,215,245))
        draw.rectangle([cx - s*3//4, cy - s//2, cx + s//8, cy + s//2],
                       fill=(200,215,225))
        for row in range(3):
            for col in range(2):
                wx = cx - s*3//4 + 10 + col * (s//5)
                wy = cy - s//2 + 10 + row * (s//5)
                draw.rectangle([wx, wy, wx + s//8, wy + s//8], fill=(155,215,245))
        draw.rounded_rectangle([cx - s//3, cy + s//8, cx + s//4, cy + s*2//5],
                                radius=5, fill=(255,255,255))
        draw.rounded_rectangle([cx - s//3 + 5, cy + s//8 + 5,
                                 cx + s//4 - 5, cy + s//8 + 14],
                                radius=3, fill=accent)

    elif icon_type == "phone":
        # 스마트폰 + 말풍선
        draw.rounded_rectangle([cx - s*2//5, cy - s//2, cx + s//8, cy + s*2//5],
                                radius=14, fill=(50,60,80))
        draw.rounded_rectangle([cx - s*2//5 + 6, cy - s//2 + 6,
                                 cx + s//8 - 6, cy + s*2//5 - 16],
                                radius=10, fill=(100,150,220))
        draw.ellipse([cx - s//8 - 10, cy + s*2//5 - 14,
                      cx - s//8 + 10, cy + s*2//5 + 2], fill=(70,80,100))
        draw.rounded_rectangle([cx + s//5, cy - s*2//5, cx + s*4//5, cy - s//8],
                                radius=10, fill=(255,255,255))
        draw.polygon([(cx + s//4, cy - s//8), (cx + s//4 + 14, cy - s//8 + 20),
                      (cx + s//4 + 28, cy - s//8)], fill=(255,255,255))
        for i in range(3):
            draw.ellipse([cx + s//4 + i*18, cy - s*5//16 - 4,
                          cx + s//4 + i*18 + 10, cy - s*5//16 + 6], fill=(150,150,150))
        draw.text((cx - s//8 - 2, cy - s//8), "☎", font=load_font(32),
                  fill=(255,255,255), anchor="mm")

    elif icon_type == "certificate":
        # 자격증 + 도장 + 리본
        draw.rounded_rectangle([cx - s*2//5, cy - s*2//5, cx + s*2//5, cy + s*2//5],
                                radius=10, fill=(255,248,220))
        draw.rounded_rectangle([cx - s*2//5, cy - s*2//5, cx + s*2//5, cy - s//5],
                                radius=10, fill=accent)
        draw.rectangle([cx - s*2//5, cy - s//4, cx + s*2//5, cy - s//5], fill=accent)
        draw.text((cx, cy - s*5//16), "자격증", font=load_font(22),
                  fill=(255,255,255), anchor="mm")
        for i, ly in enumerate([cy - s//8, cy, cy + s//8]):
            draw.rounded_rectangle([cx - s//4, ly - 4, cx + s//4, ly + 6],
                                   radius=3, fill=(200,210,220))
        draw.ellipse([cx + s//5, cy + s//5, cx + s*2//3, cy + s*7//12],
                     fill=(231,76,60))
        draw.ellipse([cx + s//5 + 8, cy + s//5 + 8,
                      cx + s*2//3 - 8, cy + s*7//12 - 8], fill=(200,40,40))
        draw.text((cx + s*13//24, cy + s*3//8), "인", font=load_font(24),
                  fill=(255,220,220), anchor="mm")
        draw.ellipse([cx - s*2//3, cy + s//4, cx - s//3, cy + s*2//3],
                     fill=(255,215,0))
        draw.text((cx - s//2, cy + s*11//24), "★", font=load_font(22),
                  fill=(230,160,0), anchor="mm")

    elif icon_type == "farm":
        # 텃밭 + 작물 + 트랙터
        draw.rectangle([cx - s*3//4, cy + s//8, cx + s*3//4, cy + s*3//5],
                       fill=(120,80,30))
        for i in range(4):
            ry = cy + s//8 + i * (s//8)
            draw.line([cx - s*3//4, ry, cx + s*3//4, ry], fill=(100,60,20), width=3)
        for px, py, pc in [(cx - s//2, cy + s//16, (34,139,34)),
                            (cx - s//4, cy, (39,174,96)),
                            (cx, cy + s//16, (34,139,34)),
                            (cx + s//4, cy, (46,180,70))]:
            draw.line([px, py + 20, px, cy + s//8], fill=(56,142,50), width=5)
            draw.ellipse([px - 14, py - 8, px + 14, py + 16], fill=pc)
        draw.ellipse([cx + s//3, cy - s*3//4, cx + s*3//4, cy - s//3],
                     fill=(255,215,50))
        draw.rounded_rectangle([cx - s*3//4, cy - s//4, cx - s//4, cy + s//8],
                                radius=8, fill=accent)
        draw.ellipse([cx - s*3//4 + 5, cy + s//8 - 5,
                      cx - s*3//4 + 35, cy + s//8 + 25], fill=(40,40,40))
        draw.ellipse([cx - s//3 - 5, cy + s//8,
                      cx - s//3 + 20, cy + s//8 + 25], fill=(40,40,40))

    elif icon_type == "repair":
        # 공구 (렌치+드라이버) + 톱니바퀴
        import math as _math
        for angle in range(0, 360, 30):
            rad = _math.radians(angle)
            gx = cx + int(_math.cos(rad) * (s//3 + 10))
            gy = cy + int(_math.sin(rad) * (s//3 + 10))
            draw.ellipse([gx - 10, gy - 10, gx + 10, gy + 10], fill=(150,150,150))
        draw.ellipse([cx - s//3, cy - s//3, cx + s//3, cy + s//3], fill=(150,150,150))
        draw.ellipse([cx - s//5, cy - s//5, cx + s//5, cy + s//5], fill=(200,200,200))
        draw.rounded_rectangle([cx - s*3//5, cy - s//8, cx + s//20, cy + s//8],
                                radius=8, fill=(70,70,80))
        draw.ellipse([cx + s//20 - 20, cy - s//5, cx + s//20 + 20, cy + s//5],
                     fill=(70,70,80))
        draw.ellipse([cx + s//20 - 12, cy - s//8, cx + s//20 + 12, cy + s//8],
                     fill=(180,180,190))
        draw.line([cx - s*2//5, cy - s*2//5, cx + s//3, cy + s//3],
                  fill=(180,120,50), width=12)
        draw.polygon([(cx + s//3 - 8, cy + s//3 - 8),
                      (cx + s//3 + 8, cy + s//3 + 8),
                      (cx + s//3 + 16, cy + s//3 - 4),
                      (cx + s//3, cy + s//3 - 16)], fill=(100,100,120))

    elif icon_type == "clothes":
        # 옷걸이 + 셔츠 + 가격표
        draw.arc([cx - s//6, cy - s*3//4, cx + s//6, cy - s//3],
                 0, 180, fill=(150,150,150), width=6)
        draw.line([cx - s//2, cy - s//3, cx + s//2, cy - s//3],
                  fill=(150,150,150), width=5)
        draw.polygon([(cx - s//3, cy - s//3), (cx - s//2, cy - s//6),
                      (cx - s//2, cy + s//3), (cx + s//2, cy + s//3),
                      (cx + s//2, cy - s//6), (cx + s//3, cy - s//3),
                      (cx + s//6, cy - s//6), (cx - s//6, cy - s//6)], fill=accent)
        draw.polygon([(cx - s//6, cy - s//6), (cx, cy + s//12), (cx + s//6, cy - s//6)],
                     fill=(255,255,255))
        for by in [cy + s//20, cy + s//8, cy + s//5]:
            draw.ellipse([cx - 6, by - 6, cx + 6, by + 6], fill=(200,220,240))
        draw.rounded_rectangle([cx + s//3, cy - s//6, cx + s*3//5, cy + s//8],
                                radius=5, fill=(255,248,220))
        draw.line([cx + s*13//24, cy - s//6, cx + s*13//24, cy - s//3],
                  fill=(150,100,50), width=3)

    elif icon_type == "receipt":
        # 영수증 + ₩ 표시 + 도장
        pts = [(cx - s//4, cy - s*2//5), (cx + s//4, cy - s*2//5),
               (cx + s//4, cy + s*2//5)]
        for i in range(6):
            x = cx + s//4 - i * (s//12)
            y = cy + s*2//5 + (8 if i % 2 == 0 else 0)
            pts.append((x, y))
        pts.append((cx - s//4, cy + s*2//5))
        draw.polygon(pts, fill=(255,252,240))
        draw.rectangle([cx - s//4, cy - s*2//5, cx + s//4, cy - s//5], fill=accent)
        draw.text((cx, cy - s*7//24), "영수증", font=load_font(18),
                  fill=(255,255,255), anchor="mm")
        for i, ly in enumerate([cy - s//8, cy, cy + s//8]):
            draw.rounded_rectangle([cx - s//5, ly - 4, cx + s//5, ly + 5],
                                   radius=2, fill=(220,220,220))
        draw.text((cx + s//2 + 5, cy + s//5), "₩", font=load_font(44),
                  fill=accent, anchor="mm")
        draw.ellipse([cx + s//6, cy + s//4, cx + s//2, cy + s*3//5],
                     fill=(231,76,60))
        draw.text((cx + s//3, cy + s*5//12), "완납", font=load_font(18),
                  fill=(255,220,220), anchor="mm")

    elif icon_type == "news":
        # 신문 + 확성기
        draw.rounded_rectangle([cx - s*3//5, cy - s*2//5, cx + s//4, cy + s*2//5],
                                radius=8, fill=(245,242,230))
        draw.rectangle([cx - s*3//5, cy - s*2//5, cx + s//4, cy - s//5],
                       fill=accent)
        draw.text((cx - s//5, cy - s*7//20), "뉴스", font=load_font(22),
                  fill=(255,255,255), anchor="mm")
        for i, ly in enumerate([cy - s//8, cy, cy + s//8, cy + s//4]):
            w = s*5//6 - i * 20
            draw.rounded_rectangle([cx - s*3//5 + 8, ly - 4, cx - s*3//5 + 8 + w, ly + 4],
                                   radius=2, fill=(180,180,170))
        draw.polygon([(cx + s//6, cy - s//5), (cx + s//6, cy + s//5),
                      (cx + s//2, cy + s//3), (cx + s//2, cy - s//3)], fill=accent)
        draw.ellipse([cx + s//6 - 14, cy - s//6, cx + s//6 + 14, cy + s//6], fill=accent)
        for r in [s//6, s//4]:
            draw.arc([cx + s//2 - r, cy - r, cx + s//2 + r, cy + r],
                     -30, 30, fill=accent, width=5)
        draw.ellipse([cx + s*2//5, cy - s*2//5 - 14,
                      cx + s*2//5 + 20, cy - s*2//5 + 6], fill=(231,76,60))

    elif icon_type == "vacation":
        # 해변 + 파라솔 + 파도
        draw.rectangle([cx - s*3//4, cy - s*3//4, cx + s*3//4, cy + s//8],
                       fill=(135,206,235))
        draw.ellipse([cx + s//4, cy - s*3//4, cx + s*3//4, cy - s//4],
                     fill=(255,220,50))
        draw.rectangle([cx - s*3//4, cy + s//8, cx + s*3//4, cy + s*3//5],
                       fill=(30,144,255))
        for i in range(3):
            wy = cy + s//8 + i * 15
            draw.arc([cx - s//2 + i*30, wy, cx - s//4 + i*30, wy + 20],
                     0, 180, fill=(100,180,255), width=4)
        draw.rectangle([cx - s*3//4, cy + s//4, cx + s*3//4, cy + s*3//5],
                       fill=(238,214,175))
        draw.line([cx - s//4, cy - s//4, cx - s//4, cy + s//4],
                  fill=(150,100,50), width=6)
        draw.chord([cx - s*3//5, cy - s*2//5, cx + s//8, cy - s//8],
                   180, 360, fill=accent)

    elif icon_type == "art":
        # 팔레트 + 붓
        draw.ellipse([cx - s*2//5, cy - s//4, cx + s*2//5, cy + s*2//5],
                     fill=(245,235,220))
        draw.ellipse([cx - s//5, cy + s//8, cx + s//8, cy + s*3//8], fill=(245,235,220))
        for px, py, pc in [
            (cx - s//4, cy - s//8, (231,76,60)),
            (cx + s//4, cy - s//8, (41,128,185)),
            (cx, cy - s//4, (39,174,96)),
            (cx + s//3, cy + s//12, (243,156,18)),
            (cx - s//3, cy + s//12, (142,68,173))]:
            draw.ellipse([px - 14, py - 14, px + 14, py + 14], fill=pc)
        draw.line([cx + s//8, cy + s*2//5, cx + s*3//5, cy - s*2//5],
                  fill=(150,100,50), width=8)
        draw.polygon([(cx + s//8 - 8, cy + s*2//5),
                      (cx + s//8 + 8, cy + s*2//5 + 8),
                      (cx + s//8 + 12, cy + s*3//5)], fill=accent)
        draw.text((cx - s*3//5, cy - s*2//5), "✦", font=load_font(32),
                  fill=(255,215,50), anchor="mm")

    elif icon_type == "clean":
        # 빗자루 + 거품 + 스프레이
        draw.line([cx - s//4, cy - s*3//5, cx + s//4, cy + s//3],
                  fill=(150,100,50), width=8)
        draw.polygon([(cx - s//5, cy + s//8), (cx + s//4, cy + s//3),
                      (cx + s//3, cy + s//5), (cx + s//5, cy - s//8)],
                     fill=(180,120,60))
        for bx, by, br in [(cx - s//3, cy - s//4, 22), (cx - s//2, cy - s//8, 16),
                            (cx - s*2//5, cy + s//12, 20), (cx - s//5, cy + s//6, 14)]:
            draw.ellipse([bx-br, by-br, bx+br, by+br], fill=(200,235,255))
            draw.arc([bx-br+4, by-br+4, bx+br-4, by+br-4],
                     200, 340, fill=(150,200,240), width=3)
        draw.rounded_rectangle([cx + s//3, cy - s//8, cx + s*3//4, cy + s*2//5],
                                radius=10, fill=accent)
        draw.rounded_rectangle([cx + s//3, cy - s//8, cx + s*3//4, cy + s//8],
                                radius=10, fill=(int(accent[0]*0.8), int(accent[1]*0.8), int(accent[2]*0.8)))
        for dx, dy in [(-30,-35),(-15,-42),(-40,-20)]:
            draw.ellipse([cx + s//3 + dx - 5, cy - s//8 + dy - 5,
                          cx + s//3 + dx + 5, cy - s//8 + dy + 5], fill=(150,230,255))

    elif icon_type == "game":
        # 게임 컨트롤러
        draw.rounded_rectangle([cx - s*2//5, cy - s//5, cx + s*2//5, cy + s//4],
                                radius=20, fill=(50,50,70))
        for dx, dy in [(0,-18),(0,18),(-18,0),(18,0)]:
            draw.rounded_rectangle([cx - s//4 + dx - 10, cy + dy - 10,
                                     cx - s//4 + dx + 10, cy + dy + 10],
                                   radius=4, fill=(80,80,100))
        for bx, by, bc in [(cx+s//4-10, cy-14, (231,76,60)),
                            (cx+s//4+10, cy+5,  (41,128,185)),
                            (cx+s//4-10, cy+24, (39,174,96)),
                            (cx+s//4-30, cy+5,  (243,156,18))]:
            draw.ellipse([bx-10, by-10, bx+10, by+10], fill=bc)
        for jx in [cx - s//5, cx + s//8]:
            draw.ellipse([jx - 16, cy + s//6, jx + 16, cy + s//6 + 32], fill=(70,70,90))
            draw.ellipse([jx - 10, cy + s//6 + 5, jx + 10, cy + s//6 + 22],
                         fill=(90,90,110))
        draw.text((cx, cy - s*2//5), "▶ PLAY", font=load_font(22),
                  fill=(255,215,50), anchor="mm")

    elif icon_type == "book":
        # 펼쳐진 책 + 북마크 + 돋보기
        draw.rounded_rectangle([cx - s*2//5, cy - s//4, cx, cy + s*2//5],
                                radius=8, fill=(255,255,255))
        draw.rounded_rectangle([cx, cy - s//4, cx + s*2//5, cy + s*2//5],
                                radius=8, fill=(255,252,240))
        draw.line([cx, cy - s//4, cx, cy + s*2//5], fill=(200,190,180), width=4)
        draw.rounded_rectangle([cx - s*2//5 - 6, cy - s*5//16,
                                 cx - s*2//5 + 6, cy + s*7//16],
                                radius=4, fill=accent)
        for i, ly in enumerate([cy - s//10, cy + s//20, cy + s//8]):
            draw.rounded_rectangle([cx - s//3, ly - 3, cx - s//16, ly + 4],
                                   radius=2, fill=(200,210,220))
            draw.rounded_rectangle([cx + s//16, ly - 3, cx + s//3, ly + 4],
                                   radius=2, fill=(200,210,220))
        draw.polygon([(cx + s//3, cy - s//4), (cx + s//3 + 16, cy - s//4),
                      (cx + s//3 + 16, cy + s//8), (cx + s//3 + 8, cy + s//16),
                      (cx + s//3, cy + s//8)], fill=(231,76,60))
        draw.ellipse([cx + s//8, cy + s//8, cx + s//2, cy + s*2//5],
                     fill=(200,230,250))
        draw.ellipse([cx + s//8 + 6, cy + s//8 + 6, cx + s//2 - 6, cy + s*2//5 - 6],
                     fill=(255,255,255))
        draw.line([cx + s//2 - 4, cy + s*2//5 - 4, cx + s*3//5, cy + s//2],
                  fill=(100,100,120), width=6)

    elif icon_type == "map":
        # 지도 + 경로 + 핀
        draw.rounded_rectangle([cx - s*2//5, cy - s//3, cx + s*2//5, cy + s//3],
                                radius=10, fill=(220,235,210))
        draw.line([cx - s*2//5, cy, cx + s*2//5, cy], fill=(220,220,220), width=10)
        draw.line([cx, cy - s//3, cx, cy + s//3], fill=(220,220,220), width=10)
        for i in range(5):
            px = cx - s//4 + i * (s//8)
            draw.ellipse([px - 4, cy - s//6 - 4, px + 4, cy - s//6 + 4], fill=accent)
        draw.ellipse([cx - s//4 - 10, cy - s//5 - 10,
                      cx - s//4 + 10, cy - s//5 + 10], fill=(39,174,96))
        pr = s//7
        draw.ellipse([cx + s//4 - pr, cy + s//6 - s//3 - pr,
                      cx + s//4 + pr, cy + s//6 - s//3 + pr], fill=(231,76,60))
        draw.polygon([(cx + s//4 - pr//2 + 4, cy + s//6 - s//3 + pr - 4),
                      (cx + s//4 + pr//2 - 4, cy + s//6 - s//3 + pr - 4),
                      (cx + s//4, cy + s//6 - s//3 + pr + 18)], fill=(231,76,60))
        draw.ellipse([cx + s//4 - 6, cy + s//6 - s//3 - 6,
                      cx + s//4 + 6, cy + s//6 - s//3 + 6], fill=(255,255,255))

    elif icon_type == "gift":
        # 선물상자 (benefit과 다른 스타일 - 파란색)
        draw.rounded_rectangle([cx - s//3, cy - s//8, cx + s//3, cy + s//3],
                                radius=8, fill=accent)
        draw.rounded_rectangle([cx - s*2//5, cy - s//4, cx + s*2//5, cy - s//8],
                                radius=6, fill=(int(accent[0]*0.75), int(accent[1]*0.75), int(accent[2]*0.75)))
        draw.rectangle([cx - s//10, cy - s//4, cx + s//10, cy + s//3],
                       fill=(255,215,0))
        draw.rectangle([cx - s*2//5, cy - s//6, cx + s*2//5, cy - s//8 + s//10],
                       fill=(255,215,0))
        draw.ellipse([cx - s//8, cy - s//4 - 16, cx + s//8, cy - s//4 + 16],
                     fill=(255,215,0))
        draw.polygon([(cx - s//8, cy - s//4), (cx - s*2//5, cy - s*3//5),
                      (cx - s//4, cy - s//4 + 5)], fill=(255,215,0))
        draw.polygon([(cx + s//8, cy - s//4), (cx + s*2//5, cy - s*3//5),
                      (cx + s//4, cy - s//4 + 5)], fill=(255,215,0))
        for sx, sy, ss in [(cx - s*3//5, cy - s//4, 28),
                            (cx + s*3//5, cy - s//3, 22),
                            (cx, cy - s*3//5, 24)]:
            draw.text((sx, sy), "★", font=load_font(ss), fill=(255,215,50), anchor="mm")


def generate_hook_text(title):
    """Claude Haiku로 썸네일 4줄 문구 생성"""
    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": f"""블로그 썸네일 문구 4줄을 만들어줘. 글자수 제한 없이 자연스럽게.

제목: {title}

출력 형식 (번호·기호 없이 4줄만):
1줄: 클릭 욕구를 자극하는 짧은 질문이나 감탄 문구 (자연스럽게, 예: "몰랐나요?" / "지금이에요!" / "이것 모르면 손해")
2줄: 핵심 혜택이나 금액 문구 (예: "최대 330만원" / "연 13% 절세" / "무료로 받을 수 있어요")
3줄: 이 글의 핵심 정보 한 문장
4줄: 대상 또는 조건 정보 한 문장

좋은 예시:
몰랐나요?
최대 330만원
근로장려금 신청 완전 정리
소득기준·기간 한눈에 확인

나쁜 예시 (이렇게 하지 마):
알고 계세요?
2026년 인상분
← 억지로 자른 느낌, 어색함"""}]
        )
        lines = [l.strip() for l in msg.content[0].text.strip().split('\n') if l.strip()]
        # 나쁜 예시 줄 제거 (←로 시작하는 줄)
        lines = [l for l in lines if not l.startswith("←") and not l.startswith("나쁜") and not l.startswith("좋은")]
        while len(lines) < 4:
            lines.append("")
        # 자르지 않음 - fit_font()가 자동으로 폰트 크기 조절
        return lines[0], lines[1], lines[2][:22], lines[3][:22]
    except Exception as e:
        print(f"   ⚠️ 문구 오류: {e}")
        clean = title.replace("&amp;", "&")
        return "꼭 확인하세요!", "", clean[:18], ""


def make_thumbnail(title, category):
    """키워드 기반 썸네일 생성 (1200×630 WEBP)"""
    W, H = 1200, 630

    accent_color, icon_type = get_theme(title)

    # 강조색 기반 파스텔 배경 (자동 생성 → 새 타입도 자동 대응)
    bg = accent_to_bg(accent_color)

    img  = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # 폰트
    f_badge  = load_font(27)
    f_sub    = load_font(29, bold=False)
    f_logo   = load_font(21, bold=False)

    # 카테고리 배지
    badge = f" {category} "
    bb = draw.textbbox((0, 0), badge, font=f_badge)
    bw = bb[2] - bb[0] + 24
    bh = bb[3] - bb[1] + 12
    draw.rounded_rectangle([44, 40, 44 + bw, 40 + bh], radius=7, fill=accent_color)
    draw.text((56, 46), badge.strip(), font=f_badge, fill="white")

    # 후킹 문구 생성
    hook1, hook2, sub1, sub2 = generate_hook_text(title)

    MAX_TW = 720  # 텍스트 최대 너비 (오른쪽 일러스트 공간 확보)

    def fit_font(text, start_size=68):
        for sz in range(start_size, 30, -3):
            f = load_font(sz)
            bb = draw.textbbox((0, 0), text, font=f)
            if (bb[2] - bb[0]) <= MAX_TW:
                return f, sz
        return load_font(32), 32

    f_title, _ = fit_font(hook1)
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

    # 오른쪽 컬러 일러스트 (패널 없이 배경 위에 바로)
    icon_cx = 970
    icon_cy = H // 2 + 20
    draw_icon(draw, icon_type, icon_cx, icon_cy, 200, accent_color)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=92)
    buf.seek(0)
    return buf.read()


def get_all_posts():
    posts = []
    page  = 1
    while True:
        r = requests.get(f"{WP_URL}/wp-json/wp/v2/posts",
            auth=AUTH,
            params={"per_page": 100, "page": page,
                    "status": "publish,future,draft",
                    "_fields": "id,title,categories"},
            timeout=20)
        if r.status_code != 200 or not r.json():
            break
        posts.extend(r.json())
        print(f"  {len(posts)}개 로드...")
        if len(r.json()) < 100:
            break
        page += 1
    return posts


def upload_and_set(post_id, img_bytes):
    fname = f"thumb-{post_id}.webp"
    r1 = requests.post(f"{WP_URL}/wp-json/wp/v2/media",
        auth=AUTH,
        headers={"Content-Disposition": f'attachment; filename="{fname}"',
                 "Content-Type": "image/webp"},
        data=img_bytes, timeout=30)
    if r1.status_code not in (200, 201):
        return False, f"미디어 업로드 실패 {r1.status_code}"
    media_id = r1.json()["id"]
    r2 = requests.post(f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        auth=AUTH, json={"featured_media": media_id}, timeout=15)
    return (True, media_id) if r2.status_code in (200, 201) else (False, f"설정 실패 {r2.status_code}")


def main():
    print("=" * 55)
    print("썸네일 전체 재생성 (키워드 기반)")
    print("=" * 55)

    posts = get_all_posts()
    print(f"총 {len(posts)}개 글\n")

    ok = ng = 0
    start = datetime.now()

    for i, post in enumerate(posts, 1):
        post_id = post["id"]
        title   = post["title"]["rendered"]
        cat_ids = post.get("categories", [])
        cat = "생활·정책"
        for cid in cat_ids:
            if cid in CAT_NAMES:
                cat = CAT_NAMES[cid]
                break

        elapsed = (datetime.now() - start).seconds
        eta = int(elapsed / i * (len(posts) - i)) if i > 1 else 0
        print(f"[{i:3d}/{len(posts)}] {title[:32]}...")
        print(f"        경과: {elapsed//60}분{elapsed%60}초 | 남은 약 {eta//60}분{eta%60}초")

        try:
            img_bytes = make_thumbnail(title, cat)
            ok2, result = upload_and_set(post_id, img_bytes)
            if ok2:
                print(f"        ✅ 완료 (media_id={result})")
                ok += 1
            else:
                print(f"        ❌ 실패: {result}")
                ng += 1
        except Exception as e:
            print(f"        ❌ 오류: {e}")
            ng += 1

        time.sleep(1.2)

    total = (datetime.now() - start).seconds
    print(f"\n{'='*55}")
    print(f"완료! 성공 {ok}개 / 실패 {ng}개")
    print(f"총 소요시간: {total//60}분 {total%60}초")
    print("=" * 55)


if __name__ == "__main__":
    main()
