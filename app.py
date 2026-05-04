import os
import sqlite3
import random
import string
from datetime import datetime
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

APP_TITLE = "MISHARP Shortlink"
DB_PATH = os.getenv("DB_PATH", "shortlinks.db")

ADMIN_ID = os.getenv("ADMIN_ID", "misharp")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "misharp1234")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")

app = FastAPI(title=APP_TITLE)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            memo TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            clicks INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            ip TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            referer TEXT DEFAULT '',
            clicked_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_logged_in(request: Request) -> bool:
    return request.session.get("logged_in") is True


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL을 입력하세요.")
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("올바른 URL이 아닙니다.")
    return url


def generate_random_code(length: int = 3) -> str:
    alphabet = string.ascii_letters + string.digits
    conn = db()
    cur = conn.cursor()
    for _ in range(300):
        code = "".join(random.choices(alphabet, k=length))
        exists = cur.execute("SELECT 1 FROM links WHERE code=?", (code,)).fetchone()
        if not exists:
            conn.close()
            return code
    conn.close()
    raise RuntimeError("랜덤 코드 생성 실패: 코드 길이를 늘려주세요.")


def generate_sequential_code() -> str:
    conn = db()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT code FROM links
        WHERE code GLOB '[0-9][0-9][0-9]'
        ORDER BY CAST(code AS INTEGER) DESC
        LIMIT 1
    """).fetchone()
    next_num = 1 if not row else int(row["code"]) + 1
    while True:
        code = str(next_num).zfill(3)
        exists = cur.execute("SELECT 1 FROM links WHERE code=?", (code,)).fetchone()
        if not exists:
            conn.close()
            return code
        next_num += 1


def esc(s):
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def layout(title: str, body: str, request: Request = None) -> HTMLResponse:
    logged = is_logged_in(request) if request else False
    nav = ""
    if logged:
        nav = """
        <div class="nav">
            <a href="/admin">대시보드</a>
            <a href="/logout">로그아웃</a>
        </div>
        """
    html = f"""
    <!doctype html>
    <html lang="ko">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{esc(title)}</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", Arial, sans-serif;
                margin: 0; background: #f6f7fb; color: #222;
            }}
            .wrap {{ max-width: 1080px; margin: 0 auto; padding: 28px 18px 60px; }}
            .top {{
                display:flex; justify-content:space-between; align-items:center;
                margin-bottom:18px;
            }}
            h1 {{ font-size: 26px; margin: 0; letter-spacing: -0.03em; }}
            h2 {{ font-size: 20px; margin: 0 0 16px; }}
            .card {{
                background:#fff; border:1px solid #e9e9ef; border-radius:16px;
                padding:22px; box-shadow:0 6px 20px rgba(20,20,30,.05); margin-bottom:18px;
            }}
            .nav a, .btn {{
                display:inline-block; padding:10px 14px; border-radius:10px;
                background:#111; color:#fff; text-decoration:none; border:0; cursor:pointer;
                font-size:14px;
            }}
            .nav a {{ margin-left:8px; background:#333; }}
            .btn.secondary {{ background:#666; }}
            .btn.danger {{ background:#b42318; }}
            .btn.light {{ background:#f0f0f3; color:#111; border:1px solid #ddd; }}
            input, select, textarea {{
                width:100%; padding:12px 12px; border:1px solid #d9d9e3; border-radius:10px;
                font-size:15px; background:#fff;
            }}
            label {{ display:block; font-weight:700; margin: 12px 0 7px; }}
            .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:14px; }}
            .muted {{ color:#777; font-size:13px; }}
            .error {{ background:#fff1f0; color:#b42318; border:1px solid #ffd4cf; padding:12px; border-radius:10px; margin-bottom:12px; }}
            .ok {{ background:#efffed; color:#136c22; border:1px solid #c7f5ca; padding:12px; border-radius:10px; margin-bottom:12px; }}
            table {{ width:100%; border-collapse:collapse; font-size:14px; }}
            th, td {{ border-bottom:1px solid #eee; padding:10px 8px; text-align:left; vertical-align:top; }}
            th {{ color:#555; background:#fafafa; }}
            .code {{ font-weight:800; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
            .url {{ max-width:330px; word-break:break-all; }}
            .actions form {{ display:inline-block; margin: 0 3px 5px 0; }}
            .pill {{ display:inline-block; padding:4px 8px; border-radius:999px; background:#eee; font-size:12px; }}
            .pill.on {{ background:#e8fff0; color:#147c2e; }}
            .pill.off {{ background:#ffeceb; color:#ad1d18; }}
            @media (max-width: 760px) {{
                .grid {{ grid-template-columns:1fr; }}
                table, thead, tbody, th, td, tr {{ display:block; }}
                th {{ display:none; }}
                td {{ padding:8px 0; }}
                .top {{ display:block; }}
                .nav {{ margin-top:12px; }}
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="top">
                <h1>{esc(APP_TITLE)}</h1>
                {nav}
            </div>
            {body}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/health")
def health():
    return PlainTextResponse("ok")


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if is_logged_in(request):
        return RedirectResponse("/admin", status_code=303)
    body = """
    <div class="card">
        <h2>관리자 로그인</h2>
        <form method="post" action="/login">
            <label>아이디</label>
            <input name="admin_id" autocomplete="username" placeholder="ADMIN_ID">
            <label>비밀번호</label>
            <input name="password" type="password" autocomplete="current-password" placeholder="ADMIN_PASSWORD">
            <div style="margin-top:16px;">
                <button class="btn" type="submit">로그인</button>
            </div>
        </form>
        <p class="muted">초기값은 misharp / misharp1234 입니다. Render 환경변수 ADMIN_ID, ADMIN_PASSWORD, SECRET_KEY를 반드시 설정하세요.</p>
    </div>
    """
    return layout("로그인", body, request)


@app.post("/login")
def login(request: Request, admin_id: str = Form(...), password: str = Form(...)):
    if admin_id == ADMIN_ID and password == ADMIN_PASSWORD:
        request.session["logged_in"] = True
        return RedirectResponse("/admin", status_code=303)
    body = """
    <div class="error">아이디 또는 비밀번호가 맞지 않습니다.</div>
    <div class="card">
        <h2>관리자 로그인</h2>
        <form method="post" action="/login">
            <label>아이디</label>
            <input name="admin_id">
            <label>비밀번호</label>
            <input name="password" type="password">
            <div style="margin-top:16px;">
                <button class="btn" type="submit">로그인</button>
            </div>
        </form>
    </div>
    """
    return layout("로그인 실패", body, request)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, msg: str = "", err: str = ""):
    if not is_logged_in(request):
        return RedirectResponse("/", status_code=303)

    conn = db()
    rows = conn.execute("SELECT * FROM links ORDER BY id DESC").fetchall()
    total_clicks = conn.execute("SELECT COUNT(*) AS c FROM clicks").fetchone()["c"]
    conn.close()

    notices = ""
    if msg:
        notices += f'<div class="ok">{esc(msg)}</div>'
    if err:
        notices += f'<div class="error">{esc(err)}</div>'

    list_rows = ""
    for r in rows:
        active = '<span class="pill on">사용중</span>' if r["is_active"] else '<span class="pill off">중지</span>'
        short_url = f"{str(request.base_url).rstrip('/')}/{r['code']}"
        toggle_text = "중지" if r["is_active"] else "사용"
        list_rows += f"""
        <tr>
            <td><span class="code">{esc(r['code'])}</span><br><a href="/{esc(r['code'])}" target="_blank">열기</a></td>
            <td class="url"><a href="{esc(r['url'])}" target="_blank">{esc(r['url'])}</a><br><span class="muted">{esc(short_url)}</span></td>
            <td>{esc(r['memo'])}</td>
            <td>{active}</td>
            <td><strong>{r['clicks']}</strong></td>
            <td>{esc(r['created_at'])}</td>
            <td class="actions">
                <form method="post" action="/admin/toggle">
                    <input type="hidden" name="code" value="{esc(r['code'])}">
                    <button class="btn light" type="submit">{toggle_text}</button>
                </form>
                <form method="post" action="/admin/delete" onsubmit="return confirm('정말 삭제할까요?');">
                    <input type="hidden" name="code" value="{esc(r['code'])}">
                    <button class="btn danger" type="submit">삭제</button>
                </form>
                <a class="btn secondary" href="/admin/clicks/{esc(r['code'])}">로그</a>
            </td>
        </tr>
        """

    body = f"""
    {notices}
    <div class="grid">
        <div class="card">
            <h2>단축링크 생성</h2>
            <form method="post" action="/admin/create">
                <label>원본 URL</label>
                <input name="url" placeholder="https://misharp.co.kr 또는 모든 외부 URL 가능" required>

                <label>생성 방식</label>
                <select name="mode">
                    <option value="random">랜덤 3자리 자동 생성</option>
                    <option value="sequential">001, 002, 003 순차 생성</option>
                    <option value="manual">직접 입력</option>
                </select>

                <label>직접 입력 코드</label>
                <input name="manual_code" placeholder="예: sale12, best, 001">

                <label>메모</label>
                <input name="memo" placeholder="예: 5월 문자 세일 / 팬츠 기획전">

                <div style="margin-top:16px;">
                    <button class="btn" type="submit">단축링크 만들기</button>
                </div>
                <p class="muted">모든 http://, https:// URL을 지원합니다. 직접 코드는 영문/숫자/하이픈/언더바 권장.</p>
            </form>
        </div>
        <div class="card">
            <h2>운영 현황</h2>
            <p>생성 링크: <strong>{len(rows)}</strong>개</p>
            <p>전체 클릭: <strong>{total_clicks}</strong>회</p>
            <p class="muted">문자 발송 예: (광고)미샵♥세일! 지금▶https://msh.kr/001</p>
        </div>
    </div>

    <div class="card">
        <h2>링크 목록</h2>
        <table>
            <thead>
                <tr>
                    <th>코드</th>
                    <th>원본 URL / 단축 URL</th>
                    <th>메모</th>
                    <th>상태</th>
                    <th>클릭</th>
                    <th>생성일</th>
                    <th>관리</th>
                </tr>
            </thead>
            <tbody>
                {list_rows if list_rows else '<tr><td colspan="7">아직 생성된 링크가 없습니다.</td></tr>'}
            </tbody>
        </table>
    </div>
    """
    return layout("관리자", body, request)


@app.post("/admin/create")
def create_link(
    request: Request,
    url: str = Form(...),
    mode: str = Form("random"),
    manual_code: str = Form(""),
    memo: str = Form("")
):
    if not is_logged_in(request):
        return RedirectResponse("/", status_code=303)

    try:
        url = normalize_url(url)
        if mode == "sequential":
            code = generate_sequential_code()
        elif mode == "manual":
            code = manual_code.strip()
            if not code:
                raise ValueError("직접 입력 방식을 선택한 경우 코드를 입력하세요.")
        else:
            code = generate_random_code(3)

        code = code.strip()
        if "/" in code or "?" in code or "#" in code or len(code) < 1:
            raise ValueError("코드에는 / ? # 등을 사용할 수 없습니다.")

        conn = db()
        conn.execute(
            "INSERT INTO links (code, url, memo, is_active, clicks, created_at, updated_at) VALUES (?, ?, ?, 1, 0, ?, ?)",
            (code, url, memo.strip(), now(), now())
        )
        conn.commit()
        conn.close()
        return RedirectResponse(f"/admin?msg=단축링크가 생성되었습니다: /{code}", status_code=303)
    except sqlite3.IntegrityError:
        return RedirectResponse("/admin?err=이미 사용 중인 코드입니다. 다른 코드를 입력하세요.", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?err={str(e)}", status_code=303)


@app.post("/admin/toggle")
def toggle_link(request: Request, code: str = Form(...)):
    if not is_logged_in(request):
        return RedirectResponse("/", status_code=303)
    conn = db()
    row = conn.execute("SELECT is_active FROM links WHERE code=?", (code,)).fetchone()
    if row:
        conn.execute("UPDATE links SET is_active=?, updated_at=? WHERE code=?", (0 if row["is_active"] else 1, now(), code))
        conn.commit()
    conn.close()
    return RedirectResponse("/admin?msg=상태가 변경되었습니다.", status_code=303)


@app.post("/admin/delete")
def delete_link(request: Request, code: str = Form(...)):
    if not is_logged_in(request):
        return RedirectResponse("/", status_code=303)
    conn = db()
    conn.execute("DELETE FROM links WHERE code=?", (code,))
    conn.execute("DELETE FROM clicks WHERE code=?", (code,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin?msg=링크가 삭제되었습니다.", status_code=303)


@app.get("/admin/clicks/{code}", response_class=HTMLResponse)
def click_logs(request: Request, code: str):
    if not is_logged_in(request):
        return RedirectResponse("/", status_code=303)
    conn = db()
    link = conn.execute("SELECT * FROM links WHERE code=?", (code,)).fetchone()
    rows = conn.execute("SELECT * FROM clicks WHERE code=? ORDER BY id DESC LIMIT 300", (code,)).fetchall()
    conn.close()
    if not link:
        return RedirectResponse("/admin?err=없는 코드입니다.", status_code=303)

    trs = ""
    for r in rows:
        trs += f"""
        <tr>
            <td>{esc(r['clicked_at'])}</td>
            <td>{esc(r['ip'])}</td>
            <td>{esc(r['referer'])}</td>
            <td class="url">{esc(r['user_agent'])}</td>
        </tr>
        """
    body = f"""
    <div class="card">
        <h2>클릭 로그: <span class="code">{esc(code)}</span></h2>
        <p>원본 URL: <a href="{esc(link['url'])}" target="_blank">{esc(link['url'])}</a></p>
        <p>총 클릭수: <strong>{link['clicks']}</strong></p>
        <a class="btn light" href="/admin">돌아가기</a>
    </div>
    <div class="card">
        <table>
            <thead><tr><th>시간</th><th>IP</th><th>Referer</th><th>User Agent</th></tr></thead>
            <tbody>{trs if trs else '<tr><td colspan="4">클릭 기록이 없습니다.</td></tr>'}</tbody>
        </table>
    </div>
    """
    return layout("클릭 로그", body, request)


@app.get("/{code}")
def go(code: str, request: Request):
    conn = db()
    link = conn.execute("SELECT * FROM links WHERE code=?", (code,)).fetchone()
    if not link:
        conn.close()
        return HTMLResponse("<h2>없는 링크입니다.</h2>", status_code=404)
    if not link["is_active"]:
        conn.close()
        return HTMLResponse("<h2>중지된 링크입니다.</h2>", status_code=410)

    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    ua = request.headers.get("user-agent", "")
    referer = request.headers.get("referer", "")

    conn.execute("UPDATE links SET clicks=clicks+1, updated_at=? WHERE code=?", (now(), code))
    conn.execute(
        "INSERT INTO clicks (code, ip, user_agent, referer, clicked_at) VALUES (?, ?, ?, ?, ?)",
        (code, ip, ua, referer, now())
    )
    conn.commit()
    conn.close()

    return RedirectResponse(link["url"], status_code=302)
