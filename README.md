# Monitor Cajui

Dashboard web para monitoramento de frequência acadêmica do sistema Cajui (IFNMG).

## Sobre o Projeto

O **Monitor Cajui** é uma aplicação web desenvolvida para facilitar o acompanhamento da frequência escolar. A aplicação realiza a extração de dados do sistema acadêmico, calcula os índices de presença e identifica disciplinas com frequência inferior a 75%.

O projeto possui uma interface responsiva, com abordagem Mobile-First e suporte a temas claro e escuro.

## Funcionalidades

- Login manual com usuário e senha.
- Extração de dados em tempo real via Web Scraping.
- Cálculo automático da frequência geral e por disciplina.
- Alertas visuais para disciplinas abaixo de 75%.
- Dashboard responsivo com foco em dispositivos móveis.
- Suporte a Dark Mode.
- Interface minimalista inspirada no Vercel e Linear.

## Como rodar localmente

**1. Clone o repositório**

    git clone https://github.com/SEU-USUARIO/monitor-cajui.git
    cd monitor-cajui

**2. Crie e ative um ambiente virtual**

    python -m venv venv

Windows:

    venv\Scripts\activate

Linux:

    source venv/bin/activate

**3. Instale as dependências**

    pip install fastapi uvicorn requests beautifulsoup4 jinja2

**4. Execute a aplicação**

    uvicorn main:app --reload

Acesse: http://127.0.0.1:8000

## Deploy

O projeto foi desenvolvido com foco em compatibilidade com a **Vercel**, utilizando FastAPI no backend e tecnologias web na interface.

## Aviso Legal

Este é um projeto independente, desenvolvido para uso pessoal e fins educacionais.

Não possui vínculo oficial, parceria ou associação com o Instituto Federal do Norte de Minas Gerais (IFNMG) ou com o sistema acadêmico Cajui.

O projeto não é responsável por alterações, indisponibilidades ou inconsistências nos dados fornecidos pelo sistema original.