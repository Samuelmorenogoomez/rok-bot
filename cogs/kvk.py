import asyncio
import io
import json
import re
import time
import aiohttp
import openpyxl
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone

from config import COLOR_BOT, ALIANZA_FULL, ALIANZA_TAG, REINO
from checks import solo_en_canal
from db import database as db


def refrescar_calendario(guild):
    from cogs.eventos import refrescar_calendario_luego
    refrescar_calendario_luego(guild)


_tareas: set = set()


def refrescar_tablero_luego(guild):
    """Repinta el tablero sin hacer esperar a quien pulsó (son varios mensajes que editar)."""
    tarea = asyncio.create_task(refrescar_tablero(guild))
    _tareas.add(tarea)
    tarea.add_done_callback(_tareas.discard)


class ConfirmResetView(discord.ui.View):
    def __init__(self, temporada_id: int, temporada_nombre: str):
        super().__init__(timeout=30)
        self.temporada_id     = temporada_id
        self.temporada_nombre = temporada_nombre

    @discord.ui.button(label='Sí, borrar todo', style=discord.ButtonStyle.danger, emoji='🗑️')
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.kvk_clear_import(self.temporada_id)
        await db.kvk_clear_stats(self.temporada_id)
        await db.kvk_clear_guerras(self.temporada_id)
        self.stop()
        refrescar_tablero_luego(interaction.guild)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title='✅ KvK reseteado',
                description=f'Todos los datos de **{self.temporada_nombre}** han sido borrados.\nPuedes usar `/kvk-importar` para cargar datos nuevos.',
                color=COLOR_BOT,
            ),
            view=None,
        )

    @discord.ui.button(label='Cancelar', style=discord.ButtonStyle.secondary, emoji='✖️')
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title='❌ Reset cancelado', color=COLOR_BOT),
            view=None,
        )


def parse_excel(data: bytes) -> list[dict]:
    wb  = openpyxl.load_workbook(io.BytesIO(data))

    # Buscar hoja K{id} (datos de jugadores individuales)
    hoja = next((wb[s] for s in wb.sheetnames if s.startswith('K') and s[1:].isdigit()), None)
    if not hoja:
        raise ValueError('No encontré la hoja de jugadores (K####) en el Excel.')

    # Fila 4 = cabeceras, fila 5+ = datos
    # Columnas 27-38 (1-based) = sección Deltas
    # En 0-indexed desde la tupla de valores: 26-37
    jugadores = []
    for row in hoja.iter_rows(min_row=5, values_only=True):
        gov_id    = row[26]
        gov_name  = row[27]
        muertes   = row[30]
        kill_pts  = row[31]
        kills_t4  = row[35]
        kills_t5  = row[36]
        dkp       = row[37]

        if not gov_id or not gov_name:
            continue
        if (kills_t4 or 0) < 0 and (kills_t5 or 0) < 0:
            continue  # Datos negativos = jugador inactivo/excluido

        jugadores.append({
            'governor_id':   str(gov_id),
            'governor_name': str(gov_name),
            'kills_t4':      max(0, kills_t4 or 0),
            'kills_t5':      max(0, kills_t5 or 0),
            'kill_points':   max(0, kill_pts  or 0),
            'muertes':       max(0, muertes   or 0),
            'dkp':           max(0, dkp       or 0),
            'aclamacion':    0,  # el Excel no trae ni la aclamación ni el poder: solo HeroScroll por enlace
            'poder_delta':   0,
            'poder_inicio':  0,
        })

    return jugadores


# ── HeroScroll por enlace (sin descargar el Excel) ─────────────────────────────

ENLACE_HEROSCROLL = re.compile(r'^https://(www\.)?heroscroll\.com/rok/kvk-dashboard\?id=[\w-]+$')
HORAS_AUTO        = 6  # cada cuánto se vuelve a leer HeroScroll solo (no hace falta más: escanean pocas veces al día)


