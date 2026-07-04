"""
Estratégia 2: probabilidade de um jogador dar N+ CHUTES A GOL (no alvo).
Padrão: 1+ chute a gol (mais fácil = mais provável).

Usa uma BASE por posição (chutes a gol esperados num jogo inteiro) — um
atacante chuta muito mais que um zagueiro — combinada com o ritmo observado
e o tempo restante. P(chegar à meta) via Poisson.
"""
import math

META_PADRAO = 1

# Chutes a gol esperados num jogo INTEIRO, por posição (base empírica aprox.).
BASE_SOG_90 = {
    "ST": 1.6, "CF": 1.6, "F": 1.5, "FW": 1.5, "ATA": 1.5, "SS": 1.5,
    "LF": 1.4, "RF": 1.4,
    "W": 1.0, "LW": 1.0, "RW": 1.0, "PON": 1.0,
    "AM": 0.9, "CAM": 0.9, "MEI": 0.7,
    "M": 0.5, "CM": 0.45, "MC": 0.45,
    "DM": 0.30, "VOL": 0.30, "CDM": 0.30,
    "D": 0.20, "LB": 0.25, "RB": 0.25, "LAT": 0.25,
    "CB": 0.15, "CD": 0.15, "ZAG": 0.15, "DC": 0.15,
    "G": 0.02,
}
BASE_PADRAO = 0.5


def _base_sog(posicoes: str) -> float:
    if not posicoes:
        return BASE_PADRAO
    toks = posicoes.replace(",", " ").replace("/", " ").split()
    bs = [BASE_SOG_90.get(t.upper()) for t in toks]
    bs = [b for b in bs if b is not None]
    return max(bs) if bs else BASE_PADRAO


def prob_chutes_gol(minuto_atual: float, chutes_gol: int, posicoes: str = "",
                    minutos_esperados: float = 90.0, meta: int = META_PADRAO) -> dict:
    """Probabilidade do jogador terminar com `meta`+ chutes a gol."""
    minuto_atual = max(0.5, float(minuto_atual))
    restante = max(0.0, min(minutos_esperados, 90.0) - minuto_atual)

    if chutes_gol >= meta:
        return {"prob": None, "aviso": f"Já tem {meta}+ chutes a gol — mercado resolvido."}

    base_rate = _base_sog(posicoes) / 90.0          # por minuto, pela posição
    # Se já chutou, mistura com o ritmo real dele (ele está "ligado" hoje)
    if chutes_gol > 0:
        obs_rate = chutes_gol / minuto_atual
        taxa = 0.5 * base_rate + 0.5 * obs_rate
    else:
        taxa = base_rate
    esperado = taxa * restante                      # chutes a gol esperados no resto

    faltam = meta - chutes_gol
    acum = sum(math.exp(-esperado) * esperado**i / math.factorial(i) for i in range(faltam))
    prob = 1.0 - acum

    return {
        "prob": round(prob, 4),
        "odd_justa": round(1.0 / prob, 2) if prob > 0 else None,
        "minutos_restantes": round(restante, 1),
        "chutes_atual": chutes_gol,
        "faltam": faltam,
        "meta": meta,
        "esperado_mais": round(esperado, 2),
    }
