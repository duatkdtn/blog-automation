# -*- coding: utf-8 -*-
"""썸네일: 제미나이 3D 그림(재시도 2회) + Pillow 글자. 실패하면 기본 배경."""
import io, os, re, json, time, base64, glob, random
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import common as C

W, H = 1200, 675
STYLE_FIX = ("귀여운 3D 일러스트, 파스텔 색감, Pixar풍, 한국인 캐릭터, 사진처럼 보이지 않게. "
             "그림 안에는 글자·숫자·로고를 절대 넣지 않는다. 사진처럼 보이는 어르신 얼굴 금지, 특정 작품·캐릭터·타사 이미지 모방 금지. "
             "16:9 가로 구도. 인물과 소품은 화면 오른쪽에 모으고, 왼쪽 절반은 단순한 배경으로 비워 둔다(글자가 올라갈 자리).")
FONT_CANDS = ["/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"]

def font(size):
    for p in FONT_CANDS + glob.glob("/usr/share/fonts/**/*Nanum*Bold*.ttf", recursive=True):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def scene_prompt(topic, title, recent_combos, call_fn):
    """Haiku가 글 내용에서 장면 한 줄을 정한다. 최근 5개와 같은 (인물, 배경) 조합 금지."""
    from generator import extract_json
    usr = f"""요양원 정보 글의 썸네일 장면을 정해 주세요.
글 제목: {title} / 질문: {topic['question']}
최근 5개 글의 (인물, 배경): {json.dumps(recent_combos[-5:], ensure_ascii=False)}  ← 같은 조합 금지
인물은 매번 바꿉니다(딸·어머니, 아들·아버지, 부부, 요양보호사, 상담사 등). 배경도 바꿉니다(집 거실, 요양원 복도, 병원 상담실, 공단 창구, 정원 등).
글 내용과 어울리는 소품(서류, 계산기, 달력, 집 모형 등)을 넣습니다. 글자·숫자가 보이는 소품은 피합니다.
JSON만: {{"people":"","background":"","props":"","scene":"한 문장 장면 설명"}}"""
    try:
        return extract_json(call_fn("당신은 썸네일 장면 기획자입니다.", usr, max_tokens=400, temperature=0.9))
    except Exception:
        return {"people": "보호자와 어르신", "background": "밝은 거실", "props": "서류와 안경", "scene": "보호자와 어르신이 서류를 함께 보는 장면"}

def gemini_image(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
    r = requests.post(url, headers={"x-goog-api-key": C.GEMINI_API_KEY, "Content-Type": "application/json"}, json=body, timeout=120)
    if r.status_code == 429 or r.status_code >= 500:
        raise TransientError(f"gemini {r.status_code}")
    if r.status_code != 200:
        raise NoImage(f"gemini {r.status_code}")
    for cand in r.json().get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            d = part.get("inlineData") or part.get("inline_data")
            if d and d.get("data"):
                return Image.open(io.BytesIO(base64.b64decode(d["data"]))).convert("RGB")
    raise NoImage("그림 없음(안전 필터 또는 텍스트 응답)")

class TransientError(Exception): pass
class NoImage(Exception): pass

def make_art(topic, title, recent_combos, call_fn):
    """최대 3번 호출(처음 + 재시도 2). 반환 (Image|None, combo, tries, note)"""
    if not C.GEMINI_API_KEY:
        return None, None, 0, "GEMINI 키 없음"
    sc = scene_prompt(topic, title, recent_combos, call_fn)
    note = ""
    for i in range(3):
        try:
            prompt = f"{sc['scene']}. 인물: {sc['people']}. 배경: {sc['background']}. 소품: {sc['props']}. {STYLE_FIX}"
            img = gemini_image(prompt)
            return img, [sc["people"], sc["background"]], i, ""
        except TransientError as e:
            note = str(e); time.sleep(8 * (i + 1))
        except NoImage as e:
            note = str(e)
            sc = scene_prompt(topic, title, recent_combos + [[sc["people"], sc["background"]]], call_fn)  # 장면 바꿔서 재시도
        except Exception as e:
            note = type(e).__name__; time.sleep(5)
    return None, None, 3, note

def _cover(img):
    r = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))

def _dominant(img):
    sm = img.resize((40, 22)).quantize(8).convert("RGB")
    cols = sm.getcolors(1000) or []
    cols = [c for c in cols if 40 < sum(c[1]) < 700] or cols
    n, rgb = max(cols)
    return rgb

def fallback_bg():
    base = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(base)
    for x in range(W):
        t = x / W
        d.line([(x, 0), (x, H)], fill=(int(255 - 40 * t), int(236 - 30 * t), int(214 - 10 * t)))
    return base