def leer_heroscroll(html: str) -> list[dict]:
    """Gobernadores del reino REINO a partir de la página del dashboard.

    HeroScroll no tiene API: la página trae los datos incrustados en trozos
    self.__next_f.push([1, "…JSON escapado…"]) de Next.js. Se usan los deltas (lo hecho en el KvK),
    igual que la sección Deltas del Excel.
    """
    trozos  = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    payload = ''.join(json.loads(t) for t in trozos)
    decoder = json.JSONDecoder()
    gobernadores = None
    for m in re.finditer(r'"governors":', payload):
        try:
            valor, _ = decoder.raw_decode(payload, m.end())
        except json.JSONDecodeError:
            continue
        if isinstance(valor, dict) and valor:
            gobernadores = valor
            break
    if not gobernadores:
        raise ValueError('no encuentro los gobernadores en la página (puede que HeroScroll haya cambiado su web)')

    jugadores = []
    for g in gobernadores.values():
        if g.get('kingdom_id') != REINO:
            continue
        d  = g.get('deltas') or {}
        t4 = d.get('t4_kills') or 0
        t5 = d.get('t5_kills') or 0
        if t4 < 0 and t5 < 0:
            continue  # Datos negativos = jugador inactivo/excluido (mismo criterio que el Excel)
        jugadores.append({
            'governor_id':   str(g['governor_id']),
            'governor_name': g.get('name') or str(g['governor_id']),
            'kills_t4':      max(0, t4),
            'kills_t5':      max(0, t5),
            'kill_points':   max(0, d.get('killpoints') or 0),
            'muertes':       max(0, d.get('deads') or 0),
            'dkp':           max(0, g.get('dkp') or 0),
            'aclamacion':    max(0, d.get('acclaim') or 0),
            'poder_delta':   d.get('power') or 0,  # puede ser negativo: poder perdido en el KvK
            # Poder al empezar el KvK = poder actual − lo ganado desde entonces; decide su grupo de metas
            'poder_inicio':  max(0, (g.get('power') or 0) - (d.get('power') or 0)),
        })
    if not jugadores:
        raise ValueError(f'el reino {REINO} no aparece en ese KvK')
    return jugadores


async def descargar_heroscroll(enlace: str) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout, headers={'User-Agent': 'Mozilla/5.0 (rok-bot)'}) as sesion:
        async with sesion.get(enlace) as resp:
            if resp.status != 200:
                raise ValueError(f'HeroScroll ha respondido con el error {resp.status}')
            html = await resp.text()
    # La página pesa varios MB: se procesa fuera del bucle para no congelar el bot
    return await asyncio.to_thread(leer_heroscroll, html)


async def enlace_heroscroll(guild_id: str, temporada_id: int) -> str | None:
    """El enlace guardado solo vale para la temporada con la que se guardó (cada KvK tiene el suyo)."""
    dato = await db.get_config(guild_id, 'heroscroll_url')
    if not dato or '|' not in dato:
        return None
    tid, enlace = dato.split('|', 1)
    return enlace if tid == str(temporada_id) else None


async def guardar_importados(guild_id: str, temporada_id: int, jugadores: list[dict]):
    rows = [
        (temporada_id, j['governor_id'], j['governor_name'], j['kills_t4'], j['kills_t5'],
         j['kill_points'], j['muertes'], j['dkp'], j['aclamacion'], j['poder_delta'], j['poder_inicio'])
        for j in jugadores
    ]
    await db.kvk_clear_import(temporada_id)
    await db.kvk_insert_import(temporada_id, rows)
    await db.set_config(guild_id, 'kvk_datos_ts', str(int(time.time())))


# ── Tablero fijo de #kvk-stats ─────────────────────────────────────────────────

MAX_DESCRIPCION = 3900  # Discord admite 4096 por embed; se deja margen
_lock_tablero   = asyncio.Lock()


def fmt_signo(n: int) -> str:
    from cogs.mge import fmt_poder
    return ('+' if n > 0 else '−' if n < 0 else '±') + fmt_poder(abs(n))


def _contra_meta(hecho: int, meta: int) -> str:
    from cogs.mge import fmt_poder
    if not meta:
        return ''
    if hecho >= meta:
        return f' / {fmt_poder(meta)} ✅'
    return f' / {fmt_poder(meta)} (faltan {fmt_poder(meta - hecho)})'


def linea_tablero(pos: int, s, grupos: list[dict]) -> str:
    """Una línea por gobernador, con las metas de su grupo de poder (y el icono del grupo si hay varios)."""
    from cogs.mge import fmt_poder
    from cogs.guerra import indice_grupo, icono_grupo
    medalla = ['🥇', '🥈', '🥉'][pos - 1] if pos <= 3 else f'`{pos:>3}.`'
    nombre  = discord.utils.escape_markdown(s['governor_name'])
    i       = indice_grupo(grupos, s)
    g       = grupos[i] if i is not None else {'kp': 0, 'aclamacion': 0}
    icono   = f' {icono_grupo(grupos, i)}' if len(grupos) > 1 else ''
    # La aclamación va primero y en negrita: es lo que más cuenta
    return (f'{medalla} **{nombre}**{icono} — '
            f'🏅 **`{fmt_poder(s["aclamacion"])}`{_contra_meta(s["aclamacion"], g["aclamacion"])}** · '
            f'⚔️ `{fmt_poder(s["kill_points"])}`{_contra_meta(s["kill_points"], g["kp"])} · '
            f'💪 `{fmt_signo(s["poder_delta"])}`')


