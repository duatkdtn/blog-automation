import os

base = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(base, 'blog_automation.py')

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '    # BMI\n    "BMI":'
new = '''    # 만나이
    "만나이":    ("🎂 만나이 계산기 - 세는나이 연나이 한번에 확인", "https://www.hijanee.com/p/blog-page_12.html"),
    "세는나이":   ("🎂 만나이 계산기 - 세는나이 연나이 한번에 확인", "https://www.hijanee.com/p/blog-page_12.html"),
    "연나이":    ("🎂 만나이 계산기 - 세는나이 연나이 한번에 확인", "https://www.hijanee.com/p/blog-page_12.html"),
    "나이계산":   ("🎂 만나이 계산기 - 세는나이 연나이 한번에 확인", "https://www.hijanee.com/p/blog-page_12.html"),
    "내나이":    ("🎂 만나이 계산기 - 세는나이 연나이 한번에 확인", "https://www.hijanee.com/p/blog-page_12.html"),
    # BMI
    "BMI":'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("✅ 만나이 키워드 5개 추가 완료!")
    print("   만나이, 세는나이, 연나이, 나이계산, 내나이")
else:
    print("❌ 패턴 못 찾음")
