# ================================================
# 자동 발행 스크립트 v1.0
# GitHub Actions에서 4시간마다 실행
# today_keywords.json에서 현재 시간 키워드 찾아서 발행
# ================================================

import json
import os
import sys
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


def send_naver_email(keyword, title, content, image_urls, blogspot_url, published_at):
    """네이버 블로그 복붙용 글을 Gmail로 전송"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        print("⚠️ Gmail 환경변수 없음 - 이메일 전송 건너뜀")
        return

    # 네이버용 HTML 구성 (이미지 포함, 복붙하면 바로 사용 가능)
    images_html = ""
    for url in image_urls[:3]:
        images_html += f'<img src="{url}" style="max-width:100%;margin:10px 0"><br>\n'

    # 블로그스팟 본문에서 HTML 태그 제거한 텍스트 (네이버용)
    import re
    plain_content = re.sub(r'<[^>]+>', '', content)
    plain_content = re.sub(r'\n{3,}', '\n\n', plain_content).strip()

    email_html = f"""
<html><body style="font-family:맑은고딕,sans-serif;max-width:700px;margin:0 auto;padding:20px">

<div style="background:#f0f7ff;border-left:4px solid #4A90E2;padding:15px;margin-bottom:20px;border-radius:4px">
  <h2 style="margin:0 0 8px 0;color:#333">📝 네이버 블로그 발행용</h2>
  <p style="margin:0;color:#666">발행 시각: {published_at} | 키워드: {keyword}</p>
  <p style="margin:5px 0 0 0"><a href="{blogspot_url}" style="color:#4A90E2">🔗 블로그스팟 원문 보기</a></p>
</div>

<div style="background:#fff3cd;border:1px solid #ffc107;padding:12px;border-radius:4px;margin-bottom:20px">
  <strong>📋 사용 방법:</strong> 아래 내용을 복사해서 네이버 블로그에 붙여넣기 하세요.
</div>

<hr style="border:2px solid #333;margin:20px 0">
<h1 style="font-size:24px;color:#111">{title}</h1>
<hr style="border:1px solid #ddd;margin:20px 0">

{images_html}

{content}

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

    # 날짜 확인 (오늘 또는 어제 키워드 허용)
    yesterday = (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")
    saved_date = data.get("date")
    if saved_date not in [today, yesterday]:
        print(f"⚠️ 사용 가능한 키워드가 없습니다. (저장된 날짜: {saved_date}, 오늘: {today})")
        return
    if saved_date == yesterday:
        print(f"ℹ️ 어제({yesterday}) 키워드로 발행합니다. (오늘 키워드 아직 미도착)")

    # 현재 시간에 맞는 키워드 찾기 (현재 시간 이전 미발행 슬롯 포함)
    schedule = data.get("schedule", [])
    target = None

    current_hour_int = int(current_time.split(":")[0])

    for item in schedule:
        item_hour_int = int(item["time"].split(":")[0])
        # 현재 시간 이하인 슬롯 중 미발행 항목 찾기 (가장 오래된 것부터)
        if item_hour_int <= current_hour_int and not item.get("published", False):
            target = item
            break

    if not target:
        print(f"⏰ {current_time} - 발행 예정 키워드 없음 (이미 발행됐거나 해당 없음)")
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
            get_google_credentials
        )
    except ImportError as e:
        print(f"❌ blog_automation.py import 실패: {e}")
        return

    # 1. 글 생성
    print(f"\n🤖 글 생성 중...")
    blog_title, content = generate_blog_post(keyword)

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

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 발행 상태 저장 완료")

        # 6. 구글 색인 요청
        print(f"\n🔍 구글 색인 요청 중...")
        request_google_indexing(post_url)

        # 7. 네이버용 글 이메일 전송
        print(f"\n📧 네이버용 글 이메일 전송 중...")
        try:
            send_naver_email(
                keyword=keyword,
                title=final_title,
                content=content,
                image_urls=all_images if all_images else [],
                blogspot_url=post_url,
                published_at=now_kst.strftime("%Y-%m-%d %H:%M")
            )
        except Exception as e:
            print(f"⚠️ 네이버 이메일 전송 실패 (발행은 성공): {e}")
    else:
        print(f"\n❌ 발행 실패")

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