async def contenido_tablero(guild: discord.Guild) -> list[list[discord.Embed]]:
    """Mensajes del tablero (cada uno con sus embeds): todos los gobernadores del reino por aclamación del KvK."""
    from cogs.guerra import grupos_metas, leyenda_grupos, orden_aclamacion
    gid       = str(guild.id)
    temporada = await db.kvk_get_active(gid)
    stats     = await db.kvk_get_import_ranking(temporada['id']) if temporada else []
    titulo    = f'📊 Tablero del KvK / KvK board — {temporada["nombre"]}' if temporada else '📊 Tablero del KvK / KvK board'
    if not stats:
        return [[discord.Embed(
            title=titulo, color=0xFF4444,
            description=(f'_Todavía no hay datos de este KvK. El liderazgo los carga con `/kvk-actualizar` '
                         f'y luego se actualizan solos.\nNo data yet for this KvK._'),
        )]]

    grupos   = grupos_metas(temporada)
    # Leyenda: cada grupo con su rango de poder, sus metas, cuántos cumplen y sus objetivos
    cabecera = leyenda_grupos(temporada, stats) or [
        '_Sin metas todavía: el liderazgo las pone con 🎯 Metas en el panel de guerra._']
    if len(grupos) > 1:
        cabecera.append('_El animal junto a cada nombre es su grupo. / The animal next to each name is their group._')
    ts = await db.get_config(gid, 'kvk_datos_ts')
    if ts:
        cabecera.append(f'🕐 Actualizado / _Updated_ <t:{ts}:R> · HeroScroll · Reino {REINO}')

    ordenados = sorted(stats, key=orden_aclamacion, reverse=True)
    bloques, actual = [], '\n'.join(cabecera) + '\n\n'
    for pos, s in enumerate(ordenados, 1):
        linea = linea_tablero(pos, s, grupos)
        if len(actual) + len(linea) + 1 > MAX_DESCRIPCION:
            bloques.append(actual)
            actual = ''
        actual += linea + '\n'
    bloques.append(actual)

    embeds = []
    for n, bloque in enumerate(bloques, 1):
        t = titulo if len(bloques) == 1 else f'{titulo} ({n}/{len(bloques)})'
        embeds.append(discord.Embed(title=t[:256], description=bloque, color=0xFF4444))
    embeds[-1].set_footer(text=f'Ordenado por 🏅 aclamación (lo que más cuenta) · ⚔️ KP del KvK · '
                               f'💪 poder ganado/perdido · ✅ meta cumplida · Se actualiza solo · {ALIANZA_TAG}')

    # Cada mensaje admite 10 embeds y ~6000 caracteres en total
    mensajes, grupo, total = [], [], 0
    for e in embeds:
        if grupo and (len(grupo) == 10 or total + len(e) > 5800):
            mensajes.append(grupo)
            grupo, total = [], 0
        grupo.append(e)
        total += len(e)
    mensajes.append(grupo)
    return mensajes


async def refrescar_tablero(guild: discord.Guild):
    """Repinta el tablero fijo de #kvk-stats editando sus mensajes.

    Si cambia el número de mensajes o alguno se ha borrado, se vuelve a publicar entero para que siga en orden.
    """
    async with _lock_tablero:
        try:
            await _refrescar_tablero(guild)
        except discord.HTTPException as e:
            print(f'[kvk] No se pudo actualizar el tablero en {guild.name}: {e}')


async def _refrescar_tablero(guild: discord.Guild):
    from cogs.guerra import buscar_canal
    gid      = str(guild.id)
    mensajes = await contenido_tablero(guild)
    dato     = await db.get_config(gid, 'kvk_tablero')
    canal, ids = None, []
    if dato and ':' in dato:
        canal_id, lista = dato.split(':', 1)
        canal = guild.get_channel(int(canal_id))
        ids   = [int(x) for x in lista.split(',') if x]

    if canal and len(ids) == len(mensajes):
        try:
            for mensaje_id, embeds in zip(ids, mensajes):
                await canal.get_partial_message(mensaje_id).edit(embeds=embeds)
            return
        except discord.NotFound:
            pass  # alguien borró un trozo: se republica entero

    if canal:
        for mensaje_id in ids:
            try:
                await canal.get_partial_message(mensaje_id).delete()
            except discord.HTTPException:
                pass
    canal = canal or buscar_canal(guild, 'kvk-stats')
    if not canal:
        return
    nuevos = [await canal.send(embeds=embeds) for embeds in mensajes]
    await db.set_config(gid, 'kvk_tablero', f'{canal.id}:' + ','.join(str(m.id) for m in nuevos))
    try:
        await nuevos[0].pin()
    except discord.HTTPException:
        pass


def embed_importados(temporada, jugadores: list[dict], origen: str) -> discord.Embed:
    """Resumen con el top 5 por aclamación tras cargar datos (Excel o HeroScroll)."""
    from cogs.guerra import orden_aclamacion
    top5     = sorted(jugadores, key=orden_aclamacion, reverse=True)[:5]
    medallas = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
    embed = discord.Embed(
        title=f'✅ KvK importado — {temporada["nombre"]}',
        description=f'**{len(jugadores)}** jugadores cargados desde {origen}',
        color=0xFF4444,
    )
    lineas = []
    for i, j in enumerate(top5):
        lineas.append(
            f'{medallas[i]} **{j["governor_name"]}** — 🏅 **`{j["aclamacion"]:,}`** · '
            f'⚔️ KP `{j["kill_points"]:,}` · 💀 `{j["muertes"]:,}`'
        )
    embed.add_field(name='🏆 Top 5 por aclamación', value='\n'.join(lineas), inline=False)
    embed.set_footer(text='Usa /kvk-ranking para ver el ranking completo')
    return embed


