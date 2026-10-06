import asyncio
import re
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import COLOR_BOT, ALIANZA_TAG, REINO
from db import database as db

ZONA = ZoneInfo('Europe/Madrid')


def fmt_poder(n: int) -> str:
    if n >= 1_000_000:
        return f'{n / 1_000_000:.3f}'.rstrip('0').rstrip('.') + 'M'
    if n >= 1_000:
        return f'{n / 1_000:.3f}'.rstrip('0').rstrip('.') + 'K'
    return str(n)

DIAS_NOMBRE = {
    0: 'Lunes', 1: 'Martes', 2: 'Miércoles',
    3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo',
}
DIAS_NOMBRE_EN = {
    0: 'Monday', 1: 'Tuesday', 2: 'Wednesday',
    3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday',
}
DIAS_CORTO = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}
DIAS_EMOJI = {
    0: '🔵', 1: '🔵', 2: '🔵', 3: '🔵', 4: '🔵', 5: '🟣', 6: '🟣',
}


def es_admin(member: discord.Member) -> bool:
    return member.guild_permissions.manage_guild


def nombre_dias(dias: str) -> str:
    """'0,1,2,3,4' → 'Lun–Vie'; '5,6' → 'Sáb, Dom'."""
    lista = sorted(int(d) for d in dias.split(',') if d != '')
    if lista == list(range(7)):
        return 'Todos los días'
    if lista == list(range(5)):
        return 'Lun–Vie'
    if lista == [5, 6]:
        return 'Fines de semana'
    return ', '.join(DIAS_CORTO[d] for d in lista)


