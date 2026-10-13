# -*- coding: utf-8 -*-
"""자동 검수 (코드 방식 C 항목). 결과: [{id, level('FAIL'|'WARN'), msg}]"""
import re, ast, operator
import requests
from bs4 import BeautifulSoup
import common as C

BANNED = ["마치며", "파트너스", "최신 내용입니다", "최신 내용이에요"]
HYPE = ["충격", "절대", "무조건", "100%", "비밀", "반드시 승인", "보장"]
INVENT = re.compile(r"(제가|저희|저는|우리 부모님은|저희 부모님)[^.。]{0,25}(했|겪|알아봤|다녀|모셨|신청했)")
# 단위가 없으면 개수/번호로 보고 통과시키는 숫자 종류
COUNT_UNITS = ("가지", "단계", "개", "번째", "번", "위", "곳", "명", "분", "개월", "시간", "회", "차", "쪽", "STEP")
FACT_UNITS = ("원", "만원", "%", "일", "년", "세", "㎡", "만 원", "천원", "배")
PHONE_OK = {"1577-1000", "1899-9988", "129", "1588-2188", "120"}
NUM_RE = re.compile(r"(\d[\d,]*\.?\d*)\s*(만\s*원|천원|원|%|퍼센트|일|개월|년|세|㎡|시간|분|가지|단계|개|번째|번|위|곳|명|회|배|등급|점)?")

def _nums_from_text(s):
    out = set()
    for m in re.finditer(r"\d[\d,]*\.?\d*", str(s)):
        t = m.group(0).replace(",", "").rstrip(".")
        try:
            v = float(t)
        except ValueError:
            continue
        out.add(v)
    return out

def build_allowed(facts, extra=()):
    allowed = set()
    for f in facts:
        blob = " ".join(str(f.get(k, "")) for k in ("값", "기준", "비고", "항목", "단위"))
        for v in _nums_from_text(blob):
            allowed.add(v)
            if v >= 10000: allowed.add(v / 10000.0)          # 2,331,200원 → 233.12만원 형태 대비
            if v >= 10000 and v % 10000 == 0: allowed.add(v // 10000)
    # 사실표 금액끼리의 합·차, 그리고 비율(10~90%)·12개월·30일 곱으로 만든 값은 '계산해 낸 숫자'로 허용한다.
    vals = sorted({float(f["값"]) for f in facts if isinstance(f.get("값"), (int, float)) and f["값"] >= 1000})
    ratios = (0.05, 0.06, 0.09, 0.1, 0.15, 0.16, 0.2, 0.4, 0.6, 0.8, 0.9, 12, 30, 31)
    for a in vals:
        for r in ratios: allowed.add(round(a * r, 2))
    for i, a in enumerate(vals):
        for b in vals[i + 1:]:
            allowed.add(a + b); allowed.add(abs(a - b))
    allowed.update({80.0, 60.0, 40.0})   # 본인부담 20%·40%·60%의 반대편(공단 부담 80% 등)
    for v in extra: allowed.add(float(v))
    return allowed

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}

def safe_eval(expr):
    expr = re.sub(r"[−–—]", "-", str(expr)); expr = re.sub(r"(?<=[\d)\s])[xX·](?=[\d(\s])", "*", expr); expr = expr.split("=")[0]
    def ev(n):
        if isinstance(n, ast.Expression): return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS: return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -ev(n.operand)
        raise ValueError("bad expr")
    return ev(ast.parse(re.sub(r"[원약\s]+(?=[-+*/×÷)]|$)", "", expr.replace(",", "")).replace("원", "").strip().replace("×", "*").replace("÷", "/").strip(), mode="eval"))

def _text(html):
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

def count_chars(html):
    return len(_text(html))

def check_title(title, topic, today_year, year_topic, recent_patterns, pattern):
    r = []
    if not title.startswith(topic["main"]): r.append(("K3a", "FAIL", "제목이 메인 키워드로 시작하지 않음"))
    n = len(title)
    if not (18 <= n <= 30): r.append(("K3b", "FAIL", f"제목 길이 {n}자 (18~30)"))
    if not re.search(r"\d", title): r.append(("K3c", "FAIL", "제목에 숫자 없음"))
    if re.search(r"[!！]|[\U0001F300-\U0001FAFF☀-➿]|\[|\]|…|★|♥|~", title) or any(h in title for h in HYPE) or title.count("?") > 1:
        r.append(("K3d", "FAIL", "제목에 금지 표현/기호"))
    ym = re.findall(r"20\d\d", title)
    if year_topic and not ym: r.append(("K3e", "FAIL", "연도가 바뀌는 주제인데 제목에 연도 없음"))
    if ym and any(int(y) != today_year for y in ym): r.append(("K3e", "FAIL", "제목 연도가 올해와 다름"))
    if topic["detail"] and not _detail_in(title, topic["detail"]): r.append(("K3g", "FAIL", "세부 키워드가 제목에 없음"))
    if not any(rk.replace(" ", "") in title.replace(" ", "") for rk in topic["related"]): r.append(("K3h", "WARN", "연관검색어가 제목에 없음"))
    if pattern and pattern in recent_patterns[-1:]: r.append(("K3f", "WARN", "직전 글과 같은 제목 패턴"))
    return r

