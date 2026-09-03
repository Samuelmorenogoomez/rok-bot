import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import urllib.parse

from config import COLOR_BOT

# Banderas → (código idioma, nombre para mostrar)
BANDERAS = {
    '🇬🇧': ('en', '🇬🇧 English'),
    '🇺🇸': ('en', '🇺🇸 English'),
    '🇪🇸': ('es', '🇪🇸 Español'),
    '🇹🇷': ('tr', '🇹🇷 Türkçe'),
    '🇩🇪': ('de', '🇩🇪 Deutsch'),
    '🇫🇷': ('fr', '🇫🇷 Français'),
    '🇮🇹': ('it', '🇮🇹 Italiano'),
    '🇵🇹': ('pt', '🇵🇹 Português'),
    '🇷🇴': ('ro', '🇷🇴 Română'),
    '🇵🇱': ('pl', '🇵🇱 Polski'),
    '🇷🇺': ('ru', '🇷🇺 Русский'),
    '🇨🇳': ('zh-CN', '🇨🇳 中文'),
}

NOMBRES_IDIOMA = {
    'en': '🇬🇧 English',
    'es': '🇪🇸 Español',
    'tr': '🇹🇷 Türkçe',
    'de': '🇩🇪 Deutsch',
    'fr': '🇫🇷 Français',
    'it': '🇮🇹 Italiano',
    'pt': '🇵🇹 Português',
    'ro': '🇷🇴 Română',
    'pl': '🇵🇱 Polski',
    'ru': '🇷🇺 Русский',
    'zh-CN': '🇨🇳 中文',
}


async def _traducir_async(texto: str, idioma_destino: str) -> str:
    """Traduce usando la API pública gratuita de Google Translate (sin API key)."""
    url = 'https://translate.googleapis.com/translate_a/single'
    params = {
        'client': 'gtx',
        'sl': 'auto',
        'tl': idioma_destino,
        'dt': 't',
        'q': texto,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json(content_type=None)
            # La respuesta es una lista anidada; concatenar los fragmentos traducidos
            return ''.join(part[0] for part in data[0] if part[0])


class Traduccion(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Reacción con bandera ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignorar reacciones del propio bot
        if payload.user_id == self.bot.user.id:
            return

        emoji = str(payload.emoji)
        if emoji not in BANDERAS:
            return

        idioma_code, idioma_nombre = BANDERAS[emoji]

        canal = self.bot.get_channel(payload.channel_id)
        if not canal:
            return

        try:
            mensaje = await canal.fetch_message(payload.message_id)
        except Exception:
            return

        texto = mensaje.content
        # Ignorar mensajes vacíos, muy cortos o que son solo comandos
        if not texto or len(texto.strip()) < 5 or texto.startswith('/'):
            return

        try:
            traduccion = await _traducir_async(texto, idioma_code)
        except Exception as e:
            print(f'[traduccion] Error al traducir: {e}')
            return

        # Si la traducción es idéntica al original, no responder (ya estaba en ese idioma)
        if traduccion.strip().lower() == texto.strip().lower():
            return

        embed = discord.Embed(description=traduccion[:2000], color=COLOR_BOT)
        embed.set_author(
            name=f'{idioma_nombre} · {mensaje.author.display_name}',
            icon_url=mensaje.author.display_avatar.url,
        )
        canal_origen = canal.mention if hasattr(canal, 'mention') else f'#{getattr(canal, "name", "?")}'
        embed.set_footer(text=f'Traducción privada de {canal_origen} · Private translation')

        # Enviar por DM al usuario que reaccionó (solo él lo ve)
        usuario = payload.member or self.bot.get_user(payload.user_id)
        if not usuario:
            try:
                usuario = await self.bot.fetch_user(payload.user_id)
            except Exception:
                return
        try:
            await usuario.send(embed=embed)
        except discord.Forbidden:
            # El usuario tiene los DMs cerrados — avisar solo a él en el canal con mensaje efímero
            # no es posible desde eventos, así que simplemente ignoramos
            pass

    # ── /traducir ──────────────────────────────────────────────────────────────

    @app_commands.command(
        name='traducir',
        description='Traduce un texto al idioma que elijas / Translate text to any language',
    )
    @app_commands.describe(
        texto='Texto a traducir / Text to translate',
        idioma='Idioma destino / Target language',
    )
    @app_commands.choices(idioma=[
        app_commands.Choice(name='🇬🇧 English',   value='en'),
        app_commands.Choice(name='🇪🇸 Español',   value='es'),
        app_commands.Choice(name='🇹🇷 Türkçe',   value='tr'),
        app_commands.Choice(name='🇩🇪 Deutsch',   value='de'),
        app_commands.Choice(name='🇫🇷 Français',  value='fr'),
        app_commands.Choice(name='🇮🇹 Italiano',  value='it'),
        app_commands.Choice(name='🇵🇹 Português', value='pt'),
        app_commands.Choice(name='🇷🇴 Română',    value='ro'),
        app_commands.Choice(name='🇵🇱 Polski',    value='pl'),
        app_commands.Choice(name='🇷🇺 Русский',   value='ru'),
    ])
    async def traducir(self, interaction: discord.Interaction, texto: str, idioma: str):
        await interaction.response.defer(ephemeral=True)

        try:
            traduccion = await _traducir_async(texto, idioma)
        except Exception as e:
            await interaction.followup.send(
                f'❌ Error al traducir. / Translation error: `{e}`', ephemeral=True
            )
            return

        nombre_idioma = NOMBRES_IDIOMA.get(idioma, idioma)
        embed = discord.Embed(
            title=f'🌐 Traducción / Translation → {nombre_idioma}',
            color=COLOR_BOT,
        )
        embed.add_field(name='Original',                      value=texto[:1024],      inline=False)
        embed.add_field(name='Traducción / Translation',      value=traduccion[:1024], inline=False)
        embed.set_footer(text='Powered by Google Translate · Gratis / Free')

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Traduccion(bot))
