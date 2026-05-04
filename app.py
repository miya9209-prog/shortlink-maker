import csv
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LINKS_CSV = DATA_DIR / "links.csv"
CLICKS_CSV = DATA_DIR / "clicks.csv"

ADMIN_ID = os.getenv("ADMIN_ID", "misharp")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "misharp1234")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

ALLOWED_DOMAINS = [
    "misharp.co.kr",
    "www.misharp.co.kr",
    "misharp.kr",
    "www.misharp.kr",
]

app = FastAPI(title="MISHARP Shortlink Maker")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)


def now_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def ensure_csv():
    if not LINKS_CSV.exists():
        with LINKS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=["code", "target_url", "memo", "active", "created_at"]).writeheader()
    if not CLICKS_CSV.exists():
        with CLICKS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=["code", "clicked_at", "ip", "user_agent", "referer"]).writeheader()


def read_links():
    ensure_csv()
    with LINKS_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_links(rows):
    ensure_csv()
    with LINKS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "target_url", "memo", "active", "created_at"])
        writer.writeheader()
        writer.writerows(rows)


def read_clicks():
    ensure_csv()
    with CLICKS_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def add_click(code: str, request: Request):
    ensure_csv()
    ua = request.headers.get("user-agent", "")
    referer = request.headers.get("referer", "")
    ip = request.client.host if request.client else ""
    with CLICKS_CSV.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "clicked_at", "ip", "user_agent", "referer"])
        writer.writerow({"code": code, "clicked_at": now_str(), "ip": ip, "user_agent": ua, "referer": referer})


def is_logged_in(request: Request) -> bool:
    return request.session.get("logged_in") is True


def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/", status_code=303)
    return None


def escape(s: Optional[str]) -> str:
    s = s or ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def validate_target_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ["http", "https"] or not parsed.netloc:
        raise ValueError("올바른 URL이 아닙니다.")
    host = parsed.netloc.lower().split(":")[0]
    if host not in ALLOWED_DOMAINS:
        raise ValueError("미샵 도메인만 등록할 수 있습니다. misharp.co.kr 링크를 입력하세요.")


