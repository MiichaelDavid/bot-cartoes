"""
Analisador PRÉ-JOGO (Copa + Clubes).

Gera sinais de cartão, chutes a gol e gols ANTES da partida começar,
baseado no histórico real dos jogadores (cache alimentado ao vivo).

COMPARA com ODDS REAIS quando disponíveis:
  - BSD (Bzzoiro): odds reais de 17+ casas, gratuito, sem limites
  - bet365: scraping opcional (requer cookie)
  - Fair odds: cálculo do modelo (sempre disponível como fallback)

Calcula EV (Valor Esperado) = (prob * odd_real) - 1
"""
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.pre_match.cache_jogadores import medias_jogador, todos_jogadores_do_time
from src.models.cartoes import probabilidade_cartao
from src.models.chutes import prob_chutes_gol
from src.models.gols import prob_gol

logger = logging.getLogger(__name__)


def _odds_reais(liga: str, time_casa: str, time_fora: str) -> dict:
    """
    Tenta buscar odds REAIS para o jogo.
    Retorna: { "odd_h": x, "odd_d": x, "odd_a": x, "fonte": "..." } ou vazio.
    """
    import src.sources.bsd_football as bsd
    if bsd._TOKEN:
        try:
            eventos = bsd.proximos_eventos()
            for ev in eventos:
                h = ev.get("home_team", "").lower()
                a = ev.get("away_team", "").lower()
                if (h in time_casa.lower() or time_casa.lower() in h) and \
                   (a in time_fora.lower() or time_fora.lower() in a):
                    odds = bsd.odds_do_jogo(ev.get("id"))
                    if odds.get("odd_h"):
                        return {**odds, "fonte": "BSD"}
        except Exception as e:
            logger.debug(f"BSD odds nao disponivel: {e}")

    import src.sources.bet365_scraper as b365
    if b365.disponivel():
        try:
            odds = b365.odds_partida()
            if odds.get("disponivel"):
                return {"fonte": "bet365", "raw": odds}
        except Exception as e:
            logger.debug(f"bet365 scraper: {e}")

    return {}


def _calcular_ev(prob: float, odd_real: float) -> float:
    """Valor Esperado = (probabilidade * odd) - 1."""
    if not odd_real or odd_real <= 1:
        return None
    return round((prob * odd_real) - 1, 4)


def _forma_peso(jogador_medias: dict) -> float:
    """Peso da forma recente baseado em minutos jogados."""
    mins = jogador_medias.get("minutos_totais", 0)
    if mins >= 180:
        return 1.0
    if mins >= 90:
        return 0.85
    return 0.7


def analisar_jogador_pre_jogo(
    nome: str,
    time: str,
    adversario: str,
    gols_sofridos_adversario_media: float = 1.5,
    minutos_esperados: float = 90.0,
    eh_titular: bool = True,
    bate_penalti: bool = False,
) -> dict:
    """Analisa um jogador para todos os mercados pré-jogo."""
    med = medias_jogador(nome, ultimas_n=5)
    if not med:
        return None

    peso = _forma_peso(med)
    posicao = med["posicao"]
    min_restantes = minutos_esperados

    resultados = {}

    faltas_por_90 = med["faltas_por_90"]
    amarelos_por_90 = med["amarelos_por_90"]

    faltas_esperadas_partida = faltas_por_90 * (minutos_esperados / 90.0)
    prob_cartao_base = min(1.0, amarelos_por_90 / 90.0 * minutos_esperados * 0.8)

    r_cartao = probabilidade_cartao(
        minuto_atual=1,
        faltas=max(1, round(faltas_esperadas_partida)),
        posicoes=posicao,
        minutos_esperados=minutos_esperados,
    )
    prob_cartao = (r_cartao.get("prob") or 0) * peso
    resultados["cartao"] = {
        "prob": round(min(prob_cartao, 0.95), 4),
        "odd_justa": round(1.0 / prob_cartao, 2) if prob_cartao > 0 else 999,
        "params": {"faltas_esperadas": round(faltas_esperadas_partida, 1)},
    }

    chutes_por_90 = med["chutes_gol_por_90"]
    chutes_esperados = chutes_por_90 * (minutos_esperados / 90.0)
    r_chutes = prob_chutes_gol(
        minuto_atual=1,
        chutes_gol=0,
        posicoes=posicao,
        minutos_esperados=minutos_esperados,
        meta=1,
    )
    prob_chutes = (r_chutes.get("prob") or 0) * peso
    resultados["chutes"] = {
        "prob": round(min(prob_chutes, 0.95), 4),
        "odd_justa": round(1.0 / prob_chutes, 2) if prob_chutes > 0 else 999,
        "params": {"chutes_por_90": round(chutes_por_90, 2)},
    }

    gols_por_90 = med["gols_por_90"]
    r_gol = prob_gol(
        taxa_historica_gols=gols_por_90,
        posicoes=posicao,
        minutos_esperados=minutos_esperados,
        forma_peso=peso,
        adversario_gols_sofridos_media=gols_sofridos_adversario_media,
        eh_titular=eh_titular,
        bate_penalti=bate_penalti,
    )
    prob_gol_val = r_gol.get("prob") or 0
    resultados["gol"] = {
        "prob": round(min(prob_gol_val, 0.95), 4),
        "odd_justa": round(1.0 / prob_gol_val, 2) if prob_gol_val > 0 else 999,
        "params": {"gols_por_90": round(gols_por_90, 3)},
    }

    return {
        "nome": nome,
        "time": med["time"],
        "posicao": posicao,
        "partidas_no_torneio": med["n_partidas"],
        "minutos_totais": med["minutos_totais"],
        "forma_peso": round(peso, 2),
        "mercados": resultados,
    }


