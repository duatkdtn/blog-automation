# -*- coding: utf-8 -*-
"""우리동네 요양원 글 자동 발행 — 하루 1회 실행(4개). 흐름은 claude/자동화_코드설계_초안.md 참조.
사용: python care_auto_publish.py [--check-existing] [--n 4]"""
import sys, os, re, json, datetime, argparse, traceback
import common as C
import checker as K
import generator as G
import thumbnail as T
import mailer as M
if os.environ.get("URI_MOCK") == "1":
    import mock_ai; mock_ai.install(G)

YEAR_WORDS = ["비용", "본인부담", "한도", "수가", "감경", "지원금", "급여", "단가", "한도액"]

def year_topic(t):
    s = t["main"] + t["detail"]
    return any(w in s for w in YEAR_WORDS)

def calc_for(meta, topic):
    c = meta.get("calculator")
    return C.CALC.get(c) if c in C.CALC else None

def category_urls():
    return {f"{C.WP_URL}/category/{s}": s for s in C.CATEGORIES}

def pick_links(self_cat, posts, k=4):
    """같은 카테고리 공개 글 우선, 부족하면 다른 공개 글, 그래도 부족하면 카테고리 페이지."""
    pub = [p for p in posts if p["status"] == "publish"]
    cat_id = C.CATEGORIES.get(self_cat)
    same = [p for p in pub if cat_id in p.get("categories", [])]
    other = [p for p in pub if p not in same]
    out = [(p["title"], p["link"]) for p in (same + other)[:k]]
    names = {"nursing-home-cost": "요양원 비용 글 모아보기", "care-grade": "장기요양등급 글 모아보기", "subsidy": "지원금 글 모아보기",
             "nursing-home-guide": "입소 가이드 글 모아보기", "compare": "비교 글 모아보기"}
    for s, nm in names.items():
        if len(out) >= 3: break
        u = f"{C.WP_URL}/category/{s}/"
        if all(u != x[1] for x in out): out.append((nm, u))
    return out[:4]

def select_title(cands, topic, today_year, yt, recent_patterns):
    best = None
    for c in cands:
        t = (c.get("title") or "").strip()
        res = K.check_title(t, topic, today_year, yt, recent_patterns, c.get("pattern"))
        fails = [x for x in res if x[1] == "FAIL"]; warns = [x for x in res if x[1] == "WARN"]
        score = (len(fails), len(warns))
        if best is None or score < best[0]: best = (score, c, res)
    return best

LAST_CTX = None

