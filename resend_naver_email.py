"""
방금 발행된 나스닥 글의 네이버용 이메일 재전송
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

base = os.path.dirname(os.path.abspath(__file__))

# config.py에서 환경 설정
import config as cfg
os.environ.setdefault('CLAUDE_API_KEY', cfg.CLAUDE_API_KEY)
os.environ.setdefault('CLAUDE_MODEL', getattr(cfg, 'CLAUDE_MODEL', 'claude-sonnet-4-6'))
os.environ.setdefault('BLOG_ID', cfg.BLOG_ID)

# 대상 포스트 정보
POST_URL = "https://www.hijanee.com/2026/07/blog-post_11.html"
KEYWORD  = "나스닥 뜻 코스피 코스닥 차이점 쉽게 설명"
TITLE    = "나스닥 뜻과 코스피·코스닥 차이점, 이렇게 쉬운 거였어요!"
NAVER_TITLE_SUGGESTIONS = [
    "나스닥·코스피·코스닥 차이점, 초보자도 5분이면 이해해요",
    "코스피 나스닥 차이점 초보자",
    "나스닥 코스닥 차이"
]
NAVER_TOP_TITLES = [
    "코스피·코스닥 뜻 쉽게 이해하고 나스닥과의 차이점 완벽... ",
    "코스피 코스닥 나스닥 뜻과 차이점 알아보기",
    "코스피 코스닥 뜻과 차이점 기준 총정리! 종목수부터 나스닥... "
]
PUBLISHED_AT = "2026-07-11 17:26"

from blog_automation import generate_blog_post
from auto_publish import send_naver_email

print("📝 블로그 글 재생성 중 (네이버용)...")
blog_title, content, _, _ = generate_blog_post(KEYWORD)
print(f"✅ 글 생성 완료: {blog_title}")

print("\n📧 네이버용 이메일 전송 중...")
send_naver_email(
    keyword=KEYWORD,
    title=TITLE,
    content=content,
    image_urls=[],
    blogspot_url=POST_URL,
    published_at=PUBLISHED_AT,
    related_keywords=NAVER_TITLE_SUGGESTIONS,
    naver_top_titles=NAVER_TOP_TITLES
)

input("\n완료! 엔터를 누르면 닫힙니다...")
