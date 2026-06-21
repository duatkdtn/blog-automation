# ================================================
# 네이버 블로그 백링크용 요약글 생성기 v1.0
# 블로그스팟 발행 후 자동으로 네이버용 글 생성
# 결과물: 블로그자동화업로드용파일모음/날짜/폴더에 저장
# ================================================

import os
import json
import requests
import anthropic
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

def now_kst():
    return datetime.now(KST)


def get_naver_blog_top_titles(keyword):
    """네이버 블로그 상위 1~3위 제목 수집"""
    try:
        from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
        url = "https://openapi.naver.com/v1/search/blog"
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        params = {"query": keyword, "display": 3, "sort": "sim"}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        titles = []
        if data.get("items"):
            for item in data["items"]:
                title = item["title"].replace("<b>", "").replace("</b>", "").strip()
                titles.append(title)
        return titles
    except Exception as e:
        print(f"   ⚠️ 네이버 상위 제목 수집 실패: {e}")
        return []


def generate_naver_title(keyword, blogspot_title, related_keywords):
    """네이버용 제목 생성 - 메인키워드+연관검색어 고정, 뒷부분만 변형"""
    try:
        from config import CLAUDE_API_KEY, CLAUDE_MODEL
    except ImportError:
        CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
        CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    # 네이버 상위 블로그 제목 참고
    top_titles = get_naver_blog_top_titles(keyword)
    top_titles_text = "\n".join([f"- {t}" for t in top_titles]) if top_titles else "없음"

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    prompt = f"""블로그스팟 원본 제목을 참고해서 네이버 블로그용 제목을 만들어주세요.

원본 제목: {blogspot_title}
메인 키워드: {keyword}
연관 검색어: {', '.join(related_keywords) if related_keywords else '없음'}

네이버 상위 1~3위 제목 참고:
{top_titles_text}

규칙:
1. 메인키워드 + 연관검색어는 반드시 포함 (고정)
2. 뒷부분 수식어만 원본과 다르게 변형
3. 30자 이내
4. 숫자 포함 (예: 3가지, 5분, 2026)
5. 클릭 유도형 (예: 총정리, 완벽정리, 한눈에, 꼭 알아야 할)
6. 제목만 출력, 다른 설명 없이"""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()


def generate_naver_content(keyword, blogspot_title, blogspot_url, original_content, related_keywords):
    """네이버 백링크용 요약 본문 생성"""
    try:
        from config import CLAUDE_API_KEY, CLAUDE_MODEL
    except ImportError:
        CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
        CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    # 원본 본문에서 HTML 태그 제거 (참고용)
    import re
    plain_text = re.sub(r'<[^>]+>', '', original_content)
    plain_text = plain_text[:2000]  # 앞 2000자만 참고

    prompt = f"""다음 블로그 글을 네이버 블로그 백링크용으로 요약해주세요.

키워드: {keyword}
원본 제목: {blogspot_title}
원본 URL: {blogspot_url}
연관 검색어: {', '.join(related_keywords) if related_keywords else '없음'}
원본 내용 참고:
{plain_text}

=== 작성 규칙 ===
1. 분량: 원본의 30~40% (600~900자)
2. 톤: 친근하고 경험담 문체 ("저도 처음엔~", "직접 해보니~")
3. 구조:
   - 도입부: 2~3문장 (검색 의도 직격)
   - 핵심 내용 요약: 소제목 2~3개
   - 정리표 1개 (원본과 다른 색상 사용):
     <table style="width:100%;border-collapse:collapse;margin:15px 0">
     <tr><th style="background:#fff3e0;padding:10px;border:1px solid #ffcc80;color:#e65100">항목</th>
     <th style="background:#fff3e0;padding:10px;border:1px solid #ffcc80;color:#e65100">내용</th></tr>
     <tr><td style="padding:10px;border:1px solid #ffcc80">...</td>
     <td style="padding:10px;border:1px solid #ffcc80">...</td></tr>
     </table>
   - 마지막: 백링크 문구
4. 마지막 문단에 반드시 포함:
   <p>더 자세한 내용은 아래 원본 글에서 확인하세요! 👇<br>
   <a href="{blogspot_url}" target="_blank">▶ {blogspot_title}</a></p>
5. HTML 태그 사용 (```html 코드블록 표시 사용하지 말 것)
6. 순수 HTML만 출력"""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    content = message.content[0].text.strip()
    content = content.replace("```html", "").replace("```", "")
    return content


