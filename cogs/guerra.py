"""Modo guerra del KvK contado con el CSV de ROKSTATS.

Un R4 activa la guerra subiendo el CSV de la alianza (foto inicial de los Kill Points).
Un R4 termina la guerra subiendo el CSV nuevo (foto final) → el bot publica la clasificación:
KP final − KP inicial de cada gobernador. Los jugadores no tienen que hacer nada.
"""
import csv
import io
import re
import time
import unicodedata
from datetime import datetime

import discord
from discord.ext import commands

from config import ALIANZA_TAG, REINO
from db import database as db
from cogs.registro import anotar
from cogs.mge import parse_poder, fmt_poder

ROLES_R4   = ('⚔️ R4', '👑 Liderazgo')
ROL_GUERRA = '⚔️ Guerra'

COLOR_INACTIVA = 0x95A5A6
COLOR_ACTIVA   = 0x2ECC71
COLOR_GUERRA   = 0xE74C3C

MEDALLAS = ['🥇', '🥈', '🥉']
DONDE_CSV = 'ROKSTATS → tu alianza → pestaña Analytics → exportar CSV'


# ── Utilidades ─────────────────────────────────────────────────────────────────

def fmt(n: int) -> str:
    return f'{n:,}'.replace(',', '.')


def es_r4(member: discord.Member) -> bool:
    if member.guild_permissions.manage_guild:
        return True
    return any(r.name in ROLES_R4 for r in member.roles)


def buscar_canal(guild: discord.Guild, nombre: str):
    exacto = next((c for c in guild.text_channels if c.name.split('│')[-1] == nombre), None)
    return exacto or next((c for c in guild.text_channels if nombre in c.name), None)


def embeds_lista(titulo: str, lineas: list[str], color: int, por_embed: int = 30) -> list[discord.Embed]:
    bloques = [lineas[i:i + por_embed] for i in range(0, len(lineas), por_embed)] or [[]]
    embeds = []
    for n, bloque in enumerate(bloques, 1):
        t = titulo if len(bloques) == 1 else f'{titulo} ({n}/{len(bloques)})'
        embeds.append(discord.Embed(title=t[:256], description='\n'.join(bloque) or '—', color=color))
    return embeds


async def enviar_embeds(enviar, embeds: list[discord.Embed], **kwargs):
    """Envía los embeds en tantos mensajes como haga falta (máx. 10 y ~6000 caracteres por mensaje)."""
    grupo, total = [], 0
    for e in embeds:
        if grupo and (len(grupo) == 10 or total + len(e) > 5800):
            await enviar(embeds=grupo, **kwargs)
            grupo, total = [], 0
        grupo.append(e)
        total += len(e)
    if grupo:
        await enviar(embeds=grupo, **kwargs)


def texto_objetivos(temporada) -> str:
    """Metas por jugador y objetivos del KvK, para el panel, el calendario y los anuncios ('' si no hay)."""
    lineas = []
    if temporada['meta_kp']:
        lineas.append(f'⚔️ Meta de KP / _KP target_: **{fmt_poder(temporada["meta_kp"])}** por jugador / _per player_')
    if temporada['meta_aclamacion']:
        lineas.append(f'🏅 Meta de aclamación / _Acclaim target_: **{fmt_poder(temporada["meta_aclamacion"])}** '
                      'por jugador / _per player_')
    if temporada['objetivos']:
        lineas.append(f'📋 {temporada["objetivos"]}')
    return '\n'.join(lineas)


async def anunciar(guild: discord.Guild, embed: discord.Embed):
    canal = buscar_canal(guild, 'kvk-chat') or buscar_canal(guild, 'kvk-anuncios')
    if not canal:
        return
    rol = discord.utils.get(guild.roles, name=ROL_GUERRA)
    try:
        await canal.send(content=rol.mention if rol else None, embed=embed,
                         allowed_mentions=discord.AllowedMentions(roles=True))
    except discord.HTTPException as e:
        print(f'[guerra] No se pudo anunciar en {canal.name}: {e}')


# ── Lectura del CSV de ROKSTATS ────────────────────────────────────────────────

