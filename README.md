# Monitor Cajui

Dashboard (PWA) para acompanhar a frequência no Cajuí (IFNMG). Projeto independente, sem vínculo oficial com o IFNMG.

## Como funciona
- **Sessão sem estado:** após o login, os cookies do Cajuí são criptografados (Fernet) e guardados no cookie do navegador. O servidor não guarda nada; reiniciar ou "dormir" não derruba o login. A senha nunca é armazenada.
- **Scraping paralelo** (httpx + asyncio), com cache de 5 min e limite de concorrência (`MAX_WORKERS`).
- **PWA:** instalável, abre na hora com o último resultado salvo no aparelho e atualiza em seguida.

## Rodar localmente
    python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env    # gere a FERNET_KEY (comando no próprio arquivo)
    uvicorn main:app --reload

## Deploy no Render (grátis)
1. Suba o repositório no GitHub (o `.env` fica fora, via `.gitignore`).
2. Render → New → Blueprint → selecione o repositório (usa o `render.yaml`).
3. Em Environment, defina `FERNET_KEY` (mesmo comando do `.env.example`).
4. (Opcional) Aponte um monitor de uptime (ex.: UptimeRobot) para `/health` a cada 5-10 min para reduzir cold starts.

O plano grátis dorme após 15 min sem tráfego; a primeira abertura depois disso pode levar cerca de 1 min.

## Instalar no celular
Android/Chrome: menu → "Instalar app". iOS/Safari: Compartilhar → "Adicionar à Tela de Início".
