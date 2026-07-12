path = r"C:\Users\HOME\Documents\Claude\Projects\블로그자동화\blog_automation.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = '    "월급":      ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),\n}'

new = '    "월급":      ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),\n    "퇴직금":    ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),\n    "퇴직":      ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),\n    "평균임금":   ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),\n}'

assert old in content, "❌ 교체 대상 코드를 찾지 못했습니다"
content = content.replace(old, new, 1)
print("✅ 퇴직금 계산기 URL 3개 추가 완료")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"✅ 저장 완료 ({len(content)} bytes)")
