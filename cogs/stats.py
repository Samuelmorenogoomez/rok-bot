import asyncio
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import COLOR_BOT
from db import database as db


def fmt_poder(n: int) -> str:
    if n >= 1_000_000_000:
        return f'{n / 1_000_000_000:.3f}'.rstrip('0').rstrip('.') + 'B'
    if n >= 1_000_000:
        return f'{n / 1_000_000:.3f}'.rstrip('0').rstrip('.') + 'M'
    return str(n)


# Roles que cuentan como gente de la alianza
ROLES_ALIANZA = {'👑 Liderazgo', '⚔️ R4', '🛡️ R3', '🌿 Miembro', '🔰 Nuevo'}

# Discord solo deja renombrar un canal 2 veces cada 10 minutos
MAX_RENOMBRES = 2
VENTANA_SEG   = 600

CANALES_STATS = ['stats_total', 'stats_poder', 'stats_kvk']


async def calcular_stats(guild: discord.Guild) -> dict:
    """Datos de la alianza contando solo a quien sigue en el servidor (más los gobernadores externos)."""
    en_alianza = [m for m in guild.members
                  if not m.bot and any(r.name in ROLES_ALIANZA for r in m.roles)]
    ids_en_servidor = {str(m.id) for m in guild.members}
    registrados = [m for m in await db.get_all_members(str(guild.id))
                   if m['user_id'].startswith('ext_') or m['user_id'] in ids_en_servidor]
    externos  = sum(1 for m in registrados if m['user_id'].startswith('ext_'))
    temporada = await db.kvk_get_active(str(guild.id))
    return {
        'miembros':    len(en_alianza) + externos,
        'registrados': registrados,
        'poder':       sum(m['poder'] for m in registrados),
        'temporada':   temporada,
    }


