import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import COLOR_BOT, ALIANZA_TAG, ALIANZA_FULL, REINO
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
        return f'{n / 1_000_000:.3f}'.rstrip('0').rstrip('.') + 'M'
    if n >= 1_000:
        return f'{n / 1_000:.3f}'.rstrip('0').rstrip('.') + 'K'
    return str(n)


# ── Constantes ─────────────────────────────────────────────────────────────────

MAX_PLAZAS = 25  # límite de opciones de un desplegable de Discord
MEDALLAS   = ['🥇', '🥈', '🥉']
SEPARADOR  = '━━━━━━━━━━━━━━━━━━━━━━'

# clave → (etiqueta del tablón, nombre del rol a mencionar)
TROPAS = {
    'infanteria': ('🗡️ Infantería / Infantry', '🗡️ Infantería'),
    'caballeria': ('🐴 Caballería / Cavalry',   '🐴 Caballería'),
    'arqueros':   ('🏹 Arqueros / Archers',     '🏹 Arqueros'),
    'maquinaria': ('⚙️ Maquinaria / Siege',     '⚙️ Maquinaria'),
    'mixto':      ('🔱 Mixto / Mixed',          '🔱 Mixto'),
    'todas':      ('🌐 Todas / All troops',     None),
}

# Rangos de cabezas doradas: clave → (etiqueta, valor numérico guardado, texto que se muestra).
# Las cabezas son solo informativas para el liderazgo: no influyen en la asignación de plazas.
RANGOS_CABEZAS = {
    'r0':    ('0 — solo voy a por puntos / just for points', 0,    '0'),
    'r1':    ('1 – 100',                                     50,   '1–100'),
    'r100':  ('100 – 300',                                   200,  '100–300'),
    'r300':  ('300 – 600',                                   450,  '300–600'),
    'r600':  ('600 – 1000',                                  800,  '600–1000'),
    'r1000': ('+1000',                                       1000, '+1000'),
}


def txt_cabezas(ins) -> str:
    return ins['cabezas_txt'] or str(ins['cabezas'] or 0)


def medalla(posicion: int) -> str:
    return MEDALLAS[posicion - 1] if posicion <= 3 else f'`#{posicion}`'


def es_externo(user_id: str) -> bool:
    return user_id.startswith('ext_')


def buscar_canal(guild: discord.Guild, fragmento: str, excluir: tuple = ()):
    return next(
        (c for c in guild.text_channels
         if fragmento in c.name and not any(x in c.name for x in excluir)),
        None,
    )


# ── Tablón ─────────────────────────────────────────────────────────────────────

async def construir_tablon(ev) -> discord.Embed:
    inscritos = await db.mge_get_inscritos(int(ev['id']))
    selec     = await db.mge_get_seleccionados(int(ev['id']))
    por_user  = {i['user_id']: i for i in inscritos}
    asignados = {s['user_id'] for s in selec}
    abierta   = ev['activo'] and ev['inscripcion_abierta']

    if not ev['activo']:
        estado, color = '🏁 **Finalizado / Finished**', 0x95A5A6
    elif abierta:
        estado, color = '🟢 **Inscripciones abiertas / Enrollment open**', 0xFFD700
    else:
        estado, color = '🔒 **Inscripciones cerradas / Enrollment closed**', 0xE67E22

    cabecera = [
        f'*{ALIANZA_FULL} · Reino {REINO}*',
        estado,
        f'🎯 Meta / Target: **{fmt_poder(ev["poder_min"])}** · '
        f'👥 Plazas / Slots: **{ev["max_plazas"]}** · {TROPAS.get(ev["tropa"], TROPAS["todas"])[0]}',
    ]
    if abierta and ev['cierre_ts']:
        cierre = int(ev['cierre_ts'])
        cabecera.append(f'⏰ Cierre / Closes: <t:{cierre}:R> · <t:{cierre}:f>')
    if ev['descripcion']:
        cabecera.append(f'_{ev["descripcion"]}_')

    # Plazas asignadas, con los huecos libres a la vista
    ocupadas = {s['posicion']: s for s in selec}
    lineas_plazas = [f'🏆 **PLAZAS / SLOTS ({len(selec)}/{ev["max_plazas"]})**']
    for pos in range(1, ev['max_plazas'] + 1):
        s = ocupadas.get(pos)
        if not s:
            lineas_plazas.append(f'{medalla(pos)} ⬜ _libre / open_')
            continue
        ins   = por_user.get(s['user_id'])
        linea = f'{medalla(pos)} **{s["gobernador"]}**'
        if ins:
            linea += f' · 🗿 {txt_cabezas(ins)}'
        if s['poder'] != ev['poder_min']:
            linea += f' · 🎯 {fmt_poder(s["poder"])}'
        lineas_plazas.append(linea)

    # Lista de espera por orden de inscripción
    espera = [i for i in inscritos if i['user_id'] not in asignados]
    lineas_espera = [f'📝 **EN ESPERA / WAITING ({len(espera)})**']
    if not espera:
        lineas_espera.append(
            '_¡Pulsa ✋ para apuntarte! / Press ✋ to sign up!_' if abierta else '_Nadie en espera. / Nobody waiting._'
        )

    descripcion = '\n'.join(cabecera) + f'\n{SEPARADOR}\n' + '\n'.join(lineas_plazas) + f'\n{SEPARADOR}\n' + '\n'.join(lineas_espera)
    for n, i in enumerate(espera):
        linea = f'\n`{n + 1:>2}.` **{i["gobernador"]}** · 🗿 {txt_cabezas(i)}'
        if i['poder']:
            linea += f' · {fmt_poder(i["poder"])}'
        if es_externo(i['user_id']):
            linea += ' · _ext_'
        resto = f'\n_… y {len(espera) - n} más / and {len(espera) - n} more_'
        if len(descripcion) + len(linea) + len(resto) > 4000:
            descripcion += resto
            break
        descripcion += linea

    embed = discord.Embed(title=f'🔥 {ev["nombre"]}', description=descripcion, color=color)
    if ev['activo']:
        embed.set_footer(text=(
            '✋ Apuntarse · 🗿 Cambiar cabezas · 🚪 Salir · ⚙️ Liderazgo\n'
            f'✋ Sign up · 🗿 Change heads · 🚪 Leave · MGE #{ev["id"]} · {ALIANZA_TAG}'
        ))
    else:
        embed.set_footer(text=f'MGE #{ev["id"]} · {ALIANZA_TAG} · Reino {REINO}')
    return embed


