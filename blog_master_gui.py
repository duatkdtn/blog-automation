# ================================================
# 비니 (Bini) GUI v1.0
# ================================================

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json
import os
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# ================================================
# 색상 테마
# ================================================
BG_DARK = "#13131f"
BG_CARD = "#1e1e30"
BG_SIDEBAR = "#0f0f1a"
BG_ITEM = "#252538"
ACCENT = "#8b7cf8"
ACCENT_HOVER = "#a594ff"
ACCENT_ACTIVE = "#252545"
TEXT_WHITE = "#eeeeff"
TEXT_GRAY = "#6666aa"
SUCCESS = "#4ade80"
WARNING = "#fbbf24"
DANGER = "#f87171"
TOGGLE_ON = "#8b7cf8"
TOGGLE_OFF = "#333355"


# ================================================
# 토글 버튼 위젯
# ================================================
class ToggleButton(tk.Canvas):
    def __init__(self, parent, variable, command=None, **kwargs):
        super().__init__(parent, width=52, height=26,
                         bg=BG_CARD, highlightthickness=0, **kwargs)
        self.variable = variable
        self.command = command
        self._draw()
        self.bind("<Button-1>", self._toggle)

    def _draw(self):
        self.delete("all")
        val = self.variable.get()
        color = TOGGLE_ON if val else TOGGLE_OFF
        # 배경
        self.create_rounded_rect(2, 2, 50, 24, 11, fill=color, outline="")
        # 원
        x = 30 if val else 14
        self.create_oval(x-10, 3, x+10, 23, fill="white", outline="")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
                  x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
                  x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _toggle(self, event=None):
        self.variable.set(not self.variable.get())
        self._draw()
        if self.command:
            self.command()


