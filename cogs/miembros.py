from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, ALIANZA_TAG, REINO
from checks import solo_en_canal
from db import database as db
from cogs.bienvenida import asignar_rol_tropa

TROPAS = {
    'infanteria': '⚔️ Infantería / Infantry',
    'caballeria': '🐴 Caballería / Cavalry',
    'arqueros':   '🏹 Arqueros / Archers',
    'maquinaria': '⚙️ Maquinaria / Siege',
    'mixto':      '🔀 Mixto / Mixed',
}

TROPAS_EMOJI = {
    'infanteria': '⚔️', 'caballeria': '🐴',
    'arqueros': '🏹', 'maquinaria': '⚙️', 'mixto': '🔀',
}


def parse_poder(s: str) -> int:
    s = s.strip().upper().replace(',', '.')
    try:
        if s.endswith('M'):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith('K'):
            return int(float(s[:-1]) * 1_000)
        return int(s.replace('.', ''))
    except ValueError:
        return -1


def fmt_poder(n: int) -> str:
    if n >= 1_000_000:
        return f'{n / 1_000_000:.3f}'.rstrip('0').rstrip('.') + 'M'
    if n >= 1_000:
        return f'{n / 1_000:.3f}'.rstrip('0').rstrip('.') + 'K'
    return str(n)


def fmt_hasta(hasta_str: str) -> str:
    try:
        hasta = datetime.fromisoformat(hasta_str)
        dias  = (hasta - datetime.utcnow()).days + 1
        return f'{hasta.strftime("%d/%m/%Y")} ({max(dias, 0)}d restantes / remaining)'
    except Exception:
        return hasta_str


