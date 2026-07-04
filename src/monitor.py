"""
Monitor em tempo real do Bot de Cartões — CLUBES (Brasileirão, Premier, LaLiga...).

Varre os jogos ao vivo de tempos em tempos, calcula a probabilidade de cartão
de cada jogador (faltas + árbitro + posição + tempo) e manda no WhatsApp/Discord
quem passar do limiar.

Rodar:  python src/monitor.py

Para a COPA DO MUNDO, rode separadamente (standalone, keyless, via ESPN):
        python src/monitor_copa.py
"""
import time
import logging

import os
import sys

# Garante que o diretório raiz esteja no path do Python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
logger = logging.getLogger("bot-cartoes")

_ja_avisados = set()   # (jogo_id, jogador) já notificados — evita spam


def _carregar_sinais_salvos():
    """Lê sinais_log.jsonl e preenche _ja_avisados para evitar spam em caso de reinicialização."""
    import os
    import json
    arq_caminho = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sinais_log.jsonl"))
    if not os.path.exists(arq_caminho):
        return
    try:
        cont = 0
        with open(arq_caminho, "r", encoding="utf-8") as f:
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
            logger.info(f"Carregados {cont} sinais anteriores de sinais_log.jsonl para evitar duplicados.")
    except Exception as e:
        logger.error(f"Erro ao carregar sinais anteriores: {e}")


def _disparar(tipo: str, jogo: dict, jg: dict, prob: float,
              odd_min: float, aposta_txt: str, motivo: str, meta: int = None):
    """Envia o sinal (Discord + WhatsApp) e registra, sem duplicar."""
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
    logger.info(f"SINAL [{tipo}]: {jg['nome']} ({jogo['time_casa']}) {prob*100:.0f}%")
    enviar_discord(sinal)
    enviar_whatsapp(f"{aposta_txt}\n{jogo['time_casa']} x {jogo['time_fora']} ({int(sinal['minuto'])}')\n"
                    f"Chance {prob*100:.0f}% · só se a casa pagar >= {odd_min:.2f}")
    registrar_sinal(sinal, prob)
    _ja_avisados.add(chave)


def _avaliar_jogo(jogo: dict, jogadores: list):
    minuto = jogo["minuto"] or 1
    total_cartoes = sum(jg.get("amarelos", 0) for jg in jogadores)
    ritmo = ritmo_cartoes_jogo(total_cartoes, minuto)   # ritmo de cartões do jogo ao vivo

    # ── Estratégia 1: melhor candidato a CARTÃO ───────────────────────────────
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

    # ── Estratégia 2: melhor candidato a N+ CHUTES A GOL ──────────────────────
    meta = config.META_CHUTES
    melhor_s = None
    for jg in jogadores:
        cg = jg.get("chutes_gol", 0)
        if cg >= meta:                      # já bateu — mercado resolvido
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


def _ciclo_apifootball() -> int:
    """Roda um ciclo. Retorna o nº de jogos ao vivo (p/ ajustar o intervalo)."""
    import src.sources.apifootball as fonte
    jogos = fonte.jogos_ao_vivo(config.LIGAS_FILTRO)
    logger.info(f"[API-Football] {len(jogos)} jogos relevantes ao vivo "
                f"(filtro: {config.LIGAS_FILTRO or 'todas'})")
    for jogo in jogos:
        jogadores = fonte.jogadores_do_jogo(jogo["id"])
        _avaliar_jogo(jogo, jogadores)
    return len(jogos)


def _ciclo_espn() -> int:
    """Ciclo via ESPN (clubes, SEM LIMITE de cota)."""
    import src.sources.espn as fonte
    jogos = fonte.jogos_ao_vivo(config.LIGAS_ESPN)
    logger.info(f"[ESPN] {len(jogos)} jogos ao vivo (ligas: {config.LIGAS_ESPN})")
    for jogo in jogos:
        jogadores = fonte.jogadores_do_jogo(jogo["_lg"], jogo["id"])
        _avaliar_jogo(jogo, jogadores)
    return len(jogos)


def loop():
    _carregar_sinais_salvos()
    logger.info(f"Bot de Cartões iniciado | fonte={config.FONTE_FALTAS} | "
                f"prob_min={config.PROB_MINIMA:.0%} | varre a cada {config.INTERVALO_SEG}s")
    if config.FONTE_FALTAS == "hibrido":
        import src.sources.espn as _espn
        ultimo_af = -1e9   # última vez que chamou a API-Football (monotonic)
        logger.info("Modo HÍBRIDO: ESPN (clubes, ilimitado) + API-Football (só Copa ao vivo)")
        while True:
            # 1) Clubes pela ESPN — sempre, de graça
            try:
                _ciclo_espn()
            except Exception as e:
                logger.error(f"erro ESPN: {e}")
            # 2) Copa pela API-Football — só quando há jogo de Copa ao vivo (ESPN avisa de graça)
            try:
                if _espn.copa_ao_vivo():
                    agora = time.monotonic()
                    if agora - ultimo_af >= config.API_FOOTBALL_INTERVALO:
                        logger.info("Copa AO VIVO → consultando API-Football")
                        _ciclo_apifootball()
                        ultimo_af = agora
                else:
                    logger.info("Sem Copa ao vivo — API-Football poupada (0 cota)")
            except Exception as e:
                logger.error(f"erro Copa/API-Football: {e}")
            time.sleep(config.INTERVALO_SEG)

    else:
        ciclo = _ciclo_espn if config.FONTE_FALTAS == "espn" else _ciclo_apifootball
        while True:
            n_vivos = 0
            try:
                n_vivos = ciclo()
            except Exception as e:
                logger.error(f"erro no ciclo {config.FONTE_FALTAS}: {e}")
            # Varre rápido com jogo ao vivo; devagar quando ocioso
            espera = config.INTERVALO_SEG if n_vivos else config.INTERVALO_OCIOSO
            time.sleep(espera)


if __name__ == "__main__":
    loop()