# ================================================
# 메인 GUI 앱
# ================================================
class BlogMasterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("비니 v1.0")
        self.root.geometry("900x650")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)
        self.root.minsize(800, 600)

        # 설정값 로드
        self.config_data = self.load_config()

        # 토글 변수
        self.toggle_blogspot = tk.BooleanVar(value=True)
        self.toggle_naver = tk.BooleanVar(value=True)
        self.toggle_insta = tk.BooleanVar(value=False)
        self.toggle_thread = tk.BooleanVar(value=False)

        # 현재 페이지
        self.current_page = None

        # UI 구성
        self.build_ui()
        self.show_page("dashboard")

        # 상태 업데이트
        self.update_status()

    # ================================================
    # 설정 파일 로드/저장
    # ================================================
    def load_config(self):
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import config as cfg
            return {
                "CLAUDE_API_KEY": getattr(cfg, "CLAUDE_API_KEY", ""),
                "GEMINI_API_KEY": getattr(cfg, "GEMINI_API_KEY", ""),
                "NAVER_CLIENT_ID": getattr(cfg, "NAVER_CLIENT_ID", ""),
                "NAVER_CLIENT_SECRET": getattr(cfg, "NAVER_CLIENT_SECRET", ""),
                "BLOG_ID": getattr(cfg, "BLOG_ID", ""),
                "CLOUDINARY_CLOUD_NAME": getattr(cfg, "CLOUDINARY_CLOUD_NAME", ""),
                "CLOUDINARY_API_KEY": getattr(cfg, "CLOUDINARY_API_KEY", ""),
                "CLOUDINARY_API_SECRET": getattr(cfg, "CLOUDINARY_API_SECRET", ""),
                "GMAIL_ADDRESS": getattr(cfg, "GMAIL_ADDRESS", ""),
                "GMAIL_APP_PASSWORD": getattr(cfg, "GMAIL_APP_PASSWORD", ""),
                "EMAIL_RECIPIENT": getattr(cfg, "EMAIL_RECIPIENT", ""),
            }
        except:
            return {}

    # ================================================
    # 전체 UI 구성
    # ================================================
    def build_ui(self):
        # 사이드바
        self.sidebar = tk.Frame(self.root, bg=BG_SIDEBAR, width=110)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # 메인 영역
        self.main_area = tk.Frame(self.root, bg=BG_DARK)
        self.main_area.pack(side="right", fill="both", expand=True)

        self.build_sidebar()

    def build_sidebar(self):
        # 로고
        logo_frame = tk.Frame(self.sidebar, bg=BG_SIDEBAR, pady=18)
        logo_frame.pack(fill="x")
        tk.Label(logo_frame, text="✦", font=("Arial", 20),
                 bg=BG_SIDEBAR, fg=ACCENT).pack()
        tk.Label(logo_frame, text="Bini", font=("Arial", 9, "bold"),
                 bg=BG_SIDEBAR, fg=TEXT_WHITE).pack()

        # 구분선
        tk.Frame(self.sidebar, bg="#222235", height=1).pack(fill="x", padx=12, pady=(0, 8))

        # 섹션 라벨 함수
        def section_label(text):
            tk.Label(self.sidebar, text=text,
                     font=("Arial", 7), bg=BG_SIDEBAR, fg=TEXT_GRAY,
                     anchor="w", padx=14).pack(fill="x", pady=(8, 2))

        # 메뉴 데이터: (page, icon, label)
        self.menu_buttons = {}
        menus = [
            ("section_main", None, "메인"),
            ("dashboard", "⊞", "대시보드"),
            ("section_tools", None, "도구"),
            ("keyword", "◎", "키워드 분석"),
            ("publish", "✎", "글 발행"),
            ("email", "📧", "이메일 발송"),
        ]

        for item in menus:
            if item[0].startswith("section_"):
                section_label(item[2])
                continue
            page, icon, label = item
            btn_frame = tk.Frame(self.sidebar, bg=BG_SIDEBAR, cursor="hand2",
                                 highlightthickness=1, highlightbackground="#3a3a5a")
            btn_frame.pack(fill="x", padx=8, pady=3)

            inner = tk.Frame(btn_frame, bg=BG_SIDEBAR, padx=6, pady=8, cursor="hand2")
            inner.pack(fill="x")

            icon_lbl = tk.Label(inner, text=icon, font=("Arial", 16),
                                bg=BG_SIDEBAR, fg=TEXT_GRAY)
            icon_lbl.pack()
            text_lbl = tk.Label(inner, text=label, font=("Malgun Gothic", 8),
                                bg=BG_SIDEBAR, fg=TEXT_GRAY)
            text_lbl.pack()

            def on_click(p=page): self.show_page(p)
            def on_enter(e, f=btn_frame, i=inner, il=icon_lbl, tl=text_lbl, p=page):
                if getattr(self, 'current_page', None) != p:
                    f.config(bg="#3a3a6a", highlightbackground=ACCENT)
                    i.config(bg="#3a3a6a")
                    il.config(bg="#3a3a6a", fg=TEXT_WHITE)
                    tl.config(bg="#3a3a6a", fg=TEXT_WHITE)
            def on_leave(e, f=btn_frame, p2=page, i=inner, il=icon_lbl, tl=text_lbl):
                if self.current_page != p2:
                    f.config(bg=BG_SIDEBAR, highlightbackground="#3a3a5a")
                    i.config(bg=BG_SIDEBAR)
                    il.config(bg=BG_SIDEBAR, fg=TEXT_GRAY)
                    tl.config(bg=BG_SIDEBAR, fg=TEXT_GRAY)

            for w in [btn_frame, inner, icon_lbl, text_lbl]:
                w.bind("<Button-1>", lambda e, p=page: on_click(p))
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)

            self.menu_buttons[page] = (btn_frame, inner, icon_lbl, text_lbl)

        # 하단 고정 - 발행이력 + 설정 + 상태
        bottom = tk.Frame(self.sidebar, bg=BG_SIDEBAR)
        bottom.pack(side="bottom", fill="x", pady=8)
        tk.Frame(bottom, bg="#222235", height=1).pack(fill="x", padx=12, pady=(0, 8))

        # 발행 이력 버튼
        hist_frame = tk.Frame(bottom, bg=BG_SIDEBAR, cursor="hand2",
                              highlightthickness=1, highlightbackground="#3a3a5a")
        hist_frame.pack(fill="x", padx=8, pady=(0, 4))
        hist_inner = tk.Frame(hist_frame, bg=BG_SIDEBAR, padx=6, pady=8)
        hist_inner.pack(fill="x")
        hist_icon = tk.Label(hist_inner, text="≡", font=("Arial", 16), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        hist_icon.pack()
        hist_lbl = tk.Label(hist_inner, text="발행 이력", font=("Malgun Gothic", 8), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        hist_lbl.pack()
        for w in [hist_frame, hist_inner, hist_icon, hist_lbl]:
            w.bind("<Button-1>", lambda e: self.show_page("history"))
            w.bind("<Enter>", lambda e: [x.config(bg="#3a3a6a") for x in [hist_frame, hist_inner, hist_icon, hist_lbl]] or
                   hist_icon.config(fg=TEXT_WHITE) or hist_lbl.config(fg=TEXT_WHITE))
            w.bind("<Leave>", lambda e: [x.config(bg=BG_SIDEBAR) for x in [hist_frame, hist_inner, hist_icon, hist_lbl]] or
                   hist_icon.config(fg=TEXT_GRAY) or hist_lbl.config(fg=TEXT_GRAY))
        self.menu_buttons["history"] = (hist_frame, hist_inner, hist_icon, hist_lbl)

        # 설정 버튼
        set_frame = tk.Frame(bottom, bg=BG_SIDEBAR, cursor="hand2",
                             highlightthickness=1, highlightbackground="#3a3a5a")
        set_frame.pack(fill="x", padx=8, pady=(0, 6))
        set_inner = tk.Frame(set_frame, bg=BG_SIDEBAR, padx=6, pady=8)
        set_inner.pack(fill="x")
        set_icon = tk.Label(set_inner, text="⚙", font=("Arial", 16), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        set_icon.pack()
        set_lbl = tk.Label(set_inner, text="설정", font=("Malgun Gothic", 8), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        set_lbl.pack()
        for w in [set_frame, set_inner, set_icon, set_lbl]:
            w.bind("<Button-1>", lambda e: self.show_page("settings"))
            w.bind("<Enter>", lambda e: [x.config(bg="#3a3a6a") for x in [set_frame, set_inner, set_icon, set_lbl]] or
                   set_icon.config(fg=TEXT_WHITE) or set_lbl.config(fg=TEXT_WHITE))
            w.bind("<Leave>", lambda e: [x.config(bg=BG_SIDEBAR) for x in [set_frame, set_inner, set_icon, set_lbl]] or
                   set_icon.config(fg=TEXT_GRAY) or set_lbl.config(fg=TEXT_GRAY))
        self.menu_buttons["settings"] = (set_frame, set_inner, set_icon, set_lbl)

        self.status_dot = tk.Label(bottom, text="● ON",
                                   font=("Arial", 8, "bold"),
                                   bg=BG_SIDEBAR, fg=SUCCESS)
        self.status_dot.pack()

    # ================================================
    # 페이지 전환
    # ================================================
    def show_page(self, page):
        # 이전 페이지 제거
        for widget in self.main_area.winfo_children():
            widget.destroy()

        # 메뉴 버튼 색상 업데이트
        for p, widgets in self.menu_buttons.items():
            btn_frame, inner, icon_lbl, text_lbl = widgets
            if p == page:
                btn_frame.config(bg=ACCENT_ACTIVE)
                inner.config(bg=ACCENT_ACTIVE)
                icon_lbl.config(bg=ACCENT_ACTIVE, fg=ACCENT)
                text_lbl.config(bg=ACCENT_ACTIVE, fg=TEXT_WHITE)
            else:
                btn_frame.config(bg=BG_SIDEBAR)
                inner.config(bg=BG_SIDEBAR)
                icon_lbl.config(bg=BG_SIDEBAR, fg=TEXT_GRAY)
                text_lbl.config(bg=BG_SIDEBAR, fg=TEXT_GRAY)

        self.current_page = page

        if page == "dashboard":
            self.build_dashboard()
        elif page == "publish":
            self.build_publish()
        elif page == "keyword":
            self.build_keyword()
        elif page == "email":
            self.run_keyword_email()
            self.show_page("dashboard")
        elif page == "history":
            self.build_history()
        elif page == "settings":
            self.build_settings()

    # ================================================
    # 대시보드 페이지
    # ================================================
    def _bind_mousewheel(self, canvas):
        """마우스 휠 스크롤 바인딩"""
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def build_dashboard(self):
        frame = tk.Frame(self.main_area, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        # 타이틀
        title_row = tk.Frame(frame, bg=BG_DARK)
        title_row.pack(fill="x", pady=(0, 10))
        tk.Label(title_row, text="대시보드", font=("Malgun Gothic", 16, "bold"),
                 bg=BG_DARK, fg=TEXT_WHITE).pack(side="left")
        now = datetime.now(KST).strftime("%Y년 %m월 %d일 %H:%M")
        tk.Label(title_row, text=f"{now} (KST)",
                 font=("Malgun Gothic", 10), bg=BG_DARK, fg=TEXT_GRAY).pack(side="right", padx=10)

        # 4등분 그리드 레이아웃
        grid = tk.Frame(frame, bg=BG_DARK)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        # ── 1. 플랫폼 설정 (좌상단) ──────────────────────────
        c1 = tk.Frame(grid, bg=BG_CARD, padx=15, pady=15)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        tk.Label(c1, text="🔀  플랫폼 설정", font=("Malgun Gothic", 12, "bold"),
                 bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 8))
        tk.Frame(c1, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 10))
        self.build_toggles(c1)

        # ── 2. 오늘의 발행 스케줄 (우상단) ──────────────────────
        c2 = tk.Frame(grid, bg=BG_CARD, padx=15, pady=15)
        c2.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        tk.Label(c2, text="🔑  오늘의 발행 스케줄", font=("Malgun Gothic", 12, "bold"),
                 bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 8))
        tk.Frame(c2, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 10))
        self.build_today_schedule(c2)

        # ── 3. 실시간 급상승 검색어 (좌하단) ─────────────────────
        c3 = tk.Frame(grid, bg=BG_CARD, padx=15, pady=15)
        c3.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))

        rt_title_row = tk.Frame(c3, bg=BG_CARD)
        rt_title_row.pack(fill="x", pady=(0, 8))
        tk.Label(rt_title_row, text="🔥  실시간 급상승 검색어",
                 font=("Malgun Gothic", 12, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(side="left")
        tk.Label(rt_title_row, text="※ 네이트 실시간",
                 font=("Malgun Gothic", 8), bg=BG_CARD, fg=TEXT_GRAY).pack(side="left", padx=(10, 0))
        # 새로고침 버튼
        def _rt_refresh():
            for w in self.rt_list_frame.winfo_children():
                w.destroy()
            tk.Label(self.rt_list_frame, text="불러오는 중...",
                     font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)
            threading.Thread(target=self._fetch_realtime_keywords, daemon=True).start()
        refresh_btn = tk.Label(rt_title_row, text="↻", font=("Malgun Gothic", 11), bg=BG_CARD,
                 fg=TEXT_GRAY, cursor="hand2")
        refresh_btn.pack(side="right", padx=4)
        refresh_btn.bind("<Button-1>", lambda e: _rt_refresh())
        tk.Frame(c3, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 10))

        # 다음 / 네이트 탭
        self.rt_source = tk.StringVar(value="nate")
        rt_tab_row = tk.Frame(c3, bg=BG_CARD)
        rt_tab_row.pack(fill="x", pady=(0, 8))
        self.rt_tab_btns = {}
        for label, val in [("네이트", "nate"), ("다음", "daum")]:
            btn = tk.Label(rt_tab_row, text=label, font=("Malgun Gothic", 10),
                           bg=ACCENT if val == "nate" else ACCENT_ACTIVE,
                           fg=TEXT_WHITE if val == "nate" else ACCENT,
                           padx=12, pady=4, cursor="hand2")
            btn.pack(side="left", padx=(0, 4))
            btn.bind("<Button-1>", lambda e, v=val: self._switch_rt_tab(v))
            self.rt_tab_btns[val] = btn

        # 고정 높이 컨테이너 (레이아웃 안정)
        rt_container = tk.Frame(c3, bg=BG_CARD, height=250)
        rt_container.pack(fill="x")
        rt_container.pack_propagate(False)
        self.rt_list_frame = tk.Frame(rt_container, bg=BG_CARD)
        self.rt_list_frame.pack(fill="both", expand=True)
        tk.Label(self.rt_list_frame, text="불러오는 중... (10~20초 소요)",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)
        self.root.after(500, self.load_realtime_keywords)

        # ── 4. 연령대별 월간 인기 검색어 (우하단) ────────────────
        c4 = tk.Frame(grid, bg=BG_CARD, padx=15, pady=15)
        c4.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

        trend_title_row = tk.Frame(c4, bg=BG_CARD)
        trend_title_row.pack(fill="x", pady=(0, 8))
        tk.Label(trend_title_row, text="📈  연령대별 월간 인기 검색어",
                 font=("Malgun Gothic", 12, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(side="left")
        tk.Label(trend_title_row, text="※ 네이버 월간 검색량 기준",
                 font=("Malgun Gothic", 8), bg=BG_CARD, fg=TEXT_GRAY).pack(side="left", padx=(10, 0))
        tk.Frame(c4, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 10))

        self.trend_age = tk.StringVar(value="20")
        tab_row = tk.Frame(c4, bg=BG_CARD)
        tab_row.pack(fill="x", pady=(0, 10))
        age_tabs = [("20대", "20"), ("30대", "30"), ("40대", "40"), ("50대", "50"), ("60대", "60")]
        self.trend_tab_btns = {}
        for label, val in age_tabs:
            btn = tk.Label(tab_row, text=label, font=("Malgun Gothic", 10),
                           bg=ACCENT_ACTIVE, fg=ACCENT, padx=12, pady=4, cursor="hand2")
            btn.pack(side="left", padx=(0, 4))
            btn.bind("<Button-1>", lambda e, v=val: self._switch_trend_tab(v))
            self.trend_tab_btns[val] = btn

        self.trend_list_frame = tk.Frame(c4, bg=BG_CARD)
        self.trend_list_frame.pack(fill="x")
        tk.Label(self.trend_list_frame, text="로딩 중...",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)
        self.root.after(300, self.load_trend_keywords)


    def load_trend_keywords(self):
        """인기 검색어 로드 (백그라운드) + 매시간 자동 갱신"""
        threading.Thread(target=self._fetch_trend_keywords, daemon=True).start()
        # 1시간(3600초)마다 자동 갱신
        self.root.after(3600 * 1000, self.load_trend_keywords)

    def _fetch_trend_keywords(self):
        """네이버 검색광고 API로 연령대별 인기 키워드 수집"""
        import urllib.request, json as _json, hmac, hashlib, base64, time
        age = self.trend_age.get()
        keywords = []

        try:
            import hmac as _hmac, hashlib as _hs, base64 as _b64, time as _t
            import requests as _req
            from config import NAVER_AD_ACCESS_LICENSE, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID

            age_seeds = {
                "20": ["자격증", "취업", "대학교", "아르바이트", "공무원"],
                "30": ["재테크", "주식", "부동산", "육아", "직장"],
                "40": ["건강검진", "보험", "교육", "재테크", "건강"],
                "50": ["노후준비", "건강보험", "연금", "건강", "여행"],
                "60": ["노인복지", "건강보험", "연금", "병원", "여행"],
            }
            seeds = age_seeds.get(age, ["건강보험"])
            seed = ",".join(seeds)

            ts = str(round(_t.time() * 1000))
            uri = "/keywordstool"
            sign = f"{ts}.GET.{uri}"
            sig = _b64.b64encode(
                _hmac.new(NAVER_AD_SECRET_KEY.encode(), sign.encode(), _hs.sha256).digest()
            ).decode()

            headers = {
                "X-Timestamp": ts,
                "X-API-KEY": NAVER_AD_ACCESS_LICENSE,
                "X-CUSTOMER": str(NAVER_AD_CUSTOMER_ID),
                "X-Signature": sig,
            }
            r = _req.get(f"https://api.naver.com{uri}",
                         headers=headers, params={"hintKeywords": seed, "showDetail": "1"}, timeout=8)
            data = r.json()
            items = data.get("keywordList", [])

            def get_vol(x):
                pc = x.get("monthlyPcQcCnt", 0)
                mob = x.get("monthlyMobileQcCnt", 0)
                try: pc = int(str(pc).replace("<", "").strip())
                except: pc = 0
                try: mob = int(str(mob).replace("<", "").strip())
                except: mob = 0
                return pc + mob

            items.sort(key=get_vol, reverse=True)
            keywords = [item["relKeyword"] for item in items[:10] if item.get("relKeyword")]
        except Exception as e:
            print(f"검색광고 API 실패: {e}")

        if not keywords:
            # 마지막 fallback: 네이버 메인 파싱
            try:
                import re
                url = "https://www.naver.com"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as res:
                    html = res.read().decode("utf-8", errors="ignore")
                matches = re.findall(r'data-clk="[^"]*"[^>]*>([^<]{2,10})</a>', html)
                keywords = [k.strip() for k in matches if k.strip() and len(k.strip()) >= 2][:10]
            except Exception as e:
                print(f"네이버 fallback 실패: {e}")

        if not keywords:
            keywords = ["데이터를 불러올 수 없어요. 잠시 후 새로고침 해주세요."]

        self.root.after(0, lambda: self._render_trend_keywords(keywords))

    def _render_trend_keywords(self, keywords):
        """검색어 목록 화면에 표시"""
        for w in self.trend_list_frame.winfo_children():
            w.destroy()

        # 탭 스타일 업데이트
        age = self.trend_age.get()
        for val, btn in self.trend_tab_btns.items():
            if val == age:
                btn.config(bg=ACCENT, fg=TEXT_WHITE)
            else:
                btn.config(bg=ACCENT_ACTIVE, fg=ACCENT)

        if not keywords:
            tk.Label(self.trend_list_frame, text="검색어 없음",
                     font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
            return

        # 2열 그리드로 표시 (한 화면에 10개)
        cols = 2
        rows_count = (len(keywords) + cols - 1) // cols  # 올림 나눗셈
        for i, kw in enumerate(keywords):
            r = i % rows_count
            c = i // rows_count
            bg = BG_ITEM if r % 2 == 0 else BG_CARD
            lbl = tk.Label(self.trend_list_frame,
                           text=f"  {i+1}.  {kw}",
                           font=("Malgun Gothic", 10),
                           bg=bg, fg=TEXT_WHITE,
                           anchor="w", cursor="hand2",
                           pady=7, padx=6)
            lbl.grid(row=r, column=c, sticky="ew", padx=2, pady=1)
            lbl.bind("<Button-1>", lambda e, k=kw: self._use_trend_keyword(k))

        for c in range(cols):
            self.trend_list_frame.columnconfigure(c, weight=1)

        now = datetime.now(KST).strftime("%H:%M")
        tk.Label(self.trend_list_frame, text=f"마지막 업데이트: {now}  |  클릭하면 키워드 분석으로 이동",
                 font=("Malgun Gothic", 8), bg=BG_CARD, fg=TEXT_GRAY).grid(
                 row=rows_count, column=0, columnspan=cols, sticky="e", pady=(6, 0))

    def _switch_trend_tab(self, age):
        self.trend_age.set(age)
        for w in self.trend_list_frame.winfo_children():
            w.destroy()
        tk.Label(self.trend_list_frame, text="로딩 중...",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)
        # 탭 스타일 즉시 업데이트
        for val, btn in self.trend_tab_btns.items():
            btn.config(bg=ACCENT if val == age else ACCENT_ACTIVE,
                       fg=TEXT_WHITE if val == age else ACCENT)
        self.load_trend_keywords()

    def load_realtime_keywords(self):
        """실시간 급상승 검색어 로드 (백그라운드) - 30분마다 자동갱신"""
        threading.Thread(target=self._fetch_realtime_keywords, daemon=True).start()
        self.root.after(1800 * 1000, self.load_realtime_keywords)

    def _fetch_realtime_keywords(self):
        """네이트 실시간 검색어 Selenium으로 가져오기"""
        keywords = []
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            import time as _t, re as _re

            opts = Options()
            opts.add_argument('--headless')
            opts.add_argument('--no-sandbox')
            opts.add_argument('--disable-dev-shm-usage')
            opts.add_argument('--disable-gpu')
            opts.add_argument('--log-level=3')
            opts.add_argument('--blink-settings=imagesEnabled=false')  # 이미지 로드 차단 → 속도↑

            driver = webdriver.Chrome(options=opts)
            try:
                source = self.rt_source.get()
                NOISE = _re.compile(r'(상승|하락|신규|동일|\s*\d+위\s*)')
                NATE_MENU = {'네이트','네이트앱','네이트온','메일','뉴스','온달','TV','만화','운세','게임','쇼핑','스포츠','연예','랭킹뉴스'}

                if source == "daum":
                    driver.get('https://www.daum.net/')
                    _t.sleep(2)
                    els = driver.find_elements(By.CSS_SELECTOR, '[class*="trendrank"] a')
                    seen = []
                    for el in els:
                        lines = el.text.strip().split('\n')
                        # 줄 중 숫자가 아닌 첫 번째 줄이 키워드
                        for line in lines:
                            text = NOISE.sub('', line).strip()
                            text = _re.sub(r'^\d+\s*', '', text).strip()
                            if text and 2 <= len(text) <= 30 and text not in seen:
                                seen.append(text)
                                break
                    keywords = seen[:10]
                else:  # nate
                    driver.get('https://www.nate.com/')
                    _t.sleep(2)
                    els = driver.find_elements(By.CSS_SELECTOR, 'ol li a')
                    seen = []
                    for el in els:
                        raw = el.text.strip().split('\n')[0].strip()
                        text = NOISE.sub('', raw).strip()
                        if text and 2 <= len(text) <= 30 and text not in seen and text not in NATE_MENU:
                            seen.append(text)
                    keywords = seen[:10]
            finally:
                driver.quit()
        except Exception as e:
            print(f"실시간 검색어 실패: {e}")

        self.root.after(0, lambda: self._render_realtime_keywords(keywords[:10]))

    def _render_realtime_keywords(self, keywords):
        for w in self.rt_list_frame.winfo_children():
            w.destroy()

        if not keywords:
            tk.Label(self.rt_list_frame, text="데이터를 가져올 수 없어요. (↻ 클릭해서 재시도)",
                     font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0, sticky="w")
            return

        cols = 2
        rows_count = (len(keywords) + cols - 1) // cols
        for i, kw in enumerate(keywords):
            r = i % rows_count
            c = i // rows_count
            bg = BG_ITEM if r % 2 == 0 else BG_CARD
            lbl = tk.Label(self.rt_list_frame,
                           text=f"  {i+1}.  {kw}",
                           font=("Malgun Gothic", 10),
                           bg=bg, fg=TEXT_WHITE,
                           anchor="w", cursor="hand2",
                           pady=6, padx=6)
            lbl.grid(row=r, column=c, sticky="ew", padx=2, pady=1)
            lbl.bind("<Button-1>", lambda e, k=kw: self._use_trend_keyword(k))
        for c in range(cols):
            self.rt_list_frame.columnconfigure(c, weight=1)

        now = datetime.now(KST).strftime("%H:%M")
        tk.Label(self.rt_list_frame, text=f"마지막 업데이트: {now}",
                 font=("Malgun Gothic", 8), bg=BG_CARD, fg=TEXT_GRAY).grid(
                 row=rows_count, column=0, columnspan=cols, sticky="e", pady=(4, 0))

    def _switch_rt_tab(self, source):
        self.rt_source.set(source)
        for val, btn in self.rt_tab_btns.items():
            btn.config(bg=ACCENT if val == source else ACCENT_ACTIVE,
                       fg=TEXT_WHITE if val == source else ACCENT)
        for w in self.rt_list_frame.winfo_children():
            w.destroy()
        tk.Label(self.rt_list_frame, text="불러오는 중...",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)
        threading.Thread(target=self._fetch_realtime_keywords, daemon=True).start()

    def _use_trend_keyword(self, keyword):
        """클릭한 검색어를 키워드 분석 탭으로 이동해서 바로 분석"""
        self.show_page("keyword")
        self.root.after(100, lambda: (
            self.kw_entry.delete(0, tk.END),
            self.kw_entry.insert(0, keyword),
            self.kw_entry.config(fg=TEXT_WHITE),
            self.run_keyword_analysis()
        ))

    def build_card(self, parent, title, content_builder):
        card = tk.Frame(parent, bg=BG_CARD, padx=20, pady=15)
        card.pack(fill="x", padx=25, pady=8)

        tk.Label(card, text=title, font=("Malgun Gothic", 12, "bold"),
                 bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 12))
        tk.Frame(card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 12))

        content_builder(card)

    def build_toggles(self, parent):
        platforms = [
            ("블로그스팟 자동발행", self.toggle_blogspot, "글 생성 후 블로그스팟에 자동 발행"),
            ("네이버 백링크 생성", self.toggle_naver, "블로그스팟 발행 후 네이버용 파일 자동 생성"),
            ("인스타그램 카드뉴스", self.toggle_insta, "준비 중"),
            ("스레드 짧은 글", self.toggle_thread, "준비 중"),
        ]

        for label, var, desc in platforms:
            row = tk.Frame(parent, bg=BG_CARD)
            row.pack(fill="x", pady=6)

            left = tk.Frame(row, bg=BG_CARD)
            left.pack(side="left", fill="x", expand=True)

            tk.Label(left, text=label, font=("Malgun Gothic", 11),
                     bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w")
            tk.Label(left, text=desc, font=("Malgun Gothic", 9),
                     bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

            toggle = ToggleButton(row, variable=var)
            toggle.pack(side="right", padx=5)

    def build_today_schedule(self, parent):
        try:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "today_keywords.json")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            schedule = data.get("schedule", [])
            if not schedule:
                tk.Label(parent, text="오늘 스케줄 없음", font=("Malgun Gothic", 10),
                         bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
                return

            for item in schedule:
                row = tk.Frame(parent, bg=BG_CARD)
                row.pack(fill="x", pady=4)

                time_label = tk.Label(row, text=item.get("time", ""),
                                      font=("Malgun Gothic", 10, "bold"),
                                      bg=BG_CARD, fg=ACCENT, width=6)
                time_label.pack(side="left")

                keyword = item.get("keyword", "")
                tk.Label(row, text=keyword, font=("Malgun Gothic", 10),
                         bg=BG_CARD, fg=TEXT_WHITE).pack(side="left", padx=10)

                status = "✅ 완료" if item.get("published") else "⏳ 대기"
                color = SUCCESS if item.get("published") else TEXT_GRAY
                tk.Label(row, text=status, font=("Malgun Gothic", 9),
                         bg=BG_CARD, fg=color).pack(side="right")

        except FileNotFoundError:
            tk.Label(parent, text="today_keywords.json 없음 (오전 5시 이메일 후 생성됨)",
                     font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
        except Exception as e:
            tk.Label(parent, text=f"오류: {e}", font=("Malgun Gothic", 10),
                     bg=BG_CARD, fg=DANGER).pack(anchor="w")

    def build_quick_actions(self, parent):
        btn_frame = tk.Frame(parent, bg=BG_CARD)
        btn_frame.pack(fill="x")
        self.make_button(btn_frame, "📧  키워드 이메일 발송", self.run_keyword_email, "#2196F3").pack(side="left")

    # ================================================
    # 글 발행 페이지
    # ================================================
    def build_publish(self):
        frame = tk.Frame(self.main_area, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(frame, text="글 발행", font=("Malgun Gothic", 18, "bold"),
                 bg=BG_DARK, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 15))

        # 키워드 입력
        card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
        card.pack(fill="x", pady=8)

        tk.Label(card, text="키워드 직접 입력해서 발행",
                 font=("Malgun Gothic", 12, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0,10))
        tk.Frame(card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 12))

        input_row = tk.Frame(card, bg=BG_CARD)
        input_row.pack(fill="x")

        tk.Label(input_row, text="키워드:", font=("Malgun Gothic", 11),
                 bg=BG_CARD, fg=TEXT_WHITE).pack(side="left", padx=(0, 10))

        self.keyword_entry = tk.Entry(input_row, font=("Malgun Gothic", 11),
                                      bg="#252540", fg=TEXT_WHITE, insertbackground=TEXT_WHITE,
                                      relief="flat", width=30)
        self.keyword_entry.pack(side="left", ipady=6, padx=(0, 10))

        self.make_button(input_row, "발행 시작", self.run_manual_publish, ACCENT).pack(side="left")

        # 진행 단계 표시
        step_card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=14)
        step_card.pack(fill="x", pady=(0, 4))

        self.steps = ["글 생성", "SEO", "이미지", "발행", "완료"]
        self._anim_offset = 0
        self._anim_running = False
        self.current_step = -1

        self.step_canvas = tk.Canvas(step_card, height=60, bg=BG_CARD, highlightthickness=0)
        self.step_canvas.pack(fill="x", expand=True)
        self.step_canvas.bind("<Configure>", lambda e: self._draw_step_bar())
        self.root.after(100, self._draw_step_bar)

        # 로그 출력창
        log_card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
        log_card.pack(fill="both", expand=True, pady=8)

        tk.Label(log_card, text="실행 로그", font=("Malgun Gothic", 12, "bold"),
                 bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 10))
        tk.Frame(log_card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(
            log_card, font=("Consolas", 10),
            bg="#111122", fg="#00ff88",
            insertbackground=TEXT_WHITE, relief="flat", height=18
        )
        self.log_text.pack(fill="both", expand=True)

    # ================================================
    # 키워드 분석 페이지
    # ================================================
    def build_keyword(self):
        frame = tk.Frame(self.main_area, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(frame, text="키워드 분석", font=("Malgun Gothic", 18, "bold"),
                 bg=BG_DARK, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 15))

        # ── 입력 카드 ──
        input_card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
        input_card.pack(fill="x", pady=(0, 10))

        input_row = tk.Frame(input_card, bg=BG_CARD)
        input_row.pack(fill="x")

        PLACEHOLDER = "키워드를 입력하세요 (예: 손예진)"
        self.kw_entry = tk.Entry(input_row, font=("Malgun Gothic", 12),
                                 bg="#252540", fg=TEXT_GRAY,
                                 insertbackground=TEXT_WHITE,
                                 relief="flat", width=35)
        self.kw_entry.pack(side="left", ipady=8, padx=(0, 10))
        self.kw_entry.insert(0, PLACEHOLDER)

        def on_focus_in(e):
            if self.kw_entry.get() == PLACEHOLDER:
                self.kw_entry.delete(0, tk.END)
                self.kw_entry.config(fg=TEXT_WHITE)
        def on_focus_out(e):
            if not self.kw_entry.get().strip():
                self.kw_entry.insert(0, PLACEHOLDER)
                self.kw_entry.config(fg=TEXT_GRAY)

        self.kw_entry.bind("<FocusIn>", on_focus_in)
        self.kw_entry.bind("<FocusOut>", on_focus_out)
        self.kw_entry.bind("<Return>", lambda e: self.run_keyword_analysis())

        # 표시 개수
        tk.Label(input_row, text="표시:", font=("Malgun Gothic", 10),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(side="left", padx=(0, 4))
        self.kw_limit_var = tk.StringVar(value="20")
        ttk.Combobox(input_row, textvariable=self.kw_limit_var,
                     values=["10", "20", "50", "전체"],
                     width=5, state="readonly").pack(side="left", padx=(0, 10))

        self.make_button(input_row, "🔍 검색", self.run_keyword_analysis, ACCENT).pack(side="left", padx=(0, 5))
        self.make_button(input_row, "초기화", self.clear_keyword_result, "#444466").pack(side="left")

        # ── 2열 레이아웃 ──
        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        # 왼쪽: 연관검색어 (네이버 자동완성)
        left_card = tk.Frame(body, bg=BG_CARD, padx=15, pady=15)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tk.Label(left_card, text="📌 연관검색어",
                 font=("Malgun Gothic", 11, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 4))
        tk.Label(left_card, text="클릭하면 검색량 분석에 자동 입력",
                 font=("Malgun Gothic", 9), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w", pady=(0, 8))
        tk.Frame(left_card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 8))

        self.kw_suggest_frame = tk.Frame(left_card, bg=BG_CARD)
        self.kw_suggest_frame.pack(fill="both", expand=True)
        tk.Label(self.kw_suggest_frame, text="키워드 검색 후 표시됩니다.",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

        # 오른쪽: 검색량 분석
        right_card = tk.Frame(body, bg=BG_CARD, padx=15, pady=15)
        right_card.grid(row=0, column=1, sticky="nsew")

        # 오른쪽 상단: 추천 키워드
        tk.Label(right_card, text="⭐ 추천 키워드 (경쟁 낮음 + 검색수 높음)",
                 font=("Malgun Gothic", 11, "bold"), bg=BG_CARD, fg=WARNING).pack(anchor="w", pady=(0, 6))
        tk.Frame(right_card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 6))
        self.kw_recommend_frame = tk.Frame(right_card, bg=BG_CARD)
        self.kw_recommend_frame.pack(fill="x", pady=(0, 10))
        tk.Label(self.kw_recommend_frame, text="검색 후 표시됩니다.",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

        # 오른쪽 하단: 검색량 테이블
        tk.Label(right_card, text="📊 검색량 분석",
                 font=("Malgun Gothic", 11, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 6))
        tk.Frame(right_card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 6))

        # 헤더
        cols_all = [("No.", 4), ("키워드", 14), ("PC검색", 7), ("모바일", 8), ("합계", 8),
                    ("경쟁강도", 7), ("PC클릭", 7), ("모바일클릭", 9), ("블로그발행수", 9), ("PC클릭률", 7), ("모바일클릭률", 9)]
        header = tk.Frame(right_card, bg="#252540")
        header.pack(fill="x", pady=(0, 2))
        for col, w in cols_all:
            tk.Label(header, text=col, font=("Malgun Gothic", 8, "bold"),
                     bg="#252540", fg=TEXT_WHITE, width=w, anchor="w", padx=3, pady=5).pack(side="left")

        # 세로 스크롤 결과 영역
        result_container = tk.Frame(right_card, bg=BG_CARD)
        result_container.pack(fill="both", expand=True)

        result_canvas = tk.Canvas(result_container, bg=BG_CARD, highlightthickness=0)
        result_scrollbar = ttk.Scrollbar(result_container, orient="vertical", command=result_canvas.yview)
        result_canvas.configure(yscrollcommand=result_scrollbar.set)
        result_scrollbar.pack(side="right", fill="y")
        result_canvas.pack(side="left", fill="both", expand=True)

        self.kw_result_frame = tk.Frame(result_canvas, bg=BG_CARD)
        rcw = result_canvas.create_window((0, 0), window=self.kw_result_frame, anchor="nw")

        def _on_frame_cfg(e): result_canvas.configure(scrollregion=result_canvas.bbox("all"))
        def _on_canvas_cfg(e): result_canvas.itemconfig(rcw, width=e.width)
        self.kw_result_frame.bind("<Configure>", _on_frame_cfg)
        result_canvas.bind("<Configure>", _on_canvas_cfg)

        def _kw_scroll(e): result_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        def _bind_kw_scroll(widget):
            widget.bind("<MouseWheel>", _kw_scroll)
            for child in widget.winfo_children():
                _bind_kw_scroll(child)

        result_canvas.bind("<MouseWheel>", _kw_scroll)
        self.kw_result_frame.bind("<MouseWheel>", _kw_scroll)
        self._kw_scroll_fn = _kw_scroll
        self._bind_kw_scroll_fn = _bind_kw_scroll
        self._kw_cols = cols_all

        self.kw_log = tk.Label(right_card, text="키워드를 입력하고 검색 버튼을 눌러주세요.",
                               font=("Malgun Gothic", 9), bg=BG_CARD, fg=TEXT_GRAY)
        self.kw_log.pack(anchor="w", pady=(6, 0))

    def clear_keyword_result(self):
        PLACEHOLDER = "키워드를 입력하세요 (예: 손예진)"
        self.kw_entry.delete(0, tk.END)
        self.kw_entry.insert(0, PLACEHOLDER)
        self.kw_entry.config(fg=TEXT_GRAY)
        for w in self.kw_result_frame.winfo_children():
            w.destroy()
        for w in self.kw_recommend_frame.winfo_children():
            w.destroy()
        for w in self.kw_suggest_frame.winfo_children():
            w.destroy()
        tk.Label(self.kw_recommend_frame, text="검색 후 표시됩니다.",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
        tk.Label(self.kw_suggest_frame, text="키워드 검색 후 표시됩니다.",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
        self.kw_log.config(text="키워드를 입력하고 검색 버튼을 눌러주세요.", fg=TEXT_GRAY)

    def run_keyword_analysis(self):
        keywords = self.kw_entry.get().strip()
        PLACEHOLDER = "키워드를 입력하세요 (예: 손예진)"
        if not keywords or keywords == PLACEHOLDER:
            messagebox.showwarning("알림", "키워드를 입력해주세요!")
            return
        self.kw_log.config(text="⏳ 조회 중...", fg=WARNING)
        for w in self.kw_result_frame.winfo_children():
            w.destroy()
        for w in self.kw_recommend_frame.winfo_children():
            w.destroy()
        for w in self.kw_suggest_frame.winfo_children():
            w.destroy()
        # 연관검색어 (네이버 자동완성) + 검색량 분석 동시 실행
        threading.Thread(target=self._run_suggest, args=(keywords,), daemon=True).start()
        threading.Thread(target=self._run_keyword_analysis, args=(keywords,), daemon=True).start()

    def _run_suggest(self, keyword):
        """네이버 자동완성 연관검색어 조회 (무료, 키 불필요)"""
        try:
            import requests
            url = "https://ac.search.naver.com/nx/ac"
            params = {"q": keyword, "q_enc": "UTF-8", "st": "11", "frm": "nv", "r_format": "json", "r_enc": "UTF-8"}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            data = resp.json()
            suggests = []
            # 응답 구조: {"query":["손예진"], "items":[["손예진","손예진 노브",...], ...]}
            if data.get("items"):
                for group in data["items"]:
                    for item in group:
                        if isinstance(item, str) and item:
                            suggests.append(item)
                        elif isinstance(item, list) and item:
                            suggests.append(item[0])

            def update_suggest():
                for w in self.kw_suggest_frame.winfo_children():
                    w.destroy()
                if not suggests:
                    tk.Label(self.kw_suggest_frame, text="연관검색어 없음",
                             font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
                    return
                for idx, sug in enumerate(suggests[:15], 1):
                    row = tk.Frame(self.kw_suggest_frame, bg=BG_CARD, cursor="hand2")
                    row.pack(fill="x", pady=1)
                    num_lbl = tk.Label(row, text=str(idx), font=("Malgun Gothic", 10),
                                       bg=BG_CARD, fg=TEXT_GRAY, width=3, anchor="e")
                    num_lbl.pack(side="left", padx=(0, 8))
                    sug_lbl = tk.Label(row, text=sug, font=("Malgun Gothic", 10),
                                       bg=BG_CARD, fg=TEXT_WHITE, anchor="w", cursor="hand2")
                    sug_lbl.pack(side="left", fill="x")

                    def on_click(s=sug):
                        self.kw_entry.delete(0, tk.END)
                        self.kw_entry.insert(0, s)
                        self.kw_entry.config(fg=TEXT_WHITE)
                        self.run_keyword_analysis()

                    def on_enter(e, r=row): r.config(bg="#252540")
                    def on_leave(e, r=row): r.config(bg=BG_CARD)

                    row.bind("<Button-1>", lambda e, s=sug: on_click(s))
                    sug_lbl.bind("<Button-1>", lambda e, s=sug: on_click(s))
                    num_lbl.bind("<Button-1>", lambda e, s=sug: on_click(s))
                    row.bind("<Enter>", on_enter)
                    row.bind("<Leave>", on_leave)

            self.root.after(0, update_suggest)
        except Exception as e:
            print(f"연관검색어 오류: {e}")

    def _run_keyword_analysis(self, keywords_str):
        try:
            import hashlib
            import hmac
            import base64
            import time

            try:
                from config import NAVER_AD_CUSTOMER_ID, NAVER_AD_ACCESS_LICENSE, NAVER_AD_SECRET_KEY
            except:
                NAVER_AD_CUSTOMER_ID = os.environ.get("NAVER_AD_CUSTOMER_ID", "")
                NAVER_AD_ACCESS_LICENSE = os.environ.get("NAVER_AD_ACCESS_LICENSE", "")
                NAVER_AD_SECRET_KEY = os.environ.get("NAVER_AD_SECRET_KEY", "")

            kw_list = [k.strip() for k in keywords_str.split(",")][:5]

            timestamp = str(round(time.time() * 1000))
            sign_str = f"{timestamp}.GET./keywordstool"
            hm = hmac.new(NAVER_AD_SECRET_KEY.encode(), sign_str.encode("utf-8"), hashlib.sha256)
            signature = base64.b64encode(hm.digest()).decode("utf-8")

            headers = {
                "X-Timestamp": timestamp,
                "X-API-KEY": NAVER_AD_ACCESS_LICENSE,
                "X-CUSTOMER": str(NAVER_AD_CUSTOMER_ID),
                "X-Signature": signature,
            }

            import requests
            resp = requests.get(
                "https://api.naver.com/keywordstool",
                headers=headers,
                params={"hintKeywords": ",".join(kw_list), "showDetail": "1"}
            )
            data = resp.json()
            items = data.get("keywordList", [])

            # 결과 없으면 공백 제거 버전으로 재시도
            if not items and " " in keywords_str:
                kw_list2 = [k.replace(" ", "") for k in kw_list]
                resp2 = requests.get(
                    "https://api.naver.com/keywordstool",
                    headers=headers,
                    params={"hintKeywords": ",".join(kw_list2), "showDetail": "1"}
                )
                items = resp2.json().get("keywordList", [])
                if items:
                    # 입력창도 공백제거 버전으로 업데이트
                    new_kw = keywords_str.replace(" ", "")
                    self.root.after(0, lambda: (
                        self.kw_entry.delete(0, tk.END),
                        self.kw_entry.insert(0, new_kw),
                        self.kw_entry.config(fg=TEXT_WHITE)
                    ))

            def get_total(item):
                pc = item.get("monthlyPcQcCnt", 0)
                mobile = item.get("monthlyMobileQcCnt", 0)
                return (pc if isinstance(pc, int) else 0) + (mobile if isinstance(mobile, int) else 0)

            items_sorted = sorted(items, key=get_total, reverse=True)

            limit_val = self.kw_limit_var.get()
            display_items = items_sorted if limit_val == "전체" else items_sorted[:int(limit_val)]
            recommend_items = [i for i in items_sorted if i.get("compIdx") == "낮음" and get_total(i) >= 1000]

            def update_ui():
                for w in self.kw_result_frame.winfo_children():
                    w.destroy()
                for w in self.kw_recommend_frame.winfo_children():
                    w.destroy()

                if not items:
                    self.kw_log.config(text="결과 없음", fg=DANGER)
                    return

                # 추천 키워드 칩
                if recommend_items:
                    for ri in recommend_items[:5]:
                        rk = ri.get("relKeyword", "")
                        rt = get_total(ri)
                        chip = tk.Frame(self.kw_recommend_frame, bg=ACCENT, padx=8, pady=3, cursor="hand2")
                        chip.pack(side="left", padx=(0, 6), pady=2)
                        lbl = tk.Label(chip, text=f"⭐ {rk} ({rt:,})",
                                       font=("Malgun Gothic", 9, "bold"), bg=ACCENT, fg=TEXT_WHITE, cursor="hand2")
                        lbl.pack()
                        def on_chip_click(s=rk):
                            self.kw_entry.delete(0, tk.END)
                            self.kw_entry.insert(0, s)
                            self.kw_entry.config(fg=TEXT_WHITE)
                            self.run_keyword_analysis()
                        chip.bind("<Button-1>", lambda e, s=rk: on_chip_click(s))
                        lbl.bind("<Button-1>", lambda e, s=rk: on_chip_click(s))
                else:
                    tk.Label(self.kw_recommend_frame, text="추천 키워드 없음 (경쟁 낮음 + 합계 1,000 이상 기준)",
                             font=("Malgun Gothic", 9), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

                # 검색량 테이블 (한 줄 + 가로 스크롤)
                for idx, item in enumerate(display_items, 1):
                    kw = item.get("relKeyword", "")
                    pc = item.get("monthlyPcQcCnt", 0)
                    mobile = item.get("monthlyMobileQcCnt", 0)
                    comp = item.get("compIdx", "-")
                    total = get_total(item)
                    pc_clk = item.get("monthlyAvePcClkCnt", 0)
                    mob_clk = item.get("monthlyAveMobileClkCnt", 0)
                    pc_ctr = item.get("monthlyAvePcCtr", 0)
                    mob_ctr = item.get("monthlyAveMobileCtr", 0)
                    blog_cnt = item.get("plAvgDepth", 0)

                    if comp == "낮음":
                        comp_color = SUCCESS; comp_bg = "#0d2a1a"
                    elif comp == "중간":
                        comp_color = WARNING; comp_bg = "#2a1f00"
                    else:
                        comp_color = DANGER; comp_bg = "#2a0d0d"
                    blog_color = SUCCESS if isinstance(blog_cnt, (int,float)) and 0 < blog_cnt < 100 else \
                                 WARNING if isinstance(blog_cnt, (int,float)) and blog_cnt < 500 else TEXT_GRAY
                    row_bg = "#252538" if idx % 2 == 0 else BG_CARD

                    row = tk.Frame(self.kw_result_frame, bg=row_bg)
                    row.pack(fill="x")

                    vals = [
                        (str(idx), 4, TEXT_GRAY),
                        (kw, 14, TEXT_WHITE),
                        (f"{pc:,}" if isinstance(pc, int) else "-", 7, TEXT_GRAY),
                        (f"{mobile:,}" if isinstance(mobile, int) else "-", 8, TEXT_GRAY),
                        (f"{total:,}", 8, TEXT_WHITE),
                        (None, 7, None),   # 경쟁강도 배지 (별도 처리)
                        (f"{float(pc_clk):,.1f}" if pc_clk not in (0, None, "-") else "0.0", 7, TEXT_GRAY),
                        (f"{float(mob_clk):,.1f}" if mob_clk not in (0, None, "-") else "0.0", 9, TEXT_GRAY),
                        (f"{int(blog_cnt):,}" if isinstance(blog_cnt, (int,float)) and blog_cnt else "-", 9, blog_color),
                        (f"{pc_ctr:.2f}%" if isinstance(pc_ctr, (int,float)) else "-", 7, TEXT_GRAY),
                        (f"{mob_ctr:.2f}%" if isinstance(mob_ctr, (int,float)) else "-", 9, TEXT_GRAY),
                    ]
                    for i2, (text, w, fg) in enumerate(vals):
                        if i2 == 5:  # 경쟁강도 배지
                            cell = tk.Frame(row, bg=row_bg, padx=4, pady=3)
                            cell.pack(side="left")
                            tk.Label(cell, text=str(comp),
                                     font=("Malgun Gothic", 8, "bold"),
                                     bg=comp_bg, fg=comp_color,
                                     padx=6, pady=2).pack()
                        else:
                            tk.Label(row, text=text, font=("Malgun Gothic", 9),
                                     bg=row_bg, fg=fg, width=w, anchor="w", padx=4, pady=4).pack(side="left")

                    self._bind_kw_scroll_fn(row)

                self.kw_log.config(text=f"✅ 전체 {len(items)}개 중 {len(display_items)}개 표시", fg=SUCCESS)

            self.root.after(0, update_ui)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.root.after(0, lambda: self.kw_log.config(text=f"❌ 오류: {str(e)[:200]}", fg=DANGER))

    # ================================================
    # 발행 이력 페이지
    # ================================================
    def build_history(self):
        frame = tk.Frame(self.main_area, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(frame, text="발행 이력", font=("Malgun Gothic", 18, "bold"),
                 bg=BG_DARK, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 15))

        card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
        card.pack(fill="both", expand=True)

        # 테이블 헤더
        header = tk.Frame(card, bg="#252540")
        header.pack(fill="x", pady=(0, 5))
        for col, w in [("발행 시간", 15), ("키워드", 20), ("상태", 8), ("URL", 30)]:
            tk.Label(header, text=col, font=("Malgun Gothic", 10, "bold"),
                     bg="#252540", fg=TEXT_WHITE, width=w, anchor="w", padx=5).pack(side="left")

        # 데이터 로드
        try:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "today_keywords.json")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("schedule", []):
                if item.get("published"):
                    row = tk.Frame(card, bg=BG_CARD)
                    row.pack(fill="x", pady=3)

                    tk.Label(row, text=item.get("published_at", "-"),
                             font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY,
                             width=15, anchor="w", padx=5).pack(side="left")
                    tk.Label(row, text=item.get("keyword", "-"),
                             font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_WHITE,
                             width=20, anchor="w", padx=5).pack(side="left")
                    tk.Label(row, text="✅ 완료",
                             font=("Malgun Gothic", 10), bg=BG_CARD, fg=SUCCESS,
                             width=8, anchor="w", padx=5).pack(side="left")

                    url = item.get("post_url", "-")
                    url_label = tk.Label(row, text=url[:35] + "..." if len(url) > 35 else url,
                                         font=("Malgun Gothic", 10), bg=BG_CARD, fg=ACCENT,
                                         cursor="hand2", anchor="w", padx=5)
                    url_label.pack(side="left")
                    if url != "-":
                        url_label.bind("<Button-1>", lambda e, u=url: self.open_url(u))

        except FileNotFoundError:
            tk.Label(card, text="발행 이력 없음", font=("Malgun Gothic", 11),
                     bg=BG_CARD, fg=TEXT_GRAY).pack(pady=30)
        except Exception as e:
            tk.Label(card, text=f"오류: {e}", font=("Malgun Gothic", 10),
                     bg=BG_CARD, fg=DANGER).pack()

    # ================================================
    # 설정 페이지
    # ================================================
    def build_settings(self):
        canvas = tk.Canvas(self.main_area, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.main_area, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=BG_DARK)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._bind_mousewheel(canvas)

        tk.Label(frame, text="설정", font=("Malgun Gothic", 18, "bold"),
                 bg=BG_DARK, fg=TEXT_WHITE).pack(anchor="w", padx=25, pady=(20, 15))

        self.setting_entries = {}

        settings_groups = [
            ("Claude API", [
                ("CLAUDE_API_KEY", "Claude API 키", True),
            ]),
            ("Google / Gemini", [
                ("GEMINI_API_KEY", "Gemini API 키", True),
                ("BLOG_ID", "블로그스팟 블로그 ID", False),
            ]),
            ("네이버 API", [
                ("NAVER_CLIENT_ID", "Naver Client ID", False),
                ("NAVER_CLIENT_SECRET", "Naver Client Secret", True),
            ]),
            ("Cloudinary", [
                ("CLOUDINARY_CLOUD_NAME", "Cloud Name", False),
                ("CLOUDINARY_API_KEY", "API Key", False),
                ("CLOUDINARY_API_SECRET", "API Secret", True),
            ]),
            ("이메일 설정", [
                ("GMAIL_ADDRESS", "Gmail 주소", False),
                ("GMAIL_APP_PASSWORD", "앱 비밀번호", True),
                ("EMAIL_RECIPIENT", "수신 이메일", False),
            ]),
        ]

        for group_title, fields in settings_groups:
            card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
            card.pack(fill="x", padx=25, pady=8)

            tk.Label(card, text=group_title, font=("Malgun Gothic", 12, "bold"),
                     bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 10))
            tk.Frame(card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 12))

            for key, label, is_secret in fields:
                row = tk.Frame(card, bg=BG_CARD)
                row.pack(fill="x", pady=5)

                tk.Label(row, text=label, font=("Malgun Gothic", 10),
                         bg=BG_CARD, fg=TEXT_GRAY, width=20, anchor="w").pack(side="left")

                show = "*" if is_secret else ""
                entry = tk.Entry(row, font=("Malgun Gothic", 10),
                                 bg="#252540", fg=TEXT_WHITE,
                                 insertbackground=TEXT_WHITE,
                                 relief="flat", show=show, width=40)
                entry.pack(side="left", ipady=5, padx=5)
                entry.insert(0, self.config_data.get(key, ""))
                self.setting_entries[key] = entry

        # 저장 버튼
        btn_frame = tk.Frame(frame, bg=BG_DARK)
        btn_frame.pack(pady=15, padx=25, anchor="w")
        self.make_button(btn_frame, "💾  설정 저장", self.save_settings, ACCENT).pack(side="left", padx=(0,10))

    # ================================================
    # 유틸리티
    # ================================================
    def make_button(self, parent, text, command, color=ACCENT):
        btn = tk.Button(
            parent, text=text,
            font=("Malgun Gothic", 10, "bold"),
            bg=color, fg=TEXT_WHITE,
            activebackground=ACCENT_HOVER, activeforeground=TEXT_WHITE,
            relief="flat", padx=16, pady=9,
            cursor="hand2", command=command,
            bd=0, highlightthickness=0
        )
        return btn

    def make_card(self, parent, title=None, pady=8):
        """일관된 카드 스타일 컨테이너"""
        card = tk.Frame(parent, bg=BG_CARD, padx=20, pady=16,
                        highlightbackground="#2e2e48", highlightthickness=1)
        card.pack(fill="x", pady=pady)
        if title:
            hdr = tk.Frame(card, bg=BG_CARD)
            hdr.pack(fill="x", pady=(0, 10))
            tk.Label(hdr, text=title, font=("Malgun Gothic", 11, "bold"),
                     bg=BG_CARD, fg=TEXT_WHITE).pack(side="left")
            tk.Frame(card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 12))
        return card

    def _draw_step_bar(self):
        """단일 Canvas에 전체 스텝바 그리기"""
        if not hasattr(self, 'step_canvas'):
            return
        c = self.step_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 10:
            return
        n = len(self.steps)
        # 각 dot의 x 위치
        xs = [int(w * (i + 0.5) / n) for i in range(n)]
        dot_y, line_y, label_y = 20, 20, 40

        # 연결선 그리기
        for i in range(n - 1):
            x1, x2 = xs[i] + 14, xs[i+1] - 14
            if i < self.current_step:
                # 완료 - 초록 실선
                c.create_line(x1, line_y, x2, line_y, fill=SUCCESS, width=2)
            elif i == self.current_step:
                # 진행 중 - 흐르는 점선
                seg, gap = 10, 6
                offset = self._anim_offset % (seg + gap)
                x = x1 - offset
                while x < x2:
                    xa = max(x1, x)
                    xb = min(x2, x + seg)
                    if xb > xa:
                        c.create_line(xa, line_y, xb, line_y, fill=ACCENT, width=2)
                    x += seg + gap
            else:
                # 대기 - 회색 점선
                x = x1
                while x < x2:
                    c.create_line(x, line_y, min(x+4, x2), line_y, fill="#333355", width=2)
                    x += 8

        # 점과 라벨 그리기
        for i, (step, x) in enumerate(zip(self.steps, xs)):
            if i < self.current_step:
                color = SUCCESS
                dot_char = "✔"
            elif i == self.current_step:
                color = ACCENT
                dot_char = "●"
            else:
                color = TEXT_GRAY
                dot_char = "●"
            c.create_text(x, dot_y, text=dot_char, fill=color, font=("Malgun Gothic", 14))
            c.create_text(x, label_y, text=step, fill=color, font=("Malgun Gothic", 9))

    def _animate_step_bar(self):
        """애니메이션 루프"""
        if not self._anim_running:
            return
        self._anim_offset += 2
        self._draw_step_bar()
        self.root.after(60, self._animate_step_bar)

    def set_step(self, step_index):
        self.current_step = step_index
        self._draw_step_bar()

    def reset_steps(self):
        self._anim_running = False
        self.current_step = -1
        self._anim_offset = 0
        self._draw_step_bar()

    def log(self, message):
        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, f"[{datetime.now(KST).strftime('%H:%M:%S')}] {message}\n")
            self.log_text.see(tk.END)

    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def update_status(self):
        self.status_dot.config(text="● 자동화 실행 중", fg=SUCCESS)
        self.root.after(60000, self.update_status)

    def refresh_dashboard(self):
        self.show_page("dashboard")

    # ================================================
    # 실행 함수들
    # ================================================
    def run_publish_now(self):
        if messagebox.askyesno("확인", "지금 바로 자동 발행을 실행할까요?"):
            self.show_page("publish")
            threading.Thread(target=self._run_auto_publish, daemon=True).start()

    def _run_auto_publish(self):
        self.log("🚀 자동 발행 시작...")
        try:
            import auto_publish
            auto_publish.main()
            self.log("✅ 완료!")
        except Exception as e:
            self.log(f"❌ 오류: {e}")

    def run_manual_publish(self):
        keyword = self.keyword_entry.get().strip()
        if not keyword:
            messagebox.showwarning("알림", "키워드를 입력해주세요!")
            return
        threading.Thread(target=self._run_manual_publish, args=(keyword,), daemon=True).start()

    def _run_manual_publish(self, keyword):
        self.log(f"📝 '{keyword}' 발행 시작...")
        self.reset_steps()
        self._anim_running = True
        self.root.after(100, self._animate_step_bar)
        try:
            from blog_automation import (
                generate_blog_post, generate_images_with_vertex,
                generate_thumbnail_with_vertex, generate_seo_metadata,
                inject_seo_metadata, insert_images_into_content, publish_to_blogger
            )
            self.set_step(0)
            self.log("글 생성 중...")
            title, content = generate_blog_post(keyword)
            self.log(f"제목: {title}")

            self.set_step(1)
            self.log("SEO 메타데이터 생성 중...")
            desc, keywords_meta = generate_seo_metadata(keyword, title, content)
            content = inject_seo_metadata(content, title, desc, keywords_meta, keyword)

            self.set_step(2)
            self.log("이미지 생성 중...")
            images = generate_images_with_vertex(keyword, count=3)
            thumbnail = generate_thumbnail_with_vertex(keyword, title)

            all_images = ([thumbnail] if thumbnail else []) + images
            if all_images:
                content = insert_images_into_content(content, all_images, keyword)

            self.set_step(3)
            self.log("블로그스팟 발행 중...")
            result = publish_to_blogger(title, content)
            post_url = result.get("url") if result else None

            if post_url:
                self._anim_running = False
                self.set_step(4)
                self.log(f"✅ 발행 완료! → {post_url}")

                if self.toggle_naver.get():
                    self.log("네이버 백링크용 글 생성 중...")
                    from naver_post_generator import generate_naver_post
                    naver_result = generate_naver_post(keyword, title, content, all_images, post_url)
                    self.log(f"✅ 네이버용 파일 저장: {naver_result['html_path']}")
            else:
                self.log("❌ 발행 실패")
        except Exception as e:
            self.log(f"❌ 오류: {e}")

    def run_keyword_email(self):
        if messagebox.askyesno("확인", "키워드 이메일을 지금 발송할까요?"):
            self.show_page("publish")
            threading.Thread(target=self._run_keyword_email, daemon=True).start()

    def _run_keyword_email(self):
        self.log("📧 키워드 이메일 발송 중...")
        try:
            import keyword_email
            keyword_email.main()
            self.log("✅ 이메일 발송 완료!")
        except Exception as e:
            self.log(f"❌ 오류: {e}")

    def save_settings(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            for key, entry in self.setting_entries.items():
                value = entry.get().strip()
                if value:
                    import re
                    pattern = rf'^({key}\s*=\s*)["\'].*?["\']'
                    replacement = f'{key} = "{value}"'
                    content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.config_data = self.load_config()
            messagebox.showinfo("완료", "설정이 저장되었습니다!")
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패: {e}")


# ================================================
# 실행
# ================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = BlogMasterApp(root)
    root.mainloop()