def build_recap_embed(temporada, stats: list, guerra: list = (), guild: discord.Guild = None) -> discord.Embed:
    medallas = ['🥇', '🥈', '🥉']
    dkp_ranking = sorted(stats, key=lambda s: s['dkp'], reverse=True)

    total_t4  = sum(s['kills_t4']    for s in stats)
    total_t5  = sum(s['kills_t5']    for s in stats)
    total_kp  = sum(s['kill_points'] for s in stats)
    total_mts = sum(s['muertes']     for s in stats)

    embed = discord.Embed(
        title=f'🔥 Resumen de Temporada — {temporada["nombre"]}',
        description=(
            f'**{ALIANZA_FULL} · Reino {REINO}**\n'
            f'👥 **{len(stats)}** gobernadores participaron en este KvK'
        ),
        color=0xFF4444,
        timestamp=datetime.now(timezone.utc),
    )

    # Top 3 aclamación: lo que más cuenta del KvK, va primero
    from cogs.guerra import orden_aclamacion
    top_acl = [s for s in sorted(stats, key=orden_aclamacion, reverse=True)[:3] if s['aclamacion'] > 0]
    if top_acl:
        embed.add_field(
            name='⭐ 🏅 Top aclamación',
            value='\n'.join(f'{medallas[i]} **{s["governor_name"]}** — `{s["aclamacion"]:,}`'
                            for i, s in enumerate(top_acl)),
            inline=False,
        )

    # Top 3 kills
    lineas_kills = []
    for i, s in enumerate(stats[:3]):
        total = s['kills_t4'] + s['kills_t5']
        lineas_kills.append(
            f'{medallas[i]} **{s["governor_name"]}**\n'
            f'`T4: {s["kills_t4"]:,}  ·  T5: {s["kills_t5"]:,}  ·  Total: {total:,}`'
        )
    embed.add_field(name='⚔️ Top Kills', value='\n'.join(lineas_kills) or '—', inline=False)

    # Top 3 DKP
    top_dkp = [s for s in dkp_ranking[:3] if s['dkp'] > 0]
    if top_dkp:
        lineas_dkp = [
            f'{medallas[i]} **{s["governor_name"]}** — `{s["dkp"]:,}` DKP'
            for i, s in enumerate(top_dkp)
        ]
        embed.add_field(name='💰 Top DKP', value='\n'.join(lineas_dkp), inline=False)

    # Top 3 KP hechos en guerra (capturas)
    if guerra:
        from cogs.guerra import fmt
        lineas_guerra = [
            f'{medallas[i]} **{g["nombre"]}** — `+{fmt(g["ganados"])}` KP'
            for i, g in enumerate(guerra[:3])
        ]
        embed.add_field(name='🔥 Top KP en guerra', value='\n'.join(lineas_guerra), inline=False)

    # Metas del KvK, comprobadas con los datos de HeroScroll
    from cogs.guerra import lineas_cumplen
    cumplen = lineas_cumplen(temporada, stats)
    if cumplen:
        embed.add_field(name='🎯 Metas del KvK', value='\n'.join(cumplen), inline=False)

    # Estadísticas globales de la alianza
    embed.add_field(
        name='📊 La alianza en cifras',
        value=(
            f'⚔️ Kills T4 · **{total_t4:,}**\n'
            f'🏆 Kills T5 · **{total_t5:,}**\n'
            f'🎯 Kill Points · **{total_kp:,}**\n'
            f'💀 Muertes · **{total_mts:,}**'
        ),
        inline=True,
    )

    # MVP
    if stats:
        mvp = stats[0]
        mvp_total = mvp['kills_t4'] + mvp['kills_t5']
        embed.add_field(
            name='🏅 MVP del KvK',
            value=f'**{mvp["governor_name"]}**\n`{mvp_total:,}` kills totales',
            inline=True,
        )

    embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO} · Temporada cerrada')
    return embed