async def refrescar_tablon(client: discord.Client, evento_id: int):
    """Vuelve a pintar el tablón del MGE con los datos actuales de la BD."""
    ev = await db.mge_get_evento(evento_id)
    if not ev or not ev['canal_id'] or not ev['mensaje_id']:
        return
    canal = client.get_channel(int(ev['canal_id']))
    if not canal:
        return
    vista = TablonView(abierta=bool(ev['inscripcion_abierta'])) if ev['activo'] else None
    try:
        await canal.get_partial_message(int(ev['mensaje_id'])).edit(embed=await construir_tablon(ev), view=vista)
    except discord.HTTPException as e:
        print(f'[mge] No se pudo actualizar el tablón del MGE #{evento_id}: {e}')


async def publicar_tablon(canal: discord.TextChannel, evento_id: int) -> discord.Message:
    ev  = await db.mge_get_evento(evento_id)
    msg = await canal.send(embed=await construir_tablon(ev), view=TablonView(abierta=bool(ev['inscripcion_abierta'])))
    await db.mge_set_tablon(evento_id, str(canal.id), str(msg.id))
    return msg


# ── Inscripción con cabezas ────────────────────────────────────────────────────

async def guardar_inscripcion(interaction: discord.Interaction, evento_id: int,
                              cabezas: int, cabezas_txt: str) -> str:
    """Inscribe (o actualiza) al usuario que pulsa y devuelve el mensaje de confirmación."""
    ev = await db.mge_get_evento(evento_id)
    if not ev or not ev['activo'] or not ev['inscripcion_abierta']:
        return '🔒 Las inscripciones de este MGE están cerradas. / Enrollment for this MGE is closed.'

    miembro    = await db.get_member(str(interaction.guild_id), str(interaction.user.id))
    gobernador = miembro['gobernador'] if miembro else interaction.user.display_name
    poder      = miembro['poder'] if miembro else 0

    nueva = await db.mge_inscribir(evento_id, str(interaction.guild_id), str(interaction.user.id),
                                   gobernador, poder, cabezas, cabezas_txt)
    await refrescar_tablon(interaction.client, evento_id)

    mostrar = cabezas_txt or str(cabezas)
    if nueva:
        texto = (f'✅ ¡Apuntado a **{ev["nombre"]}** con 🗿 **{mostrar}** cabezas doradas!\n'
                 f'_Signed up for **{ev["nombre"]}** with 🗿 **{mostrar}** golden heads!_')
    else:
        texto = f'✅ Cabezas actualizadas: 🗿 **{mostrar}** / _Heads updated_'
    if not miembro:
        texto += ('\n\nℹ️ No tienes perfil: apareces como **' + gobernador + '**. Usa `/registrar` para salir con tu '
                  'nombre de gobernador y tu poder. / _No profile yet: use `/registrar` to show your governor name._')
    return texto


class CabezasModal(discord.ui.Modal, title='🗿 Cabezas doradas / Golden heads'):
    cantidad = discord.ui.TextInput(label='¿Cuántas tienes? / How many?', placeholder='Ej: 420', max_length=6)

    def __init__(self, evento_id: int):
        super().__init__()
        self.evento_id = evento_id

    async def on_submit(self, interaction: discord.Interaction):
        valor = self.cantidad.value.strip().replace('.', '')
        if not valor.isdigit():
            await interaction.response.send_message('❌ Escribe solo un número. / Numbers only.', ephemeral=True)
            return
        texto = await guardar_inscripcion(interaction, self.evento_id, int(valor), '')
        await interaction.response.edit_message(content=texto, view=None)


class CabezasView(discord.ui.View):
    """Selector privado de cabezas doradas que aparece al pulsar ✋ o 🗿."""

    def __init__(self, evento_id: int):
        super().__init__(timeout=300)
        self.evento_id = evento_id
        opciones = [discord.SelectOption(label=etiqueta, value=clave, emoji='🗿')
                    for clave, (etiqueta, _, _) in RANGOS_CABEZAS.items()]
        opciones.append(discord.SelectOption(label='Escribir número exacto / Exact number', value='exacto', emoji='✏️'))
        selector = discord.ui.Select(placeholder='🗿 ¿Cuántas cabezas doradas tienes? / Golden heads?', options=opciones)
        selector.callback = self._elegido
        self.add_item(selector)

    async def _elegido(self, interaction: discord.Interaction):
        clave = interaction.data['values'][0]
        if clave == 'exacto':
            await interaction.response.send_modal(CabezasModal(self.evento_id))
            return
        _, valor, texto = RANGOS_CABEZAS[clave]
        mensaje = await guardar_inscripcion(interaction, self.evento_id, valor, texto)
        await interaction.response.edit_message(content=mensaje, view=None)