class Miembros(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /registrar ─────────────────────────────────────────────────────────────

    @app_commands.command(name='registrar', description='Regístrate con tu información de gobernador / Register your governor info')
    @solo_en_canal('miembros')
    @app_commands.describe(
        gobernador='Tu nombre de gobernador en el juego / Your in-game governor name',
        poder='Tu poder actual (ej: 150M, 50000K) / Your current power (e.g. 150M)',
        tropa='Tu tipo de tropa principal / Your main troop type',
    )
    @app_commands.choices(tropa=[
        app_commands.Choice(name='⚔️ Infantería / Infantry', value='infanteria'),
        app_commands.Choice(name='🐴 Caballería / Cavalry',  value='caballeria'),
        app_commands.Choice(name='🏹 Arqueros / Archers',    value='arqueros'),
        app_commands.Choice(name='⚙️ Maquinaria / Siege',   value='maquinaria'),
        app_commands.Choice(name='🔀 Mixto / Mixed',         value='mixto'),
    ])
    async def registrar(self, interaction: discord.Interaction, gobernador: str, poder: str, tropa: str):
        rol_nuevo   = discord.utils.get(interaction.guild.roles, name='🔰 Nuevo')
        rol_miembro = discord.utils.get(interaction.guild.roles, name='🌿 Miembro')
        tiene_acceso = (
            (rol_nuevo   and rol_nuevo   in interaction.user.roles) or
            (rol_miembro and rol_miembro in interaction.user.roles)
        )
        if not tiene_acceso:
            await interaction.response.send_message(
                '❌ Para registrarte primero debes solicitar el ingreso en **⚔️│reclutamiento**.\n'
                '_To register you must first apply in **⚔️│reclutamiento** and be approved by leadership._',
                ephemeral=True,
            )
            return

        poder_int = parse_poder(poder)
        if poder_int < 0:
            await interaction.response.send_message(
                '❌ Formato de poder incorrecto. Usa: `150M`, `50000K` o `150000000`\n'
                '_Incorrect power format. Use: `150M`, `50000K` or `150000000`_',
                ephemeral=True,
            )
            return

        await db.upsert_member(
            str(interaction.guild_id),
            str(interaction.user.id),
            interaction.user.display_name,
            gobernador,
            poder_int,
            tropa,
        )
        await asignar_rol_tropa(interaction.user, tropa)

        embed = discord.Embed(title='✅ Perfil registrado / Profile registered', color=COLOR_BOT)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name='Gobernador / Governor', value=gobernador,           inline=True)
        embed.add_field(name='Poder / Power',          value=fmt_poder(poder_int), inline=True)
        embed.add_field(name='Tropa / Troop',          value=TROPAS[tropa],        inline=True)
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    # ── /registrar-miembro ─────────────────────────────────────────────────────

    @app_commands.command(name='registrar-miembro', description='[ADMIN] Registra a otro miembro en su nombre / Register another member')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        usuario='Miembro de Discord a registrar / Discord member to register',
        gobernador='Nombre de gobernador en el juego / In-game governor name',
        poder='Poder actual (ej: 150M) / Current power (e.g. 150M)',
        tropa='Tipo de tropa principal / Main troop type',
    )
    @app_commands.choices(tropa=[
        app_commands.Choice(name='⚔️ Infantería / Infantry', value='infanteria'),
        app_commands.Choice(name='🐴 Caballería / Cavalry',  value='caballeria'),
        app_commands.Choice(name='🏹 Arqueros / Archers',    value='arqueros'),
        app_commands.Choice(name='⚙️ Maquinaria / Siege',   value='maquinaria'),
        app_commands.Choice(name='🔀 Mixto / Mixed',         value='mixto'),
    ])
    async def registrar_miembro(self, interaction: discord.Interaction,
                                usuario: discord.Member, gobernador: str, poder: str, tropa: str):
        poder_int = parse_poder(poder)
        if poder_int < 0:
            await interaction.response.send_message(
                '❌ Formato de poder incorrecto. Usa: `150M`, `50000K` o `150000000`',
                ephemeral=True,
            )
            return

        await db.upsert_member(
            str(interaction.guild_id),
            str(usuario.id),
            usuario.display_name,
            gobernador,
            poder_int,
            tropa,
        )
        await asignar_rol_tropa(usuario, tropa)

        embed = discord.Embed(title=f'✅ {usuario.display_name} registrado / registered', color=COLOR_BOT)
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name='Gobernador / Governor', value=gobernador,           inline=True)
        embed.add_field(name='Poder / Power',          value=fmt_poder(poder_int), inline=True)
        embed.add_field(name='Tropa / Troop',          value=TROPAS[tropa],        inline=True)
        embed.set_footer(text=f'Registrado por / Registered by {interaction.user.display_name} · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /registrar-externo ─────────────────────────────────────────────────────

    @app_commands.command(name='registrar-externo', description='[ADMIN] Registra un gobernador sin cuenta Discord / Register a governor with no Discord account')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        gobernador='Nombre de gobernador en el juego / In-game governor name',
        poder='Poder actual (ej: 150M) / Current power (e.g. 150M)',
        tropa='Tipo de tropa principal / Main troop type',
    )
    @app_commands.choices(tropa=[
        app_commands.Choice(name='⚔️ Infantería / Infantry', value='infanteria'),
        app_commands.Choice(name='🐴 Caballería / Cavalry',  value='caballeria'),
        app_commands.Choice(name='🏹 Arqueros / Archers',    value='arqueros'),
        app_commands.Choice(name='⚙️ Maquinaria / Siege',   value='maquinaria'),
        app_commands.Choice(name='🔀 Mixto / Mixed',         value='mixto'),
    ])
    async def registrar_externo(self, interaction: discord.Interaction,
                                gobernador: str, poder: str, tropa: str):
        poder_int = parse_poder(poder)
        if poder_int < 0:
            await interaction.response.send_message(
                '❌ Formato de poder incorrecto. Usa: `150M`, `50000K` o `150000000`',
                ephemeral=True,
            )
            return

        user_id_ext = 'ext_' + gobernador.lower().replace(' ', '_')

        await db.upsert_member(
            str(interaction.guild_id),
            user_id_ext,
            gobernador,
            gobernador,
            poder_int,
            tropa,
        )

        embed = discord.Embed(title='✅ Gobernador externo registrado / External governor registered', color=0x95A5A6)
        embed.add_field(name='Gobernador / Governor', value=gobernador,           inline=True)
        embed.add_field(name='Poder / Power',          value=fmt_poder(poder_int), inline=True)
        embed.add_field(name='Tropa / Troop',          value=TROPAS[tropa],        inline=True)
        embed.add_field(name='ID interno / Internal ID', value=f'`{user_id_ext}`', inline=False)
        embed.set_footer(text=f'Sin Discord / No Discord account · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /perfil ────────────────────────────────────────────────────────────────

    @app_commands.command(name='perfil', description='Muestra el perfil de un miembro / Show a member\'s profile')
    @solo_en_canal('miembros')
    @app_commands.describe(usuario='Usuario a consultar (vacío = el tuyo) / Member to check (empty = yours)')
    async def perfil(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target  = usuario or interaction.user
        miembro = await db.get_member(str(interaction.guild_id), str(target.id))

        if not miembro:
            msg = (
                'No tienes perfil. Usa `/registrar`.\n_You have no profile. Use `/registrar`._'
                if not usuario else
                f'{target.display_name} no tiene perfil. / {target.display_name} has no profile.'
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        ausencia = await db.get_ausencia(str(interaction.guild_id), str(target.id))

        embed = discord.Embed(
            title=f'{"😴 " if ausencia else "👤 "}{miembro["gobernador"]}',
            color=0x95A5A6 if ausencia else COLOR_BOT,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name='Poder / Power', value=fmt_poder(miembro['poder']),                     inline=True)
        embed.add_field(name='Tropa / Troop', value=TROPAS.get(miembro['tropa'], miembro['tropa']), inline=True)

        if ausencia:
            embed.add_field(
                name='😴 Ausente hasta / Absent until',
                value=fmt_hasta(ausencia['hasta']),
                inline=False,
            )
            if ausencia['motivo']:
                embed.add_field(name='Motivo / Reason', value=ausencia['motivo'], inline=False)

        embed.set_footer(text=f'Discord: {target.display_name} · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    # ── /miembros ──────────────────────────────────────────────────────────────

    @app_commands.command(name='miembros', description='Lista todos los miembros registrados / List all registered members')
    @solo_en_canal('miembros')
    async def miembros(self, interaction: discord.Interaction):
        lista    = await db.get_all_members(str(interaction.guild_id))
        ausentes = await db.get_ausentes_ids(str(interaction.guild_id))

        if not lista:
            await interaction.response.send_message(
                'No hay miembros registrados. Usa `/registrar`.\n_No registered members. Use `/registrar`._',
                ephemeral=True,
            )
            return

        lineas = []
        for i, m in enumerate(lista, 1):
            emoji     = TROPAS_EMOJI.get(m['tropa'], '❓')
            indicador = ' 😴' if m['user_id'] in ausentes else ''
            lineas.append(f'**{i}.** {emoji} **{m["gobernador"]}**{indicador} — {fmt_poder(m["poder"])}')

        texto = '\n'.join(lineas)
        embed = discord.Embed(
            title=f'👥 Miembros registrados / Registered Members — {len(lista)}',
            description=texto[:4000] + ('\n...' if len(texto) > 4000 else ''),
            color=COLOR_BOT,
        )
        embed.set_footer(text=f'😴 = ausente temporalmente / temporarily absent · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    # ── /ausente ───────────────────────────────────────────────────────────────

    @app_commands.command(name='ausente', description='Avisa que estarás inactivo un tiempo / Report that you will be inactive')
    @solo_en_canal('miembros')
    @app_commands.describe(
        dias='Días que estarás ausente (1–60) / Days you will be absent (1–60)',
        motivo='Motivo de la ausencia (opcional) / Reason for absence (optional)',
    )
    async def ausente(self, interaction: discord.Interaction, dias: int, motivo: str = ''):
        if not 1 <= dias <= 60:
            await interaction.response.send_message(
                '❌ El número de días debe estar entre 1 y 60. / Days must be between 1 and 60.',
                ephemeral=True,
            )
            return

        miembro = await db.get_member(str(interaction.guild_id), str(interaction.user.id))
        if not miembro:
            await interaction.response.send_message(
                '❌ No tienes perfil. Usa `/registrar` primero.\n_You have no profile. Use `/registrar` first._',
                ephemeral=True,
            )
            return

        hasta     = datetime.utcnow() + timedelta(days=dias)
        hasta_str = hasta.strftime('%Y-%m-%d %H:%M:%S')
        await db.set_ausencia(str(interaction.guild_id), str(interaction.user.id), hasta_str, motivo)

        embed = discord.Embed(title='😴 Ausencia registrada / Absence registered', color=0x95A5A6)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name='Gobernador / Governor', value=miembro['gobernador'],      inline=True)
        embed.add_field(name='Días / Days',            value=str(dias),                  inline=True)
        embed.add_field(name='Hasta / Until',          value=hasta.strftime('%d/%m/%Y'), inline=True)
        if motivo:
            embed.add_field(name='Motivo / Reason', value=motivo, inline=False)
        embed.set_footer(text='Usa /volver cuando regreses · Use /volver when you return · Expires automatically')
        await interaction.response.send_message(embed=embed)

    # ── /volver ────────────────────────────────────────────────────────────────

    @app_commands.command(name='volver', description='Cancela tu ausencia y vuelves a estar activo / Cancel your absence and become active again')
    @solo_en_canal('miembros')
    async def volver(self, interaction: discord.Interaction):
        ausencia = await db.get_ausencia(str(interaction.guild_id), str(interaction.user.id))
        if not ausencia:
            await interaction.response.send_message(
                'ℹ️ No tienes ninguna ausencia activa. / You have no active absence.', ephemeral=True
            )
            return

        await db.clear_ausencia(str(interaction.guild_id), str(interaction.user.id))
        await interaction.response.send_message(
            f'✅ ¡Bienvenido de vuelta, **{interaction.user.display_name}**! / Welcome back!\n'
            f'_Tu ausencia ha sido cancelada. / Your absence has been cancelled._',
        )

    # ── /ausentes ──────────────────────────────────────────────────────────────

    @app_commands.command(name='ausentes', description='[ADMIN] Lista todos los miembros con ausencia activa / List all absent members')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ausentes(self, interaction: discord.Interaction):
        lista = await db.get_all_ausentes(str(interaction.guild_id))

        if not lista:
            await interaction.response.send_message('✅ No hay ausencias activas. / No active absences.', ephemeral=True)
            return

        now    = datetime.utcnow()
        lineas = []
        for a in lista:
            try:
                hasta = datetime.fromisoformat(a['hasta'])
                dias  = max((hasta - now).days + 1, 0)
            except Exception:
                dias = '?'
            nombre = a['gobernador'] or a['discord_name'] or f'<@{a["user_id"]}>'
            linea  = f'😴 **{nombre}** — {dias}d restantes / remaining'
            if a['motivo']:
                linea += f'\n  _{a["motivo"]}_'
            lineas.append(linea)

        embed = discord.Embed(
            title=f'😴 Ausencias activas / Active absences — {len(lista)}',
            description='\n'.join(lineas),
            color=0x95A5A6,
        )
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /sin-registrar ─────────────────────────────────────────────────────────

    @app_commands.command(name='sin-registrar', description='[ADMIN] Miembros del servidor sin registrar / Unregistered server members')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sin_registrar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        registrados  = await db.get_all_members(str(interaction.guild_id))
        ids_reg      = {m['user_id'] for m in registrados}
        sin_reg      = [m for m in interaction.guild.members if not m.bot and str(m.id) not in ids_reg]

        if not sin_reg:
            await interaction.followup.send('✅ Todos los miembros están registrados. / All members are registered.', ephemeral=True)
            return

        lineas = [f'• {m.mention} — `{m.display_name}`' for m in sin_reg[:30]]
        embed  = discord.Embed(
            title=f'⚠️ Sin registrar / Unregistered — {len(sin_reg)} miembros / members',
            description='\n'.join(lineas),
            color=0xFF8C00,
        )
        if len(sin_reg) > 30:
            embed.description += f'\n_...y {len(sin_reg) - 30} más / and {len(sin_reg) - 30} more_'
        embed.set_footer(text=f'Pídeles que usen /registrar · Ask them to use /registrar · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Errores ────────────────────────────────────────────────────────────────

    @ausentes.error
    @sin_registrar.error
    @registrar_miembro.error
    @registrar_externo.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                '❌ No tienes permisos para este comando. / You do not have permission for this command.',
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Miembros(bot))