def _detail_in(title, detail):
    t = title.replace(" ", "")
    d = detail.replace(" ", "")
    if d in t: return True
    toks = [x for x in re.split(r"[ ·,/]+", detail) if len(x) >= 2]
    hit = sum(1 for x in toks if x in title)
    return bool(toks) and hit >= max(1, (len(toks) + 1) // 2)

def check_html(html, ctx):
    """ctx: topic, facts, allowed(set), today_label, internal_urls(set), calc_needed, numbers_used(list), calcs(list), sources(list)"""
    res = []
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    topic = ctx["topic"]
    # S15 문장이 중간에 끊긴 문단(분량 제한 등으로 잘림)
    cut = []
    for p in soup.find_all("p"):
        tx = p.get_text(" ", strip=True)
        if tx.startswith(("👉", "·", "✅", "📋", "❌")): continue
        if len(tx) > 30 and re.search(r"[가-힣0-9A-Za-z]$", tx) and tx[-1] not in "요다죠까네음함":
            cut.append(tx[-25:])
    if cut: res.append(("S15", "FAIL", "문장이 끊긴 문단 " + str(len(cut)) + "개: …" + cut[0]))
    # S14
    if soup.find("style") or soup.find("script"): res.append(("S14", "FAIL", "style/script 태그 사용"))
    # S1 요약 박스
    first = next((t for t in soup.contents if getattr(t, "name", None)), None)
    if not first or "#eaf4fb" not in (first.get("style", "") or "") or "#2980b9" not in first.get("style", ""):
        res.append(("S1", "FAIL", "첫 요소가 파란 요약 박스가 아님"))
    elif first.get_text().count("✅") < 5:
        res.append(("S1", "FAIL", "요약 박스 ✅ 5개 미만"))
    # S2 목차 문구
    if re.search(r"목차\s*\[?\s*(펼치기|접기)|\[toc\]", html): res.append(("S2", "FAIL", "AI가 목차를 썼음"))
    # S3
    if "이런 분들이 꼭 읽어보세요" not in text: res.append(("S3", "WARN", "도입부 미니박스 없음"))
    # S4 표
    tables = soup.find_all("table")
    if len(tables) < 2: res.append(("S4", "FAIL", f"표 {len(tables)}개 (2개 이상)"))
    else:
        for t in tables:
            th = t.find("thead")
            if not th or "#2980b9" not in str(th): res.append(("S4", "FAIL", "표 thead 파란색 아님")); break
        if any(not (t.parent and t.parent.name == "div" and "overflow-x:auto" in (t.parent.get("style", "").replace(" ", ""))) for t in tables):
            res.append(("S4", "FAIL", "표가 overflow-x:auto div로 감싸지지 않음"))
    # S5 FAQ
    faq_h3 = [h for h in soup.find_all("h3") if re.match(r"\s*Q\s*[\.\d]", h.get_text())]
    if len(faq_h3) < 5: res.append(("S5", "FAIL", f"FAQ 질문(h3 'Q.') {len(faq_h3)}개 (5개 이상)"))
    # S6
    if "이런 분들 꼭 확인해보세요" not in text or text.count("👉") < 5: res.append(("S6", "FAIL", "이런 분들 박스(👉 5개) 부족"))
    # S7
    if "댓글로 남겨주세요" not in text or "background:#2980b9" not in html.replace(" ", ""): res.append(("S7", "FAIL", "결론 CTA 박스/댓글 유도 없음"))
    # S8
    if "함께 읽으면 좋은 글" not in text: res.append(("S8", "FAIL", "내부링크 박스 없음"))
    # 인용된 내부 링크
    hrefs = [a.get("href", "") for a in soup.find_all("a")]
    internal = [h for h in hrefs if h.startswith(C.WP_URL)]
    bad_int = [h for h in internal if h.rstrip("/") not in ctx["internal_urls"] and h not in ctx["internal_urls"]]
    if bad_int: res.append(("L1", "FAIL", "후보에 없는 내부링크: " + ", ".join(bad_int[:3])))
    # S9/L3a 외부
    ext = [a for a in soup.find_all("a") if a.get("href", "").startswith("http") and not a["href"].startswith(C.WP_URL)]
    btn = [a for a in ext if "noopener noreferrer" in (a.get("rel") and " ".join(a.get("rel")) or "")]
    if not btn: res.append(("S9", "FAIL", "외부 버튼(noopener noreferrer) 없음"))
    for a in ext:
        dom = re.sub(r"^https?://([^/]+).*", r"\1", a["href"]).lower()
        ok = any(dom == d or dom.endswith("." + d) for d in C.ALLOWED_DOMAINS)
        if not ok: res.append(("L3a", "FAIL", "허용 목록 밖 외부 링크: " + dom)); break
        if a.get("target") != "_blank": res.append(("L3a", "FAIL", "외부 링크 target=_blank 없음")); break
    for a in ext:
        if a.get_text(strip=True) in ("여기 클릭", "바로가기", "클릭", "여기"): res.append(("L4", "WARN", "앵커 텍스트가 모호함")); break
    # S13 계산기
    if ctx.get("calc_url"):
        if ctx["calc_url"] not in html: res.append(("S13", "FAIL", "계산기 링크 누락"))
    # K1
    n = count_chars(html) + ctx.get("extra_chars", 0)
    if n < 4000: res.append(("K1", "FAIL", f"글자 수 {n} (<4,000)"))
    elif n < 5000: res.append(("K1", "WARN", f"글자 수 {n} (<5,000)"))
    # K1b 반복
    sents = [s.strip() for s in re.split(r"[.!?\n]", text) if len(s.strip()) > 15]
    if sents:
        dup = len(sents) - len(set(sents))
        if dup / len(sents) > 0.10: res.append(("K1b", "FAIL", f"반복 문장 {dup}개"))
    # K2 포커스 키워드
    cnt = text.count(topic["main"])
    if not (6 <= cnt <= 9): res.append(("K2", "FAIL", f"포커스 키워드 '{topic['main']}' {cnt}회 (6~9)"))
    # B1 금지 문구
    for b in BANNED:
        if b in text: res.append(("B1", "FAIL", f"금지 문구 '{b}'")); break
    # B2 지어낸 경험
    if INVENT.search(text): res.append(("B2", "FAIL", "지어낸 경험 표현"))
    # B3 말투
    body = re.sub(r"\s+", " ", text)
    ends_formal = len(re.findall(r"(습니다|합니다|입니다)[.\s]", body))
    ends_all = max(1, len(re.findall(r"[.요다][\s]", body)))
    if ends_formal / ends_all > 0.10: res.append(("B3", "WARN", "~습니다 체 비율 높음"))
    # K7 날짜
    if ctx["today_label"] not in text: res.append(("K7", "FAIL", f"'{ctx['today_label']} 기준' 표기 없음"))
    other = [m for m in re.findall(r"20\d\d년 \d{1,2}월 기준", text) if m.replace(" 기준", "") != ctx["today_label"].replace("년 0", "년 ")]
    # 다른 날짜의 '기준' 표기는 허용(고시 시행일 등)하지 않고 경고만
    # S10 출처 박스
    if "이 글의 정보 출처" not in html and "정보 출처" not in text: res.append(("S10", "FAIL", "출처 표기 없음"))
    # S11 면책
    if "법적 효력이 없습니다" not in text: res.append(("S11", "FAIL", "면책문구 없음"))
    # F1 숫자 대조
    res += check_numbers(text, ctx)
    # F3 계산 검산
    for c in ctx.get("calcs", []):
        try:
            v = safe_eval(c.get("식", ""))
            want = float(str(c.get("결과", "")).replace(",", "").replace("원", "").replace("만", "") or 0)
            if abs(v - want) > max(1.0, abs(want) * 0.001) and abs(v / 10000.0 - want) > 0.01:
                res.append(("F3", "FAIL", f"계산 불일치: {c.get('식')} = {v:,.0f} (글: {c.get('결과')})"))
            else:
                ctx["allowed"].add(float(v)); ctx["allowed"].add(want)
                if v >= 10000: ctx["allowed"].add(v / 10000.0)
        except Exception:
            res.append(("F3", "WARN", f"계산식 해석 불가(검산 못 함): {c.get('식')}"))
    # F4 자료부족
    if ctx.get("lacking") and "확인" not in text: res.append(("F4", "FAIL", "자료부족인데 확인 안내 문구 없음"))
    # F5
    if ("비급여" in text or "식재료" in text or "상급침실" in text) and "마다 다" not in text:
        res.append(("F5", "FAIL", "시설별 값 언급은 '요양원마다 다르다' 문구가 필요"))
    return res

def find_bad(text, ctx):
    bad = []
    allowed = ctx["allowed"]
    yr = ctx["year"]
    t = re.sub(r"\d{4}-\d{3,4}|\d{2,4}-\d{3,4}-\d{4}", lambda m: " ", text)  # 전화번호 제거
    t = re.sub(r"\d(?:\s*[,·~]\s*\d)+(?=\s*(?:등급|단계|가지|개|번))", " ", t)  # '2,3,4,5등급' 같은 나열
    for ph in re.findall(r"\d{3,4}-\d{4}", text):
        if ph not in PHONE_OK: bad.append(ph)
    for m in NUM_RE.finditer(t):
        raw, unit = m.group(1), (m.group(2) or "").replace(" ", "")
        try: v = float(raw.replace(",", ""))
        except ValueError: continue
        if unit in ("등급", "점") and v <= 5 and unit == "등급": continue
        if unit in ("가지", "단계", "개", "번째", "번", "위", "곳", "명", "회", "배") and v <= 20: continue
        if unit in ("시간", "분") and v <= 24: continue
        if unit == "" and v < 100 and "." not in raw: continue         # 번호·목록
        if unit == "년" and yr - 1 <= v <= yr + 1: continue
        if unit == "" and 2000 <= v <= 2100: continue
        if unit == "개월" and v <= 12: continue
        if unit == "일" and v <= 31 and re.search(r"\d월\s*$", t[max(0, m.start() - 4):m.start()]): continue
        if v in allowed or (v / 10000.0) in allowed or (v * 10000.0) in allowed: continue
        if unit == "" and not (v >= 10000): continue
        bad.append(f"{raw}{unit}")
    return bad

def check_numbers(text, ctx):
    res = []
    bad = find_bad(text, ctx)
    if bad:
        uniq = list(dict.fromkeys(bad))
        ctxs = []
        for b in uniq[:3]:
            i = text.find(b)
            if i >= 0: ctxs.append(text[max(0, i - 15):i + len(b) + 10].replace("\n", " "))
        res.append(("F1", "FAIL", "사실표에 없는 숫자: " + ", ".join(uniq[:8]) + (" | 앞뒤: " + " / ".join(ctxs) if ctxs else "")))
    return res

def sanitize(html, ctx):
    """사실표에 없는 숫자가 든 문장을 지운다(표 칸은 '요양원에 확인'으로). 제목·링크 안은 건드리지 않는다. 반환: (html, 정리한 건수)"""
    from bs4 import NavigableString
    soup = BeautifulSoup(html, "html.parser")
    n = 0
    for node in list(soup.find_all(string=True)):
        if node.parent is None or node.parent.name in ("script", "style"): continue
        txt = str(node)
        bads = find_bad(txt, ctx)
        if not bads: continue
        if node.parent.name in ("a", "h1", "h2", "h3", "th", "strong", "b"):   # 문장을 지울 수 없는 자리: 숫자만 말로 바꾼다
            new = txt
            for b_ in dict.fromkeys(bads):
                pat = r"\s*".join(re.escape(ch) for ch in b_.replace(" ", ""))
                new = re.sub(pat, "일정 비율" if b_.endswith("%") else "정해진 금액" if "원" in b_ else "일정 수", new, count=0)
            if new != txt: node.replace_with(NavigableString(new)); n += 1
            continue
        if node.parent.name == "td":
            node.replace_with(NavigableString("요양원에 확인")); n += 1; continue
        sents = re.split(r"(?<=[.!?요다])\s+", txt)
        keep = [x for x in sents if not find_bad(x, ctx)]
        n += len(sents) - len(keep)
        node.replace_with(NavigableString(" ".join(keep)))
    for tag_ in soup.find_all(["p", "li"]):
        if not tag_.get_text(strip=True) and not tag_.find(["a", "img", "table"]): tag_.decompose()
    return str(soup), n

def check_links_alive(html):
    res = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        h = a.get("href", "")
        if not h.startswith("http"): continue
        try:
            r = requests.head(h, timeout=15, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code in (404, 410):
                r = requests.get(h, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code in (404, 410):
                lvl = "FAIL" if h.startswith(C.WP_URL) else ("FAIL" if r.status_code in (404, 410) else "WARN")
                res.append(("L3b" if not h.startswith(C.WP_URL) else "L1", lvl, f"{r.status_code} {h}"))
        except requests.RequestException:
            if h.startswith(C.WP_URL): res.append(("L1", "FAIL", f"내부 링크 연결 실패 {h}"))
            else: res.append(("L3b", "WARN", f"외부 링크 시간 초과 {h}"))
    return res

def check_meta(slug, existing_slugs, desc):
    r = []
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug): r.append(("K6", "FAIL", "슬러그 형식"))
    if slug in existing_slugs: r.append(("K6", "FAIL", "슬러그 중복"))
    if not (100 <= len(desc) <= 140): r.append(("K5", "WARN", f"메타 설명 {len(desc)}자"))
    return r

def summarize(items):
    fails = [x for x in items if x[1] == "FAIL"]
    warns = [x for x in items if x[1] == "WARN"]
    return fails, warns
