# -*- coding: utf-8 -*-
"""워드프레스 REST 클라이언트 (응용 프로그램 비밀번호). 값은 로그에 찍지 않는다."""
import requests, time
from requests.auth import HTTPBasicAuth
import common as C

def _auth():
    return HTTPBasicAuth(C.WP_USER, C.WP_APP_PASSWORD)

def _req(method, path, **kw):
    url = C.WP_URL + "/wp-json" + path
    for i in range(3):
        try:
            r = requests.request(method, url, auth=_auth(), timeout=60, **kw)
            if r.status_code in (429, 502, 503, 504):
                time.sleep(3 * (i + 1)); continue
            return r
        except requests.RequestException as e:
            if i == 2: raise
            time.sleep(3)
    return r

def list_posts():
    """공개·예약·임시 글 목록 (제목·주소·슬러그·카테고리)."""
    out, page = [], 1
    while True:
        r = _req("GET", "/wp/v2/posts", params={"per_page": 100, "page": page,
                 "status": "publish,future,draft,pending", "context": "edit",
                 "_fields": "id,slug,link,status,date,title,categories"})
        if r.status_code != 200:
            break
        d = r.json()
        for p in d:
            out.append({"id": p["id"], "slug": p["slug"], "link": p["link"], "status": p["status"],
                        "date": p["date"], "title": p["title"].get("raw", ""), "categories": p["categories"]})
        if len(d) < 100: break
        page += 1
    return out

def upload_media(data: bytes, filename: str, alt: str, title: str):
    r = _req("POST", "/wp/v2/media", data=data, headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "image/webp"})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"media upload {r.status_code}")
    mid = r.json()["id"]
    _req("POST", f"/wp/v2/media/{mid}", json={"alt_text": alt, "title": title})
    return mid

def create_post(title, slug, content, category_id, status, date_iso=None, featured=None, excerpt=""):
    data = {"title": title, "slug": slug, "content": content, "status": status,
            "categories": [category_id], "excerpt": excerpt}
    if date_iso: data["date"] = date_iso            # 예약(future)은 사이트 시간대 기준 로컬 시각
    if featured: data["featured_media"] = featured
    r = _req("POST", "/wp/v2/posts", json=data)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"post create {r.status_code}: {r.text[:200]}")
    p = r.json()
    return {"id": p["id"], "link": p["link"], "status": p["status"], "slug": p["slug"]}

def rankmath(post_id, focus, description, title):
    meta = {"rank_math_focus_keyword": focus, "rank_math_description": description, "rank_math_title": title}
    r = _req("POST", "/rankmath/v1/updateMeta", json={"objectID": post_id, "objectType": "post", "meta": meta})
    return r.status_code == 200

def verify_description(link, description):
    """공개 글이면 meta description이 실제로 나오는지 확인. 예약글은 미리보기라 확인 못 하면 None."""
    try:
        r = requests.get(link, timeout=30, headers={"Cache-Control": "no-cache"})
        if r.status_code != 200: return None
        return description[:30] in r.text
    except requests.RequestException:
        return None

def get_post(post_id):
    r = _req("GET", f"/wp/v2/posts/{post_id}", params={"context": "edit"})
    return r.json() if r.status_code == 200 else None

def site_timezone_offset_hours():
    return 9  # 사이트 시간대 Asia/Seoul (예약 날짜는 로컬 시각 문자열로 보낸다)
