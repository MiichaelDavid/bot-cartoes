"""
Fonte de dados: Copa do Mundo via ESPN — KEYLESS e SEM LIMITE diário.

Usa o mesmo endpoint da ESPN que as ligas de clube, mas com o código
"fifa.world". A ESPN cobre a Copa de 2026 em detalhes: faltas (FC),
cartões (YC/RC), chutes a gol (SOG) e posição POR JOGADOR.

NÃO precisa de API key. NÃO gasta cota.
"""
import re
import logging
import requests

logger = logging.getLogger(__name__)
_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _minuto(status: dict) -> int:
    dc = status.get("displayClock") or ""
    m = re.search(r"\d+", dc)
    return int(m.group()) if m else (status.get("clock") or 0)


def jogos_ao_vivo() -> list:
    """Retorna todos os jogos da Copa AO VIVO detectados pela ESPN."""
    try:
        sb = requests.get(f"{_BASE}/scoreboard", headers=_H, timeout=20).json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"ESPN Copa scoreboard falhou: {e}")
        return []
    jogos = []
    nome_competicao = (sb.get("leagues") or [{}])[0].get("name", "Copa do Mundo 2026")
    for e in sb.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        status = comp.get("status", {})
        if status.get("type", {}).get("state") != "in":
            continue
        cs = comp.get("competitors", [])
        home = next((c for c in cs if c.get("homeAway") == "home"), {})
        away = next((c for c in cs if c.get("homeAway") == "away"), {})
        jogos.append({
            "id": e.get("id"),
            "liga": nome_competicao,
            "minuto": _minuto(status),
            "time_casa": home.get("team", {}).get("displayName", "?"),
            "time_fora": away.get("team", {}).get("displayName", "?"),
            "placar": f"{home.get('score','?')}-{away.get('score','?')}",
            "arbitro": "?",
        })
    return jogos


def jogadores_do_jogo(event_id) -> list:
    """Faltas/cartões/chutes por JOGADOR num jogo da Copa via ESPN."""
    try:
        j = requests.get(f"{_BASE}/summary", params={"event": event_id},
                         headers=_H, timeout=25).json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"ESPN Copa summary {event_id} falhou: {e}")
        return []
    jogadores = []
    for t in j.get("rosters", []):
        for p in t.get("roster", []):
            st = {s.get("abbreviation"): s.get("value") for s in (p.get("stats") or [])}
            if not st:
                continue
            pos = (p.get("position") or {}).get("abbreviation") or ""
            jogadores.append({
                "nome": p.get("athlete", {}).get("displayName", "?"),
                "posicao": pos.split("-")[0],
                "minutos": 0,
                "faltas": int(st.get("FC") or 0),
                "chutes_gol": int(st.get("SOG") or 0),
                "amarelos": int(st.get("YC") or 0),
                "amarelo": (st.get("YC") or 0) > 0,
                "vermelho": (st.get("RC") or 0) > 0,
            })
    return jogadores
