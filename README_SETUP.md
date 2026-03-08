# ROP Odds Mapping System
## Sistema de Mapeamento de Odds — ROP Soluções / DP Sports

Sistema automatizado de coleta, análise e alerta de odds para futebol.
Compara as odds da ROP/DP Sports com 9 concorrentes e gera relatórios
de inteligência competitiva enviados via Telegram.

**100% Online** — roda na nuvem sem instalar nada no seu computador.

---

## Deploy com 1 Clique no Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template?referralCode=ropodds)

### Passo a passo:

1. Clique no botão acima (ou acesse [railway.app](https://railway.app))
2. Faça login com sua conta GitHub
3. Clique **"New Project" → "Deploy from GitHub Repo"**
4. Selecione o repositório **ropodds**
5. Vá na aba **"Variables"** e adicione:

| Variável | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | (token do @BotFather) |
| `TELEGRAM_CHAT_ID` | (ID do grupo — veja instruções abaixo) |
| `API_KEY` | `ropodds2026` |
| `SCHEDULE_TIMES` | `09:00,14:00,17:00,19:00` |
| `TIMEZONE` | `America/Sao_Paulo` |

6. Clique **Deploy** — aguarde ~3 minutos
7. Railway gera um domínio automático (ex: `ropodds-production.up.railway.app`)

### Opção 2: Render

1. Crie uma conta em [render.com](https://render.com)
2. **New → Web Service → Connect GitHub**
3. Selecione o repositório
4. Runtime: **Docker**
5. Adicione as variáveis de ambiente (mesmas do Railway)
6. Clique **Create Web Service**

### Opção 3: Fly.io

```bash
# Instale o flyctl
curl -L https://fly.io/install.sh | sh
fly auth login
fly launch    # Responda as perguntas
fly secrets set TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx API_KEY=xxx
fly deploy
```

---

## Como Criar o Bot do Telegram

1. Abra o Telegram e procure **@BotFather**
2. Envie `/newbot`
3. Escolha um nome: `ROP Odds Alert`
4. Escolha um username: `rop_odds_alert_bot`
5. Copie o **token** que o BotFather enviar
6. Adicione o bot ao grupo desejado
7. Para pegar o **Chat ID** do grupo:
   - Envie uma mensagem no grupo
   - Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
   - Procure o campo `"chat":{"id":-XXXXX}` — esse é o Chat ID

---

## Como Usar

### Via Dashboard Web (recomendado)
Acesse a URL do seu deploy (ex: `https://ropodds.up.railway.app`):
- **/** — Dashboard com alertas, relatórios e histórico
- **/input** — Formulário para colar dados manualmente e gerar relatório

### Via API (webhook)
```bash
# Enviar dados manuais
curl -X POST https://SEU-DOMINIO/api/webhook/manual \
  -H "X-API-Key: SUA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data": "Jogo: Time A vs Time B\n...", "date": "2026-03-08"}'

# Disparar scraping automático
curl -X POST https://SEU-DOMINIO/api/webhook/scrape \
  -H "X-API-Key: SUA_API_KEY"

# Testar Telegram
curl -X POST https://SEU-DOMINIO/api/webhook/test-telegram \
  -H "X-API-Key: SUA_API_KEY"
```

### Execução Local (opcional)
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # Preencha com seus dados
python main.py         # Scheduler + Dashboard
```

---

## Formato de Dados Manuais

Se preferir coletar dados manualmente, use este formato:

```
Jogo: Atlético Madrid vs Real Sociedad
Campeonato: LaLiga
Horário: 14:30 BRT

# Odds 1X2 (Casa, Empate, Fora)
ROP: 1.54, 3.43, 4.18
ProSporte: 1.60, 3.30, 4.25
TeamBets: 1.65, 3.61, 4.47
VegasPrime: 1.62, 3.35, 4.30
MiamiBets: 1.63, 3.28, 4.20
TeamTop: 1.66, 3.40, 4.35
TMJBet: 1.61, 3.32, 4.28
MundoBets: 1.64, 3.38, 4.33
SportBetBrasil: 1.62, 3.30, 4.25
Fanáticos: 1.68, 3.36, 4.40

# Ambos Marcam (Sim, Não)
ROP: 1.55, 1.87

# Mais/Menos 2.5 Gols (Mais, Menos)
ROP: 1.59, 1.81
```

---

## Estrutura do Projeto

```
ropodds/
├── main.py                 # Ponto de entrada principal
├── models.py               # Modelos do banco de dados
├── Dockerfile              # Container para deploy cloud
├── docker-compose.yml      # Execução local com Docker
├── railway.toml            # Config Railway
├── fly.toml                # Config Fly.io
├── Procfile                # Config Render/Heroku
├── requirements.txt        # Dependências Python
├── .env.example            # Template de configuração
├── config/
│   ├── settings.py         # Configurações do sistema
│   └── sites.yaml          # Configuração dos sites
├── scrapers/
│   ├── base_scraper.py     # Classe base dos scrapers
│   ├── rop_scraper.py      # Scraper especializado para ROP
│   ├── generic_scraper.py  # Scraper genérico para concorrentes
│   ├── manual_input.py     # Parser de dados manuais
│   └── scraper_manager.py  # Orquestrador dos scrapers
├── analysis/
│   ├── odds_analyzer.py    # Engine de análise de odds
│   └── report_generator.py # Gerador de relatórios formatados
├── telegram_bot/
│   └── bot.py              # Integração com Telegram
├── dashboard/
│   ├── app.py              # Servidor web Flask + API webhooks
│   └── templates/
│       ├── index.html      # Dashboard principal
│       └── input.html      # Formulário de input manual
├── .github/workflows/
│   └── deploy-railway.yml  # CI/CD automático
├── data/                   # Banco de dados SQLite
└── logs/                   # Logs do sistema
```

---

## Regras de Análise

- **✅ Verde:** Odd da ROP é **mais de 3% superior** à média dos concorrentes
- **⚠️ Amarelo:** Odd da ROP é **mais de 3% inferior** à média dos concorrentes
- **➡️ Neutro:** Odd da ROP está dentro da faixa de ±3% da média

A média é calculada excluindo a ROP. Sites sem odds para um jogo são excluídos do cálculo.

---

## Concorrentes Monitorados

| Site | Status |
|------|--------|
| ROP/DP Sports | Principal |
| ProSporte | Concorrente |
| TeamBets | Concorrente |
| VegasPrime | Concorrente |
| MiamiBets | Concorrente |
| TeamTop | Concorrente |
| TMJBet | Concorrente |
| MundoBets | Concorrente |
| SportBetBrasil | Concorrente |
| Fanáticos Sportes | Concorrente |

---

## Horários de Execução

| Horário (BRT) | Objetivo |
|---|---|
| 09:00 | Abertura — mercados europeus e jogos do dia |
| 14:00 | Atualização — odds pré-jogo + jogos da tarde |
| 17:00 | Jogos da noite + análise dos jogos em andamento |
| 19:00 | Última verificação do dia |
