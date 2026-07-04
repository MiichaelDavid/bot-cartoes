"""
Bot do Discord para consultas interativas.

COMANDOS:
  /jogos [time]      - Jogos do dia na Copa / liga
  /sinais [time]     - Sinais pré-jogo disponiveis
  /stats <jogador>   - Estatisticas de um jogador no torneio
  /proximos          - Proximos jogos (Copa + Brasileirao)
  /cache             - Status do cache de jogadores
  /ajuda             - Lista de comandos

REQUER:
  DISCORD_BOT_TOKEN no .env (crie em https://discord.com/developers/applications)

USO:
  python src/bot_discord.py
"""
import logging
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import discord
from discord import app_commands

import src.config as config
from src.pre_match.cache_jogadores import (
    resumo_cache, top_jogadores, medias_jogador, todos_jogadores_do_time
)
from src.pre_match.analisador import gerar_sinais_time

import unicodedata

def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto_norm = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    ).lower()
    return texto_norm

_TRADUCOES_TIMES = {
    "franca": "france",
    "brasil": "brazil",
    "alemanha": "germany",
    "espanha": "spain",
    "belgica": "belgium",
    "inglaterra": "england",
    "italia": "italy",
    "holanda": "netherlands",
    "marrocos": "morocco",
    "noruega": "norway",
    "suecia": "sweden",
    "suica": "switzerland",
    "croacia": "croatia",
    "estados unidos": "united states",
    "eua": "united states",
    "turquia": "turkiye",
    "japao": "japan",
    "coreia do sul": "south korea",
    "africa do sul": "south africa",
    "arabia saudita": "saudi arabia",
    "paraguai": "paraguay",
    "uruguai": "uruguay",
    "equador": "ecuador",
    "colombia": "colombia",
}

def corresponder_time(termo_busca: str, nome_time_cache: str) -> bool:
    if not termo_busca:
        return True
    busca_norm = normalizar_texto(termo_busca)
    cache_norm = normalizar_texto(nome_time_cache)
    busca_traduzido = _TRADUCOES_TIMES.get(busca_norm, busca_norm)
    return busca_traduzido in cache_norm or busca_norm in cache_norm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bot-discord")

_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

intents = discord.Intents.default()
intents.message_content = True


from discord.ext import tasks
import datetime

class BotSinais(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info(f"Comandos sincronizados: {len(self.tree.get_commands())}")
        self.limpar_mensagens_antigas.start()

    async def on_ready(self):
        logger.info(f"Bot conectado como {self.user} (ID: {self.user.id})")

    @tasks.loop(minutes=30)
    async def limpar_mensagens_antigas(self):
        webhook_url = config.DISCORD_WEBHOOK_URL
        if not webhook_url or "/webhooks/" not in webhook_url:
            return
        try:
            channel_id = int(webhook_url.split("/webhooks/")[1].split("/")[0])
            channel = self.get_channel(channel_id)
            if not channel:
                channel = await self.fetch_channel(channel_id)
            
            limite_tempo = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=config.DISCORD_CLEAN_HOURS)
            
            # Deleta mensagens com mais de X horas
            def check(msg):
                return msg.created_at < limite_tempo
                
            deleted = await channel.purge(limit=100, check=check, before=limite_tempo)
            if deleted:
                logger.info(f"[LIMPEZA] Apagadas {len(deleted)} mensagens com mais de {config.DISCORD_CLEAN_HOURS}h no canal {channel_id}")
        except Exception as e:
            logger.warning(f"Erro na limpeza automatica de mensagens: {e}")


bot = BotSinais()


