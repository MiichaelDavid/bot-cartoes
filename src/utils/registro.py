"""
Registro e conferência dos sinais (calibração).

- registrar_sinal():                grava cada sinal disparado em sinais_log.jsonl
- conferir():                        depois dos jogos (via API-Football), checa resultado
- conferir_copa():                   idem para Copa (via ESPN, keyless)
- conferir():                        auto-detecção da fonte

Rodar a conferência:  py src/utils/registro.py
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
ARQ_COPA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sinais_log_copa.jsonl"))
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


def _conferir_copa_espn(fixture_id, jogador: str, tipo: str, meta: int = 1):
    """Confere resultado de sinal da Copa via ESPN (keyless)."""
    try:
        H = {"User-Agent": "Mozilla/5.0"}
        BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
        j = requests.get(f"{BASE}/summary", params={"event": fixture_id},
                         headers=H, timeout=25).json()
    except Exception:
        return False, None
    comp = (j.get("header") or {}).get("competitions") or [{}]
    status = (comp[0].get("status") or {}).get("type", {}).get("state", "")
    if status not in ("post", "finished"):
        return False, None
    for t in j.get("rosters", []):
        for p in t.get("roster", []):
            if p.get("athlete", {}).get("displayName") == jogador:
                st = {s.get("abbreviation"): s.get("value") for s in (p.get("stats") or [])}
                if tipo == "chutes":
                    return True, (int(st.get("SOG") or 0) >= (meta or 1))
                return True, (int(st.get("YC") or 0) > 0)
    return True, False


def _ler_copa():
    if not os.path.exists(ARQ_COPA):
        return []
    with open(ARQ_COPA, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _gravar_copa(regs: list):
    with open(ARQ_COPA, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def conferir_copa():
    """Confere sinais da Copa via ESPN (keyless, usa sinais_log_copa.jsonl)."""
    regs = _ler_copa()
    pendentes = [r for r in regs if r["resultado"] is None and r.get("fixture_id")]
    logger.info(f"[COPA] {len(pendentes)} sinais pendentes de conferência")
    for r in pendentes:
        try:
            fim, ok = _conferir_copa_espn(r["fixture_id"], r["jogador"],
                                          r.get("tipo", "cartao"), r.get("meta") or 1)
            if fim:
                r["resultado"] = bool(ok)
                logger.info(f"  [COPA {r.get('tipo')}] {r['jogador']}: {'ACONTECEU ✅' if ok else 'não ❌'}")
        except Exception as e:
            logger.error(f"erro conferindo {r['jogador']}: {e}")
    _gravar_copa(regs)

    conferidos = [r for r in regs if r["resultado"] is not None]
    if conferidos:
        n = len(conferidos)
        acertos = sum(1 for r in conferidos if r["resultado"])
        prob_media = sum(r["prob"] for r in conferidos) / n
        print("\n=== CALIBRAÇÃO COPA ===")
        print(f"Sinais conferidos: {n}")
        print(f"Aconteceram de fato: {acertos}/{n} = {acertos/n*100:.0f}%")
        print(f"Probabilidade média prevista: {prob_media*100:.0f}%")
    else:
        print("Nenhum sinal da Copa conferido ainda.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) > 1 and sys.argv[1] == "copa":
        conferir_copa()
    else:
        conferir()
