"""
Registro e conferência dos sinais (calibração).

- registrar_sinal(): grava cada sinal disparado em sinais_log.jsonl
- conferir():        depois dos jogos, checa se o jogador REALMENTE levou cartão
                     e mostra a taxa de acerto vs a probabilidade prevista.

Rodar a conferência:  py registro.py
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import json
import logging
from datetime import datetime

import requests
import src.config as config

logger = logging.getLogger(__name__)
ARQ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sinais_log.jsonl"))
FINALIZADOS = {"FT", "AET", "PEN"}


def registrar_sinal(dados: dict, prob: float):
    reg = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "tipo": dados.get("tipo", "cartao"),   # cartao | chutes
        "meta": dados.get("meta"),             # p/ chutes: N+ chutes a gol
        "fixture_id": dados.get("fixture_id"),
        "jogo": dados.get("jogo"),
        "jogador": dados["jogador"],
        "minuto": dados.get("minuto"),
        "prob": round(prob, 3),
        "resultado": None,   # None=pendente, True=aconteceu, False=não
    }
    with open(ARQ, "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def _ler() -> list:
    if not os.path.exists(ARQ):
        return []
    with open(ARQ, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _gravar(regs: list):
    with open(ARQ, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _conferir(fixture_id: int, jogador: str, tipo: str, meta: int = 1):
    """Retorna (finalizado?, aconteceu?) conforme a estratégia.
    cartao: levou amarelo? · chutes: terminou com 2+ chutes a gol?
    (só funciona p/ jogos via API-Football, ex. Copa.)"""
    H = {"x-apisports-key": config.API_FOOTBALL_KEY}
    fx = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures",
                      headers=H, params={"id": fixture_id}, timeout=20).json()
    resp = fx.get("response", [])
    if not resp:
        return False, None
    status = (resp[0]["fixture"]["status"] or {}).get("short")
    if status not in FINALIZADOS:
        return False, None
    pl = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures/players",
                      headers=H, params={"fixture": fixture_id}, timeout=20).json()
    for time in pl.get("response", []):
        for p in time.get("players", []):
            if p["player"]["name"] == jogador:
                st = (p.get("statistics") or [{}])[0]
                if tipo == "chutes":
                    return True, ((st.get("shots", {}).get("on") or 0) >= (meta or 1))
                return True, ((st.get("cards", {}).get("yellow") or 0) > 0)
    return True, False


def conferir():
    regs = _ler()
    pendentes = [r for r in regs if r["resultado"] is None and r.get("fixture_id")]
    logger.info(f"{len(pendentes)} sinais pendentes de conferência")
    for r in pendentes:
        try:
            fim, ok = _conferir(r["fixture_id"], r["jogador"], r.get("tipo", "cartao"), r.get("meta") or 1)
            if fim:
                r["resultado"] = bool(ok)
                logger.info(f"  [{r.get('tipo')}] {r['jogador']}: {'ACONTECEU ✅' if ok else 'não ❌'}")
        except Exception as e:
            logger.error(f"erro conferindo {r['jogador']}: {e}")
    _gravar(regs)

    conferidos = [r for r in regs if r["resultado"] is not None]
    if conferidos:
        n = len(conferidos)
        acertos = sum(1 for r in conferidos if r["resultado"])
        prob_media = sum(r["prob"] for r in conferidos) / n
        print("\n=== CALIBRAÇÃO ===")
        print(f"Sinais conferidos: {n}")
        print(f"Levaram cartão de fato: {acertos}/{n} = {acertos/n*100:.0f}%")
        print(f"Probabilidade média prevista: {prob_media*100:.0f}%")
        print("→ Se 'levaram de fato' << 'previsto', o modelo está otimista (ajustar).")
    else:
        print("Nenhum sinal conferido ainda (jogos podem não ter terminado).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    conferir()
