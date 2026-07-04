"""
Cache de estatísticas dos jogadores ao longo do torneio.

Acumula stats de cada partida ao vivo (via ESPN) e persiste em
player_stats_cache.json. Alimentado pelo monitor_copa.py e
consultado pelo analisador pré-jogo.

Estrutura:
{
    "jogador_nome": {
        "posicao": "ST",
        "time": "Brasil",
        "partidas": [
            {"jogo_id": 123, "adversario": "Argentina", "faltas": 3,
             "amarelos": 1, "chutes_gol": 2, "gols": 0, "minutos": 90}
        ],
        "ultima_atualizacao": "2026-07-04T14:00:00"
    },
    ...
}
"""
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
_CAMINHO = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "player_stats_cache.json"
))


_dados_cache = None


def limpar_cache_memoria():
    global _dados_cache
    _dados_cache = None


def _carregar() -> dict:
    global _dados_cache
    if _dados_cache is not None:
        return _dados_cache
    if not os.path.exists(_CAMINHO):
        return {}
    try:
        with open(_CAMINHO, "r", encoding="utf-8") as f:
            _dados_cache = json.load(f)
            return _dados_cache
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Cache corrompido, resetando: {e}")
        return {}


def _salvar(cache: dict):
    global _dados_cache
    _dados_cache = cache
    with open(_CAMINHO, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def adicionar_partida(jogo_id, time_casa, time_fora, jogadores_time_casa,
                      jogadores_time_fora, minuto_final: int = 90):
    """Adiciona stats de uma partida concluída ao cache."""
    cache = _carregar()
    ts = datetime.now().isoformat(timespec="seconds")

    for jogadores, time in [(jogadores_time_casa, time_casa),
                             (jogadores_time_fora, time_fora)]:
        adv = time_fora if time == time_casa else time_casa
        for jg in jogadores:
            nome = jg["nome"]
            if nome not in cache:
                cache[nome] = {
                    "posicao": jg.get("posicao", ""),
                    "time": time,
                    "partidas": [],
                }
            cache[nome]["partidas"].append({
                "jogo_id": jogo_id,
                "adversario": adv,
                "faltas": jg.get("faltas", 0),
                "amarelos": jg.get("amarelos", 0),
                "chutes_gol": jg.get("chutes_gol", 0),
                "gols": jg.get("gols", 0),
                "minutos": minuto_final,
            })
            cache[nome]["ultima_atualizacao"] = ts

    _salvar(cache)
    n = len(jogadores_time_casa) + len(jogadores_time_fora)
    logger.info(f"Cache atualizado: {n} jogadores de {time_casa} vs {time_fora}")


def medias_jogador(nome: str, ultimas_n: int = 5) -> dict:
    """Retorna médias por 90 min do jogador (últimas N partidas)."""
    cache = _carregar()
    dados = cache.get(nome)
    if not dados or not dados.get("partidas"):
        return None

    partidas = dados["partidas"][-ultimas_n:]
    total_min = sum(p["minutos"] or 90 for p in partidas)
    if total_min == 0:
        return None

    fator = 90.0 / total_min
    return {
        "nome": nome,
        "posicao": dados["posicao"],
        "time": dados["time"],
        "n_partidas": len(partidas),
        "faltas_por_90": sum(p["faltas"] for p in partidas) * fator,
        "amarelos_por_90": sum(p["amarelos"] for p in partidas) * fator,
        "chutes_gol_por_90": sum(p["chutes_gol"] for p in partidas) * fator,
        "gols_por_90": sum(p["gols"] for p in partidas) * fator,
        "minutos_totais": total_min,
    }


def top_jogadores(time: str = None, n: int = 10) -> list:
    """Retorna os N jogadores com mais destaque (gols, chutes, cartões)."""
    cache = _carregar()
    resultados = []
    for nome, dados in cache.items():
        if time and dados.get("time") != time:
            continue
        med = medias_jogador(nome, ultimas_n=5)
        if med and med["minutos_totais"] >= 45:
            resultados.append(med)
    return sorted(resultados, key=lambda x: x["gols_por_90"], reverse=True)[:n]


def todos_jogadores_do_time(time: str) -> list:
    """Retorna médias de todos os jogadores de um time."""
    cache = _carregar()
    resultados = []
    for nome, dados in cache.items():
        if dados.get("time") != time:
            continue
        med = medias_jogador(nome, ultimas_n=5)
        if med:
            resultados.append(med)
    return resultados


def resumo_cache():
    """Resumo do cache para debug."""
    cache = _carregar()
    times = set(d["time"] for d in cache.values())
    total = len(cache)
    pts = sum(len(d.get("partidas", [])) for d in cache.values())
    return {
        "jogadores": total,
        "partidas_registradas": pts,
        "times": sorted(times),
    }
