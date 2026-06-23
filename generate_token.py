# ================================================
# token.pickle 재발급 스크립트
# Indexing API 권한 포함한 새 토큰 발급
# ================================================

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# 필요한 API 권한 목록
SCOPES = [
    "https://www.googleapis.com/auth/blogger",         # 블로거 발행
    "https://www.googleapis.com/auth/indexing",        # 구글 색인 요청
]

def main():
    creds = None
    token_path = "token.pickle"
    client_secret_path = "client_secret.json"

    # client_secret.json 확인
    if not os.path.exists(client_secret_path):
        print("❌ client_secret.json 파일이 없습니다!")
        print("   현재 폴더에 client_secret.json을 넣어주세요.")
        return

    # 기존 토큰 확인
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        print("ℹ️  기존 token.pickle 발견 - 갱신 시도...")

    # 토큰이 없거나 만료된 경우 새로 발급
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 토큰 갱신 중...")
            creds.refresh(Request())
        else:
            print("🌐 브라우저에서 Google 계정 인증을 진행합니다...")
            print("   (블로거 계정으로 로그인하세요)\n")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # 새 토큰 저장
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        print(f"\n✅ token.pickle 저장 완료!")

    # 권한 확인
    print("\n📋 부여된 권한:")
    if hasattr(creds, 'scopes') and creds.scopes:
        for scope in creds.scopes:
            print(f"   ✓ {scope}")
    else:
        print("   (권한 정보 없음 - 정상일 수 있음)")

    print("\n🎉 완료! 이제 token.pickle을 GitHub Secret에 업로드하세요.")
    print("\n다음 명령어로 base64 변환:")
    print("   python -c \"import base64; print(base64.b64encode(open('token.pickle','rb').read()).decode())\"")

if __name__ == "__main__":
    main()