# ── Vista persistente del tablón ───────────────────────────────────────────────

class TablonView(discord.ui.View):
    def __init__(self, abierta: bool = True):
        super().__init__(timeout=None)
        self.apuntar.disabled = not abierta
        self.cabezas.disabled = not abierta

    async def _evento(self, interaction: discord.Interaction):
        ev = await db.mge_get_evento_por_mensaje(str(interaction.message.id))
        if not ev or not ev['activo']:
            await interaction.response.send_message('❌ Este MGE ya no está activo. / This MGE is no longer active.', ephemeral=True)
            return None
        return ev

    async def _abrir_selector(self, interaction: discord.Interaction, ev, texto: str):
        if not ev['inscripcion_abierta']:
            await interaction.response.send_message('🔒 Las inscripciones están cerradas. / Enrollment is closed.', ephemeral=True)
            return
        await interaction.response.send_message(texto, view=CabezasView(int(ev['id'])), ephemeral=True)

    @discord.ui.button(label='Apuntarme', emoji='✋', style=discord.ButtonStyle.success, custom_id='mge:apuntar')
    async def apuntar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ev = await self._evento(interaction)
        if not ev:
            return
        ins = await db.mge_get_inscripcion(int(ev['id']), str(interaction.user.id))
        if ins:
            await interaction.response.send_message(
                f'ℹ️ Ya estás apuntado con 🗿 **{txt_cabezas(ins)}**. Usa 🗿 para cambiarlas.\n'
                f'_Already signed up. Use 🗿 to change your heads._',
                ephemeral=True,
            )
            return
        await self._abrir_selector(interaction, ev, f'**{ev["nombre"]}** — elige tus cabezas doradas / _pick your golden heads_')

    @discord.ui.button(label='Mis cabezas', emoji='🗿', style=discord.ButtonStyle.primary, custom_id='mge:cabezas')
    async def cabezas(self, interaction: discord.Interaction, button: discord.ui.Button):
        ev = await self._evento(interaction)
        if not ev:
            return
        ins = await db.mge_get_inscripcion(int(ev['id']), str(interaction.user.id))
        texto = (f'Ahora tienes 🗿 **{txt_cabezas(ins)}**. Elige el nuevo valor / _Pick the new value_'
                 if ins else f'**{ev["nombre"]}** — elige tus cabezas doradas / _pick your golden heads_')
        await self._abrir_selector(interaction, ev, texto)

    @discord.ui.button(label='Salir', emoji='🚪', style=discord.ButtonStyle.secondary, custom_id='mge:salir')
    async def salir(self, interaction: discord.Interaction, button: discord.ui.Button):
        ev = await self._evento(interaction)
        if not ev:
            return
        selec   = await db.mge_get_seleccionados(int(ev['id']))
        tenia   = any(s['user_id'] == str(interaction.user.id) for s in selec)
        ok      = await db.mge_cancelar_inscripcion(int(ev['id']), str(interaction.user.id))
        if not ok:
            await interaction.response.send_message('ℹ️ No estabas apuntado. / You were not signed up.', ephemeral=True)
            return
        await refrescar_tablon(interaction.client, int(ev['id']))
        aviso = '\n⚠️ Has dejado libre tu plaza. / _You gave up your slot._' if tenia else ''
        await interaction.response.send_message(
            f'🚪 Te has borrado de **{ev["nombre"]}**. / _You left **{ev["nombre"]}**._{aviso}', ephemeral=True
        )

    @discord.ui.button(label='Gestionar', emoji='⚙️', style=discord.ButtonStyle.secondary, custom_id='mge:gestionar')
    async def gestionar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Solo el liderazgo. / Leadership only.', ephemeral=True)
            return
        ev = await self._evento(interaction)
        if not ev:
            return
        panel = PanelAdmin(int(ev['id']))
        await panel.recargar()
        await interaction.response.send_message(embed=panel.embed(), view=panel, ephemeral=True)


# ── Panel de administración (privado) ──────────────────────────────────────────

class MetaModal(discord.ui.Modal, title='🎯 Meta individual / Individual target'):
    meta = discord.ui.TextInput(label='Meta de poder / Power target', placeholder='Ej: 60M, 45000K', max_length=20)

    def __init__(self, panel: 'PanelAdmin', user_id: str):
        super().__init__()
        self.panel   = panel
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        meta = parse_poder(self.meta.value)
        if meta < 0:
            await interaction.response.send_message('❌ Formato: `50M`, `30000K` o `50000000`', ephemeral=True)
            return
        await db.mge_set_meta_individual(self.panel.evento_id, self.user_id, meta)
        await refrescar_tablon(interaction.client, self.panel.evento_id)
        await self.panel.render(interaction, f'🎯 Meta individual → **{fmt_poder(meta)}**')


class ExternoModal(discord.ui.Modal, title='➕ Inscribir externo / External'):
    gobernador = discord.ui.TextInput(label='Gobernador (sin Discord)', placeholder='Nombre en el juego', max_length=50)
    cantidad   = discord.ui.TextInput(label='Cabezas doradas / Golden heads', placeholder='Ej: 300', max_length=6)

    def __init__(self, panel: 'PanelAdmin'):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        valor = self.cantidad.value.strip().replace('.', '')
        if not valor.isdigit():
            await interaction.response.send_message('❌ Las cabezas deben ser un número.', ephemeral=True)
            return
        nombre  = self.gobernador.value.strip()
        user_id = 'ext_' + nombre.lower().replace(' ', '_')
        miembro = await db.get_member(str(interaction.guild_id), user_id)
        poder   = miembro['poder'] if miembro else 0
        await db.mge_inscribir(self.panel.evento_id, str(interaction.guild_id), user_id, nombre, poder, int(valor), '')
        await refrescar_tablon(interaction.client, self.panel.evento_id)
        self.panel.seleccionado = user_id
        await self.panel.render(interaction, f'➕ **{nombre}** _(externo)_ inscrito con 🗿 {valor}')


