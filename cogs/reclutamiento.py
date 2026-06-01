import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, ALIANZA_FULL, ALIANZA_TAG, REINO
from db import database as db


# ── Modal de solicitud ─────────────────────────────────────────────────────────

class SolicitudModal(discord.ui.Modal, title='📋 Solicitud de ingreso'):
    gobernador = discord.ui.TextInput(
        label='Nombre de gobernador',
        placeholder='Tu nombre exacto en el juego',
        max_length=50,
    )
    poder = discord.ui.TextInput(
        label='Poder aproximado',
        placeholder='Ej: 150M, 80000K',
        max_length=20,
    )
    tropa = discord.ui.TextInput(
        label='Tipo de tropa principal',
        placeholder='Infantería / Caballería / Arqueros / Maquinaria',
        max_length=30,
    )
    experiencia = discord.ui.TextInput(
        label='Experiencia en RoK (opcional)',
        placeholder='¿Llevas mucho tiempo jugando? ¿Has participado en KvK?',
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user  = interaction.user

        # Comprobar si ya tiene solicitud activa
        existing = await db.reclu_get_solicitud_activa(str(guild.id), str(user.id))
        if existing:
            canal_ex = guild.get_channel(int(existing['canal_id']))
            await interaction.response.send_message(
                f'ℹ️ Ya tienes una solicitud pendiente{f": {canal_ex.mention}" if canal_ex else ""}.',
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Permisos del canal privado
        roles_admin = ['🔧 Admin Discord', '👑 Liderazgo', '⚔️ R4', '🛡️ R3']
        overw = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                attach_files=True, read_message_history=True,
            ),
        }
        for nombre_rol in roles_admin:
            rol = discord.utils.get(guild.roles, name=nombre_rol)
            if rol:
                overw[rol] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    manage_messages=True, read_message_history=True,
                    attach_files=True,
                )

        # Crear categoría de candidatos si no existe
        categoria = discord.utils.get(guild.categories, name='🔍 CANDIDATOS')
        if not categoria:
            categoria = await guild.create_category(
                '🔍 CANDIDATOS',
                overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False)},
            )

        # Crear canal privado
        nombre_canal = f'reclu-{user.display_name[:20].lower().replace(" ", "-")}'
        canal = await guild.create_text_channel(nombre_canal, category=categoria, overwrites=overw)

        # Guardar en BD
        solicitud_id = await db.reclu_crear_solicitud(
            str(guild.id), str(user.id), str(canal.id),
            self.gobernador.value, self.poder.value, self.tropa.value,
        )

        # Embed de bienvenida en el canal privado
        embed_info = discord.Embed(
            title=f'📋 Solicitud de {user.display_name}',
            description=(
                f'Hola {user.mention}, gracias por tu interés en **{ALIANZA_FULL}**.\n\n'
                f'Para que podamos valorar tu candidatura, **sube en este canal las siguientes capturas de pantalla:**'
            ),
            color=COLOR_BOT,
        )
        embed_info.add_field(
            name='⚔️ 1. Capturas de tus marchas',
            value='Muéstranos tus tropas organizadas por marcha — tipo, tier y cantidad de cada una.',
            inline=False,
        )
        embed_info.add_field(
            name='⚡ 2. Tus velocidades',
            value='Captura de tus velocidades de **entrenamiento**, **construcción**, **investigación** y **curación**.',
            inline=False,
        )
        embed_info.add_field(
            name='💰 3. Tus recursos',
            value='Captura de tu pantalla de recursos (madera, piedra, comida, oro, gemas).',
            inline=False,
        )
        embed_info.add_field(
            name='📊 Datos del formulario',
            value=(
                f'🗡️ **Gobernador:** {self.gobernador.value}\n'
                f'💪 **Poder:** {self.poder.value}\n'
                f'⚔️ **Tropa:** {self.tropa.value}\n'
                + (f'📝 **Experiencia:** {self.experiencia.value}' if self.experiencia.value else '')
            ),
            inline=False,
        )
        embed_info.set_thumbnail(url=user.display_avatar.url)
        embed_info.set_footer(text=f'El liderazgo revisará tu solicitud · {ALIANZA_TAG} · Reino {REINO}')

        # Panel de decisión para admins
        embed_decision = discord.Embed(
            title='⚙️ Panel de decisión — solo liderazgo',
            color=0x2F3136,
        )
        view_decision = DecisionView()

        await canal.send(content=user.mention, embed=embed_info)
        await canal.send(embed=embed_decision, view=view_decision)

        # Notificar a canal admin si está configurado
        canal_notif_id = await db.get_config(str(guild.id), 'reclu_canal_notif')
        if canal_notif_id:
            canal_notif = guild.get_channel(int(canal_notif_id))
            if canal_notif:
                embed_notif = discord.Embed(
                    title='🔔 Nueva solicitud de ingreso',
                    description=f'{user.mention} quiere unirse · {canal.mention}',
                    color=COLOR_BOT,
                )
                embed_notif.add_field(name='Gobernador', value=self.gobernador.value, inline=True)
                embed_notif.add_field(name='Poder',      value=self.poder.value,      inline=True)
                embed_notif.add_field(name='Tropa',      value=self.tropa.value,      inline=True)
                await canal_notif.send(embed=embed_notif)

        await interaction.followup.send(
            f'✅ Solicitud enviada correctamente. El liderazgo te contactará en {canal.mention}.',
            ephemeral=True,
        )


