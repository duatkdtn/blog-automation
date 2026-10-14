# -*- coding: utf-8 -*-
"""지역별 요양원 글 생성기 v2. AI를 쓰지 않는다. 공공데이터에서 코드가 계산한 값으로 글을 만든다.
쓰는 칸: 시설명·시·군·구·동·정원·지정일·평가등급·평가연도·전화번호. 평가 점수·시설별 비용·현원(빈자리)은 쓰지 않는다.
글마다 달라지는 방법: (1) 데이터 특징에 따라 들어가는 블록이 달라진다 (2) 같은 뜻의 문장 여러 개 중 데이터와 지역 이름으로 고른다
(3) 지역 소개 문단(notes)을 사람이 데이터 근거로 써서 넣을 수 있다."""
import csv, html as H, hashlib, collections
import generator as G
import common as C

S = G.STYLE
h = lambda s: H.escape(str(s), quote=False)
GRADES = ["A", "B", "C", "D", "E"]
SHORT = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
         "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원",
         "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북",
         "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주"}

def load(fac_csv, phone_csv=None):
    ph = {}
    if phone_csv:
        for line in open(phone_csv, encoding="utf-8-sig"):
            p = line.strip().split(",")
            if len(p) >= 3 and p[2]: ph[p[0]] = p[2]
    rows = []
    for r in csv.DictReader(open(fac_csv, encoding="utf-8-sig")):
        r["cap"] = int(r["cap"] or 0)
        r["year"] = int(r["designated"][:4]) if r.get("designated") and r["designated"][:4].isdigit() else 0
        r["phone_n"] = ph.get(r["code"], r.get("phone", ""))
        rows.append(r)
    return rows

def _last(w):
    for c in reversed(w.strip()):
        if 0xAC00 <= ord(c) <= 0xD7A3 or c.isalnum(): return c
    return "가"
def _jong(w):
    c = _last(w)
    if c.isdigit(): return c in "0136478"[:0] or c in "013678"
    return 0xAC00 <= ord(c) <= 0xD7A3 and (ord(c) - 0xAC00) % 28 != 0
def q(w): return "‘" + w + "’"
def ie(w): return w + ("이에요" if _jong(w) else "예요")
def eun(w): return w + ("은" if _jong(w) else "는")
def i_(w): return w + ("이" if _jong(w) else "가")
def eul(w): return w + ("을" if _jong(w) else "를")
def ro(w):
    c = _last(w)
    return w + ("로" if not (0xAC00 <= ord(c) <= 0xD7A3) or (ord(c) - 0xAC00) % 28 in (0, 8) else "으로")
def gwa(w): return w + ("과" if _jong(w) else "와")

def _pct(a, b): return (100.0 * a / b) if b else 0.0
def pick(pool, key):
    return pool[int(hashlib.md5(key.encode()).hexdigest(), 16) % len(pool)]

def P(t, extra=""): return f'<p style="line-height:1.85;font-size:16px;margin:0 0 16px;{extra}">{t}</p>'
def NOTE(t): return f'<p style="line-height:1.85;font-size:14px;color:#666;margin:0 0 16px">{t}</p>'

def _table(head, body_rows):
    th = "".join(f'<th style="padding:10px;border:1px solid #ddd;text-align:left">{h(x)}</th>' for x in head)
    trs = ""
    for i, row in enumerate(body_rows):
        bg = "#fff" if i % 2 == 0 else "#f8f9fa"
        trs += f'<tr style="background:{bg}">' + "".join(f'<td style="padding:10px;border:1px solid #ddd">{c}</td>' for c in row) + "</tr>"
    return (f'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse"><thead style="background:#2980b9;color:#fff"><tr>{th}</tr></thead>'
            f'<tbody>{trs}</tbody></table></div>')

def stats(rows):
    n = len(rows); cap = sum(r["cap"] for r in rows)
    g = collections.Counter(r["grade"] for r in rows if r["grade"] in GRADES)
    graded = sum(g.values())
    small = sum(1 for r in rows if r["cap"] < 30); mid = sum(1 for r in rows if 30 <= r["cap"] < 80); large = sum(1 for r in rows if r["cap"] >= 80)
    old = sum(1 for r in rows if 0 < r["year"] <= 2014); midy = sum(1 for r in rows if 2015 <= r["year"] <= 2019); new = sum(1 for r in rows if r["year"] >= 2020)
    return {"n": n, "cap": cap, "g": g, "graded": graded, "none": n - graded, "small": small, "mid": mid, "large": large,
            "old": old, "midy": midy, "new": new}

def _rel(x, y):
    d = x - y
    return "same" if abs(d) < 5 else ("up" if d > 0 else "down")

