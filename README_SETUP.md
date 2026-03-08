# ROP Odds Mapping System
## Sistema de Mapeamento de Odds — ROP Soluções / DP Sports

Sistema automatizado de coleta, análise e alerta de odds para futebol.
Compara as odds da ROP/DP Sports com 9 concorrentes e gera relatórios
de inteligência competitiva enviados via Telegram.

---

## Instalação Rápida

### 1. Requisitos
- Python 3.11+
- Google Chrome ou Chromium (para o scraper)

### 2. Instalar dependências
```bash
cd ropodds
pip install -r requirements.txt
playwright install chromium
```

### 3. Configurar o Telegram Bot
```bash
python setup_telegram.py
```
Ou configure manualmente:
1. Crie um bot com @BotFather no Telegram
2. Adicione o bot ao grupo desejado
3. Copie o `.env.example` para `.env` e preencha:
```bash
cp .env.example .env
# Edite o .env com seu token e chat_id
```

### 4. Configurar os sites concorrentes
Edite `config/sites.yaml` com as URLs dos concorrentes.

---

## Como Usar

### Modo Automático (Scheduler)
Roda análises nos horários configurados (09:00, 14:00, 17:00, 19:00):
```bash
python main.py
```

### Rodar Análise Agora
```bash
python main.py --run-now
python main.py --run-now --date 2026-03-08
```

### Modo Manual (colar dados)
```bash
python main.py --manual
```
Ou a partir de um arquivo:
```bash
python main.py --manual-file dados_hoje.txt
```

### Dashboard Web
```bash
python main.py --dashboard
# Acesse http://localhost:5000
```

### Testar Telegram
```bash
python main.py --test-telegram
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
├── requirements.txt        # Dependências Python
├── setup_telegram.py       # Configurador do Telegram
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
│   ├── app.py              # Servidor web Flask
│   └── templates/
│       └── index.html      # Dashboard HTML
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
