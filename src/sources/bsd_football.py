"""
Fonte de dados: BSD (Bzzoiro Sports Data) — 100% GRÁTIS, SEM LIMITES.

Cobre 30+ ligas com odds reais de 17+ casas de apostas, stats por
jogador, ML predictions, lineups, lesões, xG.

Registro gratuito: https://sports.bzzoiro.com/register/
API Key no .env: BSD_TOKEN=sua_chave

Endpoints usados:
  /api/events/          -> partidas com odds (1X2, O/U, BTTS, Player Props)
  /api/player-stats/    -> estatísticas por jogador por partida
  /api/players/         -> perfis de jogadores
  /api/predictions/     -> ML predictions CatBoost
"""
import logging
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import requests

logger = logging.getLogger(__name__)
BASE = "https://sports.bzzoiro.com/api"
_TOKEN = os.getenv("BSD_TOKEN", "")


def _headers():
    if not _TOKEN:
        logger.warning("BSD_TOKEN não configurado no .env (registre em https://sports.bzzoiro.com/register/)")
        return {}
    return {"Authorization": f"Token {_TOKEN}"}


def _get(caminho: str, params: dict = None) -> dict:
    if not _TOKEN:
        return {}
    try:
        r = requests.get(f"{BASE}{caminho}", headers=_headers(), params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"BSD {caminho} falhou: {e}")
        return {}


def ligas_disponiveis() -> list:
    """Lista ligas disponíveis na BSD."""
    data = _get("/leagues/")
    return data.get("results", []) if "results" in data else data.get("data", [])


def proximos_eventos(league: str = None, dias: int = 3) -> list:
    """Retorna eventos futuros com odds reais (1X2, O/U, BTTS)."""
    from datetime import datetime, timedelta
    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    fim = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d")
    params = {"date_from": hoje, "date_to": fim, "status": "upcoming"}
    if league:
        params["league"] = league
    data = _get("/events/", params)
    return data.get("results", []) if "results" in data else data.get("data", [])


def odds_do_jogo(event_id) -> dict:
    """Retorna odds detalhadas de um evento específico."""
    data = _get(f"/events/{event_id}/")
    if not data:
        return {}
    ev = data.get("data", data)
    return {
        "odd_h": ev.get("odds_home"),
        "odd_d": ev.get("odds_draw"),
        "odd_a": ev.get("odds_away"),
        "odds_over_under": {
            "over": ev.get("odds_over"),
            "under": ev.get("odds_under"),
            "linha": ev.get("odds_line"),
        },
        "odds_btts": {
            "sim": ev.get("odds_btts_yes"),
            "nao": ev.get("odds_btts_no"),
        },
        "odds_player_props": ev.get("player_props"),
    }


def player_stats(event_id: int = None, player_id: int = None) -> list:
    """Stats por jogador em uma partida (139k+ registros gratuitos)."""
    params = {}
    if event_id:
        params["event"] = event_id
    if player_id:
        params["player"] = player_id
    data = _get("/player-stats/", params)
    return data.get("results", []) if "results" in data else data.get("data", [])


def player_profile(nome: str = None, team: str = None) -> list:
    """Busca perfil de jogadores."""
    params = {}
    if nome:
        params["search"] = nome
    if team:
        params["team"] = team
    data = _get("/players/", params)
    return data.get("results", []) if "results" in data else data.get("data", [])


def extracao_rapida(evento: dict) -> dict:
    """Extrai dados relevantes de um evento da BSD para nosso modelo."""
    return {
        "id": evento.get("id"),
        "liga": evento.get("league_name", evento.get("league", "")),
        "time_casa": evento.get("home_team", ""),
        "time_fora": evento.get("away_team", ""),
        "data": evento.get("kickoff", evento.get("date", "")),
        "minuto": evento.get("minute", 0),
        "placar": f"{evento.get('home_score','?')}-{evento.get('away_score','?')}",
        "odds": odds_do_jogo(evento.get("id")),
        "status": evento.get("status", "upcoming"),
    }