def gerar_sinais_time(
    time: str,
    adversario: str,
    gols_sofridos_adversario: float = 1.5,
    min_prob_cartao: float = 0.35,
    min_prob_chutes: float = 0.45,
    min_prob_gol: float = 0.20,
    liga: str = "",
) -> list:
    """Gera sinais pré-jogo com odds REAIS e EV para todos os jogadores."""
    jogadores = todos_jogadores_do_time(time)
    if not jogadores:
        logger.warning(f"Nenhum jogador em cache para {time}")
        return []

    odds_jogo = _odds_reais(liga, time, adversario) if liga else {}
    fonte_odds = odds_jogo.get("fonte", "fair odds")

    sinais = []
    for j in jogadores:
        analise = analisar_jogador_pre_jogo(
            j["nome"], time, adversario, gols_sofridos_adversario
        )
        if not analise:
            continue

        for mercado in ("cartao", "chutes", "gol"):
            m = analise["mercados"][mercado]
            prob = m["prob"]
            min_prob = {"cartao": min_prob_cartao,
                        "chutes": min_prob_chutes,
                        "gol": min_prob_gol}[mercado]

            if prob < min_prob:
                continue

            odd_justa = m["odd_justa"]

            odd_real = None
            ev = None
            if odds_jogo.get("fonte") == "BSD" and odds_jogo.get("odd_h"):
                odd_real = odds_jogo["odd_h"]
                ev = _calcular_ev(prob, odd_real)
            elif odds_jogo.get("fonte") == "bet365":
                raw = odds_jogo.get("raw", {})
                odds_lista = raw.get("odds", {}).get(mercado, [])
                for item in odds_lista:
                    if item.get("jogador", "").lower() in analise["nome"].lower():
                        odd_real = item.get("odd")
                        ev = _calcular_ev(prob, odd_real)
                        break

            sinais.append({
                "tipo": mercado,
                "jogador": analise["nome"],
                "time": analise["time"],
                "adversario": adversario,
                "posicao": analise["posicao"],
                "prob": prob,
                "odd_justa": odd_justa,
                "odd_real": odd_real,
                "ev": ev,
                "fonte_odds": fonte_odds,
                "params": m["params"],
                "partidas_no_torneio": analise["partidas_no_torneio"],
                "forma_peso": analise["forma_peso"],
            })

    sinais.sort(key=lambda x: x["ev"] if x["ev"] is not None else x["prob"], reverse=True)
    return sinais


def formatar_sinal_para_discord(sinal: dict) -> dict:
    """Monta embed do Discord com odds reais e EV."""
    tipo = sinal["tipo"]
    titulos = {"cartao": "SINAL DE CARTAO",
               "chutes": "SINAL DE CHUTES A GOL",
               "gol": "SINAL DE GOL"}
    cores = {"cartao": 0xF1C40F, "chutes": 0x3498DB, "gol": 0x2ECC71}
    verbos = {"cartao": "leva cartao amarelo",
              "chutes": "da 1+ chute(s) a gol",
              "gol": "marca gol"}

    prob_pct = sinal["prob"] * 100
    if prob_pct >= 70:
        rotulo = "MUITO ALTA"
    elif prob_pct >= 55:
        rotulo = "ALTA"
    else:
        rotulo = "BOA"

    params = sinal.get("params", {})
    linhas = []
    if sinal["tipo"] == "cartao" and "faltas_esperadas" in params:
        linhas.append(f"Media de {params['faltas_esperadas']} faltas/jogo")
    elif sinal["tipo"] == "chutes" and "chutes_por_90" in params:
        linhas.append(f"Media de {params['chutes_por_90']} chutes a gol/90min")
    elif sinal["tipo"] == "gol" and "gols_por_90" in params:
        linhas.append(f"Media de {params['gols_por_90']} gols/90min")
    linhas.append(f"Posicao: {sinal['posicao']}")
    if sinal.get("partidas_no_torneio", 0) > 0:
        linhas.append(f"{sinal['partidas_no_torneio']} jogos no torneio")

    fields = [
        {"name": "APOSTA", "value": f"**{sinal['jogador']} {verbos[tipo]}**", "inline": False},
        {"name": "Chance estimada", "value": f"**{prob_pct:.0f}%** ({rotulo})", "inline": True},
    ]

    if sinal.get("odd_real"):
        fields.append({"name": "Melhor odd real", "value": f"**{sinal['odd_real']:.2f}** ({sinal.get('fonte_odds','?')})", "inline": True})
        if sinal.get("ev") is not None:
            ev_sinal = "📈" if sinal["ev"] > 0 else "📉"
            fields.append({"name": f"Valor Esperado (EV) {ev_sinal}", "value": f"**{sinal['ev']*100:.1f}%**", "inline": True})
    else:
        fields.append({"name": "Fair odds (referencia)", "value": f"**{sinal['odd_justa']:.2f}**", "inline": True})

    fields.append({"name": "Baseado em", "value": " | ".join(linhas), "inline": False})

    return {
        "title": f"{titulos[tipo]}",
        "description": f"{sinal['time']} vs {sinal['adversario']}\n"
                       f"Jogador: **{sinal['jogador']}** ({sinal['posicao']})",
        "color": cores[tipo],
        "fields": fields,
        "footer": {"text": "Só aposte se a odd REAL for MAIOR que a fair odd." if not sinal.get("odd_real")
                   else f"EV+ = valor esperado positivo. odds: {sinal.get('fonte_odds','?')}"},
    }
