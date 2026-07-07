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
GOLD = "#D4AF37"
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
                                 highlightthickness=1, highlightbackground=GOLD)
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
                    f.config(bg=BG_SIDEBAR, highlightbackground=GOLD)
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
                              highlightthickness=1, highlightbackground=GOLD)
        hist_frame.pack(fill="x", padx=8, pady=(0, 4))
        hist_inner = tk.Frame(hist_frame, bg=BG_SIDEBAR, padx=6, pady=8)
        hist_inner.pack(fill="x")
        hist_icon = tk.Label(hist_inner, text="≡", font=("Arial", 16), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        hist_icon.pack()
        hist_lbl = tk.Label(hist_inner, text="발행 이력", font=("Malgun Gothic", 8), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        hist_lbl.pack()
        for w in [hist_frame, hist_inner, hist_icon, hist_lbl]:
            w.bind("<Button-1>", lambda e: self.show_page("history"))
            w.bind("<Enter>", lambda e: (
                [x.config(bg="#3a3a6a") for x in [hist_frame, hist_inner, hist_icon, hist_lbl]] or
                hist_icon.config(fg=TEXT_WHITE) or hist_lbl.config(fg=TEXT_WHITE)
            ) if getattr(self, 'current_page', None) != "history" else None)
            w.bind("<Leave>", lambda e: (
                [x.config(bg=BG_SIDEBAR) for x in [hist_frame, hist_inner, hist_icon, hist_lbl]] or
                hist_icon.config(fg=TEXT_GRAY) or hist_lbl.config(fg=TEXT_GRAY)
            ) if getattr(self, 'current_page', None) != "history" else None)
        self.menu_buttons["history"] = (hist_frame, hist_inner, hist_icon, hist_lbl)

        # 설정 버튼
        set_frame = tk.Frame(bottom, bg=BG_SIDEBAR, cursor="hand2",
                             highlightthickness=1, highlightbackground=GOLD)
        set_frame.pack(fill="x", padx=8, pady=(0, 6))
        set_inner = tk.Frame(set_frame, bg=BG_SIDEBAR, padx=6, pady=8)
        set_inner.pack(fill="x")
        set_icon = tk.Label(set_inner, text="⚙", font=("Arial", 16), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        set_icon.pack()
        set_lbl = tk.Label(set_inner, text="설정", font=("Malgun Gothic", 8), bg=BG_SIDEBAR, fg=TEXT_GRAY)
        set_lbl.pack()
        for w in [set_frame, set_inner, set_icon, set_lbl]:
            w.bind("<Button-1>", lambda e: self.show_page("settings"))
            w.bind("<Enter>", lambda e: (
                [x.config(bg="#3a3a6a") for x in [set_frame, set_inner, set_icon, set_lbl]] or
                set_icon.config(fg=TEXT_WHITE) or set_lbl.config(fg=TEXT_WHITE)
            ) if getattr(self, 'current_page', None) != "settings" else None)
            w.bind("<Leave>", lambda e: (
                [x.config(bg=BG_SIDEBAR) for x in [set_frame, set_inner, set_icon, set_lbl]] or
                set_icon.config(fg=TEXT_GRAY) or set_lbl.config(fg=TEXT_GRAY)
            ) if getattr(self, 'current_page', None) != "settings" else None)
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

        # 메뉴 버튼 색상 업데이트 (등록된 모든 버튼 포함)
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
        # hover 잔상 제거를 위해 약간의 딜레이 후 재적용
        self.root.after(150, self._refresh_sidebar_colors)

        if page == "dashboard":
            self.build_dashboard()
        elif page == "publish":
            self.build_publish()
        elif page == "keyword":
            self.build_keyword()
        elif page == "email":
            self.build_email()
        elif page == "history":
            self.build_history()
        elif page == "settings":
            self.build_settings()

    def _refresh_sidebar_colors(self):
        """사이드바 버튼 색상 강제 갱신"""
        page = getattr(self, 'current_page', None)
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
        for label, val in [("네이트", "nate"), ("다음", "daum"), ("구글트렌드", "google"), ("카테고리별", "category")]:
            btn = tk.Label(rt_tab_row, text=label, font=("Malgun Gothic", 10),
                           bg=ACCENT if val == "nate" else ACCENT_ACTIVE,
                           fg=TEXT_WHITE if val == "nate" else ACCENT,
                           padx=12, pady=4, cursor="hand2")
            btn.pack(side="left", padx=(0, 4))
            btn.bind("<Button-1>", lambda e, v=val: self._switch_rt_tab(v))
            self.rt_tab_btns[val] = btn

        # 카테고리별 탭용 드롭다운 (기본 숨김)
        self.cat_tab_frame = tk.Frame(c3, bg=BG_CARD)
        self.cat_tab_var = tk.StringVar(value="재테크·금융")
        CAT_OPTIONS = ["재테크·금융", "건강·의학", "부동산", "비즈니스·경제", "IT·컴퓨터",
                       "스타·연예인", "국내여행", "세계여행", "육아·결혼", "요리·레시피",
                       "패션·미용", "사회·정치", "교육·학문", "게임", "스포츠",
                       "반려동물", "인테리어·DIY", "자동차", "문화·책", "일상·생각"]
        cat_combo = ttk.Combobox(self.cat_tab_frame, textvariable=self.cat_tab_var,
                                  values=CAT_OPTIONS, state="readonly", width=14,
                                  font=("Malgun Gothic", 10))
        cat_combo.pack(side="left", padx=(0, 8))
        tk.Button(self.cat_tab_frame, text="조회", font=("Malgun Gothic", 10),
                  bg=ACCENT, fg="white", relief="flat", bd=0, padx=10, pady=2,
                  cursor="hand2", command=lambda: self._fetch_category_news(self.cat_tab_var.get())).pack(side="left")

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
        """실시간 검색어 가져오기"""
        keywords = []
        source = self.rt_source.get()
        try:
            # 구글 트렌드는 RSS로 바로 가져옴 (Selenium 불필요)
            if source == "google":
                import urllib.request, xml.etree.ElementTree as ET
                url = "https://trends.google.com/trending/rss?geo=KR"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    tree = ET.parse(r)
                seen = []
                for item in tree.findall(".//item"):
                    title = item.findtext("title", "").strip()
                    if title and title not in seen:
                        seen.append(title)
                    if len(seen) >= 20:
                        break
                keywords = seen[:20]
                self.root.after(0, lambda: self._render_realtime_keywords(keywords))
                return

            # 네이트/다음은 Selenium 사용
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
            opts.add_argument('--blink-settings=imagesEnabled=false')

            driver = webdriver.Chrome(options=opts)
            try:
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

        self.root.after(0, lambda: self._render_realtime_keywords(keywords[:20]))

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
        # 카테고리 드롭다운 표시/숨김
        if source == "category":
            self.cat_tab_frame.pack(fill="x", pady=(0, 6))
            for w in self.rt_list_frame.winfo_children():
                w.destroy()
            tk.Label(self.rt_list_frame, text="카테고리 선택 후 조회 버튼을 눌러주세요.",
                     font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)
        else:
            self.cat_tab_frame.pack_forget()
            for w in self.rt_list_frame.winfo_children():
                w.destroy()
            tk.Label(self.rt_list_frame, text="불러오는 중...",
                     font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)
            threading.Thread(target=self._fetch_realtime_keywords, daemon=True).start()

    def _fetch_category_news(self, category):
        """카테고리별 네이버 뉴스 RSS에서 키워드 수집"""
        CAT_RSS = {
            "재테크·금융": "https://rss.naver.com/main/rss/news/economy.xml",
            "건강·의학": "https://rss.naver.com/main/rss/news/society.xml",
            "부동산": "https://rss.naver.com/main/rss/news/economy.xml",
            "비즈니스·경제": "https://rss.naver.com/main/rss/news/economy.xml",
            "IT·컴퓨터": "https://rss.naver.com/main/rss/news/it.xml",
            "스타·연예인": "https://rss.naver.com/main/rss/news/entertainment.xml",
            "국내여행": "https://rss.naver.com/main/rss/news/society.xml",
            "세계여행": "https://rss.naver.com/main/rss/news/world.xml",
            "육아·결혼": "https://rss.naver.com/main/rss/news/society.xml",
            "요리·레시피": "https://rss.naver.com/main/rss/news/society.xml",
            "패션·미용": "https://rss.naver.com/main/rss/news/entertainment.xml",
            "사회·정치": "https://rss.naver.com/main/rss/news/politics.xml",
            "교육·학문": "https://rss.naver.com/main/rss/news/society.xml",
            "게임": "https://rss.naver.com/main/rss/news/it.xml",
            "스포츠": "https://rss.naver.com/main/rss/news/sports.xml",
            "반려동물": "https://rss.naver.com/main/rss/news/society.xml",
            "인테리어·DIY": "https://rss.naver.com/main/rss/news/society.xml",
            "자동차": "https://rss.naver.com/main/rss/news/it.xml",
            "문화·책": "https://rss.naver.com/main/rss/news/culture.xml",
            "일상·생각": "https://rss.naver.com/main/rss/news/society.xml",
        }
        for w in self.rt_list_frame.winfo_children():
            w.destroy()
        tk.Label(self.rt_list_frame, text="불러오는 중...",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).grid(row=0, column=0)

        def fetch():
            try:
                import requests, re
                url = CAT_RSS.get(category, "https://rss.naver.com/main/rss/news/society.xml")
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(url, headers=headers, timeout=8)
                titles = re.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', resp.text)
                # 첫번째는 채널 제목이라 제거
                titles = [t for t in titles if len(t) > 2][:20]
                self.root.after(0, lambda: self._render_realtime_keywords(titles))
            except Exception as e:
                self.root.after(0, lambda: self._render_realtime_keywords([f"오류: {e}"]))

        threading.Thread(target=fetch, daemon=True).start()

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

        # ── 카테고리 카드 ──
        cat_card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=12)
        cat_card.pack(fill="x", pady=(0, 8))

        tk.Label(cat_card, text="카테고리 선택", font=("Malgun Gothic", 10, "bold"),
                 bg=BG_CARD, fg=ACCENT).pack(anchor="w", pady=(0, 8))

        CATEGORIES = [
            ("전체", None),
            ("재테크·금융", ["주식", "절세", "보험", "연금", "적금", "투자", "ETF", "ISA", "IRP"]),
            ("건강·의학", ["다이어트", "영양제", "병원", "질병", "운동", "건강검진", "의료비"]),
            ("부동산", ["청약", "전세", "매매", "임대", "아파트", "분양", "부동산세금"]),
            ("비즈니스·경제", ["창업", "마케팅", "세금", "사업자", "직장인", "부업", "경제"]),
            ("IT·컴퓨터", ["AI", "앱", "스마트폰", "노트북", "프로그램", "인공지능", "챗GPT"]),
            ("스타·연예인", ["아이돌", "드라마", "영화", "방송", "연예인", "콘서트", "음악"]),
            ("국내여행", ["여행지", "숙소", "맛집", "관광", "캠핑", "제주도", "강원도"]),
            ("세계여행", ["해외여행", "항공권", "호텔", "유럽", "일본", "동남아", "미국"]),
            ("육아·결혼", ["육아", "출산", "임신", "결혼", "웨딩", "어린이집", "교육"]),
            ("요리·레시피", ["레시피", "요리", "맛집", "간식", "다이어트식단", "베이킹"]),
            ("패션·미용", ["화장품", "스킨케어", "패션", "뷰티", "헤어", "네일", "다이어트"]),
            ("사회·정치", ["정책", "법률", "지원금", "복지", "선거", "사회이슈"]),
            ("교육·학문", ["공부법", "수능", "영어", "자격증", "취업", "학원", "독서"]),
            ("게임", ["게임", "모바일게임", "PC게임", "리뷰", "신작게임", "e스포츠"]),
            ("스포츠", ["축구", "야구", "운동", "헬스", "골프", "농구", "피트니스"]),
            ("반려동물", ["강아지", "고양이", "펫", "동물병원", "사료", "반려동물용품"]),
            ("인테리어·DIY", ["인테리어", "홈데코", "DIY", "가구", "청소", "정리정돈"]),
            ("자동차", ["자동차", "전기차", "중고차", "자동차보험", "주차", "드라이브"]),
            ("문화·책", ["독서", "책추천", "영화리뷰", "전시회", "공연", "문화생활"]),
            ("일상·생각", ["일상", "감성", "에세이", "생각", "라이프스타일", "힐링"]),
        ]
        self.selected_category = tk.StringVar(value="전체")

        cat_scroll_frame = tk.Frame(cat_card, bg=BG_CARD)
        cat_scroll_frame.pack(fill="x")

        # 카테고리 버튼들 (2줄로 배치)
        self._cat_buttons = {}
        row1 = tk.Frame(cat_scroll_frame, bg=BG_CARD)
        row1.pack(fill="x", pady=(0, 4))
        row2 = tk.Frame(cat_scroll_frame, bg=BG_CARD)
        row2.pack(fill="x")

        half = len(CATEGORIES) // 2 + 1
        self._categories_data = CATEGORIES

        def select_cat(name, btn):
            self.selected_category.set(name)
            for b in self._cat_buttons.values():
                b.config(bg=BG_ITEM, fg=TEXT_GRAY)
            btn.config(bg=ACCENT, fg="white")

        for i, (name, seeds) in enumerate(CATEGORIES):
            parent_row = row1 if i < half else row2
            btn = tk.Button(parent_row, text=name, font=("Malgun Gothic", 9),
                            bg=ACCENT if name == "전체" else BG_ITEM,
                            fg="white" if name == "전체" else TEXT_GRAY,
                            relief="flat", bd=0, padx=8, pady=4, cursor="hand2")
            btn.config(command=lambda n=name, b=btn: select_cat(n, b))
            btn.pack(side="left", padx=2, pady=1)
            self._cat_buttons[name] = btn

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

        self.kw_limit_var = tk.StringVar(value="전체")  # 표시 드롭다운 제거

        self.make_button(input_row, "🔍 검색", self.run_keyword_analysis, ACCENT).pack(side="left", padx=(0, 5))
        self.make_button(input_row, "초기화", self.clear_keyword_result, "#444466").pack(side="left")

        # ── 2열 레이아웃 ──
        body = tk.Frame(frame, bg=BG_DARK)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        # 왼쪽: 연관검색어 (네이버 자동완성) + 발행 설정 (스크롤 가능)
        left_outer = tk.Frame(body, bg=BG_CARD)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)

        left_canvas = tk.Canvas(left_outer, bg=BG_CARD, highlightthickness=0)
        left_scroll = ttk.Scrollbar(left_outer, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_scroll.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)

        left_card = tk.Frame(left_canvas, bg=BG_CARD, padx=15, pady=15)
        left_card_win = left_canvas.create_window((0, 0), window=left_card, anchor="nw")

        def _left_cfg(e): left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        def _left_canvas_cfg(e): left_canvas.itemconfig(left_card_win, width=e.width)
        left_card.bind("<Configure>", _left_cfg)
        left_canvas.bind("<Configure>", _left_canvas_cfg)
        left_canvas.bind("<MouseWheel>", lambda e: left_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ── 연관검색어 헤더 ──
        suggest_header = tk.Frame(left_card, bg=BG_CARD)
        suggest_header.pack(fill="x", pady=(0, 4))
        tk.Label(suggest_header, text="📌 연관검색어",
                 font=("Malgun Gothic", 11, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(side="left")
        self.kw_selected_lbl = tk.Label(suggest_header, text="",
                 font=("Malgun Gothic", 9), bg=BG_CARD, fg=ACCENT)
        self.kw_selected_lbl.pack(side="right")

        tk.Label(left_card, text="체크박스로 다중 선택 후 글 생성",
                 font=("Malgun Gothic", 9), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w", pady=(0, 4))

        # 전체선택/전체해제 버튼
        sel_btn_row = tk.Frame(left_card, bg=BG_CARD)
        sel_btn_row.pack(fill="x", pady=(0, 6))
        self.kw_check_vars = []   # (BooleanVar, keyword) 목록

        def _select_all():
            for var, _ in self.kw_check_vars:
                var.set(True)
            self._update_selected_count()

        def _deselect_all():
            for var, _ in self.kw_check_vars:
                var.set(False)
            self._update_selected_count()

        tk.Button(sel_btn_row, text="전체선택", font=("Malgun Gothic", 8),
                  bg="#252540", fg=TEXT_WHITE, relief="flat", padx=8, pady=2,
                  cursor="hand2", command=_select_all).pack(side="left", padx=(0, 4))
        tk.Button(sel_btn_row, text="전체해제", font=("Malgun Gothic", 8),
                  bg="#252540", fg=TEXT_WHITE, relief="flat", padx=8, pady=2,
                  cursor="hand2", command=_deselect_all).pack(side="left")

        tk.Frame(left_card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 8))

        # 연관검색어 스크롤 영역
        suggest_container = tk.Frame(left_card, bg=BG_CARD)
        suggest_container.pack(fill="x")
        suggest_canvas = tk.Canvas(suggest_container, bg=BG_CARD, highlightthickness=0, height=220)
        suggest_sb = ttk.Scrollbar(suggest_container, orient="vertical", command=suggest_canvas.yview)
        suggest_canvas.configure(yscrollcommand=suggest_sb.set)
        suggest_sb.pack(side="right", fill="y")
        suggest_canvas.pack(side="left", fill="both", expand=True)

        self.kw_suggest_frame = tk.Frame(suggest_canvas, bg=BG_CARD)
        _sug_win = suggest_canvas.create_window((0, 0), window=self.kw_suggest_frame, anchor="nw")
        def _sug_cfg(e): suggest_canvas.configure(scrollregion=suggest_canvas.bbox("all"))
        def _sug_can_cfg(e): suggest_canvas.itemconfig(_sug_win, width=e.width)
        self.kw_suggest_frame.bind("<Configure>", _sug_cfg)
        suggest_canvas.bind("<Configure>", _sug_can_cfg)
        def _sug_scroll(e): suggest_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        suggest_canvas.bind("<MouseWheel>", _sug_scroll)
        self.kw_suggest_frame.bind("<MouseWheel>", _sug_scroll)
        self._sug_scroll_fn = _sug_scroll
        self._suggest_canvas = suggest_canvas

        tk.Label(self.kw_suggest_frame, text="키워드 검색 후 표시됩니다.",
                 font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

        # ── 발행 설정 영역 ──
        tk.Frame(left_card, bg="#2e2e48", height=1).pack(fill="x", pady=(12, 8))
        tk.Label(left_card, text="🚀 발행 설정",
                 font=("Malgun Gothic", 11, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 6))

        self.publish_mode = tk.StringVar(value="instant")

        mode_row = tk.Frame(left_card, bg=BG_CARD)
        mode_row.pack(fill="x", pady=(0, 6))
        tk.Radiobutton(mode_row, text="즉시 순차발행", variable=self.publish_mode,
                       value="instant", font=("Malgun Gothic", 9),
                       bg=BG_CARD, fg=TEXT_WHITE, selectcolor=BG_DARK,
                       activebackground=BG_CARD, activeforeground=TEXT_WHITE,
                       command=self._on_publish_mode_change).pack(side="left", padx=(0, 10))
        tk.Radiobutton(mode_row, text="예약 발행", variable=self.publish_mode,
                       value="scheduled", font=("Malgun Gothic", 9),
                       bg=BG_CARD, fg=TEXT_WHITE, selectcolor=BG_DARK,
                       activebackground=BG_CARD, activeforeground=TEXT_WHITE,
                       command=self._on_publish_mode_change).pack(side="left")

        # 예약 발행 옵션 (숨김/표시 토글)
        self.kw_schedule_frame = tk.Frame(left_card, bg=BG_CARD)
        self.kw_schedule_frame.pack(fill="x")

        # 시작날짜 - 달력 팝업 버튼
        sched_date_row = tk.Frame(self.kw_schedule_frame, bg=BG_CARD)
        sched_date_row.pack(fill="x", pady=(2, 2))
        tk.Label(sched_date_row, text="시작날짜", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY, width=7, anchor="w").pack(side="left")
        self.sched_date_var = tk.StringVar(value=datetime.now(KST).strftime("%Y-%m-%d"))
        date_lbl = tk.Label(sched_date_row, textvariable=self.sched_date_var,
                 font=("Malgun Gothic", 9), bg="#252540", fg=TEXT_WHITE,
                 relief="flat", padx=6, pady=3, cursor="hand2")
        date_lbl.pack(side="left", padx=(4, 4))
        def _open_cal():
            from tkcalendar import Calendar
            top = tk.Toplevel(self.root)
            top.title("날짜 선택")
            top.configure(bg=BG_DARK)
            top.resizable(False, False)
            top.grab_set()
            cal = Calendar(top, selectmode="day", locale="ko_KR",
                           date_pattern="yyyy-mm-dd",
                           background=BG_CARD, foreground=TEXT_WHITE,
                           headersbackground=ACCENT, headersforeground="white",
                           selectbackground=ACCENT, selectforeground="white",
                           normalbackground=BG_CARD, normalforeground=TEXT_WHITE,
                           weekendbackground=BG_CARD, weekendforeground=WARNING,
                           othermonthbackground=BG_DARK, othermonthforeground=TEXT_GRAY)
            cal.pack(padx=10, pady=10)
            def _pick():
                self.sched_date_var.set(cal.get_date())
                self._update_schedule_preview()
                top.destroy()
            tk.Button(top, text="선택", command=_pick,
                      bg=ACCENT, fg="white", relief="flat",
                      font=("Malgun Gothic", 10, "bold"),
                      padx=20, pady=6, cursor="hand2").pack(pady=(0, 10))
        date_lbl.bind("<Button-1>", lambda e: _open_cal())
        tk.Button(sched_date_row, text="📅", command=_open_cal,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Malgun Gothic", 9), cursor="hand2",
                  padx=4, pady=2).pack(side="left")

        # 시작시간 - 시/분 스핀박스
        sched_time_row = tk.Frame(self.kw_schedule_frame, bg=BG_CARD)
        sched_time_row.pack(fill="x", pady=(2, 2))
        tk.Label(sched_time_row, text="시작시간", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY, width=7, anchor="w").pack(side="left")
        now_kst = datetime.now(KST)
        self.sched_hour_var = tk.StringVar(value=now_kst.strftime("%H"))
        self.sched_min_var = tk.StringVar(value="00")
        hour_spin = tk.Spinbox(sched_time_row, textvariable=self.sched_hour_var,
                               from_=0, to=23, width=3, format="%02.0f",
                               bg="#252540", fg=TEXT_WHITE, insertbackground=TEXT_WHITE,
                               buttonbackground=ACCENT, relief="flat",
                               font=("Malgun Gothic", 10),
                               command=self._update_schedule_preview)
        hour_spin.pack(side="left", padx=(4, 2))
        tk.Label(sched_time_row, text="시", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(side="left")
        min_spin = tk.Spinbox(sched_time_row, textvariable=self.sched_min_var,
                              values=["00", "10", "20", "30", "40", "50"],
                              width=3, bg="#252540", fg=TEXT_WHITE,
                              insertbackground=TEXT_WHITE, buttonbackground=ACCENT,
                              relief="flat", font=("Malgun Gothic", 10),
                              command=self._update_schedule_preview)
        min_spin.pack(side="left", padx=(4, 2))
        tk.Label(sched_time_row, text="분", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(side="left")

        # 발행간격 - 드롭다운 1~24시간
        sched_interval_row = tk.Frame(self.kw_schedule_frame, bg=BG_CARD)
        sched_interval_row.pack(fill="x", pady=(2, 2))
        tk.Label(sched_interval_row, text="발행간격", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY, width=7, anchor="w").pack(side="left")
        self.sched_interval_var = tk.StringVar(value="1시간")
        interval_values = [f"{i}시간" for i in range(1, 25)]
        interval_cb = ttk.Combobox(sched_interval_row, textvariable=self.sched_interval_var,
                                   values=interval_values,
                                   state="readonly", width=10, font=("Malgun Gothic", 9))
        interval_cb.pack(side="left", padx=(4, 0))
        interval_cb.bind("<<ComboboxSelected>>", lambda e: self._update_schedule_preview())

        # 스케줄 미리보기
        self.kw_schedule_preview = tk.Label(self.kw_schedule_frame, text="",
                 font=("Malgun Gothic", 8), bg=BG_CARD, fg=TEXT_GRAY,
                 justify="left", wraplength=200)
        self.kw_schedule_preview.pack(anchor="w", pady=(4, 0))

        # 날짜/시간 변경시 미리보기 갱신
        self.sched_date_var.trace_add("write", lambda *a: self._update_schedule_preview())
        self.sched_hour_var.trace_add("write", lambda *a: self._update_schedule_preview())
        self.sched_min_var.trace_add("write", lambda *a: self._update_schedule_preview())

        # 초기에는 예약발행 옵션 숨김
        self.kw_schedule_frame.pack_forget()

        tk.Frame(left_card, bg="#2e2e48", height=1).pack(fill="x", pady=(10, 8))

        # ── 이미지 설정 ──
        tk.Label(left_card, text="\U0001f5bc\ufe0f \uc774\ubbf8\uc9c0 \uc124\uc815",
                 font=("Malgun Gothic", 10, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 4))

        thumb_row = tk.Frame(left_card, bg=BG_CARD)
        thumb_row.pack(fill="x", pady=(0, 4))
        tk.Label(thumb_row, text="\uc378\ub124\uc77c", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY, width=7, anchor="w").pack(side="left")
        self.thumb_var = tk.StringVar(value="\uc788\uc74c")
        tk.Radiobutton(thumb_row, text="\uc788\uc74c", variable=self.thumb_var, value="\uc788\uc74c",
                       font=("Malgun Gothic", 9), bg=BG_CARD, fg=TEXT_WHITE,
                       selectcolor=BG_DARK, activebackground=BG_CARD).pack(side="left", padx=(4,6))
        tk.Radiobutton(thumb_row, text="\uc5c6\uc74c", variable=self.thumb_var, value="\uc5c6\uc74c",
                       font=("Malgun Gothic", 9), bg=BG_CARD, fg=TEXT_WHITE,
                       selectcolor=BG_DARK, activebackground=BG_CARD).pack(side="left")

        img_row = tk.Frame(left_card, bg=BG_CARD)
        img_row.pack(fill="x", pady=(0, 8))
        tk.Label(img_row, text="\ubcf8\ubb38\uc774\ubbf8\uc9c0", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY, width=7, anchor="w").pack(side="left")
        self.img_count_var = tk.StringVar(value="2")
        img_cb = ttk.Combobox(img_row, textvariable=self.img_count_var,
                              values=["0", "1", "2", "3", "4", "5"],
                              state="readonly", width=5, font=("Malgun Gothic", 9))
        img_cb.pack(side="left", padx=(4, 4))
        tk.Label(img_row, text="\uac1c", font=("Malgun Gothic", 9),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(side="left")

        tk.Frame(left_card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 8))


        # 글 생성 시작 버튼
        gen_btn = self.make_button(left_card, "🚀 글 생성 시작", self._open_generate_preview_popup, color=ACCENT)
        gen_btn.pack(fill="x", pady=(0, 2))

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

        # 오른쪽 하단: 검색량 카드형 분석
        tk.Label(right_card, text="📊 검색량 분석",
                 font=("Malgun Gothic", 11, "bold"), bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 6))
        tk.Frame(right_card, bg="#2e2e48", height=1).pack(fill="x", pady=(0, 6))

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

        # 카테고리 선택됐고 키워드 비어있으면 → 시드 키워드 중 랜덤으로 입력
        selected_cat = self.selected_category.get()
        if (not keywords or keywords == PLACEHOLDER) and selected_cat != "전체":
            seeds = next((s for n, s in self._categories_data if n == selected_cat and s), None)
            if seeds:
                import random
                keywords = random.choice(seeds)
                self.kw_entry.delete(0, tk.END)
                self.kw_entry.insert(0, keywords)
                self.kw_entry.config(fg=TEXT_WHITE)

        if not keywords or keywords == PLACEHOLDER:
            messagebox.showwarning("알림", "키워드를 입력해주세요!")
            return

        self.kw_log.config(text=f"⏳ [{selected_cat}] {keywords} 조회 중...", fg=WARNING)
        for w in self.kw_result_frame.winfo_children():
            w.destroy()
        for w in self.kw_recommend_frame.winfo_children():
            w.destroy()
        for w in self.kw_suggest_frame.winfo_children():
            w.destroy()
        # 연관검색어 (네이버 자동완성) + 검색량 분석 동시 실행
        threading.Thread(target=self._run_suggest, args=(keywords,), daemon=True).start()
        threading.Thread(target=self._run_keyword_analysis, args=(keywords,), daemon=True).start()

    def _update_selected_count(self):
        """선택된 연관검색어 개수 표시 및 스케줄 미리보기 갱신 + 검색량 조회"""
        count = sum(1 for var, _ in self.kw_check_vars if var.get())
        if count > 0:
            self.kw_selected_lbl.config(text=f"{count}개 선택됨")
        else:
            self.kw_selected_lbl.config(text="")
        self._update_schedule_preview()
        # 선택된 키워드 검색량 조회
        selected_kws = [kw for var, kw in self.kw_check_vars if var.get()]
        if selected_kws:
            threading.Thread(target=self._run_keyword_analysis_selected,
                           args=(selected_kws,), daemon=True).start()

    def _on_publish_mode_change(self):
        """발행 방식 변경시 예약 옵션 표시/숨김"""
        if self.publish_mode.get() == "scheduled":
            self.kw_schedule_frame.pack(fill="x")
            self._update_schedule_preview()
        else:
            self.kw_schedule_frame.pack_forget()

    def _update_schedule_preview(self):
        """예약 발행 스케줄 미리보기 업데이트"""
        if self.publish_mode.get() != "scheduled":
            return
        selected = [kw for var, kw in self.kw_check_vars if var.get()]
        if not selected:
            self.kw_schedule_preview.config(text="키워드를 선택하면 스케줄이 표시됩니다.")
            return
        try:
            date_str = self.sched_date_var.get().strip()
            hour_str = self.sched_hour_var.get().strip().zfill(2)
            min_str = self.sched_min_var.get().strip().zfill(2)
            interval_str = self.sched_interval_var.get()
            interval_h = int(interval_str.replace("시간", ""))
            start_dt = datetime.strptime(f"{date_str} {hour_str}:{min_str}", "%Y-%m-%d %H:%M")
            lines = []
            for i, kw in enumerate(selected[:5]):
                dt = start_dt + timedelta(hours=interval_h * i)
                lines.append(f"{dt.strftime('%m/%d %H:%M')} → {kw}")
            if len(selected) > 5:
                lines.append(f"... 외 {len(selected)-5}개")
            self.kw_schedule_preview.config(text="\n".join(lines))
        except Exception:
            self.kw_schedule_preview.config(text="날짜/시간 형식을 확인해주세요.")

    def _toggle_suggest_kw(self, keyword):
        """연관검색어 체크박스 토글 (검색량 카드에서 호출)"""
        for var, kw in self.kw_check_vars:
            if kw == keyword:
                var.set(not var.get())
                self._update_selected_count()
                return

    def _run_suggest(self, keyword):
        """네이버 자동완성 연관검색어 조회 (무료, 키 불필요) - 체크박스 방식"""
        try:
            import requests
            url = "https://ac.search.naver.com/nx/ac"
            params = {"q": keyword, "q_enc": "UTF-8", "st": "11", "frm": "nv", "r_format": "json", "r_enc": "UTF-8"}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            data = resp.json()
            suggests = []
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
                self.kw_check_vars.clear()
                self.kw_selected_lbl.config(text="")
                if not suggests:
                    tk.Label(self.kw_suggest_frame, text="연관검색어 없음",
                             font=("Malgun Gothic", 10), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
                    return
                for idx, sug in enumerate(suggests, 1):
                    var = tk.BooleanVar(value=False)
                    self.kw_check_vars.append((var, sug))
                    row = tk.Frame(self.kw_suggest_frame, bg=BG_CARD)
                    row.pack(fill="x", pady=1)
                    row.bind("<MouseWheel>", self._sug_scroll_fn)

                    cb = tk.Checkbutton(row, variable=var, text="",
                                        bg=BG_CARD, fg=TEXT_WHITE,
                                        selectcolor=BG_DARK, activebackground=BG_CARD,
                                        command=self._update_selected_count)
                    cb.pack(side="left")
                    cb.bind("<MouseWheel>", self._sug_scroll_fn)

                    num_lbl = tk.Label(row, text=str(idx), font=("Malgun Gothic", 9),
                                       bg=BG_CARD, fg=TEXT_GRAY, width=3, anchor="e")
                    num_lbl.pack(side="left", padx=(0, 4))
                    num_lbl.bind("<MouseWheel>", self._sug_scroll_fn)

                    sug_lbl = tk.Label(row, text=sug, font=("Malgun Gothic", 9),
                                       bg=BG_CARD, fg=TEXT_WHITE, anchor="w")
                    sug_lbl.pack(side="left", fill="x")
                    sug_lbl.bind("<MouseWheel>", self._sug_scroll_fn)

                    def on_lbl_click(v=var):
                        v.set(not v.get())
                        self._update_selected_count()
                    sug_lbl.bind("<Button-1>", lambda e, v=var: on_lbl_click(v))
                    num_lbl.bind("<Button-1>", lambda e, v=var: on_lbl_click(v))

                self._suggest_canvas.after(50, lambda: self._suggest_canvas.configure(
                    scrollregion=self._suggest_canvas.bbox("all")))

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

            kw_list = [k.strip() for k in keywords_str.split(",")]

            def make_headers():
                ts = str(round(time.time() * 1000))
                sign = f"{ts}.GET./keywordstool"
                hm = hmac.new(NAVER_AD_SECRET_KEY.encode(), sign.encode("utf-8"), hashlib.sha256)
                sig = base64.b64encode(hm.digest()).decode("utf-8")
                return {
                    "X-Timestamp": ts,
                    "X-API-KEY": NAVER_AD_ACCESS_LICENSE,
                    "X-CUSTOMER": str(NAVER_AD_CUSTOMER_ID),
                    "X-Signature": sig,
                }

            import requests
            # 5개씩 나눠서 호출 (API 제한)
            items = []
            for i in range(0, len(kw_list), 5):
                chunk = kw_list[i:i+5]
                resp = requests.get(
                    "https://api.naver.com/keywordstool",
                    headers=make_headers(),
                    params={"hintKeywords": ",".join(chunk), "showDetail": "1"}
                )
                items += resp.json().get("keywordList", [])
                if i + 5 < len(kw_list):
                    time.sleep(0.3)

            # 결과 없으면 공백 제거 버전으로 재시도
            if not items and " " in keywords_str:
                kw_list2 = [k.replace(" ", "") for k in kw_list]
                for i in range(0, len(kw_list2), 5):
                    chunk = kw_list2[i:i+5]
                    resp2 = requests.get(
                        "https://api.naver.com/keywordstool",
                        headers=make_headers(),
                        params={"hintKeywords": ",".join(chunk), "showDetail": "1"}
                    )
                    items += resp2.json().get("keywordList", [])
                if items:
                    new_kw = keywords_str.replace(" ", "")
                    self.root.after(0, lambda: (
                        self.kw_entry.delete(0, tk.END),
                        self.kw_entry.insert(0, new_kw),
                        self.kw_entry.config(fg=TEXT_WHITE)
                    ))

            def parse_cnt(v):
                if isinstance(v, int): return v
                if isinstance(v, str):
                    s = v.strip().replace(",", "").replace("<", "").replace(" ", "")
                    try: return int(s)
                    except: return 0
                return 0

            def get_total(item):
                return parse_cnt(item.get("monthlyPcQcCnt", 0)) + parse_cnt(item.get("monthlyMobileQcCnt", 0))

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

                # 검색량 카드형 렌더링
                for idx, item in enumerate(display_items, 1):
                    kw = item.get("relKeyword", "")
                    pc = item.get("monthlyPcQcCnt", 0)
                    mobile = item.get("monthlyMobileQcCnt", 0)
                    comp = item.get("compIdx", "-")
                    total = get_total(item)
                    blog_cnt = item.get("plAvgDepth", 0)

                    if comp == "낮음":
                        comp_color = SUCCESS; comp_bg = "#0d2a1a"
                    elif comp == "중간":
                        comp_color = WARNING; comp_bg = "#2a1f00"
                    else:
                        comp_color = DANGER; comp_bg = "#2a0d0d"
                    blog_color = SUCCESS if isinstance(blog_cnt, (int,float)) and 0 < blog_cnt < 100 else \
                                 WARNING if isinstance(blog_cnt, (int,float)) and blog_cnt < 500 else TEXT_GRAY
                    card_bg = "#252538" if idx % 2 == 0 else "#1e1e2e"

                    card = tk.Frame(self.kw_result_frame, bg=card_bg, padx=10, pady=6,
                                    relief="flat", bd=0)
                    card.pack(fill="x", pady=1)

                    # 첫 줄: 키워드명
                    kw_row = tk.Frame(card, bg=card_bg)
                    kw_row.pack(fill="x")
                    kw_lbl = tk.Label(kw_row, text=f"키워드: {kw}",
                                      font=("Malgun Gothic", 10, "bold"),
                                      bg=card_bg, fg=TEXT_WHITE, anchor="w", cursor="hand2")
                    kw_lbl.pack(side="left")

                    # 두 번째 줄: 통계
                    pc_str = f"{pc:,}" if isinstance(pc, int) else "-"
                    mob_str = f"{mobile:,}" if isinstance(mobile, int) else "-"
                    total_str = f"{total:,}"
                    blog_str = f"{int(blog_cnt):,}" if isinstance(blog_cnt, (int,float)) and blog_cnt else "-"

                    stat_row = tk.Frame(card, bg=card_bg)
                    stat_row.pack(fill="x", pady=(2, 0))

                    tk.Label(stat_row, text=f"PC: {pc_str}",
                             font=("Malgun Gothic", 9), bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=f"모바일: {mob_str}",
                             font=("Malgun Gothic", 9), bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=f"합계: {total_str}",
                             font=("Malgun Gothic", 9, "bold"), bg=card_bg, fg=TEXT_WHITE).pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    # 경쟁강도 배지
                    comp_badge = tk.Label(stat_row, text=f"경쟁강도: {comp}",
                                          font=("Malgun Gothic", 8, "bold"),
                                          bg=comp_bg, fg=comp_color, padx=5, pady=1)
                    comp_badge.pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=f"블로그발행수: {blog_str}",
                             font=("Malgun Gothic", 9), bg=card_bg, fg=blog_color).pack(side="left")

                    # 클릭 시 연관검색어 체크박스 토글
                    def _on_card_click(k=kw):
                        self._toggle_suggest_kw(k)
                    for widget in [card, kw_lbl, kw_row, stat_row]:
                        widget.bind("<Button-1>", lambda e, k=kw: _on_card_click(k))
                    for child in stat_row.winfo_children():
                        child.bind("<Button-1>", lambda e, k=kw: _on_card_click(k))

                    self._bind_kw_scroll_fn(card)

                self.kw_log.config(text=f"✅ 전체 {len(items)}개 중 {len(display_items)}개 표시", fg=SUCCESS)

            self.root.after(0, update_ui)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.root.after(0, lambda: self.kw_log.config(text=f"❌ 오류: {str(e)[:200]}", fg=DANGER))

    def _run_keyword_analysis_selected(self, selected_kws: list):
        """선택된 체크박스 키워드를 각각 1개씩 API 조회 → 정확한 검색량 표시"""
        try:
            import hashlib, hmac, base64, time, requests

            try:
                from config import NAVER_AD_CUSTOMER_ID, NAVER_AD_ACCESS_LICENSE, NAVER_AD_SECRET_KEY
            except:
                NAVER_AD_CUSTOMER_ID = os.environ.get("NAVER_AD_CUSTOMER_ID", "")
                NAVER_AD_ACCESS_LICENSE = os.environ.get("NAVER_AD_ACCESS_LICENSE", "")
                NAVER_AD_SECRET_KEY = os.environ.get("NAVER_AD_SECRET_KEY", "")

            def make_headers():
                ts = str(round(time.time() * 1000))
                sign = f"{ts}.GET./keywordstool"
                hm = hmac.new(NAVER_AD_SECRET_KEY.encode(), sign.encode("utf-8"), hashlib.sha256)
                sig = base64.b64encode(hm.digest()).decode("utf-8")
                return {
                    "X-Timestamp": ts,
                    "X-API-KEY": NAVER_AD_ACCESS_LICENSE,
                    "X-CUSTOMER": str(NAVER_AD_CUSTOMER_ID),
                    "X-Signature": sig,
                }

            def norm(s): return s.replace(" ", "").lower()

            def parse_cnt(v):
                if isinstance(v, int): return v
                if isinstance(v, str):
                    s = v.strip().replace(",", "").replace("<", "").replace(" ", "")
                    try: return int(s)
                    except: return 0
                return 0

            # 각 키워드를 개별 호출 → 공백제거 버전도 병행 조회
            result_items = []
            for kw in selected_kws:
                kw_nospace = kw.replace(" ", "")

                def query_api(hint):
                    r = requests.get(
                        "https://api.naver.com/keywordstool",
                        headers=make_headers(),
                        params={"hintKeywords": hint, "showDetail": "1"}
                    )
                    return r.json().get("keywordList", [])

                items = query_api(kw)

                # 공백 없는 버전으로도 조회해서 더 많은 검색량 결과 선택
                items_nospace = query_api(kw_nospace) if kw != kw_nospace else []
                all_candidates = items + items_nospace

                def best_match(candidates):
                    # 정확 일치 우선 (공백 무시)
                    exact = next((i for i in candidates if norm(i.get("relKeyword","")) == norm(kw)), None)
                    if exact: return exact
                    # 검색량 가장 높은 것
                    if candidates:
                        return max(candidates, key=lambda i: parse_cnt(i.get("monthlyPcQcCnt",0)) + parse_cnt(i.get("monthlyMobileQcCnt",0)))
                    return None

                matched = best_match(all_candidates)

                if matched:
                    matched = dict(matched)
                    matched["relKeyword"] = kw  # 표시용은 원래 키워드
                    result_items.append(matched)
                else:
                    # API 결과 없으면 0으로 카드 생성
                    result_items.append({
                        "relKeyword": kw,
                        "monthlyPcQcCnt": 0,
                        "monthlyMobileQcCnt": 0,
                        "compIdx": "-",
                        "plAvgDepth": 0,
                    })

                if len(selected_kws) > 1:
                    time.sleep(0.2)  # API 제한 방지

            def parse_cnt(v):
                """네이버 API 반환값 파싱: int or '< 10' or 문자열"""
                if isinstance(v, int): return v
                if isinstance(v, str):
                    s = v.strip().replace(",", "").replace("<", "").replace(" ", "")
                    try: return int(s)
                    except: return 0
                return 0

            def fmt_cnt(v):
                """표시용: '< 10' 문자열은 그대로, int는 쉼표"""
                if isinstance(v, str) and "<" in v: return v.strip()
                n = parse_cnt(v)
                return f"{n:,}" if n else "0"

            def get_total(item):
                return parse_cnt(item.get("monthlyPcQcCnt", 0)) + parse_cnt(item.get("monthlyMobileQcCnt", 0))

            matched_sorted = sorted(result_items, key=get_total, reverse=True)

            def update_ui():
                for w in self.kw_result_frame.winfo_children():
                    w.destroy()

                if not matched_sorted:
                    self.kw_log.config(text="선택 키워드 검색량 없음", fg=DANGER)
                    return

                for idx, item in enumerate(matched_sorted, 1):
                    kw = item.get("relKeyword", "")
                    pc = item.get("monthlyPcQcCnt", 0)
                    mobile = item.get("monthlyMobileQcCnt", 0)
                    comp = item.get("compIdx", "-")
                    total = get_total(item)
                    blog_cnt = item.get("plAvgDepth", 0)

                    if comp == "낮음":
                        comp_color = SUCCESS; comp_bg = "#0d2a1a"
                    elif comp == "중간":
                        comp_color = WARNING; comp_bg = "#2a1f00"
                    else:
                        comp_color = DANGER; comp_bg = "#2a0d0d"
                    blog_color = SUCCESS if isinstance(blog_cnt, (int, float)) and 0 < blog_cnt < 100 else \
                                 WARNING if isinstance(blog_cnt, (int, float)) and blog_cnt < 500 else TEXT_GRAY
                    card_bg = "#252538" if idx % 2 == 0 else "#1e1e2e"

                    card = tk.Frame(self.kw_result_frame, bg=card_bg, padx=10, pady=6)
                    card.pack(fill="x", pady=1)

                    kw_lbl = tk.Label(card, text=f"키워드: {kw}",
                                      font=("Malgun Gothic", 10, "bold"),
                                      bg=card_bg, fg=TEXT_WHITE, anchor="w")
                    kw_lbl.pack(fill="x")

                    pc_str = fmt_cnt(pc)
                    mob_str = fmt_cnt(mobile)
                    total_str = f"{total:,}" if total else "< 10"
                    blog_str = f"{int(blog_cnt):,}" if isinstance(blog_cnt, (int, float)) and blog_cnt else "-"

                    stat_row = tk.Frame(card, bg=card_bg)
                    stat_row.pack(fill="x", pady=(2, 0))

                    tk.Label(stat_row, text=f"PC: {pc_str}", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=f"모바일: {mob_str}", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=f"합계: {total_str}", font=("Malgun Gothic", 9, "bold"),
                             bg=card_bg, fg=TEXT_WHITE).pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=f"경쟁강도: {comp}", font=("Malgun Gothic", 8, "bold"),
                             bg=comp_bg, fg=comp_color, padx=5, pady=1).pack(side="left")
                    tk.Label(stat_row, text=" | ", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=TEXT_GRAY).pack(side="left")
                    tk.Label(stat_row, text=f"블로그발행수: {blog_str}", font=("Malgun Gothic", 9),
                             bg=card_bg, fg=blog_color).pack(side="left")

                    self._bind_kw_scroll_fn(card)

                self.kw_log.config(text=f"✅ 선택 키워드 {len(matched_sorted)}개 검색량 표시", fg=SUCCESS)

            self.root.after(0, update_ui)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.root.after(0, lambda: self.kw_log.config(text=f"❌ 오류: {str(e)[:200]}", fg=DANGER))

    # ================================================
    # 글 생성 + 미리보기 팝업
    # ================================================
    def _open_generate_preview_popup(self):
        """선택된 연관검색어로 글 생성 + 미리보기 팝업 열기"""
        selected_kws = [kw for var, kw in self.kw_check_vars if var.get()]
        if not selected_kws:
            messagebox.showwarning("알림", "연관검색어를 하나 이상 선택해주세요!")
            return

        popup = tk.Toplevel(self.root)
        popup.title("글 생성 미리보기")
        popup.geometry("900x700")
        popup.configure(bg=BG_DARK)
        popup.grab_set()

        self._popup_kws = selected_kws
        self._popup_idx = 0
        self._popup_contents = {}   # {idx: (title, content)}

        # ── 레이아웃 ──
        popup_body = tk.Frame(popup, bg=BG_DARK)
        popup_body.pack(fill="both", expand=True, padx=15, pady=15)
        popup_body.columnconfigure(1, weight=1)
        popup_body.rowconfigure(0, weight=1)

        # 왼쪽: 키워드 목록
        left = tk.Frame(popup_body, bg=BG_CARD, padx=10, pady=10, width=200)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text="키워드 목록", font=("Malgun Gothic", 10, "bold"),
                 bg=BG_CARD, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 8))
        self._popup_kw_labels = []
        for i, kw in enumerate(selected_kws):
            lbl = tk.Label(left, text=f"{i+1}. {kw}",
                           font=("Malgun Gothic", 9), bg=BG_CARD, fg=TEXT_GRAY,
                           anchor="w", wraplength=160, justify="left")
            lbl.pack(fill="x", pady=2)
            self._popup_kw_labels.append(lbl)

        # 오른쪽: 편집 영역
        right = tk.Frame(popup_body, bg=BG_DARK)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # 제목
        title_row = tk.Frame(right, bg=BG_DARK)
        title_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(title_row, text="제목", font=("Malgun Gothic", 10, "bold"),
                 bg=BG_DARK, fg=TEXT_GRAY, width=5).pack(side="left")
        self._popup_title_var = tk.StringVar()
        title_entry = tk.Entry(title_row, textvariable=self._popup_title_var,
                               font=("Malgun Gothic", 11), bg="#252540", fg=TEXT_WHITE,
                               insertbackground=TEXT_WHITE, relief="flat")
        title_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # 본문
        self._popup_body_text = scrolledtext.ScrolledText(
            right, font=("Malgun Gothic", 10), bg="#252540", fg=TEXT_WHITE,
            insertbackground=TEXT_WHITE, relief="flat", wrap="word")
        self._popup_body_text.grid(row=1, column=0, sticky="nsew")

        # 상태 레이블
        self._popup_status = tk.Label(right, text="", font=("Malgun Gothic", 9),
                                      bg=BG_DARK, fg=TEXT_GRAY)
        self._popup_status.grid(row=2, column=0, sticky="w", pady=(4, 0))

        # 하단 버튼
        btn_row = tk.Frame(popup, bg=BG_DARK)
        btn_row.pack(fill="x", padx=15, pady=(0, 15))

        def go_prev():
            if self._popup_idx > 0:
                self._save_popup_current()
                self._popup_idx -= 1
                self._load_popup_content()

        def go_next():
            if self._popup_idx < len(self._popup_kws) - 1:
                self._save_popup_current()
                self._popup_idx += 1
                self._load_popup_content()

        def publish_current():
            self._save_popup_current()
            idx = self._popup_idx
            title, body = self._popup_contents.get(idx, ("", ""))
            if not title or not body:
                messagebox.showwarning("알림", "제목과 본문이 비어 있습니다.", parent=popup)
                return
            self._popup_status.config(text="⏳ 이미지 생성 및 발행 중...", fg=WARNING)
            popup.update_idletasks()

            def do_publish():
                try:
                    import blog_automation
                    kw_pub = self._popup_kws[idx]

                    use_thumb = getattr(self, 'thumb_var', None)
                    use_thumb = (use_thumb.get() == "있음") if use_thumb else True
                    n_img = getattr(self, 'img_count_var', None)
                    n_img = int(n_img.get()) if n_img else 2

                    final_body = body

                    # 이미지 생성
                    if n_img > 0 or use_thumb:
                        from blog_automation import generate_images_with_vertex, generate_thumbnail_with_vertex, insert_images_into_content
                        images = generate_images_with_vertex(kw_pub, count=n_img) if n_img > 0 else []
                        thumbnail = generate_thumbnail_with_vertex(kw_pub, title) if use_thumb else None
                        all_images = ([thumbnail] if thumbnail else []) + images
                        if all_images:
                            final_body = insert_images_into_content(final_body, all_images, kw_pub)

                    result = blog_automation.publish_to_blogger(title, final_body)
                    self.root.after(0, lambda: self._popup_status.config(
                        text=f"✅ 발행 완료: {result.get('url','') if isinstance(result,dict) else result}", fg=SUCCESS))
                except Exception as ex:
                    import traceback; print(traceback.format_exc())
                    self.root.after(0, lambda: self._popup_status.config(
                        text=f"❌ 발행 오류: {ex}", fg=DANGER))

            threading.Thread(target=do_publish, daemon=True).start()

        self.make_button(btn_row, "◀ 이전", go_prev, color="#252540").pack(side="left", padx=(0, 6))
        self.make_button(btn_row, "▶ 다음", go_next, color="#252540").pack(side="left", padx=(0, 6))
        self.make_button(btn_row, "✅ 이 글 발행", publish_current, color=SUCCESS).pack(side="left")

        self._popup_ref = popup
        self._popup_title_entry = title_entry

        # 첫 번째 키워드 글 자동 생성
        self._highlight_popup_kw(0)
        threading.Thread(target=self._generate_and_show, args=(0,), daemon=True).start()

    def _save_popup_current(self):
        """현재 팝업 편집 내용 저장"""
        idx = self._popup_idx
        title = self._popup_title_var.get()
        content = self._popup_body_text.get("1.0", "end-1c")
        self._popup_contents[idx] = (title, content)

    def _load_popup_content(self):
        """팝업에서 idx에 해당하는 내용 불러오기"""
        idx = self._popup_idx
        self._highlight_popup_kw(idx)
        if idx in self._popup_contents:
            title, content = self._popup_contents[idx]
            self._popup_title_var.set(title)
            self._popup_body_text.delete("1.0", "end")
            self._popup_body_text.insert("1.0", content)
            self._popup_status.config(text="저장된 내용을 불러왔습니다.", fg=TEXT_GRAY)
        else:
            self._popup_title_var.set("")
            self._popup_body_text.delete("1.0", "end")
            self._popup_status.config(text="⏳ 글 생성 중...", fg=WARNING)
            threading.Thread(target=self._generate_and_show, args=(idx,), daemon=True).start()

    def _highlight_popup_kw(self, idx):
        """팝업 키워드 목록에서 현재 키워드 하이라이트"""
        for i, lbl in enumerate(self._popup_kw_labels):
            if i == idx:
                lbl.config(fg=ACCENT, font=("Malgun Gothic", 9, "bold"))
            else:
                lbl.config(fg=TEXT_GRAY, font=("Malgun Gothic", 9))

    def _generate_and_show(self, idx):
        """blog_automation.generate_blog_post() 호출 후 팝업에 표시"""
        kw = self._popup_kws[idx]
        try:
            import blog_automation

            # 이미지 설정 읽기
            use_thumbnail = getattr(self, 'thumb_var', None)
            use_thumbnail = (use_thumbnail.get() == "있음") if use_thumbnail else True
            img_count = getattr(self, 'img_count_var', None)
            img_count = int(img_count.get()) if img_count else 2

            result = blog_automation.generate_blog_post(kw)
            # generate_blog_post가 dict 또는 (title, content) 반환 가능성 모두 처리
            if isinstance(result, dict):
                title = result.get("title", kw)
                content = result.get("content", "")
            elif isinstance(result, (list, tuple)) and len(result) >= 2:
                title, content = result[0], result[1]
            else:
                title = kw
                content = str(result) if result else ""

            self._popup_contents[idx] = (title, content)

            def update_ui():
                if self._popup_idx == idx:
                    self._popup_title_var.set(title)
                    self._popup_body_text.delete("1.0", "end")
                    self._popup_body_text.insert("1.0", content)
                    self._popup_status.config(text=f"✅ [{kw}] 글 생성 완료", fg=SUCCESS)
            self.root.after(0, update_ui)
        except Exception as ex:
            import traceback
            print(traceback.format_exc())
            def show_err():
                if self._popup_idx == idx:
                    self._popup_status.config(text=f"❌ 글 생성 오류: {ex}", fg=DANGER)
            self.root.after(0, show_err)

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
                c.create_line(x1, line_y, x2, line_y, fill=SUCCESS, width=2)
            elif i == self.current_step:
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
            self.log("\uae00 \uc0dd\uc131 \uc911...")
            title, content_body = generate_blog_post(keyword)
            self.log(f"\uc81c\ubaa9: {title}")

            self.set_step(1)
            self.log("SEO \uba54\ud0c0\ub370\uc774\ud130 \uc0dd\uc131 \uc911...")
            desc, keywords_meta = generate_seo_metadata(keyword, title, content_body)
            content_body = inject_seo_metadata(content_body, title, desc, keywords_meta, keyword)

            self.set_step(2)
            self.log("\uc774\ubbf8\uc9c0 \uc0dd\uc131 \uc911...")
            images = generate_images_with_vertex(keyword, count=3)
            thumbnail = generate_thumbnail_with_vertex(keyword, title)

            all_images = ([thumbnail] if thumbnail else []) + images
            if all_images:
                content_body = insert_images_into_content(content_body, all_images, keyword)

            self.set_step(3)
            self.log("\ube14\ub85c\uadf8\uc2a4\ud32f \ubc1c\ud589 \uc911...")
            result = publish_to_blogger(title, content_body)
            post_url = result.get("url") if result else None

            if post_url:
                self._anim_running = False
                self.set_step(4)
                self.log(f"\u2705 \ubc1c\ud589 \uc644\ub8cc! \u2192 {post_url}")

                if self.toggle_naver.get():
                    self.log("\ub124\uc774\ubc84 \ubc31\ub9c1\ud06c\uc6a9 \uae00 \uc0dd\uc131 \uc911...")
                    from naver_post_generator import generate_naver_post
                    naver_result = generate_naver_post(keyword, title, content_body, all_images, post_url)
                    self.log(f"\u2705 \ub124\uc774\ubc84\uc6a9 \ud30c\uc77c \uc800\uc7a5: {naver_result['html_path']}")
            else:
                self.log("\u274c \ubc1c\ud589 \uc2e4\ud328")
        except Exception as e:
            self.log(f"\u274c \uc624\ub958: {e}")

    # ================================================
    # \uc774\uba54\uc77c \ubc1c\uc1a1 \ud398\uc774\uc9c0
    # ================================================
    def build_email(self):
        frame = tk.Frame(self.main_area, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(frame, text="\uc774\uba54\uc77c \ubc1c\uc1a1", font=("Malgun Gothic", 18, "bold"),
                 bg=BG_DARK, fg=TEXT_WHITE).pack(anchor="w", pady=(0, 15))

        kw_card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
        kw_card.pack(fill="x", pady=(0, 12))
        tk.Label(kw_card, text="\ubc1c\uc1a1\ud560 \ud0a4\uc6cc\ub4dc \uc120\ud0dd", font=("Malgun Gothic", 11, "bold"),
                 bg=BG_CARD, fg=ACCENT).pack(anchor="w", pady=(0, 10))

        self.email_check_vars = []
        schedule_items = []
        try:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "today_keywords.json")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            schedule_items = data.get("schedule", [])
        except:
            schedule_items = []

        if not schedule_items:
            tk.Label(kw_card, text="today_keywords.json \uc5c6\uc74c - \uba3c\uc800 \ud0a4\uc6cc\ub4dc \uc774\uba54\uc77c\uc744 \ubc1c\uc1a1\ud558\uc138\uc694",
                     font=("Malgun Gothic", 10), bg=BG_CARD, fg=DANGER).pack(anchor="w")
        else:
            all_var = tk.BooleanVar(value=True)
            def toggle_all():
                for v in self.email_check_vars:
                    v.set(all_var.get())
            all_row = tk.Frame(kw_card, bg=BG_CARD)
            all_row.pack(fill="x", pady=(0, 6))
            tk.Checkbutton(all_row, variable=all_var, command=toggle_all,
                           bg=BG_CARD, fg=TEXT_GRAY, activebackground=BG_CARD,
                           selectcolor=BG_ITEM, font=("Malgun Gothic", 10),
                           text="\uc804\uccb4 \uc120\ud0dd").pack(side="left")
            tk.Frame(kw_card, bg="#252540", height=1).pack(fill="x", pady=(0, 8))

            for item in schedule_items:
                var = tk.BooleanVar(value=True)
                self.email_check_vars.append(var)
                row = tk.Frame(kw_card, bg=BG_ITEM, padx=10, pady=8)
                row.pack(fill="x", pady=3)
                cb = tk.Checkbutton(row, variable=var, bg=BG_ITEM,
                                    activebackground=BG_ITEM, selectcolor="#ffffff")
                cb.pack(side="left")
                time_lbl = tk.Label(row, text=item.get("time", ""),
                                    font=("Malgun Gothic", 10, "bold"),
                                    bg=BG_ITEM, fg=TEXT_WHITE, padx=8, pady=2)
                time_lbl.pack(side="left", padx=(4, 8))
                kw_text = item.get("keyword", "")
                tk.Label(row, text=kw_text[:40] + "..." if len(kw_text) > 40 else kw_text,
                         font=("Malgun Gothic", 10), bg=BG_ITEM, fg=TEXT_WHITE).pack(side="left")
                if item.get("published"):
                    tk.Label(row, text="\u2705 \ubc1c\ud589\uc644\ub8cc", font=("Malgun Gothic", 9),
                             bg=BG_ITEM, fg=SUCCESS).pack(side="right", padx=4)
                else:
                    tk.Label(row, text="\u23f3 \ub300\uae30\uc911", font=("Malgun Gothic", 9),
                             bg=BG_ITEM, fg=TEXT_GRAY).pack(side="right", padx=4)

        rec_card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
        rec_card.pack(fill="x", pady=(0, 12))
        tk.Label(rec_card, text="\uc218\uc2e0 \uc774\uba54\uc77c", font=("Malgun Gothic", 11, "bold"),
                 bg=BG_CARD, fg=ACCENT).pack(anchor="w", pady=(0, 8))
        rec_row = tk.Frame(rec_card, bg=BG_CARD)
        rec_row.pack(fill="x")
        self.email_recipient_var = tk.StringVar(value="duatkdtn@gmail.com")
        tk.Entry(rec_row, textvariable=self.email_recipient_var,
                 font=("Malgun Gothic", 11), bg=BG_ITEM, fg=TEXT_WHITE,
                 insertbackground=TEXT_WHITE, relief="flat", bd=0).pack(fill="x", ipady=6, padx=2)

        log_card = tk.Frame(frame, bg=BG_CARD, padx=20, pady=15)
        log_card.pack(fill="x", pady=(0, 12))
        tk.Label(log_card, text="\ubc1c\uc1a1 \ub85c\uadf8", font=("Malgun Gothic", 11, "bold"),
                 bg=BG_CARD, fg=ACCENT).pack(anchor="w", pady=(0, 8))
        self.email_log = tk.Text(log_card, height=5, font=("Consolas", 10),
                                 bg="#0f0f1a", fg=SUCCESS, relief="flat",
                                 state="disabled", wrap="word")
        self.email_log.pack(fill="x")

        btn_row = tk.Frame(frame, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(4, 0))

        def send_selected():
            selected = [schedule_items[i] for i, v in enumerate(self.email_check_vars) if v.get()]
            if not selected:
                messagebox.showwarning("\uc54c\ub9bc", "\ubc1c\uc1a1\ud560 \ud0a4\uc6cc\ub4dc\ub97c \uc120\ud0dd\ud574\uc8fc\uc138\uc694.")
                return
            if not messagebox.askyesno("\ud655\uc778", f"\uc120\ud0dd\ud55c {len(selected)}\uac1c \ud0a4\uc6cc\ub4dc \uc774\uba54\uc77c\uc744 \ubc1c\uc1a1\ud560\uae4c\uc694?"):
                return
            threading.Thread(target=self._send_email_selected, args=(selected,), daemon=True).start()

        def send_keyword_email():
            if not messagebox.askyesno("\ud655\uc778", "\uc624\ub298\uc758 \ud0a4\uc6cc\ub4dc \ucd94\ucc9c \uc774\uba54\uc77c\uc744 \ubc1c\uc1a1\ud560\uae4c\uc694?"):
                return
            threading.Thread(target=self._run_keyword_email, daemon=True).start()

        tk.Button(btn_row, text="\ud0a4\uc6cc\ub4dc \ucd94\ucc9c \uc774\uba54\uc77c \ubc1c\uc1a1", font=("Malgun Gothic", 11),
                  bg=BG_ITEM, fg=ACCENT, relief="flat", bd=0, padx=16, pady=8,
                  cursor="hand2", command=send_keyword_email).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="\u26a1 \uc120\ud0dd \ud0a4\uc6cc\ub4dc \ubc14\ub85c\ubcf4\ub0b4\uae30", font=("Malgun Gothic", 11, "bold"),
                  bg=ACCENT, fg="white", relief="flat", bd=0, padx=16, pady=8,
                  cursor="hand2", command=send_selected).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="\U0001f550 \uc608\uc57d (\ucd94\ud6c4\uc9c0\uc6d0)", font=("Malgun Gothic", 10),
                  bg=BG_ITEM, fg=TEXT_GRAY, relief="flat", bd=0, padx=12, pady=8,
                  cursor="hand2", command=lambda: messagebox.showinfo("\uc54c\ub9bc", "\uc608\uc57d\ubcf4\ub0b4\uae30\ub294 \ucd94\ud6c4 \uc9c0\uc6d0 \uc608\uc815\uc785\ub2c8\ub2e4.")).pack(side="left")

    def _email_log(self, msg):
        try:
            self.email_log.config(state="normal")
            self.email_log.insert("end", msg + "\n")
            self.email_log.see("end")
            self.email_log.config(state="disabled")
        except:
            pass

    def _send_email_selected(self, selected_items):
        self._email_log("\U0001f4e7 \ub124\uc774\ubc84\uc6a9 \uc774\uba54\uc77c \ubc1c\uc1a1 \uc2dc\uc791...")
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD

            for item in selected_items:
                keyword = item.get("keyword", "")
                title = item.get("title", keyword)
                post_url = item.get("post_url", "")
                self._email_log(f"  \u2192 {keyword} \ubc1c\uc1a1 \uc911...")

                body = f"<html><body><h2>{title}</h2><p>\ud0a4\uc6cc\ub4dc: {keyword}</p></body></html>"
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"[\ud0a4\uc6cc\ub4dc \ubc1c\uc1a1] {title}"
                msg["From"] = GMAIL_ADDRESS
                msg["To"] = self.email_recipient_var.get()
                msg.attach(MIMEText(body, "html", "utf-8"))

                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                    server.sendmail(GMAIL_ADDRESS, self.email_recipient_var.get(), msg.as_string())
                self._email_log(f"  \u2705 {keyword} \uc644\ub8cc!")

            self._email_log("\U0001f389 \ubaa8\ub4e0 \uc774\uba54\uc77c \ubc1c\uc1a1 \uc644\ub8cc!")
        except Exception as e:
            self._email_log(f"\u274c \uc624\ub958: {e}")

    def run_keyword_email(self):
        if messagebox.askyesno("\ud655\uc778", "\ud0a4\uc6cc\ub4dc \uc774\uba54\uc77c\uc744 \uc9c0\uae08 \ubc1c\uc1a1\ud560\uae4c\uc694?"):
            self.show_page("publish")
            threading.Thread(target=self._run_keyword_email, daemon=True).start()

    def _run_keyword_email(self):
        self._email_log("\U0001f4e7 \ud0a4\uc6cc\ub4dc \ucd94\ucc9c \uc774\uba54\uc77c \ubc1c\uc1a1 \uc911...")
        try:
            import keyword_email
            keyword_email.main()
            self._email_log("\u2705 \ud0a4\uc6cc\ub4dc \uc774\uba54\uc77c \ubc1c\uc1a1 \uc644\ub8cc!")
        except Exception as e:
            self._email_log(f"\u274c \uc624\ub958: {e}")

    def save_settings(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = f.read()
            for key, entry in self.setting_entries.items():
                value = entry.get().strip()
                if value:
                    import re
                    pattern = rf'^({key}\s*=\s*)["\'\'].*?["\'\']'
                    replacement = f'{key} = "{value}"'
                    cfg = re.sub(pattern, replacement, cfg, flags=re.MULTILINE)
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(cfg)
            self.config_data = self.load_config()
            messagebox.showinfo("\uc644\ub8cc", "\uc124\uc815\uc774 \uc800\uc7a5\ub418\uc5c8\uc2b5\ub2c8\ub2e4!")
        except Exception as e:
            messagebox.showerror("\uc624\ub958", f"\uc800\uc7a5 \uc2e4\ud328: {e}")


# ================================================
# \uc2e4\ud589
# ================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = BlogMasterApp(root)
    root.mainloop()
