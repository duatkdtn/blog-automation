from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=options)

try:
    # 다음 - 더 많은 선택자 시도
    print("=== 다음 실시간 ===")
    driver.get('https://www.daum.net/')
    time.sleep(3)

    # 페이지 소스에서 실시간 관련 클래스 찾기
    selectors = [
        '.realtime_part a', '.link_issue', '.sr_realtimeissue a',
        '[class*="realtime"] a', '[class*="trendrank"] a',
        '.issue_wrap a', '.hot_issue a', '.rank_list a'
    ]
    for sel in selectors:
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        if els:
            texts = [e.text.strip() for e in els[:5] if e.text.strip()]
            if texts:
                print(f"선택자 '{sel}': {texts}")

    # 네이트 - 10개 다 가져오기
    print("\n=== 네이트 실시간 (10개) ===")
    driver.get('https://www.nate.com/')
    time.sleep(3)
    elements = driver.find_elements(By.CSS_SELECTOR, '#keywordRank a, .rtkwd_list a, [class*="keyword"] a')
    keywords = []
    for el in elements:
        text = el.text.strip()
        if text and len(text) > 1 and text not in keywords:
            keywords.append(text)
    for i, kw in enumerate(keywords[:10]):
        print(f"{i+1}. {kw}")

finally:
    driver.quit()
