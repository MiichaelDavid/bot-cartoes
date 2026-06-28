"""
Envio de mensagens pro WhatsApp via CallMeBot (grátis, pessoal).

Setup (uma vez, ~2 min):
  1. Adicione o número do CallMeBot nos seus contatos e mande a mensagem de
     ativação que está em: https://www.callmebot.com/blog/free-api-whatsapp-messages/
  2. Você recebe de volta uma API key.
  3. Coloque no .env:
       CALLMEBOT_PHONE=55SEUNUMEROCOMDDD     (ex.: 5511999999999)
       CALLMEBOT_APIKEY=sua_api_key
"""
import os
import requests
from urllib.parse import quote


def enviar_whatsapp(texto: str,
                    phone: str = None,
                    apikey: str = None,
                    timeout: int = 20) -> bool:
    phone = phone or os.getenv("CALLMEBOT_PHONE", "")
    apikey = apikey or os.getenv("CALLMEBOT_APIKEY", "")
    if not phone or not apikey:
        print("[whatsapp] CALLMEBOT_PHONE/APIKEY não configurados — não enviei.")
        return False
    url = (
        "https://api.callmebot.com/whatsapp.php"
        f"?phone={phone}&text={quote(texto)}&apikey={apikey}"
    )
    try:
        r = requests.get(url, timeout=timeout)
        ok = r.status_code == 200
        if not ok:
            print(f"[whatsapp] falha HTTP {r.status_code}: {r.text[:120]}")
        return ok
    except requests.exceptions.RequestException as e:
        print(f"[whatsapp] erro de conexão: {e}")
        return False
