# ================================================
# 한발뉴스24 - AI 분류 모듈 (hanbal_ai.py)
# 수집된 기사 → Claude Haiku → 카테고리별 1개 선정 + 요약
# ================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CLAUDE_API_KEY, CLAUDE_MODEL
import anthropic
import json
import re


def build_prompt(collected_data):
    """지침서 기반 시스템 프롬프트 + 기사 목록 조합"""

    today = collected_data["today"]
    window_start = collected_data["window_start"]
    window_end = collected_data["window_end"]

    # 기사 목록 텍스트 구성
    articles_text = ""
    for cat_name, articles in collected_data["categories"].items():
        articles_text += f"\n### {cat_name} ({len(articles)}개)\n"
        if not articles:
            articles_text += "  (수집된 기사 없음)\n"
            continue
        for i, a in enumerate(articles, 1):
            articles_text += f"""  [{i}] 제목: {a['제목']}
  언론사: {a['언론사']} | 발행: {a['발행시각']}
  요약: {a['본문요약'][:200]}
  URL: {a['url']}
"""

    system_prompt = f"""당신은 한국어 생활정보 블로그 운영자를 돕는 뉴스 소재 정리 도우미입니다.

오늘 날짜: {today} (한국 시간)
기사 허용 기간: {window_start} ~ {window_end}

[절대 규칙]
1. 기사에 없는 숫자·날짜·금액을 만들어 쓰지 않는다
2. "예정"을 "시행"으로 바꾸지 않는다
3. 입력된 URL을 그대로 쓴다. 새로 만들지 않는다
4. 설명 문장, 인사말 없이 JSON만 출력한다
5. 코드블록(```json```)은 쓰지 않는다. 날 JSON만 출력한다
6. 빈 목록은 []로 쓴다

[출력 형식] - 아래 형식 그대로, 12개 카테고리 순서 유지:
{{
  "생성일": "{today}",
  "기간": {{"시작": "{window_start}", "끝": "{window_end}"}},
  "항목": [
    {{
      "카테고리": "카테고리명",
      "상태": "선정" 또는 "해당없음",
      "제목": "핵심만 20자 안팎으로 줄인 제목",
      "한줄요약": "60자 안팎, 초등학생도 이해하도록 쉽게",
      "핵심사실": ["기사에 있는 날짜·금액·조건 최대 3개"],
      "확정여부": "확정 또는 예정 또는 논의중",
      "시행_마감일": "YYYY-MM-DD 또는 null",
      "키워드후보": ["실제 검색창에 칠 만한 표현 2~3개"],
      "기사날짜": "발행시각 그대로",
      "출처": "언론사명",
      "링크": "입력된 URL 그대로",
      "교차_출처": [],
      "블로그적합도": {{"등급": "상 또는 중 또는 하", "이유": "한 문장"}},
      "주의": [],
      "민감도": "보통 또는 주의"
    }}
  ]
}}

기사가 없는 카테고리는:
{{"카테고리": "카테고리명", "상태": "해당없음", "사유": "허용 기간 내 적합 기사 없음"}}"""

    user_prompt = f"""아래 카테고리별 기사 목록을 보고, 각 카테고리에서 블로그 소재로 가장 적합한 기사 1개를 선정해 JSON으로 출력하세요.

{articles_text}

규칙:
- 카테고리마다 정확히 1개 선정 (기사 없으면 해당없음)
- 항목은 반드시 12개, 카테고리 순서(생활·정책 → 건강·의료 → ... → 트렌드·기술) 유지
- JSON만 출력, 다른 텍스트 없음"""

    return system_prompt, user_prompt


def run_ai(collected_data):
    """Claude Haiku로 기사 분류 및 요약"""

    print("[한발뉴스24] AI 분류 시작...")

    system_prompt, user_prompt = build_prompt(collected_data)

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,  # claude-haiku-4-5-20251001
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        raw_text = message.content[0].text.strip()
        print(f"  AI 응답 길이: {len(raw_text)}자")

        # JSON 파싱
        # 혹시 코드블록이 붙어있으면 제거
        raw_text = re.sub(r"```json\s*", "", raw_text)
        raw_text = re.sub(r"```\s*", "", raw_text)
        raw_text = raw_text.strip()

        result = json.loads(raw_text)
        print(f"  파싱 성공! 항목 {len(result.get('항목', []))}개")

        # URL 검증: 입력에 없는 URL이면 해당없음으로 변경
        all_urls = set()
        for articles in collected_data["categories"].values():
            for a in articles:
                all_urls.add(a["url"])

        for item in result.get("항목", []):
            if item.get("상태") == "선정":
                link = item.get("링크", "")
                if link and link not in all_urls:
                    print(f"  [경고] URL 검증 실패: {item['카테고리']} → 해당없음 처리")
                    item["상태"] = "해당없음"
                    item["사유"] = "URL 검증 실패"

        return result

    except json.JSONDecodeError as e:
        print(f"  [오류] JSON 파싱 실패: {e}")
        print(f"  원본 응답 앞 500자: {raw_text[:500]}")
        return None
    except Exception as e:
        print(f"  [오류] AI 호출 실패: {e}")
        return None


def print_summary(result):
    """결과 요약 출력"""
    if not result:
        print("결과 없음")
        return

    print(f"\n{'='*50}")
    print(f"[한발뉴스24] AI 분류 결과")
    print(f"{'='*50}")
    for item in result.get("항목", []):
        status = item.get("상태", "")
        cat = item.get("카테고리", "")
        if status == "선정":
            print(f"  ✅ {cat}: {item.get('제목', '')[:35]}")
            print(f"      → {item.get('한줄요약', '')[:50]}")
            print(f"      적합도: {item.get('블로그적합도', {}).get('등급', '')} | {item.get('출처', '')}")
        else:
            print(f"  ❌ {cat}: {item.get('사유', '해당없음')}")
    print()


# ================================================
# 단독 테스트 실행
# ================================================
if __name__ == "__main__":
    from hanbal_collector import collect_news

    print("1단계: 뉴스 수집")
    collected = collect_news()

    print("\n2단계: AI 분류")
    result = run_ai(collected)

    print_summary(result)

    # 결과 파일로 저장 (디버그용)
    if result:
        import datetime
        today = datetime.datetime.now().strftime("%Y%m%d")
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"hanbal_result_{today}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"결과 저장: {out_path}")
