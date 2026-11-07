"""Scraping assíncrono do Cajuí (httpx + BeautifulSoup)."""
import asyncio
import logging
import os
import re

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("uvicorn.error")

BASE = "https://cajui.ifnmg.edu.br"
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "20"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))


# Onde fica a tela com as disciplinas (o Cajuí mudou o /portal; testamos alguns endereços)
CANDIDATAS = ["/portal", "/portal/aluno/painel", "/portal/aluno/painel/index", "/portal/aluno"]
_painel_ok: str | None = None


class SessaoExpirada(Exception):
    pass


class CajuiIndisponivel(Exception):
    pass


def _client(cookies=None) -> httpx.AsyncClient:
    c = httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT, follow_redirects=True)
    if isinstance(cookies, dict):          # formato antigo (sessões já emitidas)
        for nome, valor in cookies.items():
            c.cookies.set(nome, valor)
    elif cookies:                          # formato novo: preserva domínio e path
        for ck in cookies:
            c.cookies.set(ck["name"], ck["value"], domain=ck["domain"], path=ck["path"])
    return c


def _exportar_cookies(c: httpx.AsyncClient) -> list[dict]:
    # Lista (e não dict): o mesmo nome pode existir em paths diferentes (/cajui e /portal)
    return [{"name": ck.name, "value": ck.value, "domain": ck.domain, "path": ck.path}
            for ck in c.cookies.jar]


def _titulo(soup) -> str:
    return (soup.title.string or "").strip() if soup.title else ""


def _links(soup, todos: bool = False) -> list[str]:
    vistos: list[str] = []
    for a in soup.find_all("a", href=True):
        h = a["href"].split("?")[0].split("#")[0].strip()
        if not h or h.startswith(("javascript", "mailto", "tel")):
            continue
        if h not in vistos:
            vistos.append(h)
    if todos:
        return vistos[:60]
    chave = [h for h in vistos if re.search(r"portal|aluno|painel|frequ|logout|sair|perfil|matric|home", h, re.I)]
    return (chave or vistos)[:25]


async def _diagnostico(c: httpx.AsyncClient, soup_portal: BeautifulSoup) -> None:
    """Só registra no log (sem valores de cookie, sem senha) para descobrir onde o portal está."""
    try:
        home = await c.get("/")
        soup_home = BeautifulSoup(home.text, "lxml")
        log.warning("Cajuí HOME: status=%s url=%s titulo=%r", home.status_code, home.url, _titulo(soup_home))
        log.warning("Cajuí LINKS home (todos): %s", _links(soup_home, todos=True))
        log.warning("Cajuí LINKS portal: %s", _links(soup_portal))
        log.warning("Cajuí textos da página do portal: %s",
                    [t.get_text(" ", strip=True)[:80] for t in soup_portal.select("h1,h2,h3")[:4]])
        log.warning("Cajuí cookies na sessão: %s", sorted({ck.name for ck in c.cookies.jar}))
    except Exception as e:  # diagnóstico nunca pode quebrar o app
        log.warning("Cajuí diagnóstico falhou: %r", e)


async def fazer_login(usuario: str, senha: str) -> list[dict] | None:
    """Devolve os cookies da sessão do Cajuí, ou None se as credenciais forem inválidas."""
    try:
        async with _client() as c:
            r = await c.get("/cajui/login")
            tag = BeautifulSoup(r.text, "lxml").find("input", {"name": "_csrf"})
            if not tag:
                log.warning("Cajuí GET login: status=%s server=%s corpo=%r", r.status_code,
                            r.headers.get("server"), " ".join(r.text.split())[:300])
                raise CajuiIndisponivel(f"Sem formulário de login (HTTP {r.status_code})")

            r = await c.post("/cajui/login", data={
                "_csrf": tag["value"],
                "LoginForm[username]": usuario,
                "LoginForm[password]": senha,
                "login-button": "",
            })
            if r.status_code in (403, 429, 503):
                raise CajuiIndisponivel(f"HTTP {r.status_code}")
            if "loginform-username" in r.text:
                return None
            cookies = _exportar_cookies(c)
            log.warning("Cajuí login OK: status=%s url=%s cookies=%s", r.status_code, r.url,
                        [(k["name"], k["path"]) for k in cookies])
            return cookies
    except httpx.HTTPError as e:
        log.warning("Cajuí erro de rede: %r", e)
        raise CajuiIndisponivel(str(e)) from e


async def _achar_painel(c: httpx.AsyncClient):
    """Devolve (resposta, soup) da primeira página candidata que contém disciplinas."""
    global _painel_ok
    ordem = ([_painel_ok] if _painel_ok else []) + [p for p in CANDIDATAS if p != _painel_ok]
    ultima = None
    for path in ordem:
        r = await c.get(path)
        soup = BeautifulSoup(r.text, "lxml")
        n = len(soup.select(".sanfona"))
        log.warning("Cajuí tentativa %s: status=%s url=%s titulo=%r sanfona=%s",
                    path, r.status_code, r.url, _titulo(soup), n)
        if "/login" in str(r.url) or "loginform-username" in r.text:
            raise SessaoExpirada()
        if n:
            _painel_ok = path
            return r, soup
        ultima = (r, soup)
    return ultima


async def pegar_dados(cookies) -> list[dict]:
    try:
        async with _client(cookies) as c:
            r, soup = await _achar_painel(c)
            meta = soup.find("meta", {"name": "csrf-token"})
            sanfonas = soup.select(".sanfona")
            if not sanfonas:
                await _diagnostico(c, soup)
                raise CajuiIndisponivel("Nenhuma disciplina encontrada no portal")
            if not meta:
                raise SessaoExpirada()
            csrf = meta["content"]

            materias = []
            for el in sanfonas:
                b = el.find("b")
                materias.append({
                    "id": el.get("parametro"), "oferta": el.get("oferta"),
                    "nome": b.text.strip() if b else "Disciplina",
                })

            sem = asyncio.Semaphore(MAX_WORKERS)
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-Token": csrf,
            }

            async def uma(m: dict) -> dict:
                async with sem:
                    r = await c.post(
                        "/portal/aluno/painel/get-informacoes-matricula",
                        headers=headers,
                        data={"matricula_id": m["id"], "oferta_id": m["oferta"]},
                    )
                mp = re.search(r"(\d+) Presenças", r.text)
                mf = re.search(r"(\d+) Faltas", r.text)
                pres = int(mp.group(1)) if mp else 0
                falt = int(mf.group(1)) if mf else 0
                total = pres + falt
                pct = (pres / total * 100) if total else 100.0
                return {"nome": m["nome"], "presencas": pres, "faltas": falt,
                        "total": total, "percentual": round(pct, 1)}

            return list(await asyncio.gather(*(uma(m) for m in materias)))
    except httpx.HTTPError as e:
        log.warning("Cajuí erro de rede: %r", e)
        raise CajuiIndisponivel(str(e)) from e