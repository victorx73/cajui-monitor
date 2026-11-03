import os
import time
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Variável global para manter a sessão (simulando um banco de dados em memória)
sessions = {}

def fazer_login(usuario, senha):
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    # 1. Pega o token de login
    r = session.get("https://cajui.ifnmg.edu.br/cajui/login")
    soup = BeautifulSoup(r.text, 'html.parser')
    token = soup.find('input', {'name': '_csrf'})['value']
    
    # 2. Faz o login
    payload = {
        '_csrf': token,
        'LoginForm[username]': usuario,
        'LoginForm[password]': senha,
        'login-button': ''
    }
    r_login = session.post("https://cajui.ifnmg.edu.br/cajui/login", data=payload)
    
    if "loginform-username" in r_login.text:
        return None # Login falhou
        
    return session

def pegar_dados(session):
    r_painel = session.get("https://cajui.ifnmg.edu.br/portal")
    soup = BeautifulSoup(r_painel.text, 'html.parser')
    
    materias = []
    for el in soup.select('.sanfona'):
        matricula_id = el.get('parametro')
        oferta_id = el.get('oferta')
        nome = el.find('b').text.strip()
        materias.append({'id': matricula_id, 'oferta': oferta_id, 'nome': nome})
        
    token_csrf = soup.find('meta', {'name': 'csrf-token'})['content']
    
    dados_finais = []
    for m in materias:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': token_csrf
        }
        payload = {'matricula_id': m['id'], 'oferta_id': m['oferta']}
        r_freq = session.post("https://cajui.ifnmg.edu.br/portal/aluno/painel/get-informacoes-matricula", headers=headers, data=payload)
        
        # Extrai os números
        import re
        match_pres = re.search(r'(\d+) Presenças', r_freq.text)
        match_falt = re.search(r'(\d+) Faltas', r_freq.text)
        
        pres = int(match_pres.group(1)) if match_pres else 0
        falt = int(match_falt.group(1)) if match_falt else 0
        total = pres + falt
        pct = (pres / total * 100) if total > 0 else 100.0
        
        dados_finais.append({
            "nome": m['nome'], "presencas": pres, "faltas": falt, "total": total, "percentual": round(pct, 1)
        })
        
    return dados_finais

# --- Rotas ---

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def fazer_login_post(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    session = fazer_login(usuario, senha)
    if not session:
        return templates.TemplateResponse("login.html", {"request": request, "erro": "Usuário ou senha inválidos."})
    
    # Gera um ID de sessão simples (pode ser um UUID, mas para simplificar usamos o tempo)
    session_id = str(time.time())
    sessions[session_id] = session
    
    response = RedirectResponse(url="/painel", status_code=303)
    response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=86400) # 1 dia
    return response

@app.get("/painel", response_class=HTMLResponse)
def painel(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return RedirectResponse(url="/")
    
    session = sessions[session_id]
    try:
        dados = pegar_dados(session)
    except:
        return RedirectResponse(url="/logout")
        
    pres_total = sum(d['presencas'] for d in dados)
    aulas_total = sum(d['total'] for d in dados)
    geral = round((pres_total / aulas_total * 100), 1) if aulas_total > 0 else 100.0
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "dados": dados,
        "geral": geral,
        "atualizado": datetime.now().strftime("%H:%M"),
        "limite": 75.0,
        "erro": None,
        "atualizando": False
    })

@app.get("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/")
    response.delete_cookie("session_id")
    return response