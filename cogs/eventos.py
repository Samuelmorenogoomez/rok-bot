import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
DIAS_EMOJI = {
    0: '🔵', 1: '🔵', 2: '🔵', 3: '🔵', 4: '🔵', 5: '🟣', 6: '🟣',
}
NOMBRES_DIAS = {
    '0,1,2,3,4,5,6': 'Todos los días',
    '0,1,2,3,4':      'Lun–Vie',
    '0': 'Lunes', '1': 'Martes', '2': 'Miércoles',
    '3': 'Jueves', '4': 'Viernes', '5': 'Sábado', '6': 'Domingo',
}


async def build_semana_embed(guild_id: str) -> discord.Embed:
    now    = datetime.now(ZONA)
    events = await db.get_guild_events(guild_id)

    embed = discord.Embed(
        title='📅  Calendario de la Alianza',
        description=f'*{ALIANZA_TAG} · Reino {REINO}*',
        color=0x5865F2,
        timestamp=datetime.now(),
    )

    # ── KvK activo ────────────────────────────────────────────────────────────
    temporada = await db.kvk_get_active(guild_id)
    if temporada:
        tipo   = '🔄 Recuperación' if temporada['recuperacion'] else '⚔️ Principal'
        guerra = '🟢 ACTIVA' if temporada['guerra_activa'] else '🔴 inactiva'
        valor  = f'{tipo} · Guerra: {guerra}'
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
                f'👥 {inscritos} inscritos · 🏆 {len(selec)}/{m["max_plazas"]} plazas'
            )
        embed.add_field(name='📝 MGEs activos', value='\n'.join(lineas_mge), inline=False)

    tiene_algo = bool(temporada or mges)
    for offset in range(7):
        dia_dt    = now + timedelta(days=offset)
        dia_idx   = str(dia_dt.weekday())
        fecha_iso = dia_dt.strftime('%Y-%m-%d')
        nombre    = DIAS_NOMBRE.get(str(dia_dt.weekday()), '')
        emoji     = DIAS_EMOJI[dia_dt.weekday()]
        fecha     = dia_dt.strftime('%d/%m')
        hoy       = '  *(hoy)*' if offset == 0 else ('  *(mañana)*' if offset == 1 else '')

        ev_dia = [
            ev for ev in events
            if (ev['fecha_unica'] == fecha_iso if ev['puntual'] else dia_idx in ev['dias'].split(','))
        ]
        ev_dia.sort(key=lambda e: e['hora'])

        if ev_dia:
            tiene_algo = True
            lineas = [f'🕐 **{ev["hora"]}** — {ev["nombre"]}' for ev in ev_dia]
            embed.add_field(
                name=f'{emoji} {nombre} {fecha}{hoy}',
                value='\n'.join(lineas),
                inline=False,
            )

    if not tiene_algo:
        embed.description += '\n\n_No hay eventos, KvK ni MGE activos esta semana._'

    embed.set_footer(text=f'Actualizado · {now.strftime("%H:%M")} · Hora de España')
    return embed


