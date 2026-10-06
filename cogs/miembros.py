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


def embed_perfil(target: discord.abc.User, miembro, ausencia) -> discord.Embed:
    embed = discord.Embed(
        title=f'{"😴 " if ausencia else "👤 "}{miembro["gobernador"]}',
        color=0x95A5A6 if ausencia else COLOR_BOT,
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name='Poder / Power', value=fmt_poder(miembro['poder']),                     inline=True)
    embed.add_field(name='Tropa / Troop', value=TROPAS.get(miembro['tropa'], miembro['tropa']), inline=True)
    if ausencia:
        embed.add_field(name='😴 Ausente hasta / Absent until', value=fmt_hasta(ausencia['hasta']), inline=False)
        if ausencia['motivo']:
            embed.add_field(name='Motivo / Reason', value=ausencia['motivo'], inline=False)
    embed.set_footer(text=f'Discord: {target.display_name} · {ALIANZA_TAG} · Reino {REINO}')
    return embed


def puede_registrarse(member: discord.Member) -> bool:
    """Solo los aprobados en reclutamiento (🔰 Nuevo) o los que ya son 🌿 Miembro."""
    return any(r.name in ('🔰 Nuevo', '🌿 Miembro') for r in member.roles)


# ── Formularios ────────────────────────────────────────────────────────────────