def _wrap(draw, text, fnt, maxw):
    """단어(공백) 단위로 줄바꿈, 한 단어가 너무 길 때만 글자 단위로 자른다."""
    lines, cur = [], ""
    for w in text.split(" "):
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= maxw:
            cur = trial
        else:
            if cur: lines.append(cur)
            if draw.textlength(w, font=fnt) > maxw:
                part = ""
                for ch in w:
                    if draw.textlength(part + ch, font=fnt) > maxw and part:
                        lines.append(part); part = ch
                    else: part += ch
                cur = part
            else:
                cur = w
    if cur: lines.append(cur)
    return lines

def compose(art, title, subtitle, today, fallback=False):
    base = _cover(art) if art is not None else fallback_bg()
    rgb = _dominant(base) if art is not None else (214, 128, 60)
    dark = tuple(int(c * 0.35) for c in rgb)
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(W):
        a = int(235 * max(0.0, 1 - max(0, x - 80) / 700.0)) if x < 780 else 0
        gd.line([(x, 0), (x, H)], fill=dark + (a,))
    img = Image.alpha_composite(base.convert("RGBA"), grad)
    d = ImageDraw.Draw(img)
    # 로고 칩
    chip = font(30); ct = "우리동네 요양원"
    cw = d.textlength(ct, font=chip) + 40
    d.rounded_rectangle((60, 55, 60 + cw, 110), radius=26, fill=(243, 156, 18))
    d.text((80, 62), ct, font=chip, fill=(255, 255, 255))
    # 제목 (최대 2줄, 자동 글자 크기)
    size = 74
    while size > 44:
        f = font(size); lines = _wrap(d, title, f, 640)
        if len(lines) <= 2: break
        size -= 4
    f = font(size); lines = _wrap(d, title, f, 640)[:2]
    y = 150
    for ln in lines:
        d.text((62, y + 3), ln, font=f, fill=(0, 0, 0)); d.text((60, y), ln, font=f, fill=(255, 255, 255)); y += int(size * 1.25)
    # 부제 띠
    sf = font(30); sw = d.textlength(subtitle, font=sf) + 36
    d.rounded_rectangle((60, y + 18, 60 + sw, y + 18 + 54), radius=10, fill=(253, 227, 190))
    d.text((78, y + 25), subtitle, font=sf, fill=(120, 70, 10))
    # 하단
    d.text((60, H - 62), f"{today} 기준 · 출처 국민건강보험공단 등", font=font(26), fill=(255, 255, 255, 230))
    out = io.BytesIO(); img.convert("RGB").save(out, "WEBP", quality=88)
    return out.getvalue()


# ── 지역 글용: AI에게 장면을 묻지 않고 코드가 조합(인물×배경×소품)으로 정한다
PEOPLE = ["딸과 어머니", "아들과 아버지", "중년 부부", "요양보호사와 어르신", "상담 직원과 보호자", "손주와 할머니",
          "남매와 어머니", "며느리와 시어머니", "사회복지사와 어르신 부부", "아들 내외와 아버지"]
BGS = ["밝은 집 거실", "요양원 복도", "햇살 드는 정원", "아늑한 상담실", "공단 창구", "동네 산책길", "작은 카페", "병원 대기실", "베란다가 있는 집", "도서관 열람실"]
PROPS = ["서류와 돋보기", "작은 지도와 핀", "전화기", "집 모형", "달력과 연필", "찻잔과 메모지", "체크리스트 클립보드", "꽃 화분"]

def region_scene(key, n, a_share_high, recent):
    import hashlib
    hv = int(hashlib.md5(key.encode()).hexdigest(), 16)
    for t in range(60):
        p, b = PEOPLE[(hv + t) % 10], BGS[(hv // 10 + t * 3) % 10]
        if [p, b] not in recent[-8:]: break
    prop = PROPS[(hv // 100) % 8]
    extra = "여러 채의 작은 요양원 건물 모형" if n >= 30 else ("작은 요양원 건물 모형 한 채" if n <= 8 else "")
    if a_share_high: extra = (extra + ", " if extra else "") + "별 모양 스티커"
    scene = f"{p}가 {b}에서 요양원을 알아보는 따뜻한 장면"
    return {"people": p, "background": b, "props": prop + (", " + extra if extra else ""), "scene": scene}

def art_from_scene(sc):
    """최대 3번 호출. 반환 (Image|None, tries, note)"""
    if not C.GEMINI_API_KEY: return None, 0, "GEMINI 키 없음"
    note = ""
    for i in range(3):
        try:
            prompt = f"{sc['scene']}. 인물: {sc['people']}. 배경: {sc['background']}. 소품: {sc['props']}. {STYLE_FIX}"
            return gemini_image(prompt), i, ""
        except TransientError as e:
            note = str(e); time.sleep(8 * (i + 1))
        except NoImage as e:
            note = str(e); sc = dict(sc); sc["props"] = "서류"
        except Exception as e:
            note = type(e).__name__; time.sleep(5)
    return None, 3, note
