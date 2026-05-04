# MISHARP ShortLink

미샵 전용 단축 URL/문자 링크 관리 시스템입니다.

## 기능
- `/admin` 관리자 페이지
- 미샵 랜딩 URL을 짧은 코드로 생성
- `/{slug}` 접속 시 원본 URL로 302 리다이렉트
- 클릭수/접속기기 User-Agent 기록
- 링크 사용/중지
- 미샵 도메인만 허용하는 안전장치

## 환경변수
- `ADMIN_PASSWORD`: 관리자 비밀번호
- `SESSION_SECRET`: 세션 암호화 문자열
- `BASE_URL`: 실제 단축 도메인 예: `https://mshp.kr`
- `ALLOWED_HOSTS`: 허용할 목적지 도메인, 기본 `misharp.co.kr,www.misharp.co.kr`
- `DB_PATH`: SQLite DB 경로, 기본 `shortlinks.db`

## 로컬 실행
```bash
pip install -r requirements.txt
ADMIN_PASSWORD=1234 SESSION_SECRET=abc BASE_URL=http://localhost:8000 uvicorn app:app --reload
```

관리자: http://localhost:8000/admin

## 문자 발송 전 필수 테스트
1. 갤럭시 삼성인터넷
2. 갤럭시 크롬
3. 아이폰 사파리
4. 카카오톡 인앱브라우저
5. SMS9 발송 테스트 1건

## 권장 도메인
`mshp.kr`, `mishop.kr`, `misharp.kr` 등 미샵 전용 도메인 권장.

DNS 예시:
- 배포서비스가 Render/Fly/Railway라면 CNAME을 해당 서비스 안내값으로 설정
- 루트 도메인 사용 시 서비스별 A 레코드 또는 ALIAS 설정 필요
