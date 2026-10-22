"""Registro de acciones de admin.

Cada acción se guarda primero en la base de datos (solo se añade, nunca se borra) y luego se publica
en el canal 📋│logs-bot, que solo puede leer el liderazgo y donde nadie puede escribir.
Si alguien borra un registro o el canal entero, el bot lo restaura y apunta quién lo hizo.
"""
import asyncio
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import COLOR_BOT, ALIANZA_TAG
from db import database as db

CANAL_NOMBRE   = '📋│logs-bot'
RETENCION_DIAS = 3   # lo más antiguo se borra solo para que no se llene
CATEGORIA_ADMIN = '👑 ADMINISTRACIÓN'

# Comandos de admin que no se registran al usarlos: los de solo consulta (para no llenar el canal de ruido)
# y los que solo abren un formulario o una confirmación (se registra el resultado real, no la apertura)
SOLO_LECTURA = {'log', 'panel', 'ausentes', 'ver-canales', 'resumen-miembros', 'sin-registrar', 'reclu-pendientes',
                'limpiar-canal', 'mge-crear', 'setup-servidor'}

_lock   = asyncio.Lock()   # mantiene el orden de los registros
_tareas: set = set()


def es_comando_admin(command) -> bool:
    return bool(command) and (getattr(command, 'description', '') or '').startswith('[ADMIN]')


def overwrites_logs(guild: discord.Guild) -> dict:
    """Solo lectura para el liderazgo; nadie escribe salvo el bot."""
    ow = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    for nombre in ('👑 Liderazgo', '⚔️ R4'):
        rol = discord.utils.get(guild.roles, name=nombre)
        if rol:
            ow[rol] = discord.PermissionOverwrite(
                view_channel=True, read_message_history=True, send_messages=False,
                add_reactions=False, manage_messages=False, create_public_threads=False,
            )
    ow[guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                               read_message_history=True, embed_links=True)
    return ow


async def canal_logs(guild: discord.Guild, crear: bool = True):
    canal_id = await db.get_config(str(guild.id), 'logs_canal')
    canal    = guild.get_channel(int(canal_id)) if canal_id else None
    if not canal:
        canal = next((c for c in guild.text_channels if c.name.split('│')[-1] == 'logs-bot'), None)
    if not canal and crear:
        categoria = discord.utils.get(guild.categories, name=CATEGORIA_ADMIN)
        canal = await guild.create_text_channel(
            CANAL_NOMBRE, category=categoria, overwrites=overwrites_logs(guild),
            topic=f'Registro de acciones de admin de los últimos {RETENCION_DIAS} días (lo anterior se borra solo). '
                  'Si alguien borra algo, el bot lo restaura. Consulta con /log.',
        )
    if canal and str(canal.id) != canal_id:
        await db.set_config(str(guild.id), 'logs_canal', str(canal.id))
    return canal


def formatear(reg) -> str:
    texto = f'🕐 <t:{reg["ts"]}:f> · <@{reg["user_id"]}> ({reg["user_name"]}) · **{reg["accion"]}**'
    if reg['detalle']:
        texto += f' — {reg["detalle"]}'
    return texto[:1990]


async def _publicar(canal: discord.TextChannel, reg, prefijo: str = ''):
    msg = await canal.send(prefijo + formatear(reg), allowed_mentions=discord.AllowedMentions.none())
    await db.log_set_mensaje(reg['id'], str(msg.id))


async def _anotar(guild: discord.Guild, user_id: str, user_name: str, accion: str, detalle: str):
    detalle = ' · '.join(linea.strip() for linea in str(detalle).splitlines() if linea.strip())[:1500]
    async with _lock:
        try:
            ts     = int(time.time())
            reg_id = await db.log_insertar(str(guild.id), user_id, user_name, accion, detalle, ts)
        except Exception as e:
            print(f'[registro] No se pudo guardar en BD: {type(e).__name__}: {e}')
            return
        try:
            canal = await canal_logs(guild)
            if canal:
                reg = {'id': reg_id, 'ts': ts, 'user_id': user_id, 'user_name': user_name,
                       'accion': accion, 'detalle': detalle}
                await _publicar(canal, reg)
        except Exception as e:
            print(f'[registro] Guardado en BD pero no publicado en Discord: {type(e).__name__}: {e}')


