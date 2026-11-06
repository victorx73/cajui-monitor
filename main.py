import asyncio
import hashlib
import os
import time

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Form, Request  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

import scraper  # noqa: E402
from security import SESSION_MAX_AGE, login_bloqueado, pack, registrar_tentativa, unpack  # noqa: E402

COOKIE_NAME = os.getenv("COOKIE_NAME", "cajui_session")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
LIMITE = float(os.getenv("FREQUENCIA_MINIMA", "75"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
REFRESH_MIN_INTERVAL = 20  # segundos entre "atualizar" forçados

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")
jinja = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape())


def render(nome: str, **ctx) -> HTMLResponse:
    return HTMLResponse(jinja.get_template(nome).render(**ctx))


@app.middleware("http")
async def headers_seguranca(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; "
        "script-src 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/") or request.url.path in ("/", "/painel"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def ip_do_cliente(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "?")


def cookies_da_sessao(request: Request) -> dict | None:
    return unpack(request.cookies.get(COOKIE_NAME))


# --- cache em memória (só otimização; perder no restart não afeta o login) ---
_cache: dict[str, tuple[float, dict]] = {}
_locks: dict[str, asyncio.Lock] = {}


async def dados_com_cache(request: Request, cookies: dict, forcar: bool) -> dict:
    chave = hashlib.sha256(request.cookies[COOKIE_NAME].encode()).hexdigest()
    lock = _locks.setdefault(chave, asyncio.Lock())
    async with lock:  # evita scrapes duplicados do mesmo usuário
        hit = _cache.get(chave)
        if hit:
            idade = time.time() - hit[0]
            if idade < (REFRESH_MIN_INTERVAL if forcar else CACHE_TTL):
                return hit[1]
        dados = await scraper.pegar_dados(cookies)
        pres = sum(d["presencas"] for d in dados)
        aulas = sum(d["total"] for d in dados)
        payload = {
            "dados": dados,
            "geral": round(pres / aulas * 100, 1) if aulas else 100.0,
            "limite": LIMITE,
            "ts": int(time.time()),
        }
        _cache[chave] = (time.time(), payload)
        return payload


# --- rotas ---
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    if cookies_da_sessao(request):
        return RedirectResponse("/painel")
    return render("login.html")


@app.post("/login")
async def login(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    ip = ip_do_cliente(request)
    if login_bloqueado(ip):
        return render("login.html", erro="Muitas tentativas. Aguarde alguns minutos.")
    registrar_tentativa(ip)
    try:
        cookies = await scraper.fazer_login(usuario.strip(), senha)
    except scraper.CajuiIndisponivel as e:
        scraper.log.warning("Cajuí indisponível: %r", e)
        return render("login.html", erro="Cajuí indisponível no momento. Tente de novo.")
    if not cookies:
        return render("login.html", erro="Usuário ou senha inválidos.")
    # a senha não é guardada em lugar nenhum: sai de escopo aqui
    resp = RedirectResponse("/painel", status_code=303)
    resp.set_cookie(COOKIE_NAME, pack(cookies), max_age=SESSION_MAX_AGE,
                    httponly=True, secure=COOKIE_SECURE, samesite="lax")
    return resp


@app.get("/painel", response_class=HTMLResponse)
def painel(request: Request):
    if not cookies_da_sessao(request):
        return RedirectResponse("/")
    return render("index.html", limite=LIMITE)


@app.get("/api/faltas")
async def api_faltas(request: Request, refresh: int = 0):
    cookies = cookies_da_sessao(request)
    if not cookies:
        return JSONResponse({"erro": "Sessão expirada"}, status_code=401)
    try:
        return await dados_com_cache(request, cookies, bool(refresh))
    except scraper.SessaoExpirada:
        return JSONResponse({"erro": "Sessão expirada"}, status_code=401)
    except scraper.CajuiIndisponivel:
        return JSONResponse({"erro": "Cajuí indisponível no momento"}, status_code=502)


@app.get("/logout")
def logout():
    resp = RedirectResponse("/")
    resp.delete_cookie(COOKIE_NAME)
    return resp
