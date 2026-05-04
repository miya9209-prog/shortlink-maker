import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

APP_NAME = "MISHARP Shortlink Maker"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LINKS_FILE = DATA_DIR / "links.json"
CLICKS_FILE = DATA_DIR / "clicks.jsonl"

ADMIN_ID = os.getenv("ADMIN_ID", "misharp")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "misharp1234")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
ALLOWED_TARGET_DOMAINS = [
    d.strip().lower() for d in os.getenv("ALLOWED_TARGET_DOMAINS", "misharp.co.kr,www.misharp.co.kr").split(",") if d.strip()
]

app = FastAPI(title=APP_NAME)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def load_links() -> Dict[str, Dict[str, Any]]:
    if not LINKS_FILE.exists():
        LINKS_FILE.write_text("{}", encoding="utf-8")
    try:
        return json.loads(LINKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_links(links: Dict[str, Dict[str, Any]]) -> None:
    LINKS_FILE.write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")


def is_logged_in(request: Request) -> bool:
    return request.session.get("admin") is True


def require_login(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Login required")


def clean_code(code: str) -> str:
    code = (code or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,50}", code):
        raise ValueError("단축코드는 영문 소문자/숫자/-/_ 조합 2~51자로 입력하세요.")
    return code


def validate_target_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("원본 URL은 https:// 로 시작하는 전체 주소를 입력하세요.")
    host = parsed.netloc.lower().split(":")[0]
    if ALLOWED_TARGET_DOMAINS and host not in ALLOWED_TARGET_DOMAINS:
        raise ValueError(f"허용 도메인만 등록 가능합니다: {', '.join(ALLOWED_TARGET_DOMAINS)}")
    return url


def device_label(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "iphone" in ua or "ipad" in ua:
        return "iPhone/iPad"
    if "android" in ua or "samsung" in ua:
        return "Galaxy/Android"
    if "windows" in ua:
        return "Windows"
    if "macintosh" in ua or "mac os" in ua:
        return "Mac"
    return "Other"


def count_clicks(code: str) -> int:
    if not CLICKS_FILE.exists():
        return 0
    total = 0
    with CLICKS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                if row.get("code") == code:
                    total += 1
            except Exception:
                pass
    return total


def recent_clicks(limit: int = 200):
    if not CLICKS_FILE.exists():
        return []
    rows = []
    with CLICKS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return list(reversed(rows[-limit:]))


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if not is_logged_in(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": ""})
    links = load_links()
    enriched = []
    for code, item in sorted(links.items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
        enriched.append({**item, "code": code, "clicks": count_clicks(code)})
    return templates.TemplateResponse("admin.html", {"request": request, "links": enriched, "allowed_domains": ALLOWED_TARGET_DOMAINS})


@app.post("/login")
def login(request: Request, admin_id: str = Form(...), password: str = Form(...)):
    if admin_id == ADMIN_ID and password == ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "아이디 또는 비밀번호가 맞지 않습니다."})


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.post("/create")
def create_link(request: Request, code: str = Form(...), target_url: str = Form(...), memo: str = Form("")):
    require_login(request)
    links = load_links()
    try:
        code = clean_code(code)
        target_url = validate_target_url(target_url)
    except ValueError as e:
        return HTMLResponse(f"<script>alert('{str(e)}');history.back();</script>", status_code=400)
    if code in links:
        return HTMLResponse("<script>alert('이미 사용 중인 단축코드입니다.');history.back();</script>", status_code=400)
    links[code] = {
        "target_url": target_url,
        "memo": memo.strip(),
        "active": True,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_links(links)
    return RedirectResponse("/", status_code=303)


@app.post("/toggle/{code}")
def toggle_link(request: Request, code: str):
    require_login(request)
    links = load_links()
    if code in links:
        links[code]["active"] = not links[code].get("active", True)
        save_links(links)
    return RedirectResponse("/", status_code=303)


@app.post("/delete/{code}")
def delete_link(request: Request, code: str):
    require_login(request)
    links = load_links()
    if code in links:
        del links[code]
        save_links(links)
    return RedirectResponse("/", status_code=303)


@app.get("/stats", response_class=HTMLResponse)
def stats(request: Request):
    require_login(request)
    return templates.TemplateResponse("stats.html", {"request": request, "clicks": recent_clicks(300)})


@app.get("/{code}")
def go(code: str, request: Request):
    links = load_links()
    item = links.get(code)
    if not item or not item.get("active", True):
        return HTMLResponse("<h2>사용할 수 없는 링크입니다.</h2>", status_code=404)
    ua = request.headers.get("user-agent", "")
    row = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "code": code,
        "target_url": item.get("target_url"),
        "device": device_label(ua),
        "user_agent": ua[:300],
        "ip": request.client.host if request.client else "",
    }
    with CLICKS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return RedirectResponse(item["target_url"], status_code=302)
