# ================================================
# 자동 발행 스크립트 v1.0
# GitHub Actions에서 4시간마다 실행
# today_keywords.json에서 현재 시간 키워드 찾아서 발행
# ================================================

import json
import os
import sys
import re
import base64
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# GitHub Actions 환경에서 token.pickle 복원
def restore_token():
    token_b64 = os.environ.get("GOOGLE_TOKEN")
    if token_b64:
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.pickle")
        with open(token_path, "wb") as f:
            f.write(base64.b64decode(token_b64))
        print("✅ Google 토큰 복원 완료")

# config.py가 없을 때 환경변수로 대체
def setup_env():
    env_vars = {
        "CLAUDE_API_KEY": os.environ.get("CLAUDE_API_KEY"),
        "CLAUDE_MODEL": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        "BLOG_ID": os.environ.get("BLOG_ID"),
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
        "CLOUDINARY_CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME"),
        "CLOUDINARY_API_KEY": os.environ.get("CLOUDINARY_API_KEY"),
        "CLOUDINARY_API_SECRET": os.environ.get("CLOUDINARY_API_SECRET"),
        "NAVER_CLIENT_ID": os.environ.get("NAVER_CLIENT_ID"),
        "NAVER_CLIENT_SECRET": os.environ.get("NAVER_CLIENT_SECRET"),
    }
    # config.py가 없으면 임시 생성
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            for key, val in env_vars.items():
                if val:
                    f.write(f'{key} = "{val}"\n')
        print("✅ config.py 임시 생성 완료")

def request_google_indexing(post_url):
    """구글 서치콘솔 Indexing API로 색인 요청"""
    try:
        from google.oauth2 import service_account
        import googleapiclient.discovery

        # token.pickle로 인증 (기존 OAuth 토큰 재사용)
        import pickle
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.pickle")
        if not os.path.exists(token_path):
            print("⚠️ token.pickle 없음 - 색인 요청 건너뜀")
            return False

        with open(token_path, "rb") as f:
            creds = pickle.load(f)

        # Indexing API 호출
        service = googleapiclient.discovery.build(
            "indexing", "v3", credentials=creds,
            cache_discovery=False
        )
        body = {
            "url": post_url,
            "type": "URL_UPDATED"
        }
        response = service.urlNotifications().publish(body=body).execute()
        print(f"✅ 구글 색인 요청 완료! → {post_url}")
        return True
    except Exception as e:
        print(f"⚠️ 색인 요청 실패 (발행은 성공): {e}")
        return False


ANCHOR_TEXTS = [
    "자세한 내용 확인하기",
    "원문 보러가기",
    "더 자세히 알아보기",
    "관련 정보 원문",
    "참고 자료 보기",
    "전체 내용 확인",
    "원본 글 읽기",
    "상세 정보 보기",
    "전문 내용 보기",
    "더 많은 정보 보기",
    "관련 글 바로가기",
    "자세한 정보는 여기서",
    "내용 더 보기",
    "원문 확인하기",
    "전체 글 읽기",
    "참고한 원문 보기",
    "출처 글 확인",
    "더 읽어보기",
    "관련 포스팅 보기",
    "전체 정보 확인하기",
]


