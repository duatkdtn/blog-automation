# ================================================
# 자동 발행 스크립트 v1.0
# GitHub Actions에서 4시간마다 실행
# today_keywords.json에서 현재 시간 키워드 찾아서 발행
# ================================================

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
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

    # 현재 시간에 맞는 키워드 찾기
    schedule = data.get("schedule", [])
    target = None

    for item in schedule:
        # 시간 매칭 (예: "04:00" → 04시 00~59분 사이면 실행)
        item_hour = item["time"].split(":")[0]
        current_hour = current_time.split(":")[0]
        if item_hour == current_hour and not item.get("published", False):
            target = item
            break

    if not target:
        print(f"⏰ {current_time} - 발행 예정 키워드 없음 (이미 발행됐거나 해당 없음)")
        return

    keyword = target["keyword"]
    title = target["title"]
    print(f"📝 발행 키워드: {keyword}")
    print(f"📌 발행 제목: {title}")

    # blog_automation.py에서 함수 import
    try:
        from blog_automation import (
            generate_blog_content,
            generate_images_with_vertex,
            generate_thumbnail_with_vertex,
            create_blog_post,
            get_blogger_service
        )
    except ImportError as e:
        print(f"❌ blog_automation.py import 실패: {e}")
        return

    # 글 생성 및 발행
    print(f"\n🤖 글 생성 중...")
    content = generate_blog_content(keyword, title)

    print(f"\n🎨 이미지 생성 중...")
    images = generate_images_with_vertex(keyword, count=3)
    thumbnail = generate_thumbnail_with_vertex(keyword, title)

    print(f"\n📤 블로그스팟 발행 중...")
    service = get_blogger_service()
    post_url = create_blog_post(service, title, content, images, thumbnail, keyword)

    if post_url:
        print(f"\n✅ 발행 완료! → {post_url}")

        # 발행 완료 표시
        target["published"] = True
        target["post_url"] = post_url
        target["published_at"] = now_kst.strftime("%Y-%m-%d %H:%M")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 발행 상태 저장 완료")
    else:
        print(f"\n❌ 발행 실패")

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
