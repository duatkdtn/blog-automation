# -*- coding: utf-8 -*-
"""시험용 가짜 AI (URI_MOCK=1). 배관(파싱·조립·검수·썸네일 합성) 확인용이며 글 품질과는 무관."""
import json, re

W1=["아침","저녁","서류","상담","확인","준비","가족","보호자","어르신","병원","공단","창구","전화","방문","신청","접수"]
W2=["먼저","차근차근","천천히","꼼꼼히","미리","함께","직접","나눠서"]

def install(G):
    def fake_call(system, user, max_tokens=4096, temperature=0.6):
        G.USAGE["in"] += 1000; G.USAGE["out"] += 500
        main = re.search(r"메인 키워드[^=:]*[=:]\s*([^/\n]+?)\s*(/|\n|$)", user)
        main = (main.group(1).strip() if main else "요양원 비용")
        detail = re.search(r"세부 키워드[^=:]*[=:]\s*([^/\n]+?)\s*(/|\n|$)", user)
        detail = detail.group(1).strip() if detail else "1등급 한 달"
        if "지금은 1단계" in system:
            return json.dumps({"titles": [
                {"title": f"{main} {detail}, 3가지 먼저 확인", "pattern": "체크형"},
                {"title": f"{main} {detail} 5가지 정리", "pattern": "단순형"},
                {"title": f"{main}, {detail} 이렇게 4단계", "pattern": "순서형"}],
                "slug": "mock-" + str(abs(hash(main + detail)) % 10000), "tags": ["요양원", "장기요양", "비용"],
                "meta_description": f"{main} {detail}을 쉬운 말로 정리했어요. 국민건강보험공단 기준 숫자와 확인 방법, 주의할 점까지 한 번에 살펴봐요 지금 확인해 보세요 정말로",
                "outline": ["먼저 알아둘 점", "표로 보는 기준", "예시로 계산해 보기", "주의할 점"],
                "sources": ["국민건강보험공단"], "button": "longtermcare", "calculator": "copayment", "infographic": False}, ensure_ascii=False)
        if "지금은 2단계" in system:
            para = f"{main}를 알아보다 보면 막막하셨던 적 있으시죠. 천천히 하나씩 짚어 볼게요."
            def sent(k): return f"{W2[k%8]} {W1[(k//8)%16]}에서 {W1[(k*3)%16]}와 {W1[(k*7+1)%16]}를 {W2[(k*5)%8]} 살펴보면 {W1[(k*11+2)%16]} 순서가 {k%9+1}단계로 정리돼요 (참고 {k})."
            filler = "".join(f"<p>{sent(k)} 이 부분은 요양원마다 다르니 입소할 곳에서 확인하세요 {W1[k%16]}{W2[(k+3)%8]}{k}.</p>" if k%9==0 else f"<p>{sent(k)}</p>" for k in range(1, 70))
            filler2 = "".join(f"<p>{sent(k)}</p>" for k in range(200, 270))
            tbl = ("<div style=\"overflow-x:auto\"><table style=\"width:100%;border-collapse:collapse\"><thead style=\"background:#2980b9;color:#fff\"><tr><th>구분</th><th>내용</th></tr></thead>"
                   "<tbody><tr style=\"background:#fff\"><td>1등급 시설급여</td><td>1일 93,070원</td></tr><tr style=\"background:#f8f9fa\"><td>본인부담</td><td>20%</td></tr></tbody></table></div>")
            body = (f"<h2 style=\"color:#2c3e50\">먼저 알아둘 점</h2>{filler}{tbl}<h2 style=\"color:#2c3e50\">예시로 계산해 보기</h2>"
                    f"<p>93,070 × 30 = 2,792,100원이고, 20%는 558,420원이에요 <a href=\"https://www.longtermcare.or.kr\" target=\"_blank\" rel=\"noopener\">국민건강보험공단 장기요양보험 안내</a>.</p>{tbl}"
                    f"<h2 style=\"color:#2c3e50\">주의할 점</h2>{filler2}")
            body = body.replace("번호", "").replace("<p style=\"line-height:1.85\">" + main, "<p style=\"line-height:1.85\">" + "비용", 50)
            return (f"<summary>이런 분이 알아둘 점\n한 달 비용이 얼마인지\n본인부담금 줄이는 방법\n이것만 주의하면 돼요\n지원 혜택 확인</summary>"
                    f"<intro><p>{para}</p><p>{main}를 쉬운 말로 풀어 드릴게요. {main}는 {main}대로 {main}도 함께 봐요 {main}.</p></intro><body>{body}</body>"
                    f"<meta>{{\"numbers\":[{{\"값\":\"93,070\",\"근거\":\"fee_daily_fac_1\"}}],\"calcs\":[{{\"식\":\"93070*30\",\"결과\":\"2792100\"}},{{\"식\":\"2792100*0.2\",\"결과\":\"558420\"}}],\"lacking\":[]}}</meta>")
        if "지금은 3단계" in system:
            faq = [{"q": f"비용 질문 {W1[k]}", "a": f"답변이에요 {k}. 요양원마다 다르니 입소할 곳에서 확인하세요. 국민건강보험공단 기준이에요." * 2} for k in range(1, 6)]
            miss = ("<h2 style=\"color:#2c3e50\">자주 하는 오해</h2><div style=\"background:#fdf2f8;border:1px solid #d2b4de\"><p>❌ 비용은 다 똑같다 → 비급여는 시설마다 다 달라요</p><p>❌ 등급 없으면 못 간다 → 3~5등급도 가능해요</p><p>❌ 한 번 정하면 끝 → 바꿀 수 있어요</p></div>"
                    "<div style=\"background:#eafaf1\"><p>✅ 확인은 공단에 하세요</p></div>" + "" + "".join(f"<p>풀이 {W1[k%16]} {W2[k%8]} {W1[(k*5)%16]} 설명 {k*13} 줄째 문장이에요.</p>" for k in range(60)))
            return (f"<mistakes>{miss}</mistakes><faq>{json.dumps(faq, ensure_ascii=False)}</faq><who>처음 알아보는 가족\n비용이 궁금한 분\n등급이 막 나온 분\n본인부담이 걱정인 분\n입소를 앞둔 보호자</who>"
                    f"<cta>{{\"head\":\"오늘 확인부터 시작해 보세요\",\"summary\":\"핵심만 정리했으니 하나씩 확인해 보세요.\",\"related\":\"본인부담금\"}}</cta>"
                    f"<meta>{{\"numbers\":[],\"calcs\":[],\"lacking\":[]}}</meta>")
        if "검수자" in system:
            return json.dumps({k: {"ok": True, "why": ""} for k in ["K4", "B4", "B5", "F5", "B6"]})
        if "썸네일" in system:
            return json.dumps({"people": "딸과 어머니", "background": "거실", "props": "서류", "scene": "서류를 함께 보는 장면"}, ensure_ascii=False)
        return "[]"
    G.call = fake_call