def generate_naver_content(keyword, title, content, blogspot_url, related_keywords=None, naver_top_titles=None):
    """Claude API로 네이버용 요약 글 생성"""
    import re
    try:
        import anthropic
        claude_api_key = os.environ.get("CLAUDE_API_KEY")
        if not claude_api_key:
            try:
                from config import CLAUDE_API_KEY
                claude_api_key = CLAUDE_API_KEY
            except:
                pass
        if not claude_api_key:
            return None, None, None

        # 블스 본문에서 HTML 태그 제거
        plain_content = re.sub(r'<[^>]+>', '', content)
        plain_content = re.sub(r'\n{3,}', '\n\n', plain_content).strip()

        # 연관검색어, 네이버 상위 제목 텍스트 구성
        related_text = ", ".join(related_keywords) if related_keywords else "없음"
        naver_top_text = "\n".join([f"- {t}" for t in naver_top_titles]) if naver_top_titles else "없음"

        client = anthropic.Anthropic(api_key=claude_api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": f"""아래 블로그 글을 네이버 블로그용으로 재작성해줘.

키워드: {keyword}
제목: {title}
실제 연관검색어 (네이버/구글 API 조회): {related_text}
네이버 현재 상위 노출 제목 (참고용):
{naver_top_text}
원문 블로그: {blogspot_url}

원문 내용:
{plain_content[:3000]}

다음 형식으로 작성해줘:

===제목시작===
아래 3가지 유형의 제목을 각각 1개씩 만들어줘.
공통 규칙: 메인키워드 + 실제 연관검색어 조합, 30자 이내, 숫자 포함 선택적
- 반드시 위의 실제 연관검색어 단어를 제목에 포함할 것
- 네이버 상위 노출 제목 스타일 참고하되 차별화할 것
- 제목만 출력, 유형 태그([검색 노출형] 등) 절대 포함하지 말 것

1. 검색 노출형: 키워드를 앞에 배치, 정보 탐색 의도 반영 (예: "K뷰티 수면팩 성분 비교, 직접 써봤어요")
2. 핵심 요약형: 글의 핵심 정보를 압축 (예: "수면팩 브랜드 3가지 성분 차이 총정리")
3. 카피라이팅형: 감성/호기심 유발, 경험담 문체 (예: "자는 동안 피부 바뀐다는 수면팩, 진짜였어요")

===본문시작===
- 1인칭 경험담 형식 ("저도 직접 해봤는데" 말투)
- 친근하고 솔직한 말투
- 초등학생이나 70대 할머니도 바로 이해할 수 있는 쉬운 말 사용. 전문 용어, 어려운 한자어 절대 금지
- 나쁜 예: "심폐지구력", "절세 혜택 활용", "효능 및 효과", "섭취 시" / 좋은 예: "숨이 덜 차요", "세금 덜 내요", "이런 점이 좋아요", "먹으면"
- 문장은 짧게. 한 문장에 한 가지 내용만
- 원문과 구조를 반드시 다르게 할 것 (순서, 관점, 표현 모두 변형)
- 구조: 나의 경험/궁금증 → 핵심 정보 (원문과 다른 예시 활용) → 주의사항 → FAQ 3개 → 마무리
- 원문에서 사용한 예시나 표현을 그대로 쓰지 말 것. 다른 상황, 다른 각도로 풀어쓸 것
- 첫 문장은 독자에게 말 걸듯 시작 (예: "혹시 이거 저만 몰랐던 건가요?", "저도 이번에 처음 알았는데요~")
- FAQ는 반드시 아래 형식으로 작성:
  ❓ Q. 질문 내용
  💡 A. 답변 내용
  (3개 모두 이 형식 적용)
- 마무리에 "더 자세한 내용은 아래 원문에서 확인하세요 👇" 문구 포함
- 외부 공식사이트 링크는 절대 넣지 말것
- 분량은 800~1200자
- 마크다운 문법 절대 사용 금지 (###, ##, #, ---, ** 등 절대 사용하지 말것)
- 수평선(---) 절대 사용 금지
- 줄 시작에 # 기호 절대 사용 금지

===해시태그시작===
#태그1 #태그2 ... (10개)"""
            }]
        )

        result = message.content[0].text

        # 제목, 본문, 해시태그 파싱
        # ===마커=== 방식 우선, 구 [마커] 방식 폴백
        titles_match = re.search(r'===제목시작===(.*?)===본문시작===', result, re.DOTALL)
        if not titles_match:
            titles_match = re.search(r'\[제목\s*3\s*가지\](.*?)\[본문\]', result, re.DOTALL)
        body_match = re.search(r'===본문시작===(.*?)===해시태그시작===', result, re.DOTALL)
        if not body_match:
            body_match = re.search(r'\[본문\](.*?)\[해시태그\]', result, re.DOTALL)
        tags_match = re.search(r'===해시태그시작===(.*?)$', result, re.DOTALL)
        if not tags_match:
            tags_match = re.search(r'\[해시태그\](.*?)$', result, re.DOTALL)

        titles_raw = titles_match.group(1).strip() if titles_match else ""
        body = body_match.group(1).strip() if body_match else ""
        tags = tags_match.group(1).strip() if tags_match else ""

        # 제목 섹션 파싱: 번호 있으면 추출, 없으면 비어있지 않은 줄 그대로 사용
        if titles_raw:
            title_lines = re.findall(r'^[1-3][.)]\s*.+', titles_raw, re.MULTILINE)
            if title_lines:
                titles = "\n".join(title_lines[:3])
            else:
                # 번호 없이 줄로만 돼있는 경우 → 비어있지 않은 줄 3개 사용
                raw_lines = [l.strip() for l in titles_raw.split("\n") if l.strip() and len(l.strip()) > 5]
                titles = "\n".join(raw_lines[:3])
        else:
            titles = ""

        # 파싱 실패 시 전체 결과에서 번호 줄 추출
        if not titles:
            title_lines = re.findall(r'^[1-3][.)]\s*.+', result, re.MULTILINE)
            titles = "\n".join(title_lines[:3])
        else:
            title_lines = re.findall(r'^[1-3][.)]\s*.+', titles, re.MULTILINE)

        # 본문 파싱 실패 시 전체 결과 사용 (단, 제목 줄·마커는 제거)
        if not body:
            body = result
            # 마커 제거
            for marker in ['===제목시작===', '===본문시작===', '===해시태그시작===',
                           '[제목3가지]', '[본문]', '[해시태그]']:
                body = body.replace(marker, '')
            # 제목 줄 제거 (이미 titles로 추출했으니 본문에서 빼기)
            for t_line in title_lines:
                body = body.replace(t_line, '')
            body = re.sub(r'\n{3,}', '\n\n', body).strip()

        return titles, body, tags

    except Exception as e:
        print(f"⚠️ 네이버용 글 생성 실패: {e}")
        return None, None, None