class PanelAdmin(discord.ui.View):
    """Panel privado para el liderazgo: se elige un gobernador y se actúa sobre él."""

    def __init__(self, evento_id: int):
        super().__init__(timeout=900)
        self.evento_id        = evento_id
        self.seleccionado     = None   # user_id elegido en el desplegable
        self.confirmar_final  = False
        self.pagina           = 0      # página de la lista de espera en el asignado rápido
        self.ev               = None
        self.inscritos        = []
        self.selec            = []

    # ── Datos y pintado ────────────────────────────────────────────────────────

    def _plaza_de(self, user_id: str):
        return next((s for s in self.selec if s['user_id'] == user_id), None)

    async def recargar(self):
        self.ev        = await db.mge_get_evento(self.evento_id)
        self.inscritos = await db.mge_get_inscritos(self.evento_id)
        self.selec     = await db.mge_get_seleccionados(self.evento_id)
        if self.seleccionado and not any(i['user_id'] == self.seleccionado for i in self.inscritos):
            self.seleccionado = None
        self._montar()

    def _espera(self) -> list:
        asignados = {s['user_id'] for s in self.selec}
        return [i for i in self.inscritos if i['user_id'] not in asignados]

    def _siguiente_libre(self):
        ocupadas = {s['posicion'] for s in self.selec}
        return next((p for p in range(1, min(self.ev['max_plazas'], MAX_PLAZAS) + 1) if p not in ocupadas), None)

    def _montar(self):
        self.clear_items()
        activo = bool(self.ev['activo'])

        # Fila 0: marcar de golpe a los que entran (selección múltiple sobre la lista de espera)
        espera    = self._espera()
        siguiente = self._siguiente_libre()
        libres    = min(self.ev['max_plazas'], MAX_PLAZAS) - len(self.selec)
        if activo and siguiente and espera:
            if self.pagina * 25 >= len(espera):
                self.pagina = 0
            trozo    = espera[self.pagina * 25:(self.pagina + 1) * 25]
            opciones = []
            for n, i in enumerate(trozo, self.pagina * 25 + 1):
                desc = f'🗿 {txt_cabezas(i)}' + (f' · {fmt_poder(i["poder"])}' if i['poder'] else '')
                opciones.append(discord.SelectOption(label=f'{n}. {i["gobernador"]}'[:100], value=i['user_id'],
                                                     description=desc[:100]))
            sel_rapido = discord.ui.Select(
                placeholder=f'✅ Marca a los que entran (hasta {libres}) / Tick who gets in',
                options=opciones, row=0, min_values=1, max_values=min(libres, len(opciones)),
            )
        else:
            texto = ('✅ Todas las plazas cubiertas / All slots filled' if not siguiente
                     else 'Nadie en lista de espera / Nobody waiting')
            sel_rapido = discord.ui.Select(placeholder=texto, row=0, disabled=True,
                                           options=[discord.SelectOption(label='—', value='none')])
        sel_rapido.callback = self._asignar_rapido
        self.add_item(sel_rapido)

        # Fila 1: retocar a un gobernador (primero los que tienen plaza, por orden de plaza)
        con_plaza_ids = [s['user_id'] for s in self.selec]
        por_user      = {i['user_id']: i for i in self.inscritos}
        orden         = [por_user[u] for u in con_plaza_ids if u in por_user] + espera
        if orden:
            opciones = []
            for i in orden[:25]:
                plaza = self._plaza_de(i['user_id'])
                desc  = f'🗿 {txt_cabezas(i)}' + (f' · plaza #{plaza["posicion"]}' if plaza else ' · en espera')
                opciones.append(discord.SelectOption(
                    label=i['gobernador'][:100], value=i['user_id'], description=desc[:100],
                    emoji='🏆' if plaza else '📝', default=i['user_id'] == self.seleccionado,
                ))
            sel_gob = discord.ui.Select(placeholder='✏️ Retocar: elige un gobernador / Edit a governor',
                                        options=opciones, row=1, disabled=not activo)
        else:
            sel_gob = discord.ui.Select(placeholder='Nadie inscrito todavía / Nobody yet', row=1, disabled=True,
                                        options=[discord.SelectOption(label='—', value='none')])
        sel_gob.callback = self._elegir_gobernador
        self.add_item(sel_gob)

        # Fila 2: mover al gobernador elegido a otra plaza (si está ocupada, se intercambian)
        ocupadas = {s['posicion']: s for s in self.selec}
        actual   = self._plaza_de(self.seleccionado) if self.seleccionado else None
        opciones = []
        for pos in range(1, min(self.ev['max_plazas'], MAX_PLAZAS) + 1):
            ocupante = ocupadas.get(pos)
            opciones.append(discord.SelectOption(
                label=f'#{pos} · {ocupante["gobernador"] if ocupante else "libre / open"}'[:100],
                value=str(pos),
                emoji=MEDALLAS[pos - 1] if pos <= 3 else ('🔸' if ocupante else '⬜'),
                default=bool(actual and actual['posicion'] == pos),
            ))
        sel_pos = discord.ui.Select(placeholder='↕️ Mover a la plaza… / Move to slot…', options=opciones, row=2,
                                    disabled=not (activo and self.seleccionado))
        sel_pos.callback = self._asignar_posicion
        self.add_item(sel_pos)

        # Fila 3: acciones
        con_plaza = bool(activo and actual)
        abierta   = bool(self.ev['inscripcion_abierta'])
        self._boton('Meta', '🎯', discord.ButtonStyle.primary, 3, self._meta, not con_plaza)
        self._boton('Quitar', '❌', discord.ButtonStyle.danger, 3, self._quitar, not con_plaza)
        self._boton('Vaciar plazas', '🧹', discord.ButtonStyle.secondary, 3, self._vaciar, not (activo and self.selec))
        self._boton('Externo', '➕', discord.ButtonStyle.secondary, 3, self._externo, not activo)
        self._boton('Cerrar inscr.' if abierta else 'Reabrir inscr.',
                    '🔒' if abierta else '🔓', discord.ButtonStyle.secondary, 3, self._abrir_cerrar, not activo)

        # Fila 4: publicar, finalizar y paginar la lista de espera si hay más de 25
        self._boton('Publicar lista final', '📢', discord.ButtonStyle.success, 4, self._publicar,
                    not (activo and self.selec))
        self._boton('¿Seguro? Pulsa otra vez' if self.confirmar_final else 'Finalizar MGE',
                    '⚠️' if self.confirmar_final else '🏁', discord.ButtonStyle.danger, 4, self._finalizar, not activo)
        if activo and siguiente and len(espera) > 25:
            self._boton('Siguientes 25', '➡️', discord.ButtonStyle.secondary, 4, self._pagina)

    def _boton(self, label, emoji, style, row, callback, disabled=False):
        boton = discord.ui.Button(label=label, emoji=emoji, style=style, row=row, disabled=disabled)
        boton.callback = callback
        self.add_item(boton)

    def _lista(self) -> str:
        """Lista numerada de todos los inscritos con su estado."""
        if not self.inscritos:
            return '\n\n_Nadie inscrito todavía._'
        texto = f'\n\n📋 **Inscritos / Signed up ({len(self.inscritos)})**'
        for n, i in enumerate(self.inscritos, 1):
            plaza = self._plaza_de(i['user_id'])
            linea = f'\n`{n:>2}.` {medalla(plaza["posicion"]) if plaza else "📝"} **{i["gobernador"]}** · 🗿 {txt_cabezas(i)}'
            if i['poder']:
                linea += f' · {fmt_poder(i["poder"])}'
            if len(texto) + len(linea) > 3500:
                return texto + f'\n_… y {len(self.inscritos) - n + 1} más_'
            texto += linea
        return texto

    def embed(self, aviso: str = '') -> discord.Embed:
        ev    = self.ev
        libre = ev['max_plazas'] - len(self.selec)
        e = discord.Embed(
            title=f'⚙️ Gestión — {ev["nombre"]}',
            description=(
                f'👥 **{len(self.inscritos)}** inscritos · 🏆 **{len(self.selec)}/{ev["max_plazas"]}** plazas '
                f'({libre} libres) · {"🟢 abiertas" if ev["inscripcion_abierta"] else "🔒 cerradas"}'
                + self._lista()
            ),
            color=0x2F3136,
        )
        if self.seleccionado:
            ins   = next(i for i in self.inscritos if i['user_id'] == self.seleccionado)
            plaza = self._plaza_de(self.seleccionado)
            info  = f'🗿 {txt_cabezas(ins)}'
            if ins['poder']:
                info += f' · 💪 {fmt_poder(ins["poder"])}'
            info += (f'\n🏆 Plaza **#{plaza["posicion"]}** · 🎯 {fmt_poder(plaza["poder"])}'
                     if plaza else '\n📝 En espera / waiting')
            e.add_field(name=f'Seleccionado: {ins["gobernador"]}', value=info, inline=False)
        else:
            e.add_field(name='Cómo se usa', value=(
                '✅ **Elegir el top:** en el primer desplegable marca a todos los que entran de una vez; '
                'ocupan las plazas libres en el orden de la lista.\n'
                '✏️ **Retocar:** elige un gobernador y muévelo; si la plaza está ocupada, **se intercambian**.\n'
                '📢 Cuando esté bien, *Publicar lista final*.'
            ), inline=False)
        if len(self._espera()) > 25:
            e.add_field(name='ℹ️', value='Más de 25 en espera: usa ➡️ *Siguientes 25* para ver el resto en el desplegable.', inline=False)
        if aviso:
            e.add_field(name='Última acción', value=aviso, inline=False)
        return e

    async def render(self, interaction: discord.Interaction, aviso: str = ''):
        await self.recargar()
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed(aviso), view=self)
        else:
            await interaction.response.edit_message(embed=self.embed(aviso), view=self)

    # ── Callbacks ──────────────────────────────────────────────────────────────

    async def _elegir_gobernador(self, interaction: discord.Interaction):
        self.seleccionado    = interaction.data['values'][0]
        self.confirmar_final = False
        await self.render(interaction)

    async def _asignar_posicion(self, interaction: discord.Interaction):
        pos      = int(interaction.data['values'][0])
        ins      = next(i for i in self.inscritos if i['user_id'] == self.seleccionado)
        actual   = self._plaza_de(self.seleccionado)
        ocupante = next((s for s in self.selec if s['posicion'] == pos and s['user_id'] != self.seleccionado), None)
        meta     = actual['poder'] if actual else self.ev['poder_min']
        await db.mge_seleccionar(self.evento_id, str(interaction.guild_id), self.seleccionado,
                                 ins['gobernador'], meta, pos)
        aviso = f'{medalla(pos)} **{ins["gobernador"]}** → plaza #{pos}'
        if ocupante and actual:
            # Intercambio: el que estaba en esa plaza pasa a la antigua del elegido
            await db.mge_seleccionar(self.evento_id, str(interaction.guild_id), ocupante['user_id'],
                                     ocupante['gobernador'], ocupante['poder'], actual['posicion'])
            aviso += f'\n🔁 **{ocupante["gobernador"]}** pasa a la plaza #{actual["posicion"]}'
        elif ocupante:
            aviso += f'\n↩️ **{ocupante["gobernador"]}** vuelve a la lista de espera'
        await refrescar_tablon(interaction.client, self.evento_id)
        await self.render(interaction, aviso)

    async def _meta(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MetaModal(self, self.seleccionado))

    async def _quitar(self, interaction: discord.Interaction):
        ins = next(i for i in self.inscritos if i['user_id'] == self.seleccionado)
        await db.mge_quitar_seleccion(self.evento_id, self.seleccionado)
        await refrescar_tablon(interaction.client, self.evento_id)
        await self.render(interaction, f'❌ **{ins["gobernador"]}** vuelve a la lista de espera')

    async def _asignar_rapido(self, interaction: discord.Interaction):
        marcados = set(interaction.data['values'])
        # Se colocan en las plazas libres respetando el orden de la lista
        elegidos = [i for i in self._espera() if i['user_id'] in marcados]
        ocupadas = {s['posicion'] for s in self.selec}
        libres   = [p for p in range(1, min(self.ev['max_plazas'], MAX_PLAZAS) + 1) if p not in ocupadas]
        lineas   = []
        for pos, ins in zip(libres, elegidos):
            await db.mge_seleccionar(self.evento_id, str(interaction.guild_id), ins['user_id'],
                                     ins['gobernador'], self.ev['poder_min'], pos)
            lineas.append(f'{medalla(pos)} {ins["gobernador"]}')
        await refrescar_tablon(interaction.client, self.evento_id)
        aviso = '✅ Asignados: ' + ' · '.join(lineas) if lineas else '⚠️ No quedaban plazas libres.'
        await self.render(interaction, aviso[:1024])

    async def _pagina(self, interaction: discord.Interaction):
        self.pagina += 1
        await self.render(interaction)

    async def _vaciar(self, interaction: discord.Interaction):
        n = await db.mge_vaciar_seleccion(self.evento_id)
        await refrescar_tablon(interaction.client, self.evento_id)
        await self.render(interaction, f'🧹 {n} plazas vaciadas; todos vuelven a la lista de espera.')

    async def _externo(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ExternoModal(self))

    async def _abrir_cerrar(self, interaction: discord.Interaction):
        abrir = not self.ev['inscripcion_abierta']
        await db.mge_set_inscripcion_abierta(self.evento_id, abrir)
        await refrescar_tablon(interaction.client, self.evento_id)
        await self.render(interaction, '🔓 Inscripciones reabiertas' if abrir else '🔒 Inscripciones cerradas')

    async def _publicar(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ev = self.ev
        lineas = [f'{medalla(s["posicion"])} **{s["gobernador"]}** — 🎯 **{fmt_poder(s["poder"])}**' for s in self.selec]
        embed = discord.Embed(
            title=f'🏆 Participantes / Participants — {ev["nombre"]}',
            description=(
                f'**{ALIANZA_FULL} · Reino {REINO}**\n\n'
                f'¡Estos son los **{len(self.selec)}** seleccionados y sus metas!\n'
                f'_These are the **{len(self.selec)}** selected participants and their targets!_\n\n'
                + '\n'.join(lineas)
            ),
            color=0xFFD700,
        )
        embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
        menciones = ' '.join(f'<@{s["user_id"]}>' for s in self.selec if not es_externo(s['user_id']))

        guild  = interaction.guild
        canal  = None
        canal_id = await db.get_config(str(guild.id), 'mge_canal_resultados')
        if canal_id:
            canal = guild.get_channel(int(canal_id))
        canal = canal or buscar_canal(guild, 'mge-resultados') or interaction.channel
        await canal.send(content=menciones or None, embed=embed)

        # Aviso por MD a cada seleccionado con su plaza y su meta
        enviados = 0
        for s in self.selec:
            if es_externo(s['user_id']):
                continue
            miembro = guild.get_member(int(s['user_id']))
            if not miembro:
                continue
            try:
                await miembro.send(
                    f'🏆 **{ev["nombre"]}** · {ALIANZA_TAG}\n'
                    f'Tienes la plaza {medalla(s["posicion"])} con meta 🎯 **{fmt_poder(s["poder"])}**. ¡A por ello! 🔥\n'
                    f'_You got slot #{s["posicion"]} with a **{fmt_poder(s["poder"])}** target. Go for it!_'
                )
                enviados += 1
            except discord.HTTPException:
                pass
        await self.render(interaction, f'📢 Lista publicada en {canal.mention} · {enviados} MD enviados')

    async def _finalizar(self, interaction: discord.Interaction):
        if not self.confirmar_final:
            self.confirmar_final = True
            await self.render(interaction, '⚠️ Al finalizar, el tablón se congela y pasa al historial. Pulsa otra vez para confirmar.')
            return
        await db.mge_set_inscripcion_abierta(self.evento_id, False)
        await db.mge_cerrar_evento(str(interaction.guild_id), self.evento_id)
        await refrescar_tablon(interaction.client, self.evento_id)
        await self.render(interaction, '🏁 MGE finalizado. Ya aparece en `/mge-historial`.')
        self.stop()


# ── Creación ───────────────────────────────────────────────────────────────────

class CrearModal(discord.ui.Modal, title='🔥 Nuevo MGE'):
    nombre = discord.ui.TextInput(label='Nombre', placeholder='Ej: MGE Caballería', max_length=60)
    meta   = discord.ui.TextInput(label='Meta de poder', placeholder='Ej: 50M, 30000K', max_length=20)
    plazas = discord.ui.TextInput(label=f'Plazas (1-{MAX_PLAZAS})', default='10', max_length=2)
    horas  = discord.ui.TextInput(label='Cierre de inscripciones en X horas (opcional)',
                                  placeholder='Ej: 48 · vacío = lo cierras tú a mano', max_length=4, required=False)
    descripcion = discord.ui.TextInput(label='Descripción (opcional)', style=discord.TextStyle.paragraph,
                                       max_length=300, required=False)

    def __init__(self, tropa: str, anunciar: bool):
        super().__init__()
        self.tropa    = tropa
        self.anunciar = anunciar

    async def on_submit(self, interaction: discord.Interaction):
        meta = parse_poder(self.meta.value)
        if meta < 0:
            await interaction.response.send_message('❌ Meta incorrecta. Usa `50M`, `30000K` o `50000000`.', ephemeral=True)
            return
        if not self.plazas.value.strip().isdigit() or not 1 <= int(self.plazas.value) <= MAX_PLAZAS:
            await interaction.response.send_message(f'❌ Las plazas deben ser un número entre 1 y {MAX_PLAZAS}.', ephemeral=True)
            return
        horas = self.horas.value.strip()
        if horas and not horas.isdigit():
            await interaction.response.send_message('❌ Las horas de cierre deben ser un número (o déjalo vacío).', ephemeral=True)
            return
        cierre_ts = int(time.time()) + int(horas) * 3600 if horas else 0

        await interaction.response.defer(ephemeral=True)
        guild     = interaction.guild
        evento_id = await db.mge_crear_evento(str(guild.id), self.nombre.value.strip(), meta, int(self.plazas.value),
                                              self.descripcion.value.strip(), self.tropa, cierre_ts)

        config = await db.get_canal_config(str(guild.id), 'mge-inscripciones')
        canal  = guild.get_channel(int(config['canal_id'])) if config else None
        canal  = canal or buscar_canal(guild, 'mge-inscripciones') or interaction.channel
        tablon = await publicar_tablon(canal, evento_id)

        respuesta = f'✅ MGE creado y tablón publicado: {tablon.jump_url}\nGestiónalo con el botón ⚙️ del tablón.'
        if self.anunciar:
            anuncios = buscar_canal(guild, 'anuncios', excluir=('kvk', 'ark'))
            if anuncios:
                rol_nombre = TROPAS.get(self.tropa, TROPAS['todas'])[1]
                rol        = discord.utils.get(guild.roles, name=rol_nombre) if rol_nombre else None
                embed = discord.Embed(
                    title=f'🔥 {self.nombre.value.strip()} — ¡Inscripciones abiertas! / Enrollment open!',
                    description=(
                        f'🎯 Meta / Target: **{fmt_poder(meta)}** · 👥 **{self.plazas.value}** plazas / slots · '
                        f'{TROPAS.get(self.tropa, TROPAS["todas"])[0]}\n'
                        + (f'⏰ Cierre / Closes: <t:{cierre_ts}:R>\n' if cierre_ts else '')
                        + f'\n👉 **[Apúntate aquí con un clic / Sign up here with one click]({tablon.jump_url})**'
                    ),
                    color=0xFFD700,
                )
                embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
                await anuncios.send(content=rol.mention if rol else None, embed=embed)
                respuesta += f'\n📢 Anunciado en {anuncios.mention}.'
            else:
                respuesta += '\n⚠️ No encontré canal de anuncios; no se ha anunciado.'
        await interaction.followup.send(respuesta, ephemeral=True)


# ── Cog ────────────────────────────────────────────────────────────────────────

class Mge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TablonView())
        self.autocierre.start()

    async def cog_unload(self):
        self.autocierre.cancel()

    # ── Cierre automático de inscripciones ─────────────────────────────────────

    @tasks.loop(minutes=1)
    async def autocierre(self):
        for ev in await db.mge_get_pendientes_autocierre(int(time.time())):
            await db.mge_set_inscripcion_abierta(int(ev['id']), False)
            await refrescar_tablon(self.bot, int(ev['id']))
            canal = self.bot.get_channel(int(ev['canal_id'])) if ev['canal_id'] else None
            if canal:
                try:
                    await canal.send(
                        f'🔒 Inscripciones de **{ev["nombre"]}** cerradas. El liderazgo asignará las plazas.\n'
                        f'_Enrollment for **{ev["nombre"]}** is closed. Leadership will assign the slots._'
                    )
                except discord.HTTPException:
                    pass

    @autocierre.before_loop
    async def antes_autocierre(self):
        await self.bot.wait_until_ready()

    # ── Autocomplete ───────────────────────────────────────────────────────────

    async def _ac_eventos(self, interaction: discord.Interaction, current: str):
        eventos = await db.mge_get_eventos_activos(str(interaction.guild_id))
        return [
            app_commands.Choice(name=f'#{e["id"]} {e["nombre"]} — meta {fmt_poder(e["poder_min"])}', value=str(e['id']))
            for e in eventos
            if current.lower() in e['nombre'].lower()
        ][:25]

    # ── /mge-crear ─────────────────────────────────────────────────────────────

    @app_commands.command(name='mge-crear', description='[ADMIN] Crea un MGE y publica su tablón de inscripción con botones')
    @app_commands.describe(
        tropa='Tropa a la que va dirigido (se menciona su rol en el anuncio)',
        anunciar='Publicar también un aviso en #anuncios (por defecto sí)',
    )
    @app_commands.choices(tropa=[
        app_commands.Choice(name='🗡️ Infantería',      value='infanteria'),
        app_commands.Choice(name='🐴 Caballería',       value='caballeria'),
        app_commands.Choice(name='🏹 Arqueros',         value='arqueros'),
        app_commands.Choice(name='⚙️ Maquinaria',      value='maquinaria'),
        app_commands.Choice(name='🔱 Mixto',            value='mixto'),
        app_commands.Choice(name='🌐 Todas las tropas', value='todas'),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_crear(self, interaction: discord.Interaction, tropa: str = 'todas', anunciar: bool = True):
        await interaction.response.send_modal(CrearModal(tropa, anunciar))

    # ── /mge-tablon ────────────────────────────────────────────────────────────

    @app_commands.command(name='mge-tablon', description='[ADMIN] Vuelve a publicar el tablón de un MGE en este canal')
    @app_commands.describe(evento='MGE cuyo tablón quieres publicar aquí')
    @app_commands.autocomplete(evento=_ac_eventos)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mge_tablon(self, interaction: discord.Interaction, evento: str):
        ev = await db.mge_get_evento(int(evento))
        if not ev or ev['guild_id'] != str(interaction.guild_id) or not ev['activo']:
            await interaction.response.send_message('❌ MGE no encontrado o finalizado.', ephemeral=True)
            return
        # Borrar el tablón anterior para que solo haya uno con botones
        if ev['canal_id'] and ev['mensaje_id']:
            antiguo = self.bot.get_channel(int(ev['canal_id']))
            if antiguo:
                try:
                    await antiguo.get_partial_message(int(ev['mensaje_id'])).delete()
                except discord.HTTPException:
                    pass
        msg = await publicar_tablon(interaction.channel, int(ev['id']))
        await interaction.response.send_message(f'✅ Tablón publicado: {msg.jump_url}', ephemeral=True)

    # ── /mge-historial ─────────────────────────────────────────────────────────

    @app_commands.command(name='mge-historial', description='Historial de MGEs / MGE History')
    @app_commands.describe(usuario='Gobernador a consultar (vacío = lista general) / Governor to check (empty = general list)')
    async def mge_historial(self, interaction: discord.Interaction, usuario: discord.Member = None):
        guild_id = str(interaction.guild_id)

        if usuario:
            historial = await db.mge_get_historial_usuario(guild_id, str(usuario.id))
            miembro   = await db.get_member(guild_id, str(usuario.id))
            nombre    = miembro['gobernador'] if miembro else usuario.display_name

            embed = discord.Embed(
                title=f'📜 Historial MGE / MGE History — {nombre}',
                color=COLOR_BOT,
            )
            embed.set_thumbnail(url=usuario.display_avatar.url)

            if not historial:
                embed.description = (
                    '_Este gobernador no ha participado en ningún MGE todavía._\n'
                    '_This governor has not participated in any MGE yet._'
                )
            else:
                lineas = []
                for h in historial:
                    fecha = h['created_at'][:10] if h['created_at'] else '—'
                    lineas.append(
                        f'{medalla(h["posicion"])} **{h["nombre"]}** — 🎯 {fmt_poder(h["meta_individual"])} · 📅 {fecha}'
                    )
                embed.description = '\n'.join(lineas)
                embed.set_footer(text=f'{len(historial)} participaciones / participations · {ALIANZA_TAG} · Reino {REINO}')

            await interaction.response.send_message(embed=embed)
            return

        cerrados = await db.mge_get_eventos_cerrados(guild_id)
        if not cerrados:
            await interaction.response.send_message(
                '📋 No hay MGEs finalizados todavía. / No finished MGEs yet.', ephemeral=True
            )
            return

        embed = discord.Embed(
            title='📜 Historial de MGEs / MGE History',
            description=(
                f'*{ALIANZA_TAG} · Reino {REINO}*\n'
                'Usa `/mge-historial usuario:@alguien` para historial personal.\n'
                '_Use `/mge-historial usuario:@someone` for personal history._'
            ),
            color=0x95A5A6,
        )
        for e in cerrados[:10]:
            selec = await db.mge_get_seleccionados(int(e['id']))
            fecha = e['created_at'][:10] if e['created_at'] else '—'
            if selec:
                top3 = ' · '.join(f'{medalla(s["posicion"])} {s["gobernador"]}' for s in selec[:3])
            else:
                top3 = '_Sin participantes / No participants_'
            embed.add_field(
                name=f'`#{e["id"]}` {e["nombre"]} · 📅 {fecha}',
                value=(
                    f'🎯 Meta / Target: {fmt_poder(e["poder_min"])} · '
                    f'👥 {len(selec)} participantes / participants\n{top3}'
                ),
                inline=False,
            )
        embed.set_footer(text=f'Últimos / Last {min(len(cerrados), 10)} MGEs · {ALIANZA_TAG}')
        await interaction.response.send_message(embed=embed)

    # ── Errores ────────────────────────────────────────────────────────────────

    @mge_crear.error
    @mge_tablon.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                '❌ No tienes permisos para este comando. / You do not have permission for this command.',
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Mge(bot))
