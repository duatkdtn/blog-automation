import anthropic
import os
import pickle
import requests
import random
import base64
import io
from PIL import Image
import cloudinary
import cloudinary.uploader
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import *

# Cloudinary 설정
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# Google OAuth 범위
SCOPES = ['https://www.googleapis.com/auth/blogger']


def upload_image_to_cloudinary(img_bytes, filename="blog_image"):
    """이미지를 압축해서 Cloudinary에 업로드하고 URL 반환"""
    try:
        # Pillow로 이미지 압축 (1MB 이하)
        img = Image.open(io.BytesIO(img_bytes))

        # JPEG로 변환 및 압축
        output = io.BytesIO()
        img.convert("RGB").save(output, format="JPEG", quality=75, optimize=True)
        compressed = output.getvalue()

        # Cloudinary 업로드
        result = cloudinary.uploader.upload(
            compressed,
            public_id=filename,
            folder="blog_automation",
            overwrite=True,
            resource_type="image"
        )
        url = result.get("secure_url")
        print(f"   ✅ 업로드 완료: {url}")
        return url
    except Exception as e:
        print(f"   ⚠️ 업로드 실패: {e}")
        return None


def get_google_credentials():
    """Google 인증 처리"""
    creds = None

    token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.pickle")

    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"]
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)

        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def translate_keyword(keyword):
    """Claude로 키워드를 영어로 번역"""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": f"다음 한국어 키워드를 이미지 검색에 적합한 영어 단어 1~3개로만 번역해주세요. 번역 결과만 출력하세요: {keyword}"}]
    )
    return message.content[0].text.strip()


def generate_images_with_vertex(keyword, count=3):
    """AI Studio Gemini로 이미지 생성 - 블로그 내용 기반 한국 스타일"""
    import time
    print(f"\n🎨 Gemini로 이미지 생성 중...")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompts = [
        f"Realistic photo of Korean people in a scene related to '{keyword}'. Indoor Korean setting, natural daylight, warm atmosphere. IMPORTANT: zero text, zero letters, zero words, zero numbers, zero signs, zero banners, zero watermarks anywhere in the entire image. Pure photographic scene only.",
        f"A Korean person in a moment related to '{keyword}'. Modern Korean interior background. IMPORTANT: absolutely no text, no letters, no words, no numbers, no signs, no banners, no labels, no watermarks of any kind visible anywhere in the image.",
        f"Korean lifestyle photo about '{keyword}'. Korean people, Korean style surroundings. IMPORTANT: strictly no text, no writing, no letters, no numbers, no signs, no banners anywhere in the image whatsoever.",
    ]

    image_url_list = []
    for i, prompt in enumerate(prompts[:count]):
        try:
            print(f"   이미지 {i+1}/{count} 생성 중...")
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"]
                )
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    img_bytes = part.inline_data.data
                    url = upload_image_to_cloudinary(img_bytes, f"blog_{keyword}_{i+1}_{int(time.time())}")
                    if url:
                        image_url_list.append(url)
                        print(f"   ✅ 이미지 {i+1} 완료!")
                    break
        except Exception as e:
            print(f"   ⚠️ 이미지 {i+1} 생성 실패: {e}")

    return image_url_list