class CsvInvalido(ValueError):
    pass


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return ' '.join(sin_tildes.lower().split())


def _columna(cabeceras: list[str], *opciones) -> int | None:
    norm = [_normalizar(c) for c in cabeceras]
    for opcion in opciones:
        for i, c in enumerate(norm):
            if c == opcion:
                return i
    return None


def _numero(texto: str) -> int:
    digitos = re.sub(r'\D', '', texto or '')
    return int(digitos) if digitos else 0


def fecha_exportacion(nombre_archivo: str) -> datetime | None:
    """ROKSTATS pone la hora de exportación en el nombre: ..._analytics_2026-10-20_07-53-58.csv"""
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})[_ T](\d{2})-(\d{2})-(\d{2})', nombre_archivo or '')
    return datetime(*map(int, m.groups())) if m else None


def leer_csv(datos: bytes) -> list[dict]:
    """Devuelve [{governor_id, nombre, kp, poder}] a partir del CSV de analytics de la alianza."""
    try:
        texto = datos.decode('utf-8-sig')
    except UnicodeDecodeError:
        texto = datos.decode('latin-1')
    if not texto.strip():
        raise CsvInvalido('el archivo está vacío')
    try:
        dialecto = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=',;\t')
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.reader(io.StringIO(texto), dialecto))
    cabeceras = filas[0]

    col_id     = _columna(cabeceras, 'id del jugador', 'id del gobernador', 'player id', 'governor id', 'id')
    col_nombre = _columna(cabeceras, 'nombre', 'name', 'governor', 'gobernador')
    col_kp     = _columna(cabeceras, 'puntos de muerte', 'kill points', 'killpoints', 'kp')
    col_poder  = _columna(cabeceras, 'poder', 'power')
    faltan = [n for n, c in (('ID del jugador', col_id), ('Nombre', col_nombre), ('Puntos de muerte', col_kp))
              if c is None]
    if faltan:
        raise CsvInvalido(f'no encuentro las columnas: {", ".join(faltan)}')

    jugadores = {}
    for fila in filas[1:]:
        if len(fila) <= max(col_id, col_nombre, col_kp):
            continue
        gov_id = re.sub(r'\D', '', fila[col_id])
        if not gov_id:
            continue
        jugadores[gov_id] = {
            'governor_id': gov_id,
            'nombre':      fila[col_nombre].strip() or gov_id,
            'kp':          _numero(fila[col_kp]),
            'poder':       _numero(fila[col_poder]) if col_poder is not None and col_poder < len(fila) else 0,
        }
    if not jugadores:
        raise CsvInvalido('no hay ningún jugador en el archivo')
    return list(jugadores.values())


async def leer_adjunto(adjunto: discord.Attachment | None) -> list[dict]:
    if not adjunto:
        raise CsvInvalido('no has adjuntado ningún archivo')
    if not adjunto.filename.lower().endswith('.csv'):
        raise CsvInvalido(f'`{adjunto.filename}` no es un .csv')
    return leer_csv(await adjunto.read())


def txt_exportado(nombre_archivo: str) -> str:
    fecha = fecha_exportacion(nombre_archivo)
    return fecha.strftime('%d/%m/%Y %H:%M') if fecha else nombre_archivo


# ── Panel fijo (#kvk-stats) ────────────────────────────────────────────────────

COMO_FUNCIONA = (
    f'1️⃣ Un R4 activa la guerra subiendo el CSV de la alianza ({DONDE_CSV}).\n'
    '2️⃣ Al terminar, un R4 sube el CSV nuevo.\n'
    '3️⃣ El bot publica la clasificación: **KP hechos entre los dos CSV**. ¡No tenéis que hacer nada!\n'
    '_1️⃣ An R4 starts the war uploading the alliance CSV from ROKSTATS. '
    '2️⃣ When it ends, an R4 uploads the new CSV. '
    '3️⃣ The bot posts the ranking: **KP made between both CSVs**. You don\'t need to do anything!_'
)


