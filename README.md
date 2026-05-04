# MISHARP Shortlink Maker

Render 배포용 FastAPI 단축링크 앱입니다.

## Render 설정

Build Command:
```
pip install -r requirements.txt
```

Start Command:
```
uvicorn app:app --host 0.0.0.0 --port $PORT
```

## 환경변수

Render > Settings > Environment 에서 아래 값을 추가하세요.

```
ADMIN_ID=misharp
ADMIN_PASSWORD=원하는비밀번호
SECRET_KEY=긴랜덤문자열
BASE_URL=https://msh.kr
```

BASE_URL은 도메인 연결 전에는 Render 주소를 넣어도 됩니다.
