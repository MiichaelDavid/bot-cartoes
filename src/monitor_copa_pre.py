"""
Monitor PRÉ-JOGO (Copa + Clubes).

Gera sinais ANTES das partidas com ODDS REAIS e cálculo de EV.

Fontes de odds:
  - BSD (Bzzoiro): gratuito, 17+ casas, para clubes (Brasileirão, Premier, etc.)
  - bet365: scraping opcional (requer BET365_COOKIE no .env)
  - Fair odds: cálculo do modelo (fallback universal)

USO:
    python src/monitor_copa_pre.py                          # análise única
    python src/monitor_copa_pre.py --loop                   # modo contínuo
    python src/monitor_copa_pre.py --liga "Brasileirão"     # filtrar por liga
"""
import argparse
import logging
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.config as config
from src.pre_match.analisador import gerar_sinais_time, formatar_sinal_para_discord
from src.pre_match.cache_jogadores import resumo_cache, top_jogadores
from src.services.whatsapp import enviar_whatsapp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot-pre")

_ja_enviados = set()


def _disparar_pre(sinal: dict):
    """Dispara sinal pré-jogo para Discord + WhatsApp com odds REAIS."""
    chave = (sinal["jogador"], sinal["time"], sinal["adversario"], sinal["tipo"])
    if chave in _ja_enviados:
        return
    _ja_enviados.add(chave)

    embed = formatar_sinal_para_discord(sinal)
    payload = {"username": "Bot de Sinais (Pré-Jogo)", "embeds": [embed]}
    if config.DISCORD_WEBHOOK_URL:
        try:
            import requests
            r = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if r.status_code in (200, 204):
                logger.info(f"Discord: {sinal['jogador']} - {sinal['tipo']} | "
                            f"prob {sinal['prob']*100:.0f}% | "
                            f"{'EV ' + str(round(sinal['ev']*100,1)) + '%' if sinal.get('ev') is not None else 'fair ' + str(sinal['odd_justa'])}")
            else:
                logger.error(f"Discord HTTP {r.status_code}")
        except Exception as e:
            logger.error(f"Discord erro: {e}")
    else:
        logger.info(f"Sinal: {sinal['jogador']} - {sinal['tipo']} | "
                    f"{sinal['prob']*100:.0f}% | "
                    f"{'EV ' + str(round(sinal['ev']*100,1)) + '%' if sinal.get('ev') is not None else 'fair ' + str(sinal['odd_justa'])}")

    aposta_txt = {
        "cartao": f"{sinal['jogador']} leva cartao amarelo",
        "chutes": f"{sinal['jogador']} da 1+ chute(s) a gol",
        "gol": f"{sinal['jogador']} marca gol",
    }.get(sinal['tipo'], sinal['jogador'])

    if sinal.get("odd_real"):
        whatsapp_msg = (f"SINAL PRE-JOGO | {aposta_txt}\n"
                        f"{sinal['time']} vs {sinal['adversario']}\n"
                        f"Chance: {sinal['prob']*100:.0f}%\n"
                        f"Melhor odd: {sinal['odd_real']:.2f} ({sinal.get('fonte_odds','?')})\n"
                        f"{'EV POSITIVO +'+str(round(sinal['ev']*100,1))+'%' if sinal.get('ev',0) > 0 else 'EV negativo'}")
    else:
        whatsapp_msg = (f"SINAL PRE-JOGO | {aposta_txt}\n"
                        f"{sinal['time']} vs {sinal['adversario']}\n"
                        f"Chance: {sinal['prob']*100:.0f}%\n"
                        f"Fair odds: {sinal['odd_justa']:.2f} (referencia)\n"
                        f"Só aposte se a odd da casa >= {sinal['odd_justa']:.2f}")
    enviar_whatsapp(whatsapp_msg)


def analisar_e_disparar(time_casa: str, time_fora: str, liga: str = ""):
    """Analisa o jogo e dispara sinais pré-jogo com odds reais."""
    logger.info(f"Analisando: {time_casa} vs {time_fora} [{liga or 'Copa'}]")

    for time, adv in [(time_casa, time_fora), (time_fora, time_casa)]:
        sinais = gerar_sinais_time(time, adv, liga=liga)
        if not sinais:
            logger.info(f"  {time}: sem sinais")
            continue

        logger.info(f"  {time}: {len(sinais)} sinais | "
                    f"fonte odds: {sinais[0].get('fonte_odds','fair odds')}")
        top = sinais[:5]
        for s in top:
            ev_str = f"EV {s['ev']*100:.1f}%" if s.get('ev') is not None else f"fair {s['odd_justa']}"
            logger.info(f"    {s['tipo']}: {s['jogador']} ({s['prob']*100:.0f}%, {ev_str})")
            _disparar_pre(s)


