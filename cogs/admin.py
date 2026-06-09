import json
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import COLOR_BOT, ALIANZA_FULL, REINO
from db import database as db

ZONA = ZoneInfo('Europe/Madrid')

TROPAS_EMOJI = {
    'infanteria': '🗡️', 'caballeria': '🐴',
    'arqueros': '🏹', 'maquinaria': '⚙️', 'mixto': '🔀',
}


def fmt_poder(n: int) -> str:
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.0f}K'
    return str(n)


async def build_panel_embed(guild: discord.Guild) -> discord.Embed:
    now  = datetime.now(ZONA)
    embed = discord.Embed(
        title=f'🔥 Panel de Control — {ALIANZA_FULL}',
        description=f'*Reino {REINO} · {guild.name}*',
        color=COLOR_BOT,
        timestamp=datetime.now(timezone.utc),
    )

    # ── Cola de títulos ───────────────────────────────────────────────────────
    cola = await db.get_queue(str(guild.id))
    if cola:
        lineas = []
        for i, r in enumerate(cola[:5], 1):
            from config import TITULOS
            t = TITULOS.get(r['titulo'], {})
            lineas.append(f'**{i}.** <@{r["user_id"]}> → {t.get("emoji","❓")} {t.get("nombre", r["titulo"])}')
        if len(cola) > 5:
            lineas.append(f'_...y {len(cola) - 5} más_')
        embed.add_field(name=f'🏰 Cola de títulos ({len(cola)})', value='\n'.join(lineas), inline=False)
    else:
        embed.add_field(name='🏰 Cola de títulos', value='_Vacía_', inline=False)

    # ── KvK activo ────────────────────────────────────────────────────────────
    temporada = await db.kvk_get_active(str(guild.id))
    if temporada:
        ranking = await db.kvk_get_ranking(temporada['id'])
        medallas = ['🥇', '🥈', '🥉']
        lineas = []
        for i, s in enumerate(ranking[:3]):
            total = s['kills_t4'] + s['kills_t5']
            lineas.append(f'{medallas[i]} **{s["username"]}** — {total:,} kills')
        if not lineas:
            lineas = ['_Nadie ha registrado bajas aún_']
        embed.add_field(
            name=f'⚔️ KvK: {temporada["nombre"]}',
            value='\n'.join(lineas),
            inline=False,
        )
    else:
        embed.add_field(name='⚔️ KvK', value='_Sin temporada activa_', inline=False)

    # ── Próximos eventos ──────────────────────────────────────────────────────
    eventos = await db.get_guild_events(str(guild.id))
    DIAS_NOMBRE = {'0': 'Lun', '1': 'Mar', '2': 'Mié', '3': 'Jue', '4': 'Vie', '5': 'Sáb', '6': 'Dom'}
    if eventos:
        lineas = []
        for ev in eventos[:4]:
            dias_str = ', '.join(DIAS_NOMBRE.get(d, d) for d in ev['dias'].split(','))
            lineas.append(f'📅 **{ev["nombre"]}** — {ev["hora"]} ({dias_str})')
        embed.add_field(name='📅 Eventos programados', value='\n'.join(lineas), inline=False)
    else:
        embed.add_field(name='📅 Eventos', value='_Sin eventos programados_', inline=False)

    # ── Estadísticas de miembros ──────────────────────────────────────────────
    miembros = await db.get_all_members(str(guild.id))
    if miembros:
        total_poder = sum(m['poder'] for m in miembros)
        distribucion = {}
        for m in miembros:
            distribucion[m['tropa']] = distribucion.get(m['tropa'], 0) + 1
        dist_str = ' · '.join(f'{TROPAS_EMOJI.get(t,"?")} {n}' for t, n in sorted(distribucion.items(), key=lambda x: -x[1]))
        embed.add_field(
            name=f'👥 Miembros registrados — {len(miembros)}',
            value=f'💪 Poder total: **{fmt_poder(total_poder)}**\n{dist_str}',
            inline=False,
        )
    else:
        embed.add_field(name='👥 Miembros', value='_Nadie registrado aún_', inline=False)

    # ── Encuestas activas ─────────────────────────────────────────────────────
    encuestas = await db.get_all_active_encuestas()
    enc_guild = [e for e in encuestas if e['guild_id'] == str(guild.id)]
    if enc_guild:
        lineas = [f'📊 **{e["pregunta"][:50]}**' for e in enc_guild[:3]]
        embed.add_field(name=f'📊 Encuestas activas ({len(enc_guild)})', value='\n'.join(lineas), inline=False)

    embed.set_footer(text=f'Actualizado · {now.strftime("%H:%M")} hora España')
    return embed