def anotar(guild: discord.Guild, user, accion: str, detalle: str = ''):
    """Registra una acción de admin sin hacer esperar a quien la hizo."""
    if guild is None:
        return
    user_id   = str(user.id) if user else '0'
    user_name = getattr(user, 'display_name', None) or getattr(user, 'name', None) or 'desconocido'
    tarea = asyncio.create_task(_anotar(guild, user_id, user_name, accion, detalle))
    _tareas.add(tarea)
    tarea.add_done_callback(_tareas.discard)


def registrar_error(interaction: discord.Interaction, error: Exception):
    """Llamado desde el gestor de errores global: intentos sin permiso y fallos de comandos de admin."""
    comando = interaction.command
    if not es_comando_admin(comando):
        return
    if isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
        anotar(interaction.guild, interaction.user, f'⛔ /{comando.qualified_name}', 'intento sin permisos')
    else:
        original = getattr(error, 'original', error)
        anotar(interaction.guild, interaction.user, f'❌ /{comando.qualified_name}',
               f'{type(original).__name__}: {original}')


def detalle_parametros(interaction: discord.Interaction) -> str:
    partes = []
    for nombre, valor in interaction.namespace:
        if valor is None or valor == '':
            continue
        texto = getattr(valor, 'mention', None) or str(getattr(valor, 'name', valor) if hasattr(valor, 'filename') else valor)
        partes.append(f'{nombre}: {texto}')
    return ' · '.join(partes)


async def quien_borro(guild: discord.Guild, accion: discord.AuditLogAction, canal_id: int = None):
    """Busca en el registro de auditoría de Discord quién acaba de borrar algo."""
    await asyncio.sleep(2)  # el registro de auditoría tarda un momento en aparecer
    try:
        ahora = datetime.now(timezone.utc)
        async for entrada in guild.audit_logs(limit=10, action=accion):
            if (ahora - entrada.created_at).total_seconds() > 120:
                continue
            canal = getattr(entrada.extra, 'channel', None)
            if canal_id and canal is not None and canal.id != canal_id:
                continue
            if accion == discord.AuditLogAction.channel_delete and entrada.target and entrada.target.id != canal_id:
                continue
            return entrada.user
    except (discord.Forbidden, discord.HTTPException):
        pass
    return None


async def purgar_antiguos(guild: discord.Guild, antes_ts: int) -> int:
    """Borra de la BD y del canal los registros anteriores a antes_ts.

    Primero se borran de la BD: así, cuando desaparece el mensaje, el vigilante de borrados
    ya no lo encuentra y no lo restaura.
    """
    async with _lock:
        mensajes = await db.log_purgar_antiguos(str(guild.id), antes_ts)
    canal = await canal_logs(guild, crear=False)
    if not canal:
        return 0
    ids = set(mensajes)
    # También los avisos del bot (canal recreado, etc.) que no tienen registro propio
    async for m in canal.history(limit=None, before=datetime.fromtimestamp(antes_ts, timezone.utc)):
        if m.author == guild.me:
            ids.add(str(m.id))
    borrados = 0
    for mensaje_id in ids:
        try:
            await canal.get_partial_message(int(mensaje_id)).delete()
            borrados += 1
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            print(f'[registro] No se pudo borrar el mensaje {mensaje_id}: {e}')
        await asyncio.sleep(0.5)
    return borrados


# Canales donde el bot publica o edita cosas que la gente usa
CANALES_CLAVE = ('mge', 'calendario', 'miembros', 'anuncios', 'kvk-anuncios', 'bienvenida', 'reclutamiento', 'logs-bot')
PERMISOS_NECESARIOS = {
    'view_channel': 'Ver canal', 'send_messages': 'Enviar mensajes',
    'embed_links': 'Insertar enlaces', 'read_message_history': 'Leer historial',
}