def _buscar_proximos_jogos_espn() -> list:
    """Busca próximos jogos via ESPN."""
    import requests
    H = {"User-Agent": "Mozilla/5.0"}
    jogos = []

    for endpoint in ["fifa.world", "bra.1"]:
        try:
            sb = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/soccer/{endpoint}/scoreboard",
                headers=H, timeout=20
            ).json()
            nome_liga = (sb.get("leagues") or [{}])[0].get("name", endpoint)
            for e in sb.get("events", []):
                comp = (e.get("competitions") or [{}])[0]
                status = comp.get("status", {}).get("type", {}).get("state", "")
                if status in ("pre", "scheduled"):
                    date_str = e.get("date") or comp.get("date")
                    if date_str:
                        try:
                            from datetime import datetime, timezone, timedelta
                            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            agora = datetime.now(timezone.utc)
                            if not (timedelta(seconds=0) < dt - agora <= timedelta(hours=36)):
                                continue
                        except Exception as date_err:
                            logger.warning(f"Erro ao filtrar data {date_str}: {date_err}")

                    cs = comp.get("competitors", [])
                    home = next((c for c in cs if c.get("homeAway") == "home"), {})
                    away = next((c for c in cs if c.get("homeAway") == "away"), {})
                    jogos.append({
                        "time_casa": home.get("team", {}).get("displayName", "?"),
                        "time_fora": away.get("team", {}).get("displayName", "?"),
                        "liga": nome_liga,
                        "endpoint": endpoint,
                    })
        except Exception as e:
            logger.debug(f"ESPN {endpoint} falhou: {e}")

    return jogos


def modo_analise_geral(liga_filtro: str = ""):
    """Modo: analisa próximos jogos com odds reais."""
    resumo = resumo_cache()
    logger.info(f"Cache: {resumo['jogadores']} jogadores, {resumo['partidas_registradas']} partidas")

    if resumo["jogadores"] == 0:
        logger.warning("Cache vazio! Primeiro rode o monitor ao vivo:")
        logger.warning("  python src/monitor_copa.py")
        logger.warning("  (ou configure BSD_TOKEN no .env para stats adicionais)")
        return

    artilheiros = top_jogadores(n=5)
    if artilheiros:
        logger.info("Top 5 artilheiros (cache):")
        for j in artilheiros:
            logger.info(f"  {j['nome']} ({j['time']}): {j['gols_por_90']:.2f} gols/90min")

    jogos = _buscar_proximos_jogos_espn()
    logger.info(f"Proximos jogos: {len(jogos)}")

    for jogo in jogos:
        if liga_filtro and liga_filtro.lower() not in jogo.get("liga", "").lower():
            continue
        logger.info(f"--- {jogo['time_casa']} vs {jogo['time_fora']} [{jogo.get('liga','')}] ---")
        analisar_e_disparar(jogo["time_casa"], jogo["time_fora"], liga=jogo.get("liga", ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analisador pré-jogo com odds reais")
    parser.add_argument("--loop", action="store_true", help="Modo contínuo (a cada 60min)")
    parser.add_argument("--liga", type=str, default="",
                        help="Filtrar por liga (ex: 'Brasileirão', 'World Cup')")
    args = parser.parse_args()

    logger.info("Analisador Pre-Jogo com ODDS REAIS")
    if os.getenv("BSD_TOKEN"):
        logger.info("  Fonte odds: BSD (Bzzoiro) - gratuito, 17+ casas")
    if os.getenv("BET365_COOKIE"):
        logger.info("  Fonte odds: bet365 (scraping opcional)")
    else:
        logger.info("  Fair odds: modelo probabilistico (fallback)")

    if args.loop:
        logger.info("Modo LOOP: analisando a cada 60 minutos")
        while True:
            modo_analise_geral(liga_filtro=args.liga)
            time.sleep(3600)
    else:
        modo_analise_geral(liga_filtro=args.liga)