def send_naver_email(keyword, title, content, image_urls, blogspot_url, published_at, related_keywords=None, naver_top_titles=None):
    """네이버 블로그 복붙용 글을 Gmail로 전송"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        print("⚠️ Gmail 환경변수 없음 - 이메일 전송 건너뜀")
        return

    import random
    import re

    # 네이버용 글 생성
    print("🤖 네이버용 글 생성 중...")
    naver_titles, naver_body, naver_tags = generate_naver_content(keyword, title, content, blogspot_url, related_keywords, naver_top_titles)

    # 생성 실패 시 기존 방식으로 폴백
    if not naver_body:
        print("⚠️ 네이버용 글 생성 실패 - 원문 그대로 발송")
        plain_content = re.sub(r'<[^>]+>', '', content)
        naver_body = plain_content
        naver_titles = ""
        naver_tags = ""

    # 이미지 HTML
    images_html = ""
    for url in image_urls[:3]:
        images_html += f'<img src="{url}" style="max-width:100%;margin:10px 0"><br>\n'

    # 앵커텍스트
    anchor_text = random.choice(ANCHOR_TEXTS)

    # 마크다운 → HTML 변환
    import re as _re
    naver_body = _re.sub(r'^### (.+)$', r'<h3>\1</h3>', naver_body, flags=_re.MULTILINE)
    naver_body = _re.sub(r'^## (.+)$', r'<h2>\1</h2>', naver_body, flags=_re.MULTILINE)
    naver_body = _re.sub(r'^# (.+)$', r'<h1>\1</h1>', naver_body, flags=_re.MULTILINE)
    naver_body = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', naver_body)
    naver_body = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', naver_body)
    naver_body = _re.sub(r'^- (.+)$', r'• \1', naver_body, flags=_re.MULTILINE)
    # 찌꺼기 제거 (빈 ##, ---, 단독 # 등)
    naver_body = _re.sub(r'^#{1,6}\s*$', '', naver_body, flags=_re.MULTILINE)
    naver_body = _re.sub(r'^-{2,}\s*$', '', naver_body, flags=_re.MULTILINE)
    naver_body = _re.sub(r'\n{3,}', '\n\n', naver_body)

    # 본문 줄바꿈 처리
    br_tag = '<br>\n'
    naver_body_html = naver_body.replace('\n', br_tag)

    # 제목 박스 HTML 미리 생성 - 라벨 고정으로 붙이기
    TITLE_LABELS = ["🔍 검색 노출형", "📝 핵심 요약형", "🎯 카피라이팅형"]
    if naver_titles:
        lines = [l.strip() for l in naver_titles.strip().split('\n') if l.strip()]
        # 번호(1. 2. 3.) 제거하고 라벨 고정 부착
        labeled_lines = []
        for idx, line in enumerate(lines[:3]):
            # "1. " "2) " 번호만 제거 (lstrip은 숫자 전체를 지우는 버그 있음)
            clean = re.sub(r'^[1-3][.)]\s*', '', line).strip()
            # [검색 노출형] 같은 대괄호 태그 제거
            clean = re.sub(r'^\[.*?\]\s*', '', clean).strip()
            # "검색 노출형: " "핵심 요약형: " 텍스트 제거
            clean = re.sub(r'^(검색 노출형|핵심 요약형|카피라이팅형)\s*:\s*', '', clean).strip()
            label = TITLE_LABELS[idx] if idx < len(TITLE_LABELS) else f"{idx+1}."
            labeled_lines.append(f'<div style="margin-bottom:10px"><span style="background:#764ba2;color:white;padding:2px 8px;border-radius:8px;font-size:11px;margin-right:6px">{label}</span><strong>{clean}</strong></div>')
        titles_inner = '\n'.join(labeled_lines)
        titles_html = f'<div style="background:#f8f8f8;border:1px solid #ddd;padding:15px;border-radius:6px;margin-bottom:20px"><strong>📌 추천 제목 3가지</strong><br><br>{titles_inner}</div>'
    else:
        titles_html = ''
    tags_html = f'<div style="background:#f0f0f0;padding:12px;border-radius:6px;margin-top:20px;font-size:14px;color:#555">📌 {naver_tags}</div>' if naver_tags else ''

    email_html = f"""
