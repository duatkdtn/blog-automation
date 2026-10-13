# -*- coding: utf-8 -*-
"""Haiku 3단계 호출로 글 만들기. 숫자는 사실표에서만. 고정 서식 부분(요약·FAQ·CTA·출처·면책 등)은 코드가 조립한다."""
import re, json, time, html as H
import common as C

STYLE = {
    "summary": "background:#eaf4fb;border:2px solid #2980b9;border-radius:8px;padding:20px 24px;margin:0 0 24px;",
    "mini": "background:#f8f9fa;border:1px solid #dee2e6;padding:15px 20px;margin:20px 0;border-radius:6px;",
    "faq": "background:#f8f9fa;border-left:4px solid #2980b9;padding:14px 18px;margin:0 0 18px;",
    "who": "background:#eaf4fb;border:1px solid #aed6f1;border-radius:8px;padding:20px 24px;margin:30px 0;",
    "cta": "background:#2980b9;color:#fff;padding:30px;border-radius:8px;text-align:center;margin:30px 0;",
    "links": "background:#eaf4fb;border:1px solid #aed6f1;border-radius:8px;padding:20px 24px;margin:30px 0;",
    "src": "background:#f0f8ff;border-left:4px solid #2980b9;padding:15px 20px;margin:24px 0;",
    "disc": "background:#f8f9fa;border:1px solid #dee2e6;padding:15px 20px;font-size:0.9em;color:#666;margin:24px 0;",
    "calc": "background:#eaf4fb;border:2px solid #2980b9;border-radius:8px;padding:22px;margin:28px 0;text-align:center;",
    "btn": "display:inline-block;background:#2980b9;color:#fff;padding:14px 28px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:17px;",
    "h2": "color:#2c3e50;font-size:24px;margin:36px 0 14px;",
    "h3": "color:#2c3e50;font-size:19px;margin:24px 0 8px;",
}

SYSTEM_BASE = """당신은 '우리동네 요양원'(요양원 비용·장기요양등급·지원금 정보 사이트)의 글 작성자입니다.
독자는 부모님을 모시려는 40~60대 자녀이며, 단어는 70~80대도 이해하는 쉬운 말로 씁니다.
말투는 ~더라고요, ~이에요, ~해요 (친근한 존댓말). '~습니다/합니다' 체는 쓰지 않습니다.

[절대 규칙]
1. 숫자·금액·비율·기한·일수는 아래 '사실표'에 있는 것만 씁니다. 기억으로 채우지 않습니다. 사실표에 없는 숫자가 필요하면 쓰지 않고 '정확한 내용은 국민건강보험공단(1577-1000)이나 입소할 요양원에 확인하세요'처럼 확인처를 쓰고, 자료부족 목록에 무엇이 필요했는지 적습니다.
2. 요양원마다 다른 값(비급여 식재료비·간식비·상급침실료·시설별 비용)은 단정하지 않습니다. 이런 말을 쓸 때는 '요양원마다 다르니 입소할 곳에서 확인하세요'를 본문에 씁니다.
3. 계산이 필요한 숫자는 사실표 값으로만 계산하고, 계산식을 본문에 보여 줍니다. 계산한 것은 calcs 목록에 {"식": "2331200*0.2", "결과": "466240"} 형태로 적습니다.
4. 글쓴이가 겪은 일처럼 지어내지 않습니다. '제가 ~했을 때', '저희 부모님은' 금지. 도입부는 공감형으로 씁니다.
5. 진단·치료·약 복용을 권하지 않습니다. 의료·법률 판단은 '전문가·공단에 확인'으로 안내합니다.
6. 근거로 쓰지 않은 기관 이름은 적지 않습니다. '마치며'·파트너스 안내·'최신 내용입니다' 같은 문구 금지.
7. 면회·외출처럼 법에 정한 것이 없는 내용은 '법에 정해진 시간이 없고 시설 운영규정에 따르니 입소 전에 확인하세요'로 씁니다.
8. 어려운 말은 쉬운 말로 풀어 씁니다. 예시와 계산 예시를 넣습니다.
9. 스타일은 inline style만 씁니다. <style>, <script>, class 사용 금지.
10. 표·본문·FAQ 어디에서든 숫자(금액·%·일수·개수)는 사실표에 있는 값 또는 사실표 값으로 계산한 값만 씁니다. 사실표에 없는 '대략 ○○만원', '월 ○○만~○○만원', '100%' 같은 숫자는 쓰지 않습니다. 비급여 항목(식재료비·간식비·상급침실료·이미용비 등)은 항목 이름과 '요양원마다 다르니 확인하세요'만 쓰고 금액은 쓰지 않습니다. 합계는 사실표 값끼리만 더하고 calcs에 식을 적습니다.
11. 말투 점검: 문장 끝이 '~입니다/합니다/습니다'이면 '~이에요/해요/어요'로 바꿔 씁니다. 표 안의 설명 문장도 같습니다.
"""

