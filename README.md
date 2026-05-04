# MISHARP Shortlink Operational Version

미샵 운영용 단축링크 서버입니다.

## 주요 기능
- 관리자 로그인
- 모든 http/https URL 단축
- 랜덤 3자리 자동 코드
- 001, 002, 003 순차 코드
- 직접 코드 입력
- SQLite DB 저장
- 클릭수 기록
- 클릭 로그 확인
- 링크 중지/재사용
- 링크 삭제
- Render 배포 지원

## Render 설정

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

## Render 환경변수

반드시 Render > Settings > Environment 에서 설정하세요.

```text
ADMIN_ID=misharp
ADMIN_PASSWORD=원하는비밀번호
SECRET_KEY=긴랜덤문자열
```

## 주의
Render 무료 플랜은 서버가 잠들 수 있습니다.
문자 마케팅 실사용은 유료 플랜을 권장합니다.
