"""
Monitor STANDALONE para a Copa do Mundo 2026.

USO:
    python src/monitor_copa.py

Funciona 100% pela ESPN (keyless, ilimitado). Dispara sinais de cartão
amarelo e chutes a gol no Discord e WhatsApp.

INDEPENDENTE do monitor.py (que cuida dos clubes). Pode rodar junto ou
separado. Quando a Copa acabar, é só parar este processo — o bot dos
clubes continua intacto.
"""
import time
import json
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.config as config
from src.models.cartoes import probabilidade_cartao, ritmo_cartoes_jogo
from src.models.chutes import prob_chutes_gol
from src.services.whatsapp import enviar_whatsapp
from src.services.discord_notifier import enviar_discord
from src.utils.registro import registrar_sinal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot-copa")

_ja_avisados: set = set()
_LOG_COPA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sinais_log_copa.jsonl"))


def _carregar_sinais_salvos():
    if not os.path.exists(_LOG_COPA):
        return
    try:
        cont = 0
        with open(_LOG_COPA, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    dado = json.loads(linha)
                    fixture_id = dado.get("fixture_id")
                    jogador = dado.get("jogador")
                    tipo = dado.get("tipo", "cartao")
                    if fixture_id and jogador:
                        _ja_avisados.add((fixture_id, jogador, tipo))
                        cont += 1
                except Exception:
                    continue
        if cont > 0:
            logger.info(f"Carregados {cont} sinais anteriores da Copa para evitar duplicados.")
    except Exception as e:
        logger.error(f"Erro ao carregar sinais da Copa: {e}")


def _disparar(tipo: str, jogo: dict, jg: dict, prob: float,
              odd_min: float, aposta_txt: str, motivo: str, meta: int = None):
    chave = (jogo["id"], jg["nome"], tipo)
    if chave in _ja_avisados:
        return
    sinal = {
        "tipo": tipo,
        "meta": meta,
        "fixture_id": jogo["id"],
        "competicao": jogo.get("liga", ""),
        "jogo": f"{jogo['time_casa']} x {jogo['time_fora']}",
        "placar": jogo.get("placar", ""),
        "minuto": jogo["minuto"] or 0,
        "jogador": jg["nome"],
        "prob": prob,
        "odd_min": odd_min,
        "aposta_txt": aposta_txt,
        "motivo": motivo,
    }
    logger.info(f"SINAL COPA [{tipo}]: {jg['nome']} ({jogo['time_casa']}) {prob*100:.0f}%")
    enviar_discord(sinal)
    enviar_whatsapp(f"🏆 COPA | {aposta_txt}\n{jogo['time_casa']} x {jogo['time_fora']} ({int(sinal['minuto'])}')\n"
                    f"Chance {prob*100:.0f}% · só se a casa pagar >= {odd_min:.2f}")
    _registrar_sinal_copa(sinal, prob)
    _ja_avisados.add(chave)


def _registrar_sinal_copa(dados: dict, prob: float):
    from datetime import datetime
    reg = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "tipo": dados.get("tipo", "cartao"),
        "meta": dados.get("meta"),
        "fixture_id": dados.get("fixture_id"),
        "jogo": dados.get("jogo"),
        "jogador": dados["jogador"],
        "minuto": dados.get("minuto"),
        "prob": round(prob, 3),
        "resultado": None,
    }
    with open(_LOG_COPA, "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def _avaliar_jogo(jogo: dict, jogadores: list):
    minuto = jogo["minuto"] or 1
    total_cartoes = sum(jg.get("amarelos", 0) for jg in jogadores)
    ritmo = ritmo_cartoes_jogo(total_cartoes, minuto)

    melhor_c = None
    for jg in jogadores:
        if jg.get("amarelo") or jg.get("vermelho") or jg["faltas"] < config.MIN_FALTAS:
            continue
        r = probabilidade_cartao(minuto, jg["faltas"], ritmo, jg.get("posicao", ""))
        if r.get("prob") and (melhor_c is None or r["prob"] > melhor_c[2]):
            melhor_c = (jg, r, r["prob"])
    if melhor_c and melhor_c[2] >= config.PROB_MINIMA:
        jg, r, p = melhor_c
        motivo = (f"Já fez **{jg['faltas']} faltas** · jogo com {total_cartoes} amarelos "
                  f"(ritmo ~{ritmo}/90) · faltam {r['minutos_restantes']:.0f} min")
        _disparar("cartao", jogo, jg, p, r["odd_justa"],
                  f"{jg['nome']} leva cartão amarelo", motivo)

    meta = config.META_CHUTES
    melhor_s = None
    for jg in jogadores:
        cg = jg.get("chutes_gol", 0)
        if cg >= meta:
            continue
        r = prob_chutes_gol(minuto, cg, jg.get("posicao", ""), meta=meta)
        if r.get("prob") and (melhor_s is None or r["prob"] > melhor_s[2]):
            melhor_s = (jg, r, r["prob"])
    if melhor_s and melhor_s[2] >= config.PROB_MINIMA_CHUTES:
        jg, r, p = melhor_s
        motivo = (f"Tem **{r['chutes_atual']} chute(s) a gol** · posição ofensiva "
                  f"({jg.get('posicao','?')}) · faltam {r['minutos_restantes']:.0f} min")
        _disparar("chutes", jogo, jg, p, r["odd_justa"],
                  f"{jg['nome']} dá {meta}+ chute(s) a gol", motivo, meta=meta)


def loop():
    import src.sources.copa as copa
    _carregar_sinais_salvos()
    logger.info("🏆 Monitor da Copa do Mundo iniciado (ESPN keyless, ilimitado)")
    logger.info(f"prob_min_cartao={config.PROB_MINIMA:.0%} | "
                f"prob_min_chutes={config.PROB_MINIMA_CHUTES:.0%} | "
                f"varre a cada {config.INTERVALO_SEG}s")

    while True:
        n_vivos = 0
        try:
            jogos = copa.jogos_ao_vivo()
            if jogos:
                logger.info(f"[COPA] {len(jogos)} jogo(s) ao vivo")
                for jogo in jogos:
                    jogadores = copa.jogadores_do_jogo(jogo["id"])
                    if not jogadores:
                        logger.debug(f"[COPA] {jogo['time_casa']}x{jogo['time_fora']} sem stats ainda")
                        continue
                    logger.info(f"[COPA] {jogo['time_casa']}x{jogo['time_fora']} — "
                                f"{len(jogadores)} jogadores c/ stats, min {jogo['minuto']}'")
                    _avaliar_jogo(jogo, jogadores)
                n_vivos = len(jogos)
            else:
                logger.info("[COPA] Nenhum jogo ao vivo agora")
        except Exception as e:
            logger.error(f"erro no ciclo da Copa: {e}", exc_info=True)

        espera = config.INTERVALO_SEG if n_vivos else config.INTERVALO_OCIOSO
        time.sleep(espera)


if __name__ == "__main__":
    loop()