class RegistroModal(discord.ui.Modal, title='📝 Registro / Registration'):
    def __init__(self, miembro=None):
        super().__init__()
        self.gobernador = discord.ui.TextInput(
            placeholder='Tal cual aparece en el juego / Exactly as in-game', max_length=50,
            default=miembro['gobernador'] if miembro else None,
        )
        self.poder = discord.ui.TextInput(
            placeholder='Ej: 150M, 50000K', max_length=20,
            default=fmt_poder(miembro['poder']) if miembro else None,
        )
        tropa_actual = miembro['tropa'] if miembro else None
        self.tropa = discord.ui.Select(
            placeholder='Elige tu tropa / Pick your troop',
            options=[discord.SelectOption(label=nombre, value=clave, emoji=TROPAS_EMOJI[clave],
                                          default=clave == tropa_actual)
                     for clave, nombre in TROPAS.items()],
        )
        self.add_item(discord.ui.Label(text='Nombre de gobernador / Governor name', component=self.gobernador))
        self.add_item(discord.ui.Label(text='Poder actual / Current power', component=self.poder))
        self.add_item(discord.ui.Label(text='Tropa principal / Main troop', component=self.tropa))

    async def on_submit(self, interaction: discord.Interaction):
        poder_int = parse_poder(self.poder.value)
        if poder_int < 0:
            await interaction.response.send_message(
                '❌ Formato de poder incorrecto. Usa: `150M`, `50000K` o `150000000`\n'
                '_Incorrect power format. Use: `150M`, `50000K` or `150000000`_',
                ephemeral=True,
            )
            return
        nuevo = await db.get_member(str(interaction.guild_id), str(interaction.user.id)) is None
        tropa = self.tropa.values[0]
        gobernador = self.gobernador.value.strip()
        await db.upsert_member(str(interaction.guild_id), str(interaction.user.id),
                               interaction.user.display_name, gobernador, poder_int, tropa)
        try:
            await asignar_rol_tropa(interaction.user, tropa)
        except discord.HTTPException as e:
            print(f'[miembros] No se pudieron asignar roles a {interaction.user}: {e}')

        embed = discord.Embed(
            title='✅ ¡Registrado! / Registered!' if nuevo else '✅ Perfil actualizado / Profile updated',
            color=COLOR_BOT,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name='Gobernador / Governor', value=gobernador,           inline=True)
        embed.add_field(name='Poder / Power',          value=fmt_poder(poder_int), inline=True)
        embed.add_field(name='Tropa / Troop',          value=TROPAS[tropa],        inline=True)
        embed.set_footer(text=f'Puedes actualizarlo cuando quieras con 📝 · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AusenciaModal(discord.ui.Modal, title='😴 Ausencia / Absence'):
    def __init__(self):
        super().__init__()
        self.dias   = discord.ui.TextInput(placeholder='1 – 60', max_length=2)
        self.motivo = discord.ui.TextInput(placeholder='Vacaciones, trabajo… / Holidays, work…', max_length=200,
                                           style=discord.TextStyle.paragraph, required=False)
        self.add_item(discord.ui.Label(text='¿Cuántos días? / How many days?', component=self.dias))
        self.add_item(discord.ui.Label(text='Motivo (opcional) / Reason (optional)', component=self.motivo))

    async def on_submit(self, interaction: discord.Interaction):
        dias = self.dias.value.strip()
        if not dias.isdigit() or not 1 <= int(dias) <= 60:
            await interaction.response.send_message(
                '❌ Los días deben ser un número entre 1 y 60. / Days must be between 1 and 60.', ephemeral=True
            )
            return
        hasta = datetime.utcnow() + timedelta(days=int(dias))
        await db.set_ausencia(str(interaction.guild_id), str(interaction.user.id),
                              hasta.strftime('%Y-%m-%d %H:%M:%S'), self.motivo.value.strip())
        await interaction.response.send_message(
            f'😴 Ausencia registrada hasta el **{hasta.strftime("%d/%m/%Y")}** ({dias} días).\n'
            f'_Absence registered until **{hasta.strftime("%d/%m/%Y")}**._\n'
            'Cuando vuelvas pulsa ✅ **He vuelto** (o caduca sola). / _Press ✅ when you are back (or it expires)._',
            ephemeral=True,
        )


# ── Panel anclado del canal de miembros ────────────────────────────────────────

class PanelMiembrosView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Registrarme / Actualizar', emoji='📝', style=discord.ButtonStyle.success,
                       custom_id='miembros:registrar')
    async def registrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not puede_registrarse(interaction.user):
            await interaction.response.send_message(
                '❌ Para registrarte primero debes solicitar el ingreso en **⚔️│reclutamiento**.\n'
                '_To register you must first apply in **⚔️│reclutamiento** and be approved by leadership._',
                ephemeral=True,
            )
            return
        miembro = await db.get_member(str(interaction.guild_id), str(interaction.user.id))
        await interaction.response.send_modal(RegistroModal(miembro))

    @discord.ui.button(label='Mi perfil', emoji='👤', style=discord.ButtonStyle.primary, custom_id='miembros:perfil')
    async def perfil(self, interaction: discord.Interaction, button: discord.ui.Button):
        miembro = await db.get_member(str(interaction.guild_id), str(interaction.user.id))
        if not miembro:
            await interaction.response.send_message(
                'Todavía no tienes perfil: pulsa 📝 **Registrarme**. / _No profile yet: press 📝._', ephemeral=True
            )
            return
        ausencia = await db.get_ausencia(str(interaction.guild_id), str(interaction.user.id))
        await interaction.response.send_message(embed=embed_perfil(interaction.user, miembro, ausencia), ephemeral=True)

    @discord.ui.button(label='Ausencia', emoji='😴', style=discord.ButtonStyle.secondary, custom_id='miembros:ausencia')
    async def ausencia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await db.get_member(str(interaction.guild_id), str(interaction.user.id)):
            await interaction.response.send_message(
                '❌ Primero regístrate con 📝. / _Register first with 📝._', ephemeral=True
            )
            return
        await interaction.response.send_modal(AusenciaModal())

    @discord.ui.button(label='He vuelto', emoji='✅', style=discord.ButtonStyle.secondary, custom_id='miembros:volver')
    async def volver(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await db.get_ausencia(str(interaction.guild_id), str(interaction.user.id)):
            await interaction.response.send_message(
                'ℹ️ No tienes ninguna ausencia activa. / You have no active absence.', ephemeral=True
            )
            return
        await db.clear_ausencia(str(interaction.guild_id), str(interaction.user.id))
        await interaction.response.send_message(
            f'✅ ¡Bienvenido de vuelta, **{interaction.user.display_name}**! / Welcome back!', ephemeral=True
        )


class Miembros(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(PanelMiembrosView())

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
                'No tienes perfil. Pulsa 📝 **Registrarme** en el canal de miembros.\n'
                '_You have no profile. Press 📝 **Register** in the members channel._'
                if not usuario else
                f'{target.display_name} no tiene perfil. / {target.display_name} has no profile.'
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        ausencia = await db.get_ausencia(str(interaction.guild_id), str(target.id))
        await interaction.response.send_message(embed=embed_perfil(target, miembro, ausencia))

    # ── /miembros ──────────────────────────────────────────────────────────────

    @app_commands.command(name='miembros', description='Lista todos los miembros registrados / List all registered members')
    @solo_en_canal('miembros')
    async def miembros(self, interaction: discord.Interaction):
        lista    = await db.get_all_members(str(interaction.guild_id))
        ausentes = await db.get_ausentes_ids(str(interaction.guild_id))

        if not lista:
            await interaction.response.send_message(
                'No hay miembros registrados. Pulsad 📝 **Registrarme** en este canal.\n_No registered members. Press 📝 **Register**._',
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
        embed.set_footer(text=f'Pídeles que pulsen 📝 Registrarme · Ask them to press 📝 Register · {ALIANZA_TAG} · Reino {REINO}')
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