class Eventos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_eventos.start()
        self.actualizar_semana.start()

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
                    title=f'⏰ {ev["nombre"]} — en 30 minutos',
                    description=ev['descripcion'] or '',
                    color=COLOR_BOT,
                )
                embed.add_field(name='Hora', value=f'{ev["hora"]} (España)')
                await canal.send(content=rol_mention, embed=embed)

            elif current_time == ev['hora'] and ev['dia_ultima_ejecucion'] != today:
                await db.update_event_ejecucion(ev['id'], today)
                embed = discord.Embed(
                    title=f'🚨 {ev["nombre"]} — ¡AHORA!',
                    description=ev['descripcion'] or '',
                    color=0xFF0000,
                )
                await canal.send(content=rol_mention, embed=embed)

                if ev['puntual']:
                    await db.delete_event_by_id(ev['id'])
                    await self._refrescar_semana(canal.guild)

    @check_eventos.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ── Tarea: actualizar embed de semana ────────────────────────────────────

    @tasks.loop(hours=1)
    async def actualizar_semana(self):
        for guild in self.bot.guilds:
            try:
                await self._refrescar_semana(guild)
            except Exception as e:
                print(f'[eventos] Error actualizando calendario en {guild.name}: {type(e).__name__}: {e}')

    @actualizar_semana.before_loop
    async def before_semana(self):
        await self.bot.wait_until_ready()

    async def _refrescar_semana(self, guild: discord.Guild):
        canal_id  = await db.get_config(str(guild.id), 'eventos_semana_canal')
        mensaje_id = await db.get_config(str(guild.id), 'eventos_semana_mensaje')
        if not canal_id:
            return

        canal = guild.get_channel(int(canal_id))
        if not canal:
            return

        embed = await build_semana_embed(str(guild.id))

        if mensaje_id:
            try:
                msg = await canal.fetch_message(int(mensaje_id))
                await msg.edit(embed=embed)
                return
            except discord.NotFound:
                pass

        msg = await canal.send(embed=embed)
        await db.set_config(str(guild.id), 'eventos_semana_mensaje', str(msg.id))
        try:
            await msg.pin()
        except Exception:
            pass

    # ── Comandos ──────────────────────────────────────────────────────────────

    @app_commands.command(name='canal-eventos', description='[ADMIN] Activa el resumen semanal automático de eventos en un canal')
    @app_commands.describe(canal='Canal donde se publicará el resumen semanal')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def canal_eventos(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await db.set_config(str(interaction.guild_id), 'eventos_semana_canal', str(canal.id))
        await db.set_config(str(interaction.guild_id), 'eventos_semana_mensaje', '')

        await interaction.response.defer()
        await self._refrescar_semana(interaction.guild)
        await interaction.followup.send(
            f'✅ Canal de eventos configurado en {canal.mention}. El resumen se actualiza cada hora automáticamente.',
            ephemeral=True,
        )

    @app_commands.command(name='evento-crear', description='[ADMIN] Crea un recordatorio de evento (recurrente o puntual)')
    @app_commands.describe(
        nombre='Nombre del evento (ej: Ark of Osiris)',
        hora='Hora en formato HH:MM — hora de España',
        canal='Canal donde se enviará el aviso',
        dia='Día(s) de la semana — para eventos que se repiten',
        fecha='Fecha concreta dd/mm/aaaa — para un evento puntual que NO se repite nunca más',
        rol='Rol al que se mencionará (opcional, por defecto @everyone)',
        descripcion='Descripción opcional',
    )
    @app_commands.choices(dia=[
        app_commands.Choice(name='Todos los días',  value='0,1,2,3,4,5,6'),
        app_commands.Choice(name='Lunes a Viernes', value='0,1,2,3,4'),
        app_commands.Choice(name='Lunes',           value='0'),
        app_commands.Choice(name='Martes',          value='1'),
        app_commands.Choice(name='Miércoles',       value='2'),
        app_commands.Choice(name='Jueves',          value='3'),
        app_commands.Choice(name='Viernes',         value='4'),
        app_commands.Choice(name='Sábado',          value='5'),
        app_commands.Choice(name='Domingo',         value='6'),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def evento_crear(
        self,
        interaction: discord.Interaction,
        nombre: str,
        hora: str,
        canal: discord.TextChannel,
        dia: str = None,
        fecha: str = None,
        rol: discord.Role = None,
        descripcion: str = '',
    ):
        try:
            datetime.strptime(hora, '%H:%M')
        except ValueError:
            await interaction.response.send_message('❌ Formato de hora incorrecto. Usa HH:MM (ej: 20:00)', ephemeral=True)
            return

        if not dia and not fecha:
            await interaction.response.send_message(
                '❌ Indica `dia` para un evento recurrente o `fecha` para uno puntual.', ephemeral=True
            )
            return
        if dia and fecha:
            await interaction.response.send_message(
                '❌ Indica solo uno: `dia` (recurrente) o `fecha` (puntual), no ambos.', ephemeral=True
            )
            return

        if fecha:
            try:
                fecha_dt = datetime.strptime(fecha, '%d/%m/%Y')
            except ValueError:
                await interaction.response.send_message(
                    '❌ Formato de fecha incorrecto. Usa dd/mm/aaaa (ej: 15/07/2026)', ephemeral=True
                )
                return
            dias_db       = str(fecha_dt.weekday())
            fecha_unica_db = fecha_dt.strftime('%Y-%m-%d')
            es_puntual    = True
        else:
            dias_db        = dia
            fecha_unica_db = ''
            es_puntual     = False

        await db.create_event(
            guild_id=str(interaction.guild_id),
            canal_id=str(canal.id),
            rol_ping=str(rol.id) if rol else '',
            nombre=nombre,
            descripcion=descripcion,
            hora=hora,
            dias=dias_db,
            puntual=es_puntual,
            fecha_unica=fecha_unica_db,
        )

        embed = discord.Embed(title='✅ Evento creado', color=COLOR_BOT)
        embed.add_field(name='Nombre', value=nombre, inline=True)
        embed.add_field(name='Hora',   value=f'{hora} (España)', inline=True)
        if es_puntual:
            embed.add_field(name='📌 Tipo', value=f'Puntual — {fecha_dt.strftime("%d/%m/%Y")}\n_No se repetirá_', inline=True)
        else:
            embed.add_field(name='🔁 Días', value=NOMBRES_DIAS.get(dia, dia), inline=True)
        embed.add_field(name='Canal',  value=canal.mention, inline=True)
        if rol:
            embed.add_field(name='Ping', value=rol.mention, inline=True)
        embed.set_footer(text='Avisos automáticos: 30 min antes y a la hora exacta')
        await interaction.response.send_message(embed=embed)

        # Actualizar el resumen semanal si está configurado
        await self._refrescar_semana(interaction.guild)

    @app_commands.command(name='evento-lista', description='Muestra todos los eventos programados')
    async def evento_lista(self, interaction: discord.Interaction):
        eventos = await db.get_guild_events(str(interaction.guild_id))
        if not eventos:
            await interaction.response.send_message('No hay eventos. Usa `/evento-crear`.', ephemeral=True)
            return

        embed = discord.Embed(title='📅 Eventos programados', color=COLOR_BOT)
        for ev in eventos:
            canal = self.bot.get_channel(int(ev['canal_id']))
            if ev['puntual']:
                try:
                    fecha_str = datetime.strptime(ev['fecha_unica'], '%Y-%m-%d').strftime('%d/%m/%Y')
                except ValueError:
                    fecha_str = ev['fecha_unica']
                cuando = f'📌 Puntual · {fecha_str}'
            else:
                cuando = f'🔁 {NOMBRES_DIAS.get(ev["dias"], ev["dias"])}'
            embed.add_field(
                name=f'`#{ev["id"]}` {ev["nombre"]}',
                value=f'🕐 **{ev["hora"]}** · {cuando} · {canal.mention if canal else "canal eliminado"}',
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='evento-eliminar', description='[ADMIN] Elimina un evento programado')
    @app_commands.describe(id='ID del evento (ver /evento-lista)')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def evento_eliminar(self, interaction: discord.Interaction, id: int):
        ok = await db.delete_event(str(interaction.guild_id), id)
        if ok:
            await self._refrescar_semana(interaction.guild)
            await interaction.response.send_message(f'🗑️ Evento `#{id}` eliminado.')
        else:
            await interaction.response.send_message(f'❌ No se encontró el evento `#{id}`.', ephemeral=True)

    @canal_eventos.error
    @evento_crear.error
    @evento_eliminar.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos para este comando.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Eventos(bot))
