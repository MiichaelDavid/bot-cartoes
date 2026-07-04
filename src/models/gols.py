"""
Modelo de probabilidade de UM JOGADOR MARCAR GOL (pré-jogo).

Usa taxa histórica de gols por 90 min (ou por jogo), combinada com:
- Posição (atacantes > meias > defensores)
- Forma recente (peso maior para últimos jogos)
- Força do adversário (defesa)
- Se é provável jogar (titular? minutos?)

P(gol no jogo) via Poisson: 1 - exp(-lambda)
"""
import math

GOLS_POR_90 = {
    "ST": 0.45, "CF": 0.45, "F": 0.42, "FW": 0.42, "ATA": 0.42, "SS": 0.35,
    "LF": 0.35, "RF": 0.35,
    "W": 0.25, "LW": 0.25, "RW": 0.25, "PON": 0.25,
    "AM": 0.18, "CAM": 0.18, "MEI": 0.12,
    "M": 0.10, "CM": 0.08, "MC": 0.08,
    "DM": 0.05, "VOL": 0.05, "CDM": 0.05,
    "D": 0.03, "LB": 0.04, "RB": 0.04, "LAT": 0.04,
    "CB": 0.02, "CD": 0.02, "ZAG": 0.02, "DC": 0.02,
    "G": 0.01,
}
BASE_PADRAO = 0.10
PENALTY_TAKER_BONUS = 0.12


def _base_gols(posicoes: str) -> float:
    if not posicoes:
        return BASE_PADRAO
    toks = posicoes.replace(",", " ").replace("/", " ").split()
    bs = [GOLS_POR_90.get(t.upper()) for t in toks]
    bs = [b for b in bs if b is not None]
    return max(bs) if bs else BASE_PADRAO


def prob_gol(
    taxa_historica_gols: float,
    posicoes: str = "",
    minutos_esperados: float = 90.0,
    forma_peso: float = 1.0,
    adversario_gols_sofridos_media: float = 1.5,
    eh_titular: bool = True,
    bate_penalti: bool = False,
) -> dict:
    if not eh_titular:
        minutos_esperados = min(minutos_esperados, 30.0)

    base_pos = _base_gols(posicoes)
    if taxa_historica_gols > 0:
        taxa = 0.4 * base_pos / 90.0 + 0.6 * (taxa_historica_gols / 90.0)
    else:
        taxa = base_pos / 90.0

    taxa *= forma_peso
    fator_adversario = adversario_gols_sofridos_media / 1.5
    taxa *= max(0.5, fator_adversario)

    lam = taxa * minutos_esperados
    if bate_penalti:
        lam += PENALTY_TAKER_BONUS

    prob = 1.0 - math.exp(-lam)
    return {
        "prob": round(prob, 4),
        "odd_justa": round(1.0 / prob, 2) if prob > 0 else None,
        "lambda": round(lam, 4),
    }
