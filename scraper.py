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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class SessaoExpirada(Exception):
    pass


class CajuiIndisponivel(Exception):
    pass


def _client(cookies: dict | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE,
        cookies=cookies,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
        timeout=TIMEOUT,
        follow_redirects=True,
    )


async def fazer_login(usuario: str, senha: str) -> dict | None:
    try:
        async with _client() as c:
            r = await c.get("/cajui/login")
            tag = BeautifulSoup(r.text, "lxml").find("input", {"name": "_csrf"})
            log.warning("Cajuí GET login: status=%s server=%s corpo=%r",
            r.status_code, r.headers.get("server"), " ".join(r.text.split())[:300])
            if not tag:
                raise CajuiIndisponivel(
                    f"Sem formulário de login (HTTP {r.status_code})"
                )

            r = await c.post(
                "/cajui/login",
                data={
                    "_csrf": tag["value"],
                    "LoginForm[username]": usuario,
                    "LoginForm[password]": senha,
                    "login-button": "",
                },
            )
            log.warning(
                "Cajuí POST login: status=%s url=%s tem_form=%s",
                r.status_code,
                r.url,
                "loginform-username" in r.text,
            )
            if r.status_code in (403, 429, 503):
                raise CajuiIndisponivel(f"HTTP {r.status_code}")
            if "loginform-username" in r.text:
                return None
            return {ck.name: ck.value for ck in c.cookies.jar}
    except httpx.HTTPError as e:
        log.warning("Cajuí erro de rede: %r", e)
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
                materias.append(
                    {
                        "id": el.get("parametro"),
                        "oferta": el.get("oferta"),
                        "nome": b.text.strip() if b else "Disciplina",
                    }
                )

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
                return {
                    "nome": m["nome"],
                    "presencas": pres,
                    "faltas": falt,
                    "total": total,
                    "percentual": round(pct, 1),
                }

            return list(await asyncio.gather(*(uma(m) for m in materias)))
    except httpx.HTTPError as e:
        raise CajuiIndisponivel(str(e)) from e
