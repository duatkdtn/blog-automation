"""
blog_automation.py 복원 스크립트
- 12e6778 커밋 기준으로 복원된 파일에 CALCULATOR_PAGES 45개 키워드 적용
"""
import os

base = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(base, 'blog_automation_restored.py')
dst = os.path.join(base, 'blog_automation.py')

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

old_dict = '''CALCULATOR_PAGES = {
    "근로장려금": ("🧮 근로장려금 계산기 - 내 지원금 바로 확인", "https://www.hijanee.com/p/blog-page_10.html"),
    "장려금":    ("🧮 근로장려금 계산기 - 내 지원금 바로 확인", "https://www.hijanee.com/p/blog-page_10.html"),
    "연봉":      ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "실수령":    ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "월급":      ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
}'''

new_dict = '''CALCULATOR_PAGES = {
    # 근로장려금
    "근로장려금": ("🧮 근로장려금 계산기 - 내 지원금 바로 확인", "https://www.hijanee.com/p/blog-page_10.html"),
    "장려금":    ("🧮 근로장려금 계산기 - 내 지원금 바로 확인", "https://www.hijanee.com/p/blog-page_10.html"),
    "자녀장려금":  ("🧮 근로장려금 계산기 - 내 지원금 바로 확인", "https://www.hijanee.com/p/blog-page_10.html"),
    "근로자녀장려금": ("🧮 근로장려금 계산기 - 내 지원금 바로 확인", "https://www.hijanee.com/p/blog-page_10.html"),
    # 연봉 실수령액
    "연봉":      ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "실수령":    ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "월급":      ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "최저임금":   ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "최저시급":   ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "시급":      ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    "주휴수당":   ("📊 연봉 실수령액 계산기 - 세후 월급 바로 확인", "https://www.hijanee.com/p/blog-page.html"),
    # 퇴직금
    "평균임금":   ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    "퇴직금":    ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    "퇴직":      ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    "퇴사":      ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    "IRP":       ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    "퇴직연금":   ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    "명예퇴직":   ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    "희망퇴직":   ("💼 퇴직금 계산기 - 내 퇴직금 얼마인지 바로 확인", "https://www.hijanee.com/p/blog-page_11.html"),
    # 실업급여
    "실업급여":   ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    "구직급여":   ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    "고용보험":   ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    "실직":      ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    "권고사직":   ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    "해고":      ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    "계약만료":   ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    "재취업":     ("📋 실업급여 계산기 - 수령액 지급일수 바로 확인", "https://www.hijanee.com/p/blog-page_91.html"),
    # 취득세
    "취득세":     ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "부동산":     ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "아파트":     ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "주택":      ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "매매":      ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "청약":      ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "분양":      ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "재개발":     ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "재건축":     ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    "양도세":     ("🏠 취득세 계산기 - 주택 부동산 취득세 바로 계산", "https://www.hijanee.com/p/blog-page_758.html"),
    # BMI
    "BMI":        ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
    "비만":        ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
    "체질량지수":   ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
    "다이어트":   ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
    "체중":      ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
    "표준체중":   ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
    "뱃살":      ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
    "체지방":     ("⚖️ BMI 계산기 - 체질량지수 비만도 바로 확인", "https://www.hijanee.com/p/bmi.html"),
}'''

if old_dict in content:
    new_content = content.replace(old_dict, new_dict)
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    print(f"✅ blog_automation.py 복원 완료!")
    print(f"   총 줄 수: {len(new_content.splitlines())}")
    print(f"   CALCULATOR_PAGES 키워드 수: {new_content.count('hijanee.com')}")
else:
    print("❌ 오류: 원본 딕셔너리를 찾지 못했습니다.")
    print("   blog_automation_restored.py 파일을 확인해주세요.")
