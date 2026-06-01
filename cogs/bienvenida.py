import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, ALIANZA_NOMBRE, ALIANZA_TAG, ALIANZA_FULL, REINO
from db import database as db

ROLES_TROPA = {
    'infanteria': '🗡️ Infantería',
    'caballeria': '🐴 Caballería',
    'arqueros':   '🏹 Arqueros',
    'maquinaria': '⚙️ Maquinaria',
    'mixto':      '🔱 Mixto',
}


async def asignar_rol_tropa(member: discord.Member, tropa: str):
    # Quitar roles de tropa anteriores
    for nombre_rol in ROLES_TROPA.values():
        rol = discord.utils.get(member.guild.roles, name=nombre_rol)
        if rol and rol in member.roles:
            await member.remove_roles(rol, reason='Cambio de tipo de tropa')

    # Asignar nuevo rol de tropa
    nuevo_rol = discord.utils.get(member.guild.roles, name=ROLES_TROPA[tropa])
    if nuevo_rol:
        await member.add_roles(nuevo_rol, reason='Registro de tropa')

    # Pasar de Nuevo → Miembro
    rol_nuevo    = discord.utils.get(member.guild.roles, name='🔰 Nuevo')
    rol_miembro  = discord.utils.get(member.guild.roles, name='🌿 Miembro')
    if rol_nuevo and rol_nuevo in member.roles:
        await member.remove_roles(rol_nuevo, reason='Registro completado')
    if rol_miembro and rol_miembro not in member.roles:
        await member.add_roles(rol_miembro, reason='Registro completado')


class Bienvenida(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Asignar rol de Nuevo automáticamente
        rol_nuevo = discord.utils.get(member.guild.roles, name='🔰 Nuevo')
        if rol_nuevo:
            await member.add_roles(rol_nuevo, reason='Nuevo miembro')

        # Buscar canal de bienvenida configurado
        canal_id = await db.get_config(str(member.guild.id), 'bienvenida_canal')
        if not canal_id:
            return

        canal = member.guild.get_channel(int(canal_id))
        if not canal:
            return

        msg_personalizado = await db.get_config(str(member.guild.id), 'bienvenida_msg')

        embed = discord.Embed(
            title=f'🔥 ¡Bienvenido a {ALIANZA_NOMBRE}!',
            description=msg_personalizado or (
                f'Hola {member.mention}, ¡bienvenido al servidor oficial de '
                f'**{ALIANZA_FULL}** del **Reino {REINO}**!\n\n'
                f'Para acceder al servidor completo, regístrate con tu perfil de gobernador.'
            ),
            color=COLOR_BOT,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name='📋 Primeros pasos',
            value=(
                '**1.** Ve al canal de miembros y usa `/registrar`\n'
                '**2.** Consulta `/comandante` para ver builds y equipamiento\n'
                '**3.** Usa `/pedir` para solicitar títulos de reino'
            ),
            inline=False,
        )
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO} · Miembro #{member.guild.member_count}')

        await canal.send(content=member.mention, embed=embed)

    @app_commands.command(name='config-bienvenida', description='[ADMIN] Configura el canal y mensaje de bienvenida')
    @app_commands.describe(
        canal='Canal donde se publicará la bienvenida',
        mensaje='Mensaje personalizado (opcional)',
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config_bienvenida(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        mensaje: str = None,
    ):
        await db.set_config(str(interaction.guild_id), 'bienvenida_canal', str(canal.id))
        if mensaje:
            await db.set_config(str(interaction.guild_id), 'bienvenida_msg', mensaje)

        embed = discord.Embed(title='✅ Bienvenida configurada', color=COLOR_BOT)
        embed.add_field(name='Canal', value=canal.mention, inline=True)
        if mensaje:
            embed.add_field(name='Mensaje', value=mensaje[:200], inline=False)
        embed.set_footer(text=f'{ALIANZA_TAG} · Los nuevos miembros recibirán el rol 🔰 Nuevo automáticamente')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='bienvenida-test', description='[ADMIN] Prueba el mensaje de bienvenida contigo mismo')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def bienvenida_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.on_member_join(interaction.user)
        await interaction.followup.send('✅ Mensaje de bienvenida enviado de prueba.', ephemeral=True)

    @config_bienvenida.error
    @bienvenida_test.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Bienvenida(bot))
