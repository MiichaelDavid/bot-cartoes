"""
Notificador Discord (webhook) — serve as duas estratégias (cartão e chutes).
Recebe um dict já pronto e só monta o banner claro.
"""
import logging
import requests
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.config as config

logger = logging.getLogger(__name__)
COR = {"cartao": 0xF1C40F, "chutes": 0x3498DB}   # amarelo / azul


def _webhook() -> str:
    return config.DISCORD_WEBHOOK_URL


def enviar_discord(sinal: dict) -> bool:
    """
    sinal: tipo ('cartao'|'chutes'), jogo, competicao, placar, minuto,
           aposta_txt, prob (0-1), odd_min, motivo
    """
    url = _webhook()
    if not url:
        return False

    prob = sinal["prob"] * 100
    rotulo = "MUITO ALTA" if prob >= 70 else "ALTA" if prob >= 60 else "BOA"
    titulo = "🟨 SINAL DE CARTÃO" if sinal["tipo"] == "cartao" else "🎯 SINAL DE CHUTES A GOL"

    embed = {
        "title": titulo,
        "description": f"⚽ **{sinal.get('jogo','')}**  —  {int(sinal['minuto'])}' "
                       f"(placar {sinal.get('placar','?')})\n_{sinal.get('competicao','')}_",
        "color": COR.get(sinal["tipo"], 0x95A5A6),
        "fields": [
            {"name": "✅ O QUE APOSTAR", "value": f"**{sinal['aposta_txt']}**", "inline": False},
            {"name": "📊 Chance", "value": f"**{prob:.0f}%** ({rotulo})", "inline": True},
            {"name": "💰 Só aposte se a casa pagar", "value": f"**{sinal['odd_min']:.2f} ou mais**", "inline": True},
            {"name": "📌 Por quê", "value": sinal["motivo"], "inline": False},
        ],
        "footer": {"text": "Na bet365, ache esse mercado do jogador. "
                           "Odd MAIOR que o mínimo = vale. Menor = pule. Estimativa, não garantia."},
    }
    try:
        r = requests.post(url, json={"username": "Bot de Cartões", "embeds": [embed]}, timeout=15)
        ok = r.status_code in (200, 204)
        if not ok:
            logger.error(f"Discord HTTP {r.status_code}: {r.text[:120]}")
        return ok
    except requests.exceptions.RequestException as e:
        logger.error(f"Discord erro: {e}")
        return False
