from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, ALIANZA_TAG, REINO
from checks import solo_en_canal
from db import database as db
from cogs.bienvenida import asignar_rol_tropa

TROPAS = {
    'infanteria': '⚔️ Infantería',
    'caballeria': '🐴 Caballería',
    'arqueros':   '🏹 Arqueros',
    'maquinaria': '⚙️ Maquinaria',
    'mixto':      '🔀 Mixto',
}

TROPAS_EMOJI = {k: v.split()[0] for k, v in TROPAS.items()}


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
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.0f}K'
    return str(n)


def fmt_hasta(hasta_str: str) -> str:
    try:
        hasta = datetime.fromisoformat(hasta_str)
        dias  = (hasta - datetime.utcnow()).days + 1
        return f'{hasta.strftime("%d/%m/%Y")} ({max(dias, 0)}d restantes)'
    except Exception:
        return hasta_str


class Miembros(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /registrar ─────────────────────────────────────────────────────────────

    @app_commands.command(name='registrar', description='Regístrate con tu información de gobernador')
    @solo_en_canal('miembros')
    @app_commands.describe(
        gobernador='Tu nombre de gobernador en el juego',
        poder='Tu poder actual (ej: 150M, 50000K, 150000000)',
        tropa='Tu tipo de tropa principal',
    )
    @app_commands.choices(tropa=[
        app_commands.Choice(name='⚔️ Infantería',  value='infanteria'),
        app_commands.Choice(name='🐴 Caballería',  value='caballeria'),
        app_commands.Choice(name='🏹 Arqueros',    value='arqueros'),
        app_commands.Choice(name='⚙️ Maquinaria', value='maquinaria'),
        app_commands.Choice(name='🔀 Mixto',       value='mixto'),
    ])
    async def registrar(self, interaction: discord.Interaction, gobernador: str, poder: str, tropa: str):
        poder_int = parse_poder(poder)
        if poder_int < 0:
            await interaction.response.send_message(
                '❌ Formato de poder incorrecto. Usa: `150M`, `50000K` o `150000000`',
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

        embed = discord.Embed(title='✅ Perfil registrado', color=COLOR_BOT)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name='Gobernador', value=gobernador,        inline=True)
        embed.add_field(name='Poder',      value=fmt_poder(poder_int), inline=True)
        embed.add_field(name='Tropa',      value=TROPAS[tropa],     inline=True)
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    # ── /perfil ────────────────────────────────────────────────────────────────

    @app_commands.command(name='perfil', description='Muestra el perfil de un miembro')
    @solo_en_canal('miembros')
    @app_commands.describe(usuario='Usuario a consultar (vacío = el tuyo)')
    async def perfil(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target  = usuario or interaction.user
        miembro = await db.get_member(str(interaction.guild_id), str(target.id))

        if not miembro:
            msg = 'No tienes perfil. Usa `/registrar`.' if not usuario else f'{target.display_name} no tiene perfil.'
            await interaction.response.send_message(msg, ephemeral=True)
            return

        ausencia = await db.get_ausencia(str(interaction.guild_id), str(target.id))

        embed = discord.Embed(
            title=f'{"😴 " if ausencia else "👤 "}{miembro["gobernador"]}',
            color=0x95A5A6 if ausencia else COLOR_BOT,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name='Poder', value=fmt_poder(miembro['poder']), inline=True)
        embed.add_field(name='Tropa', value=TROPAS.get(miembro['tropa'], miembro['tropa']), inline=True)

        if ausencia:
            embed.add_field(
                name='😴 Ausente hasta',
                value=fmt_hasta(ausencia['hasta']),
                inline=False,
            )
            if ausencia['motivo']:
                embed.add_field(name='Motivo', value=ausencia['motivo'], inline=False)

        embed.set_footer(text=f'Discord: {target.display_name} · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    # ── /miembros ──────────────────────────────────────────────────────────────

    @app_commands.command(name='miembros', description='Lista todos los miembros registrados ordenados por poder')
    @solo_en_canal('miembros')
    async def miembros(self, interaction: discord.Interaction):
        lista    = await db.get_all_members(str(interaction.guild_id))
        ausentes = await db.get_ausentes_ids(str(interaction.guild_id))

        if not lista:
            await interaction.response.send_message('No hay miembros registrados. Usa `/registrar`.', ephemeral=True)
            return

        lineas = []
        for i, m in enumerate(lista, 1):
            emoji    = TROPAS_EMOJI.get(m['tropa'], '❓')
            indicador = ' 😴' if m['user_id'] in ausentes else ''
            lineas.append(f'**{i}.** {emoji} **{m["gobernador"]}**{indicador} — {fmt_poder(m["poder"])}')

        texto = '\n'.join(lineas)
        embed = discord.Embed(
            title=f'👥 Miembros registrados — {len(lista)}',
            description=texto[:4000] + ('\n...' if len(texto) > 4000 else ''),
            color=COLOR_BOT,
        )
        embed.set_footer(text=f'😴 = ausente temporalmente · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    # ── /ausente ───────────────────────────────────────────────────────────────

    @app_commands.command(name='ausente', description='Avisa que estarás inactivo durante un tiempo')
    @solo_en_canal('miembros')
    @app_commands.describe(
        dias='Días que estarás ausente (1–60)',
        motivo='Motivo de la ausencia (opcional)',
    )
    async def ausente(self, interaction: discord.Interaction, dias: int, motivo: str = ''):
        if not 1 <= dias <= 60:
            await interaction.response.send_message('❌ El número de días debe estar entre 1 y 60.', ephemeral=True)
            return

        miembro = await db.get_member(str(interaction.guild_id), str(interaction.user.id))
        if not miembro:
            await interaction.response.send_message('❌ No tienes perfil. Usa `/registrar` primero.', ephemeral=True)
            return

        hasta     = datetime.utcnow() + timedelta(days=dias)
        hasta_str = hasta.strftime('%Y-%m-%d %H:%M:%S')
        await db.set_ausencia(str(interaction.guild_id), str(interaction.user.id), hasta_str, motivo)

        embed = discord.Embed(title='😴 Ausencia registrada', color=0x95A5A6)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name='Gobernador', value=miembro['gobernador'],            inline=True)
        embed.add_field(name='Días',       value=str(dias),                        inline=True)
        embed.add_field(name='Hasta',      value=hasta.strftime('%d/%m/%Y'),       inline=True)
        if motivo:
            embed.add_field(name='Motivo', value=motivo, inline=False)
        embed.set_footer(text='Usa /volver cuando regreses · La ausencia expira automáticamente')
        await interaction.response.send_message(embed=embed)

    # ── /volver ────────────────────────────────────────────────────────────────

    @app_commands.command(name='volver', description='Cancela tu ausencia y vuelves a estar activo')
    @solo_en_canal('miembros')
    async def volver(self, interaction: discord.Interaction):
        ausencia = await db.get_ausencia(str(interaction.guild_id), str(interaction.user.id))
        if not ausencia:
            await interaction.response.send_message('ℹ️ No tienes ninguna ausencia activa.', ephemeral=True)
            return

        await db.clear_ausencia(str(interaction.guild_id), str(interaction.user.id))
        await interaction.response.send_message(
            f'✅ ¡Bienvenido de vuelta, **{interaction.user.display_name}**! Tu ausencia ha sido cancelada.',
        )

    # ── /ausentes ──────────────────────────────────────────────────────────────

    @app_commands.command(name='ausentes', description='[ADMIN] Lista todos los miembros con ausencia activa')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ausentes(self, interaction: discord.Interaction):
        lista = await db.get_all_ausentes(str(interaction.guild_id))

        if not lista:
            await interaction.response.send_message('✅ No hay ausencias activas.', ephemeral=True)
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
            linea  = f'😴 **{nombre}** — {dias}d restantes'
            if a['motivo']:
                linea += f'\n  _{a["motivo"]}_'
            lineas.append(linea)

        embed = discord.Embed(
            title=f'😴 Ausencias activas — {len(lista)}',
            description='\n'.join(lineas),
            color=0x95A5A6,
        )
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /sin-registrar ─────────────────────────────────────────────────────────

    @app_commands.command(name='sin-registrar', description='[ADMIN] Lista los miembros del servidor que no están registrados')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sin_registrar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        registrados  = await db.get_all_members(str(interaction.guild_id))
        ids_reg      = {m['user_id'] for m in registrados}
        sin_reg      = [m for m in interaction.guild.members if not m.bot and str(m.id) not in ids_reg]

        if not sin_reg:
            await interaction.followup.send('✅ Todos los miembros están registrados.', ephemeral=True)
            return

        lineas = [f'• {m.mention} — `{m.display_name}`' for m in sin_reg[:30]]
        embed  = discord.Embed(
            title=f'⚠️ Sin registrar — {len(sin_reg)} miembros',
            description='\n'.join(lineas),
            color=0xFF8C00,
        )
        if len(sin_reg) > 30:
            embed.description += f'\n_...y {len(sin_reg) - 30} más_'
        embed.set_footer(text=f'Pídeles que usen /registrar · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Errores ────────────────────────────────────────────────────────────────

    @ausentes.error
    @sin_registrar.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Miembros(bot))