def add_text_to_thumbnail(img_bytes, title):
    """썸네일 이미지에 한국어 제목 텍스트 합성 - 상위 블로거 스타일"""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        import textwrap

        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        w, h = img.size

        # 하단 그라데이션 오버레이 (60% → 100% 점점 진해짐)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        for i in range(int(h * 0.45), h):
            alpha = int(210 * (i - h * 0.45) / (h * 0.55))
            draw_overlay.line([(0, i), (w, i)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)

        # 폰트 설정 - 굵은 폰트 우선 시도
        font_size = max(36, w // 16)
        font = None
        font_paths = [
            r"C:\Windows\Fonts\malgunbd.ttf",              # 맑은 고딕 Bold (Windows)
            r"C:\Windows\Fonts\malgun.ttf",                # 맑은 고딕 (Windows)
            r"C:\Windows\Fonts\gulim.ttc",                 # 굴림 (Windows)
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",   # Linux Bold
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",       # Linux
            "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",  # Linux 바른고딕
        ]
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, font_size)
                small_font = ImageFont.truetype(fp, max(18, font_size // 2))
                break
            except:
                continue
        if font is None:
            font = ImageFont.load_default()
            small_font = font

        # 제목 텍스트 (최대 16자 줄바꿈)
        lines = textwrap.wrap(title, width=16)[:3]  # 최대 3줄
        total_h = len(lines) * (font_size + 12)
        y = h - total_h - 50

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (w - text_w) // 2

            # 텍스트 그림자 (여러 겹으로 선명하게)
            for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3)]:
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 180))
            # 흰색 메인 텍스트
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += font_size + 12

        output = io.BytesIO()
        img.convert("RGB").save(output, format="JPEG", quality=88)
        return output.getvalue()
    except Exception as e:
        print(f"   ⚠️ 텍스트 합성 실패: {e}")
        return img_bytes


def generate_hook_text(keyword, title):
    """Claude API로 썸네일용 후킹 문구 생성 (15자 이내)"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""아래 블로그 제목을 보고 썸네일에 들어갈 후킹 문구를 1개만 만들어줘.

블로그 제목: {title}
키워드: {keyword}

조건:
- 15자 이내
- 짧고 강렬하게
- 숫자 포함하면 더 좋음 (예: 3가지, 30만원)
- 궁금증 유발 (예: 모르면 손해, 이것만 알면)
- 문구만 출력, 다른 말 없이"""
            }]
        )
        hook = message.content[0].text.strip().strip('"').strip("'")
        return hook[:20] if hook else title
    except:
        return title


def generate_thumbnail_with_vertex(keyword, title):
    """AI Studio Gemini로 썸네일 생성 + 후킹 문구 합성"""
    import time
    print(f"\n🖼️  썸네일 생성 중...")

    # 후킹 문구 생성
    hook_text = generate_hook_text(keyword, title)
    print(f"   📌 썸네일 문구: {hook_text}")

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Eye-catching blog thumbnail photo with Korean people related to '{keyword}'. Vibrant colors, Korean urban or indoor background, natural and lively scene. IMPORTANT: zero text, zero letters, zero words, zero numbers, zero signs, zero banners, zero watermarks anywhere in the entire image. Pure photographic scene only."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_bytes = part.inline_data.data
                img_bytes = add_text_to_thumbnail(img_bytes, hook_text)
                url = upload_image_to_cloudinary(img_bytes, f"thumbnail_{keyword}_{int(time.time())}")
                if url:
                    print(f"   ✅ 썸네일 완료!")
                    return url
    except Exception as e:
        print(f"   ⚠️ 썸네일 생성 실패: {e}")

    return None


