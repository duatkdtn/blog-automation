import pickle, os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.pickle")
with open(path, 'rb') as f:
    creds = pickle.load(f)

print("=" * 60)
print("아래 값을 복사해서 GitHub Secret에 저장하세요")
print("=" * 60)
print(creds.refresh_token)
print("=" * 60)
input("\n엔터를 누르면 창이 닫힙니다...")
