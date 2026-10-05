# ================================================
# 한발뉴스24 - 메인 실행 파일 (hanbal_main.py)
# 매일 새벽 5시 GitHub Actions에서 자동 실행
# ================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hanbal_collector import collect_news
from hanbal_ai import run_ai, print_summary
from hanbal_email import send_email, build_html

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT
from datetime import datetime
from zoneinfo import ZoneInfo
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import traceback

KST = ZoneInfo("Asia/Seoul")


def send_error_email(error_msg):
    """실패 시 에러 알림 메일 발송"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    subject = f"[한발뉴스24] ❌ {today} 실행 실패"
    body = f"""<html><body>
<h2 style="color:#e74c3c;">한발뉴스24 실행 실패</h2>
<p>날짜: {today}</p>
<pre style="background:#f8f9fa;padding:16px;border-radius:6px;font-size:13px;">{error_msg}</pre>
<p style="color:#999;font-size:12px;">GitHub Actions 로그를 확인해주세요.</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, EMAIL_RECIPIENT, msg.as_string())
        print("  에러 알림 메일 발송 완료")
    except Exception as e:
        print(f"  에러 알림 메일도 실패: {e}")


def main():
    today = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*50}")
    print(f"[한발뉴스24] 시작: {today} (KST)")
    print(f"{'='*50}\n")

    try:
        # 1단계: 뉴스 수집
        print("▶ 1단계: 뉴스 수집")
        collected = collect_news()
        total = sum(len(v) for v in collected["categories"].values())
        print(f"  총 {total}개 기사 수집 완료\n")

        if total == 0:
            raise Exception("수집된 기사가 0개입니다. Tavily API 또는 네트워크를 확인해주세요.")

        # 2단계: AI 분류
        print("▶ 2단계: AI 분류")
        result = run_ai(collected)

        if result is None:
            raise Exception("AI 분류 실패. Claude API 응답을 확인해주세요.")

        print_summary(result)

        # 결과 저장 (디버그용)
        today_str = datetime.now(KST).strftime("%Y%m%d")
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"hanbal_result_{today_str}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  결과 저장: {json_path}\n")

        # 3단계: 이메일 발송
        print("▶ 3단계: 이메일 발송")
        success = send_email(result)

        if not success:
            raise Exception("이메일 발송 실패. Gmail 설정을 확인해주세요.")

        print(f"\n{'='*50}")
        print(f"[한발뉴스24] 완료! ✅")
        print(f"{'='*50}\n")

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"\n❌ 오류 발생:\n{error_msg}")
        send_error_email(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
