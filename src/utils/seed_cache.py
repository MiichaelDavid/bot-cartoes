"""
Utilitário para alimentar o cache de jogadores com dados históricos.

Busca partidas concluídas via ESPN (Copa + Brasileirão) e salva no cache
de jogadores para que comandos como /sinais funcionem imediatamente.
"""
import sys
import os
import requests
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.pre_match.cache_jogadores as cache_jogadores

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("seed-cache")

def obter_jogos_cacheados() -> set:
    cache = cache_jogadores._carregar()
    jogos_ids = set()
    for jogador_dados in cache.values():
        for partida in jogador_dados.get("partidas", []):
            if "jogo_id" in partida:
                jogos_ids.add(str(partida["jogo_id"]))
    return jogos_ids

def seed_liga(endpoint: str, dates_range: str):
    logger.info(f"Buscando eventos para {endpoint} ({dates_range})...")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{endpoint}/scoreboard"
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        r = requests.get(url, params={"dates": dates_range, "limit": 200}, headers=H, timeout=20).json()
    except Exception as e:
        logger.error(f"Erro ao obter scoreboard para {endpoint}: {e}")
        return

    events = r.get("events", [])
    logger.info(f"Total de eventos encontrados: {len(events)}")
    
    completed_events = [e for e in events if e.get("competitions")[0].get("status").get("type").get("state") == "post"]
    logger.info(f"Eventos concluídos a processar: {len(completed_events)}")

    jogos_existentes = obter_jogos_cacheados()
    logger.info(f"Jogos já catalogados no cache atualmente: {len(jogos_existentes)}")

    novos_adicionados = 0

    for idx, e in enumerate(completed_events):
        jid = str(e.get("id"))
        if jid in jogos_existentes:
            logger.debug(f"Jogo {jid} já está no cache, pulando.")
            continue

        comp = e.get("competitions")[0]
        cs = comp.get("competitors", [])
        home = next((c for c in cs if c.get("homeAway") == "home"), {})
        away = next((c for c in cs if c.get("homeAway") == "away"), {})
        
        time_casa = home.get("team", {}).get("displayName", "?")
        time_fora = away.get("team", {}).get("displayName", "?")
        
        logger.info(f"[{idx+1}/{len(completed_events)}] Baixando stats de: {time_casa} x {time_fora} (ID: {jid})")
        
        try:
            summary_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{endpoint}/summary"
            sum_data = requests.get(summary_url, params={"event": jid}, headers=H, timeout=20).json()
            
            rosters = sum_data.get("rosters", [])
            if not rosters:
                logger.warning(f"Sem rosters disponíveis para o jogo {jid}")
                continue
                
            jogadores_casa = []
            jogadores_fora = []
            
            for roster_team in rosters:
                is_home = roster_team.get("homeAway") == "home"
                team_list = jogadores_casa if is_home else jogadores_fora
                
                for p in roster_team.get("roster", []):
                    st = {s.get("abbreviation"): s.get("value") for s in (p.get("stats") or [])}
                    if not st:
                        continue
                    pos = (p.get("position") or {}).get("abbreviation") or ""
                    team_list.append({
                        "nome": p.get("athlete", {}).get("displayName", "?"),
                        "posicao": pos.split("-")[0],
                        "faltas": int(st.get("FC") or 0),
                        "chutes_gol": int(st.get("SOG") or 0),
                        "amarelos": int(st.get("YC") or 0),
                        "gols": int(st.get("G") or 0),
                    })
            
            if jogadores_casa or jogadores_fora:
                cache_jogadores.adicionar_partida(
                    jid, time_casa, time_fora,
                    jogadores_casa, jogadores_fora,
                    minuto_final=90
                )
                novos_adicionados += 1
        except Exception as err:
            logger.error(f"Erro ao processar jogo {jid}: {err}")

    logger.info(f"Fim do processamento para {endpoint}. {novos_adicionados} novos jogos adicionados.")

if __name__ == "__main__":
    # Seed Copa do Mundo 2026 (De 11 de Junho até hoje)
    seed_liga("fifa.world", "20260611-20260704")
    # Seed Brasileirão 2026 (De 1º de Abril até hoje)
    seed_liga("bra.1", "20260401-20260704")