def cuando_evento(ev) -> str:
    if ev['puntual']:
        try:
            return '📌 ' + datetime.strptime(ev['fecha_unica'], '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            return '📌 ' + ev['fecha_unica']
    return '🔁 ' + nombre_dias(ev['dias'])


def parse_hora(texto: str) -> str | None:
    """Acepta '20:00', '20.30', '20h', '9:05', '20' → 'HH:MM'."""
    m = re.fullmatch(r'(\d{1,2})(?:\s*[:.h]\s*(\d{2})?)?\s*h?', texto.strip().lower())
    if not m:
        return None
    horas, minutos = int(m.group(1)), int(m.group(2) or 0)
    if horas > 23 or minutos > 59:
        return None
    return f'{horas:02d}:{minutos:02d}'


def parse_fecha(texto: str) -> date | None:
    """Acepta dd/mm/aaaa, dd/mm/aa o dd/mm (sin año = la próxima vez que llegue esa fecha)."""
    texto = texto.strip().replace('-', '/').replace('.', '/')
    for formato in ('%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    try:
        dia_mes = datetime.strptime(texto, '%d/%m')
    except ValueError:
        return None
    hoy   = datetime.now(ZONA).date()
    fecha = date(hoy.year, dia_mes.month, dia_mes.day)
    return fecha if fecha >= hoy else date(hoy.year + 1, dia_mes.month, dia_mes.day)


# ── Calendario semanal ─────────────────────────────────────────────────────────

async def build_semana_embed(guild_id: str) -> discord.Embed:
    now    = datetime.now(ZONA)
    events = await db.get_guild_events(guild_id)

    embed = discord.Embed(
        title='📅  Calendario de la Alianza · Alliance Calendar',
        description=f'*{ALIANZA_TAG} · Reino {REINO}*',
        color=0x5865F2,
        timestamp=datetime.now(),
    )

    # ── KvK activo ────────────────────────────────────────────────────────────
    temporada = await db.kvk_get_active(guild_id)
    if temporada:
        tipo   = '🔄 Recuperación / Recovery' if temporada['recuperacion'] else '⚔️ Principal / Main'
        guerra = '🟢 ACTIVA / ACTIVE' if temporada['guerra_activa'] else '🔴 inactiva / inactive'
        valor  = f'{tipo} · War: {guerra}'
        if temporada['historia']:
            valor += f'\n📖 {temporada["historia"]}'
        if temporada['fecha_inicio'] or temporada['fecha_fin']:
            valor += f'\n📅 {temporada["fecha_inicio"] or "?"} → {temporada["fecha_fin"] or "?"}'
        embed.add_field(name=f'⚔️ KvK: {temporada["nombre"]}', value=valor, inline=False)

    # ── MGEs activos ──────────────────────────────────────────────────────────
    mges = await db.mge_get_eventos_activos(guild_id)
    if mges:
        lineas_mge = []
        for m in mges:
            inscritos = await db.mge_count_inscritos(int(m['id']))
            selec     = await db.mge_get_seleccionados(int(m['id']))
            lineas_mge.append(
                f'**{m["nombre"]}** — 🎯 {fmt_poder(m["poder_min"])} · '
                f'👥 {inscritos} inscritos / enrolled · 🏆 {len(selec)}/{m["max_plazas"]} plazas / slots'
            )
        embed.add_field(name='📝 MGEs activos / Active MGEs', value='\n'.join(lineas_mge), inline=False)

    tiene_algo = bool(temporada or mges)
    for offset in range(7):
        dia_dt    = now + timedelta(days=offset)
        dia_idx   = str(dia_dt.weekday())
        fecha_iso = dia_dt.strftime('%Y-%m-%d')
        nombre_es = DIAS_NOMBRE[dia_dt.weekday()]
        nombre_en = DIAS_NOMBRE_EN[dia_dt.weekday()]
        emoji     = DIAS_EMOJI[dia_dt.weekday()]
        fecha     = dia_dt.strftime('%d/%m')
        hoy       = '  *(hoy / today)*' if offset == 0 else ('  *(mañana / tomorrow)*' if offset == 1 else '')

        ev_dia = [
            ev for ev in events
            if (ev['fecha_unica'] == fecha_iso if ev['puntual'] else dia_idx in ev['dias'].split(','))
        ]
        ev_dia.sort(key=lambda e: e['hora'])

        if ev_dia:
            tiene_algo = True
            lineas = [f'🕐 **{ev["hora"]}** — {ev["nombre"]}' for ev in ev_dia]
            embed.add_field(
                name=f'{emoji} {nombre_es} / {nombre_en} {fecha}{hoy}',
                value='\n'.join(lineas),
                inline=False,
            )

    if not tiene_algo:
        embed.description += '\n\n_No hay eventos, KvK ni MGE activos esta semana. / No active events, KvK or MGE this week._'

    embed.set_footer(text=f'Actualizado / Updated · {now.strftime("%H:%M")} · Spain Time · ➕ ⚙️ solo liderazgo')
    return embed


async def refrescar_calendario(guild: discord.Guild):
    """Repinta el calendario anclado (o lo publica si no existe)."""
    canal_id   = await db.get_config(str(guild.id), 'eventos_semana_canal')
    mensaje_id = await db.get_config(str(guild.id), 'eventos_semana_mensaje')
    if not canal_id:
        return
    canal = guild.get_channel(int(canal_id))
    if not canal:
        return

    embed = await build_semana_embed(str(guild.id))
    if mensaje_id:
        try:
            await canal.get_partial_message(int(mensaje_id)).edit(embed=embed, view=CalendarioView())
            return
        except discord.NotFound:
            pass

    msg = await canal.send(embed=embed, view=CalendarioView())
    await db.set_config(str(guild.id), 'eventos_semana_mensaje', str(msg.id))
    try:
        await msg.pin()
    except discord.HTTPException:
        pass


_tareas: set = set()


def refrescar_calendario_luego(guild: discord.Guild):
    """Repinta el calendario sin hacer esperar a quien pulsó el botón."""
    tarea = asyncio.create_task(refrescar_calendario(guild))
    _tareas.add(tarea)
    tarea.add_done_callback(_tareas.discard)


async def canal_avisos_por_defecto(guild: discord.Guild, respaldo: discord.abc.GuildChannel) -> discord.abc.GuildChannel:
    canal_id = await db.get_config(str(guild.id), 'eventos_avisos_canal')
    canal    = guild.get_channel(int(canal_id)) if canal_id else None
    if not canal:
        canal = next((c for c in guild.text_channels if 'eventos-general' in c.name), None)
    return canal or respaldo


# ── Formulario de evento (crear y editar) ─────────────────────────────────────

class EventoModal(discord.ui.Modal):
    def __init__(self, evento=None, panel: 'PanelEventos' = None):
        super().__init__(title='✏️ Editar evento' if evento else '➕ Nuevo evento')
        self.evento = evento
        self.panel  = panel

        self.nombre = discord.ui.TextInput(placeholder='Ej: Ark of Osiris', max_length=60,
                                           default=evento['nombre'] if evento else None)
        self.hora   = discord.ui.TextInput(placeholder='Ej: 20:00 (hora de España)', max_length=5,
                                           default=evento['hora'] if evento else None)
        dias_actuales = set(evento['dias'].split(',')) if evento and not evento['puntual'] else set()
        self.dias = discord.ui.Select(
            placeholder='Elige uno o varios días', min_values=0, max_values=7, required=False,
            options=[discord.SelectOption(label=DIAS_NOMBRE[d], value=str(d), default=str(d) in dias_actuales)
                     for d in range(7)],
        )
        fecha_actual = ''
        if evento and evento['puntual']:
            try:
                fecha_actual = datetime.strptime(evento['fecha_unica'], '%Y-%m-%d').strftime('%d/%m/%Y')
            except ValueError:
                fecha_actual = evento['fecha_unica']
        self.fecha = discord.ui.TextInput(placeholder='dd/mm/aaaa — solo si NO se repite', max_length=10,
                                          required=False, default=fecha_actual or None)
        rol_actual = [discord.SelectDefaultValue(id=int(evento['rol_ping']), type=discord.SelectDefaultValueType.role)] \
            if evento and evento['rol_ping'] else []
        self.rol = discord.ui.RoleSelect(placeholder='Vacío = @everyone', min_values=0, max_values=1,
                                         required=False, default_values=rol_actual)

        self.add_item(discord.ui.Label(text='Nombre del evento', component=self.nombre))
        self.add_item(discord.ui.Label(text='Hora', component=self.hora))
        self.add_item(discord.ui.Label(text='Días que se repite', description='Déjalo vacío si es un evento de un solo día',
                                       component=self.dias))
        self.add_item(discord.ui.Label(text='…o fecha concreta', description='Para un evento que no se repite',
                                       component=self.fecha))
        self.add_item(discord.ui.Label(text='Rol a avisar', component=self.rol))

    async def on_submit(self, interaction: discord.Interaction):
        hora = parse_hora(self.hora.value)
        if not hora:
            await interaction.response.send_message('❌ Hora incorrecta. Usa por ejemplo `20:00` o `9:30`.', ephemeral=True)
            return
        dias  = sorted(self.dias.values, key=int)
        fecha = self.fecha.value.strip()
        if dias and fecha:
            await interaction.response.send_message(
                '❌ Elige **días que se repite** o **una fecha concreta**, no las dos cosas.', ephemeral=True)
            return
        if not dias and not fecha:
            await interaction.response.send_message(
                '❌ Indica los **días que se repite** o **una fecha concreta**.', ephemeral=True)
            return

        if fecha:
            fecha_dt = parse_fecha(fecha)
            if not fecha_dt:
                await interaction.response.send_message('❌ Fecha incorrecta. Usa `dd/mm/aaaa` (ej: 15/11/2026).', ephemeral=True)
                return
            if fecha_dt < datetime.now(ZONA).date():
                await interaction.response.send_message('❌ Esa fecha ya ha pasado.', ephemeral=True)
                return
            dias_db, fecha_db, puntual = str(fecha_dt.weekday()), fecha_dt.strftime('%Y-%m-%d'), True
        else:
            dias_db, fecha_db, puntual = ','.join(dias), '', False

        rol    = self.rol.values[0] if self.rol.values else None
        nombre = self.nombre.value.strip()

        if self.evento:
            await db.update_event(int(self.evento['id']), nombre, hora, dias_db, puntual, fecha_db,
                                  str(rol.id) if rol else '')
            aviso = f'✏️ **{nombre}** actualizado'
        else:
            canal = await canal_avisos_por_defecto(interaction.guild, interaction.channel)
            nuevo_id = await db.create_event(
                guild_id=str(interaction.guild_id), canal_id=str(canal.id), rol_ping=str(rol.id) if rol else '',
                nombre=nombre, descripcion='', hora=hora, dias=dias_db, puntual=puntual, fecha_unica=fecha_db,
            )
            aviso = f'✅ **{nombre}** creado · avisos en {canal.mention}'
            if self.panel:
                self.panel.seleccionado = nuevo_id
        refrescar_calendario_luego(interaction.guild)

        if self.panel:
            await self.panel.render(interaction, aviso)
            return

        cuando = (f'📌 {fecha_dt.strftime("%d/%m/%Y")}' if puntual else f'🔁 {nombre_dias(dias_db)}')
        await interaction.response.send_message(
            f'{aviso}\n🕐 **{hora}** · {cuando} · 🔔 {rol.mention if rol else "@everyone"}\n'
            '_Avisos automáticos 30 min antes y a la hora. Para editarlo, pulsa ⚙️ Gestionar en el calendario._',
            ephemeral=True,
        )


# ── Panel de gestión (privado) ────────────────────────────────────────────────

class PanelEventos(discord.ui.LayoutView):
    def __init__(self, guild_id: str):
        super().__init__(timeout=900)
        self.guild_id         = guild_id
        self.eventos          = []
        self.seleccionado     = None
        self.confirmar_borrar = False
        self.aviso            = ''

    def _evento(self):
        return next((e for e in self.eventos if e['id'] == self.seleccionado), None)

    async def recargar(self):
        self.eventos = await db.get_guild_events(self.guild_id)
        if not self._evento():
            self.seleccionado = None
        self._montar()

    async def render(self, interaction: discord.Interaction, aviso: str = ''):
        self.aviso = aviso
        await self.recargar()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    def _boton(self, fila, label, emoji, style, callback, disabled=False):
        boton = discord.ui.Button(label=label, emoji=emoji, style=style, disabled=disabled)
        boton.callback = callback
        fila.add_item(boton)

    def _montar(self):
        self.clear_items()
        cont = discord.ui.Container(accent_colour=0x5865F2)
        cabecera = f'## ⚙️ Eventos ({len(self.eventos)})'
        if self.aviso:
            cabecera += f'\n> {self.aviso}'
        cont.add_item(discord.ui.TextDisplay(cabecera))

        if self.eventos:
            opciones = [discord.SelectOption(
                label=f'{e["hora"]} · {e["nombre"]}'[:100], value=str(e['id']),
                description=cuando_evento(e)[:100], default=e['id'] == self.seleccionado,
            ) for e in self.eventos[:25]]
            sel = discord.ui.Select(placeholder='Elige un evento para editarlo o borrarlo', options=opciones)
            sel.callback = self._elegir
            cont.add_item(discord.ui.ActionRow(sel))
        else:
            cont.add_item(discord.ui.TextDisplay('_No hay eventos todavía. Pulsa ➕ Crear evento._'))

        ev = self._evento()
        if ev:
            cont.add_item(discord.ui.Separator())
            rol = f'<@&{ev["rol_ping"]}>' if ev['rol_ping'] else '@everyone'
            cont.add_item(discord.ui.TextDisplay(
                f'### {ev["nombre"]}\n🕐 **{ev["hora"]}** · {cuando_evento(ev)}\n'
                f'📢 Avisos en <#{ev["canal_id"]}> · 🔔 {rol}'
            ))
            canal = discord.ui.ChannelSelect(
                placeholder='📢 Cambiar canal de avisos', channel_types=[discord.ChannelType.text],
                default_values=[discord.SelectDefaultValue(id=int(ev['canal_id']),
                                                           type=discord.SelectDefaultValueType.channel)],
            )
            canal.callback = self._cambiar_canal
            cont.add_item(discord.ui.ActionRow(canal))
            fila = discord.ui.ActionRow()
            self._boton(fila, 'Editar', '✏️', discord.ButtonStyle.primary, self._editar)
            self._boton(fila, '¿Seguro? Pulsa otra vez' if self.confirmar_borrar else 'Eliminar',
                        '⚠️' if self.confirmar_borrar else '🗑️', discord.ButtonStyle.danger, self._eliminar)
            cont.add_item(fila)

        cont.add_item(discord.ui.Separator())
        fila = discord.ui.ActionRow()
        self._boton(fila, 'Crear evento', '➕', discord.ButtonStyle.success, self._crear)
        self._boton(fila, 'Cerrar', '✖️', discord.ButtonStyle.secondary, self._cerrar)
        cont.add_item(fila)
        self.add_item(cont)

    async def _elegir(self, interaction: discord.Interaction):
        self.seleccionado     = int(interaction.data['values'][0])
        self.confirmar_borrar = False
        await self.render(interaction)

    async def _cambiar_canal(self, interaction: discord.Interaction):
        canal_id = interaction.data['values'][0]
        await db.update_event_canal(self.seleccionado, canal_id)
        await self.render(interaction, f'📢 Avisos de este evento → <#{canal_id}>')

    async def _editar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EventoModal(evento=self._evento(), panel=self))

    async def _eliminar(self, interaction: discord.Interaction):
        ev = self._evento()
        if not self.confirmar_borrar:
            self.confirmar_borrar = True
            await self.render(interaction, f'⚠️ Vas a eliminar **{ev["nombre"]}**. Pulsa otra vez para confirmar.')
            return
        await db.delete_event(self.guild_id, int(ev['id']))
        self.confirmar_borrar = False
        refrescar_calendario_luego(interaction.guild)
        await self.render(interaction, f'🗑️ **{ev["nombre"]}** eliminado')

    async def _crear(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EventoModal(panel=self))

    async def _cerrar(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            cerrado = discord.ui.LayoutView()
            cerrado.add_item(discord.ui.TextDisplay('✅ Panel cerrado.'))
            await interaction.edit_original_response(view=cerrado)


# ── Botones del calendario anclado ─────────────────────────────────────────────

class CalendarioView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if es_admin(interaction.user):
            return True
        await interaction.response.send_message('❌ Solo el liderazgo puede gestionar eventos. / Leadership only.',
                                                ephemeral=True)
        return False

    @discord.ui.button(label='Crear evento', emoji='➕', style=discord.ButtonStyle.success, custom_id='cal:crear')
    async def crear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EventoModal())

    @discord.ui.button(label='Gestionar', emoji='⚙️', style=discord.ButtonStyle.secondary, custom_id='cal:gestionar')
    async def gestionar(self, interaction: discord.Interaction, button: discord.ui.Button):
        panel = PanelEventos(str(interaction.guild_id))
        await panel.recargar()
        await interaction.response.send_message(view=panel, ephemeral=True)


# ── Cog ────────────────────────────────────────────────────────────────────────

class Eventos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_eventos.start()
        self.actualizar_semana.start()

    async def cog_load(self):
        self.bot.add_view(CalendarioView())

    def cog_unload(self):
        self.check_eventos.cancel()
        self.actualizar_semana.cancel()

    # ── Tarea: avisos automáticos ─────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def check_eventos(self):
        now          = datetime.now(ZONA)
        today        = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        current_day  = str(now.weekday())

        eventos = await db.get_all_active_events()
        for ev in eventos:
            if ev['puntual']:
                if ev['fecha_unica'] != today:
                    continue
            else:
                if current_day not in ev['dias'].split(','):
                    continue

            canal = self.bot.get_channel(int(ev['canal_id']))
            if not canal:
                continue

            rol_mention = f'<@&{ev["rol_ping"]}>' if ev['rol_ping'] else '@everyone'
            event_dt    = datetime.strptime(ev['hora'], '%H:%M').replace(
                year=now.year, month=now.month, day=now.day, tzinfo=ZONA
            )
            aviso_time = (event_dt - timedelta(minutes=30)).strftime('%H:%M')

            if current_time == aviso_time and ev['dia_ultimo_aviso'] != today:
                await db.update_event_aviso(ev['id'], today)
                embed = discord.Embed(
                    title=f'⏰ {ev["nombre"]} — en 30 minutos / in 30 minutes',
                    description=ev['descripcion'] or '',
                    color=COLOR_BOT,
                )
                embed.add_field(name='Hora / Time', value=f'{ev["hora"]} (Spain)')
                await canal.send(content=rol_mention, embed=embed)

            elif current_time == ev['hora'] and ev['dia_ultima_ejecucion'] != today:
                await db.update_event_ejecucion(ev['id'], today)
                embed = discord.Embed(
                    title=f'🚨 {ev["nombre"]} — ¡AHORA! / NOW!',
                    description=ev['descripcion'] or '',
                    color=0xFF0000,
                )
                await canal.send(content=rol_mention, embed=embed)

                if ev['puntual']:
                    await db.delete_event_by_id(ev['id'])
                    await refrescar_calendario(canal.guild)

    @check_eventos.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ── Tarea: actualizar el calendario ───────────────────────────────────────

    @tasks.loop(hours=1)
    async def actualizar_semana(self):
        for guild in self.bot.guilds:
            try:
                await refrescar_calendario(guild)
            except Exception as e:
                print(f'[eventos] Error actualizando calendario en {guild.name}: {type(e).__name__}: {e}')

    @actualizar_semana.before_loop
    async def before_semana(self):
        await self.bot.wait_until_ready()

    # ── Comandos ──────────────────────────────────────────────────────────────

    @app_commands.command(name='canal-eventos', description='[ADMIN] Publica el calendario con botones en un canal (ej: #calendario)')
    @app_commands.describe(
        canal='Canal donde se ancla el calendario con los botones de crear y gestionar',
        avisos='Canal por defecto donde saldrán los avisos de los eventos nuevos (opcional)',
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def canal_eventos(self, interaction: discord.Interaction, canal: discord.TextChannel,
                            avisos: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)
        # Si había un calendario anterior, se borra para que solo quede uno con botones
        canal_viejo = await db.get_config(guild_id, 'eventos_semana_canal')
        msg_viejo   = await db.get_config(guild_id, 'eventos_semana_mensaje')
        if canal_viejo and msg_viejo:
            viejo = interaction.guild.get_channel(int(canal_viejo))
            if viejo:
                try:
                    await viejo.get_partial_message(int(msg_viejo)).delete()
                except discord.HTTPException:
                    pass
        await db.set_config(guild_id, 'eventos_semana_canal', str(canal.id))
        await db.set_config(guild_id, 'eventos_semana_mensaje', '')
        if avisos:
            await db.set_config(guild_id, 'eventos_avisos_canal', str(avisos.id))

        await refrescar_calendario(interaction.guild)
        destino = await canal_avisos_por_defecto(interaction.guild, canal)
        await interaction.followup.send(
            f'✅ Calendario anclado en {canal.mention} con los botones ➕ Crear evento y ⚙️ Gestionar.\n'
            f'📢 Los avisos de los eventos nuevos saldrán en {destino.mention} (se puede cambiar por evento).',
            ephemeral=True,
        )

    @canal_eventos.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Eventos(bot))
