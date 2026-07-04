"""Configuração central do Bot de Cartões."""
import os
from dotenv import load_dotenv

load_dotenv()


def _f(nome, padrao):
    try:
        return float(os.getenv(nome, padrao))
    except ValueError:
        return padrao


# ── Fontes de dados ───────────────────────────────────────────────────────────
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")     # api-football.com (grátis 100/dia)
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

BET365_COOKIE = os.getenv("BET365_COOKIE", "")           # opcional — odds ao vivo
BET365_USER_AGENT = os.getenv(
    "BET365_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
)

# Fonte de dados:
#   "hibrido"     -> Copa via API-Football + clubes via ESPN (recomendado)
#   "apifootball" -> só Copa do Mundo (tem por jogador), 100 req/dia
#   "espn"        -> só clubes (Premier, LaLiga, Europa, Champions...), SEM LIMITE
FONTE_FALTAS = os.getenv("FONTE_FALTAS", "hibrido")

# Ligas da ESPN a vigiar (códigos ESPN). Sem limite de cota, pode pôr várias.
LIGAS_ESPN = [s.strip() for s in os.getenv(
    "LIGAS_ESPN",
    "uefa.europa,uefa.champions,eng.1,esp.1,ita.1,ger.1,fra.1"
).split(",") if s.strip()]

# ── Notificações ───────────────────────────────────────────────────────────────
CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE", "")
CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ── Regras do sinal ────────────────────────────────────────────────────────────
PROB_MINIMA = _f("PROB_MINIMA", 0.40)         # prob mínima de CARTÃO p/ avisar
PROB_MINIMA_CHUTES = _f("PROB_MINIMA_CHUTES", 0.50)  # prob mínima de CHUTES A GOL
META_CHUTES = int(_f("META_CHUTES", 1))       # mercado: N+ chutes a gol (1 = mais fácil)
EV_MINIMO = _f("EV_MINIMO", 0.05)         # se tiver odd, valor mínimo
MIN_FALTAS = int(_f("MIN_FALTAS", 2))     # só olha quem já fez X faltas
INTERVALO_SEG = int(_f("INTERVALO_SEG", 480))      # varre a cada N s COM jogo relevante
INTERVALO_OCIOSO = int(_f("INTERVALO_OCIOSO", 3600))  # sem jogo: economiza cota (1 h)
# No modo híbrido: de quanto em quanto a API-Football é chamada (só com Copa ao vivo)
API_FOOTBALL_INTERVALO = int(_f("API_FOOTBALL_INTERVALO", 600))  # 10 min

# Só gasta cota (chamada de jogadores) em jogos destas competições.
# Vazio = todas (gasta MUITO). Substrings do nome da liga, em minúsculo.
LIGAS_FILTRO = [s.strip().lower() for s in
                os.getenv("LIGAS_FILTRO", "world cup").split(",") if s.strip()]

# Média de amarelos/jogo de um árbitro "neutro" (referência do modelo)
ARBITRO_MEDIA_PADRAO = _f("ARBITRO_MEDIA_PADRAO", 3.8)

# Tempo (em horas) para limpar mensagens antigas do canal de sinais
DISCORD_CLEAN_HOURS = int(_f("DISCORD_CLEAN_HOURS", 24))