class RefreshView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Actualizar', emoji='🔄', style=discord.ButtonStyle.secondary, custom_id='panel:refresh')
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Solo los admins pueden actualizar el panel.', ephemeral=True)
            return
        embed = await build_panel_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(RefreshView())

    # ── /panel ────────────────────────────────────────────────────────────────

    @app_commands.command(name='panel', description='[ADMIN] Panel de control con el estado de todo el servidor')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        embed = await build_panel_embed(interaction.guild)
        await interaction.followup.send(embed=embed, view=RefreshView())

    # ── /anunciar ─────────────────────────────────────────────────────────────

    @app_commands.command(name='anunciar', description='[ADMIN] Publica un anuncio formateado')
    @app_commands.describe(
        titulo='Título del anuncio',
        mensaje='Cuerpo del anuncio (usa \\n para saltos de línea)',
        tipo='Tipo de anuncio (cambia el color)',
        rol='Rol al que mencionar (opcional)',
        imagen='URL de imagen para adjuntar (opcional)',
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name='📢 General',     value='general'),
        app_commands.Choice(name='⚔️ Guerra/KvK', value='guerra'),
        app_commands.Choice(name='🚨 Urgente',     value='urgente'),
        app_commands.Choice(name='✅ Positivo',    value='positivo'),
        app_commands.Choice(name='📅 Evento',      value='evento'),
        app_commands.Choice(name='ℹ️ Info',        value='info'),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def anunciar(
        self,
        interaction: discord.Interaction,
        titulo: str,
        mensaje: str,
        tipo: str = 'general',
        rol: discord.Role = None,
        imagen: str = None,
    ):
        COLORES = {
            'general':  COLOR_BOT,
            'guerra':   0xFF4444,
            'urgente':  0xFF0000,
            'positivo': 0x00FF7F,
            'evento':   0x5865F2,
            'info':     0x00BFFF,
        }
        ICONOS = {
            'general': '📢', 'guerra': '⚔️', 'urgente': '🚨',
            'positivo': '✅', 'evento': '📅', 'info': 'ℹ️',
        }

        embed = discord.Embed(
            title=f'{ICONOS[tipo]} {titulo}',
            description=mensaje.replace('\\n', '\n'),
            color=COLORES[tipo],
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        if imagen:
            embed.set_image(url=imagen)
        embed.set_footer(text=interaction.guild.name)

        contenido = rol.mention if rol else ''
        await interaction.response.send_message(content=contenido, embed=embed)

    # ── /resumen-miembros ─────────────────────────────────────────────────────

    @app_commands.command(name='resumen-miembros', description='[ADMIN] Resumen detallado de todos los miembros registrados')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def resumen_miembros(self, interaction: discord.Interaction):
        miembros = await db.get_all_members(str(interaction.guild_id))
        if not miembros:
            await interaction.response.send_message('No hay miembros registrados.', ephemeral=True)
            return

        total_poder = sum(m['poder'] for m in miembros)
        top5        = miembros[:5]
        distribucion = {}
        for m in miembros:
            distribucion[m['tropa']] = distribucion.get(m['tropa'], 0) + 1

        embed = discord.Embed(title=f'👥 Resumen de miembros — {len(miembros)} registrados', color=COLOR_BOT)
        embed.add_field(name='💪 Poder total',   value=fmt_poder(total_poder), inline=True)
        embed.add_field(name='📊 Poder medio',   value=fmt_poder(total_poder // len(miembros)), inline=True)
        embed.add_field(name='🏆 Poder máximo',  value=fmt_poder(miembros[0]['poder']), inline=True)

        dist_lines = '\n'.join(f'{TROPAS_EMOJI.get(t,"?")} **{t.capitalize()}**: {n} jugadores' for t, n in sorted(distribucion.items(), key=lambda x: -x[1]))
        embed.add_field(name='🔢 Distribución de tropas', value=dist_lines, inline=False)

        top_lines = '\n'.join(f'**{i}.** {TROPAS_EMOJI.get(m["tropa"],"?")} **{m["gobernador"]}** — {fmt_poder(m["poder"])}' for i, m in enumerate(top5, 1))
        embed.add_field(name='🥇 Top 5 por poder', value=top_lines, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='config-canal', description='[ADMIN] Configura en qué canal funciona cada tipo de comando')
    @app_commands.describe(
        tipo='Tipo de comandos a restringir',
        canal='Canal donde funcionarán esos comandos',
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name='🏰 Cola de títulos  (/pedir, /cola...)',        value='titulos'),
        app_commands.Choice(name='⚔️ KvK  (/kvk-matar, /kvk-ranking...)',        value='kvk'),
        app_commands.Choice(name='📊 Encuestas  (/encuesta, /fecha, /si-no)',     value='encuestas'),
        app_commands.Choice(name='👥 Miembros  (/registrar, /perfil, /miembros)', value='miembros'),
        app_commands.Choice(name='🔍 Comandantes  (/comandante, /equipo...)',     value='comandantes'),
        app_commands.Choice(name='📝 MGE Inscripciones  (/mge-lista, /mge-inscribir...)', value='mge-inscripciones'),
        app_commands.Choice(name='🏆 MGE Resultados  (/mge-seleccionados...)',           value='mge-resultados'),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config_canal(self, interaction: discord.Interaction, tipo: str, canal: discord.TextChannel):
        await db.set_canal_config(str(interaction.guild_id), tipo, str(canal.id))

        NOMBRES = {
            'titulos': '🏰 Cola de títulos', 'kvk': '⚔️ KvK',
            'encuestas': '📊 Encuestas', 'miembros': '👥 Miembros',
            'comandantes': '🔍 Comandantes',
        }
        await interaction.response.send_message(
            f'✅ **{NOMBRES[tipo]}** → ahora solo funciona en {canal.mention}',
            ephemeral=True
        )

    @app_commands.command(name='ver-canales', description='[ADMIN] Muestra la configuración de canales actual')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ver_canales(self, interaction: discord.Interaction):
        configs = await db.get_all_canales_config(str(interaction.guild_id))
        NOMBRES = {
            'titulos': '🏰 Cola de títulos', 'kvk': '⚔️ KvK',
            'encuestas': '📊 Encuestas', 'miembros': '👥 Miembros',
            'comandantes': '🔍 Comandantes',
        }
        embed = discord.Embed(title='⚙️ Configuración de canales', color=COLOR_BOT)
        if not configs:
            embed.description = '_Sin restricciones configuradas. Los comandos funcionan en cualquier canal._'
        else:
            for c in configs:
                canal = interaction.guild.get_channel(int(c['canal_id']))
                embed.add_field(
                    name=NOMBRES.get(c['tipo'], c['tipo']),
                    value=canal.mention if canal else '⚠️ Canal eliminado',
                    inline=True,
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='sync-comandos', description='[ADMIN] Fuerza la resincronización de todos los comandos slash')
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_comandos(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        # 1. Primero copiar todos los comandos al servidor y sincronizar
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)
        # 2. Luego borrar comandos globales de Discord (evita duplicados)
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()
        await interaction.followup.send(
            f'✅ {len(synced)} comandos sincronizados al servidor. Comandos globales eliminados.\nHaz **Ctrl+R** en Discord para verlos actualizados.',
            ephemeral=True,
        )

    @panel.error
    @anunciar.error
    @resumen_miembros.error
    @config_canal.error
    @sync_comandos.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
