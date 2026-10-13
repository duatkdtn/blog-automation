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

def plan_mail(plans, remaining, date_label):
    blocks = ""
    for i, p in enumerate(plans, 1):
        blocks += (f'<div style="border:1px solid #ddd;border-radius:8px;padding:14px 18px;margin:0 0 14px">'
                   f'<b>{i}. {e(p["title"])}</b><br>발행: {e(p["when"])}<br>'
                   f'키워드: {e(p["main"])} / {e(p["detail"])} · 유형 {e(p["type"])}<br>'
                   f'답하는 질문: {e(p["question"])}<br>핵심: {e(p["gist"])}</div>')
    warn = f'<p style="color:#c0392b"><b>⚠️ 남은 주제 {remaining}개 — 곧 보충됩니다.</b></p>' if remaining <= 12 else f"<p>남은 주제 {remaining}개</p>"
    return send(f"[우리동네 요양원] 오늘 발행 예정 {len(plans)}개 ({date_label})",
                f"<h3>오늘 발행 계획</h3>{blocks}{warn}<p style='color:#888'>막고 싶으면 워드프레스에서 예약글을 지우거나 비공개로 바꾸세요.</p>")

def result_mail(rows, held, lacks, cost, remaining, extra_notes):
    ok = sum(1 for r in rows if r["state"] in ("발행", "예약")); hold = len(held)
    warns = sum(1 for r in rows if r["warns"])
    th = "<tr>" + "".join(f"<th style='border:1px solid #ccc;padding:4px 8px;background:#eee'>{x}</th>" for x in
        ["번호", "제목", "상태", "시각", "글자 수", "경고", "자료부족", "썸네일", "링크"]) + "</tr>"
    trs = ""
    for i, r in enumerate(rows, 1):
        trs += "<tr>" + "".join(f"<td style='border:1px solid #ccc;padding:4px 8px'>{x}</td>" for x in [
            i, e(r["title"]), r["state"], e(r["when"]), r["chars"], len(r["warns"]), len(r["lack"]), e(r["thumb"]),
            f'<a href="{e(r["link"])}">열기</a>' if r.get("link") else "-"]) + "</tr>"
    detail = ""
    for r in rows:
        if r["warns"] or r["lack"] or r["revisions"]:
            detail += f"<p><b>{e(r['title'])}</b><br>" + "".join(f"· 경고 {e(w)}<br>" for w in r["warns"]) + \
                      "".join(f"· 자료부족 {e(l)}<br>" for l in r["lack"]) + (f"· 자동 고쳐쓰기 {r['revisions']}회<br>" if r["revisions"] else "") + "</p>"
    hold_html = "".join(f"<p>⚠️ <b>{e(h['title'])}</b>: " + "; ".join(e(x) for x in h["fails"][:6]) + "</p>" for h in held)
    subj = f"[우리동네 요양원] 결과 — 발행 {ok} / 보류 {hold} / 경고 있음 {warns}"
    return send(subj, f"<table style='border-collapse:collapse;font-size:14px'>{th}{trs}</table>{detail}{hold_html}"
                      f"<p>모델 비용 추정: {e(cost)}</p><p>남은 주제 {remaining}개</p>{extra_notes}")

def hold_mail(title, fails, warns, topic):
    body = (f"<h3>보류: {e(title)}</h3><p>주제 {e(topic['main'])} / {e(topic['detail'])}</p><p><b>실패 항목</b><br>" +
            "<br>".join(e(x) for x in fails) + "</p><p>경고<br>" + "<br>".join(e(x) for x in warns) + "</p>"
            "<p>할 일: 다시 쓰기 요청 / 주제 제외 / 사실표에 숫자 추가 중 선택해서 알려 주세요.</p>")
    return send(f"[우리동네 요양원] ⚠️ 보류 — {title}", body)