async def _buscar_jogos_espn(endpoint: str = "fifa.world") -> list:
    import requests
    H = {"User-Agent": "Mozilla/5.0"}
    jogos = []
    try:
        sb = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{endpoint}/scoreboard",
            headers=H, timeout=20
        ).json()
        nome_liga = (sb.get("leagues") or [{}])[0].get("name", endpoint)
        for e in sb.get("events", []):
            comp = (e.get("competitions") or [{}])[0]
            status = comp.get("status", {}).get("type", {}).get("state", "")
            cs = comp.get("competitors", [])
            home = next((c for c in cs if c.get("homeAway") == "home"), {})
            away = next((c for c in cs if c.get("homeAway") == "away"), {})
            placar = f"{home.get('score','?')}-{away.get('score','?')}"
            clock = comp.get("status", {}).get("displayClock", "")
            jogos.append({
                "time_casa": home.get("team", {}).get("displayName", "?"),
                "time_fora": away.get("team", {}).get("displayName", "?"),
                "placar": placar,
                "status": status,
                "clock": clock,
                "liga": nome_liga,
            })
    except Exception as e:
        logger.warning(f"ESPN {endpoint} falhou: {e}")
    return jogos


@bot.tree.command(name="jogos", description="Mostra os jogos do dia")
@app_commands.describe(time="Filtrar por time (opcional)")
async def cmd_jogos(interaction: discord.Interaction, time: str = None):
    logger.info(f"Comando /jogos recebido de {interaction.user} (time: {time})")
    await interaction.response.defer()
    endpoints = [("fifa.world", "Copa do Mundo"), ("bra.1", "Brasileirao")]
    linhas = []
    for ep, nome in endpoints:
        jogos = await _buscar_jogos_espn(ep)
        if not jogos:
            continue
        vivos = [j for j in jogos if j["status"] == "in"]
        previstos = [j for j in jogos if j["status"] in ("pre", "scheduled")]
        if vivos:
            linhas.append(f"\n**{nome} — AO VIVO**")
            for j in vivos:
                if time and not (corresponder_time(time, j["time_casa"]) or corresponder_time(time, j["time_fora"])):
                    continue
                linhas.append(f"  {j['time_casa']} x {j['time_fora']}  `{j['placar']}`  {j['clock']}")
        if previstos:
            linhas.append(f"\n**{nome} — Proximos**")
            for j in previstos:
                if time and not (corresponder_time(time, j["time_casa"]) or corresponder_time(time, j["time_fora"])):
                    continue
                linhas.append(f"  {j['time_casa']} x {j['time_fora']}")

    if not linhas:
        await interaction.followup.send("Nenhum jogo encontrado.")
        return
    embed = discord.Embed(title="Jogos do Dia", description="\n".join(linhas), color=0x2ECC71)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="sinais", description="Mostra sinais pre-jogo disponiveis")
@app_commands.describe(time="Filtrar por time (opcional)")
async def cmd_sinais(interaction: discord.Interaction, time: str = None):
    logger.info(f"Comando /sinais recebido de {interaction.user} (time: {time})")
    await interaction.response.defer()
    resumo = resumo_cache()
    if resumo["jogadores"] == 0:
        await interaction.followup.send("Cache vazio. Rode `monitor_copa.py` primeiro para acumular stats.")
        return

    times = resumo["times"]
    if time:
        times = [t for t in times if corresponder_time(time, t)]

    if not times:
        await interaction.followup.send(f"Time '{time}' nao encontrado no cache.")
        return

    linhas = []
    limite = 20 if time else 8
    for t in times[:4]:
        sinais = gerar_sinais_time(t, "?", liga="")
        if sinais:
            linhas.append(f"\n**{t}** — {len(sinais)} sinais")
            for s in sinais[:limite]:
                ev = f"EV {s['ev']*100:.1f}%" if s.get('ev') is not None else f"fair {s['odd_justa']}"
                linhas.append(f"  {s['tipo'].upper()}: {s['jogador']} ({s['prob']*100:.0f}%, {ev})")
            if len(sinais) > limite:
                linhas.append(f"  ... +{len(sinais)-limite} sinais")

    if not linhas:
        await interaction.followup.send("Nenhum sinal disponivel (cache sem dados suficientes).")
        return

    embed = discord.Embed(title="Sinais Pre-Jogo", description="\n".join(linhas), color=0xF1C40F)
    embed.set_footer(text="Use fair odds como referencia se nao houver odd real")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="stats", description="Estatisticas de um jogador no torneio")
