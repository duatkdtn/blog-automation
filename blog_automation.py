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

    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
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

        with open('token.pickle', 'wb') as token:
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
        f"Korean people in a realistic scene related to '{keyword}'. Indoor Korean setting, natural daylight, warm and friendly atmosphere. Clean background with no signage, no banners, no text, no writing anywhere. High quality photo.",
        f"A Korean person doing something related to '{keyword}'. Modern Korean cafe or home interior background. Natural candid moment. No signs, no banners, no text, no writing visible anywhere in the image.",
        f"Real life Korean lifestyle scene about '{keyword}'. Korean people, Korean style clothing and surroundings. No text, no signs, no banners, no writing of any kind in the entire image.",
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
    """썸네일 이미지에 한국어 제목 텍스트 합성"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        w, h = img.size

        # 반투명 검정 오버레이 (하단 40%)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle([(0, int(h * 0.6)), (w, h)], fill=(0, 0, 0, 160))
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)

        # 윈도우 기본 한국어 폰트
        font_path = r"C:\Windows\Fonts\malgun.ttf"
        font_size = max(30, w // 20)
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            font = ImageFont.load_default()

        # 제목 줄바꿈 (최대 20자)
        lines = textwrap.wrap(title, width=20)
        total_h = len(lines) * (font_size + 10)
        y = h - total_h - 40

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (w - text_w) // 2
            # 그림자
            draw.text((x+2, y+2), line, font=font, fill=(0, 0, 0, 200))
            # 흰색 텍스트
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += font_size + 10

        output = io.BytesIO()
        img.convert("RGB").save(output, format="JPEG", quality=85)
        return output.getvalue()
    except Exception as e:
        print(f"   ⚠️ 텍스트 합성 실패: {e}")
        return img_bytes


def generate_thumbnail_with_vertex(keyword, title):
    """AI Studio Gemini로 썸네일 생성 + 한국어 제목 합성"""
    import time
    print(f"\n🖼️  썸네일 생성 중...")

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Eye-catching blog thumbnail with Korean people related to '{keyword}'. Vibrant colors, Korean urban or indoor background, natural and lively scene. Absolutely no text, no signs, no banners, no writing anywhere in the image."

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
                img_bytes = add_text_to_thumbnail(img_bytes, title)
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

    prompt = f"""당신은 {BLOG_LANGUAGE} 블로그 작가입니다.
아래 키워드로 SEO에 최적화된 블로그 글을 작성해주세요.

오늘 날짜: {today}
{news_section}
키워드: {keyword}
글 길이: 1000~3000자 사이 (너무 길지 않게, 핵심만 담아서)
톤: 친근하고 따뜻한 말투. 독자에게 직접 말하듯이 "~하셨나요?", "~해보세요!" 같은 표현 사용. 딱딱한 설명문보다 대화하듯 자연스럽게.

다음 구조로 작성해주세요:
1. 첫 줄에 "제목: [제목내용]" 형식으로 제목 작성
2. 도입부: 독자의 공감을 얻는 짧은 이야기나 질문으로 시작 (<p> 태그)
3. 본문은 아래 태그만 사용:
   - <h2> : 대주제 (3~4개)
   - <h3> : 소주제 (각 h2 아래 2~3개)
   - <p> : 본문 내용
   - <ul><li> : 목록
   - <strong> : 강조
4. 마지막에 자주 묻는 질문(FAQ) 섹션:
   - <h2>자주 묻는 질문</h2>
   - <h3>Q: 질문</h3><p>A: 답변</p> 형식으로 3개

절대 ```html 같은 코드블록 표시를 사용하지 마세요.
순수 HTML 태그만 사용하고, 제목 줄 이후 바로 HTML 본문을 작성하세요."""

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


def insert_images_into_content(content, image_urls, keyword):
    """본문 h2 섹션마다 이미지 삽입"""
    if not image_urls:
        return content

    img_style = 'style="width:100%;max-width:700px;height:auto;margin:15px auto;display:block;border-radius:8px;"'

    # 맨 첫 이미지는 본문 맨 위에
    first_img = f'<p><img src="{image_urls[0]}" alt="{keyword}" {img_style} /></p>\n'

    # h2 섹션마다 이미지 삽입
    sections = content.split('<h2>')
    result = first_img + sections[0]
    img_index = 1

    for section in sections[1:]:
        result += '<h2>' + section
        if img_index < len(image_urls):
            img_html = f'\n<p><img src="{image_urls[img_index]}" alt="{keyword}" {img_style} /></p>\n'
            result += img_html
            img_index += 1

    return result


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

    if not keyword.strip():
        print("❌ 키워드를 입력해주세요!")
        return

    # 글 생성
    title, content = generate_blog_post(keyword)

    # Vertex AI로 본문 이미지 생성
    image_urls = generate_images_with_vertex(keyword, count=3)

    # Vertex AI로 썸네일 생성
    thumbnail_url = generate_thumbnail_with_vertex(keyword, title)

    # 이미지 삽입 (썸네일을 맨 앞에)
    if thumbnail_url:
        image_urls = [thumbnail_url] + image_urls

    if image_urls:
        content = insert_images_into_content(content, image_urls, keyword)
        print(f"🖼️  이미지 {len(image_urls)}장 삽입됐어요! (썸네일 포함)")

    print(f"\n{'='*50}")
    print(f"제목: {title}")
    print(f"{'='*50}")

    # 발행 여부 확인
    publish = input("\n블로그에 발행하시겠어요? (y/n): ")

    if publish.lower() == 'y':
        publish_to_blogger(title, content)
    else:
        print("발행을 취소했습니다.")

    print("\n✨ 완료!")


if __name__ == "__main__":
    main()
