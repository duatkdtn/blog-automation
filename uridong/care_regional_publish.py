# -*- coding: utf-8 -*-
"""지역별 요양원 글 발행 — AI를 쓰지 않는다(비용 0원). 실행할 때마다 아직 안 쓴 지역을 골라 그날 만들어 올린다.
사용: python care_regional_publish.py --mode dry|draft|publish [--n 1] [--region "서울특별시|종로구;경상남도|거제시"] [--replace]
  dry     워드프레스에 쓰지 않고 out/ 폴더에 html만 저장
  draft   워드프레스에 임시글(공개 안 됨)로 저장
  publish 즉시 공개
시설 데이터: data/facilities.csv, data/phones.csv (공공데이터, 분기 1회 갱신). 발행 기록: data/regional_history.json"""
import os, re, sys, json, argparse, collections
import common as C
import regional as R
import thumbnail as T
import mailer as M
import generator as G

MIN_FAC = 5          # 시설이 이보다 적은 지역은 글이 얇아서 만들지 않는다
MIN_CHARS = 2800     # 글자 수(공백 포함) 하한. 이보다 짧으면 올리지 않는다

def history():
    return C.load_json("regional_history.json", {"done": []})

def candidates(rows, done_keys):
    cnt = collections.Counter((r["sido"], r["sigungu"]) for r in rows if r["type"] == "A03")
    code5 = {}
    for r in rows:
        if r["type"] == "A03": code5.setdefault((r["sido"], r["sigungu"]), r["code"][:5])
    keys = [k for k, v in cnt.items() if v >= MIN_FAC and f"{k[0]}|{k[1]}" not in done_keys]
    keys.sort(key=lambda k: (-cnt[k], code5[k]))
    return [(k, code5[k]) for k in keys]

def pick_links(posts, k=4):
    pub = [p for p in posts if p["status"] == "publish" and "nursing-homes-" not in p["slug"]]
    out = [(p["title"], p["link"]) for p in pub[:k]]
    for s, nm in (("nursing-home-cost", "요양원 비용 글 모아보기"), ("care-grade", "장기요양등급 글 모아보기"), ("subsidy", "지원금 글 모아보기")):
        if len(out) >= 3: break
        out.append((nm, f"{C.WP_URL}/category/{s}/"))
    return out[:4]