async def revisar_permisos(guild: discord.Guild):
    """Al arrancar: si al bot le falta algún permiso en sus canales, se apunta en el log."""
    problemas = []
    for canal in guild.text_channels:
        if canal.name.split('│')[-1] not in CANALES_CLAVE:
            continue
        permisos = canal.permissions_for(guild.me)
        faltan = [nombre for clave, nombre in PERMISOS_NECESARIOS.items() if not getattr(permisos, clave)]
        if faltan:
            problemas.append(f'#{canal.name}: falta {", ".join(faltan)}')
    for problema in problemas:
        print(f'[registro] Permisos: {problema}')
        anotar(guild, guild.me, '⚠️ Al bot le faltan permisos',
               f'{problema} · arréglalo con /setup-servidor o dando esos permisos al rol del bot')


async def cerrar_mge_sin_tablon(guild: discord.Guild):
    """Un MGE activo sin tablón no lo puede usar nadie (quedan de creaciones que fallaron): se cierra."""
    for ev in await db.mge_get_eventos_activos(str(guild.id)):
        if not ev['mensaje_id']:
            await db.mge_cerrar_evento(str(guild.id), int(ev['id']))
            anotar(guild, guild.me, '🧹 MGE sin tablón cerrado', f'#{ev["id"]} {ev["nombre"]} (no se llegó a publicar)')


async def asegurar_canal(guild: discord.Guild):
    """Crea el canal de logs si no existe y lo devuelve a 👑 ADMINISTRACIÓN si se movió (p. ej. al archivo)."""
    canal     = await canal_logs(guild)
    categoria = discord.utils.get(guild.categories, name=CATEGORIA_ADMIN)
    if canal and categoria and canal.category != categoria:
        await canal.edit(category=categoria, overwrites=overwrites_logs(guild), reason='Canal de logs en su sitio')
    return canal


