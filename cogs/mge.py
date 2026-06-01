import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, ALIANZA_TAG, ALIANZA_FULL, REINO
from checks import solo_en_canal
from db import database as db


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


class Mge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Autocomplete ───────────────────────────────────────────────────────────

    async def _ac_eventos(self, interaction: discord.Interaction, current: str):
        eventos = await db.mge_get_eventos_activos(str(interaction.guild_id))
        return [
            app_commands.Choice(
                name=f'{e["nombre"]} — meta {fmt_poder(e["poder_min"])}',
                value=str(e['id']),
            )
            for e in eventos
            if current.lower() in e['nombre'].lower()
        ][:25]

    # ── /mge-crear ─────────────────────────────────────────────────────────────

    @app_commands.command(name='mge-crear', description='[ADMIN] Crea un MGE con meta de poder y número de plazas')
    @app_commands.describe(
        nombre='Nombre del MGE (ej: MGE Entrenamiento, MGE Investigación...)',
        meta='Meta de poder a conseguir en el MGE (ej: 50M, 30000K)',
        plazas='Número de participantes seleccionados (por defecto 10)',
        descripcion='Detalle adicional sobre el MGE (opcional)',
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_crear(self, interaction: discord.Interaction, nombre: str, meta: str,
                        plazas: int = 10, descripcion: str = ''):
        meta_int = parse_poder(meta)
        if meta_int < 0:
            await interaction.response.send_message(
                '❌ Formato incorrecto. Usa: `50M`, `30000K` o `50000000`',
                ephemeral=True,
            )
            return
        if not 1 <= plazas <= 100:
            await interaction.response.send_message('❌ El número de plazas debe estar entre 1 y 100.', ephemeral=True)
            return

        evento_id = await db.mge_crear_evento(str(interaction.guild_id), nombre, meta_int, plazas, descripcion)

        embed = discord.Embed(title='✅ MGE creado', color=COLOR_BOT)
        embed.add_field(name='Nombre',  value=nombre,            inline=True)
        embed.add_field(name='Meta',    value=fmt_poder(meta_int), inline=True)
        embed.add_field(name='Plazas',  value=str(plazas),        inline=True)
        embed.add_field(name='ID',      value=f'`#{evento_id}`',  inline=True)
        if descripcion:
            embed.add_field(name='Descripción', value=descripcion, inline=False)
        embed.set_footer(text=f'Inscripciones: /mge-inscribir · Asignación: /mge-asignar · {ALIANZA_TAG}')
        await interaction.response.send_message(embed=embed)

    # ── /mge-cerrar ────────────────────────────────────────────────────────────

    @app_commands.command(name='mge-cerrar', description='[ADMIN] Cierra un MGE — ya no acepta inscripciones')
    @app_commands.describe(evento='MGE a cerrar')
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_cerrar(self, interaction: discord.Interaction, evento: str):
        ok = await db.mge_cerrar_evento(str(interaction.guild_id), int(evento))
        if ok:
            await interaction.response.send_message('✅ MGE cerrado.', ephemeral=True)
        else:
            await interaction.response.send_message('❌ No encontré ese MGE.', ephemeral=True)

    # ── /mge-lista ─────────────────────────────────────────────────────────────

    @app_commands.command(name='mge-lista', description='Muestra los MGEs disponibles y su meta de poder')
    @solo_en_canal('mge-inscripciones')
    async def mge_lista(self, interaction: discord.Interaction):
        eventos = await db.mge_get_eventos_activos(str(interaction.guild_id))
        if not eventos:
            await interaction.response.send_message(
                '📋 No hay MGEs activos ahora mismo.',
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title='📋 MGEs disponibles',
            description=f'*{ALIANZA_TAG} · Reino {REINO}*\nUsa `/mge-inscribir` para apuntarte a uno.',
            color=COLOR_BOT,
        )

        for e in eventos:
            inscritos = await db.mge_count_inscritos(int(e['id']))
            selec     = await db.mge_get_seleccionados(int(e['id']))

            valor = (
                f'🎯 Meta de poder: **{fmt_poder(e["poder_min"])}**\n'
                f'👥 Inscritos: **{inscritos}** · Plazas asignadas: **{len(selec)}/{e["max_plazas"]}**'
            )
            if e['descripcion']:
                valor += f'\n_{e["descripcion"]}_'

            embed.add_field(name=f'`#{e["id"]}` {e["nombre"]}', value=valor, inline=False)

        embed.set_footer(text='Inscríbete y el liderazgo asignará las plazas')
        await interaction.response.send_message(embed=embed)

    # ── /mge-inscribir ─────────────────────────────────────────────────────────

    @app_commands.command(name='mge-inscribir', description='Apúntate a un MGE para que el liderazgo te tenga en cuenta')
    @solo_en_canal('mge-inscripciones')
    @app_commands.describe(evento='MGE al que quieres apuntarte')
    @app_commands.autocomplete(evento=_ac_eventos)
    async def mge_inscribir(self, interaction: discord.Interaction, evento: str):
        miembro = await db.get_member(str(interaction.guild_id), str(interaction.user.id))
        if not miembro:
            await interaction.response.send_message(
                '❌ No tienes perfil registrado. Usa `/registrar` primero.',
                ephemeral=True,
            )
            return

        ev = await db.mge_get_evento(int(evento))
        if not ev or not ev['activo']:
            await interaction.response.send_message('❌ Ese MGE no está disponible.', ephemeral=True)
            return

        ok = await db.mge_inscribir(int(evento), str(interaction.guild_id), str(interaction.user.id),
                                    miembro['gobernador'], miembro['poder'])
        if not ok:
            await interaction.response.send_message(
                f'ℹ️ Ya estás inscrito en **{ev["nombre"]}**.', ephemeral=True
            )
            return

        inscritos = await db.mge_count_inscritos(int(evento))
        embed = discord.Embed(
            title='✅ Inscripción registrada',
            description=f'El liderazgo revisará las inscripciones y asignará las plazas.',
            color=COLOR_BOT,
        )
        embed.add_field(name='MGE',        value=ev['nombre'],              inline=True)
        embed.add_field(name='Gobernador', value=miembro['gobernador'],     inline=True)
        embed.add_field(name='Inscritos',  value=str(inscritos),            inline=True)
        embed.add_field(name='🎯 Meta',    value=fmt_poder(ev['poder_min']), inline=True)
        embed.set_footer(text=f'Usa /mge-salir para cancelar · {ALIANZA_TAG}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /mge-salir ─────────────────────────────────────────────────────────────

    @app_commands.command(name='mge-salir', description='Cancela tu inscripción en un MGE')
    @solo_en_canal('mge-inscripciones')
    @app_commands.describe(evento='MGE del que quieres salir')
    @app_commands.autocomplete(evento=_ac_eventos)
    async def mge_salir(self, interaction: discord.Interaction, evento: str):
        ev = await db.mge_get_evento(int(evento))
        ok = await db.mge_cancelar_inscripcion(int(evento), str(interaction.user.id))
        if not ok:
            await interaction.response.send_message('ℹ️ No estás inscrito en ese MGE.', ephemeral=True)
            return
        nombre = ev['nombre'] if ev else f'MGE #{evento}'
        await interaction.response.send_message(f'✅ Inscripción en **{nombre}** cancelada.', ephemeral=True)

    # ── /mge-participantes ─────────────────────────────────────────────────────

    @app_commands.command(name='mge-participantes', description='[ADMIN] Lista los inscritos en un MGE')
    @app_commands.describe(evento='MGE a consultar')
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_participantes(self, interaction: discord.Interaction, evento: str):
        ev        = await db.mge_get_evento(int(evento))
        inscritos = await db.mge_get_inscritos(int(evento))

        if not ev:
            await interaction.response.send_message('❌ MGE no encontrado.', ephemeral=True)
            return

        embed = discord.Embed(
            title=f'👥 Inscritos — {ev["nombre"]}',
            description=f'🎯 Meta: **{fmt_poder(ev["poder_min"])}** · **{len(inscritos)}** inscritos',
            color=COLOR_BOT,
        )

        if not inscritos:
            embed.description += '\n\n_Nadie se ha inscrito todavía._'
        else:
            lineas = [
                f'**{i}.** **{ins["gobernador"]}** — {fmt_poder(ins["poder"])}'
                for i, ins in enumerate(inscritos, 1)
            ]
            embed.add_field(name='Lista (por poder)', value='\n'.join(lineas[:25]), inline=False)
            if len(inscritos) > 25:
                embed.set_footer(text=f'Mostrando 25 de {len(inscritos)} · {ALIANZA_TAG}')
            else:
                embed.set_footer(text=f'Usa /mge-asignar para asignar plazas · {ALIANZA_TAG}')

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /mge-asignar ───────────────────────────────────────────────────────────

    @app_commands.command(name='mge-asignar', description='[ADMIN] Asigna una posición y meta individual a un participante')
    @app_commands.describe(
        evento='MGE al que asignar',
        posicion='Posición que ocupa (1 = top 1, 2 = top 2...)',
        usuario='Miembro al que asignar esa posición',
        meta='Meta de poder individual para este participante (vacío = usa la meta del MGE)',
    )
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_asignar(self, interaction: discord.Interaction, evento: str,
                          posicion: int, usuario: discord.Member, meta: str = ''):
        ev = await db.mge_get_evento(int(evento))
        if not ev or not ev['activo']:
            await interaction.response.send_message('❌ MGE no encontrado o cerrado.', ephemeral=True)
            return

        if not 1 <= posicion <= ev['max_plazas']:
            await interaction.response.send_message(
                f'❌ La posición debe estar entre **1** y **{ev["max_plazas"]}**.',
                ephemeral=True,
            )
            return

        # Meta individual o la del MGE por defecto
        if meta:
            meta_int = parse_poder(meta)
            if meta_int < 0:
                await interaction.response.send_message(
                    '❌ Formato de meta incorrecto. Usa: `50M`, `30000K` o `50000000`', ephemeral=True
                )
                return
        else:
            meta_int = ev['poder_min']

        miembro    = await db.get_member(str(interaction.guild_id), str(usuario.id))
        gobernador = miembro['gobernador'] if miembro else usuario.display_name

        # poder se reutiliza para guardar la meta individual del participante
        await db.mge_seleccionar(int(evento), str(interaction.guild_id),
                                 str(usuario.id), gobernador, meta_int, posicion)

        seleccionados = await db.mge_get_seleccionados(int(evento))
        medalla = ['🥇', '🥈', '🥉'][posicion - 1] if posicion <= 3 else f'**#{posicion}**'

        await interaction.response.send_message(
            f'✅ {medalla} **{gobernador}** → posición **{posicion}** · '
            f'Meta: **{fmt_poder(meta_int)}** · '
            f'{len(seleccionados)}/{ev["max_plazas"]} plazas cubiertas.',
            ephemeral=True,
        )

    # ── /mge-quitar ────────────────────────────────────────────────────────────

    @app_commands.command(name='mge-quitar', description='[ADMIN] Quita la plaza asignada a un miembro')
    @app_commands.describe(
        evento='MGE del que quitar la plaza',
        usuario='Miembro al que quitar la plaza',
    )
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_quitar(self, interaction: discord.Interaction, evento: str, usuario: discord.Member):
        ok = await db.mge_quitar_seleccion(int(evento), str(usuario.id))
        if not ok:
            await interaction.response.send_message(f'ℹ️ {usuario.display_name} no tiene plaza asignada.', ephemeral=True)
            return
        seleccionados = await db.mge_get_seleccionados(int(evento))
        ev = await db.mge_get_evento(int(evento))
        await interaction.response.send_message(
            f'✅ Plaza de **{usuario.display_name}** retirada — '
            f'**{len(seleccionados)}/{ev["max_plazas"]}** plazas cubiertas.',
            ephemeral=True,
        )

    # ── /mge-seleccionados ─────────────────────────────────────────────────────

    @app_commands.command(name='mge-seleccionados', description='[ADMIN] Muestra los participantes elegidos y su meta individual')
    @solo_en_canal('mge-resultados')
    @app_commands.describe(evento='MGE a consultar')
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_seleccionados(self, interaction: discord.Interaction, evento: str):
        ev            = await db.mge_get_evento(int(evento))
        seleccionados = await db.mge_get_seleccionados(int(evento))

        if not seleccionados:
            await interaction.response.send_message(
                f'⏳ Todavía no hay participantes asignados para **{ev["nombre"] if ev else "este MGE"}**.',
                ephemeral=True,
            )
            return

        medallas = ['🥇', '🥈', '🥉']
        lineas   = []
        for s in seleccionados:
            pos    = medallas[s['posicion'] - 1] if s['posicion'] <= 3 else f'**#{s["posicion"]}**'
            lineas.append(f'{pos} **{s["gobernador"]}** — 🎯 {fmt_poder(s["poder"])}')

        embed = discord.Embed(
            title=f'🏆 Seleccionados — {ev["nombre"]}',
            description='\n'.join(lineas),
            color=0xFFD700,
        )
        embed.set_footer(text=f'{len(seleccionados)}/{ev["max_plazas"]} plazas · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    # ── /mge-publicar ──────────────────────────────────────────────────────────

    @app_commands.command(name='mge-publicar', description='[ADMIN] Publica la lista final con metas individuales y menciona a todos')
    @app_commands.describe(evento='MGE a publicar')
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_publicar(self, interaction: discord.Interaction, evento: str):
        ev            = await db.mge_get_evento(int(evento))
        seleccionados = await db.mge_get_seleccionados(int(evento))

        if not seleccionados:
            await interaction.response.send_message('❌ No hay participantes asignados todavía.', ephemeral=True)
            return

        medallas = ['🥇', '🥈', '🥉']
        lineas   = []
        for s in seleccionados:
            pos = medallas[s['posicion'] - 1] if s['posicion'] <= 3 else f'**#{s["posicion"]}**'
            lineas.append(f'{pos} **{s["gobernador"]}** — 🎯 Meta: **{fmt_poder(s["poder"])}**')

        menciones = ' '.join(f'<@{s["user_id"]}>' for s in seleccionados)

        embed = discord.Embed(
            title=f'🏆 Participantes del {ev["nombre"]}',
            description=(
                f'**{ALIANZA_FULL} · Reino {REINO}**\n\n'
                f'¡Estos son los **{len(seleccionados)}** seleccionados y sus metas!'
            ),
            color=0xFFD700,
        )
        embed.add_field(name='🎖️ Lista de participantes', value='\n'.join(lineas), inline=False)
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')

        # Publicar en canal de resultados si está configurado, si no en el canal actual
        canal_resultados = None
        canal_id = await db.get_config(str(interaction.guild_id), 'mge_canal_resultados')
        if canal_id:
            canal_resultados = interaction.guild.get_channel(int(canal_id))
        if not canal_resultados:
            canal_resultados = next(
                (c for c in interaction.guild.text_channels if 'mge-resultados' in c.name),
                None,
            )

        if canal_resultados and canal_resultados != interaction.channel:
            await canal_resultados.send(content=menciones, embed=embed)
            await interaction.response.send_message(
                f'✅ Lista publicada en {canal_resultados.mention}', ephemeral=True
            )
        else:
            await interaction.response.send_message(content=menciones, embed=embed)

    # ── Errores ────────────────────────────────────────────────────────────────

    @mge_crear.error
    @mge_cerrar.error
    @mge_participantes.error
    @mge_asignar.error
    @mge_quitar.error
    @mge_publicar.error
    @mge_seleccionados.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Mge(bot))
