# -*- coding: utf-8 -*-
import smtplib, ssl, html as H
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import common as C

def send(subject, html_body):
    import os
    if os.environ.get("URI_MOCK") == "1" or not (C.GMAIL_ADDRESS and C.GMAIL_APP_PASSWORD):
        C.log("[메일 생략]", subject); return False
    if C.DRY_RUN: subject = "[시험] " + subject
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject; msg["From"] = C.GMAIL_ADDRESS; msg["To"] = C.EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=60) as s:
            s.login(C.GMAIL_ADDRESS, C.GMAIL_APP_PASSWORD)
            s.sendmail(C.GMAIL_ADDRESS, [C.EMAIL_RECIPIENT], msg.as_string())
        return True
    except Exception as e:
        C.log("메일 실패", type(e).__name__); return False

def e(x): return H.escape(str(x))

def wrap(title, sub, body):
    return (f'<div style="background:#f4f6f8;padding:20px 10px;font-family:Malgun Gothic,Apple SD Gothic Neo,sans-serif">'
            f'<div style="max-width:560px;margin:0 auto">'
            f'<div style="background:linear-gradient(135deg,#2980b9,#1b4f72);color:#fff;border-radius:10px;padding:22px;text-align:center;margin-bottom:14px">'
            f'<div style="font-size:20px;font-weight:bold">{title}</div><div style="font-size:13px;opacity:.85;margin-top:6px">{sub}</div></div>'
            f'{body}</div></div>')

def card(color, label, title, meta, extra="", link=None):
    ln = f'<div style="margin-top:6px"><a href="{e(link)}" style="color:#2980b9;font-size:13px">글 보기 →</a></div>' if link else ""
    return (f'<div style="background:#fff;border:1px solid #e1e4e8;border-left:4px solid {color};border-radius:8px;padding:12px 16px;margin:0 0 10px">'
            f'<div style="font-size:14px"><b style="color:{color}">{label}</b>&nbsp; {e(title)}</div>'
            f'<div style="font-size:12px;color:#888;margin-top:4px">{meta}</div>{extra}{ln}</div>')

def note(items, color="#c0392b"):
    return "".join(f'<div style="font-size:12px;color:{color};margin-top:4px">· {e(x)}</div>' for x in items)

def plan_mail(plans, remaining, date_label):
    cards = ""
    for i, p in enumerate(plans, 1):
        meta = (f'발행: {e(p["when"])} | 키워드: {e(p["main"])} / {e(p["detail"])} | 유형 {e(p["type"])}')
        extra = (f'<div style="font-size:13px;margin-top:6px">❓ {e(p["question"])}</div>'
                 f'<div style="font-size:13px;color:#555;margin-top:2px">💡 {e(p["gist"])}</div>')
        cards += card("#2980b9", f"예정 {i}", p["title"], meta, extra)
    if remaining <= 12:
        foot = f'<div style="color:#c0392b;font-size:13px"><b>⚠️ 남은 주제 {remaining}개 — 곧 보충됩니다.</b></div>'
    else:
        foot = f'<div style="color:#666;font-size:13px">남은 주제 {remaining}개</div>'
    foot += '<div style="color:#999;font-size:12px;margin-top:6px">막고 싶으면 워드프레스에서 예약글을 지우거나 비공개로 바꾸세요.</div>'
    return send(f"[우리동네 요양원] 오늘 발행 예정 {len(plans)}개 ({date_label})",
                wrap("📅 오늘 발행 계획", f"{e(date_label)} · {len(plans)}개 예정", cards + foot))

def result_mail(rows, held, lacks, cost, remaining, extra_notes):
    ok = sum(1 for r in rows if r["state"] in ("발행", "예약")); hold = len(held)
    warns = sum(1 for r in rows if r["warns"])
    total = len(rows) + hold
    cards = ""
    for r in rows:
        done = r["state"] in ("발행", "예약")
        color = ("#27ae60" if not r["warns"] else "#e67e22") if done else "#e74c3c"
        label = ("✅ 발행 완료" if r["state"] == "발행" else "⏰ 예약 완료") if done else "❌ " + e(r["state"])
        if done and r["warns"]: label = label + " ⚠️"
        meta = f'{e(r["when"])} | {r["chars"]:,}자 | 경고 {len(r["warns"])} | 자료부족 {len(r["lack"])} | 썸네일 {e(r["thumb"])}'
        extra = note(r["warns"], "#e67e22") + note(["자료부족: " + x for x in r["lack"]], "#888") + \
                (note([f"자동 고쳐쓰기 {r['revisions']}회"], "#888") if r["revisions"] else "")
        cards += card(color, label, r["title"], meta, extra, r.get("link"))
    for h in held:
        cards += card("#e74c3c", "⛔ 보류", h["title"], "공개하지 않고 멈춤", note(h["fails"][:8]))
    foot = (f'<div style="font-size:13px;color:#666;margin-top:8px">모델 비용 추정: {e(cost)} · 남은 주제 {remaining}개</div>{extra_notes}')
    subj = f"[우리동네 요양원] 결과 — 발행 {ok} / 보류 {hold} / 경고 있음 {warns}"
    return send(subj, wrap("🚀 우리동네 요양원 자동 발행 결과", C.now_kst().strftime("%Y-%m-%d") + f" · 발행 {ok}/{total}개", cards + foot))

def hold_mail(title, fails, warns, topic):
    body = card("#e74c3c", "⛔ 보류", title, f'주제 {e(topic["main"])} / {e(topic["detail"])}',
                '<div style="font-size:13px;margin-top:8px"><b>실패 항목</b></div>' + note(fails) +
                ('<div style="font-size:13px;margin-top:8px"><b>경고</b></div>' + note(warns, "#e67e22") if warns else "")) + \
           '<div style="font-size:13px;color:#555">할 일: 다시 쓰기 요청 / 주제 제외 / 사실표에 숫자 추가 중 선택해서 알려 주세요.</div>'
    return send(f"[우리동네 요양원] ⚠️ 보류 — {title}", wrap("⚠️ 글 보류 알림", e(title), body))