<html><body style="font-family:맑은고딕,sans-serif;max-width:700px;margin:0 auto;padding:20px">

<div style="background:#f0f7ff;border-left:4px solid #4A90E2;padding:15px;margin-bottom:20px;border-radius:4px">
  <h2 style="margin:0 0 8px 0;color:#333">📝 네이버 블로그 발행용</h2>
  <p style="margin:0;color:#666">발행 시각: {published_at} | 키워드: {keyword}</p>
</div>

<div style="background:#fff3cd;border:1px solid #ffc107;padding:12px;border-radius:4px;margin-bottom:20px">
  <strong>📋 사용 방법:</strong> 아래 제목 중 하나 선택 → 본문 복사 → 네이버 블로그에 붙여넣기
</div>

{titles_html}

<hr style="border:2px solid #333;margin:20px 0">
<h1 style="font-size:22px;color:#111">✍️ 본문 (복붙용)</h1>
<hr style="border:1px solid #ddd;margin:20px 0">

{images_html}

<div style="line-height:1.9;font-size:15px;color:#222">
{naver_body_html}
</div>

<div style="border-top:2px solid #ddd;margin-top:40px;padding-top:20px;text-align:center">
  <a href="{blogspot_url}" style="display:inline-block;background:#2c3e50;color:white;padding:12px 28px;border-radius:6px;font-weight:bold;text-decoration:none;font-size:15px">👉 {anchor_text}</a>
  <p style="margin:12px 0 0 0;font-size:16px;color:#333">🔗 원문: <a href="{blogspot_url}" style="color:#4A90E2;font-weight:bold;word-break:break-all;">{blogspot_url}</a></p>
</div>

{tags_html}

<hr style="border:2px solid #333;margin:30px 0">
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[네이버 발행용] {title}"
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, gmail_address, msg.as_string())

    print(f"✅ 네이버용 이메일 전송 완료! → {gmail_address}")