def generate_hashtags(keyword, related_keywords):
    """해시태그 8개 생성"""
    try:
        from config import CLAUDE_API_KEY, CLAUDE_MODEL
    except ImportError:
        CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
        CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    prompt = f"""키워드: {keyword}
연관검색어: {', '.join(related_keywords) if related_keywords else '없음'}

네이버 블로그 해시태그 8개 만들어주세요.
규칙:
- #없이 단어만, 쉼표로 구분
- 메인키워드 포함
- 연관검색어 포함
- 공백없이 붙여쓰기
- 예: 고속도로통행료미납,하이패스미납요금,통행료미납조회,...

해시태그만 출력하세요."""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    tags = message.content[0].text.strip()
    # # 붙이기
    tag_list = [f"#{t.strip().replace('#','')}" for t in tags.split(',') if t.strip()]
    return tag_list[:8]


def save_naver_post(keyword, title, content, hashtags, image_urls, blogspot_url):
    """네이버용 결과물 파일로 저장"""
    today = now_kst().strftime("%Y-%m-%d")
    safe_keyword = keyword.replace(" ", "_").replace("/", "_")

    # 저장 폴더
    base_dir = r"C:\Users\HOME\Documents\Claude\Projects\블로그자동화\블로그자동화업로드용파일모음"
    date_dir = os.path.join(base_dir, today)
    os.makedirs(date_dir, exist_ok=True)

    # 1. HTML 본문 파일 (복붙용)
    html_path = os.path.join(date_dir, f"{safe_keyword}_네이버.html")

    # 이미지 삽입
    img_html = ""
    if image_urls:
        img_style = 'style="width:100%;max-width:700px;height:auto;margin:15px auto;display:block;border-radius:8px;"'
        # 썸네일 (첫번째 이미지)
        img_html += f'<p><img src="{image_urls[0]}" alt="{keyword}" {img_style} /></p>\n'
        # 본문 이미지 (두번째, 세번째)
        for i, url in enumerate(image_urls[1:3], 1):
            img_html += f'<p><img src="{url}" alt="{keyword} {i}" {img_style} /></p>\n'

    full_html = img_html + "\n" + content

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    # 2. 제목 + 해시태그 txt 파일
    txt_path = os.path.join(date_dir, f"{safe_keyword}_제목해시태그.txt")
    hashtag_str = " ".join(hashtags)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"[제목]\n{title}\n\n")
        f.write(f"[원본 링크]\n{blogspot_url}\n\n")
        f.write(f"[해시태그]\n{hashtag_str}\n\n")
        f.write(f"[이미지 URL 목록]\n")
        for i, url in enumerate(image_urls, 1):
            f.write(f"이미지{i}: {url}\n")

    print(f"\n✅ 네이버용 파일 저장 완료!")
    print(f"   📄 본문: {html_path}")
    print(f"   📝 제목/태그: {txt_path}")

    return html_path, txt_path


def generate_naver_post(keyword, title, content, image_urls, blogspot_url, related_keywords=None):
    """네이버 백링크용 글 전체 생성 (auto_publish.py에서 호출)"""
    if related_keywords is None:
        related_keywords = []

    print(f"\n{'='*50}")
    print(f"📝 네이버 백링크용 글 생성 중...")
    print(f"   키워드: {keyword}")
    print(f"{'='*50}")

    # 1. 네이버용 제목 생성
    print(f"\n📌 네이버용 제목 생성 중...")
    naver_title = generate_naver_title(keyword, title, related_keywords)
    print(f"   ✅ 제목: {naver_title}")

    # 2. 요약 본문 생성
    print(f"\n✍️  요약 본문 생성 중...")
    naver_content = generate_naver_content(keyword, title, blogspot_url, content, related_keywords)
    print(f"   ✅ 본문 생성 완료!")

    # 3. 해시태그 생성
    print(f"\n🏷️  해시태그 생성 중...")
    hashtags = generate_hashtags(keyword, related_keywords)
    print(f"   ✅ {' '.join(hashtags)}")

    # 4. 파일 저장
    html_path, txt_path = save_naver_post(
        keyword, naver_title, naver_content,
        hashtags, image_urls, blogspot_url
    )

    return {
        "title": naver_title,
        "content": naver_content,
        "hashtags": hashtags,
        "html_path": html_path,
        "txt_path": txt_path
    }


if __name__ == "__main__":
    # 단독 테스트용
    print("네이버 포스트 생성기 단독 테스트")
    keyword = input("키워드 입력: ")
    blogspot_url = input("블로그스팟 URL 입력: ")
    title = input("블로그스팟 제목 입력: ")
    content = input("본문 일부 입력 (간단히): ")
    image_urls = []

    result = generate_naver_post(keyword, title, content, image_urls, blogspot_url)
    print(f"\n완료! 파일 위치: {result['html_path']}")