# ── Modal de rechazo ───────────────────────────────────────────────────────────

class RechazarModal(discord.ui.Modal, title='❌ Motivo del rechazo'):
    motivo = discord.ui.TextInput(
        label='Motivo (se enviará al candidato)',
        placeholder='Ej: Poder insuficiente para la temporada actual...',
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        solicitud = await db.reclu_get_por_canal(str(interaction.guild_id), str(interaction.channel_id))
        if not solicitud:
            await interaction.followup.send('❌ No encontré esta solicitud.', ephemeral=True)
            return

        member = interaction.guild.get_member(int(solicitud['user_id']))
        motivo = self.motivo.value or 'No se ha especificado un motivo.'

        await db.reclu_actualizar_estado(solicitud['id'], 'rechazada')

        embed = discord.Embed(
            title='❌ Solicitud rechazada',
            description=(
                f'{member.mention if member else "El candidato"}, tu solicitud ha sido rechazada.\n\n'
                f'**Motivo:** {motivo}\n\n'
                f'Puedes volver a intentarlo más adelante si mejoras tu perfil.'
            ),
            color=0xFF4444,
        )
        embed.set_footer(text=f'Rechazado por {interaction.user.display_name}')
        await interaction.followup.send(embed=embed)

        # DM al candidato
        if member:
            try:
                embed_dm = discord.Embed(
                    title=f'❌ Solicitud rechazada — {ALIANZA_FULL}',
                    description=(
                        f'Tu solicitud de ingreso al **Reino {REINO}** ha sido rechazada.\n\n'
                        f'**Motivo:** {motivo}\n\n'
                        f'¡No te rindas! Puedes volver a intentarlo cuando mejores tu perfil.'
                    ),
                    color=0xFF4444,
                )
                await member.send(embed=embed_dm)
            except Exception:
                pass

        await asyncio.sleep(8)
        try:
            await interaction.channel.delete(reason='Solicitud rechazada')
        except Exception:
            pass


# ── Vista de decisión (persistente) ───────────────────────────────────────────

class DecisionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='✅ Aprobar', style=discord.ButtonStyle.success, custom_id='reclu_aprobar')
    async def aprobar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Solo el liderazgo puede aprobar.', ephemeral=True)
            return

        solicitud = await db.reclu_get_por_canal(str(interaction.guild_id), str(interaction.channel_id))
        if not solicitud:
            await interaction.response.send_message('❌ No encontré esta solicitud.', ephemeral=True)
            return

        await interaction.response.defer()

        member = interaction.guild.get_member(int(solicitud['user_id']))

        # Asignar rol 🔰 Nuevo
        if member:
            rol_nuevo = discord.utils.get(interaction.guild.roles, name='🔰 Nuevo')
            if rol_nuevo:
                await member.add_roles(rol_nuevo, reason='Solicitud de ingreso aprobada')

        await db.reclu_actualizar_estado(solicitud['id'], 'aprobada')

        embed = discord.Embed(
            title='✅ ¡Solicitud aprobada!',
            description=(
                f'{member.mention if member else "El candidato"} ha sido aceptado en **{ALIANZA_FULL}**. 🔥\n\n'
                f'Ve al canal de miembros y usa `/registrar` para completar tu perfil.'
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text=f'Aprobado por {interaction.user.display_name} · Este canal se cerrará en 10 segundos')
        await interaction.followup.send(embed=embed)

        # DM al candidato
        if member:
            try:
                embed_dm = discord.Embed(
                    title=f'🎉 ¡Bienvenido a {ALIANZA_FULL}!',
                    description=(
                        f'Tu solicitud ha sido **aprobada**. ¡Ya eres parte del **Reino {REINO}**!\n\n'
                        f'Ve al canal de miembros y usa `/registrar` para completar tu perfil.'
                    ),
                    color=0x2ECC71,
                )
                await member.send(embed=embed_dm)
            except Exception:
                pass

        await asyncio.sleep(10)
        try:
            await interaction.channel.delete(reason='Solicitud aprobada')
        except Exception:
            pass

    @discord.ui.button(label='❌ Rechazar', style=discord.ButtonStyle.danger, custom_id='reclu_rechazar')
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Solo el liderazgo puede rechazar.', ephemeral=True)
            return

        await interaction.response.send_modal(RechazarModal())


# ── Vista del panel público ────────────────────────────────────────────────────

class PanelReclutamientoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='🔥 Solicitar ingreso',
        style=discord.ButtonStyle.success,
        custom_id='reclu_solicitar',
    )
    async def solicitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        rol_miembro = discord.utils.get(interaction.guild.roles, name='🌿 Miembro')
        if rol_miembro and rol_miembro in interaction.user.roles:
            await interaction.response.send_message('ℹ️ Ya eres miembro de la alianza.', ephemeral=True)
            return
        await interaction.response.send_modal(SolicitudModal())