def build(sido_full, sigungu, rows_all, today, code5, internal_links, note=None):
    sido_short = SHORT.get(sido_full, sido_full)
    a03 = [r for r in rows_all if r["type"] == "A03"]
    here = [r for r in a03 if r["sido"] == sido_full and r["sigungu"] == sigungu]
    coh = [r for r in rows_all if r["type"] == "A04" and r["sido"] == sido_full and r["sigungu"] == sigungu]
    sido_rows = [r for r in a03 if r["sido"] == sido_full]
    st, ss, sn = stats(here), stats(sido_rows), stats(a03)
    place = f"{sido_short} {sigungu}"
    K = place
    n, cap = st["n"], st["cap"]
    avg = round(cap / n) if n else 0
    big = max(here, key=lambda r: r["cap"]); small = min(here, key=lambda r: r["cap"])
    a_share, a_sido, a_nat = _pct(st["g"]["A"], st["graded"]), _pct(ss["g"]["A"], ss["graded"]), _pct(sn["g"]["A"], sn["graded"])
    rel = _rel(a_share, a_nat) if st["graded"] else "none"
    dong = collections.Counter(r["dong"] for r in here if r["dong"])
    dtop = dong.most_common(1)[0] if dong else None
    dom_size = max(("small", "mid", "large"), key=lambda k: st[k]) if n else "mid"
    dom_year = max(("old", "midy", "new"), key=lambda k: st[k]) if n else "midy"
    skw = f"{sigungu} 요양원"

    title = f"{place} 요양원 {n}곳, 정원·평가등급 정리"
    slug = f"nursing-homes-{code5}"

    # ── 요약 박스
    size_word = {"small": "작은 곳이 많은 편", "mid": "중간 규모가 많은 편", "large": "큰 시설이 많은 편"}[dom_size]
    gtxt = {"up": "A등급 비율이 전국 평균보다 높아요", "same": "A등급 비율이 전국 평균과 비슷해요", "down": "A등급 비율이 전국 평균보다 낮아요", "none": "평가등급 정보가 아직 없어요"}[rel]
    items = [pick([f"{place}에는 노인요양시설(요양원)이 {n}곳 있어요", f"{eul(place)} 기준으로 요양원은 {n}곳이에요"], K + "s1"),
             pick([f"시설 규모는 {size_word}이에요", f"정원으로 보면 {size_word}이에요"], K + "s2"),
             f"평가등급은 {gtxt}",
             pick([f"정원이 가장 큰 곳은 {ie(q(big['name']))}", f"가장 큰 시설은 {ie(q(big['name']))}"], K + "s4"),
             pick(["시설별 비용과 빈자리는 공공 자료에 없어서 전화로 확인해야 해요", "비용과 빈자리는 공공 자료에 없으니 전화로 물어보세요"], K + "s5")]
    before = f'<div style="{S["summary"]}"><p style="margin:0 0 12px;font-weight:bold;font-size:18px;color:#2c3e50">{h(pick(["이 글에서 알 수 있어요", "먼저 핵심만 볼까요", "한눈에 보는 핵심"], K+"k5"))}</p>' + \
             "".join(f'<p style="margin:0 0 8px;font-size:16px;line-height:1.7">✅ {h(x)}</p>' for x in items) + "</div>"

    # ── 도입
    openers = [f"부모님을 모실 {eul(skw)} 찾다 보면, 어느 곳이 어떤 곳인지 한눈에 보기가 어렵더라고요.",
               f"{eul(skw)} 알아보시는데 시설 이름만 줄줄이 나와서 막막하셨던 적 있으시죠.",
               f"{place}에서 요양원을 알아보는 분들이 제일 먼저 궁금해하시는 건 ‘어디에 몇 곳이 있나’예요.",
               f"요양원은 이름만 봐서는 차이를 알기 어려워요. 그래서 {place}의 시설을 자료로 먼저 정리해 봤어요."]
    ft = {"up": "평가에서 A등급을 받은 곳의 비율이 전국 평균보다 높은 지역이에요.",
          "same": "평가등급 분포는 전국 평균과 크게 다르지 않아요.",
          "down": "평가에서 A등급을 받은 곳의 비율이 전국 평균보다 낮은 지역이라, 등급을 꼼꼼히 확인해 보시는 게 좋아요.",
          "none": "평가등급 정보가 없는 시설이 많아 직접 확인이 더 중요해요."}[rel]
    mid_p = note if note else pick([f"이 글은 {place}의 노인요양시설을 공공 자료로 정리했어요. {ft}", f"{place} 시설의 규모, 지정 시기, 평가등급을 공공 자료로 모았어요. {ft}"], K + "i2")
    intro = P(h(pick(openers, K + "i1"))) + P(h(mid_p)) + P(h(pick(
        ["비용은 시설마다 달라서 공공 자료에는 없어요. 마음에 드는 곳을 골라 전화로 물어보실 수 있게 전화번호를 함께 적었어요.",
         "한 달 비용과 빈자리는 공공 자료에서 찾을 수 없어요. 대신 전화번호를 같이 실어 두었으니 직접 물어보세요."], K + "i3")))
    mini = (f'<div style="{S["mini"]}"><strong>{h(pick(["🙋 이런 분들이 꼭 읽어보세요", "🙋 이런 분께 맞는 글이에요", "🙋 이럴 때 읽어보세요"], K+"m0"))}</strong><br>· ' + h(pick([eul(skw)+" 처음 알아보는 가족", eul(skw)+" 비교해 보려는 자녀", "부모님 시설을 찾기 시작한 분"], K+"m1")) + '<br>'
            '· ' + h(pick(["우리 동네 시설이 어떤 곳들인지 궁금한 분", "근처에 시설이 얼마나 되는지 알고 싶은 분", "시설 이름만 알고 정보가 없는 분"], K+"m2")) + '<br>· ' + h(pick(["평가등급을 보고 시설을 고르고 싶은 보호자", "전화해 볼 후보를 추리고 싶은 보호자", "등급과 규모를 같이 보고 싶은 분"], K+"m3")) + '</div>')

    # ── 한눈에 보기
    sec1 = f'<h2 style="{S["h2"]}">{h(pick([place+" 요양원 한눈에 보기", place+" 요양원은 어떤 곳들일까요", place+" 요양원 현황 먼저 보기", "먼저 "+place+" 전체 모습부터"], K+"h1"))}</h2>'
    lead = {"small": f"{place}은 규모가 작은 시설이 많은 지역이에요.", "mid": f"{place}은 중간 규모 시설이 중심인 지역이에요.",
            "large": f"{place}은 큰 시설이 많은 지역이에요."}[dom_size]
    lead = lead.replace(place + "은", eun(place))
    lead2 = pick([f"시설은 모두 {n}곳이고, 정원을 합치면 {cap:,}명이에요.", f"노인요양시설 {n}곳을 합친 정원은 {cap:,}명이에요."], K + "o1")
    if dtop and n > 3 and dtop[1] >= 2: lead2 += f" " + pick([f"{dtop[0]}에 가장 많이 모여 있어요.", f"시설이 제일 많은 동네는 {dtop[0]}이에요.", f"{dtop[0]} 쪽에 시설이 몰려 있는 편이에요."], K+"o2")
    sec1 += P(h(lead) + " " + h(lead2))
    ov = [["시설 수(노인요양시설)", f"{n}곳"], ["정원 합계", f"{cap:,}명"], ["한 곳 평균 정원", f"{avg}명"],
          ["가장 큰 곳", f"{h(big['name'])} ({big['cap']}명)"], ["가장 작은 곳", f"{h(small['name'])} ({small['cap']}명)"]]
    sec1 += _table(["구분", "내용"], ov)
    extra = ""
    if coh: extra = " " + pick([f"소규모 노인요양공동생활가정은 별도로 {len(coh)}곳이 있고, 이 글의 표에서는 뺐어요.", f"정원이 아주 적은 공동생활가정 {len(coh)}곳은 따로 있어서 이 표에는 넣지 않았어요.", f"작은 규모의 공동생활가정이 {len(coh)}곳 더 있지만 이 글에서는 제외했어요."], K+"n6")
    sec1 += NOTE(pick(["정원은 받을 수 있는 인원이고, 지금 비어 있는 자리 수가 아니에요. 빈자리는 공공 자료에 없어서 전화로 확인하셔야 해요.", "표의 정원은 최대 인원이에요. 현재 몇 분이 계신지는 자료에 없으니 전화로 물어보세요.", "정원이 곧 빈자리는 아니에요. 입소 가능 여부는 시설마다 다르니 꼭 전화로 확인하세요.", "여기 적힌 정원은 기준 인원이고 현재 입소자 수와는 달라요. 빈자리는 시설에 문의하세요."], K+"n1") + extra)

    sec_size = ""
    if n >= 4:
        sec_size = f'<h3 style="{S["h3"]}">{h(pick(["규모로 나눠 보면", "큰 곳과 작은 곳의 비율", "시설 크기는 어떤가요", "정원 규모별로 정리하면"], K+"h2"))}</h3>'
        txt = {"small": ["정원이 30명 안 되는 작은 시설이 가장 많아요. 가족적인 분위기를 찾는 분께 맞을 수 있어요.", "작은 시설이 중심이에요. 방문해서 분위기를 직접 보고 고르시기 좋아요."],
               "mid": ["정원이 30명에서 80명 사이의 중간 규모가 가장 많아요. 가장 흔한 형태예요.", "중간 규모가 중심이라 선택의 폭이 넓은 편이에요."],
               "large": ["정원이 80명 이상인 큰 시설이 가장 많아요. 프로그램과 인력이 다양한 편이지만 방문해서 분위기를 보세요.", "큰 시설이 중심이에요. 규모가 큰 만큼 생활 방식을 꼭 확인해 보세요."]}[dom_size]
        sec_size += P(h(pick(txt, K + "z1")))
        sec_size += _table(["규모", "시설 수"], [["작은 곳 (정원 30명 미만)", f"{st['small']}곳"], ["중간 (30명~79명)", f"{st['mid']}곳"], ["큰 곳 (80명 이상)", f"{st['large']}곳"]])
    sec_year = ""
    if n >= 4 and st["old"] + st["midy"] + st["new"] >= 3:
        sec_year = f'<h3 style="{S["h3"]}">{h(pick(["언제 문을 열었나", "오래된 곳과 새 시설", "지정된 시기별로 보면", "시설이 생긴 시기"], K+"h3"))}</h3>'
        txt = {"old": ["2014년 이전에 지정된 곳이 가장 많아요. 오래 운영된 시설이 많다는 뜻이에요.", "오래된 시설이 중심이에요. 건물 상태와 시설 개선 여부를 직접 보시는 게 좋아요."],
               "midy": ["2015년에서 2019년 사이에 지정된 곳이 가장 많아요.", "비교적 최근 십 년 사이에 생긴 시설이 중심이에요."],
               "new": ["2020년 이후에 새로 지정된 곳이 가장 많아요. 비교적 새 시설이 많은 지역이에요.", "최근에 생긴 시설이 많아요. 새 건물이 많은 대신 운영 기록이 짧을 수 있어요."]}[dom_year]
        sec_year += P(h(pick(txt, K + "y1")))
        sec_year += _table(["지정 시기", "시설 수"], [["2014년 이전", f"{st['old']}곳"], ["2015~2019년", f"{st['midy']}곳"], ["2020년 이후", f"{st['new']}곳"]])
        sec_year += NOTE(pick(["지정 시기는 장기요양기관으로 지정된 해를 기준으로 했어요.", "문을 연 해가 아니라 장기요양기관으로 지정된 해예요.", "표의 시기는 지정받은 해 기준이에요."], K+"n2"))

    # ── 평가등급
    sec2 = f'<h2 style="{S["h2"]}">{h(pick([place+" 요양원 평가등급", "평가등급으로 본 "+place, place+" 시설들의 평가 결과", place+" 요양원 등급 분포"], K+"h4"))}</h2>'
    if st["graded"]:
        txt = {"up": [f"결론부터 말하면, {eun(sigungu)} A등급 비율이 전국 평균보다 높은 편이에요.", f"{eun(sigungu)} 전국과 비교하면 A등급 비율이 높은 곳이에요."],
               "same": [f"결론부터 말하면, {eun(sigungu)} 전국 평균과 비슷한 수준이에요.", f"{eun(sigungu)} A등급 비율이 전국과 큰 차이가 없어요."],
               "down": [f"결론부터 말하면, {eun(sigungu)} A등급 비율이 전국 평균보다 낮은 편이에요.", f"{eun(sigungu)} 전국과 비교하면 A등급 비율이 낮은 곳이에요."]}[rel]
        sec2 += P(h(pick(txt, K + "g1")) + " " + h(f"{sido_short} 전체와 견줘 봐도 {'높은' if a_share > a_sido + 4 else ('낮은' if a_share < a_sido - 4 else '비슷한')} 편이에요."))
        sec2 += _table(["평가등급", "시설 수", "비율"], [[f"{k}등급", f"{st['g'][k]}곳", f"{_pct(st['g'][k], st['graded']):.0f}%"] for k in GRADES])
        sec2 += NOTE(pick([f"A가 가장 높은 등급이에요. 평가를 받은 시설만 세었고, 평가 결과가 없는 {st['none']}곳은 새로 문을 열었거나 평가 대상이 아닐 수 있어요.", f"평가 결과가 없는 {st['none']}곳은 제외하고 센 결과예요. 새 시설이거나 평가 대상이 아닌 경우가 있어요. A가 가장 높은 등급이에요.", f"등급은 A가 가장 높아요. {st['none']}곳은 평가 정보가 없어 빠졌어요."], K+"n3b") if st["none"] else pick(["A가 가장 높은 등급이에요. 평가를 받은 시설만 세었어요.", "평가를 받은 시설만 센 결과이고 A가 가장 높아요.", "A에서 E까지 있고 A가 가장 높은 등급이에요."], K+"n3"))
    else:
        sec2 += P("이 지역 시설은 아직 공개된 평가등급 정보가 없어요. 시설에 직접 물어보세요.")

    # ── 목록
    shown = sorted(here, key=lambda r: (-r["cap"], r["name"]))[:60]
    sec3 = f'<h2 style="{S["h2"]}">{h(pick([place+" 요양원 전체 목록", place+" 요양원 이름과 전화번호", "시설별로 하나씩 보기", place+" 노인요양시설 목록"], K+"h5"))}</h2>'
    body = []
    for r in shown:
        ph = r["phone_n"]
        tel = f'<a href="tel:{ph.replace("-", "")}" style="color:#2980b9">{h(ph)}</a>' if ph else "공단에 확인"
        gr = (f'{r["grade"]}등급' + ("" if str(r.get("eval_year")) == "2025" else f' ({r["eval_year"]}년)')) if r["grade"] in GRADES and r.get("eval_year") else "정보 없음"
        body.append([h(r["name"]), h(r["dong"] or "-"), f'{r["cap"]}명', gr, tel])
    sec3 += _table(["시설명", "동", "정원", "평가등급(2025년 기준)", "전화"], body)
    sec3 += NOTE(pick(["정원이 큰 순서로 정리했어요.", "큰 시설부터 차례로 실었어요.", "정원이 많은 곳이 위에 오도록 정리했어요."], K+"n4") + (f" {len(shown)}곳만 실었어요." if n > len(shown) else "") + " " + pick(["전화번호는 공공 자료에 올라 있는 번호 그대로예요.", "번호는 공공 자료에 나온 그대로 적었어요.", "연락처는 공개된 자료 기준이에요."], K+"n5"))

    # ── 시설 몇 곳 살펴보기 (시설마다 다른 실제 값으로 쓴 문장)
    spot = ""
    if n >= 3:
        top3 = sorted(here, key=lambda r: (-r["cap"], r["name"]))[:3]
        newest = max((r for r in here if r["year"]), key=lambda r: (r["year"], r["name"]), default=None)
        oldest = min((r for r in here if r["year"]), key=lambda r: (r["year"], r["name"]), default=None)
        def line(r, i):
            dn = r["dong"] or sigungu
            g = f"{r['grade']}등급" if r["grade"] in GRADES else None
            nm = r["name"]; Q = q(nm)
            t = [f"{dn}의 {eun(Q)} 정원이 {r['cap']}명이에요." + (f" 평가는 {ie(g)}." if g else " 평가 정보는 없어요."),
                 f"{dn}에 있는 {eun(Q)} 정원 {r['cap']}명 규모예요." + (f" 평가등급은 {ro(g)} 나와 있어요." if g else ""),
                 f"{eun(Q)} {dn}에 있고, {r['cap']}명까지 모실 수 있어요." + (f" {eul(g)} 받았어요." if g else ""),
                 f"정원 {r['cap']}명인 {eun(Q)} {dn}에 자리해 있어요." + (f" 평가 결과는 {ie(g)}." if g else ""),
                 f"{dn}에서는 {i_(Q)} 정원 {r['cap']}명으로 알려져 있어요." + (f" 등급은 {ie(g)}." if g else "")]
            return pick(t, K + r["code"] + str(i))
        spot = f'<h3 style="{S["h3"]}">{h(pick(["정원이 큰 곳 세 군데", "먼저 눈에 띄는 큰 시설들", "규모 순으로 세 곳만 짚어 보면"], K+"h10"))}</h3>' + \
               "".join(P(h(line(r, i))) for i, r in enumerate(top3))
        if newest and oldest and newest["code"] != oldest["code"]:
            nn, on = q(newest["name"]), q(oldest["name"])
            sp2 = pick([f"가장 최근에 지정된 곳은 {nn}{'이고' if _jong(newest['name']) else '고'} {newest['year']}년에 지정됐어요. 가장 오래된 곳은 {ro(on)} {oldest['year']}년이에요.",
                        f"지정 시기로 보면 {i_(on)} {oldest['year']}년으로 가장 앞서고, {i_(nn)} {newest['year']}년으로 가장 최근이에요.",
                        f"{newest['year']}년에 지정된 {eun(nn)} 가장 새 시설이고, {oldest['year']}년 지정의 {i_(on)} 가장 오래됐어요."], K+"sp2")
            spot += P(h(sp2))
    # ── 동별
    sec6 = ""
    if len(dong) >= 3:
        rows6 = [[h(d_), f"{c_}곳", f"{sum(r['cap'] for r in here if r['dong']==d_):,}명"] for d_, c_ in sorted(dong.items(), key=lambda x: (-x[1], x[0]))[:10]]
        sec6 = f'<h2 style="{S["h2"]}">{h(pick([sigungu+" 동네별로 보면", "어느 동네에 많을까요", sigungu+" 안에서 시설이 모인 곳", "가까운 동네부터 찾기"], K+"h6"))}</h2>' + P(h(pick([f"{dtop[0]}에 시설이 가장 많고, 그다음부터는 동네마다 한두 곳씩 흩어져 있어요.", f"시설은 {dtop[0]}에 가장 많이 모여 있어요. 가까운 동네부터 둘러보시면 편해요."], K + "d1"))) + _table(["동", "시설 수", "정원 합계"], rows6)

    # ── 시·도 비교
    by_g = collections.defaultdict(list)
    for r in sido_rows: by_g[r["sigungu"]].append(r)
    tab = []
    for g_, rr in by_g.items():
        s_ = stats(rr); tab.append((g_, s_["n"], s_["cap"], _pct(s_["g"]["A"], s_["graded"]), s_["graded"]))
    tot = len(tab); rk_n = 1 + sum(1 for x in tab if x[1] > n)
    sec5 = ""
    if tot >= 3:
        pos = "많은 편" if rk_n <= tot / 3 else ("적은 편" if rk_n > 2 * tot / 3 else "중간 정도")
        top5 = sorted(tab, key=lambda x: (-x[1], x[0]))[:5]
        rows5 = [[h(x[0]), f"{x[1]}곳", f"{x[2]:,}명", (f"{x[3]:.0f}%" if x[4] else "-")] for x in top5]
        if sigungu not in [x[0] for x in top5]:
            me = next(x for x in tab if x[0] == sigungu)
            rows5.append([h(sigungu) + " (이 글)", f"{me[1]}곳", f"{me[2]:,}명", (f"{me[3]:.0f}%" if me[4] else "-")])
        txtp = {"많은 편": f"{sido_short}에서 {eun(sigungu)} 요양원이 많은 편에 들어요.", "적은 편": f"{sido_short}에서 {eun(sigungu)} 요양원이 적은 편이에요. 옆 지역까지 함께 보시면 선택지가 넓어져요.",
                "중간 정도": f"{sido_short}에서 {eun(sigungu)} 시설 수가 중간 정도예요."}[pos]
        sec5 = f'<h2 style="{S["h2"]}">{h(pick([sido_short+" 안에서 비교하면", "이웃 지역과 견주어 보면", sido_short+"의 다른 지역은 어떨까요", sido_short+" 시·군·구와 나란히 놓고 보기"], K+"h7"))}</h2>' + P(h(txtp) + " " + h(pick(["시설이 많은 곳 몇 군데와 나란히 놓고 보세요.", "시설 수가 많은 지역 다섯 곳과 비교한 표예요.", "아래 표에서 이웃 지역과 견주어 보세요.", "비교하기 쉽게 표로 모았어요."], K+"o3"))) + _table(["지역", "시설 수", "정원 합계", "A등급 비율"], rows5)

    # ── 고를 때 / 오해 / 이런분들
    tips_all = ["한 달 비용은 시설마다 달라서 전화로 직접 물어보세요", "지금 들어갈 자리가 있는지 확인하세요", "평가등급과 함께 직접 방문해서 분위기를 보세요",
                "우리 부모님 본인부담금은 계산기로 미리 계산해 보세요", "비급여 항목(식비·간식비 등)이 어디까지인지 서면으로 받아 두세요", "집에서 가까운 곳을 먼저 보면 자주 찾아뵙기 좋아요", "면회 시간과 방문 규칙이 어떤지 물어보세요", "식사와 간식이 어떻게 나오는지 직접 보세요", "병원과 얼마나 가까운지, 응급 때 어떻게 하는지 확인하세요", "방 구조(몇 인실)와 개인 물품 보관 방식을 물어보세요", "입소 전에 계약서를 먼저 받아서 읽어 보세요", "프로그램(운동·인지활동)이 어떻게 운영되는지 물어보세요"]
    extra_tip = {"large": "큰 시설은 층·구역별로 생활이 다를 수 있으니 부모님이 지낼 구역을 꼭 보세요", "small": "작은 시설은 인력 배치와 야간 돌봄 방식을 꼭 물어보세요", "mid": "정원 대비 요양보호사 수를 물어보세요"}[dom_size]
    k = int(hashlib.md5((K + "t").encode()).hexdigest(), 16)
    tips = [tips_all[(k + i) % len(tips_all)] for i in range(4)] + [extra_tip]
    sec4 = (f'<h2 style="{S["h2"]}">{h(pick([place+"에서 요양원 고를 때 확인할 것", "전화하기 전에 챙길 것들", "후보를 고르는 순서", "방문 전에 알아두면 좋은 것"], K+"h8"))}</h2>'
            f'<div style="background:#f0f8ff;border-left:4px solid #2980b9;padding:14px 18px;margin:0 0 16px;line-height:1.9;font-size:16px">' + "<br>".join("· " + h(t) for t in tips) + "</div>"
            '<p style="line-height:1.85;font-size:16px;margin:0 0 16px">시설 정보는 <a href="https://www.longtermcare.or.kr" target="_blank" rel="noopener" style="color:#2980b9">국민건강보험공단 노인장기요양보험 공식 사이트</a>' + pick(["에서도 조회할 수 있어요.", "에서 시설 정보를 더 찾아볼 수 있어요.", "에 가면 기관별 정보를 확인할 수 있어요."], K+"o4") + '</p>')
    myth_all = [("평가등급이 높으면 무조건 좋은 시설이다", "등급은 평가 때의 기록이에요. 방문해서 직접 보는 것도 꼭 필요해요."),
                ("정원이 크면 자리가 많이 남아 있다", "정원은 받을 수 있는 인원이지 지금 빈자리가 아니에요. 전화로 확인하세요."),
                ("요양원 비용은 어디나 똑같다", "나라가 정한 급여는 같지만 식비 같은 비급여 항목은 시설마다 달라요."),
                ("평가 정보가 없으면 나쁜 시설이다", "새로 문을 열었거나 평가 대상이 아닌 경우도 있어요. 직접 물어보세요."),
                ("가까운 곳이 무조건 제일 좋다", "가까운 것도 중요하지만 부모님 상태에 맞는 돌봄인지 함께 보세요."),
                ("새로 생긴 시설이 더 좋다", "새 건물은 좋지만 운영 기록이 짧을 수 있어요. 돌봄 인력과 운영 방식을 함께 보세요."),
                ("한 번 입소하면 옮길 수 없다", "상황에 따라 시설을 옮길 수 있어요. 불편하면 공단이나 시설에 상담해 보세요."),
                ("전화번호가 같으면 같은 시설이다", "같은 법인이 여러 시설을 운영하면 번호가 같을 수 있어요. 이름과 주소로 구분하세요.")]
    m0 = k % len(myth_all); myths = [myth_all[m0], myth_all[(m0 + 3) % len(myth_all)]]
    mybox = (f'<div style="background:#fdf2f8;border:1px solid #d2b4de;border-radius:8px;padding:18px 22px;margin:24px 0">'
             f'<p style="margin:0 0 10px;font-weight:bold;font-size:18px;color:#2c3e50">{h(pick(["흔한 오해", "이렇게 알고 계시면 달라요", "자주 하는 착각"], K+"b1"))}</p>' +
             "".join(f'<p style="margin:0 0 10px;font-size:16px;line-height:1.8">❌ “{h(a)}” → {h(b)}</p>' for a, b in myths) + "</div>")

    # ── FAQ
    big_name = big["name"]
    faq_items = [(pick([f"{place}에는 요양원이 몇 곳 있나요?", f"{skw}은 모두 몇 곳이에요?"], K + "q1"), pick([f"공공 자료 기준으로 {n}곳이에요.", f"노인요양시설로 등록된 곳은 {n}곳이에요."], K + "a1")),
                 (pick([f"{sigungu} 요양원 비용은 얼마인가요?", f"{sigungu}에서 한 달 비용은 어느 정도예요?", f"{skw} 비용은 어디서 알 수 있나요?"], K+"q2"), pick(["시설별 비용은 공공 자료에 없어요. 본인부담금은 계산기로 미리 계산해 보시고, 입소할 곳에는 전화로 확인하세요.", "정해진 금액을 알려드리기 어려워요. 나라가 정한 부분은 계산기로 보시고, 식비 같은 비급여는 시설에 직접 물어보세요."], K + "a2")),
                 (pick([f"{sigungu}에서 정원이 가장 큰 요양원은 어디인가요?", f"{sigungu}에서 제일 큰 시설은 어디예요?", f"가장 많은 분을 모실 수 있는 곳은 어디인가요?"], K+"q3"), pick([f"공공 자료 기준으로 {ie(q(big_name))}. 정원이 크다고 빈자리가 있다는 뜻은 아니에요.", f"{i_(q(big_name))} 가장 커요. 다만 빈자리는 전화로 확인하셔야 해요.", f"정원으로는 {i_(q(big_name))} 가장 커요. 규모와 빈자리는 별개예요."], K+"a3")),
                 (pick(["평가등급은 무엇인가요?", "평가등급은 어떻게 보는 건가요?", "A등급이면 가장 좋은 건가요?"], K+"q4"), pick(["장기요양기관 평가에서 받은 등급이에요. A가 가장 높은 등급이에요.", "시설 운영을 평가해서 매긴 등급이에요. A부터 E까지 있고 A가 가장 좋아요."], K + "a4"))]
    faq = f'<h2 style="{S["h2"]}">{h(pick(["자주 묻는 질문", "많이 물어보시는 것들", "궁금한 점 짚어보기", place+" 요양원, 이것이 궁금해요"], K+"h9"))}</h2>' + "".join(
        f'<h3 style="{S["h3"]}">Q. {h(q)}</h3><div style="{S["faq"]}"><p style="margin:0;line-height:1.85;font-size:16px">A. {h(a)}</p></div>' for q, a in faq_items)
    who_all = ["부모님 입소 시기를 고민하는 가족", "형제들과 시설 후보를 나눠 보려는 분", "요양병원과 요양원 사이에서 고민하는 분", "등급 판정은 받았는데 어디 갈지 모르는 가족", f"{skw}을 처음 알아보는 자녀", "시설 이름만 있고 정보가 없어 막막한 분", "평가등급을 보고 후보를 줄이고 싶은 분", "가까운 동네에 어떤 시설이 있는지 궁금한 분",
               "전화해 볼 시설 목록이 필요한 보호자", "다른 지역과 비교해 보고 싶은 분"]
    w0 = k % len(who_all); who = [who_all[(w0 + 3 * i) % len(who_all)] for i in range(4)]
    whobox = (f'<div style="{S["who"]}"><p style="margin:0 0 12px;font-weight:bold;font-size:18px;color:#2c3e50">{h(pick(["✅ 이런 분들 꼭 확인해보세요!", "✅ 이런 분께 도움이 돼요", "✅ 이런 상황이라면 꼭 보세요"], K+"k4"))}</p>' +
              "".join(f'<p style="margin:0 0 8px;font-size:16px">👉 {h(x)}</p>' for x in who) + "</div>")

    calc = (f'<div style="{S["calc"]}"><p style="margin:0 0 10px;font-weight:bold;font-size:18px;color:#2c3e50">{h(pick(["우리 부모님은 한 달에 얼마를 낼까요?", "본인이 내는 돈은 얼마일까요?", "내 경우 비용은 계산기로 확인하세요"], K+"k1"))}</p>'
            f'<p style="margin:0 0 14px;font-size:16px">{h(pick(["본인부담금 계산기로 바로 확인해 보세요.", "등급과 소득만 고르면 금방 나와요.", "부모님 상황에 맞춰 직접 계산해 볼 수 있어요."], K+"k2"))}</p>'
            f'<a href="{C.CALC["copayment"]}" style="{S["btn"]}">{h(pick(["본인부담금 계산기 해보기", "계산기로 확인하기", "내 본인부담금 계산해 보기"], K+"k6"))}</a></div>')
    cta = (f'<div style="{S["cta"]}"><p style="margin:0 0 12px;font-size:20px;font-weight:bold">{h(pick(["마음에 드는 곳 두세 곳에 먼저 전화해 보세요", "후보를 두세 곳으로 줄여서 직접 가 보세요", "전화 한 통이 가장 정확한 정보예요"], K + "c1"))}</p>'
           f'<p style="margin:0 0 12px;font-size:16px;line-height:1.8">{h(pick([f"{place}의 시설은 이 글의 표에서 골라 보세요. 비용과 빈자리는 전화로 물어보는 게 가장 정확해요.", f"표에서 후보를 고르고, 비용과 빈자리는 직접 물어보세요."], K + "c2"))}</p>'
           f'<p style="margin:0 0 12px;font-size:16px;line-height:1.8">{h(pick(["비슷한 주제로 요양원 비용 정리도 해뒀으니 함께 참고해보세요!", "비용이 궁금하시면 요양원 비용 정리 글도 함께 보세요!", "본인부담금이 궁금하시면 관련 글도 정리해 뒀어요!"], K+"c3"))}</p>'
           f'<p style="margin:0;font-size:16px">{h(pick(["궁금한 점은 댓글로 남겨주세요 :)", "물어보고 싶은 게 있으면 댓글 남겨주세요 :)", "더 궁금한 건 댓글로 알려주세요 :)"], K+"c4"))}</p></div>')
    links = "".join(f'<p style="margin:0 0 10px;font-size:16px">👉 <a href="{u}" style="color:#2980b9">{h(t)}</a></p>' for t, u in internal_links)
    linkbox = f'<div style="{S["links"]}"><p style="margin:0 0 12px;font-weight:bold;font-size:18px;color:#2c3e50">{h(pick(["📌 함께 읽으면 좋은 글", "📌 이어서 보면 좋은 글", "📌 같이 찾아보시는 글"], K+"k3"))}</p>{links}</div>'
    button = f'<p style="text-align:center;margin:30px 0"><a href="https://www.longtermcare.or.kr" target="_blank" rel="noopener noreferrer" style="{S["btn"]}">{pick(["🔗 국민건강보험공단 장기요양 바로가기", "🔗 장기요양보험 공식 사이트 가기", "🔗 국민건강보험공단 노인장기요양보험"], K+"k7")}</a></p>'
    src = (f'<div style="{S["src"]}">📋 이 글의 정보 출처: ' + pick(["국민건강보험공단 장기요양기관 정보(보건복지데이터포털 공공데이터)와 장기요양기관 평가 결과 자료 기준으로 작성되었습니다.", "보건복지데이터포털에 공개된 장기요양기관 정보와 국민건강보험공단의 평가 결과를 기준으로 정리했습니다.", "공공데이터(장기요양기관 정보, 평가 결과)를 기준으로 작성되었습니다. 제공: 국민건강보험공단."], K+"s9") + '</div>')
    disc = (f'<div style="{S["disc"]}">{today} 기준 작성. 시설 정보와 평가 결과는 수시로 변경될 수 있으므로, 실제 이용 전 국민건강보험공단 및 해당 요양원에서 최신 정보를 반드시 확인하세요. '
            f'이 글은 정보 제공 목적으로 작성되었으며, 법적 효력이 없습니다.</div>')
    after = (f'<p style="font-size:14px;color:#888;margin:0 0 18px">{today} 기준</p>' + intro + mini + sec1 + sec_size + sec_year + sec2 + sec3 + spot + sec6 + sec5 + sec4 + mybox + faq + whobox + calc + cta + linkbox + button + src + disc)
    desc = f"{place} 요양원은 {n}곳이에요. 시설별 정원과 평가등급, 전화번호를 공공 자료로 한 번에 볼 수 있게 정리했어요. 비용은 전화로 확인하세요."
    return {"title": title, "slug": slug, "before": before, "after": after, "meta_description": desc, "focus": f"{sigungu} 요양원", "n": n, "cap": cap}