def run_check(topic, facts, today, meta, title, before, after, p1, p3, posts, existing_slugs):
    full = before + after
    allowed = K.build_allowed(facts, extra=G.SLOT_NUMS)
    internal = {u.rstrip("/") for u in category_urls()} | {C.WP_URL, C.WP_URL + "/"}
    for p in posts: internal.add(p["link"].rstrip("/")); internal.add(p["link"])
    for u in C.CALC.values(): internal.add(u.rstrip("/")); internal.add(u)
    for u in list(internal): internal.add(u + "/")
    calcs = (p1["meta"].get("calcs") or []) + (p3["meta"].get("calcs") or [])
    lack = (p1["meta"].get("lacking") or []) + (p3["meta"].get("lacking") or [])
    ctx = {"topic": topic, "facts": facts, "allowed": allowed, "today_label": today, "internal_urls": internal,
           "calc_url": calc_for(meta, topic), "calcs": calcs, "lacking": lack, "year": int(today[:4])}
    global LAST_CTX
    LAST_CTX = ctx
    res = K.check_html(full, ctx)
    res += K.check_meta(meta["slug"], existing_slugs, meta["meta_description"])
    res += K.check_title(title, topic, ctx["year"], year_topic(topic), [], None)[:0]
    return res, lack

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-existing", action="store_true"); ap.add_argument("--n", type=int, default=C.POSTS_PER_RUN)
    a = ap.parse_args()
    import wp_client as W
    facts = C.load_json("facts.json"); topics = C.load_json("topics.json"); hist = C.load_json("history.json", {"posts": []})
    posts = W.list_posts() if (C.WP_USER and not os.environ.get("URI_MOCK")) else hist.get("site_posts", [])
    if a.check_existing:
        return check_existing(posts, facts)
    today = C.today_label(); year = C.now_kst().year
    existing_titles = [p["title"] for p in posts]; existing_slugs = {p["slug"] for p in posts}
    pending = [t for t in topics if t["status"] == "대기"]
    if len(pending) <= 12:
        pending = replenish(topics, facts, existing_titles) or pending
    plan_topics = pending[:a.n]
    if not plan_topics:
        M.send("[우리동네 요양원] 주제 없음", "<p>발행할 주제가 없습니다. 주제 목록을 보충해 주세요.</p>"); return
    recent_patterns = [p.get("pattern") for p in hist["posts"][-5:]]
    recent_combos = [p.get("combo") for p in hist["posts"][-5:] if p.get("combo")]
    # 1단계: 제목·메타 (4개 모두) → 사전 메일
    staged = []
    for t in plan_topics:
        fb = ""
        for attempt in range(3):
            meta = G.stage1(t, facts, today, year_topic(t), recent_patterns, existing_titles, fb)
            score, cand, res = select_title(meta["titles"], t, year, year_topic(t), recent_patterns)
            if score[0] == 0: break
            fb = "; ".join(f"{x[0]} {x[2]}" for x in res if x[1] == "FAIL")
        t["_meta"] = meta; t["_title"] = cand["title"].strip(); t["_pattern"] = cand.get("pattern"); t["_title_res"] = res
        recent_patterns.append(cand.get("pattern"))
        staged.append(t)
    now = C.now_kst()
    whens = [now + datetime.timedelta(hours=C.INTERVAL_HOURS * i) for i in range(len(staged))]
    plans = [{"title": t["_title"], "when": ("즉시" if i == 0 else w.strftime("%m/%d %H:%M")), "main": t["main"], "detail": t["detail"],
              "type": t["type"], "question": t["question"], "gist": "; ".join(t["_meta"].get("outline", [])[:3])} for i, (t, w) in enumerate(zip(staged, whens))]
    M.plan_mail(plans, len(pending) - len(staged), f"{now.month}/{now.day}")
    rows, held = [], []
    first_publish = None
    for i, t in enumerate(staged):
        try:
            row = process(t, i, whens, facts, today, posts, existing_slugs, recent_combos, hist, held)
            if row: rows.append(row); posts = posts + ([{"id": row["id"], "slug": row["slug"], "link": row.get("link", ""), "status": "future" if row["state"] == "예약" else "publish",
                                                        "title": row["title"], "categories": [C.CATEGORIES.get(t["category"])]}] if row.get("id") else [])
            existing_slugs.add(row["slug"] if row else "")
        except Exception as e:
            C.log("오류", t["main"], type(e).__name__, str(e)[:200])
            traceback.print_exc()
            held.append({"title": t["_title"], "fails": [f"실행 오류 {type(e).__name__}"]})
            M.hold_mail(t["_title"], [f"실행 오류 {type(e).__name__}"], [], t)
    cost_in, cost_out = G.USAGE["in"], G.USAGE["out"]
    C.log(f"[비용] 입력 {cost_in:,} / 출력 {cost_out:,} 토큰 → 약 ${cost_in*1e-6*1.0 + cost_out*1e-6*5.0:.2f} (약 {int((cost_in*1e-6*1.0 + cost_out*1e-6*5.0)*1400):,}원)")
    cost = f"입력 {cost_in:,} / 출력 {cost_out:,} 토큰 (Haiku 단가 기준 추정 약 ${cost_in*1e-6*1.0 + cost_out*1e-6*5.0:.2f})"
    remaining = len([x for x in topics if x["status"] == "대기"])
    lacks = [l for r in rows for l in r["lack"]]
    M.result_mail(rows, held, lacks, cost, remaining, "")
    if C.DRY_RUN or os.environ.get("URI_MOCK"):
        C.log("시험 실행: 기록 파일은 저장하지 않음"); return
    C.save_json("topics.json", [{k: v for k, v in t.items() if not k.startswith("_")} for t in topics])
    hist["site_posts"] = [{"id": p["id"], "slug": p["slug"], "link": p["link"], "status": p["status"], "title": p["title"], "categories": p["categories"]} for p in posts]
    C.save_json("history.json", hist)

