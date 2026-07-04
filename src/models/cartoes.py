"""
Modelo de probabilidade de CARTÃO AMARELO de um jogador (ao vivo).

Heurística (não é exato — é estimativa pra comparar com a odd da casa):
  - taxa de faltas do jogador até agora, suavizada por um prior (jogadores
    se regulam depois de faltar muito cedo, então não extrapolamos cru);
  - perfil do árbitro (média de amarelos por jogo);
  - posição (zagueiro/volante levam mais que atacante);
  - tempo restante e expectativa de minutos em campo.

P(cartão no resto do jogo) = 1 - exp(-lambda)
  lambda = faltas_esperadas * P(cartão|falta) * fator_arbitro * fator_posicao
           + risco_base (dissidência, etc.)
"""
import math

# Conversão média falta → amarelo no futebol (~3.7 amarelos por ~24 faltas/jogo).
P_CARTAO_POR_FALTA = 0.14
# Média de referência de amarelos por jogo de um árbitro "neutro".
MEDIA_CARTOES_ARBITRO = 3.8
# Risco-base de cartão por motivo não-falta (reclamação, perda de tempo) por 90'.
RISCO_BASE_90 = 0.06

# Prior para suavizar a taxa de faltas (peso ~30 min a 0,02 falta/min).
PRIOR_FALTAS = 0.02 * 30
PRIOR_MINUTOS = 30.0

FATOR_POSICAO = {
    # Posições de 1 letra da API-Football
    "G": 0.50, "D": 1.15, "M": 1.05, "F": 0.85,
    # Posições da ESPN
    "CD": 1.20, "CB": 1.20,
    # Posições detalhadas (SofaScore / manual)
    "DM": 1.25, "VOL": 1.25, "CDM": 1.25,
    "CB": 1.20, "DC": 1.20, "ZAG": 1.20,
    "DR": 1.10, "DL": 1.10, "LB": 1.10, "RB": 1.10, "LAT": 1.10,
    "MC": 1.00, "CM": 1.00, "MEI": 0.95, "AM": 0.90, "CAM": 0.90,
    "RW": 0.85, "LW": 0.85, "W": 0.85, "PON": 0.85,
    "ST": 0.85, "CF": 0.85, "ATA": 0.85, "FW": 0.85,
}


def _fator_posicao(posicoes: str) -> float:
    """Pega o maior fator entre as posições citadas (ex.: 'MC DR DM')."""
    if not posicoes:
        return 1.0
    toks = posicoes.replace(",", " ").replace("/", " ").split()
    fatores = [FATOR_POSICAO.get(t.upper(), 1.0) for t in toks]
    return max(fatores) if fatores else 1.0


def probabilidade_cartao(
    minuto_atual: float,
    faltas: int,
    arbitro_media_cartoes: float = MEDIA_CARTOES_ARBITRO,
    posicoes: str = "",
    minutos_esperados: float = 90.0,
    ja_amarelado: bool = False,
) -> dict:
    """
    Retorna dict com a probabilidade estimada e os componentes.
    Se o jogador já tem amarelo, o mercado 'levar cartão' já bateu — devolve
    aviso (o relevante passa a ser 2º amarelo/vermelho, muito mais raro).
    """
    minuto_atual = max(0.1, float(minuto_atual))
    fim = 90.0  # ignora acréscimos pra ser conservador
    restante = max(0.0, min(minutos_esperados, fim) - minuto_atual)

    if ja_amarelado:
        return {
            "prob": None,
            "aviso": "Jogador JÁ tem amarelo — mercado 'levar cartão' já resolveu. "
                     "(2º amarelo/vermelho é outro mercado, bem mais raro.)",
        }

    # Taxa de faltas suavizada (falta/min)
    taxa = (faltas + PRIOR_FALTAS) / (minuto_atual + PRIOR_MINUTOS)
    faltas_esperadas = taxa * restante

    fator_arb = arbitro_media_cartoes / MEDIA_CARTOES_ARBITRO
    fator_pos = _fator_posicao(posicoes)

    lam = (
        faltas_esperadas * P_CARTAO_POR_FALTA * fator_arb * fator_pos
        + RISCO_BASE_90 * (restante / 90.0) * fator_arb
    )
    prob = 1.0 - math.exp(-lam)

    return {
        "prob": round(prob, 4),
        "odd_justa": round(1.0 / prob, 2) if prob > 0 else None,
        "minutos_restantes": round(restante, 1),
        "faltas_esperadas": round(faltas_esperadas, 2),
        "taxa_faltas_min": round(taxa, 4),
        "fator_arbitro": round(fator_arb, 2),
        "fator_posicao": round(fator_pos, 2),
        "lambda": round(lam, 3),
    }


def ritmo_cartoes_jogo(total_cartoes: int, minuto: float,
                       media_liga: float = MEDIA_CARTOES_ARBITRO,
                       peso_prior: float = 30.0) -> float:
    """
    Quantos amarelos/90min ESTE jogo está tendo (rigidez do árbitro + pegada do
    jogo), lido ao vivo. Suavizado por um prior da liga pra não exagerar cedo
    (ex.: 1 cartão aos 5' não significa 18/jogo).
    """
    minuto = max(1.0, float(minuto))
    prior_por_min = media_liga / 90.0
    blend_por_min = (total_cartoes + prior_por_min * peso_prior) / (minuto + peso_prior)
    return round(blend_por_min * 90.0, 2)


def avaliar_vs_odd(prob: float, odd: float) -> dict:
    """Compara a probabilidade do modelo com uma odd da casa."""
    if not odd or odd <= 1.0 or not prob:
        return {"implicita": None, "ev": None}
    implicita = 1.0 / odd
    ev = prob * odd - 1.0
    return {
        "implicita": round(implicita, 4),
        "ev": round(ev, 4),
        "veredito": "modelo vê valor" if ev > 0 else "modelo NÃO vê valor",
    }
