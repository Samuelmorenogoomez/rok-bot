import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone

from config import COLOR_BOT
from db import database as db


def fmt_poder(n: int) -> str:
    if n >= 1_000_000_000:
        return f'{n / 1_000_000_000:.3f}'.rstrip('0').rstrip('.') + 'B'
    if n >= 1_000_000:
        return f'{n / 1_000_000:.3f}'.rstrip('0').rstrip('.') + 'M'
    return str(n)


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.actualizar_stats.start()

    def cog_unload(self):
        self.actualizar_stats.cancel()

    @tasks.loop(minutes=5)
    async def actualizar_stats(self):
        for guild in self.bot.guilds:
            try:
                await self._update(guild)
            except Exception as e:
                print(f'[stats] Error actualizando {guild.name}: {type(e).__name__}: {e}')

    @actualizar_stats.before_loop
    async def before_stats(self):
        await self.bot.wait_until_ready()
        print('[stats] Tarea de estadísticas iniciada')

    async def _update(self, guild: discord.Guild):
        # Leer IDs de canales configurados
        ids = {
            'total':       await db.get_config(str(guild.id), 'stats_total'),
            'registrados': await db.get_config(str(guild.id), 'stats_registrados'),
            'poder':       await db.get_config(str(guild.id), 'stats_poder'),
            'kvk':         await db.get_config(str(guild.id), 'stats_kvk'),
        }
        if not any(ids.values()):
            return

        # Calcular datos
        total_discord   = guild.member_count
        miembros_db     = await db.get_all_members(str(guild.id))
        registrados     = len(miembros_db)
        poder_total     = sum(m['poder'] for m in miembros_db)
        temporada       = await db.kvk_get_active(str(guild.id))

        nombres = {
            'total':       f'👥 Miembros: {total_discord}',
            'registrados': f'🌿 Registrados: {registrados}',
            'poder':       f'💪 Poder: {fmt_poder(poder_total)}',
            'kvk':         f'⚔️ KvK: {temporada["nombre"][:15] if temporada else "Sin KvK"}',
        }

        for clave, canal_id in ids.items():
            if not canal_id:
                continue
            canal = guild.get_channel(int(canal_id))
            if canal and canal.name != nombres[clave]:
                try:
                    await canal.edit(name=nombres[clave])
                except Exception:
                    pass

    # ── Comandos ──────────────────────────────────────────────────────────────

    @app_commands.command(name='stats-setup', description='[ADMIN] Crea los canales de estadísticas en tiempo real')
    @app_commands.describe(categoria='Categoría donde crear los canales de stats')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def stats_setup(self, interaction: discord.Interaction, categoria: discord.CategoryChannel):
        await interaction.response.defer(ephemeral=True)

        ow = {
            role: discord.PermissionOverwrite(view_channel=True, connect=False)
            for role in interaction.guild.roles
        }
        ow[interaction.guild.default_role] = discord.PermissionOverwrite(
            view_channel=True, connect=False
        )

        canales = [
            ('stats_total',       f'👥 Miembros: {interaction.guild.member_count}'),
            ('stats_registrados', '🌿 Registrados: 0'),
            ('stats_poder',       '💪 Poder: 0'),
            ('stats_kvk',         '⚔️ KvK: Sin KvK'),
        ]

        creados    = 0
        existentes = 0

        for clave, nombre in canales:
            canal_id_guardado = await db.get_config(str(interaction.guild_id), clave)

            # Si ya existe en la BD, solo actualiza permisos
            if canal_id_guardado:
                canal = interaction.guild.get_channel(int(canal_id_guardado))
                if canal:
                    await canal.edit(overwrites=ow)
                    existentes += 1
                    continue

            # Si no existe, crear
            canal = await interaction.guild.create_voice_channel(
                nombre, category=categoria, overwrites=ow
            )
            await db.set_config(str(interaction.guild_id), clave, str(canal.id))
            creados += 1

        await self._update(interaction.guild)

        partes = []
        if creados:    partes.append(f'{creados} creados')
        if existentes: partes.append(f'{existentes} ya existían (actualizados)')
        await interaction.followup.send(
            f'✅ Canales de estadísticas en **{categoria.name}**: {", ".join(partes)}. Se actualizan cada 5 minutos.',
            ephemeral=True,
        )

    @app_commands.command(name='stats-actualizar', description='[ADMIN] Fuerza la actualización inmediata de las estadísticas')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def stats_actualizar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._update(interaction.guild)
        await interaction.followup.send('✅ Estadísticas actualizadas.', ephemeral=True)

    @app_commands.command(name='stats-embed', description='Muestra un embed con las estadísticas completas de la alianza')
    async def stats_embed(self, interaction: discord.Interaction):
        miembros  = await db.get_all_members(str(interaction.guild_id))
        temporada = await db.kvk_get_active(str(interaction.guild_id))

        total_discord = interaction.guild.member_count
        registrados   = len(miembros)
        poder_total   = sum(m['poder'] for m in miembros)

        distribucion: dict[str, int] = {}
        for m in miembros:
            distribucion[m['tropa']] = distribucion.get(m['tropa'], 0) + 1

        TROPAS = {'infanteria': '🗡️', 'caballeria': '🐴', 'arqueros': '🏹', 'maquinaria': '⚙️', 'mixto': '🔀'}

        embed = discord.Embed(
            title=f'📊 Estadísticas — {interaction.guild.name}',
            color=COLOR_BOT,
            timestamp=datetime.now(timezone.utc),
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.add_field(name='👥 Miembros Discord', value=str(total_discord), inline=True)
        embed.add_field(name='🌿 Registrados',       value=str(registrados),   inline=True)
        embed.add_field(name='💪 Poder total',        value=fmt_poder(poder_total), inline=True)

        if registrados > 0:
            embed.add_field(
                name='📊 Poder medio',
                value=fmt_poder(poder_total // registrados),
                inline=True,
            )
            embed.add_field(
                name='🏆 Mayor poder',
                value=fmt_poder(miembros[0]['poder']) if miembros else '—',
                inline=True,
            )
            embed.add_field(name='​', value='​', inline=True)

        if distribucion:
            dist_txt = '  '.join(f'{TROPAS.get(t,"?")} **{n}**' for t, n in sorted(distribucion.items(), key=lambda x: -x[1]))
            embed.add_field(name='Distribución de tropas', value=dist_txt, inline=False)

        if temporada:
            stats_kvk = await db.kvk_get_import_ranking(temporada['id'])
            embed.add_field(
                name='⚔️ KvK activo',
                value=f'**{temporada["nombre"]}** · {len(stats_kvk)} jugadores con datos',
                inline=False,
            )
        else:
            embed.add_field(name='⚔️ KvK', value='Sin temporada activa', inline=False)

        embed.set_footer(text='Actualizado')
        await interaction.response.send_message(embed=embed)

    @stats_setup.error
    @stats_actualizar.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