# ── Cog ────────────────────────────────────────────────────────────────────────

class Reclutamiento(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(PanelReclutamientoView())
        self.bot.add_view(DecisionView())

    # ── /reclu-panel ───────────────────────────────────────────────────────────

    @app_commands.command(name='reclu-panel', description='[ADMIN] Publica el panel de reclutamiento con botón de solicitud')
    @app_commands.describe(canal='Canal público donde publicar el panel')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reclu_panel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        embed = discord.Embed(
            title=f'🔥 ¡Únete a {ALIANZA_FULL}!',
            description=(
                f'**Reino {REINO}**\n\n'
                f'¿Quieres formar parte de nuestra alianza?\n'
                f'Pulsa el botón, rellena el formulario y el liderazgo revisará tu candidatura.'
            ),
            color=COLOR_BOT,
        )
        embed.add_field(
            name='📋 Lo que buscamos',
            value=(
                '• Jugadores activos en **KvK** y **Ark of Osiris**\n'
                '• Disposición a seguir las órdenes del liderazgo\n'
                '• Comunicación y trabajo en equipo'
            ),
            inline=False,
        )
        embed.add_field(
            name='📸 Necesitarás subir',
            value=(
                '⚔️ Capturas de tus **marchas**\n'
                '⚡ Capturas de tus **velocidades**\n'
                '💰 Captura de tus **recursos**'
            ),
            inline=False,
        )
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO} · El proceso es rápido y confidencial')

        msg = await canal.send(embed=embed, view=PanelReclutamientoView())
        await db.set_config(str(interaction.guild_id), 'reclu_panel_canal',   str(canal.id))
        await db.set_config(str(interaction.guild_id), 'reclu_panel_mensaje', str(msg.id))
        try:
            await msg.pin()
        except discord.Forbidden:
            pass

        await interaction.response.send_message(f'✅ Panel de reclutamiento publicado en {canal.mention}.', ephemeral=True)

    # ── /reclu-notif ───────────────────────────────────────────────────────────

    @app_commands.command(name='reclu-notif', description='[ADMIN] Canal donde el bot avisa de nuevas solicitudes')
    @app_commands.describe(canal='Canal de notificaciones (recomendado: panel-control o chat-admin)')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reclu_notif(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await db.set_config(str(interaction.guild_id), 'reclu_canal_notif', str(canal.id))
        await interaction.response.send_message(
            f'✅ Notificaciones de reclutamiento → {canal.mention}', ephemeral=True
        )

    # ── /reclu-pendientes ──────────────────────────────────────────────────────

    @app_commands.command(name='reclu-pendientes', description='[ADMIN] Lista las solicitudes pendientes de revisar')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reclu_pendientes(self, interaction: discord.Interaction):
        pendientes = await db.reclu_get_pendientes(str(interaction.guild_id))
        if not pendientes:
            await interaction.response.send_message('✅ No hay solicitudes pendientes.', ephemeral=True)
            return

        embed = discord.Embed(
            title=f'📋 Solicitudes pendientes — {len(pendientes)}',
            color=COLOR_BOT,
        )
        for s in pendientes:
            canal = interaction.guild.get_channel(int(s['canal_id']))
            embed.add_field(
                name=f'🗡️ {s["gobernador"]} — {s["poder"]}',
                value=f'{canal.mention if canal else "⚠️ canal eliminado"} · Tropa: {s["tropa"]}',
                inline=False,
            )
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Errores ────────────────────────────────────────────────────────────────

    @reclu_panel.error
    @reclu_notif.error
    @reclu_pendientes.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Reclutamiento(bot))
