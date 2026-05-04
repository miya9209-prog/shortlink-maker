import csv
import os
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

APP_TITLE = "미샵 단축링크 관리자"
DATA_DIR = Path("data")
LINKS_FILE = DATA_DIR / "links.csv"
CLICKS_FILE = DATA_DIR / "clicks.csv"
COUNTER_FILE = DATA_DIR / "counter.txt"

ADMIN_ID = os.getenv("ADMIN_ID", "misharp")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "misharp1234")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-misharp-shortlink-secret")
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "")  # 예: https://msh.kr

ALLOWED_TARGET_HOSTS = {
    "misharp.co.kr",
    "www.misharp.co.kr",
}

app = FastAPI(title=APP_TITLE)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)


def ensure_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not LINKS_FILE.exists():
        with LINKS_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["code", "target_url", "memo", "active", "created_at"])
            writer.writeheader()
    if not CLICKS_FILE.exists():
        with CLICKS_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "code", "target_url", "ip", "user_agent", "referer"])
            writer.writeheader()
    if not COUNTER_FILE.exists():
        COUNTER_FILE.write_text("1", encoding="utf-8")


def read_links() -> List[Dict[str, str]]:
    ensure_files()
    with LINKS_FILE.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_links(rows: List[Dict[str, str]]) -> None:
    ensure_files()
    with LINKS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "target_url", "memo", "active", "created_at"])
        writer.writeheader()
        writer.writerows(rows)


def find_link(code: str) -> Optional[Dict[str, str]]:
    for row in read_links():
        if row.get("code") == code:
            return row
    return None


def click_counts() -> Dict[str, int]:
    ensure_files()
    counts: Dict[str, int] = {}
    with CLICKS_FILE.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("code", "")
            counts[code] = counts.get(code, 0) + 1
    return counts


def recent_clicks(limit: int = 50) -> List[Dict[str, str]]:
    ensure_files()
    with CLICKS_FILE.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return list(reversed(rows[-limit:]))


def is_valid_target_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in ALLOWED_TARGET_HOSTS
    except Exception:
        return False


def normalize_code(code: str) -> str:
    allowed = string.ascii_letters + string.digits + "-_"
    return "".join(ch for ch in code.strip() if ch in allowed)


def generate_random_code(length: int = 3) -> str:
    chars = string.ascii_letters + string.digits
    existing = {row["code"] for row in read_links()}
    for _ in range(200):
        code = "".join(random.choices(chars, k=length))
        if code not in existing:
            return code
    # 3자리 공간이 거의 차면 4자리로 자동 확장
    while True:
        code = "".join(random.choices(chars, k=length + 1))
        if code not in existing:
            return code


def generate_sequential_code() -> str:
    ensure_files()
    existing = {row["code"] for row in read_links()}
    num = int(COUNTER_FILE.read_text(encoding="utf-8").strip() or "1")
    while True:
        code = str(num).zfill(3)
        num += 1
        if code not in existing:
            COUNTER_FILE.write_text(str(num), encoding="utf-8")
            return code


def make_short_url(request: Request, code: str) -> str:
    if BASE_DOMAIN:
        return BASE_DOMAIN.rstrip("/") + "/" + code
    return str(request.base_url).rstrip("/") + "/" + code


def require_login(request: Request) -> bool:
    return bool(request.session.get("logged_in"))