def validate_code(code: str):
    code = (code or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", code):
        raise ValueError("단축코드는 영문/숫자/하이픈/언더바 2~40자로 입력하세요.")


def page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',Arial,sans-serif;background:#f6f7f9;margin:0;color:#222}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px}}
.card{{background:#fff;border-radius:18px;padding:24px;box-shadow:0 8px 28px rgba(0,0,0,.07);margin-bottom:18px}}
h1{{margin:0 0 18px;font-size:28px}} h2{{font-size:20px;margin:0 0 14px}}
input,textarea,select{{width:100%;box-sizing:border-box;border:1px solid #ddd;border-radius:12px;padding:12px;font-size:15px;margin:7px 0 14px}}
button,.btn{{display:inline-block;border:0;background:#111;color:#fff;border-radius:12px;padding:11px 16px;font-weight:700;text-decoration:none;cursor:pointer}}
.btn2{{background:#eee;color:#111}} .danger{{background:#c62828}}
table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{border-bottom:1px solid #eee;padding:10px;text-align:left;vertical-align:top}} th{{background:#fafafa}}
.small{{font-size:13px;color:#666}} .error{{background:#fff0f0;color:#b00020;padding:12px;border-radius:12px;margin-bottom:12px}}
.ok{{background:#effff2;color:#0b6b20;padding:12px;border-radius:12px;margin-bottom:12px}}
.code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:#f2f2f2;padding:2px 6px;border-radius:6px}}
.top{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:18px}} .actions a{{margin-left:8px}}
@media(max-width:700px){{.wrap{{padding:14px}} table{{font-size:12px}} th,td{{padding:7px}}}}
</style>
</head>
<body><div class="wrap">{body}</div></body></html>"""
    return HTMLResponse(html)


@app.get("/health")
def health():
    return PlainTextResponse("ok")


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    if is_logged_in(request):
        return RedirectResponse("/admin", status_code=303)
    body = f"""
    <div class="card" style="max-width:460px;margin:60px auto;">
      <h1>미샵 단축링크 관리자</h1>
      <p class="small">문자 발송용 짧은 링크를 만들고 클릭수를 확인합니다.</p>
      {f'<div class="error">{escape(error)}</div>' if error else ''}
      <form method="post" action="/login">
        <label>아이디</label><input name="admin_id" value="misharp" autocomplete="username">
        <label>비밀번호</label><input name="password" type="password" autocomplete="current-password">
        <button type="submit">로그인</button>
      </form>
      <p class="small">초기값: misharp / misharp1234<br>Render 환경변수에서 반드시 변경하세요.</p>
    </div>
    """
    return page("미샵 단축링크 로그인", body)


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
def admin(request: Request, msg: str = "", error: str = ""):
    r = require_login(request)
    if r: return r
    links = read_links()
    clicks = read_clicks()
    count_map = {}
    for c in clicks:
        count_map[c.get("code", "")] = count_map.get(c.get("code", ""), 0) + 1
    host = BASE_URL or str(request.base_url).rstrip("/")
    rows_html = ""
    for item in links:
        code = item["code"]
        short = f"{host}/{code}"
        rows_html += f"""
        <tr>
          <td><b>{escape(code)}</b><br><span class="small"><a href="/{escape(code)}" target="_blank">{escape(short)}</a></span></td>
          <td><a href="{escape(item['target_url'])}" target="_blank">{escape(item['target_url'])}</a><br><span class="small">{escape(item.get('memo',''))}</span></td>
          <td>{'사용중' if item.get('active') == '1' else '중지'}</td>
          <td>{count_map.get(code, 0)}</td>
          <td class="small">{escape(item.get('created_at',''))}</td>
          <td>
            <form method="post" action="/admin/toggle" style="display:inline"><input type="hidden" name="code" value="{escape(code)}"><button class="btn2" type="submit">사용/중지</button></form>
            <form method="post" action="/admin/delete" style="display:inline" onsubmit="return confirm('삭제할까요?')"><input type="hidden" name="code" value="{escape(code)}"><button class="danger" type="submit">삭제</button></form>
          </td>
        </tr>"""
    if not rows_html:
        rows_html = '<tr><td colspan="6" class="small">아직 생성된 링크가 없습니다.</td></tr>'
    body = f"""
    <div class="top"><h1>미샵 단축링크 관리자</h1><div class="actions"><a class="btn btn2" href="/clicks">클릭로그</a><a class="btn btn2" href="/logout">로그아웃</a></div></div>
    {f'<div class="ok">{escape(msg)}</div>' if msg else ''}
    {f'<div class="error">{escape(error)}</div>' if error else ''}
    <div class="card">
      <h2>새 단축링크 만들기</h2>
      <form method="post" action="/admin/create">
        <label>단축코드</label><input name="code" placeholder="예: sale12, pants12, may-event" required>
        <label>미샵 원본 URL</label><input name="target_url" placeholder="https://misharp.co.kr/..." required>
        <label>메모</label><input name="memo" placeholder="예: 전상품 12% 세일 문자">
        <button type="submit">생성하기</button>
      </form>
    </div>
    <div class="card">
      <h2>링크 목록</h2>
      <table><thead><tr><th>단축링크</th><th>원본 URL</th><th>상태</th><th>클릭수</th><th>생성일</th><th>관리</th></tr></thead><tbody>{rows_html}</tbody></table>
    </div>
    """
    return page("미샵 단축링크 관리자", body)


@app.post("/admin/create")
def create_link(request: Request, code: str = Form(...), target_url: str = Form(...), memo: str = Form("")):
    r = require_login(request)
    if r: return r
    try:
        code = code.strip()
        target_url = normalize_url(target_url)
        validate_code(code)
        validate_target_url(target_url)
        rows = read_links()
        if any(x["code"] == code for x in rows):
            raise ValueError("이미 사용 중인 단축코드입니다.")
        rows.append({"code": code, "target_url": target_url, "memo": memo.strip(), "active": "1", "created_at": now_str()})
        write_links(rows)
        return RedirectResponse(f"/admin?msg={code} 링크가 생성되었습니다", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?error={str(e)}", status_code=303)


@app.post("/admin/toggle")
def toggle_link(request: Request, code: str = Form(...)):
    r = require_login(request)
    if r: return r
    rows = read_links()
    for item in rows:
        if item["code"] == code:
            item["active"] = "0" if item.get("active") == "1" else "1"
    write_links(rows)
    return RedirectResponse("/admin?msg=상태가 변경되었습니다", status_code=303)


@app.post("/admin/delete")
def delete_link(request: Request, code: str = Form(...)):
    r = require_login(request)
    if r: return r
    rows = [x for x in read_links() if x["code"] != code]
    write_links(rows)
    return RedirectResponse("/admin?msg=삭제되었습니다", status_code=303)


@app.get("/clicks", response_class=HTMLResponse)
def clicks_page(request: Request):
    r = require_login(request)
    if r: return r
    clicks = list(reversed(read_clicks()))[:300]
    rows_html = ""
    for c in clicks:
        ua = c.get("user_agent", "")
        device = "갤럭시/안드로이드" if "Android" in ua else ("아이폰" if "iPhone" in ua else "기타")
        rows_html += f"<tr><td>{escape(c.get('clicked_at',''))}</td><td>{escape(c.get('code',''))}</td><td>{escape(device)}</td><td class='small'>{escape(c.get('ip',''))}</td><td class='small'>{escape(ua[:160])}</td></tr>"
    if not rows_html:
        rows_html = '<tr><td colspan="5" class="small">아직 클릭 로그가 없습니다.</td></tr>'
    body = f"""
    <div class="top"><h1>클릭 로그</h1><div><a class="btn btn2" href="/admin">관리자 홈</a></div></div>
    <div class="card"><table><thead><tr><th>시간</th><th>코드</th><th>기기</th><th>IP</th><th>User-Agent</th></tr></thead><tbody>{rows_html}</tbody></table></div>
    """
    return page("클릭 로그", body)


@app.get("/{code}")
def redirect_short(code: str, request: Request):
    if code in ["favicon.ico", "robots.txt"]:
        raise HTTPException(status_code=404)
    links = read_links()
    for item in links:
        if item["code"] == code and item.get("active") == "1":
            add_click(code, request)
            return RedirectResponse(item["target_url"], status_code=302)
    return page("링크 없음", "<div class='card'><h1>링크를 찾을 수 없습니다</h1><p>주소가 잘못되었거나 중지된 링크입니다.</p></div>")
