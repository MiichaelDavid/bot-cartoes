# Bot de Cartões ⚽🟨

Monitora jogos **ao vivo**, calcula a **probabilidade de cada jogador levar cartão**
(faltas + perfil do árbitro + posição + tempo restante) e manda o **sinal no seu
WhatsApp** automaticamente.

> ⚠️ É uma **estimativa heurística** pra te ajudar a ler o jogo — não é garantia
> de lucro. O modelo é mais simples que o da casa de aposta.

## Como funciona
```
Jogos ao vivo  ──► API-Football (estável)  ou  SofaScore (Playwright, granular)
                         │ faltas por jogador, minuto, posição, cartões
                         ▼
              Modelo de probabilidade de cartão  (cartoes.py)
                         ▼
        prob ≥ limiar  ──►  sinal formatado  ──►  WhatsApp (CallMeBot)
```

## Setup (3 passos)

### 1. Instalar
```bash
cd "Bot Cartoes"
pip install -r requirements.txt
copy .env.example .env
```

### 2. WhatsApp (CallMeBot, grátis)
Siga https://www.callmebot.com/blog/free-api-whatsapp-messages/ → você recebe uma
API key. Preencha no `.env`: `CALLMEBOT_PHONE` (com DDD, ex. 5511…) e `CALLMEBOT_APIKEY`.

### 3. Fonte de dados
- **Opção A — API-Football (recomendada):** crie conta grátis em
  https://www.api-football.com/ (100 req/dia), cole a chave em `API_FOOTBALL_KEY`.
  Deixe `FONTE_FALTAS=apifootball`.
- **Opção B — SofaScore (faltas por jogador mais granulares):** `FONTE_FALTAS=sofascore`,
  e instale o navegador: `playwright install chromium`. Roda melhor no seu PC.

## Rodar
```bash
py monitor.py
```
Ele varre os jogos ao vivo a cada `INTERVALO_SEG` e te manda no WhatsApp quem
passar de `PROB_MINIMA`. Testar um sinal isolado: `py bot.py`.

## Ajustes (no .env)
| Variável | O quê |
|---|---|
| `PROB_MINIMA` | prob mínima de cartão pra avisar (padrão 0.40) |
| `MIN_FALTAS` | só olha quem já fez X faltas (padrão 2) |
| `INTERVALO_SEG` | de quanto em quanto varre (padrão 60s) |

## Status / a validar
- ✅ Modelo, WhatsApp, montador de sinal e loop: prontos e rodando.
- ⏳ Captura ao vivo precisa ser validada numa **partida em andamento** (foi
  construída de madrugada, sem jogos no ar). A fonte SofaScore é não-oficial e
  pode quebrar quando o site mudar.