def process(t, i, whens, facts, today, posts, existing_slugs, recent_combos, hist, held):
    meta = t["_meta"]; title = t["_title"]
    feedback = ""; revisions = 0; fails = []; warns = []
    meta = dict(meta); meta["meta_description"] = G.fix_meta(meta, t, title)
    for attempt in range(3):               # 처음 + 고쳐쓰기 최대 2회
        codes = {f.split()[0] for f in fails}
        redo1 = attempt == 0 or not codes <= {"S5", "S6"}      # 뒷부분(FAQ·이런분들) 문제만이면 앞부분은 그대로 둔다(비용 절약)
        redo3 = attempt == 0 or not codes <= {"S4", "K1", "K1b", "K2"}   # 본문 표·분량·키워드 문제만이면 뒷부분은 그대로 둔다
        if redo1: p1 = G.stage2(t, facts, today, meta, title, feedback)
        if redo3: p3 = G.stage3(t, facts, today, meta, title, p1, feedback)
        links = pick_links(t["category"], posts)
        before, after = G.assemble(t, meta, title, p1, p3, today, links, calc_for(meta, t))
        after = G.trim_keyword(before, after, t["main"])
        res, lack = run_check(t, facts, today, meta, title, before, after, p1, p3, posts, existing_slugs)
        res += [("S0", "WARN", w) for w in dict.fromkeys(G.SLOT_WARN)]; G.SLOT_WARN.clear()
        rv = G.reviewer(t, title, K.BeautifulSoup(before + after, "html.parser").get_text(" ", strip=True), today)
        for k, lvl in (("K4", "FAIL"), ("B4", "FAIL"), ("B5", "FAIL"), ("F5", "FAIL"), ("B6", "WARN")):
            v = rv.get(k)
            if isinstance(v, dict) and v.get("ok") is False: res.append((k, lvl, v.get("why", "")))
        res += K.check_links_alive(before + after)
        fails = [f"{x[0]} {x[2]}" for x in res if x[1] == "FAIL"]
        warns = [f"{x[0]} {x[2]}" for x in res if x[1] == "WARN"]
        C.log(f"[시도 {attempt+1}] 실패 {len(fails)}개:", "; ".join(fails)[:600], "| 경고", len(warns))
        if fails and attempt == 2 and all(f.startswith("F1") for f in fails):
            b2, n1 = K.sanitize(before, LAST_CTX); a2, n2 = K.sanitize(after, LAST_CTX)
            res2, lack2 = run_check(t, facts, today, meta, title, b2, a2, p1, p3, posts, existing_slugs)
            f2 = [f"{x[0]} {x[2]}" for x in res2 if x[1] == "FAIL"]
            C.log(f"[자동 정리] 사실표에 없는 숫자가 든 문장 {n1+n2}개 삭제 → 남은 실패 {len(f2)}개")
            if not f2:
                before, after, res, lack = b2, a2, res2, lack2
                fails = []; warns = [f"{x[0]} {x[2]}" for x in res2 if x[1] == "WARN"] + [f"자동 정리: 숫자 든 문장 {n1+n2}개 삭제"]
        if not fails: break
        if attempt < 2:
            revisions += 1; feedback = "; ".join(fails)[:900] + " / 고칠 때도 분량(본문 3,800자 이상)과 표 2개 이상, 제목은 그대로 유지하고, 사실표에 없는 숫자는 지우거나 '공단·요양원에 확인'으로 바꾸세요."
    if fails or len(warns) >= 4:
        reason = fails or ["경고 4개 이상(품질 흔들림): " + "; ".join(warns[:4])]
        C.log("보류:", title, reason, warns)
        held.append({"title": title, "fails": reason}); M.hold_mail(title, reason, warns, t)
        t["status"] = "보류"; return None
    # 썸네일
    art, combo, tries, note = T.make_art(t, title, recent_combos, G.call)
    png = T.compose(art, title, t["detail"], today)
    thumb = "정상" if art is not None and tries == 0 else (f"재생성 {tries}회" if art is not None else "대체")
    if combo: recent_combos.append(combo)
    content = G.wrap_blocks(before, after)
    when = whens[i]
    status = "publish" if i == 0 else "future"
    date_iso = None if i == 0 else when.strftime("%Y-%m-%dT%H:%M:%S")
    row = {"title": title, "state": "발행" if i == 0 else "예약", "when": "즉시" if i == 0 else when.strftime("%m/%d %H:%M"),
           "chars": K.count_chars(before + after), "warns": warns, "lack": lack, "thumb": thumb, "revisions": revisions, "slug": meta["slug"], "link": ""}
    if C.DRY_RUN or os.environ.get("URI_MOCK"):
        os.makedirs(os.path.join(C.BASE, "out"), exist_ok=True)
        open(os.path.join(C.BASE, "out", f"{meta['slug']}.html"), "w", encoding="utf-8").write(content)
        open(os.path.join(C.BASE, "out", f"{meta['slug']}.webp"), "wb").write(png)
        t["status"] = "시험"; return row
    import wp_client as W
    mid = W.upload_media(png, f"{meta['slug']}.webp", title, title)
    post = W.create_post(title, meta["slug"], content, C.CATEGORIES[t["category"]], status, date_iso, mid, meta["meta_description"])
    rm = W.rankmath(post["id"], t["main"], meta["meta_description"], title)
    if not rm: row["warns"].append("D4 Rank Math 저장 실패")
    elif status == "publish":
        ok = W.verify_description(post["link"], meta["meta_description"])
        if ok is False: row["warns"].append("D4 meta description이 화면에 안 나옴")
    row.update({"id": post["id"], "link": post["link"], "slug": post["slug"]})
    t["status"] = "발행" if i == 0 else "예약"
    hist["posts"].append({"title": title, "slug": post["slug"], "pattern": t.get("_pattern"), "combo": combo, "date": C.now_kst().isoformat(), "topic": t["no"], "id": post["id"]})
    return row