async def contenido_panel(guild: discord.Guild):
    gid       = str(guild.id)
    guerra    = await db.guerra_get_abierta(gid)
    temporada = await db.kvk_get_active(gid)

    if not guerra:
        color = COLOR_INACTIVA
        texto = ('🔴 **Sin guerra activa.** / _No active war._')
    else:
        color = COLOR_ACTIVA
        num   = await db.guerra_numero(guerra)
        n     = await db.guerra_contar_datos(guerra['id'], 'inicial')
        texto = (f'🟢 **GUERRA #{num} ACTIVA** desde <t:{guerra["inicio_ts"]}:t> (<t:{guerra["inicio_ts"]}:R>)\n'
                 f'_War #{num} in progress._\n\n'
                 f'📄 CSV inicial: **{n}** gobernadores · exportado {txt_exportado(guerra["csv_inicial"])}')

    embed = discord.Embed(title='⚔️ Modo guerra · Kill Points / War mode', description=texto, color=color)
    if temporada:
        embed.add_field(
            name='🎯 Objetivos del KvK / KvK goals',
            value=(texto_objetivos(temporada) or '_El liderazgo aún no ha fijado metas. / No goals set yet._')[:1024],
            inline=False,
        )
    embed.add_field(name='❓ Cómo funciona / How it works', value=COMO_FUNCIONA, inline=False)
    pie = f'Temporada: {temporada["nombre"]}' if temporada else 'Sin temporada KvK activa'
    embed.set_footer(text=f'{pie} · {ALIANZA_TAG} · Reino {REINO}')
    return embed, PanelGuerraView('activa' if guerra else None)


async def publicar_panel(canal: discord.TextChannel) -> discord.Message:
    embed, view = await contenido_panel(canal.guild)
    msg = await canal.send(embed=embed, view=view)
    await db.set_config(str(canal.guild.id), 'guerra_panel', f'{canal.id}:{msg.id}')
    return msg


async def refrescar_panel(guild: discord.Guild, crear: bool = True):
    """Actualiza el panel; si se ha borrado, lo vuelve a publicar en #kvk-stats."""
    embed, view = await contenido_panel(guild)
    dato = await db.get_config(str(guild.id), 'guerra_panel')
    if dato:
        canal_id, msg_id = dato.split(':')
        canal = guild.get_channel(int(canal_id))
        if canal:
            try:
                await canal.get_partial_message(int(msg_id)).edit(embed=embed, view=view)
                return
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                print(f'[guerra] No se pudo actualizar el panel: {e}')
                return
    canal = buscar_canal(guild, 'kvk-stats') if crear else None
    if canal:
        try:
            msg = await publicar_panel(canal)
            await msg.pin()
        except discord.HTTPException as e:
            print(f'[guerra] No se pudo publicar el panel: {e}')


