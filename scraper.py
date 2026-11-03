import os
import re
import time
import json
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

def coletar_frequencia():
    disciplinas = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--window-position=-32000,-32000"])
        page = browser.new_page()

        # 1. Login
        page.goto("https://cajui.ifnmg.edu.br/cajui/login", timeout=30000)
        page.wait_for_selector("#loginform-username", timeout=15000)
        page.fill("#loginform-username", os.getenv("CAJUI_USER"))
        page.fill("#loginform-password", os.getenv("CAJUI_PASS"))
        
        try: page.evaluate("document.getElementById('loginform-rememberme').value = '1'")
        except: pass
            
        page.click('button[name="login-button"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # 2. Pega os IDs das matérias e o Token CSRF
        materias = page.evaluate("""() => {
            const elementos = document.querySelectorAll('.sanfona');
            const lista = [];
            elementos.forEach(el => {
                lista.push({
                    matricula_id: el.getAttribute('parametro'),
                    oferta_id: el.getAttribute('oferta'),
                    nome: el.querySelector('b').innerText
                });
            });
            return lista;
        }""")
        
        token = page.evaluate("document.querySelector('meta[name=\"csrf-token\"]').content")

        # 3. Busca a frequência de cada matéria
        for mat in materias:
            html = page.evaluate("""(args) => {
                return fetch('/portal/aluno/painel/get-informacoes-matricula', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-Token': args.token
                    },
                    body: `matricula_id=${args.matricula_id}&oferta_id=${args.oferta_id}`
                }).then(r => r.text());
            }""", {"token": token, "matricula_id": mat['matricula_id'], "oferta_id": mat['oferta_id']})

            match_pres = re.search(r'<span class="float-right badge label-success">(\d+) Presenças</span>', html)
            match_falt = re.search(r'<span class="float-right badge label-danger">(\d+) Faltas</span>', html)
            
            presencas = int(match_pres.group(1)) if match_pres else 0
            faltas = int(match_falt.group(1)) if match_falt else 0
            total = presencas + faltas
            percentual = (presencas / total * 100) if total > 0 else 100.0

            disciplinas.append({
                "nome": mat['nome'],
                "presencas": presencas,
                "faltas": faltas,
                "total": total,
                "percentual": round(percentual, 1)
            })
            time.sleep(0.5)

        browser.close()
    return disciplinas

if __name__ == "__main__":
    try:
        dados = coletar_frequencia()
        # Imprime o JSON para o app.py capturar
        print(json.dumps(dados))
    except Exception as e:
        print(json.dumps({"erro": str(e)}))