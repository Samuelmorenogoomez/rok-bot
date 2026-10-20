"""Modo guerra del KvK con capturas de Kill Points.

Un R4 activa la guerra → cada jugador sube la captura de su perfil con sus KP (inicial).
Un R4 termina la guerra → hay MINUTOS_CIERRE minutos para subir la captura final.
Al acabar el plazo el bot cierra la guerra y publica la clasificación: KP final − KP inicial.
"""
import asyncio
import re
import time
from pathlib import Path

import discord
from discord.ext import commands, tasks

from config import ALIANZA_TAG, REINO
from db import database as db
from cogs.registro import anotar, overwrites_logs

MINUTOS_CIERRE  = 20
ROLES_R4        = ('⚔️ R4', '👑 Liderazgo')
ROL_GUERRA      = '⚔️ Guerra'
CANAL_REVISION  = '📸│kvk-capturas'
CATEGORIA_ADMIN = '👑 ADMINISTRACIÓN'

COLOR_INACTIVA = 0x95A5A6
COLOR_ACTIVA   = 0x2ECC71
COLOR_CIERRE   = 0xF39C12
COLOR_GUERRA   = 0xE74C3C

MEDALLAS = ['🥇', '🥈', '🥉']
NOMBRE_FASE = {'inicial': 'inicial / start', 'final': 'final / end'}


# ── Utilidades ─────────────────────────────────────────────────────────────────

def fmt(n: int) -> str:
    return f'{n:,}'.replace(',', '.')


def es_r4(member: discord.Member) -> bool:
    if member.guild_permissions.manage_guild:
        return True
    return any(r.name in ROLES_R4 for r in member.roles)


def leer_kp(texto: str) -> int | None:
    """Acepta 10.400.500, 10,400,500, 10 400 500 o 10400500."""
    digitos = re.sub(r'\D', '', texto or '')
    if not digitos or len(digitos) > 12:
        return None
    valor = int(digitos)
    return valor if valor > 0 else None


def buscar_canal(guild: discord.Guild, nombre: str):
    exacto = next((c for c in guild.text_channels if c.name.split('│')[-1] == nombre), None)
    return exacto or next((c for c in guild.text_channels if nombre in c.name), None)


def nombre_jugador(guild: discord.Guild, fila) -> str:
    if fila['gobernador']:
        return fila['gobernador']
    miembro = guild.get_member(int(fila['user_id']))
    return miembro.display_name if miembro else f'<@{fila["user_id"]}>'


def ganados(fila) -> int:
    return max(0, fila['kp_final'] - fila['kp_inicial'])


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


async def canal_revision(guild: discord.Guild):
    """Canal privado del liderazgo donde llegan las capturas (se crea si no existe)."""
    canal = buscar_canal(guild, 'kvk-capturas')
    if canal:
        return canal
    try:
        categoria = discord.utils.get(guild.categories, name=CATEGORIA_ADMIN)
        return await guild.create_text_channel(
            CANAL_REVISION, category=categoria, overwrites=overwrites_logs(guild),
            topic='Capturas de Kill Points de las guerras del KvK. Un R4 puede corregir el número con ✏️.',
        )
    except discord.HTTPException as e:
        print(f'[guerra] No se pudo crear el canal de capturas: {e}')
        return None