def facts_text(facts):
    lines = []
    for f in facts:
        v = f.get("값")
        v = f"{v:,}" if isinstance(v, int) else v
        lines.append(f"- [{f['id']}] {f['항목']}: {v}{f.get('단위','')} (기준:{f.get('기준','')}; 출처:{f.get('출처','')}; 비고:{f.get('비고','')})")
    return "\n".join(lines)

def client():
    import anthropic
    return anthropic.Anthropic(api_key=C.CLAUDE_API_KEY)

USAGE = {"in": 0, "out": 0}
NO_TEMP = [False]

def call(system, user, max_tokens=4096, temperature=0.6):
    cl = client()
    last = None
    for i in range(3):
        try:
            kw = dict(model=C.MODEL, max_tokens=max_tokens, system=system,
                      messages=[{"role": "user", "content": user}])
            if not NO_TEMP[0]:
                kw["temperature"] = temperature
            try:
                r = cl.messages.create(**kw)
            except TypeError as te:
                if "temperature" in str(te) and not NO_TEMP[0]:
                    NO_TEMP[0] = True; kw.pop("temperature", None)
                    r = cl.messages.create(**kw)
                else:
                    raise
            USAGE["in"] += r.usage.input_tokens; USAGE["out"] += r.usage.output_tokens
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        except Exception as e:  # 과부하·일시 오류 재시도
            last = e; print(f"[Haiku 오류 {i+1}/3] {type(e).__name__}: {str(e)[:300]}", flush=True)
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"Haiku 호출 실패: {type(last).__name__}: {str(last)[:300]}")

def extract_json(s):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.S) or re.search(r"(\{.*\})", s, re.S)
    if not m: raise ValueError("JSON 없음")
    return json.loads(m.group(1))