class PanelGuerraView(discord.ui.View):
    """Botones del panel. Con estado='todos' se registra la vista persistente con todos los botones."""

    VISIBLES = {
        None:     {'activar', 'ranking', 'metas'},
        'activa': {'terminar', 'cancelar', 'ranking', 'metas'},
    }

    def __init__(self, estado='todos'):
        super().__init__(timeout=None)
        if estado == 'todos':
            return
        for item in list(self.children):
            if item.custom_id.split(':')[1] not in self.VISIBLES[estado]:
                self.remove_item(item)

    @staticmethod
    async def _solo_r4(interaction: discord.Interaction) -> bool:
        if es_r4(interaction.user):
            return True
        await interaction.response.send_message('❌ Solo un R4 puede hacer esto. / R4 only.', ephemeral=True)
        return False

    @discord.ui.button(label='Activar guerra / Start war', emoji='🟢', style=discord.ButtonStyle.success,
                       custom_id='guerra:activar')
    async def activar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._solo_r4(interaction):
            return
        gid = str(interaction.guild_id)
        if not await db.kvk_get_active(gid):
            await interaction.response.send_message(
                '❌ No hay temporada KvK activa. Créala primero con `/kvk-inicio`.', ephemeral=True)
            return
        if await db.guerra_get_abierta(gid):
            await interaction.response.send_message('ℹ️ Ya hay una guerra en curso.', ephemeral=True)
            return
        await interaction.response.send_modal(CsvModal('activar'))

    @discord.ui.button(label='Terminar guerra / End war', emoji='🔴', style=discord.ButtonStyle.danger,
                       custom_id='guerra:terminar')
    async def terminar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._solo_r4(interaction):
            return
        if not await db.guerra_get_abierta(str(interaction.guild_id)):
            await interaction.response.send_message('ℹ️ No hay ninguna guerra activa.', ephemeral=True)
            return
        await interaction.response.send_modal(CsvModal('terminar'))

    @discord.ui.button(label='Anular', emoji='🗑️', style=discord.ButtonStyle.secondary, custom_id='guerra:cancelar')
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._solo_r4(interaction):
            return
        guerra = await db.guerra_get_abierta(str(interaction.guild_id))
        if not guerra:
            await interaction.response.send_message('ℹ️ No hay ninguna guerra activa.', ephemeral=True)
            return
        await interaction.response.send_message(
            '⚠️ ¿Anular la guerra en curso? **No contará nada** y se borrará el CSV inicial. '
            'Úsalo si se activó por error o con un CSV equivocado.',
            view=AnularView(guerra['id']), ephemeral=True,
        )

    @discord.ui.button(label='Ranking', emoji='🏆', style=discord.ButtonStyle.secondary, custom_id='guerra:ranking')
    async def ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message('❌ No hay temporada KvK activa.', ephemeral=True)
            return
        filas = await db.guerra_ranking_temporada(temporada['id'])
        if not filas:
            await interaction.response.send_message(
                '📋 Todavía no hay KP de guerra esta temporada. / _No war KP yet this season._', ephemeral=True)
            return
        meta = temporada['meta_kp']
        lineas = []
        for i, f in enumerate(filas):
            pos   = MEDALLAS[i] if i < 3 else f'**{i + 1}.**'
            marca = ' ✅' if meta and f['ganados'] >= meta else ''
            lineas.append(f'{pos} **{f["nombre"]}** — `+{fmt(f["ganados"])}` KP · {f["guerras"]} ⚔️{marca}')
        embeds = embeds_lista(f'🏆 Bajas en guerra — {temporada["nombre"]}', lineas, COLOR_GUERRA)
        if meta:
            cumplen = sum(1 for f in filas if f['ganados'] >= meta)
            embeds[0].add_field(name='🎯 Meta de KP / KP target',
                                value=f'**{fmt_poder(meta)}** · ✅ la cumplen **{cumplen}** de {len(filas)}',
                                inline=False)
        embeds[-1].set_footer(text=f'KP hechos solo durante las guerras · ⚔️ = guerras en las que sumó'
                                   f'{" · ✅ = meta de KP cumplida" if meta else ""} · {ALIANZA_TAG}')
        await interaction.response.defer(ephemeral=True)
        await enviar_embeds(interaction.followup.send, embeds, ephemeral=True)

    @discord.ui.button(label='Metas', emoji='🎯', style=discord.ButtonStyle.primary, custom_id='guerra:metas')
    async def metas(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._solo_r4(interaction):
            return
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message(
                '❌ No hay temporada KvK activa. Créala primero con `/kvk-inicio`.', ephemeral=True)
            return
        await interaction.response.send_modal(MetasModal(temporada))


class AnularView(discord.ui.View):
    def __init__(self, guerra_id: int):
        super().__init__(timeout=60)
        self.guerra_id = guerra_id

    @discord.ui.button(label='Sí, anular', emoji='🗑️', style=discord.ButtonStyle.danger)
    async def si(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        guerra = await db.guerra_get(self.guerra_id)
        if not guerra or not await db.guerra_cancelar(self.guerra_id):
            await interaction.response.edit_message(content='ℹ️ Esa guerra ya no está activa.', view=None)
            return
        await interaction.response.edit_message(content='🗑️ Guerra anulada.', view=None)
        await refrescar_panel(interaction.guild)
        from cogs.kvk import refrescar_calendario
        refrescar_calendario(interaction.guild)
        anotar(interaction.guild, interaction.user, '⚔️ Guerra', '🗑️ anuló la guerra en curso (no cuenta)')

    @discord.ui.button(label='No', emoji='✖️', style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content='Cancelado.', view=None)


class CsvModal(discord.ui.Modal):
    def __init__(self, accion: str):
        super().__init__(title='🟢 Activar guerra · CSV inicial' if accion == 'activar' else '🔴 Terminar guerra · CSV final')
        self.accion  = accion
        self.archivo = discord.ui.FileUpload(required=True, min_values=1, max_values=1)
        self.add_item(discord.ui.Label(
            text='CSV de ROKSTATS',
            description='Descárgalo justo ahora: alianza → Analytics → exportar CSV',
            component=self.archivo,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        adjunto = self.archivo.values[0] if self.archivo.values else None
        try:
            filas = await leer_adjunto(adjunto)
        except CsvInvalido as e:
            await interaction.response.send_message(f'❌ CSV no válido: {e}.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if self.accion == 'activar':
            texto = await activar_guerra(interaction.guild, interaction.user, adjunto.filename, filas)
        else:
            texto = await terminar_guerra(interaction.guild, interaction.user, adjunto.filename, filas)
        await interaction.followup.send(texto, ephemeral=True)


class MetasModal(discord.ui.Modal):
    """Metas de KP y aclamación por jugador y objetivos del KvK; viene relleno con lo actual para editarlo."""

    def __init__(self, temporada):
        super().__init__(title='🎯 Metas y objetivos del KvK')
        self.temporada_id = temporada['id']
        self.meta_kp = discord.ui.TextInput(
            placeholder='Ej: 300M · vacío = sin meta', max_length=20, required=False,
            default=fmt_poder(temporada['meta_kp']) if temporada['meta_kp'] else None,
        )
        self.meta_aclamacion = discord.ui.TextInput(
            placeholder='Ej: 25000 o 25K · vacío = sin meta', max_length=20, required=False,
            default=fmt_poder(temporada['meta_aclamacion']) if temporada['meta_aclamacion'] else None,
        )
        self.objetivos = discord.ui.TextInput(
            placeholder='Ej: Tomar el paso 6 el viernes. Nadie se queda sin tropas en el hospital.',
            style=discord.TextStyle.paragraph, max_length=800, required=False,
            default=temporada['objetivos'] or None,
        )
        self.anunciar = discord.ui.Select(options=[
            discord.SelectOption(label='No, solo actualizar el panel', value='no', emoji='🔕', default=True),
            discord.SelectOption(label='Sí, anunciarlo en kvk-anuncios', value='si', emoji='📢'),
        ])
        self.add_item(discord.ui.Label(text='Meta de KP por jugador',
                                       description='El ✅ del ranking se mide con los KP hechos en las guerras',
                                       component=self.meta_kp))
        self.add_item(discord.ui.Label(text='Meta de aclamación por jugador', component=self.meta_aclamacion))
        self.add_item(discord.ui.Label(text='Objetivos (opcional)', description='Lo que la alianza quiere conseguir',
                                       component=self.objetivos))
        self.add_item(discord.ui.Label(text='¿Avisar a la alianza?', component=self.anunciar))

    async def on_submit(self, interaction: discord.Interaction):
        metas = {}
        for nombre, campo in (('KP', self.meta_kp), ('aclamación', self.meta_aclamacion)):
            texto = campo.value.strip()
            valor = parse_poder(texto) if texto else 0
            if valor < 0:
                await interaction.response.send_message(
                    f'❌ Meta de {nombre} incorrecta. Usa `300M`, `25K` o `300000000` (o déjalo vacío).', ephemeral=True)
                return
            metas[nombre] = valor
        objetivos = self.objetivos.value.strip()

        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        await db.kvk_set_metas(self.temporada_id, metas['KP'], metas['aclamación'], objetivos)
        temporada = await db.kvk_get_active(str(guild.id))
        await refrescar_panel(guild)
        from cogs.kvk import refrescar_calendario
        refrescar_calendario(guild)
        anotar(guild, interaction.user, '🎯 Metas KvK',
               f'KP {fmt_poder(metas["KP"]) if metas["KP"] else "—"} · '
               f'aclamación {fmt_poder(metas["aclamación"]) if metas["aclamación"] else "—"}'
               + (f' · objetivos: {objetivos}' if objetivos else ''))

        respuesta = '✅ Metas guardadas. El panel y el calendario ya las muestran.'
        if self.anunciar.values and self.anunciar.values[0] == 'si' and temporada:
            canal = buscar_canal(guild, 'kvk-anuncios') or buscar_canal(guild, 'kvk-chat')
            embed = discord.Embed(
                title=f'🎯 Objetivos del KvK / KvK goals — {temporada["nombre"]}',
                description=texto_objetivos(temporada) or '_Sin metas por ahora. / No goals for now._',
                color=COLOR_GUERRA,
            )
            embed.set_footer(text=f'Los KP de las guerras se cuentan solos con ROKSTATS · {ALIANZA_TAG} · Reino {REINO}')
            if not canal:
                respuesta += '\n⚠️ No encontré #kvk-anuncios; no se ha anunciado.'
            else:
                try:
                    await canal.send(embed=embed)
                    respuesta += f'\n📢 Anunciado en {canal.mention}.'
                except discord.HTTPException as e:
                    print(f'[guerra] No se pudieron anunciar las metas en {canal.name}: {e}')
                    respuesta += f'\n⚠️ No he podido escribir en {canal.mention}.'
        await interaction.followup.send(respuesta, ephemeral=True)


# ── Cambios de estado ──────────────────────────────────────────────────────────

async def activar_guerra(guild: discord.Guild, user: discord.Member, archivo: str, filas: list[dict]) -> str:
    gid = str(guild.id)
    temporada = await db.kvk_get_active(gid)
    if not temporada:
        return '❌ No hay temporada KvK activa.'
    if await db.guerra_get_abierta(gid):
        return 'ℹ️ Ya hay una guerra en curso.'
    guerra_id = await db.guerra_crear(gid, temporada['id'], str(user.id), int(time.time()), archivo, filas)
    num = await db.guerra_numero(await db.guerra_get(guerra_id))
    await refrescar_panel(guild)
    from cogs.kvk import refrescar_calendario
    refrescar_calendario(guild)

    embed = discord.Embed(
        title=f'🟢 ¡Guerra #{num} activada! / War #{num} started!',
        description=(
            'A partir de ahora cuentan los Kill Points que hagáis. Los datos salen de ROKSTATS: '
            '**no tenéis que subir nada**. ¡A por ellos! 🔥\n'
            '_Kill Points count from now on. Data comes from ROKSTATS: **you don\'t need to upload anything**._'
        ),
        color=COLOR_ACTIVA,
    )
    embed.set_footer(text=f'Activada por {user.display_name} · {len(filas)} gobernadores · {ALIANZA_TAG}')
    await anunciar(guild, embed)
    anotar(guild, user, '⚔️ Guerra',
           f'🟢 activó la guerra #{num} ({temporada["nombre"]}) con {archivo} ({len(filas)} gobernadores)')
    return (f'✅ Guerra #{num} activada con **{len(filas)}** gobernadores '
            f'(CSV exportado {txt_exportado(archivo)}).\n'
            'Cuando termine, pulsa 🔴 **Terminar guerra** y sube el CSV nuevo.')


async def terminar_guerra(guild: discord.Guild, user: discord.Member, archivo: str, filas: list[dict]) -> str:
    guerra = await db.guerra_get_abierta(str(guild.id))
    if not guerra:
        return 'ℹ️ No hay ninguna guerra activa.'

    f_ini, f_fin = fecha_exportacion(guerra['csv_inicial']), fecha_exportacion(archivo)
    if f_ini and f_fin and f_fin <= f_ini:
        return (f'❌ Este CSV se exportó el {txt_exportado(archivo)}, no después del inicial '
                f'({txt_exportado(guerra["csv_inicial"])}). Descarga uno nuevo de ROKSTATS.')

    inicial = await db.guerra_get_datos(guerra['id'], 'inicial')
    comunes = [f for f in filas if f['governor_id'] in inicial]
    if not comunes:
        return '❌ Ningún gobernador de este CSV estaba en el inicial. ¿Es de otra alianza?'
    if not any(f['kp'] > inicial[f['governor_id']] for f in comunes):
        return ('❌ Nadie tiene más Kill Points que en el CSV inicial. Seguramente ROKSTATS aún no se ha '
                'actualizado: espera un poco, vuelve a descargar el CSV y pulsa 🔴 otra vez. La guerra sigue activa.')

    if not await db.guerra_cerrar(guerra['id'], str(user.id), int(time.time()), archivo, filas):
        return 'ℹ️ La guerra ya estaba cerrada.'
    await refrescar_panel(guild)
    from cogs.kvk import refrescar_calendario
    refrescar_calendario(guild)

    num = await db.guerra_numero(guerra)
    anotar(guild, user, '⚔️ Guerra', f'🔴 terminó la guerra #{num} con {archivo}')
    enlace = await publicar_resultados(guild, await db.guerra_get(guerra['id']), num)
    return f'✅ Guerra #{num} cerrada.' + (f' Ranking publicado: {enlace}' if enlace else '')


async def publicar_resultados(guild: discord.Guild, guerra, num: int) -> str | None:
    filas    = await db.guerra_resultados(guerra['id'])
    con_kp   = [f for f in filas if f['ganados'] > 0]
    sin_kp   = len(filas) - len(con_kp)
    total    = sum(f['ganados'] for f in con_kp)
    duracion = max(1, round((guerra['fin_ts'] - guerra['inicio_ts']) / 60))

    lineas = []
    for i, f in enumerate(con_kp):
        pos = MEDALLAS[i] if i < 3 else f'**{i + 1}.**'
        lineas.append(f'{pos} **{f["nombre"]}** — `+{fmt(f["ganados"])}` KP')
    embeds = embeds_lista(f'🏆 Bajas de la guerra #{num} / War #{num} kills', lineas, COLOR_GUERRA)
    embeds[0].add_field(
        name='📊 Resumen / Summary',
        value=(f'👥 Con KP / _With KP_: **{len(con_kp)}** · sin KP / _without_: {sin_kp}\n'
               f'🔥 KP de la alianza / _Alliance KP_: **{fmt(total)}**\n'
               f'⏱️ Duración / _Duration_: **{duracion} min**\n'
               f'📄 CSV: {txt_exportado(guerra["csv_inicial"])} → {txt_exportado(guerra["csv_final"])}'),
        inline=False,
    )
    embeds[-1].set_footer(text=f'Datos de ROKSTATS · KP final − KP inicial · {ALIANZA_TAG} · Reino {REINO}')

    canal = buscar_canal(guild, 'kvk-stats') or buscar_canal(guild, 'kvk-chat')
    if not canal:
        return None
    mensajes = []

    async def enviar(**kwargs):
        mensajes.append(await canal.send(**kwargs))

    try:
        await enviar_embeds(enviar, embeds)
    except discord.HTTPException as e:
        print(f'[guerra] No se pudo publicar el ranking: {e}')
        return None

    chat = buscar_canal(guild, 'kvk-chat')
    if chat and chat != canal:
        top = ' · '.join(f'{MEDALLAS[i]} {f["nombre"]} `+{fmt(f["ganados"])}`' for i, f in enumerate(con_kp[:3]))
        try:
            await chat.send(f'🏁 **Guerra #{num} terminada** / _War #{num} over_ — {top}\n'
                            f'📊 Ranking completo / _Full ranking_: {mensajes[0].jump_url}')
        except discord.HTTPException:
            pass
    return mensajes[0].jump_url


# ── Cog ────────────────────────────────────────────────────────────────────────

class Guerra(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(PanelGuerraView())

    @commands.Cog.listener()
    async def on_ready(self):
        # Asegura que el panel existe y refleja el estado actual
        for guild in self.bot.guilds:
            try:
                await refrescar_panel(guild)
            except Exception as e:
                print(f'[guerra] Error refrescando el panel en {guild.name}: {e}')


async def setup(bot: commands.Bot):
    await bot.add_cog(Guerra(bot))
