import os
import sqlite3
import string
import random
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

APP_NAME = "MISHARP ShortLink"
DB_PATH = os.getenv("DB_PATH", "shortlinks.db")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-session-secret")
BASE_URL = os.getenv("BASE_URL", "")  # 예: https://mshp.kr
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "misharp.co.kr,www.misharp.co.kr").split(",") if h.strip()]

app = FastAPI(title=APP_NAME)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")
templates = Jinja2Templates(directory="templates")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            target_url TEXT NOT NULL,
            memo TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            clicked_at TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            referer TEXT
        )
        """)
        conn.commit()


init_db()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_logged_in(request: Request) -> bool:
    return request.session.get("admin") is True


def require_login(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")


def make_slug(length=5):
    alphabet = string.ascii_letters + string.digits
    for _ in range(50):
        slug = "".join(random.choice(alphabet) for _ in range(length))
        with db() as conn:
            exists = conn.execute("SELECT 1 FROM links WHERE slug=?", (slug,)).fetchone()
        if not exists:
            return slug
    raise RuntimeError("slug 생성 실패")


def validate_url(url: str):
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("https:// 로 시작하는 정상 URL을 입력하세요.")
    # 기본은 미샵 도메인만 허용. 외부 랜딩도 쓰려면 환경변수 ALLOWED_HOSTS에 추가.
    if ALLOWED_HOSTS and parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"허용되지 않은 도메인입니다: {parsed.hostname}. ALLOWED_HOSTS에 추가하세요.")
    return url


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "비밀번호가 맞지 않습니다."}, status_code=401)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    with db() as conn:
        rows = conn.execute("""
        SELECT l.*, COUNT(c.id) AS clicks
        FROM links l LEFT JOIN clicks c ON l.slug = c.slug
        GROUP BY l.id
        ORDER BY l.id DESC
        """).fetchall()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "rows": rows,
        "base_url": BASE_URL.rstrip("/"),
        "error": "",
        "ok": ""
    })


@app.post("/admin/create", response_class=HTMLResponse)
def create_link(request: Request, target_url: str = Form(...), slug: str = Form(""), memo: str = Form("")):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    ok = ""
    error = ""
    try:
        target_url = validate_url(target_url)
        slug = slug.strip().replace(" ", "") or make_slug()
        allowed_chars = set(string.ascii_letters + string.digits + "-_")
        if not slug or any(ch not in allowed_chars for ch in slug):
            raise ValueError("단축코드는 영문/숫자/-/_ 만 가능합니다.")
        with db() as conn:
            conn.execute(
                "INSERT INTO links (slug, target_url, memo, created_at, is_active) VALUES (?, ?, ?, ?, 1)",
                (slug, target_url, memo.strip(), now_iso())
            )
            conn.commit()
        full = f"{BASE_URL.rstrip('/')}/{slug}" if BASE_URL else f"/{slug}"
        ok = f"생성 완료: {full}"
    except sqlite3.IntegrityError:
        error = "이미 사용 중인 단축코드입니다."
    except Exception as e:
        error = str(e)

    with db() as conn:
        rows = conn.execute("""
        SELECT l.*, COUNT(c.id) AS clicks
        FROM links l LEFT JOIN clicks c ON l.slug = c.slug
        GROUP BY l.id
        ORDER BY l.id DESC
        """).fetchall()
    return templates.TemplateResponse("admin.html", {"request": request, "rows": rows, "base_url": BASE_URL.rstrip("/"), "error": error, "ok": ok})


@app.post("/admin/toggle/{slug}")
def toggle_link(request: Request, slug: str):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    with db() as conn:
        row = conn.execute("SELECT is_active FROM links WHERE slug=?", (slug,)).fetchone()
        if row:
            conn.execute("UPDATE links SET is_active=? WHERE slug=?", (0 if row["is_active"] else 1, slug))
            conn.commit()
    return RedirectResponse("/admin", status_code=303)


@app.get("/stats/{slug}", response_class=HTMLResponse)
def stats(request: Request, slug: str):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    with db() as conn:
        link = conn.execute("SELECT * FROM links WHERE slug=?", (slug,)).fetchone()
        if not link:
            raise HTTPException(404, "없는 링크입니다.")
        clicks = conn.execute("SELECT * FROM clicks WHERE slug=? ORDER BY id DESC LIMIT 200", (slug,)).fetchall()
        total = conn.execute("SELECT COUNT(*) AS n FROM clicks WHERE slug=?", (slug,)).fetchone()["n"]
    return templates.TemplateResponse("stats.html", {"request": request, "link": link, "clicks": clicks, "total": total, "base_url": BASE_URL.rstrip("/")})


@app.get("/{slug}")
def redirect_slug(request: Request, slug: str):
    with db() as conn:
        link = conn.execute("SELECT * FROM links WHERE slug=? AND is_active=1", (slug,)).fetchone()
        if not link:
            raise HTTPException(404, "단축 링크를 찾을 수 없습니다.")
        conn.execute(
            "INSERT INTO clicks (slug, clicked_at, ip, user_agent, referer) VALUES (?, ?, ?, ?, ?)",
            (slug, now_iso(), request.client.host if request.client else "", request.headers.get("user-agent", ""), request.headers.get("referer", ""))
        )
        conn.commit()
    return RedirectResponse(link["target_url"], status_code=302)