def main():
    restore_token()
    setup_env()
    # 현재 시간 확인 (한국시간 기준 - GitHub Actions는 UTC이므로 +9)
    now_utc = datetime.utcnow()
    # UTC → KST (+9시간)
    from datetime import timedelta
    now_kst = now_utc + timedelta(hours=9)
    current_time = now_kst.strftime("%H:%M")
    today = now_kst.strftime("%Y-%m-%d")

    print(f"\n{'='*50}")
    print(f"🚀 자동 발행 실행 - KST {now_kst.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    # today_keywords.json 읽기
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "today_keywords.json")

    if not os.path.exists(json_path):
        print("❌ today_keywords.json 없음 - 오늘 키워드 이메일이 아직 발송되지 않았습니다.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 순서대로 미발행 항목 찾기 (날짜 체크 없음 - 미발행 항목 있으면 순서대로 발행)
    schedule = data.get("schedule", [])
    target = None

    for item in schedule:
        if not item.get("published", False):
            target = item
            break

    if not target:
        print(f"✅ 오늘 발행할 키워드가 모두 발행 완료되었습니다.")
        return

    print(f"🕐 예정 시간 {target['time']} 슬롯 발행 시작 (현재 KST {current_time})")

    keyword = target["keyword"]
    title = target["title"]
    print(f"📝 발행 키워드: {keyword}")
    print(f"📌 발행 제목: {title}")

    # blog_automation.py에서 함수 import
    try:
        from blog_automation import (
            generate_blog_post,
            generate_images_with_vertex,
            generate_thumbnail_with_vertex,
            generate_seo_metadata,
            inject_seo_metadata,
            insert_images_into_content,
            publish_to_blogger,
            get_google_credentials,
            add_external_links,
            add_internal_links
        )
    except ImportError as e:
        print(f"❌ blog_automation.py import 실패: {e}")
        return

    # 1. 글 생성
    print(f"\n🤖 글 생성 중...")
    blog_title, content, map_keyword, place_links = generate_blog_post(keyword)

    # 제목은 today_keywords.json의 추천 제목 사용 (없으면 Claude 생성 제목)
    final_title = title if title else blog_title

    # 2. SEO 메타데이터 생성
    description, keywords_meta = generate_seo_metadata(keyword, final_title, content)
    content = inject_seo_metadata(content, final_title, description, keywords_meta, keyword)

    # 3. 이미지 생성
    print(f"\n🎨 이미지 생성 중...")
    images = generate_images_with_vertex(keyword, count=3)
    thumbnail = generate_thumbnail_with_vertex(keyword, final_title)

    # 4. 이미지 삽입
    if thumbnail:
        all_images = [thumbnail] + images
    else:
        all_images = images
    if all_images:
        content = insert_images_into_content(content, all_images, keyword)

    # 4-1. 외부링크 버튼 추가
    print(f"\n🔗 외부링크 추가 중...")
    content = add_external_links(content, keyword, map_keyword=map_keyword, place_links=place_links)

    # 4-2. 내부링크 추가
    print(f"\n📚 내부링크 추가 중...")
    blog_id = os.environ.get("BLOG_ID")
    content = add_internal_links(content, keyword, blog_id)

    # 5. 블로그스팟 발행
    print(f"\n📤 블로그스팟 발행 중...")
    result = publish_to_blogger(final_title, content)
    post_url = result.get("url") if result else None

    if post_url:
        print(f"\n✅ 발행 완료! → {post_url}")

        # 발행 완료 표시
        target["published"] = True
        target["post_url"] = post_url
        target["published_at"] = now_kst.strftime("%Y-%m-%d %H:%M")

        # JSON 파일 저장 (GitHub Actions가 커밋할 수 있도록)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 today_keywords.json 업데이트 완료 (published: true)")

        # 네이버용 이메일 발송
        naver_title = target.get("naver_title", "")
        related_keywords = target.get("related_keywords", [])
        naver_top_titles = target.get("naver_top_titles", [])
        try:
            send_naver_email(keyword, naver_title or final_title, content,
                           [img for img in all_images if img], post_url,
                           now_kst.strftime("%Y-%m-%d %H:%M"),
                           related_keywords, naver_top_titles)
        except Exception as e:
            print(f"⚠️ 네이버 이메일 전송 실패 (발행은 완료): {e}")
    else:
        print(f"❌ 블로그스팟 발행 실패")

if __name__ == '__main__':
    main()