def get_pexels_images(keyword, count=4):
    """Pexels API로 이미지 검색 (무료, 워터마크 없음)"""
    print(f"\n🖼️  Pexels에서 이미지 검색 중...")
    print(f"   검색 키워드: {keyword}")

    # 한국어 키워드를 영어로 번역해서 검색
    en_keyword = translate_keyword(keyword)
    print(f"   영어 키워드: {en_keyword}")

    url = "https://api.pexels.com/v1/search"
    headers = {
        "Authorization": PEXELS_API_KEY
    }
    params = {
        "query": en_keyword,
        "per_page": count * 2,
        "orientation": "landscape"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if data.get("photos"):
            photos = data["photos"][:count]
            image_urls = [p["src"]["large"] for p in photos]
            print(f"✅ 이미지 {len(image_urls)}장 찾았어요!")
            return image_urls
        else:
            print("⚠️ 이미지를 찾지 못했어요.")
            return []
    except Exception as e:
        print(f"⚠️ 이미지 검색 실패: {e}")
        return []


def search_naver_news(keyword):
    """네이버 뉴스 검색으로 최신 정보 수집"""
    print(f"\n🔍 최신 뉴스 검색 중...")

    url = "https://openapi.naver.com/v1/search/news"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": keyword,
        "display": 5,
        "sort": "date"  # 최신순
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if data.get("items"):
            news_list = []
            for item in data["items"]:
                # HTML 태그 제거
                title = item["title"].replace("<b>", "").replace("</b>", "")
                desc = item["description"].replace("<b>", "").replace("</b>", "")
                pub_date = item.get("pubDate", "")
                news_list.append(f"제목: {title}\n날짜: {pub_date}\n내용: {desc}")

            news_text = "\n\n".join(news_list)
            print(f"✅ 최신 뉴스 {len(data['items'])}개 수집 완료!")
            return news_text
        else:
            print("⚠️ 관련 뉴스를 찾지 못했어요.")
            return ""
    except Exception as e:
        print(f"⚠️ 뉴스 검색 실패: {e}")
        return ""


def generate_blog_post(keyword):
    """Claude API로 블로그 글 생성"""
    from datetime import datetime
    today = datetime.now().strftime("%Y년 %m월 %d일")

    # 최신 뉴스 수집
    news_text = search_naver_news(keyword)

    print(f"\n✍️  '{keyword}' 키워드로 블로그 글 생성 중...")

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    # 뉴스 정보가 있으면 프롬프트에 포함
    news_section = ""
    if news_text:
        news_section = f"""
아래는 오늘 기준 최신 뉴스입니다. 키워드 "{keyword}"와 직접 관련된 내용만 참고하고, 관련 없는 내용은 무시하세요:

=== 최신 뉴스 ===
{news_text}
=================

주의: 뉴스 내용이 특정 지역이나 특수한 사례인 경우 글 전체를 그 내용으로 채우지 말고, 전국 독자에게 유용한 일반적인 정보 위주로 작성하세요.
"""

    prompt = f"""당신은 한국어 블로그 작가이자 구글 SEO 전문가입니다.
아래 키워드로 구글 상위노출 + 클릭률 높은 수익형 블로그 글을 작성해주세요.

오늘 날짜: {today}
{news_section}
키워드: {keyword}
글 길이: 반드시 2000자 이상 3000자 이하로 작성할 것. 각 섹션을 충분히 풍부하게 채워야 함. 2000자 미만이거나 3000자 초과하면 안 됨.
톤: 친근하고 따뜻한 말투. "저도 처음엔 몰랐는데요~", "직접 해보니까요~" 같은 경험담 문체. 독자에게 직접 말하듯 자연스럽게.

=== 글쓰기 구조 (반드시 따를 것) ===

[1. 제목]
첫 줄에 반드시 "제목: [제목내용]" 형식으로 작성

[2. 도입부] - <p> 태그 3~4개 (충분히 길게)
- 검색한 사람이 원하는 정보가 바로 있다는 확신을 주는 첫 문장
- 예: "2026년 건강검진 항목 정리해드립니다. 특히 30대 직장인이 꼭 알아야 할 핵심만 뽑았습니다."
- 경험담 2~3줄: "저도 처음엔 어디까지 무료인지 몰라서 헤맸는데요. 이 글 하나로 다 정리하실 수 있게 준비했습니다."
- 이 글에서 다룰 내용 미리보기 (독자가 끝까지 읽게 유도)

[3. 본문] - h2 섹션 4~5개 (각 섹션 충분히 길게 작성)
각 h2 아래 구성:
- <h2> 대주제
- <h3> 소주제 2~3개 (각각 2~3문단씩 상세 설명)
- <p> 설명 (각 소주제마다 최소 3~4문장 이상)
- 정보 정리는 반드시 표나 리스트로 시각화:
  * 표: <table style="width:100%;border-collapse:collapse;margin:15px 0"><tr><th style="background:#f0f4ff;padding:10px;border:1px solid #ddd">항목</th>...</tr></table>
  * 리스트: <ul style="padding-left:20px"><li style="margin:8px 0">내용</li></ul>
- 경험 + 이유 + 추천 섹션 최소 2개: "직접 해보니까요~", "이걸 알고 나서 달라졌어요~"
- 표는 반드시 2개 이상 포함 (각 표는 4행 이상)

[4. 주의사항 / 실수하기 쉬운 점] - h2 섹션 1개 (새로 추가)
- 많은 사람들이 놓치는 포인트 3~5가지를 구체적으로 설명
- <ul> 리스트로 정리

[5. FAQ] - 자주 묻는 질문 5개 (기존 3개에서 늘림)
<h2>자주 묻는 질문</h2>
<h3>Q: 질문</h3><p>A: 상세한 답변 (2~3문장 이상)</p>

[6. 결론 + 행동 유도] - <p> 태그 3~4개
- 핵심 내용 요약 (2~3줄)
- 독자에게 도움이 됐으면 하는 따뜻한 마무리 문장
- 관련 정보 추가 탐색 유도 문구
- 예: "비슷한 주제로 [관련키워드]도 정리해뒀으니 함께 참고해보세요!"
- 댓글/공유 유도: "궁금한 점은 댓글로 남겨주세요 :)"

[7. 면책문구 + AI 생성 표시] - 글 맨 마지막에 반드시 포함 (순서 지킬 것)
<p style="background:#f8f9fa;border-left:3px solid #adb5bd;padding:10px 14px;border-radius:4px;color:#6c757d;font-size:0.9em;margin-top:30px">※ 본 정보는 작성 시점({today}) 기준이며, 시장 상황·정책 변경 등에 따라 실제 내용과 다를 수 있습니다. 최신 정보는 공식 채널을 통해 반드시 확인하시기 바랍니다.</p>
<p style="background:#f1f3f5;border:1px solid #dee2e6;padding:8px 14px;border-radius:6px;color:#adb5bd;font-size:0.78em;margin-top:10px;line-height:1.5">🤖 본 콘텐츠는 AI(인공지능)의 도움을 받아 작성되었습니다. 「AI 생성 콘텐츠 표시에 관한 지침」에 따라 이를 고지하며, 정보의 정확성은 공식 채널을 통해 확인하시기 바랍니다.</p>

=== 주의사항 ===
- 절대 ```html 같은 코드블록 표시 사용하지 말 것
- 순수 HTML 태그만 사용
- 표는 반드시 2개 이상 포함
- 제목 줄 이후 바로 HTML 본문 작성
- 가격, 날짜, 법령, 정책, 수치 등 시간에 따라 바뀔 수 있는 정보가 있더라도 글 중간에 면책문구를 삽입하지 말 것. 면책문구는 글 맨 마지막(AI 생성 표시 바로 위)에 한 번만 넣음.
- 글 전체 길이는 반드시 2000자 이상 3000자 이하. 너무 짧아도, 너무 길어도 안 됨."""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text

    # ```html 등 코드블록 제거
    response_text = response_text.replace("```html", "").replace("```", "")

    # 제목과 본문 분리
    lines = response_text.strip().split('\n')
    title = ""
    content_lines = []
    content_started = False

    for line in lines:
        if line.startswith("제목:"):
            title = line.replace("제목:", "").strip()
        elif title and not content_started and line.strip():
            content_started = True
            content_lines.append(line)
        elif content_started:
            content_lines.append(line)

    content = '\n'.join(content_lines)

    print(f"✅ 글 생성 완료! 제목: {title}")
    return title, content


def generate_seo_metadata(keyword, title, content):
    """Claude로 SEO 메타데이터 생성 (description + keywords)"""
    print(f"\n🔍 SEO 메타데이터 생성 중...")

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    # 본문 앞 500자만 참고
    content_preview = content[:500] if content else ""

    prompt = f"""다음 블로그 글의 SEO 메타데이터를 생성해주세요.

키워드: {keyword}
제목: {title}
본문 미리보기: {content_preview}

아래 형식으로 정확히 출력하세요:

메타설명: [구글 검색결과에 표시될 설명. 검색자가 클릭하고 싶게 만드는 문장. 150자 이내. 핵심 정보 + 클릭유도 포함]
메타키워드: [관련 키워드 8~10개, 쉼표로 구분. 메인키워드+연관키워드+롱테일키워드 포함]"""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    result = message.content[0].text.strip()
    description = ""
    keywords_meta = ""

    for line in result.split("\n"):
        line = line.strip()
        if line.startswith("메타설명:"):
            description = line.replace("메타설명:", "").strip()
        elif line.startswith("메타키워드:"):
            keywords_meta = line.replace("메타키워드:", "").strip()

    print(f"   ✅ 메타설명: {description[:50]}...")
    print(f"   ✅ 메타키워드: {keywords_meta[:50]}...")
    return description, keywords_meta


def inject_seo_metadata(content, title, description, keywords_meta, keyword):
    """블로그 본문 HTML에 SEO 메타태그 삽입"""
    meta_tags = f"""<meta name="description" content="{description}" />
<meta name="keywords" content="{keywords_meta}" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{description}" />
<meta property="og:type" content="article" />
<meta name="robots" content="index, follow" />
<!-- SEO: {keyword} -->
"""
    return meta_tags + content


def insert_images_into_content(content, image_urls, keyword):
    """본문 h2 섹션마다 이미지 삽입 + alt태그 키워드 포함"""
    if not image_urls:
        return content

    img_style = 'style="width:100%;max-width:700px;height:auto;margin:15px auto;display:block;border-radius:8px;"'

    # alt태그용 설명 변형 (이미지마다 다르게)
    alt_variants = [
        f"{keyword} 관련 이미지",
        f"{keyword} 설명 사진",
        f"{keyword} 정보 안내",
        f"{keyword} 참고 이미지",
    ]

    # 맨 첫 이미지는 본문 맨 위에
    first_alt = alt_variants[0]
    first_img = f'<p><img src="{image_urls[0]}" alt="{first_alt}" {img_style} /></p>\n'

    # h2 섹션마다 이미지 삽입
    sections = content.split('<h2>')
    result = first_img + sections[0]
    img_index = 1

    for section in sections[1:]:
        result += '<h2>' + section
        if img_index < len(image_urls):
            alt_text = alt_variants[img_index % len(alt_variants)]
            img_html = f'\n<p><img src="{image_urls[img_index]}" alt="{alt_text}" {img_style} /></p>\n'
            result += img_html
            img_index += 1

    return result


# 외부링크 카테고리별 공식 사이트 목록
# 지도형 카테고리: URL에 KEYWORD_PLACEHOLDER 포함 → 실제 키워드로 치환됨
MAP_CATEGORIES = {"먹거리/맛집", "여행", "반려동물", "레저/공공시설", "지역정보"}

EXTERNAL_LINKS = {
    "먹거리/맛집": [
        ("네이버 지도", "https://map.naver.com/v5/search/KEYWORD_PLACEHOLDER"),
        ("카카오맵", "https://map.kakao.com/?q=KEYWORD_PLACEHOLDER"),
    ],
    "보험": [
        ("국민건강보험 공식사이트", "https://www.nhis.or.kr"),
        ("금융감독원", "https://www.fss.or.kr"),
        ("건강보험심사평가원", "https://www.hira.or.kr"),
    ],
    "취업/직장": [
        ("고용노동부", "https://www.moel.go.kr"),
        ("워크넷", "https://www.work.go.kr"),
        ("고용24", "https://www.고용24.kr"),
    ],
    "부동산/청약": [
        ("청약홈", "https://www.applyhome.co.kr"),
        ("국토교통부", "https://www.molit.go.kr"),
        ("부동산공시가격알리미", "https://www.realtyprice.kr"),
    ],
    "의료/건강": [
        ("국민건강보험", "https://www.nhis.or.kr"),
        ("질병관리청", "https://www.kdca.go.kr"),
        ("건강보험심사평가원", "https://www.hira.or.kr"),
    ],
    "정부지원/복지": [
        ("복지로", "https://www.bokjiro.go.kr"),
        ("정부24", "https://www.gov.kr"),
        ("국민비서", "https://www.ips.go.kr"),
    ],
    "세금/법률": [
        ("국세청 홈택스", "https://www.hometax.go.kr"),
        ("법제처", "https://www.law.go.kr"),
        ("대한법률구조공단", "https://www.klac.or.kr"),
    ],
    "육아/교육": [
        ("교육부", "https://www.moe.go.kr"),
        ("임신육아종합포털", "https://www.childcare.go.kr"),
        ("EBS", "https://www.ebs.co.kr"),
    ],
    "경제/금융": [
        ("한국은행", "https://www.bok.or.kr"),
        ("금융위원회", "https://www.fsc.go.kr"),
        ("금융감독원", "https://www.fss.or.kr"),
    ],
    "자동차": [
        ("한국교통안전공단", "https://www.kotsa.or.kr"),
        ("국토교통부", "https://www.molit.go.kr"),
        ("자동차민원 대국민포털", "https://www.ecar.go.kr"),
    ],
    "환경/날씨": [
        ("기상청", "https://www.weather.go.kr"),
        ("환경부", "https://www.me.go.kr"),
        ("에어코리아", "https://www.airkorea.or.kr"),
    ],
    "여행": [
        ("네이버 지도", "https://map.naver.com/v5/search/KEYWORD_PLACEHOLDER"),
        ("카카오맵", "https://map.kakao.com/?q=KEYWORD_PLACEHOLDER"),
    ],
    "반려동물": [
        ("네이버 지도", "https://map.naver.com/v5/search/KEYWORD_PLACEHOLDER"),
        ("카카오맵", "https://map.kakao.com/?q=KEYWORD_PLACEHOLDER"),
    ],
    "뷰티/식품": [
        ("식품의약품안전처", "https://www.mfds.go.kr"),
        ("식품안전나라", "https://www.foodsafetykorea.go.kr"),
    ],
    "IT/전자": [
        ("과학기술정보통신부", "https://www.msit.go.kr"),
        ("한국인터넷진흥원", "https://www.kisa.or.kr"),
    ],
    "스포츠/연예": [
        ("대한체육회", "https://www.sports.or.kr"),
        ("한국콘텐츠진흥원", "https://www.kocca.kr"),
    ],
    "레저/공공시설": [
        ("네이버 지도", "https://map.naver.com/v5/search/KEYWORD_PLACEHOLDER"),
        ("카카오맵", "https://map.kakao.com/?q=KEYWORD_PLACEHOLDER"),
    ],
    "지역정보": [
        ("네이버 지도", "https://map.naver.com/v5/search/KEYWORD_PLACEHOLDER"),
        ("카카오맵", "https://map.kakao.com/?q=KEYWORD_PLACEHOLDER"),
    ],
}


def get_external_links_for_keyword(keyword):
    """키워드에 맞는 외부링크 카테고리 자동 판단. (category, links) 튜플 반환"""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    categories = list(EXTERNAL_LINKS.keys())
    prompt = f"""키워드: "{keyword}"
이 키워드가 아래 카테고리 중 어디에 해당하는지 1개만 골라주세요. 카테고리 이름만 정확히 출력하세요.
카테고리: {', '.join(categories)}
해당 없으면 "없음"이라고만 출력하세요."""

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        category = message.content[0].text.strip()
        return category, EXTERNAL_LINKS.get(category, [])
    except:
        return "없음", []


def add_external_links(content, keyword):
    """글 하단에 외부링크 버튼 추가"""
    from urllib.parse import quote
    category, links = get_external_links_for_keyword(keyword)
    if not links:
        return content

    # 지도형 카테고리: URL에 키워드 삽입
    encoded_keyword = quote(keyword)
    is_map = category in MAP_CATEGORIES

    buttons_html = ""
    for name, url in links[:2]:
        actual_url = url.replace("KEYWORD_PLACEHOLDER", encoded_keyword)
        buttons_html += f'''<a href="{actual_url}" target="_blank" rel="noopener" style="display:inline-block;background:#e74c3c;color:white;padding:12px 20px;border-radius:6px;font-weight:bold;text-decoration:none;margin:6px 4px;font-size:14px">▶ {name} 바로가기</a>\n'''

    # 카테고리에 따라 섹션 제목 변경
    if is_map:
        section_title = "📍 네이버·카카오 지도에서 위치 확인하세요"
    else:
        section_title = "📌 공식 사이트에서 정확한 정보를 확인하세요"

    external_section = f'''
<div style="background:#fff8f8;border:1px solid #ffcccc;border-radius:8px;padding:20px;margin:30px 0">
<p style="font-weight:bold;color:#c0392b;margin:0 0 12px">{section_title}</p>
{buttons_html}</div>'''

    # 면책문구 바로 앞에 삽입
    if '<p style="background:#f8f9fa' in content:
        content = content.replace('<p style="background:#f8f9fa', external_section + '\n<p style="background:#f8f9fa', 1)
    else:
        content += external_section

    return content


def add_internal_links(content, keyword, blog_id):
    """Blogger API로 기존 글 목록 가져와서 연관 글 내부링크 추가"""
    try:
        creds = get_google_credentials()
        service = build('blogger', 'v3', credentials=creds)

        # 최근 발행글 50개 가져오기
        posts = service.posts().list(
            blogId=blog_id,
            maxResults=50,
            fields="items(title,url)"
        ).execute()

        items = posts.get("items", [])
        if not items:
            return content

        # 현재 발행 중인 글(같은 키워드 제목) 제외
        items = [p for p in items if keyword not in p.get("title", "") and keyword[:10] not in p.get("title", "")]

        if not items:
            return content

        # 글 목록 텍스트로 만들기
        posts_text = "\n".join([f"- {p['title']} | {p['url']}" for p in items])

        # Claude에게 연관 글 2개 선택 요청
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        prompt = f"""오늘 발행할 글의 키워드: "{keyword}"

아래 기존 발행 글 목록에서 오늘 키워드와 연관성이 높은 글 2개를 골라주세요.
형식: 제목|URL (한 줄에 하나씩, 정확히 2개만)

글 목록:
{posts_text}

해당 없으면 "없음"이라고만 출력하세요."""

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        result = message.content[0].text.strip()
        if result == "없음" or not result:
            return content

        # 파싱
        related = []
        for line in result.split("\n"):
            line = line.strip().lstrip("-").strip()
            if "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    title = parts[0].strip()
                    url = parts[1].strip()
                    if url.startswith("http"):
                        related.append((title, url))

        if not related:
            return content

        # 내부링크 섹션 생성
        links_html = ""
        for title, url in related[:2]:
            links_html += f'<li style="margin:8px 0"><a href="{url}" style="color:#2980b9;text-decoration:none">👉 {title}</a></li>\n'

        internal_section = f'''
<div style="background:#f0f7ff;border:1px solid #b3d4f5;border-radius:8px;padding:20px;margin:30px 0">
<p style="font-weight:bold;color:#1a5276;margin:0 0 12px;font-size:17px">📚 함께 읽으면 좋은 글</p>
<ul style="padding-left:20px;margin:0;font-size:16px;line-height:1.8">
{links_html}</ul></div>'''

        # 면책문구 바로 앞에 삽입
        if '<p style="background:#f8f9fa' in content:
            content = content.replace('<p style="background:#f8f9fa', internal_section + '\n<p style="background:#f8f9fa', 1)
        else:
            content += internal_section

        print(f"✅ 내부링크 {len(related)}개 추가 완료!")
        return content

    except Exception as e:
        print(f"⚠️ 내부링크 추가 실패 (발행은 계속): {e}")
        return content


def publish_to_blogger(title, content):
    """Blogger에 글 발행"""
    print(f"\n📤 블로그에 발행 중...")

    creds = get_google_credentials()
    service = build('blogger', 'v3', credentials=creds)

    post = {
        'title': title,
        'content': content
    }

    result = service.posts().insert(
        blogId=BLOG_ID,
        body=post
    ).execute()

    print(f"✅ 발행 완료!")
    print(f"🔗 URL: {result.get('url', '확인 불가')}")
    return result


def main():
    print("=" * 50)
    print("   BlogMaster - 블로그 자동화 프로그램")
    print("=" * 50)

    keyword = input("\n📌 키워드를 입력하세요: ")