def check(title, before, after):
    text = before + after
    bad = []
    n = len(re.sub(r"<[^>]+>", "", text))
    if n < MIN_CHARS: bad.append(f"글자 수 {n}자 (하한 {MIN_CHARS})")
    if text.count("<table") < 2: bad.append("표 2개 미만")
    for w in ("nan", "None", "{", "}", "(은)는", "은(는)", "이(가)"):
        if w in re.sub(r"<[^>]+>", "", text): bad.append(f"이상한 글자 '{w}'")
    if len(title) > 40: bad.append("제목이 너무 김")
    return n, bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="dry"); ap.add_argument("--n", type=int, default=1); ap.add_argument("--region", default=""); ap.add_argument("--replace", action="store_true", help="같은 슬러그의 임시글이 있으면 새 내용으로 바꾼다(공개 글은 건드리지 않음)")
    a = ap.parse_args()
    if a.mode == "dry": C.DRY_RUN = True
    rows = R.load(os.path.join(C.DATA, "facilities.csv"), os.path.join(C.DATA, "phones.csv"))
    hist = history(); done = {d["key"] for d in hist["done"]}
    today = C.today_label()
    posts = []
    if a.mode != "dry":
        import wp_client as W
        posts = W.list_posts()
        slugs = {p["slug"] for p in posts}
    else:
        slugs = set()
    if a.region:
        queue = []
        for part in a.region.split(";"):
            s, g = part.strip().split("|"); code = next(r["code"][:5] for r in rows if r["type"] == "A03" and r["sido"] == s and r["sigungu"] == g)
            queue.append(((s, g), code))
        a.n = max(a.n, len(queue))
    else:
        queue = candidates(rows, done)
    results = []; made = 0
    for (s, g), code in queue:
        if made >= a.n: break
        slug = f"nursing-homes-{code}"
        old = next((p for p in posts if p["slug"] == slug), None)
        if old and not (a.replace and old["status"] == "draft"):
            C.log("이미 있는 슬러그, 건너뜀:", slug, old["status"]); continue
        links = pick_links(posts) if posts else [("요양원 비용 글 모아보기", f"{C.WP_URL}/category/nursing-home-cost/"), ("장기요양등급 글 모아보기", f"{C.WP_URL}/category/care-grade/"), ("지원금 글 모아보기", f"{C.WP_URL}/category/subsidy/")]
        pkg = R.build(s, g, rows, today, code, links)
        n_chars, bad = check(pkg["title"], pkg["before"], pkg["after"])
        C.log(f"[{s} {g}] {pkg['title']} / {n_chars}자 / 문제 {bad}")
        if bad:
            results.append({"region": f"{s} {g}", "title": pkg["title"], "state": "건너뜀", "bad": bad, "link": ""}); continue
        content = G.wrap_blocks(pkg["before"], pkg["after"])
        recent = [d.get("combo") for d in hist["done"] if d.get("combo")]
        here_n = pkg["n"]
        a_high = "A등급 비율이 전국 평균보다 높" in pkg["before"]
        sc = T.region_scene(f"{s}|{g}", here_n, a_high, recent)
        art, tries, note = T.art_from_scene(sc) if a.mode != "dry" or os.environ.get("URI_DRY_ART") == "1" else (None, 0, "dry")
        sub = {0: "시설 수 · 정원 · 평가등급", 1: "시설별 전화번호까지", 2: "정원 큰 곳부터 한눈에"}[int(__import__("hashlib").md5(g.encode()).hexdigest(), 16) % 3]
        png = T.compose(art, pkg["title"], sub, today, fallback=art is None)
        thumb = "3D 그림" if art is not None else f"기본 이미지({note})"
        C.log("썸네일:", thumb, "| 장면:", sc["people"], "/", sc["background"], "/", sc["props"])
        if a.mode == "dry":
            os.makedirs(os.path.join(C.BASE, "out"), exist_ok=True)
            open(os.path.join(C.BASE, "out", f"{pkg['slug']}.html"), "w", encoding="utf-8").write(content)
            open(os.path.join(C.BASE, "out", f"{pkg['slug']}.webp"), "wb").write(png)
            results.append({"region": f"{s} {g}", "title": pkg["title"], "state": "시험", "bad": [], "link": ""}); made += 1; continue
        mid = W.upload_media(png, f"{pkg['slug']}.webp", pkg["title"], pkg["title"])
        status = "publish" if a.mode == "publish" else "draft"
        if old:
            post = W.update_post(old["id"], {"title": pkg["title"], "content": content, "featured_media": mid, "excerpt": pkg["meta_description"], "status": status})
            hist["done"] = [d for d in hist["done"] if d["key"] != f"{s}|{g}"]
        else:
            post = W.create_post(pkg["title"], pkg["slug"], content, C.CATEGORIES["nursing-home-guide"], status, None, mid, pkg["meta_description"])
        rm = W.rankmath(post["id"], pkg["focus"], pkg["meta_description"], pkg["title"])
        hist["done"].append({"key": f"{s}|{g}", "id": post["id"], "slug": post["slug"], "status": post["status"] if old else status, "date": C.now_kst().isoformat(), "combo": [sc["people"], sc["background"]], "thumb": thumb})
        results.append({"region": f"{s} {g}", "title": pkg["title"], "state": ("발행" if status == "publish" else "임시글") + (" (교체)" if old else ""), "bad": ([] if rm else ["Rank Math 저장 실패"]) + ([f"썸네일 {thumb}"] if art is None else []), "link": post["link"]}); made += 1
        slugs.add(pkg["slug"])
    if a.mode != "dry": C.save_json("regional_history.json", hist)
    body = "".join(f'<p><b>{r["state"]}</b> {M.e(r["title"])} {("— " + M.e("; ".join(r["bad"]))) if r["bad"] else ""} {("<a href=" + chr(34) + r["link"] + chr(34) + ">링크</a>") if r["link"] else ""}</p>' for r in results) or "<p>만들 지역이 없어요(모두 완료 또는 조건 미달).</p>"
    M.send(f"[우리동네 요양원] 지역 글 {a.mode} — {sum(1 for r in results if r['state'] in ('발행','임시글','시험'))}개", M.wrap("지역 글 결과", C.now_kst().strftime("%Y-%m-%d"), body))
    for r in results: C.log(r)

if __name__ == "__main__":
    main()