def html_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f5f6f8; color:#1f2328; margin:0;}}
.wrap {{max-width:1080px; margin:40px auto; padding:0 18px;}}
.card {{background:white; border-radius:20px; box-shadow:0 10px 30px rgba(0,0,0,.07); padding:28px; margin-bottom:20px;}}
h1 {{font-size:28px; margin:0 0 12px;}}
h2 {{font-size:20px; margin:0 0 16px;}}
label {{display:block; font-weight:700; margin:14px 0 7px;}}
input, select {{width:100%; box-sizing:border-box; padding:13px 14px; border:1px solid #d9d9d9; border-radius:12px; font-size:15px;}}
button, .btn {{display:inline-block; background:#111; color:white; border:0; border-radius:12px; padding:12px 16px; font-weight:800; cursor:pointer; text-decoration:none;}}
.btn2 {{background:#666;}}
.btn-danger {{background:#b42318;}}
small,.muted {{color:#666;}}
.error {{background:#fff0f0; color:#b42318; padding:12px; border-radius:12px; margin:10px 0;}}
.success {{background:#effaf3; color:#146c2e; padding:12px; border-radius:12px; margin:10px 0;}}
table {{width:100%; border-collapse:collapse; font-size:14px;}}
th,td {{border-bottom:1px solid #eee; padding:10px; text-align:left; vertical-align:top;}}
th {{background:#fafafa;}}
.code {{font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-weight:800;}}
.grid {{display:grid; grid-template-columns:1fr 1fr; gap:18px;}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}} table{{font-size:12px}} .wrap{{margin:20px auto}}}}
</style>
</head>
<body><div class="wrap">{body}</div></body></html>
""")


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"


@app.get("/", response_class=HTMLResponse)
def root(request: Request, error: str = ""):
    if require_login(request):
        return RedirectResponse("/admin", status_code=303)
    err = f'<div class="error">{error}</div>' if error else ""
    body = f"""
    <div class="card" style="max-width:520px;margin:80px auto;">
      <h1>{APP_TITLE}</h1>
      <p class="muted">문자 발송용 짧은 링크를 만들고 클릭수를 확인합니다.</p>
      {err}
      <form method="post" action="/login">
        <label>아이디</label>
        <input name="admin_id" value="misharp" autocomplete="username">
        <label>비밀번호</label>
        <input name="password" type="password" autocomplete="current-password">
        <div style="margin-top:16px"><button type="submit">로그인</button></div>
      </form>
      <p><small>초기값: misharp / misharp1234<br>Render 환경변수에서 반드시 변경하세요.</small></p>
    </div>
    """
    return html_page(APP_TITLE, body)


@app.post("/login")
def login(request: Request, admin_id: str = Form(...), password: str = Form(...)):
    if admin_id == ADMIN_ID and password == ADMIN_PASSWORD:
        request.session["logged_in"] = True
        return RedirectResponse("/admin", status_code=303)
    return RedirectResponse("/?error=아이디 또는 비밀번호가 맞지 않습니다", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, message: str = "", error: str = ""):
    if not require_login(request):
        return RedirectResponse("/", status_code=303)
    links = read_links()
    counts = click_counts()
    rows = ""
    for row in reversed(links):
        code = row.get("code", "")
        short_url = make_short_url(request, code)
        active = row.get("active", "1") == "1"
        rows += f"""
        <tr>
          <td class="code"><a href="/{code}" target="_blank">/{code}</a></td>
          <td><input value="{short_url}" readonly onclick="this.select()"></td>
          <td style="max-width:260px;word-break:break-all"><a href="{row.get('target_url','')}" target="_blank">{row.get('target_url','')}</a><br><small>{row.get('memo','')}</small></td>
          <td>{counts.get(code,0)}</td>
          <td>{'사용중' if active else '중지'}</td>
          <td>
            <form method="post" action="/toggle/{code}" style="display:inline"><button class="btn2" type="submit">{'중지' if active else '사용'}</button></form>
            <form method="post" action="/delete/{code}" style="display:inline" onsubmit="return confirm('삭제할까요?')"><button class="btn-danger" type="submit">삭제</button></form>
          </td>
        </tr>"""
    msg = f'<div class="success">{message}</div>' if message else ""
    err = f'<div class="error">{error}</div>' if error else ""
    click_rows = ""
    for c in recent_clicks(30):
        ua = c.get("user_agent", "")[:90]
        click_rows += f"<tr><td>{c.get('timestamp','')}</td><td class='code'>/{c.get('code','')}</td><td>{c.get('ip','')}</td><td>{ua}</td></tr>"
    body = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <div><h1>{APP_TITLE}</h1><p class="muted">자동 3자리 랜덤 / 001 순차 / 수동 코드 생성 지원</p></div>
      <a class="btn btn2" href="/logout">로그아웃</a>
    </div>
    {msg}{err}
    <div class="card">
      <h2>단축링크 만들기</h2>
      <form method="post" action="/create">
        <label>미샵 원본 URL</label>
        <input name="target_url" placeholder="https://misharp.co.kr/..." required>
        <div class="grid">
          <div>
            <label>코드 생성 방식</label>
            <select name="mode">
              <option value="random">자동 랜덤 3자리 예: a7K</option>
              <option value="sequential">자동 순차 001, 002, 003</option>
              <option value="manual">직접 입력</option>
            </select>
          </div>
          <div>
            <label>직접 입력 코드</label>
            <input name="manual_code" placeholder="예: sale12, pants, 001">
          </div>
        </div>
        <label>메모</label>
        <input name="memo" placeholder="예: 5월 연휴 전상품 12% 문자">
        <div style="margin-top:16px"><button type="submit">단축링크 생성</button></div>
      </form>
    </div>
    <div class="card">
      <h2>링크 목록</h2>
      <table><thead><tr><th>코드</th><th>단축 URL</th><th>원본/메모</th><th>클릭</th><th>상태</th><th>관리</th></tr></thead><tbody>{rows or '<tr><td colspan="6">아직 생성된 링크가 없습니다.</td></tr>'}</tbody></table>
    </div>
    <div class="card">
      <h2>최근 클릭 로그</h2>
      <table><thead><tr><th>시간</th><th>코드</th><th>IP</th><th>기기/브라우저</th></tr></thead><tbody>{click_rows or '<tr><td colspan="4">아직 클릭 로그가 없습니다.</td></tr>'}</tbody></table>
    </div>
    """
    return html_page(APP_TITLE, body)


@app.post("/create")
def create_link(request: Request, target_url: str = Form(...), mode: str = Form("random"), manual_code: str = Form(""), memo: str = Form("")):
    if not require_login(request):
        return RedirectResponse("/", status_code=303)
    target_url = target_url.strip()
    if not is_valid_target_url(target_url):
        return RedirectResponse("/admin?error=미샵 도메인 URL만 등록할 수 있습니다. 예: https://misharp.co.kr/...", status_code=303)
    if mode == "manual":
        code = normalize_code(manual_code)
        if not code:
            return RedirectResponse("/admin?error=직접 입력 코드를 입력하세요", status_code=303)
    elif mode == "sequential":
        code = generate_sequential_code()
    else:
        code = generate_random_code(3)
    if find_link(code):
        return RedirectResponse(f"/admin?error=이미 사용 중인 코드입니다: {code}", status_code=303)
    rows = read_links()
    rows.append({"code": code, "target_url": target_url, "memo": memo.strip(), "active": "1", "created_at": datetime.now().isoformat(timespec="seconds")})
    write_links(rows)
    short_url = make_short_url(request, code)
    return RedirectResponse(f"/admin?message=생성 완료: {short_url}", status_code=303)


@app.post("/toggle/{code}")
def toggle_link(request: Request, code: str):
    if not require_login(request):
        return RedirectResponse("/", status_code=303)
    rows = read_links()
    for row in rows:
        if row.get("code") == code:
            row["active"] = "0" if row.get("active", "1") == "1" else "1"
    write_links(rows)
    return RedirectResponse("/admin?message=상태를 변경했습니다", status_code=303)


@app.post("/delete/{code}")
def delete_link(request: Request, code: str):
    if not require_login(request):
        return RedirectResponse("/", status_code=303)
    rows = [row for row in read_links() if row.get("code") != code]
    write_links(rows)
    return RedirectResponse("/admin?message=삭제했습니다", status_code=303)


def log_click(request: Request, code: str, target_url: str) -> None:
    ensure_files()
    with CLICKS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "code", "target_url", "ip", "user_agent", "referer"])
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "code": code,
            "target_url": target_url,
            "ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
            "referer": request.headers.get("referer", ""),
        })


@app.get("/{code}")
def redirect_code(request: Request, code: str):
    if code in {"favicon.ico", "robots.txt"}:
        return PlainTextResponse("", status_code=404)
    link = find_link(code)
    if not link:
        return html_page("링크 없음", "<div class='card'><h1>링크를 찾을 수 없습니다</h1><p>주소를 다시 확인해주세요.</p></div>")
    if link.get("active", "1") != "1":
        return html_page("링크 중지", "<div class='card'><h1>중지된 링크입니다</h1><p>관리자에게 문의해주세요.</p></div>")
    target_url = link.get("target_url", "")
    log_click(request, code, target_url)
    return RedirectResponse(target_url, status_code=302)
