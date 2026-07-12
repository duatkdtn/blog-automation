import os

base = os.path.dirname(os.path.abspath(__file__))

# ── 1. blog_automation.py: literal \n → 실제 줄바꿈 ──────────────────
ba_path = os.path.join(base, 'blog_automation.py')
with open(ba_path, 'r', encoding='utf-8') as f:
    ba = f.read()

old1 = "        hook = message.content[0].text.strip().strip('\"').strip(\"'\")\n        # 줄바꿈 없으면 공백 기준으로 분리\n        if '\\n' not in hook:"
new1 = "        hook = message.content[0].text.strip().strip('\"').strip(\"'\")\n        hook = hook.replace('\\\\n', '\\n')  # literal \\n → 실제 줄바꿈\n        # 줄바꿈 없으면 공백 기준으로 분리\n        if '\\n' not in hook:"

if old1 in ba:
    ba = ba.replace(old1, new1)
    with open(ba_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(ba)
    print("✅ blog_automation.py 썸네일 fix 완료")
else:
    print("❌ blog_automation.py 패턴 못 찾음")

# ── 2. auto_publish.py: Gmail/BLOG_ID config.py fallback ─────────────
ap_path = os.path.join(base, 'auto_publish.py')
with open(ap_path, 'r', encoding='utf-8') as f:
    ap = f.read()

# Gmail fallback
old2 = '''    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        print("⚠️ Gmail 환경변수 없음 - 이메일 전송 건너뜀")
        return'''

new2 = '''    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_password:
        try:
            import config as _cfg
            gmail_address = getattr(_cfg, 'GMAIL_ADDRESS', None)
            gmail_password = getattr(_cfg, 'GMAIL_APP_PASSWORD', None)
        except ImportError:
            pass

    if not gmail_address or not gmail_password:
        print("⚠️ Gmail 환경변수 없음 - 이메일 전송 건너뜀")
        return'''

if old2 in ap:
    ap = ap.replace(old2, new2)
    print("✅ auto_publish.py Gmail fallback 완료")
else:
    print("❌ auto_publish.py Gmail 패턴 못 찾음")

# BLOG_ID fallback
old3 = '    blog_id = os.environ.get("BLOG_ID")'
new3 = '''    blog_id = os.environ.get("BLOG_ID")
    if not blog_id:
        try:
            import config as _cfg2
            blog_id = getattr(_cfg2, 'BLOG_ID', None)
        except ImportError:
            pass'''

if old3 in ap:
    ap = ap.replace(old3, new3)
    print("✅ auto_publish.py BLOG_ID fallback 완료")
else:
    print("❌ auto_publish.py BLOG_ID 패턴 못 찾음")

with open(ap_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(ap)
print("✅ auto_publish.py 저장 완료")