@app_commands.describe(jogador="Nome do jogador")
async def cmd_stats(interaction: discord.Interaction, jogador: str):
    logger.info(f"Comando /stats recebido de {interaction.user} (jogador: {jogador})")
    await interaction.response.defer()
    med = medias_jogador(jogador, ultimas_n=5)
    if not med:
        await interaction.followup.send(f"Jogador '{jogador}' nao encontrado no cache.")
        return

    embed = discord.Embed(
        title=f"{med['nome']} ({med['time']})",
        description=f"Posicao: {med['posicao']} | {med['n_partidas']} jogos | {med['minutos_totais']} min",
        color=0x3498DB
    )
    embed.add_field(name="Faltas/90min", value=f"{med['faltas_por_90']:.2f}", inline=True)
    embed.add_field(name="Amarelos/90min", value=f"{med['amarelos_por_90']:.2f}", inline=True)
    embed.add_field(name="Chutes a Gol/90min", value=f"{med['chutes_gol_por_90']:.2f}", inline=True)
    embed.add_field(name="Gols/90min", value=f"{med['gols_por_90']:.3f}", inline=True)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="proximos", description="Proximos jogos (Copa + Brasileirao)")
async def cmd_proximos(interaction: discord.Interaction):
    logger.info(f"Comando /proximos recebido de {interaction.user}")
    await interaction.response.defer()
    endpoints = [("fifa.world", "Copa do Mundo"), ("bra.1", "Brasileirao Serie A")]
    linhas = []
    for ep, nome in endpoints:
        jogos = await _buscar_jogos_espn(ep)
        previstos = [j for j in jogos if j["status"] in ("pre", "scheduled")]
        if previstos:
            linhas.append(f"\n**{nome}**")
            for j in previstos[:6]:
                linhas.append(f"  {j['time_casa']} x {j['time_fora']}")
            if len(previstos) > 6:
                linhas.append(f"  ... +{len(previstos)-6} jogos")

    if not linhas:
        await interaction.followup.send("Nenhum jogo programado.")
        return
    embed = discord.Embed(title="Proximos Jogos", description="\n".join(linhas), color=0x9B59B6)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="cache", description="Status do cache de jogadores")
async def cmd_cache(interaction: discord.Interaction):
    logger.info(f"Comando /cache recebido de {interaction.user}")
    resumo = resumo_cache()
    top = top_jogadores(n=5)
    desc = (f"Jogadores no cache: **{resumo['jogadores']}**\n"
            f"Partidas registradas: **{resumo['partidas_registradas']}**\n"
            f"Times: **{len(resumo['times'])}**\n"
            f"Times: {', '.join(sorted(resumo['times'])[:8])}")
    if top:
        desc += "\n\n**Top 5 artilheiros (gols/90min):**\n"
        for j in top:
            desc += f"{j['nome']} ({j['time']}): {j['gols_por_90']:.3f}\n"
    embed = discord.Embed(title="Cache de Jogadores", description=desc, color=0x1ABC9C)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ajuda", description="Lista de comandos do bot")
async def cmd_ajuda(interaction: discord.Interaction):
    logger.info(f"Comando /ajuda recebido de {interaction.user}")
    desc = (
        "**/jogos** `[time]` — Jogos do dia (ao vivo + proximos)\n"
        "**/sinais** `[time]` — Sinais pre-jogo com odds\n"
        "**/stats** `<jogador>` — Estatisticas do jogador\n"
        "**/proximos** — Proximos jogos programados\n"
        "**/cache** — Status do cache de jogadores\n"
        "**/ajuda** — Esta mensagem\n\n"
        "Dados via ESPN (keyless) + BSD (odds reais).\n"
        "Alertas automaticos sao enviados via webhook."
    )
    embed = discord.Embed(title="Comandos do Bot de Sinais", description=desc, color=0x95A5A6)
    await interaction.response.send_message(embed=embed)


def rodar():
    if not _TOKEN:
        logger.error("DISCORD_BOT_TOKEN nao configurado no .env")
        logger.error("Crie em: https://discord.com/developers/applications")
        return
    logger.info("Iniciando bot do Discord...")
    logger.info(f"Comandos registrados: /jogos, /sinais, /stats, /proximos, /cache, /ajuda")
    bot.run(_TOKEN)


if __name__ == "__main__":
    rodar()