class Registro(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._revisado = False  # la revisión de arranque solo una vez, no en cada reconexión
        self.purgar.start()

    def cog_unload(self):
        self.purgar.cancel()

    # ── Purga de lo que tiene más de RETENCION_DIAS ───────────────────────────

    @tasks.loop(hours=1)
    async def purgar(self):
        antes = int(time.time()) - RETENCION_DIAS * 86400
        for guild in self.bot.guilds:
            try:
                await purgar_antiguos(guild, antes)
            except Exception as e:
                print(f'[registro] Error purgando el log de {guild.name}: {type(e).__name__}: {e}')

    @purgar.before_loop
    async def antes_purgar(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._revisado:
            return
        self._revisado = True
        for guild in self.bot.guilds:
            try:
                canal = await asegurar_canal(guild)
                print(f'[registro] Canal de logs listo en {guild.name}: #{canal.name}')
            except discord.Forbidden:
                print(f'[registro] Sin permiso para crear/mover el canal de logs en {guild.name} '
                      '(hace falta "Gestionar canales"). Los registros se guardan igual en la BD.')
            except Exception as e:
                print(f'[registro] Error preparando el canal de logs en {guild.name}: {type(e).__name__}: {e}')
            try:
                await revisar_permisos(guild)
                await cerrar_mge_sin_tablon(guild)
            except Exception as e:
                print(f'[registro] Error en la revisión de arranque de {guild.name}: {type(e).__name__}: {e}')

    # ── Comandos de admin terminados con éxito ────────────────────────────────

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        if es_comando_admin(command) and command.qualified_name not in SOLO_LECTURA:
            anotar(interaction.guild, interaction.user, f'/{command.qualified_name}', detalle_parametros(interaction))

    # ── Protección: lo borrado se restaura ────────────────────────────────────

    async def _restaurar(self, guild: discord.Guild, mensaje_ids: list[str], accion_auditoria):
        canal_id = await db.get_config(str(guild.id), 'logs_canal')
        regs = await db.log_get_por_mensajes(mensaje_ids)
        if not regs or not canal_id:
            return
        quien = await quien_borro(guild, accion_auditoria, int(canal_id))
        canal = await canal_logs(guild)
        async with _lock:
            for reg in regs:
                await _publicar(canal, reg, prefijo='♻️ *restaurado* · ')
        anotar(guild, quien, '🗑️ Borró registros del log',
               f'{len(regs)} registro(s); el bot los ha vuelto a publicar'
               + ('' if quien else ' (no se pudo ver quién: falta el permiso Ver registro de auditoría)'))

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if not payload.guild_id:
            return
        canal_id = await db.get_config(str(payload.guild_id), 'logs_canal')
        if canal_id and str(payload.channel_id) == canal_id:
            guild = self.bot.get_guild(payload.guild_id)
            await self._restaurar(guild, [str(payload.message_id)], discord.AuditLogAction.message_delete)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        if not payload.guild_id:
            return
        canal_id = await db.get_config(str(payload.guild_id), 'logs_canal')
        if canal_id and str(payload.channel_id) == canal_id:
            guild = self.bot.get_guild(payload.guild_id)
            await self._restaurar(guild, [str(i) for i in payload.message_ids], discord.AuditLogAction.message_bulk_delete)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        canal_id = await db.get_config(str(channel.guild.id), 'logs_canal')
        if canal_id != str(channel.id):
            return
        guild = channel.guild
        quien = await quien_borro(guild, discord.AuditLogAction.channel_delete, channel.id)
        await db.set_config(str(guild.id), 'logs_canal', '')
        nuevo = await canal_logs(guild)
        ultimos = list(reversed(await db.log_buscar(str(guild.id), limite=25)))
        async with _lock:
            await nuevo.send(
                f'⚠️ El canal de logs fue borrado{f" por {quien.mention}" if quien else ""} y el bot lo ha recreado. '
                f'Aquí van los últimos {len(ultimos)} registros; **todos** siguen en la base de datos (`/log`).',
                allowed_mentions=discord.AllowedMentions.none(),
            )
            for reg in ultimos:
                await _publicar(nuevo, reg, prefijo='♻️ ')
        anotar(guild, quien, '🗑️ Borró el canal de logs', 'el bot lo ha recreado')

    # ── /log ──────────────────────────────────────────────────────────────────

    @app_commands.command(name='log', description='[ADMIN] Consulta el registro de acciones de admin')
    @app_commands.describe(
        usuario='Solo las acciones de esta persona',
        buscar='Texto a buscar (ej: mge, limpiar, evento)',
        cantidad='Cuántos registros mostrar (máx. 50, por defecto 20). Solo hay los de los últimos 3 días',
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def log(self, interaction: discord.Interaction, usuario: discord.Member = None,
                  buscar: str = None, cantidad: app_commands.Range[int, 1, 50] = 20):
        regs = await db.log_buscar(str(interaction.guild_id), str(usuario.id) if usuario else None, buscar, cantidad)
        if not regs:
            await interaction.response.send_message('📋 No hay registros con ese filtro.', ephemeral=True)
            return
        lineas = []
        largo  = 0
        for reg in regs:
            linea = formatear(reg)
            if largo + len(linea) > 3900:
                lineas.append(f'_… y más; afina con `usuario` o `buscar`_')
                break
            lineas.append(linea)
            largo += len(linea) + 1
        filtro = ' · '.join(x for x in (usuario.display_name if usuario else '', f'"{buscar}"' if buscar else '') if x)
        embed = discord.Embed(title=f'📋 Registro de admin{" — " + filtro if filtro else ""}',
                              description='\n'.join(lineas), color=COLOR_BOT)
        embed.set_footer(text=f'Del más reciente al más antiguo · {ALIANZA_TAG}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @log.error
    async def log_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Registro(bot))
