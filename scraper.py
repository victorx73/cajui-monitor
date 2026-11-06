"""Scraping assíncrono do Cajuí (httpx + BeautifulSoup)."""
import asyncio
import os
import re

import httpx
from bs4 import BeautifulSoup

BASE = "https://cajui.ifnmg.edu.br"
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "20"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class SessaoExpirada(Exception):
    pass


class CajuiIndisponivel(Exception):
    pass


def _client(cookies: dict | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE, cookies=cookies, headers={"User-Agent": UA},
        timeout=TIMEOUT, follow_redirects=True,
    )


async def fazer_login(usuario: str, senha: str) -> dict | None:
    """Devolve os cookies da sessão do Cajuí, ou None se as credenciais forem inválidas."""
    try:
        async with _client() as c:
            r = await c.get("/cajui/login")
            tag = BeautifulSoup(r.text, "lxml").find("input", {"name": "_csrf"})
            if not tag:
                raise CajuiIndisponivel("Formulário de login não encontrado.")
            r = await c.post("/cajui/login", data={
                "_csrf": tag["value"],
                "LoginForm[username]": usuario,
                "LoginForm[password]": senha,
                "login-button": "",
            })
            if "loginform-username" in r.text:
                return None
            return {ck.name: ck.value for ck in c.cookies.jar}
    except httpx.HTTPError as e:
        raise CajuiIndisponivel(str(e)) from e


async def pegar_dados(cookies: dict) -> list[dict]:
    try:
        async with _client(cookies) as c:
            r = await c.get("/portal")
            soup = BeautifulSoup(r.text, "lxml")
            meta = soup.find("meta", {"name": "csrf-token"})
            if "/login" in str(r.url) or not meta:
                raise SessaoExpirada()
            csrf = meta["content"]

            materias = []
            for el in soup.select(".sanfona"):
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
        raise CajuiIndisponivel(str(e)) from e
