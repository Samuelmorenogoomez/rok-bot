import discord
from discord import app_commands
from discord.ext import commands

from config import TITULOS, COLOR_BOT, ALIANZA_TAG, REINO
from checks import solo_en_canal
from db import database as db


# ── Embed de cola ──────────────────────────────────────────────────────────────

def build_embed(cola: list) -> discord.Embed:
    embed = discord.Embed(title='🏰 Cola de Títulos', color=COLOR_BOT)
    if not cola:
        embed.description = '_La cola está vacía. Pulsa un título para unirte._'
    else:
        lineas = []
        for i, row in enumerate(cola, 1):
            t = TITULOS[row['titulo']]
            lineas.append(f'**{i}.** <@{row["user_id"]}> → {t["emoji"]} **{t["nombre"]}** _{t["buff"]}_')
        embed.description = '\n'.join(lineas)
    embed.set_footer(text=f'{len(cola)} en cola · {ALIANZA_TAG} · Reino {REINO}')
    return embed


# ── Actualizar panel fijado ────────────────────────────────────────────────────

async def update_panel(bot: commands.Bot, guild: discord.Guild):
    canal_id   = await db.get_config(str(guild.id), 'titulos_panel_canal')
    mensaje_id = await db.get_config(str(guild.id), 'titulos_panel_mensaje')
    if not canal_id or not mensaje_id:
        return
    canal = guild.get_channel(int(canal_id))
    if not canal:
        return
    try:
        msg  = await canal.fetch_message(int(mensaje_id))
        cola = await db.get_queue(str(guild.id))
        await msg.edit(embed=build_embed(cola), view=ColaPanelView(bot))
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


# ── Botones del panel ──────────────────────────────────────────────────────────

class TituloButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, titulo_key: str):
        t = TITULOS[titulo_key]
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=t['nombre'],
            emoji=t['emoji'],
            custom_id=f'titulo:{titulo_key}',
            row=0,
        )
        self.bot       = bot
        self.titulo_key = titulo_key

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_id  = str(interaction.user.id)
        t        = TITULOS[self.titulo_key]

        cola     = await db.get_queue(guild_id)
        existing = next((r for r in cola if r['user_id'] == user_id), None)

        if existing:
            if existing['titulo'] == self.titulo_key:
                pos = next(i + 1 for i, r in enumerate(cola) if r['user_id'] == user_id)
                await interaction.response.send_message(
                    f'ℹ️ Ya estás en cola para {t["emoji"]} **{t["nombre"]}** — posición **#{pos}**.',
                    ephemeral=True,
                )
            else:
                t_actual = TITULOS[existing['titulo']]
                await interaction.response.send_message(
                    f'⚠️ Ya estás esperando {t_actual["emoji"]} **{t_actual["nombre"]}**. '
                    f'Pulsa **❌ Cancelar** primero si quieres cambiarlo.',
                    ephemeral=True,
                )
            return

        ok = await db.add_to_queue(guild_id, user_id, interaction.user.display_name, self.titulo_key)
        if not ok:
            await interaction.response.send_message('⚠️ Ya estás en la cola.', ephemeral=True)
            return

        cola = await db.get_queue(guild_id)
        pos  = next(i + 1 for i, r in enumerate(cola) if r['user_id'] == user_id)

        await interaction.response.send_message(
            f'✅ En cola → {t["emoji"]} **{t["nombre"]}** · Posición **#{pos}**',
            ephemeral=True,
        )
        await update_panel(self.bot, interaction.guild)


class CancelarPanelButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label='Cancelar mi petición',
            emoji='❌',
            custom_id='titulo:cancelar',
            row=1,
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        ok = await db.remove_from_queue(str(interaction.guild_id), str(interaction.user.id))
        if not ok:
            await interaction.response.send_message(
                'ℹ️ No tienes ninguna petición activa en la cola.',
                ephemeral=True,
            )
            return
        await interaction.response.send_message('✅ Tu petición ha sido cancelada.', ephemeral=True)
        await update_panel(self.bot, interaction.guild)


class ColaPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        for key in TITULOS:
            self.add_item(TituloButton(bot, key))
        self.add_item(CancelarPanelButton(bot))


# ── Cog ────────────────────────────────────────────────────────────────────────

class Titulos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Registrar la view persistente para que los botones funcionen tras reiniciar el bot
        self.bot.add_view(ColaPanelView(self.bot))

    # ── /panel-titulos ─────────────────────────────────────────────────────────

    @app_commands.command(
        name='panel-titulos',
        description='[ADMIN] Publica o refresca el panel interactivo de títulos con botones',
    )
    @app_commands.describe(canal='Canal donde publicar el panel (solo la primera vez o para moverlo)')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_titulos(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        guild_id = str(interaction.guild_id)

        canal_id_guardado   = await db.get_config(guild_id, 'titulos_panel_canal')
        mensaje_id_guardado = await db.get_config(guild_id, 'titulos_panel_mensaje')

        # Intentar refrescar el panel existente si no se especifica canal nuevo
        if canal_id_guardado and mensaje_id_guardado and not canal:
            canal_actual = interaction.guild.get_channel(int(canal_id_guardado))
            if canal_actual:
                try:
                    msg  = await canal_actual.fetch_message(int(mensaje_id_guardado))
                    cola = await db.get_queue(guild_id)
                    await msg.edit(embed=build_embed(cola), view=ColaPanelView(self.bot))
                    await interaction.response.send_message(
                        f'✅ Panel actualizado en {canal_actual.mention}.', ephemeral=True
                    )
                    return
                except discord.NotFound:
                    pass

        if not canal:
            await interaction.response.send_message(
                '❌ Indica el canal donde publicar el panel: `/panel-titulos #canal`',
                ephemeral=True,
            )
            return

        cola = await db.get_queue(guild_id)
        msg  = await canal.send(embed=build_embed(cola), view=ColaPanelView(self.bot))
        await db.set_config(guild_id, 'titulos_panel_canal',   str(canal.id))
        await db.set_config(guild_id, 'titulos_panel_mensaje', str(msg.id))
        try:
            await msg.pin()
        except discord.Forbidden:
            pass

        await interaction.response.send_message(f'✅ Panel publicado y fijado en {canal.mention}.', ephemeral=True)

    # ── /pedir ─────────────────────────────────────────────────────────────────

    @app_commands.command(name='pedir', description='Pide un título de reino')
    @solo_en_canal('titulos')
    @app_commands.choices(titulo=[
        app_commands.Choice(name='⚔️ Duke — +10% entrenamiento',     value='duke'),
        app_commands.Choice(name='🏗️ Architect — +10% construcción', value='architect'),
        app_commands.Choice(name='🔬 Scientist — +10% investigación', value='scientist'),
        app_commands.Choice(name='⚕️ Justice — +10% curación',        value='justice'),
        app_commands.Choice(name='🛡️ General — buffs de combate',     value='general'),
    ])
    async def pedir(self, interaction: discord.Interaction, titulo: str):
        ok = await db.add_to_queue(
            str(interaction.guild_id),
            str(interaction.user.id),
            interaction.user.display_name,
            titulo,
        )
        if not ok:
            await interaction.response.send_message(
                '❌ Ya estás en la cola. Usa `/cancelar` si quieres cambiar de título.',
                ephemeral=True,
            )
            return

        cola     = await db.get_queue(str(interaction.guild_id))
        posicion = next((i + 1 for i, r in enumerate(cola) if r['user_id'] == str(interaction.user.id)), '?')
        t        = TITULOS[titulo]

        await interaction.response.send_message(
            f'✅ **{interaction.user.display_name}** añadido → {t["emoji"]} **{t["nombre"]}** · Posición: **#{posicion}**',
            embed=build_embed(cola),
        )
        await update_panel(self.bot, interaction.guild)

    # ── /cola ──────────────────────────────────────────────────────────────────

    @app_commands.command(name='cola', description='Muestra la cola actual de títulos')
    @solo_en_canal('titulos')
    async def cola(self, interaction: discord.Interaction):
        cola = await db.get_queue(str(interaction.guild_id))
        await interaction.response.send_message(embed=build_embed(cola))

    # ── /cancelar ──────────────────────────────────────────────────────────────

    @app_commands.command(name='cancelar', description='Cancela tu petición de título')
    @solo_en_canal('titulos')
    async def cancelar(self, interaction: discord.Interaction):
        ok = await db.remove_from_queue(str(interaction.guild_id), str(interaction.user.id))
        if not ok:
            await interaction.response.send_message('❌ No tienes ninguna petición activa.', ephemeral=True)
            return
        cola = await db.get_queue(str(interaction.guild_id))
        await interaction.response.send_message('✅ Tu petición ha sido cancelada.', embed=build_embed(cola))
        await update_panel(self.bot, interaction.guild)

    # ── /dar ───────────────────────────────────────────────────────────────────

    @app_commands.command(name='dar', description='[ADMIN] Marca el título del siguiente jugador como dado')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def dar(self, interaction: discord.Interaction):
        siguiente = await db.get_next(str(interaction.guild_id))
        if not siguiente:
            await interaction.response.send_message('La cola está vacía.', ephemeral=True)
            return

        await db.mark_given(str(interaction.guild_id), siguiente['user_id'])
        t    = TITULOS[siguiente['titulo']]
        cola = await db.get_queue(str(interaction.guild_id))

        msg = f'{t["emoji"]} <@{siguiente["user_id"]}> — tu título **{t["nombre"]}** ha sido dado. ¡Aprovéchalo!'
        if cola:
            t_sig = TITULOS[cola[0]['titulo']]
            msg += (
                f'\n\n⏭️ <@{cola[0]["user_id"]}> ¡Prepárate, **eres el siguiente**! '
                f'{t_sig["emoji"]} **{t_sig["nombre"]}**'
            )

        await interaction.response.send_message(msg, embed=build_embed(cola))
        await update_panel(self.bot, interaction.guild)

    # ── /saltar ────────────────────────────────────────────────────────────────

    @app_commands.command(name='saltar', description='[ADMIN] Salta al siguiente sin dar el título')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def saltar(self, interaction: discord.Interaction):
        siguiente = await db.get_next(str(interaction.guild_id))
        if not siguiente:
            await interaction.response.send_message('La cola está vacía.', ephemeral=True)
            return

        await db.remove_from_queue(str(interaction.guild_id), siguiente['user_id'])
        cola = await db.get_queue(str(interaction.guild_id))

        msg = f'⏭️ <@{siguiente["user_id"]}> saltado de la cola.'
        if cola:
            t_sig = TITULOS[cola[0]['titulo']]
            msg += (
                f'\n\n🔔 <@{cola[0]["user_id"]}> ¡Ahora **eres el primero**! '
                f'{t_sig["emoji"]} **{t_sig["nombre"]}**'
            )

        await interaction.response.send_message(msg, embed=build_embed(cola))
        await update_panel(self.bot, interaction.guild)

    # ── /limpiar ───────────────────────────────────────────────────────────────

    @app_commands.command(name='limpiar', description='[ADMIN] Limpia toda la cola de títulos')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def limpiar(self, interaction: discord.Interaction):
        await db.clear_queue(str(interaction.guild_id))
        await interaction.response.send_message('🗑️ Cola limpiada.', embed=build_embed([]))
        await update_panel(self.bot, interaction.guild)

    # ── Errores ────────────────────────────────────────────────────────────────

    @panel_titulos.error
    @dar.error
    @saltar.error
    @limpiar.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Titulos(bot))
