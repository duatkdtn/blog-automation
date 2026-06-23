# ================================================
# 자동 발행 스크립트 v1.0
# GitHub Actions에서 4시간마다 실행
# today_keywords.json에서 현재 시간 키워드 찾아서 발행
# ================================================

import json
import os
import sys
import base64
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

    # 날짜 확인
    if data.get("date") != today:
        print(f"⚠️ 오늘({today}) 키워드가 아닙니다. (저장된 날짜: {data.get('date')})")
        return

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

        # 네이버 백링크용 글 생성
        print(f"\n📝 네이버 백링크용 글 생성 시작...")
        try:
            from naver_post_generator import generate_naver_post
            related_keywords = target.get("related_keywords", [])
            naver_result = generate_naver_post(
                keyword=keyword,
                title=final_title,
                content=content,
                image_urls=all_images if all_images else [],
                blogspot_url=post_url,
                related_keywords=related_keywords
            )
            print(f"✅ 네이버용 파일 생성 완료!")
            print(f"   📄 {naver_result['html_path']}")
            print(f"   📝 {naver_result['txt_path']}")
        except Exception as e:
            print(f"⚠️ 네이버 글 생성 실패 (블로그스팟 발행은 성공): {e}")
    else:
        print(f"\n❌ 발행 실패")

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