def replenish(topics, facts, existing_titles):
    """남은 주제 12개 이하 → 후보 20개 생성. 숫자가 필요한데 사실표에 없으면 보류."""
    from generator import call, extract_json
    used = [f"{t['main']}|{t['detail']}" for t in topics]
    ids = {f["id"] for f in facts}
    usr = f"""요양원 정보 사이트의 새 글 주제 후보 20개를 만드세요.
범위: 요양원·장기요양등급·본인부담금·지원금·치매·주야간보호·방문요양·복지용구·입소 준비 (시니어 연금·건강·노후 준비 등 일반 시니어 주제는 제외).
이미 쓴 (메인|세부) 쌍과 겹치면 안 됨: {json.dumps(used, ensure_ascii=False)}
이미 발행된 제목: {' / '.join(existing_titles[-40:])}
각 후보에 필요한 사실표 항목 id를 fact_ids에 적고, 숫자가 필요 없으면 needs_numbers=false.
사실표 id 목록: {', '.join(sorted(ids))}
JSON 배열만: [{{"main":"","detail":"","related":["",""],"type":"정보|절차|비교|체크리스트|계산","question":"","category":"nursing-home-cost|care-grade|subsidy|nursing-home-guide|compare","needs_numbers":true,"fact_ids":["id"]}}]"""
    raw = call("당신은 키워드 기획자입니다.", usr, max_tokens=4000, temperature=0.9)
    m = re.search(r"\[.*\]", raw, re.S)
    try: cands = json.loads(m.group(0))
    except Exception: return None
    n0 = max(t["no"] for t in topics); added = 0; held = []
    for c in cands:
        key = f"{c.get('main')}|{c.get('detail')}"
        if key in used or not c.get("main") or c.get("category") not in C.CATEGORIES: continue
        need = c.get("needs_numbers", True); fid = c.get("fact_ids", [])
        ok = (not need) or (fid and all(f in ids for f in fid))
        n0 += 1
        topics.append({"no": n0, "main": c["main"], "detail": c["detail"], "related": c.get("related", [])[:3], "type": c.get("type", "정보"),
                       "question": c["question"], "category": c["category"], "fact_status": "자동 생성" + ("" if need else " (숫자 없음)"),
                       "status": "대기" if ok else "보류-사실표필요"})
        used.append(key); added += 1
        if not ok: held.append(c["main"] + " " + c["detail"])
    if not (C.DRY_RUN or os.environ.get("URI_MOCK")): C.save_json("topics.json", topics)
    M.send(f"[우리동네 요양원] 주제 {added}개 자동 보충", f"<p>남은 주제가 12개 이하라 새 후보 {added}개를 만들었어요.</p>" +
           (f"<p>사실표가 필요해 보류: {', '.join(held)}</p>" if held else ""))
    return [t for t in topics if t["status"] == "대기"]

def check_existing(posts, facts):
    """이미 발행된 글에 검수기를 돌려 본다(검수기 시험용). 글 내용은 REST raw."""
    import wp_client as W
    out = []
    for p in posts:
        if p["status"] != "publish": continue
        d = W.get_post(p["id"])
        if not d: continue
        raw = d["content"]["raw"]
        raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S).replace("[toc]", "")
        allowed = K.build_allowed(facts)
        internal = {x["link"].rstrip("/") for x in posts} | {u.rstrip("/") for u in category_urls()}
        for u in C.CALC.values(): internal.add(u.rstrip("/"))
        for u in list(internal): internal.add(u + "/")
        ctx = {"topic": {"main": re.split(r"[ ,]", p["title"])[0], "detail": "", "related": [], "question": "", "type": ""}, "facts": facts, "allowed": allowed,
               "today_label": C.today_label(), "internal_urls": internal, "calc_url": None, "calcs": [], "lacking": [], "year": C.now_kst().year}
        res = K.check_html(raw, ctx)
        out.append((p["id"], p["title"], [f"{x[1]} {x[0]} {x[2]}" for x in res]))
    for pid, tt, r in out:
        print(pid, tt); [print("   ", x) for x in r]

if __name__ == "__main__":
    main()