def tag(s, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", s, re.S)
    return m.group(1).strip() if m else ""

PATTERNS = ["쉼표형", "연도형", "질문형", "기준 제시형", "비교형", "순서형", "체크형", "단순형"]
PATTERN_HELP = """제목 패턴 8개(모양만 참고, 문구 그대로 쓰지 않음):
쉼표형 장기요양등급 신청 서류, 5가지만 챙기세요 / 연도형 요양원 비용 2026, 1등급부터 5등급까지 한눈에 / 질문형 장기요양등급 결과 언제 나올까? 확인 4가지 방법 / 기준 제시형 요양원 비용 얼마나 들까? 본인부담 20% 기준 / 비교형 요양원 vs 요양병원 차이, 비용·조건 3가지 / 순서형 장기요양등급 신청, 4단계로 끝내는 순서 정리 / 체크형 요양원 비용, 월 한도액과 비급여 3가지 먼저 확인 / 단순형 요양원 입소 절차 5단계, 준비물과 계약까지"""

def stage1(topic, facts, today, year_topic, recent_patterns, existing_titles, feedback=""):
    sys1 = SYSTEM_BASE + "\n지금은 1단계입니다. 글의 제목 후보·메타·구성을 JSON으로만 답합니다."
    usr = f"""오늘: {today}  (연도: {today[:4]})
주제: 메인 키워드={topic['main']} / 세부 키워드={topic['detail']} / 연관검색어={', '.join(topic['related'])}
글 유형: {topic['type']} / 이 글이 답하는 질문: {topic['question']} / 카테고리: {topic['category']}
작성 주의: {topic.get('fact_status','')}
연도를 제목에 넣는 주제인가: {'예(연도 ' + today[:4] + ')' if year_topic else '아니오(연도 쓰지 않음)'}
최근 발행 글의 제목 패턴: {', '.join(recent_patterns[-5:]) or '없음'} (같은 패턴을 연속해서 쓰지 않음)
{PATTERN_HELP}
이미 발행한 글 제목(겹치지 않게): {' / '.join(existing_titles[-30:])}

제목 규칙(코드가 검사함): 메인 키워드가 제목 맨 앞(표기 그대로) · 세부 키워드 포함 · 연관검색어도 가능하면 포함(공백 포함 30자를 넘으면 연관검색어는 뺌) · 숫자 1개 이상 · 공백 포함 18~30자 · 느낌표/이모지/대괄호/과장 표현 금지. 제목의 개수 숫자('5가지','4단계')는 본문의 실제 개수와 같아야 합니다. 금액·비율 숫자는 사실표 값만.
서로 다른 패턴으로 제목 후보 3개를 만드세요.
{('이전 시도 실패 이유: ' + feedback) if feedback else ''}

사실표(여기 있는 숫자만 쓸 수 있음):
{facts_text(facts)}

JSON 형식:
{{"titles":[{{"title":"","pattern":"쉼표형|연도형|질문형|기준 제시형|비교형|순서형|체크형|단순형"}},{{}},{{}}],
"slug":"영문 소문자와 하이픈만, 3~6단어",
"tags":["","",""],
"meta_description":"공백 포함 110~135자(너무 짧거나 길면 안 됨), 메인 키워드 포함, 수치는 사실표 값만",
"outline":["본문 h2 소제목 4~6개 (연관검색어를 소제목에 나눠 넣기)"],
"sources":["근거로 쓸 기관 이름 (국민건강보험공단|건강보험심사평가원|보건복지부 고시|법제처 국가법령정보센터|중앙치매센터|치매안심센터 안내|복지로|정부24 중에서 실제 근거로 쓴 것만)"],
"button":"longtermcare|bokjiro|law|nid|nhis 중 하나",
"calculator":"copayment|care-grade|none (본인부담금·비용 계산 주제면 copayment, 등급 판정 주제면 care-grade, 아니면 none)",
"infographic":true 또는 false (신청방법·절차·단계 4단계 이상 글이면 true)}}"""
    return extract_json(call(sys1, usr, max_tokens=1500, temperature=0.8))

def stage2(topic, facts, today, meta, title, feedback=""):
    sys2 = SYSTEM_BASE + """
지금은 2단계입니다. 글의 앞부분을 씁니다. 아래 태그 형식으로만 답하세요.
<summary>요약 항목 5개, 한 줄에 하나씩(문장 끝 마침표 없이). 이 글에서 알 수 있는 핵심</summary>
<intro>공감형 도입부 2~3문단. 각 문단은 <p style="line-height:1.85;font-size:16px;margin:0 0 16px">...</p>. 첫 문장에서 검색한 사람의 궁금증을 바로 건드림. 지어낸 경험담 금지.</intro>
<body>본문 HTML. 구성: h2 소제목(스타일 지정) 안에 내용. 소주제는 h3. 표 2개 이상(반드시 <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse"><thead style="background:#2980b9;color:#fff">…</thead><tbody> 행은 번갈아 background:#fff / #f8f9fa), 리스트 박스(background:#f0f8ff;border-left:4px solid #2980b9;padding:14px 18px), 공식 출처 인라인 링크 1~2개(<a href="https://www.longtermcare.or.kr" target="_blank" rel="noopener">구체적 키워드 앵커</a>, 앵커에 '여기 클릭' '바로가기' 금지), 단계가 필요한 글은 <ol>. 예시와 계산 예시 포함.</body>
<meta>{"numbers":[{"값":"본문에 쓴 숫자","근거":"사실표 id"}],"calcs":[{"식":"","결과":""}],"lacking":["사실표에 없어 쓰지 못한 정보"]}</meta>
h2 스타일: style="color:#2c3e50;font-size:24px;margin:36px 0 14px;"  h3 스타일: style="color:#2c3e50;font-size:19px;margin:24px 0 8px;"
본문(<body>)은 공백 포함 순수 글자 3,800자 이상으로 충분히 자세히 씁니다(소제목마다 3~4문단 + 예시). 같은 말을 반복해서 늘리지 마세요.
[표 필수] <body> 안에 표(<table>)를 반드시 2개 이상 넣습니다. 표가 없으면 글이 불합격입니다. 표 모양 예시(내용만 바꿔 복사해서 쓰세요):
<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse"><thead style="background:#2980b9;color:#fff"><tr><th style="padding:10px;border:1px solid #ddd">구분</th><th style="padding:10px;border:1px solid #ddd">내용</th></tr></thead><tbody><tr style="background:#fff"><td style="padding:10px;border:1px solid #ddd">…</td><td style="padding:10px;border:1px solid #ddd">…</td></tr><tr style="background:#f8f9fa"><td style="padding:10px;border:1px solid #ddd">…</td><td style="padding:10px;border:1px solid #ddd">…</td></tr></tbody></table></div>
표는 사실표의 값을 그대로 옮기거나(금액·한도액·비율), 숫자가 필요 없는 비교·절차·체크 표로 만듭니다."""
    usr = f"""오늘: {today}  글 제목: {title}
메인 키워드(본문 전체에서 정확히 7회 안팎(최대 9회). 그 이상 쓰지 말고 '이 비용', '비용', '이 금액'처럼 줄여 씁니다): {topic['main']} / 세부 키워드: {topic['detail']} / 연관검색어: {', '.join(topic['related'])}
이 글이 답하는 질문: {topic['question']}  /  작성 주의: {topic.get('fact_status','')}
본문 소제목 구성(이 순서·의미로): {json.dumps(meta['outline'], ensure_ascii=False)}
{'인포그래픽(STEP1→STEP4 카드, 바깥 div style="overflow-x:auto", 카드 min-height:100px, 배경 #eaf4fb/#d6eaf8 번갈아)을 본문 중간에 넣으세요.' if meta.get('infographic') else '인포그래픽은 넣지 않습니다.'}
제목에 개수 숫자가 있으면 그 개수만큼 본문 항목을 정확히 만드세요.
{('이전 시도 실패 이유(고쳐서 다시 쓰기): ' + feedback) if feedback else ''}

사실표:
{facts_text(facts)}"""
    out = call(sys2, usr, max_tokens=8192)
    mj = {}
    try: mj = json.loads(tag(out, "meta"))
    except Exception: pass
    return {"summary": [x.strip(" -·✅") for x in tag(out, "summary").split("\n") if x.strip()],
            "intro": tag(out, "intro"), "body": tag(out, "body"), "meta": mj}

def stage3(topic, facts, today, meta, title, part1, feedback=""):
    sys3 = SYSTEM_BASE + """
지금은 3단계입니다. 글의 뒷부분을 씁니다. 아래 태그 형식으로만 답하세요.
<mistakes>오해/주의사항 HTML. ❌ 오해 → 올바른 설명 박스 1개(style="background:#fdf2f8;border:1px solid #d2b4de;border-radius:8px;padding:18px 22px;margin:18px 0") 안에 ❌ 줄 3개 이상 + ✅ 올바른 경우 박스 1개(style="background:#eafaf1;border:1px solid #a9dfbf;border-radius:8px;padding:18px 22px;margin:18px 0"). 앞에 h2(스타일 지정) 소제목.</mistakes>
<faq>JSON 배열 [{"q":"질문","a":"답변 2~3문장, 근거 기관 표기"}] 5~7개. 연관검색어를 질문에 나눠 넣음. 질문에 'Q.'는 붙이지 않음.</faq>
<who>이 글이 도움 되는 사람 5~6가지를 한 줄씩(👉는 붙이지 않음)</who>
<cta>JSON {"head":"핵심 행동 촉구 한 문장(굵게 표시될 문구)","summary":"이 글 요약 + 행동 독려 1~2문장","related":"비슷한 주제로 정리해 둔 관련 키워드 한 개"}</cta>
<meta>{"numbers":[{"값":"","근거":""}],"calcs":[{"식":"","결과":""}],"lacking":[]}</meta>
h2 스타일: style="color:#2c3e50;font-size:24px;margin:36px 0 14px;"
이 뒷부분은 공백 포함 순수 글자 1,800자 이상이 되게 충분히 자세히 씁니다(오해 박스는 ❌ 4개 이상, FAQ 답변은 한 질문당 3~4문장으로 구체적으로, 질문은 6~7개)."""
    usr = f"""오늘: {today}  글 제목: {title}
메인 키워드: {topic['main']} / 세부 키워드: {topic['detail']} / 연관검색어: {', '.join(topic['related'])}
이 글이 답하는 질문: {topic['question']} / 작성 주의: {topic.get('fact_status','')}
앞부분(이미 작성됨, 내용과 겹치거나 모순되지 않게 이어 씀):
요약: {json.dumps(part1['summary'], ensure_ascii=False)}
본문 요약: {re.sub(r'<[^>]+>', ' ', part1['body'])[:2500]}
{('이전 시도 실패 이유(고쳐서 다시 쓰기): ' + feedback) if feedback else ''}

사실표:
{facts_text(facts)}"""
    out = call(sys3, usr, max_tokens=5000)
    def j(name, default):
        try: return json.loads(tag(out, name))
        except Exception: return default
    return {"mistakes": tag(out, "mistakes"), "faq": j("faq", []), "who": [x.strip(" -·👉") for x in tag(out, "who").split("\n") if x.strip()],
            "cta": j("cta", {}), "meta": j("meta", {})}

def h(s): return H.escape(str(s), quote=False)

def assemble(topic, meta, title, p1, p3, today, internal_links, calc_url):
    """고정 서식은 코드가 만든다. 반환: (html_before_toc, html_after_toc)"""
    S = STYLE
    items = "".join(f'<p style="margin:0 0 8px;font-size:16px;line-height:1.7">✅ {h(x)}</p>' for x in p1["summary"][:5])
    summary = f'<div style="{S["summary"]}"><p style="margin:0 0 12px;font-weight:bold;font-size:18px;color:#2c3e50">이 글에서 알 수 있어요</p>{items}</div>'
    mini = (f'<div style="{S["mini"]}"><strong>🙋 이런 분들이 꼭 읽어보세요</strong><br>· 처음 요양원을 알아보는 가족<br>'
            f'· {h(topic["question"])} 궁금한 분<br>· 장기요양 제도가 아직 낯선 보호자</div>')
    faq = f'<h2 style="{S["h2"]}">자주 묻는 질문</h2>' + "".join(
        f'<h3 style="{S["h3"]}">Q. {h(x.get("q",""))}</h3><div style="{S["faq"]}"><p style="margin:0;line-height:1.85;font-size:16px">A. {h(x.get("a",""))}</p></div>'
        for x in p3["faq"][:7])
    who = f'<div style="{S["who"]}"><p style="margin:0 0 12px;font-weight:bold;font-size:18px;color:#2c3e50">✅ 이런 분들 꼭 확인해보세요!</p>' + "".join(
        f'<p style="margin:0 0 8px;font-size:16px;line-height:1.7">👉 {h(x)}</p>' for x in p3["who"][:6]) + '</div>'
    calc = ""
    if calc_url:
        nm = "본인부담금 계산기" if "copayment" in calc_url else "장기요양등급 자가진단"
        calc = (f'<div style="{S["calc"]}"><p style="margin:0 0 10px;font-weight:bold;font-size:18px;color:#2c3e50">내 경우는 얼마일까요?</p>'
                f'<p style="margin:0 0 14px;font-size:16px">{nm}으로 바로 확인해 보세요.</p>'
                f'<a href="{calc_url}" style="{S["btn"]}">{nm} 해보기</a></div>')
    c = p3.get("cta", {})
    cta = (f'<div style="{S["cta"]}"><p style="margin:0 0 12px;font-size:20px;font-weight:bold">{h(c.get("head","필요한 정보부터 차근차근 확인해 보세요"))}</p>'
           f'<p style="margin:0 0 12px;font-size:16px;line-height:1.8">{h(c.get("summary",""))}</p>'
           f'<p style="margin:0 0 12px;font-size:16px;line-height:1.8">비슷한 주제로 {h(c.get("related", topic["main"]))}도 정리해뒀으니 함께 참고해보세요!</p>'
           f'<p style="margin:0;font-size:16px">궁금한 점은 댓글로 남겨주세요 :)</p></div>')
    links = "".join(f'<p style="margin:0 0 10px;font-size:16px">👉 <a href="{u}" style="color:#2980b9">{h(t)}</a></p>' for t, u in internal_links)
    linkbox = f'<div style="{S["links"]}"><p style="margin:0 0 12px;font-weight:bold;font-size:18px;color:#2c3e50">📌 함께 읽으면 좋은 글</p>{links}</div>'
    key = meta.get("button") if meta.get("button") in C.HOT else "longtermcare"
    btxt, burl = C.HOT[key]
    button = f'<p style="text-align:center;margin:30px 0"><a href="{burl}" target="_blank" rel="noopener noreferrer" style="{S["btn"]}">{btxt}</a></p>'
    srcs = [s for s in meta.get("sources", []) if s in C.AGENCIES] or ["국민건강보험공단"]
    src = f'<div style="{S["src"]}">📋 이 글의 정보 출처: {"·".join(srcs)} 자료 기준으로 작성되었습니다.</div>'
    disc = (f'<div style="{S["disc"]}">{today} 기준 작성. 요양원 비용·장기요양등급·지원금 정보는 수시로 변경될 수 있으므로, 실제 이용·신청 전 '
            f'국민건강보험공단 및 해당 요양원에서 최신 정보를 반드시 확인하세요. 이 글은 정보 제공 목적으로 작성되었으며, 법적 효력이 없습니다.</div>')
    before = summary
    after = (f'<p style="font-size:14px;color:#888;margin:0 0 18px">{today} 기준</p>' + p1["intro"] + mini + p1["body"] +
             p3["mistakes"] + faq + who + calc + cta + linkbox + button + src + disc)
    return before, after

def wrap_blocks(before, after):
    return (f"<!-- wp:html -->\n{before}\n<!-- /wp:html -->\n\n<!-- wp:shortcode -->\n[toc]\n<!-- /wp:shortcode -->\n\n"
            f"<!-- wp:html -->\n{after}\n<!-- /wp:html -->")

def reviewer(topic, title, html_text, today):
    """A 항목(의미 판단): K4 제목 숫자=본문 개수, B4 의료·법률 단정, B5 질문 답함, F5 단정 금지, S10 출처."""
    sys_r = "당신은 글 검수자입니다. 지침 위반 여부만 JSON으로 답합니다. 명백한 위반만 위반으로 봅니다(애매하면 통과)."
    usr = f"""제목: {title}
이 글이 답해야 하는 질문: {topic['question']}
검사 항목:
K4: 제목에 개수 숫자(예: 5가지, 4단계)가 있다면 본문에 그 개수의 항목이 정확히 있는가? (없으면 해당 없음=통과)
B4: 진단·치료·약 복용을 권하거나 의료·법률 판단을 단정하는 문장이 있는가? (있으면 위반)
B5: 본문이 위 '답해야 하는 질문'에 실제로 답하는가?
F5: 요양원마다 다른 값(비급여 식재료비·간식비·상급침실료 등)의 금액을 '모든 요양원이 이렇다'는 식으로 확정해 쓰는가? ('요양원마다 다르니 확인하세요' 안내가 함께 있거나 금액을 쓰지 않았으면 통과. 확정해 쓴 경우만 위반)
B6: 풀어 쓰지 않은 어려운 전문용어가 많은가?
JSON만: {{"K4":{{"ok":true,"why":""}},"B4":{{"ok":true,"why":""}},"B5":{{"ok":true,"why":""}},"F5":{{"ok":true,"why":""}},"B6":{{"ok":true,"why":""}}}}

글 본문(텍스트):
{html_text[:12000]}"""
    try:
        return extract_json(call(sys_r, usr, max_tokens=700, temperature=0.0))
    except Exception:
        return {}


def trim_keyword(before, after, kw, keep=8):
    """포커스 키워드가 너무 많이 나오면 초과분을 키워드의 마지막 낱말로 줄인다(링크·소제목은 건드리지 않음)."""
    from bs4 import BeautifulSoup, NavigableString
    tail = kw.split()[-1] if " " in kw else None
    if not tail: return after
    soup = BeautifulSoup(after, "html.parser")
    n = BeautifulSoup(before, "html.parser").get_text(" ", strip=True).count(kw)
    for node in soup.find_all(string=True):
        if node.parent.name in ("a", "h1", "h2", "h3") and kw in node: n += node.count(kw)
    for node in soup.find_all(string=True):
        if node.parent.name in ("a", "h1", "h2", "h3", "script", "style") or kw not in node:
            continue
        parts = node.split(kw); out = parts[0]
        for seg in parts[1:]:
            n += 1
            out += (kw if n <= keep else tail) + seg
        if out != str(node): node.replace_with(NavigableString(out))
    return str(soup)
