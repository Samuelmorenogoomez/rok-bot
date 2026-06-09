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
    @app_commands.describe(
        evento='MGE al que quieres apuntarte',
        cabezas='Cabezas doradas que tienes disponibles para el evento',
    )
    @app_commands.autocomplete(evento=_ac_eventos)
    async def mge_inscribir(self, interaction: discord.Interaction, evento: str, cabezas: int):
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
                                    miembro['gobernador'], miembro['poder'], cabezas)
        if not ok:
            await interaction.response.send_message(
                f'ℹ️ Ya estás inscrito en **{ev["nombre"]}**.', ephemeral=True
            )
            return

        inscritos = await db.mge_count_inscritos(int(evento))
        embed = discord.Embed(
            title='✅ Inscripción registrada',
            description='El liderazgo revisará las inscripciones y asignará las plazas.',
            color=COLOR_BOT,
        )
        embed.add_field(name='MGE',               value=ev['nombre'],               inline=True)
        embed.add_field(name='Gobernador',         value=miembro['gobernador'],      inline=True)
        embed.add_field(name='👑 Cabezas doradas', value=str(cabezas),               inline=True)
        embed.add_field(name='🎯 Meta',            value=fmt_poder(ev['poder_min']), inline=True)
        embed.add_field(name='Inscritos',          value=str(inscritos),             inline=True)
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

    # ── /mge-inscribir-externo ────────────────────────────────────────────────

    async def _ac_externos(self, interaction: discord.Interaction, current: str):
        externos = await db.get_miembros_externos(str(interaction.guild_id))
        return [
            app_commands.Choice(name=e['gobernador'], value=e['gobernador'])
            for e in externos
            if current.lower() in e['gobernador'].lower()
        ][:25]

    @app_commands.command(name='mge-inscribir-externo', description='[ADMIN] Inscribe a un gobernador externo (sin Discord) en un MGE')
    @app_commands.describe(
        evento='MGE al que inscribir',
        gobernador='Gobernador externo registrado',
        cabezas='Cabezas doradas disponibles (opcional)',
    )
    @app_commands.autocomplete(evento=_ac_eventos, gobernador=_ac_externos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_inscribir_externo(self, interaction: discord.Interaction,
                                    evento: str, gobernador: str, cabezas: int):
        ev = await db.mge_get_evento(int(evento))
        if not ev or not ev['activo']:
            await interaction.response.send_message('❌ MGE no encontrado o cerrado.', ephemeral=True)
            return

        user_id_ext = 'ext_' + gobernador.lower().replace(' ', '_')
        miembro     = await db.get_member(str(interaction.guild_id), user_id_ext)
        poder       = miembro['poder'] if miembro else 0

        ok = await db.mge_inscribir(int(evento), str(interaction.guild_id),
                                    user_id_ext, gobernador, poder, cabezas)
        if not ok:
            await interaction.response.send_message(
                f'ℹ️ **{gobernador}** ya está inscrito en **{ev["nombre"]}**.', ephemeral=True
            )
            return

        inscritos = await db.mge_count_inscritos(int(evento))
        await interaction.response.send_message(
            f'✅ **{gobernador}** _(externo)_ inscrito en **{ev["nombre"]}** · '
            f'👑 {cabezas} cabezas · {inscritos} inscritos en total.',
            ephemeral=True,
        )

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
            total_cabezas = sum(ins['cabezas'] or 0 for ins in inscritos)
            lineas = [
                f'**{i}.** **{ins["gobernador"]}** — {fmt_poder(ins["poder"])} · 👑 {ins["cabezas"] or 0}'
                for i, ins in enumerate(inscritos, 1)
            ]
            embed.add_field(name='Lista (por poder) · 👑 = cabezas doradas', value='\n'.join(lineas[:25]), inline=False)
            embed.add_field(name='👑 Total cabezas doradas', value=str(total_cabezas), inline=True)
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
        usuario='Miembro de Discord a asignar (usa gobernador_ext si no está en el servidor)',
        gobernador_ext='Nombre de gobernador externo (sin cuenta Discord)',
        meta='Meta de poder individual (vacío = usa la meta del MGE)',
    )
    @app_commands.autocomplete(evento=_ac_eventos, gobernador_ext=_ac_externos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_asignar(self, interaction: discord.Interaction, evento: str,
                          posicion: int, usuario: discord.Member = None,
                          gobernador_ext: str = None, meta: str = ''):
        if not usuario and not gobernador_ext:
            await interaction.response.send_message(
                '❌ Debes indicar `usuario` (miembro Discord) o `gobernador_ext` (externo sin Discord).',
                ephemeral=True,
            )
            return

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

        if meta:
            meta_int = parse_poder(meta)
            if meta_int < 0:
                await interaction.response.send_message(
                    '❌ Formato de meta incorrecto. Usa: `50M`, `30000K` o `50000000`', ephemeral=True
                )
                return
        else:
            meta_int = ev['poder_min']

        # Resolver user_id y nombre de gobernador
        if usuario:
            miembro    = await db.get_member(str(interaction.guild_id), str(usuario.id))
            gobernador = miembro['gobernador'] if miembro else usuario.display_name
            user_id    = str(usuario.id)
        else:
            gobernador = gobernador_ext
            user_id    = 'ext_' + gobernador_ext.lower().replace(' ', '_')

        await db.mge_seleccionar(int(evento), str(interaction.guild_id),
                                 user_id, gobernador, meta_int, posicion)

        seleccionados = await db.mge_get_seleccionados(int(evento))
        medalla = ['🥇', '🥈', '🥉'][posicion - 1] if posicion <= 3 else f'**#{posicion}**'
        ext_tag = ' _(externo)_' if not usuario else ''

        await interaction.response.send_message(
            f'✅ {medalla} **{gobernador}**{ext_tag} → posición **{posicion}** · '
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

    # ── /mge-anunciar ─────────────────────────────────────────────────────────

    @app_commands.command(name='mge-anunciar', description='[ADMIN] Anuncia un MGE en el canal de anuncios explicando cómo inscribirse')
    @app_commands.describe(
        evento='MGE a anunciar',
        tropa='Tipo de tropa al que va dirigido el MGE (vacío = todas las tropas)',
        canal='Canal donde publicar (vacío = busca #anuncios automáticamente)',
    )
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.choices(tropa=[
        app_commands.Choice(name='⚔️ Infantería',  value='infanteria'),
        app_commands.Choice(name='🐴 Caballería',  value='caballeria'),
        app_commands.Choice(name='🏹 Arqueros',    value='arqueros'),
        app_commands.Choice(name='⚙️ Maquinaria', value='maquinaria'),
        app_commands.Choice(name='🔀 Mixto',       value='mixto'),
        app_commands.Choice(name='🌐 Todas las tropas', value='todas'),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_anunciar(self, interaction: discord.Interaction, evento: str,
                           tropa: str = 'todas', canal: discord.TextChannel = None):
        ev = await db.mge_get_evento(int(evento))
        if not ev or not ev['activo']:
            await interaction.response.send_message('❌ MGE no encontrado o cerrado.', ephemeral=True)
            return

        # Resolver canal destino
        if not canal:
            canal = next(
                (c for c in interaction.guild.text_channels
                 if 'anuncios' in c.name and 'kvk' not in c.name and 'ark' not in c.name),
                None,
            )
        if not canal:
            await interaction.response.send_message(
                '❌ No encontré canal de anuncios. Especifica el canal con el parámetro `canal`.',
                ephemeral=True,
            )
            return

        # Canal de inscripciones
        canal_inscripciones = next(
            (c for c in interaction.guild.text_channels if 'mge-inscripciones' in c.name), None
        )

        # Datos de tropa
        TROPAS_FULL = {
            'infanteria': '⚔️ Infantería',
            'caballeria': '🐴 Caballería',
            'arqueros':   '🏹 Arqueros',
            'maquinaria': '⚙️ Maquinaria',
            'mixto':      '🔀 Mixto',
            'todas':      '🌐 Todas las tropas',
        }
        nombre_tropa = TROPAS_FULL.get(tropa, '🌐 Todas las tropas')

        # Mencionar el rol de tropa si aplica
        mencion_tropa = ''
        if tropa != 'todas':
            roles_nombres = {
                'infanteria': '🗡️ Infantería',
                'caballeria': '🐴 Caballería',
                'arqueros':   '🏹 Arqueros',
                'maquinaria': '⚙️ Maquinaria',
                'mixto':      '🔱 Mixto',
            }
            rol_tropa = discord.utils.get(interaction.guild.roles, name=roles_nombres.get(tropa, ''))
            if rol_tropa:
                mencion_tropa = rol_tropa.mention

        seleccionados = await db.mge_get_seleccionados(int(evento))
        inscritos     = await db.mge_count_inscritos(int(evento))

        canal_ref = canal_inscripciones.mention if canal_inscripciones else '**📝│mge-inscripciones**'

        embed = discord.Embed(
            title=f'🔥 {ev["nombre"]} — ¡Inscripciones abiertas!',
            description=(
                f'**{ALIANZA_FULL} · Reino {REINO}**\n\n'
                f'¡Ha comenzado el período de inscripciones para el **{ev["nombre"]}**!\n'
                + (f'Este MGE está orientado a **{nombre_tropa}**.\n' if tropa != 'todas' else '')
                + (f'\n_{ev["descripcion"]}_' if ev['descripcion'] else '')
            ),
            color=0xFFD700,
        )

        embed.add_field(
            name='📊 Detalles del evento',
            value=(
                f'🎯 **Meta de poder:** {fmt_poder(ev["poder_min"])}\n'
                f'👥 **Plazas:** {ev["max_plazas"]} participantes\n'
                f'🗡️ **Tropa:** {nombre_tropa}'
            ),
            inline=False,
        )

        embed.add_field(
            name='📋 Cómo inscribirse',
            value=(
                f'**1.** Ve al canal {canal_ref}\n'
                f'**2.** Usa `/mge-lista` para ver el evento y su meta\n'
                f'**3.** Usa `/mge-inscribir` y selecciona **{ev["nombre"]}**\n'
                f'**4.** El liderazgo revisará y asignará las {ev["max_plazas"]} plazas\n\n'
                f'> ⚠️ Necesitas tener el perfil registrado con `/registrar` para poder inscribirte.'
            ),
            inline=False,
        )

        embed.add_field(
            name='⏳ Estado actual',
            value=(
                f'📝 **Inscritos:** {inscritos}\n'
                f'🏆 **Plazas asignadas:** {len(seleccionados)}/{ev["max_plazas"]}'
            ),
            inline=False,
        )

        embed.set_footer(text=f'Usa /mge-salir para cancelar tu inscripción · {ALIANZA_TAG} · Reino {REINO}')

        content = mencion_tropa if mencion_tropa else None
        await canal.send(content=content, embed=embed)

        await interaction.response.send_message(
            f'✅ Anuncio del **{ev["nombre"]}** publicado en {canal.mention}.',
            ephemeral=True,
        )

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

    # ── /mge-historial ─────────────────────────────────────────────────────────

    @app_commands.command(name='mge-historial', description='Historial de MGEs de un gobernador (o resumen general)')
    @app_commands.describe(usuario='Gobernador a consultar (vacío = lista todos los MGEs pasados)')
    async def mge_historial(self, interaction: discord.Interaction, usuario: discord.Member = None):
        guild_id = str(interaction.guild_id)
        medallas = ['🥇', '🥈', '🥉']

        # ── Con usuario: historial personal ───────────────────────────────────
        if usuario:
            historial = await db.mge_get_historial_usuario(guild_id, str(usuario.id))
            miembro   = await db.get_member(guild_id, str(usuario.id))
            nombre    = miembro['gobernador'] if miembro else usuario.display_name

            embed = discord.Embed(
                title=f'📜 Historial MGE — {nombre}',
                color=COLOR_BOT,
            )
            embed.set_thumbnail(url=usuario.display_avatar.url)

            if not historial:
                embed.description = '_Este gobernador no ha participado en ningún MGE todavía._'
            else:
                lineas = []
                for h in historial:
                    pos   = medallas[h['posicion'] - 1] if h['posicion'] <= 3 else f'**#{h["posicion"]}**'
                    fecha = h['created_at'][:10] if h['created_at'] else '—'
                    lineas.append(
                        f'{pos} **{h["nombre"]}** — 🎯 {fmt_poder(h["meta_individual"])} · 📅 {fecha}'
                    )
                embed.description = '\n'.join(lineas)
                embed.set_footer(text=f'{len(historial)} participaciones · {ALIANZA_TAG} · Reino {REINO}')

            await interaction.response.send_message(embed=embed)
            return

        # ── Sin usuario: resumen de todos los MGEs cerrados ───────────────────
        cerrados = await db.mge_get_eventos_cerrados(guild_id)
        if not cerrados:
            await interaction.response.send_message(
                '📋 No hay MGEs finalizados todavía.', ephemeral=True
            )
            return

        embed = discord.Embed(
            title='📜 Historial de MGEs',
            description=f'*{ALIANZA_TAG} · Reino {REINO}*\nUsa `/mge-historial usuario:@alguien` para ver el historial personal.',
            color=0x95A5A6,
        )
        for e in cerrados[:10]:
            selec = await db.mge_get_seleccionados(int(e['id']))
            fecha = e['created_at'][:10] if e['created_at'] else '—'
            if selec:
                partes = []
                for s in selec[:3]:
                    pos_str = medallas[s['posicion'] - 1] if s['posicion'] <= 3 else f'#{s["posicion"]}'
                    partes.append(f'{pos_str} {s["gobernador"]}')
                top3 = ' · '.join(partes)
            else:
                top3 = '_Sin participantes_'
            embed.add_field(
                name=f'`#{e["id"]}` {e["nombre"]} · 📅 {fecha}',
                value=f'🎯 Meta: {fmt_poder(e["poder_min"])} · 👥 {len(selec)} participantes\n{top3}',
                inline=False,
            )
        embed.set_footer(text=f'Mostrando los últimos {min(len(cerrados), 10)} MGEs · {ALIANZA_TAG}')
        await interaction.response.send_message(embed=embed)

    # ── Errores ────────────────────────────────────────────────────────────────

    @mge_crear.error
    @mge_cerrar.error
    @mge_participantes.error
    @mge_asignar.error
    @mge_inscribir_externo.error
    @mge_quitar.error
    @mge_anunciar.error
    @mge_publicar.error
    @mge_seleccionados.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Mge(bot))
