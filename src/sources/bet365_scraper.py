"""
Scraper opcional para odds da bet365 (cartão, chutes, gols por jogador).

Requer cookie de sessão logada na bet365. Se não configurado, o sistema
usa fair odds do modelo como referência.

Config no .env:
  BET365_COOKIE=sua_cookie
  BET365_USER_AGENT=seu_user_agent

AVISO: scraping pode quebrar a qualquer momento. Use por sua conta e risco.
"""
import logging
import os
import sys
import re
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import requests

logger = logging.getLogger(__name__)

_COOKIE = os.getenv("BET365_COOKIE", "")
_USER_AGENT = os.getenv("BET365_USER_AGENT",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
_BASE = "https://www.bet365.com"


def disponivel() -> bool:
    return bool(_COOKIE)


def _headers():
    return {
        "User-Agent": _USER_AGENT,
        "Cookie": _COOKIE,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://www.bet365.com/",
    }


def odds_partida(url_partida: str = None) -> dict:
    """
    Tenta extrair odds de jogadores de uma partida da bet365.
    Retorna dict com odds de cartão, chutes e gol se encontrar.

    ATENÇÃO: A bet365 não tem API pública. Este scraper é FRÁGIL
    e pode parar de funcionar a qualquer momento.
    """
    if not _COOKIE:
        return {"disponivel": False, "motivo": "BET365_COOKIE não configurado"}

    try:
        r = requests.get(url_partida or _BASE, headers=_headers(), timeout=15)
        texto = r.text

        odds_encontradas = {
            "cartoes": _extrair_odds(texto, "cartao", "amarelo"),
            "chutes": _extrair_odds(texto, "chutes", "gol"),
            "gols": _extrair_odds(texto, "marcar", "gol"),
        }

        return {
            "disponivel": True,
            "odds": odds_encontradas,
            "url": url_partida or _BASE,
        }
    except Exception as e:
        logger.warning(f"bet365 scraper falhou: {e}")
        return {"disponivel": False, "motivo": str(e)}


def _extrair_odds(texto: str, *palavras_chave: str) -> list:
    """Tenta extrair odds do HTML/JS da página (implementação frágil)."""
    resultados = []
    padroes = [
        r'["\'](?:player|jogador)["\']\s*[:=]\s*["\']([^"\']+)["\'].*?["\'](?:price|odd)["\']\s*[:=]\s*([\d.]+)',
        r'([A-Z][a-zçãáéíóú]+(?:\s+[A-Z][a-zçãáéíóú]+)+).*?(\d+\.\d+)',
    ]
    for padrao in padroes:
        for match in re.finditer(padrao, texto, re.IGNORECASE | re.DOTALL):
            nome = match.group(1).strip()
            try:
                odd = float(match.group(2))
                if 1.01 <= odd <= 100:
                    resultados.append({"jogador": nome, "odd": odd})
            except ValueError:
                continue

    if any(p in texto.lower() for p in palavras_chave):
        logger.debug(f"bet365: página contém palavras-chave {palavras_chave}")

    return resultados[:20]