class Kvk(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_heroscroll.start()

    def cog_unload(self):
        self.auto_heroscroll.cancel()

    @app_commands.command(name='kvk-inicio', description='[ADMIN] Inicia una nueva temporada KvK y publica el anuncio')
    @app_commands.describe(
        nombre='Nombre de la temporada (ej: KvK Mayo 2026)',
        historia='Historia/temática elegida para este KvK',
        fecha_inicio='Fecha de inicio (dd/mm/aaaa)',
        fecha_fin='Fecha de fin (dd/mm/aaaa)',
        recuperacion='¿Es un KvK de recuperación?',
    )
    @app_commands.choices(recuperacion=[
        app_commands.Choice(name='✅ Sí, es de recuperación', value='si'),
        app_commands.Choice(name='❌ No, KvK normal', value='no'),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kvk_inicio(self, interaction: discord.Interaction, nombre: str, historia: str,
                         fecha_inicio: str, fecha_fin: str, recuperacion: str):
        try:
            d_inicio = datetime.strptime(fecha_inicio, '%d/%m/%Y')
            d_fin    = datetime.strptime(fecha_fin, '%d/%m/%Y')
        except ValueError:
            await interaction.response.send_message(
                '❌ Formato de fecha incorrecto. Usa `dd/mm/aaaa` (ej: 15/07/2026).',
                ephemeral=True,
            )
            return

        if await db.guerra_get_abierta(str(interaction.guild_id)):
            await interaction.response.send_message(
                '❌ Hay una guerra en curso. Termínala desde el panel de guerra antes de empezar otra temporada.',
                ephemeral=True,
            )
            return

        es_recuperacion = recuperacion == 'si'

        # Cerrar temporada anterior si existe (sin borrar sus datos históricos)
        await db.kvk_end_active(str(interaction.guild_id))
        temporada_id = await db.kvk_create(
            str(interaction.guild_id), nombre, historia, fecha_inicio, fecha_fin, es_recuperacion
        )
        refrescar_calendario(interaction.guild)

        tipo_kvk = '🔄 KvK de Recuperación' if es_recuperacion else '⚔️ KvK Principal'

        embed = discord.Embed(
            title=f'⚔️ ¡Nuevo KvK! — {nombre}',
            description=(
                f'**{ALIANZA_FULL} · Reino {REINO}**\n\n'
                f'¡Ha comenzado la preparación para un nuevo Kingdom vs Kingdom!'
            ),
            color=0xFF4444,
        )
        embed.add_field(name='📖 Historia', value=historia, inline=False)
        embed.add_field(name='🗂️ Tipo', value=tipo_kvk, inline=True)
        embed.add_field(name='📅 Inicio', value=d_inicio.strftime('%d/%m/%Y'), inline=True)
        embed.add_field(name='🏁 Fin', value=d_fin.strftime('%d/%m/%Y'), inline=True)
        embed.add_field(
            name='💪 Preparación',
            value=(
                'Revisad vuestras tropas, equipamiento y comandantes.\n'
                'Estad atentos a **🎙️│voz-guerra** y **💬│kvk-chat** para las órdenes del liderazgo.'
            ),
            inline=False,
        )
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO} · ID temporada #{temporada_id}')

        # Publicar en #anuncios y #kvk-anuncios
        canal_anuncios = next(
            (c for c in interaction.guild.text_channels
             if 'anuncios' in c.name and 'kvk' not in c.name and 'ark' not in c.name),
            None,
        )
        canal_kvk_anuncios = next(
            (c for c in interaction.guild.text_channels if 'kvk-anuncios' in c.name), None
        )

        publicados = []
        for canal in {canal_anuncios, canal_kvk_anuncios} - {None}:
            try:
                await canal.send(embed=embed)
                publicados.append(canal.mention)
            except discord.Forbidden:
                pass

        resumen = f'✅ **{nombre}** iniciado — ID `{temporada_id}`.'
        if publicados:
            resumen += f'\nAnuncio publicado en {", ".join(publicados)}.'
        else:
            resumen += '\n⚠️ No encontré los canales de anuncios para publicarlo automáticamente.'

        await interaction.response.send_message(resumen, ephemeral=True)

    @app_commands.command(name='kvk-fin', description='[ADMIN] Cierra la temporada KvK activa y publica el resumen')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kvk_fin(self, interaction: discord.Interaction):
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message('❌ No hay ninguna temporada activa.', ephemeral=True)
            return
        if await db.guerra_get_abierta(str(interaction.guild_id)):
            await interaction.response.send_message(
                '❌ Hay una guerra en curso. Termínala desde el panel de guerra antes de cerrar la temporada.',
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        stats  = await db.kvk_get_import_ranking(temporada['id'])
        guerra = await db.guerra_ranking_temporada(temporada['id'])
        await db.kvk_end_active(str(interaction.guild_id))
        refrescar_calendario(interaction.guild)
        from cogs.guerra import refrescar_panel
        await refrescar_panel(interaction.guild)

        await interaction.followup.send(f'✅ Temporada **{temporada["nombre"]}** cerrada.')

        if not stats and not guerra:
            return

        # Buscar canal de recap: primero config guardada, luego kvk-anuncios por nombre
        canal = None
        canal_id = await db.get_config(str(interaction.guild_id), 'kvk_canal_recap')
        if canal_id:
            canal = interaction.guild.get_channel(int(canal_id))
        if not canal:
            canal = next(
                (c for c in interaction.guild.text_channels if 'kvk-anuncios' in c.name),
                None,
            )
        if canal:
            await canal.send(embed=build_recap_embed(temporada, stats, guerra, interaction.guild))

    @app_commands.command(name='kvk-importar', description='[ADMIN] Importa estadísticas KvK desde el Excel de heroscroll.com')
    @app_commands.describe(archivo='Archivo .xlsx exportado de heroscroll.com/rok/kvk-dashboard')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kvk_importar(self, interaction: discord.Interaction, archivo: discord.Attachment):
        if not archivo.filename.endswith('.xlsx'):
            await interaction.response.send_message('❌ El archivo debe ser un `.xlsx`.', ephemeral=True)
            return

        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message(
                '❌ No hay temporada KvK activa. Usa `/kvk-inicio` primero.', ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            data      = await archivo.read()
            jugadores = parse_excel(data)
        except Exception as e:
            await interaction.followup.send(f'❌ Error leyendo el Excel: `{e}`', ephemeral=True)
            return

        if not jugadores:
            await interaction.followup.send('❌ No se encontraron jugadores en el archivo.', ephemeral=True)
            return

        await guardar_importados(str(interaction.guild_id), temporada['id'], jugadores)
        await interaction.followup.send(embed=embed_importados(temporada, jugadores, f'`{archivo.filename}`'))
        await refrescar_tablero(interaction.guild)

    @app_commands.command(name='kvk-actualizar',
                          description=f'[ADMIN] Carga las stats del reino {REINO} desde el enlace de HeroScroll (luego se actualiza solo)')
    @app_commands.describe(enlace='Enlace heroscroll.com/rok/kvk-dashboard?id=… (solo la primera vez o para cambiarlo)')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kvk_actualizar(self, interaction: discord.Interaction, enlace: str = None):
        gid       = str(interaction.guild_id)
        temporada = await db.kvk_get_active(gid)
        if not temporada:
            await interaction.response.send_message(
                '❌ No hay temporada KvK activa. Usa `/kvk-inicio` primero.', ephemeral=True)
            return
        if enlace:
            enlace = enlace.strip()
            if not ENLACE_HEROSCROLL.match(enlace):
                await interaction.response.send_message(
                    '❌ El enlace tiene que ser como `https://www.heroscroll.com/rok/kvk-dashboard?id=C13345`.',
                    ephemeral=True)
                return
        else:
            enlace = await enlace_heroscroll(gid, temporada['id'])
            if not enlace:
                await interaction.response.send_message(
                    '❌ Aún no tengo el enlace de este KvK. Pásamelo: `/kvk-actualizar enlace:https://www.heroscroll.com/…`',
                    ephemeral=True)
                return

        await interaction.response.defer()
        try:
            jugadores = await descargar_heroscroll(enlace)
        except (ValueError, aiohttp.ClientError, asyncio.TimeoutError) as e:
            await interaction.followup.send(f'❌ No he podido leer HeroScroll: {str(e) or "no responde"}.', ephemeral=True)
            return

        await db.set_config(gid, 'heroscroll_url', f'{temporada["id"]}|{enlace}')
        await guardar_importados(gid, temporada['id'], jugadores)
        embed = embed_importados(temporada, jugadores, f'[HeroScroll]({enlace}) · solo el reino {REINO}')
        embed.set_footer(text=f'Se actualiza solo cada {HORAS_AUTO} h mientras dure el KvK · '
                              'el tablero fijo de #kvk-stats también se actualiza')
        await interaction.followup.send(embed=embed)
        await refrescar_tablero(interaction.guild)

    # ── Actualización automática desde HeroScroll ──────────────────────────────

    @tasks.loop(hours=HORAS_AUTO)
    async def auto_heroscroll(self):
        for guild in self.bot.guilds:
            gid = str(guild.id)
            try:
                temporada = await db.kvk_get_active(gid)
                enlace    = await enlace_heroscroll(gid, temporada['id']) if temporada else None
                if not enlace:
                    continue
                jugadores = await descargar_heroscroll(enlace)
                await guardar_importados(gid, temporada['id'], jugadores)
                print(f'[kvk] HeroScroll: {len(jugadores)} gobernadores del {REINO} actualizados en {guild.name}')
                await refrescar_tablero(guild)
            except Exception as e:
                # Si HeroScroll falla se conservan los datos anteriores y se reintenta en la siguiente vuelta
                print(f'[kvk] No se pudo actualizar desde HeroScroll en {guild.name}: {type(e).__name__}: {e}')

    @auto_heroscroll.before_loop
    async def antes_auto_heroscroll(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name='kvk-ranking', description='[ADMIN] Muestra el ranking del KvK actual')
    @solo_en_canal('kvk')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kvk_ranking(self, interaction: discord.Interaction):
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message('❌ No hay ninguna temporada KvK activa.', ephemeral=True)
            return

        # Usar datos importados si existen, si no los manuales
        stats = await db.kvk_get_import_ranking(temporada['id'])
        fuente = '📊 heroscroll.com'

        if not stats:
            stats  = await db.kvk_get_ranking(temporada['id'])
            fuente = '✏️ Registros manuales'

        if not stats:
            await interaction.response.send_message(
                '❌ Sin datos. Usa `/kvk-importar` con el Excel de heroscroll.com.',
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        from cogs.guerra import (embeds_lista, enviar_embeds, cumple_kp, cumple_aclamacion, lineas_cumplen,
                                 grupos_metas, indice_grupo, icono_grupo, orden_aclamacion)
        from cogs.mge import fmt_poder

        # Los importados (HeroScroll/Excel) traen KP y aclamación: se ordena por aclamación, que es lo que más cuenta.
        # Los registros manuales antiguos no los traen y siguen ordenados por kills.
        con_metas = 'kill_points' in stats[0].keys()
        if con_metas:
            stats = sorted(stats, key=orden_aclamacion, reverse=True)
        grupos    = grupos_metas(temporada) if con_metas else []
        meta_kp   = any(g['kp'] for g in grupos)

        medallas = ['🥇', '🥈', '🥉']
        lineas = []
        for i, s in enumerate(stats):
            t4    = s['kills_t4']
            t5    = s['kills_t5']
            total = t4 + t5
            # Las filas de la BD no tienen .get(): los importados traen governor_name y los manuales username
            name  = s['governor_name'] if 'governor_name' in s.keys() else s['username']
            pos   = medallas[i] if i < 3 else f'**{i+1}.**'
            icono = f' {icono_grupo(grupos, indice_grupo(grupos, s))}' if len(grupos) > 1 else ''
            linea = f'{pos} **{name}**{icono} — '
            if con_metas:
                linea += (f'🏅 **`{fmt_poder(s["aclamacion"])}`**'
                          f'{"✅" if cumple_aclamacion(temporada, s, grupos) else ""} · '
                          f'KP `{fmt_poder(s["kill_points"])}`{"✅" if meta_kp and cumple_kp(temporada, s, grupos) else ""} · ')
            linea += f'T4: `{t4:,}` · T5: `{t5:,}` · Total: `{total:,}` · 💀 `{s["muertes"]:,}`'
            lineas.append(linea)

        # Todos los jugadores, repartidos en tantos embeds como haga falta
        embeds = embeds_lista(f'🏆 Ranking KvK — {temporada["nombre"]}', lineas, 0xFF4444, por_embed=20)
        if con_metas:
            cumplen = lineas_cumplen(temporada, stats)
            if cumplen:
                embeds[0].add_field(name='🎯 Metas del KvK', value='\n'.join(cumplen), inline=False)
        embeds[-1].set_footer(text=f'Fuente: {fuente} · {len(stats)} jugadores'
                                   + (' · ordenado por 🏅 aclamación (lo que más cuenta) · ✅ = meta cumplida'
                                      if con_metas else ''))
        await enviar_embeds(interaction.followup.send, embeds)

    @app_commands.command(name='kvk-buscar', description='Busca las stats de un gobernador por nombre')
    @solo_en_canal('kvk')
    @app_commands.describe(nombre='Nombre del gobernador (parcial también funciona)')
    async def kvk_buscar(self, interaction: discord.Interaction, nombre: str):
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message('❌ No hay temporada activa.', ephemeral=True)
            return

        stats = await db.kvk_get_import_ranking(temporada['id'])
        if not stats:
            await interaction.response.send_message('❌ No hay datos importados.', ephemeral=True)
            return

        encontrados = [
            s for s in stats
            if nombre.lower() in s['governor_name'].lower()
        ]

        if not encontrados:
            await interaction.response.send_message(
                f'❌ No encontré ningún gobernador con "{nombre}".', ephemeral=True
            )
            return

        from cogs.guerra import orden_aclamacion
        s = encontrados[0]
        total = s['kills_t4'] + s['kills_t5']
        # La posición es la del ranking por aclamación, el mismo orden que el tablero
        por_aclamacion = sorted(stats, key=orden_aclamacion, reverse=True)
        ranking_pos = next((i+1 for i, r in enumerate(por_aclamacion) if r['governor_id'] == s['governor_id']), '?')

        embed = discord.Embed(
            title=f'⚔️ Stats KvK — {s["governor_name"]}',
            color=0xFF4444,
        )
        embed.add_field(name='🏆 Posición',   value=f'#{ranking_pos} por aclamación', inline=True)
        embed.add_field(name='⭐ 🏅 Aclamación', value=f'**{s["aclamacion"]:,}**', inline=True)
        embed.add_field(name='T4 kills',      value=f'{s["kills_t4"]:,}', inline=True)
        embed.add_field(name='T5 kills',      value=f'{s["kills_t5"]:,}', inline=True)
        embed.add_field(name='Total kills',   value=f'{total:,}', inline=True)
        embed.add_field(name='💀 Muertes',    value=f'{s["muertes"]:,}', inline=True)
        embed.add_field(name='Kill Points',   value=f'{s["kill_points"]:,}', inline=True)
        embed.add_field(name='DKP',           value=f'{s["dkp"]:,}', inline=True)

        # Progreso hacia las metas de su grupo de poder (datos de HeroScroll)
        from cogs.mge import fmt_poder
        from cogs.guerra import grupos_metas, indice_grupo, etiqueta_grupo
        grupos   = grupos_metas(temporada)
        i        = indice_grupo(grupos, s)
        progreso = []
        if i is not None:
            if len(grupos) > 1:
                progreso.append(f'Grupo **{etiqueta_grupo(grupos, i)}** · poder al empezar el KvK: '
                                f'{fmt_poder(s["poder_inicio"])}')
            for icono, nombre_meta, hecho, meta in (('⭐ 🏅', 'Aclamación (la principal)', s['aclamacion'],
                                                      grupos[i]['aclamacion']),
                                                     ('⚔️', 'KP', s['kill_points'], grupos[i]['kp'])):
                if meta:
                    pct = min(100, round(hecho * 100 / meta))
                    progreso.append(f'{icono} {nombre_meta}: **{fmt_poder(hecho)}** / {fmt_poder(meta)} '
                                    f'({pct} %){" ✅" if hecho >= meta else ""}')
            if grupos[i]['objetivos']:
                progreso.append(f'📋 Objetivos de tu grupo / _Your group goals_: {grupos[i]["objetivos"]}')
        if progreso:
            embed.add_field(name='🎯 Metas del KvK', value='\n'.join(progreso), inline=False)
        embed.set_footer(text=f'Temporada: {temporada["nombre"]}')
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='kvk-reset', description='[ADMIN] Borra todos los datos del KvK actual y permite empezar de cero')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kvk_reset(self, interaction: discord.Interaction):
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message('❌ No hay ninguna temporada activa.', ephemeral=True)
            return

        # Confirmación con botones
        embed = discord.Embed(
            title='⚠️ ¿Confirmar reset del KvK?',
            description=(
                f'Vas a borrar **todos los datos** de la temporada:\n'
                f'**{temporada["nombre"]}**\n\n'
                f'Esto eliminará:\n'
                f'• Todos los datos importados del Excel\n'
                f'• Todos los registros manuales\n'
                f'• Las guerras cerradas y sus capturas de Kill Points\n\n'
                f'La temporada seguirá activa para que puedas volver a importar.'
            ),
            color=0xFF4444,
        )

        view = ConfirmResetView(temporada['id'], temporada['nombre'])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name='kvk-dkp', description='Ranking de DKP de la temporada actual')
    @solo_en_canal('kvk')
    async def kvk_dkp(self, interaction: discord.Interaction):
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message('❌ No hay temporada activa.', ephemeral=True)
            return

        stats = await db.kvk_get_import_ranking(temporada['id'])
        if not stats:
            await interaction.response.send_message('❌ No hay datos importados. Usa `/kvk-importar` primero.', ephemeral=True)
            return

        ranking = sorted((s for s in stats if s['dkp'] > 0), key=lambda s: s['dkp'], reverse=True)
        if not ranking:
            await interaction.response.send_message('❌ No hay datos de DKP en esta temporada.', ephemeral=True)
            return

        medallas = ['🥇', '🥈', '🥉']
        lineas = []
        for i, s in enumerate(ranking):
            pos   = medallas[i] if i < 3 else f'**{i+1}.**'
            total = s['kills_t4'] + s['kills_t5']
            lineas.append(
                f'{pos} **{s["governor_name"]}** — '
                f'`{s["dkp"]:,}` DKP · '
                f'Kills: `{total:,}` · 💀 `{s["muertes"]:,}`'
            )

        embed = discord.Embed(
            title=f'💰 Ranking DKP — {temporada["nombre"]}',
            description='\n'.join(lineas[:20]),
            color=0xFFD700,
        )
        embed.set_footer(text=f'{len(ranking)} gobernadores con DKP · {ALIANZA_TAG} · Reino {REINO}')
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='kvk-canal-recap', description='[ADMIN] Configura el canal donde se publica el resumen al cerrar el KvK')
    @app_commands.describe(canal='Canal donde se publicará el resumen de fin de temporada')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kvk_canal_recap(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await db.set_config(str(interaction.guild_id), 'kvk_canal_recap', str(canal.id))
        await interaction.response.send_message(
            f'✅ El resumen de fin de temporada se publicará en {canal.mention}.',
            ephemeral=True,
        )

    @kvk_inicio.error
    @kvk_fin.error
    @kvk_importar.error
    @kvk_actualizar.error
    @kvk_reset.error
    @kvk_ranking.error
    @kvk_canal_recap.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Kvk(bot))
