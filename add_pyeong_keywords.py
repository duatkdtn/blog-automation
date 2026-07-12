import os

base = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(base, 'blog_automation.py')

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '    # 만나이\n    "만나이":'
new = '''    # 평수 변환기
    "평수":     ("📐 평수 계산기 - 평 m² ft² 면적 단위 변환", "https://www.hijanee.com/p/blog-page_92.html"),
    "전용면적":  ("📐 평수 계산기 - 평 m² ft² 면적 단위 변환", "https://www.hijanee.com/p/blog-page_92.html"),
    "공급면적":  ("📐 평수 계산기 - 평 m² ft² 면적 단위 변환", "https://www.hijanee.com/p/blog-page_92.html"),
    "제곱미터":  ("📐 평수 계산기 - 평 m² ft² 면적 단위 변환", "https://www.hijanee.com/p/blog-page_92.html"),
    "평형":     ("📐 평수 계산기 - 평 m² ft² 면적 단위 변환", "https://www.hijanee.com/p/blog-page_92.html"),
    "분양면적":  ("📐 평수 계산기 - 평 m² ft² 면적 단위 변환", "https://www.hijanee.com/p/blog-page_92.html"),
    # 만나이
    "만나이":'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("✅ 평수 키워드 6개 추가 완료!")
    print("   평수, 전용면적, 공급면적, 제곱미터, 평형, 분양면적")
else:
    print("❌ 패턴 못 찾음")
