"""
Fonte de dados: API escondida da ESPN — KEYLESS e SEM LIMITE diário.

Dá faltas cometidas (FC) e cartões (YC/RC) POR JOGADOR, ao vivo, para as
competições de CLUBES que a ESPN cobre em detalhe (Premier, La Liga, Serie A,
Bundesliga, Ligue 1, Champions, Europa League...) e também para a COPA DO MUNDO.

Para a Copa, use o módulo src/sources/copa.py (mesma ESPN, código fifa.world)
ou rode o monitor standalone: python src/monitor_copa.py
"""
import re
import logging
import requests

logger = logging.getLogger(__name__)
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _minuto(status: dict) -> int:
    dc = status.get("displayClock") or ""
    m = re.search(r"\d+", dc)
    return int(m.group()) if m else (status.get("clock") or 0)


def jogos_ao_vivo(ligas: list) -> list:
    """Jogos AO VIVO (state='in') nas ligas ESPN informadas. Sem custo de cota."""
    jogos = []
    for lg in ligas:
        try:
            sb = requests.get(f"{BASE}/{lg}/scoreboard", headers=H, timeout=20).json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"ESPN {lg} falhou: {e}")
            continue
        nome_liga = (sb.get("leagues") or [{}])[0].get("name", lg)
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
                "_lg": lg,
                "liga": nome_liga,
                "minuto": _minuto(status),
                "time_casa": home.get("team", {}).get("displayName", "?"),
                "time_fora": away.get("team", {}).get("displayName", "?"),
                "placar": f"{home.get('score','?')}-{away.get('score','?')}",
                "arbitro": "?",
            })
    return jogos


def copa_ao_vivo() -> bool:
    """Há jogo da Copa do Mundo ao vivo agora? (checado de graça na ESPN)."""
    try:
        sb = requests.get(f"{BASE}/fifa.world/scoreboard", headers=H, timeout=15).json()
    except requests.exceptions.RequestException:
        return False
    for e in sb.get("events", []):
        st = (e.get("competitions") or [{}])[0].get("status", {})
        if st.get("type", {}).get("state") == "in":
            return True
    return False


def jogadores_do_jogo(lg: str, event_id: str) -> list:
    """Faltas/cartões por jogador de um jogo (FC=faltas cometidas, YC=amarelo)."""
    try:
        j = requests.get(f"{BASE}/{lg}/summary", params={"event": event_id},
                         headers=H, timeout=25).json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"ESPN summary {event_id} falhou: {e}")
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
                "posicao": pos.split("-")[0],     # "CD-L" -> "CD"
                "minutos": 0,
                "faltas": int(st.get("FC") or 0),
                "chutes_gol": int(st.get("SOG") or 0),
                "amarelos": int(st.get("YC") or 0),
                "amarelo": (st.get("YC") or 0) > 0,
                "vermelho": (st.get("RC") or 0) > 0,
            })
    return jogadores
