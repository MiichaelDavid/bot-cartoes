"""
Fonte de dados ao vivo: API-Football (api-football.com) — oficial, estável.
Plano grátis: 100 requisições/dia. Tem faltas e cartões por jogador.

Endpoints usados:
  GET /fixtures?live=all           -> jogos ao vivo (placar, minuto, árbitro)
  GET /fixtures/players?fixture=ID -> stats por jogador (faltas, cartões, posição)
"""
import requests
import logging
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.config import API_FOOTBALL_KEY, API_FOOTBALL_BASE

logger = logging.getLogger(__name__)


def _get(endpoint: str, params: dict) -> list:
    if not API_FOOTBALL_KEY:
        logger.warning("API_FOOTBALL_KEY não configurada no .env")
        return []
    try:
        r = requests.get(
            f"{API_FOOTBALL_BASE}{endpoint}",
            headers={"x-apisports-key": API_FOOTBALL_KEY},
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            logger.error(f"API-Football erro: {data['errors']}")
        return data.get("response", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"API-Football falhou: {e}")
        return []


def jogos_ao_vivo(filtro_nomes: list = None) -> list:
    """Lista jogos ao vivo, filtrando por nome da competição (economiza cota)."""
    resp = _get("/fixtures", {"live": "all"})
    jogos = []
    for f in resp:
        fx, liga, teams, goals = f["fixture"], f["league"], f["teams"], f["goals"]
        if filtro_nomes and not any(s in liga["name"].lower() for s in filtro_nomes):
            continue
        jogos.append({
            "id": fx["id"],
            "liga": liga["name"],
            "minuto": (fx.get("status") or {}).get("elapsed") or 0,
            "arbitro": fx.get("referee") or "?",
            "time_casa": teams["home"]["name"],
            "time_fora": teams["away"]["name"],
            "placar": f"{goals['home']}-{goals['away']}",
        })
    return jogos


def jogadores_do_jogo(fixture_id: int) -> list:
    """Stats por jogador de um jogo: faltas cometidas, cartões, posição, minutos."""
    resp = _get("/fixtures/players", {"fixture": fixture_id})
    jogadores = []
    for time in resp:
        for p in time.get("players", []):
            st = (p.get("statistics") or [{}])[0]
            jogos_st = st.get("games") or {}
            faltas = (st.get("fouls") or {}).get("committed")
            cartoes = (st.get("cards") or {})
            chutes = (st.get("shots") or {})
            jogadores.append({
                "nome": p["player"]["name"],
                "posicao": jogos_st.get("position") or "",
                "minutos": jogos_st.get("minutes") or 0,
                "faltas": faltas or 0,
                "chutes_gol": chutes.get("on") or 0,
                "amarelos": cartoes.get("yellow") or 0,
                "amarelo": (cartoes.get("yellow") or 0) > 0,
                "vermelho": (cartoes.get("red") or 0) > 0,
            })
    return jogadores