def nombres_canales(datos: dict) -> dict:
    temporada = datos['temporada']
    return {
        'stats_total':       f'👥 Miembros: {datos["miembros"]}',
        'stats_registrados': f'🌿 Registrados: {len(datos["registrados"])}',  # canal antiguo, si aún existe
        'stats_poder':       f'💪 Poder: {fmt_poder(datos["poder"])}',
        'stats_kvk':         f'⚔️ KvK: {temporada["nombre"][:20] if temporada else "Sin KvK"}',
    }


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._renombres: dict[int, list[float]] = {}  # canal → instantes de sus últimos renombres
        self.actualizar_stats.start()

    def cog_unload(self):
        self.actualizar_stats.cancel()

    @tasks.loop(minutes=10)
    async def actualizar_stats(self):
        for guild in self.bot.guilds:
            try:
                await self._update(guild)
            except Exception as e:
                print(f'[stats] Error actualizando {guild.name}: {type(e).__name__}: {e}')

    @actualizar_stats.before_loop
    async def before_stats(self):
        await self.bot.wait_until_ready()

    def _puede_renombrar(self, canal_id: int) -> float:
        """0 si se puede renombrar ya; si no, segundos que faltan."""
        ahora    = time.monotonic()
        recientes = [t for t in self._renombres.get(canal_id, []) if ahora - t < VENTANA_SEG]
        self._renombres[canal_id] = recientes
        if len(recientes) < MAX_RENOMBRES:
            return 0
        return VENTANA_SEG - (ahora - recientes[0])

    async def _update(self, guild: discord.Guild) -> list[str]:
        """Renombra los canales que hayan cambiado. Devuelve los que quedan pendientes por el límite de Discord."""
        datos   = await calcular_stats(guild)
        nombres = nombres_canales(datos)
        pendientes = []

        for clave, nombre in nombres.items():
            canal_id = await db.get_config(str(guild.id), clave)
            canal    = guild.get_channel(int(canal_id)) if canal_id else None
            if not canal or canal.name == nombre:
                continue
            espera = self._puede_renombrar(canal.id)
            if espera:
                pendientes.append(f'{nombre} (en ~{int(espera // 60) + 1} min)')
                continue
            self._renombres[canal.id].append(time.monotonic())
            try:
                # Nunca quedarse esperando a Discord: si nos frena, se reintenta en la siguiente vuelta
                await asyncio.wait_for(canal.edit(name=nombre, reason='Estadísticas'), timeout=15)
            except (asyncio.TimeoutError, discord.HTTPException) as e:
                print(f'[stats] No se pudo renombrar {canal.id}: {type(e).__name__}')
                pendientes.append(nombre)
        return pendientes

    # ── Comandos ──────────────────────────────────────────────────────────────

    @app_commands.command(name='stats-setup', description='[ADMIN] Crea los canales de estadísticas en tiempo real')
    @app_commands.describe(categoria='Categoría donde crear los canales de stats')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def stats_setup(self, interaction: discord.Interaction, categoria: discord.CategoryChannel):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        # Visibles para todos, pero nadie puede entrar: solo sirven para mostrar el dato
        ow = {guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False)}

        nombres    = nombres_canales(await calcular_stats(guild))
        creados    = 0
        existentes = 0
        for clave in CANALES_STATS:
            canal_id = await db.get_config(str(guild.id), clave)
            canal    = guild.get_channel(int(canal_id)) if canal_id else None
            if canal:
                await canal.edit(overwrites=ow, category=categoria)
                existentes += 1
                continue
            canal = await guild.create_voice_channel(nombres[clave], category=categoria, overwrites=ow)
            self._renombres[canal.id] = []
            await db.set_config(str(guild.id), clave, str(canal.id))
            creados += 1

        partes = []
        if creados:
            partes.append(f'{creados} creados')
        if existentes:
            partes.append(f'{existentes} ya existían')
        await interaction.followup.send(
            f'✅ Canales de estadísticas en **{categoria.name}**: {", ".join(partes)}. Se actualizan cada 10 minutos.',
            ephemeral=True,
        )

    @app_commands.command(name='stats-actualizar', description='[ADMIN] Fuerza la actualización inmediata de las estadísticas')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def stats_actualizar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        pendientes = await self._update(interaction.guild)
        if pendientes:
            await interaction.followup.send(
                '⏳ Actualizado lo que se podía. Discord solo deja renombrar un canal 2 veces cada 10 min, '
                'así que quedan pendientes:\n• ' + '\n• '.join(pendientes),
                ephemeral=True,
            )
        else:
            await interaction.followup.send('✅ Estadísticas al día.', ephemeral=True)

    @app_commands.command(name='stats-embed', description='Muestra un embed con las estadísticas completas de la alianza')
    async def stats_embed(self, interaction: discord.Interaction):
        datos       = await calcular_stats(interaction.guild)
        registrados = datos['registrados']  # ya vienen ordenados por poder
        temporada   = datos['temporada']

        distribucion: dict[str, int] = {}
        for m in registrados:
            distribucion[m['tropa']] = distribucion.get(m['tropa'], 0) + 1

        TROPAS = {'infanteria': '🗡️', 'caballeria': '🐴', 'arqueros': '🏹', 'maquinaria': '⚙️', 'mixto': '🔱'}

        embed = discord.Embed(
            title=f'📊 Estadísticas — {interaction.guild.name}',
            color=COLOR_BOT,
            timestamp=datetime.now(timezone.utc),
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.add_field(name='👥 Miembros alianza', value=str(datos['miembros']),  inline=True)
        embed.add_field(name='🌿 Registrados',       value=str(len(registrados)),   inline=True)
        embed.add_field(name='💪 Poder total',        value=fmt_poder(datos['poder']), inline=True)

        if registrados:
            embed.add_field(name='📊 Poder medio', value=fmt_poder(datos['poder'] // len(registrados)), inline=True)
            embed.add_field(name='🏆 Mayor poder',
                            value=f'{registrados[0]["gobernador"]} · {fmt_poder(registrados[0]["poder"])}', inline=True)
            embed.add_field(name='​', value='​', inline=True)

        if distribucion:
            dist_txt = '  '.join(f'{TROPAS.get(t, "?")} **{n}**'
                                 for t, n in sorted(distribucion.items(), key=lambda x: -x[1]))
            embed.add_field(name='Distribución de tropas', value=dist_txt, inline=False)

        if temporada:
            stats_kvk = await db.kvk_get_import_ranking(temporada['id'])
            embed.add_field(name='⚔️ KvK activo',
                            value=f'**{temporada["nombre"]}** · {len(stats_kvk)} jugadores con datos', inline=False)
        else:
            embed.add_field(name='⚔️ KvK', value='Sin temporada activa', inline=False)

        embed.set_footer(text='Solo cuenta a quien sigue en el servidor · Actualizado')
        await interaction.response.send_message(embed=embed)

    @stats_setup.error
    @stats_actualizar.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
