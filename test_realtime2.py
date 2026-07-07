from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time, re

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--log-level=3')

driver = webdriver.Chrome(options=options)

try:
    # 네이트 - 전체 링크 텍스트 덤프
    print("=== 네이트 HTML 구조 분석 ===")
    driver.get('https://www.nate.com/')
    time.sleep(3)

    # 여러 셀렉터 시도
    selectors = [
        '#keywordRank a',
        '.rtkwd_list a',
        '[class*="keyword"] a',
        '[class*="rank"] a',
        '[class*="trend"] a',
        '.issue a',
        'ol li a',
        'ul li a',
    ]
    for sel in selectors:
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        texts = [e.text.strip() for e in els if e.text.strip() and len(e.text.strip()) > 1]
        if texts:
            print(f"[{sel}] ({len(texts)}개): {texts[:10]}")

    # 페이지 소스에서 순위 관련 텍스트 직접 추출
    print("\n=== 페이지소스 분석 (실시간 관련) ===")
    src = driver.page_source
    # 순위 관련 섹션 찾기
    matches = re.findall(r'<(?:li|span|a)[^>]*>(\d+위[^<]{2,20})</', src)
    if matches:
        print("위 패턴:", matches[:10])

    # a 태그 텍스트 전부
    all_a = driver.find_elements(By.TAG_NAME, 'a')
    short_texts = [a.text.strip() for a in all_a if 2 <= len(a.text.strip()) <= 20]
    print(f"\n짧은 a태그 텍스트 ({len(short_texts)}개 중 앞 30개):")
    print(short_texts[:30])

finally:
    driver.quit()