async def anunciar(guild: discord.Guild, embed: discord.Embed, view: discord.ui.View | None = None):
    canal = buscar_canal(guild, 'kvk-chat') or buscar_canal(guild, 'kvk-anuncios')
    if not canal:
        return
    rol = discord.utils.get(guild.roles, name=ROL_GUERRA)
    try:
        await canal.send(
            content=rol.mention if rol else None, embed=embed, view=view,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
    except discord.HTTPException as e:
        print(f'[guerra] No se pudo anunciar en {canal.name}: {e}')


# ── Panel fijo (#kvk-stats) ────────────────────────────────────────────────────

COMO_FUNCIONA = (
    '1️⃣ Un R4 activa la guerra → pulsa 📸 y sube la captura de tu perfil con tus **Kill Points**.\n'
    f'2️⃣ Un R4 termina la guerra → tienes **{MINUTOS_CIERRE} min** para subir la captura final.\n'
    '3️⃣ Solo cuentan los KP hechos **entre las dos capturas**.\n'
    '_1️⃣ An R4 starts the war → press 📸 and upload your profile screenshot with your **Kill Points**._\n'
    f'_2️⃣ An R4 ends the war → you have **{MINUTOS_CIERRE} min** to upload the final screenshot._\n'
    '_3️⃣ Only KP made **between both screenshots** count._'
)


async def contenido_panel(guild: discord.Guild):
    gid       = str(guild.id)
    guerra    = await db.guerra_get_abierta(gid)
    temporada = await db.kvk_get_active(gid)
    estado    = guerra['estado'] if guerra else None

    if not guerra:
        color = COLOR_INACTIVA
        texto = ('🔴 **Sin guerra activa.** Cuando un R4 la active podréis subir la captura inicial.\n'
                 '_No active war. When an R4 starts it you can upload your start screenshot._')
    elif estado == 'activa':
        color = COLOR_ACTIVA
        n     = await db.guerra_contar_capturas(guerra['id'], 'inicial')
        num   = await db.guerra_numero(guerra)
        texto = (f'🟢 **GUERRA #{num} ACTIVA** desde <t:{guerra["inicio_ts"]}:t> (<t:{guerra["inicio_ts"]}:R>)\n'
                 f'Pulsa 📸 y sube tu **captura inicial**. / _Press 📸 and upload your **start screenshot**._\n\n'
                 f'📸 Capturas iniciales / _Start screenshots_: **{n}**')
    else:
        color = COLOR_CIERRE
        ini   = await db.guerra_contar_capturas(guerra['id'], 'inicial')
        fin   = await db.guerra_contar_capturas(guerra['id'], 'final')
        num   = await db.guerra_numero(guerra)
        texto = (f'⏳ **GUERRA #{num} TERMINADA** — sube tu **captura final** antes de '
                 f'<t:{guerra["limite_ts"]}:t> (<t:{guerra["limite_ts"]}:R>)\n'
                 f'_War over — upload your **final screenshot** before the deadline._\n\n'
                 f'📸 Capturas finales / _Final screenshots_: **{fin}/{ini}**')

    embed = discord.Embed(title='⚔️ Modo guerra · Kill Points / War mode', description=texto, color=color)
    embed.add_field(name='❓ Cómo funciona / How it works', value=COMO_FUNCIONA, inline=False)
    pie = f'Temporada: {temporada["nombre"]}' if temporada else 'Sin temporada KvK activa'
    embed.set_footer(text=f'{pie} · {ALIANZA_TAG} · Reino {REINO}')
    return embed, PanelGuerraView(estado)


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


_refrescos: dict[int, asyncio.Task] = {}


def refrescar_panel_luego(guild: discord.Guild, segundos: float = 3):
    """Agrupa varias actualizaciones seguidas (muchas capturas a la vez) en una sola edición."""
    if guild.id in _refrescos and not _refrescos[guild.id].done():
        return

    async def _tarea():
        await asyncio.sleep(segundos)
        await refrescar_panel(guild)

    _refrescos[guild.id] = asyncio.create_task(_tarea())


class PanelGuerraView(discord.ui.View):
    """Botones del panel. Con estado='todos' se registra la vista persistente con todos los botones."""

    VISIBLES = {
        None:     {'activar', 'ranking'},
        'activa': {'captura', 'mia', 'ranking', 'terminar'},
        'cierre': {'captura', 'mia', 'ranking'},
    }

    def __init__(self, estado='todos', con_admin: bool = True):
        super().__init__(timeout=None)
        if estado == 'todos':
            return
        visibles = set(self.VISIBLES[estado])
        if not con_admin:
            visibles -= {'activar', 'terminar'}
        for item in list(self.children):
            if item.custom_id.split(':')[1] not in visibles:
                self.remove_item(item)
        self.captura.label = ('Subir captura inicial / Upload start' if estado == 'activa'
                              else 'Subir captura final / Upload final')

    @discord.ui.button(label='Activar guerra / Start war', emoji='🟢', style=discord.ButtonStyle.success,
                       custom_id='guerra:activar')
    async def activar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_r4(interaction.user):
            await interaction.response.send_message('❌ Solo un R4 puede activar la guerra. / R4 only.', ephemeral=True)
            return
        gid = str(interaction.guild_id)
        if not await db.kvk_get_active(gid):
            await interaction.response.send_message(
                '❌ No hay temporada KvK activa. Créala primero con `/kvk-inicio`.', ephemeral=True)
            return
        if await db.guerra_get_abierta(gid):
            await interaction.response.send_message('ℹ️ Ya hay una guerra en curso.', ephemeral=True)
            return
        await interaction.response.send_message(
            '⚠️ ¿Activar la guerra **ahora**? Se avisará al rol ⚔️ Guerra para que suban la captura inicial.',
            view=ConfirmarView('activar'), ephemeral=True,
        )

    @discord.ui.button(label='Subir captura / Upload screenshot', emoji='📸', style=discord.ButtonStyle.primary,
                       custom_id='guerra:captura')
    async def captura(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid, uid = str(interaction.guild_id), str(interaction.user.id)
        guerra = await db.guerra_get_abierta(gid)
        if not guerra:
            await interaction.response.send_message(
                '🔴 No hay ninguna guerra activa. / _No active war._', ephemeral=True)
            return
        if not await db.get_member(gid, uid):
            canal = buscar_canal(interaction.guild, 'miembros')
            donde = canal.mention if canal else 'el canal de miembros'
            await interaction.response.send_message(
                f'❌ Tienes que estar registrado. Pulsa 📝 **Registrarme** en {donde}.\n'
                f'_You must be registered. Press 📝 **Register** in {donde}._', ephemeral=True)
            return
        if guerra['estado'] == 'activa':
            fase = 'inicial'
        else:
            if not await db.captura_get(guerra['id'], uid, 'inicial'):
                await interaction.response.send_message(
                    '❌ No subiste la captura inicial cuando se activó la guerra, así que no puedes participar en esta.\n'
                    "_You didn't upload a start screenshot, so you can't take part in this war._", ephemeral=True)
                return
            fase = 'final'
        await interaction.response.send_modal(CapturaModal(guerra['id'], fase))

    @discord.ui.button(label='Mis capturas / My screenshots', emoji='👤', style=discord.ButtonStyle.secondary,
                       custom_id='guerra:mia')
    async def mia(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid, uid = str(interaction.guild_id), str(interaction.user.id)
        guerra = await db.guerra_get_abierta(gid)
        if not guerra:
            await interaction.response.send_message('🔴 No hay ninguna guerra activa.', ephemeral=True)
            return
        ini = await db.captura_get(guerra['id'], uid, 'inicial')
        fin = await db.captura_get(guerra['id'], uid, 'final')
        lineas = [
            f'📸 Inicial / _Start_: **{fmt(ini["kp"])}** KP' if ini else '📸 Inicial / _Start_: ❌ sin subir / _missing_',
            f'📸 Final: **{fmt(fin["kp"])}** KP' if fin else '📸 Final: — ',
        ]
        if ini and fin:
            lineas.append(f'🔥 Hechos en esta guerra / _Made this war_: **+{fmt(max(0, fin["kp"] - ini["kp"]))}** KP')
        await interaction.response.send_message('\n'.join(lineas), ephemeral=True)

    @discord.ui.button(label='Ranking', emoji='🏆', style=discord.ButtonStyle.secondary, custom_id='guerra:ranking')
    async def ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        temporada = await db.kvk_get_active(str(interaction.guild_id))
        if not temporada:
            await interaction.response.send_message('❌ No hay temporada KvK activa.', ephemeral=True)
            return
        filas = await db.guerra_ranking_temporada(temporada['id'])
        if not filas:
            await interaction.response.send_message(
                '📋 Todavía no hay guerras cerradas esta temporada. / _No finished wars yet this season._',
                ephemeral=True)
            return
        lineas = []
        for i, f in enumerate(filas):
            pos = MEDALLAS[i] if i < 3 else f'**{i + 1}.**'
            lineas.append(f'{pos} **{nombre_jugador(interaction.guild, f)}** — '
                          f'`+{fmt(f["ganados"])}` KP · {f["guerras"]} ⚔️')
        embeds = embeds_lista(f'🏆 Bajas en guerra — {temporada["nombre"]}', lineas, COLOR_GUERRA)
        embeds[-1].set_footer(text=f'KP hechos solo durante las guerras · ⚔️ = guerras con las dos capturas · {ALIANZA_TAG}')
        await interaction.response.defer(ephemeral=True)
        await enviar_embeds(interaction.followup.send, embeds, ephemeral=True)

    @discord.ui.button(label='Terminar guerra / End war', emoji='🔴', style=discord.ButtonStyle.danger,
                       custom_id='guerra:terminar')
    async def terminar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_r4(interaction.user):
            await interaction.response.send_message('❌ Solo un R4 puede terminar la guerra. / R4 only.', ephemeral=True)
            return
        guerra = await db.guerra_get_abierta(str(interaction.guild_id))
        if not guerra or guerra['estado'] != 'activa':
            await interaction.response.send_message('ℹ️ No hay ninguna guerra activa que terminar.', ephemeral=True)
            return
        await interaction.response.send_message(
            f'⚠️ ¿Terminar la guerra **ahora**? Empezarán los **{MINUTOS_CIERRE} minutos** para subir la captura final.',
            view=ConfirmarView('terminar'), ephemeral=True,
        )


class ConfirmarView(discord.ui.View):
    def __init__(self, accion: str):
        super().__init__(timeout=60)
        self.accion = accion

    @discord.ui.button(label='Sí', emoji='✅', style=discord.ButtonStyle.success)
    async def si(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content='⏳ …', view=None)
        if self.accion == 'activar':
            texto = await activar_guerra(interaction.guild, interaction.user)
        else:
            texto = await terminar_guerra(interaction.guild, interaction.user)
        await interaction.edit_original_response(content=texto)

    @discord.ui.button(label='Cancelar', emoji='✖️', style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content='Cancelado.', view=None)


# ── Cambios de estado ──────────────────────────────────────────────────────────

async def activar_guerra(guild: discord.Guild, user: discord.Member) -> str:
    gid = str(guild.id)
    temporada = await db.kvk_get_active(gid)
    if not temporada:
        return '❌ No hay temporada KvK activa.'
    if await db.guerra_get_abierta(gid):
        return 'ℹ️ Ya hay una guerra en curso.'
    guerra_id = await db.guerra_crear(gid, temporada['id'], str(user.id), int(time.time()))
    guerra    = await db.guerra_get(guerra_id)
    num       = await db.guerra_numero(guerra)
    await refrescar_panel(guild)
    from cogs.kvk import refrescar_calendario
    refrescar_calendario(guild)

    embed = discord.Embed(
        title=f'🟢 ¡Guerra #{num} activada! / War #{num} started!',
        description=(
            'Pulsa 📸 y sube **ya** la captura de tu perfil donde se vean tus **Kill Points**.\n'
            'Solo contarán los KP que hagas a partir de ahora.\n'
            '_Press 📸 and upload **now** your profile screenshot showing your **Kill Points**. '
            'Only KP made from now on will count._'
        ),
        color=COLOR_ACTIVA,
    )
    embed.set_footer(text=f'Activada por {user.display_name} · {ALIANZA_TAG}')
    await anunciar(guild, embed, PanelGuerraView('activa', con_admin=False))
    anotar(guild, user, '⚔️ Guerra', f'🟢 activó la guerra #{num} ({temporada["nombre"]})')
    return f'✅ Guerra #{num} activada y anunciada.'


async def terminar_guerra(guild: discord.Guild, user: discord.Member) -> str:
    guerra = await db.guerra_get_abierta(str(guild.id))
    if not guerra or guerra['estado'] != 'activa':
        return 'ℹ️ No hay ninguna guerra activa que terminar.'
    ahora  = int(time.time())
    limite = ahora + MINUTOS_CIERRE * 60
    if not await db.guerra_iniciar_cierre(guerra['id'], str(user.id), ahora, limite):
        return 'ℹ️ La guerra ya se estaba terminando.'
    num = await db.guerra_numero(guerra)
    await refrescar_panel(guild)

    embed = discord.Embed(
        title=f'⏳ ¡Guerra #{num} terminada! / War #{num} is over!',
        description=(
            f'Tenéis **{MINUTOS_CIERRE} minutos** (hasta <t:{limite}:t>, <t:{limite}:R>) para pulsar 📸 '
            'y subir la **captura final** con vuestros Kill Points.\n'
            'Quien no la suba no sumará KP en esta guerra.\n'
            f'_You have **{MINUTOS_CIERRE} minutes** to press 📸 and upload your **final screenshot**. '
            'No final screenshot = no KP for this war._'
        ),
        color=COLOR_CIERRE,
    )
    embed.set_footer(text=f'Terminada por {user.display_name} · {ALIANZA_TAG}')
    await anunciar(guild, embed, PanelGuerraView('cierre', con_admin=False))
    anotar(guild, user, '⚔️ Guerra', f'🔴 terminó la guerra #{num}; plazo de captura final hasta <t:{limite}:t>')
    return f'✅ Guerra #{num} terminada. El bot la cerrará y publicará el ranking en {MINUTOS_CIERRE} min.'


async def cerrar_guerra(guild: discord.Guild, guerra):
    """Fin del plazo de capturas finales: cierra la guerra y publica la clasificación."""
    if not await db.guerra_cerrar(guerra['id']):
        return
    await refrescar_panel(guild)
    from cogs.kvk import refrescar_calendario
    refrescar_calendario(guild)

    num       = await db.guerra_numero(guerra)
    filas     = await db.guerra_resultados(guerra['id'])
    con_final = sorted((f for f in filas if f['kp_final'] is not None), key=ganados, reverse=True)
    sin_final = [f for f in filas if f['kp_final'] is None]
    titulo    = f'🏆 Bajas de la guerra #{num} / War #{num} kills'

    lineas = []
    for i, f in enumerate(con_final):
        pos = MEDALLAS[i] if i < 3 else f'**{i + 1}.**'
        lineas.append(f'{pos} **{nombre_jugador(guild, f)}** — `+{fmt(ganados(f))}` KP')
    embeds = embeds_lista(titulo, lineas or ['_Nadie subió las dos capturas. / Nobody uploaded both screenshots._'],
                          COLOR_GUERRA)

    total    = sum(ganados(f) for f in con_final)
    duracion = max(1, round((guerra['fin_ts'] - guerra['inicio_ts']) / 60))
    embeds[0].add_field(
        name='📊 Resumen / Summary',
        value=(f'👥 Participantes / _Players_: **{len(con_final)}**\n'
               f'🔥 KP de la alianza / _Alliance KP_: **{fmt(total)}**\n'
               f'⏱️ Duración / _Duration_: **{duracion} min**'),
        inline=False,
    )
    if sin_final:
        nombres = ', '.join(nombre_jugador(guild, f) for f in sin_final)
        embeds[-1].add_field(name='⚠️ Sin captura final (0 KP) / No final screenshot',
                             value=nombres[:1024], inline=False)
    embeds[-1].set_footer(text=f'Solo cuentan los KP hechos entre las dos capturas · {ALIANZA_TAG} · Reino {REINO}')

    canal = buscar_canal(guild, 'kvk-stats') or buscar_canal(guild, 'kvk-chat')
    if not canal:
        return
    primero = None

    async def enviar(**kwargs):
        nonlocal primero
        msg = await canal.send(**kwargs)
        primero = primero or msg

    try:
        await enviar_embeds(enviar, embeds)
    except discord.HTTPException as e:
        print(f'[guerra] No se pudo publicar el ranking: {e}')
        return

    chat = buscar_canal(guild, 'kvk-chat')
    if chat and chat != canal and primero:
        top = ' · '.join(f'{MEDALLAS[i]} {nombre_jugador(guild, f)} `+{fmt(ganados(f))}`'
                         for i, f in enumerate(con_final[:3]))
        try:
            await chat.send(f'🏁 **Guerra #{num} cerrada** / _War #{num} closed_ — {top or "sin participantes"}\n'
                            f'📊 Ranking completo / _Full ranking_: {primero.jump_url}')
        except discord.HTTPException:
            pass


# ── Subida de capturas ─────────────────────────────────────────────────────────

class CapturaModal(discord.ui.Modal):
    def __init__(self, guerra_id: int, fase: str):
        titulo = '📸 Captura inicial / Start screenshot' if fase == 'inicial' else '📸 Captura final / Final screenshot'
        super().__init__(title=titulo)
        self.guerra_id = guerra_id
        self.fase      = fase
        self.kp     = discord.ui.TextInput(placeholder='Ej: 10.400.000', max_length=20)
        self.imagen = discord.ui.FileUpload(required=True, min_values=1, max_values=1)
        self.add_item(discord.ui.Label(text='Kill Points de tu perfil / Your Kill Points', component=self.kp))
        self.add_item(discord.ui.Label(text='Captura del perfil / Profile screenshot',
                                       description='Que se vean bien los Kill Points / Kill Points must be visible',
                                       component=self.imagen))

    async def on_submit(self, interaction: discord.Interaction):
        await guardar_captura(interaction, self.guerra_id, self.fase, self.kp.value, self.imagen.values)


async def guardar_captura(interaction: discord.Interaction, guerra_id: int, fase: str, texto_kp: str, adjuntos):
    guild = interaction.guild
    gid, uid = str(guild.id), str(interaction.user.id)

    async def error(msg: str):
        await interaction.response.send_message(msg, ephemeral=True)

    guerra = await db.guerra_get(guerra_id)
    estado_ok = 'activa' if fase == 'inicial' else 'cierre'
    if not guerra or guerra['estado'] != estado_ok:
        await error('⌛ Ya no se puede subir esta captura: la guerra ha cambiado de fase. / _Too late for this screenshot._')
        return
    kp = leer_kp(texto_kp)
    if kp is None:
        await error(f'❌ `{texto_kp}` no es un número de Kill Points válido. Ej: `10.400.000`.')
        return
    adjunto = adjuntos[0] if adjuntos else None
    if not adjunto or not (adjunto.content_type or '').startswith('image/'):
        await error('❌ El archivo tiene que ser una imagen (captura de pantalla). / _The file must be an image._')
        return

    inicial = None
    if fase == 'inicial':
        previo = await db.captura_max_kp_previo(gid, uid, guerra_id)
        if kp < previo:
            await error(f'❌ Tus KP no pueden ser menos que en tu última captura (**{fmt(previo)}**). '
                        '¿Es una captura antigua?\n_Your KP cannot be lower than in your last screenshot._')
            return
    else:
        inicial = await db.captura_get(guerra_id, uid, 'inicial')
        if kp < inicial['kp']:
            await error(f'❌ Los KP finales (**{fmt(kp)}**) no pueden ser menos que los iniciales '
                        f'(**{fmt(inicial["kp"])}**). Revisa el número.\n_Final KP cannot be lower than start KP._')
            return

    await interaction.response.defer(ephemeral=True, thinking=True)
    anterior = await db.captura_get(guerra_id, uid, fase)
    miembro  = await db.get_member(gid, uid)
    num      = await db.guerra_numero(guerra)

    url, rev_canal, rev_msg = adjunto.url, '', ''
    canal = await canal_revision(guild)
    if canal:
        try:
            ext     = Path(adjunto.filename).suffix or '.png'
            archivo = await adjunto.to_file(filename=f'captura_{uid}_{fase}{ext}')
            embed   = embed_revision(interaction.user, miembro['gobernador'], num, fase, kp, inicial)
            embed.set_image(url=f'attachment://{archivo.filename}')
            msg = await canal.send(embed=embed, file=archivo, view=RevisionView())
            url, rev_canal, rev_msg = msg.jump_url, str(canal.id), str(msg.id)
        except discord.HTTPException as e:
            print(f'[guerra] No se pudo enviar la captura a revisión: {e}')

    await db.captura_guardar(guerra_id, gid, uid, fase, kp, url, rev_canal, rev_msg, int(time.time()))

    if anterior and anterior['revision_msg'] and anterior['revision_canal']:
        viejo_canal = guild.get_channel(int(anterior['revision_canal']))
        if viejo_canal:
            try:
                viejo = await viejo_canal.fetch_message(int(anterior['revision_msg']))
                e = viejo.embeds[0] if viejo.embeds else discord.Embed()
                e.title = f'♻️ SUSTITUIDA — {e.title or ""}'[:256]
                e.color = COLOR_INACTIVA
                await viejo.edit(embed=e, view=None)
            except discord.HTTPException:
                pass

    refrescar_panel_luego(guild)
    if fase == 'inicial':
        texto = (f'✅ Captura inicial guardada: **{fmt(kp)}** KP.\n'
                 '¡A por ellos! Cuando un R4 termine la guerra, sube aquí la captura final.\n'
                 f'_Start screenshot saved. Upload the final one when an R4 ends the war._')
    else:
        texto = (f'✅ Captura final guardada: **{fmt(kp)}** KP.\n'
                 f'🔥 Has hecho **+{fmt(kp - inicial["kp"])}** KP en esta guerra. / _You made this war._')
    if anterior:
        texto += '\n♻️ Sustituye a la que habías subido antes. / _Replaces your previous one._'
    await interaction.followup.send(texto, ephemeral=True)


def embed_revision(user: discord.abc.User, gobernador: str, num: int, fase: str, kp: int, inicial=None) -> discord.Embed:
    embed = discord.Embed(
        title=f'📸 Guerra #{num} · captura {NOMBRE_FASE[fase]}',
        color=COLOR_ACTIVA if fase == 'inicial' else COLOR_CIERRE,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name='Jugador', value=f'{user.mention}\n{gobernador}', inline=True)
    embed.add_field(name='Kill Points', value=f'**{fmt(kp)}**', inline=True)
    if inicial:
        embed.add_field(name='Inicial', value=fmt(inicial['kp']), inline=True)
        embed.add_field(name='Hechos', value=f'+{fmt(max(0, kp - inicial["kp"]))}', inline=True)
    embed.set_footer(text='Comprueba que el número coincide con la captura · ✏️ para corregir')
    return embed


# ── Revisión por el liderazgo ──────────────────────────────────────────────────

class RevisionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Corregir KP', emoji='✏️', style=discord.ButtonStyle.secondary, custom_id='guerra:corregir')
    async def corregir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_r4(interaction.user):
            await interaction.response.send_message('❌ Solo un R4 puede corregir capturas.', ephemeral=True)
            return
        captura = await db.captura_get_por_revision(str(interaction.message.id))
        if not captura:
            await interaction.response.send_message('ℹ️ Esta captura ya no existe o fue sustituida.', ephemeral=True)
            return
        await interaction.response.send_modal(CorregirModal(captura))


class CorregirModal(discord.ui.Modal, title='✏️ Corregir Kill Points'):
    def __init__(self, captura):
        super().__init__()
        self.captura = captura
        self.kp = discord.ui.TextInput(default=str(captura['kp']), max_length=20)
        self.add_item(discord.ui.Label(text='Kill Points correctos', component=self.kp))

    async def on_submit(self, interaction: discord.Interaction):
        c  = self.captura
        kp = leer_kp(self.kp.value)
        if kp is None:
            await interaction.response.send_message(f'❌ `{self.kp.value}` no es un número válido.', ephemeral=True)
            return
        await db.captura_corregir(c['guerra_id'], c['user_id'], c['fase'], kp, str(interaction.user.id))

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        embed.set_field_at(1, name='Kill Points', value=f'**{fmt(kp)}**', inline=True)
        if c['fase'] == 'final' and len(embed.fields) >= 4:
            ini = await db.captura_get(c['guerra_id'], c['user_id'], 'inicial')
            if ini:
                embed.set_field_at(2, name='Inicial', value=fmt(ini['kp']), inline=True)
                embed.set_field_at(3, name='Hechos', value=f'+{fmt(max(0, kp - ini["kp"]))}', inline=True)
        nota = f'{fmt(c["kp"])} → **{fmt(kp)}** por {interaction.user.mention}'
        idx = next((i for i, f in enumerate(embed.fields) if f.name == '✏️ Corregido'), None)
        if idx is None:
            embed.add_field(name='✏️ Corregido', value=nota, inline=False)
        else:
            embed.set_field_at(idx, name='✏️ Corregido', value=nota, inline=False)
        await interaction.response.edit_message(embed=embed)

        guerra = await db.guerra_get(c['guerra_id'])
        anotar(interaction.guild, interaction.user, '⚔️ Guerra',
               f'✏️ corrigió la captura {c["fase"]} de <@{c["user_id"]}>: {fmt(c["kp"])} → {fmt(kp)}')
        if guerra and guerra['estado'] == 'cerrada':
            await interaction.followup.send(
                'ℹ️ Esa guerra ya estaba cerrada: el ranking de temporada (🏆) ya tiene el valor corregido, '
                'pero el mensaje de resultados publicado no cambia.', ephemeral=True)


# ── Cog ────────────────────────────────────────────────────────────────────────

class Guerra(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(PanelGuerraView())
        self.bot.add_view(RevisionView())
        self.cierre_automatico.start()

    async def cog_unload(self):
        self.cierre_automatico.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # Asegura que el panel existe y refleja el estado (por si el bot estuvo caído durante un cambio)
        for guild in self.bot.guilds:
            try:
                await refrescar_panel(guild)
            except Exception as e:
                print(f'[guerra] Error refrescando el panel en {guild.name}: {e}')

    @tasks.loop(seconds=30)
    async def cierre_automatico(self):
        for guerra in await db.guerra_pendientes_cierre(int(time.time())):
            guild = self.bot.get_guild(int(guerra['guild_id']))
            if not guild:
                continue
            try:
                await cerrar_guerra(guild, guerra)
            except Exception as e:
                print(f'[guerra] Error cerrando la guerra {guerra["id"]}: {type(e).__name__}: {e}')

    @cierre_automatico.before_loop
    async def antes_cierre(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Guerra(bot))
