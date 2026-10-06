import asyncio
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


_tareas: set = set()
_refrescos_pendientes: set = set()


def en_segundo_plano(coro):
    """Lanza una corrutina sin esperarla, guardando la referencia para que no se pierda."""
    tarea = asyncio.create_task(coro)
    _tareas.add(tarea)
    tarea.add_done_callback(_tareas.discard)


def programar_refresco(client: discord.Client, evento_id: int, espera: float = 1.5):
    """Actualiza el tablón poco después, juntando en una sola edición los cambios seguidos.

    Así el panel responde al momento y no se choca con el límite de ediciones de Discord.
    """
    if evento_id in _refrescos_pendientes:
        return
    _refrescos_pendientes.add(evento_id)

    async def _tarea():
        await asyncio.sleep(espera)
        _refrescos_pendientes.discard(evento_id)
        await refrescar_tablon(client, evento_id)

    en_segundo_plano(_tarea())


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
    programar_refresco(interaction.client, evento_id)

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
        programar_refresco(interaction.client, int(ev['id']))
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
        await interaction.response.send_message(view=panel, ephemeral=True)


# ── Panel de administración (privado) ──────────────────────────────────────────

POR_PAGINA = 10  # plazas por página del panel (cada plaza es un desplegable)


class MetaModal(discord.ui.Modal, title='🎯 Meta / Target'):
    meta = discord.ui.TextInput(label='Meta de poder / Power target', placeholder='Ej: 60M, 45000K', max_length=20)

    def __init__(self, panel: 'PanelAdmin', posicion: str):
        super().__init__()
        self.panel    = panel
        self.posicion = posicion  # número de plaza o 'todas'

    async def on_submit(self, interaction: discord.Interaction):
        meta = parse_poder(self.meta.value)
        if meta < 0:
            await interaction.response.send_message('❌ Formato: `50M`, `30000K` o `50000000`', ephemeral=True)
            return
        if self.posicion == 'todas':
            for s in self.panel.selec:
                await db.mge_set_meta_individual(self.panel.evento_id, s['user_id'], meta)
            aviso = f'🎯 Todas las plazas → **{fmt_poder(meta)}**'
        else:
            s = next((s for s in self.panel.selec if s['posicion'] == int(self.posicion)), None)
            if s:
                await db.mge_set_meta_individual(self.panel.evento_id, s['user_id'], meta)
            aviso = f'🎯 Plaza #{self.posicion} → **{fmt_poder(meta)}**'
        programar_refresco(interaction.client, self.panel.evento_id)
        await self.panel.render(interaction, aviso)


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
        programar_refresco(interaction.client, self.panel.evento_id)
        await self.panel.render(interaction, f'➕ **{nombre}** _(externo)_ inscrito con 🗿 {valor}')


class PanelAdmin(discord.ui.LayoutView):
    """Panel privado del liderazgo: una lista de plazas, cada una con su desplegable (nombre + meta)."""

    def __init__(self, evento_id: int):
        super().__init__(timeout=900)
        self.evento_id       = evento_id
        self.modo            = 'plazas'  # 'plazas' o 'mas' (más opciones)
        self.pagina          = 0
        self.aviso           = ''
        self.confirmar_final = False
        self.ev              = None
        self.inscritos       = []
        self.selec           = []

    # ── Datos ──────────────────────────────────────────────────────────────────

    def _plaza_de(self, user_id: str):
        return next((s for s in self.selec if s['user_id'] == user_id), None)

    def _espera(self) -> list:
        asignados = {s['user_id'] for s in self.selec}
        return [i for i in self.inscritos if i['user_id'] not in asignados]

    def _n_plazas(self) -> int:
        return min(self.ev['max_plazas'], MAX_PLAZAS)

    async def recargar(self):
        self.ev        = await db.mge_get_evento(self.evento_id)
        self.inscritos = await db.mge_get_inscritos(self.evento_id)
        self.selec     = await db.mge_get_seleccionados(self.evento_id)
        self._montar()

    async def render(self, interaction: discord.Interaction, aviso: str = ''):
        self.aviso = aviso
        await self.recargar()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    # ── Pintado ────────────────────────────────────────────────────────────────

    def _montar(self):
        self.clear_items()
        ev     = self.ev
        activo = bool(ev['activo'])
        estado = ('🏁 finalizado' if not activo
                  else '🟢 inscripciones abiertas' if ev['inscripcion_abierta'] else '🔒 inscripciones cerradas')
        cabecera = (f'## ⚙️ {ev["nombre"]}\n'
                    f'👥 **{len(self.inscritos)}** inscritos · 🏆 **{len(self.selec)}/{self._n_plazas()}** plazas · {estado}')
        if self.aviso:
            cabecera += f'\n> {self.aviso}'

        contenedor = discord.ui.Container(accent_colour=0xFFD700)
        contenedor.add_item(discord.ui.TextDisplay(cabecera))
        contenedor.add_item(discord.ui.Separator())
        if self.modo == 'mas':
            self._montar_mas(contenedor, activo)
        else:
            self._montar_plazas(contenedor, activo)
        self.add_item(contenedor)

    def _boton(self, fila, label, emoji, style, callback, disabled=False):
        boton = discord.ui.Button(label=label, emoji=emoji, style=style, disabled=disabled)
        boton.callback = callback
        fila.add_item(boton)

    def _desplegable_plaza(self, pos: int, activo: bool) -> discord.ui.Select:
        ocupante = next((s for s in self.selec if s['posicion'] == pos), None)
        por_user = {i['user_id']: i for i in self.inscritos}
        meta     = ocupante['poder'] if ocupante else self.ev['poder_min']
        emoji    = MEDALLAS[pos - 1] if pos <= 3 else None
        opciones = []
        if ocupante:
            ins = por_user.get(ocupante['user_id'])
            opciones.append(discord.SelectOption(
                label=f'#{pos} {ocupante["gobernador"]} — 🎯 {fmt_poder(meta)}'[:100], value=ocupante['user_id'],
                description=f'🗿 {txt_cabezas(ins)}' if ins else None, emoji=emoji, default=True,
            ))
            opciones.append(discord.SelectOption(label='Dejar la plaza vacía', value='__vacia__', emoji='⬜'))
        for i in self._espera():
            desc = f'🗿 {txt_cabezas(i)}' + (f' · {fmt_poder(i["poder"])}' if i['poder'] else '') + ' · en espera'
            opciones.append(discord.SelectOption(label=i['gobernador'][:100], value=i['user_id'],
                                                 description=desc[:100], emoji='📝'))
        for s in self.selec:
            if s['posicion'] != pos:
                opciones.append(discord.SelectOption(
                    label=s['gobernador'][:100], value=s['user_id'], emoji='🔁',
                    description=f'Ahora en #{s["posicion"]} · se intercambian',
                ))
        if not opciones:
            opciones = [discord.SelectOption(label='Nadie inscrito todavía', value='__nada__')]
        sel = discord.ui.Select(
            placeholder=f'#{pos} · ⬜ libre — elige quién · 🎯 {fmt_poder(meta)}',
            options=opciones[:25],
            disabled=not activo or opciones[0].value == '__nada__',
        )
        sel.callback = lambda interaction, p=pos: self._elegir(interaction, p)
        return sel

    def _montar_plazas(self, contenedor: discord.ui.Container, activo: bool):
        n_plazas = self._n_plazas()
        paginas  = (n_plazas + POR_PAGINA - 1) // POR_PAGINA
        self.pagina = min(self.pagina, paginas - 1)
        desde = self.pagina * POR_PAGINA + 1
        hasta = min(desde + POR_PAGINA - 1, n_plazas)
        for pos in range(desde, hasta + 1):
            contenedor.add_item(discord.ui.ActionRow(self._desplegable_plaza(pos, activo)))

        contenedor.add_item(discord.ui.Separator())
        espera = self._espera()
        if espera:
            texto = f'📝 **En espera ({len(espera)}):** '
            nombres = [f'{i["gobernador"]} (🗿 {txt_cabezas(i)})' for i in espera]
            lista   = ', '.join(nombres)
            texto  += lista if len(lista) < 1500 else lista[:1500] + '…'
        else:
            texto = '📝 _Nadie en espera._'
        contenedor.add_item(discord.ui.TextDisplay(texto))

        fila = discord.ui.ActionRow()
        if paginas > 1:
            self._boton(fila, f'{desde}-{hasta}', '◀️', discord.ButtonStyle.secondary, self._anterior, self.pagina == 0)
            self._boton(fila, 'Más plazas', '▶️', discord.ButtonStyle.secondary, self._siguiente, self.pagina >= paginas - 1)
        self._boton(fila, 'Publicar', '📢', discord.ButtonStyle.success, self._publicar, not (activo and self.selec))
        self._boton(fila, 'Más opciones', '🔧', discord.ButtonStyle.secondary, self._mas)
        self._boton(fila, 'Cerrar', '✖️', discord.ButtonStyle.secondary, self._cerrar)
        contenedor.add_item(fila)

    def _montar_mas(self, contenedor: discord.ui.Container, activo: bool):
        contenedor.add_item(discord.ui.TextDisplay('### 🔧 Más opciones'))

        opciones = [discord.SelectOption(label='Todas las plazas a la vez', value='todas', emoji='🎯')]
        for s in self.selec:
            opciones.append(discord.SelectOption(
                label=f'#{s["posicion"]} {s["gobernador"]} — 🎯 {fmt_poder(s["poder"])}'[:100], value=str(s['posicion']),
                emoji=MEDALLAS[s['posicion'] - 1] if s['posicion'] <= 3 else None,
            ))
        sel_meta = discord.ui.Select(placeholder='🎯 Cambiar la meta de…', options=opciones[:25],
                                     disabled=not (activo and self.selec))
        sel_meta.callback = self._elegir_meta
        contenedor.add_item(discord.ui.ActionRow(sel_meta))

        abierta = bool(self.ev['inscripcion_abierta'])
        fila = discord.ui.ActionRow()
        self._boton(fila, 'Inscribir externo', '➕', discord.ButtonStyle.secondary, self._externo, not activo)
        self._boton(fila, 'Cerrar inscripciones' if abierta else 'Reabrir inscripciones',
                    '🔒' if abierta else '🔓', discord.ButtonStyle.secondary, self._abrir_cerrar, not activo)
        self._boton(fila, 'Vaciar plazas', '🧹', discord.ButtonStyle.secondary, self._vaciar, not (activo and self.selec))
        contenedor.add_item(fila)

        fila = discord.ui.ActionRow()
        self._boton(fila, 'Volver', '⬅️', discord.ButtonStyle.primary, self._volver)
        self._boton(fila, '¿Seguro? Pulsa otra vez' if self.confirmar_final else 'Finalizar MGE',
                    '⚠️' if self.confirmar_final else '🏁', discord.ButtonStyle.danger, self._finalizar, not activo)
        self._boton(fila, 'Cerrar', '✖️', discord.ButtonStyle.secondary, self._cerrar)
        contenedor.add_item(fila)

    # ── Plazas ─────────────────────────────────────────────────────────────────

    async def _elegir(self, interaction: discord.Interaction, pos: int):
        valor    = interaction.data['values'][0]
        guild_id = str(interaction.guild_id)
        ocupante = next((s for s in self.selec if s['posicion'] == pos), None)
        meta_pos = ocupante['poder'] if ocupante else self.ev['poder_min']  # la meta va con la plaza
        aviso    = ''

        if valor == '__vacia__':
            if ocupante:
                await db.mge_quitar_seleccion(self.evento_id, ocupante['user_id'])
                aviso = f'⬜ Plaza #{pos} vacía · **{ocupante["gobernador"]}** vuelve a la espera'
        elif not ocupante or valor != ocupante['user_id']:
            ins    = next(i for i in self.inscritos if i['user_id'] == valor)
            previa = self._plaza_de(valor)
            await db.mge_seleccionar(self.evento_id, guild_id, valor, ins['gobernador'], meta_pos, pos)
            aviso = f'{medalla(pos)} **{ins["gobernador"]}** → plaza #{pos}'
            if previa and ocupante:
                # Intercambio: el que estaba aquí pasa a la plaza que deja libre el elegido
                await db.mge_seleccionar(self.evento_id, guild_id, ocupante['user_id'], ocupante['gobernador'],
                                         previa['poder'], previa['posicion'])
                aviso += f' · 🔁 **{ocupante["gobernador"]}** pasa a la #{previa["posicion"]}'
            elif ocupante:
                aviso += f' · **{ocupante["gobernador"]}** vuelve a la espera'

        programar_refresco(interaction.client, self.evento_id)
        await self.render(interaction, aviso)

    async def _anterior(self, interaction: discord.Interaction):
        self.pagina -= 1
        await self.render(interaction)

    async def _siguiente(self, interaction: discord.Interaction):
        self.pagina += 1
        await self.render(interaction)

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

        guild    = interaction.guild
        canal    = None
        canal_id = await db.get_config(str(guild.id), 'mge_canal_resultados')
        if canal_id:
            canal = guild.get_channel(int(canal_id))
        canal = canal or buscar_canal(guild, 'mge-resultados') or interaction.channel
        await canal.send(content=menciones or None, embed=embed)

        # Los MD se mandan en segundo plano para no hacer esperar al panel
        en_segundo_plano(enviar_mds(guild, ev['nombre'], list(self.selec)))
        await self.render(interaction, f'📢 Lista publicada en {canal.mention} · enviando MD a los seleccionados')

    # ── Más opciones ───────────────────────────────────────────────────────────

    async def _mas(self, interaction: discord.Interaction):
        self.modo = 'mas'
        await self.render(interaction)

    async def _volver(self, interaction: discord.Interaction):
        self.modo            = 'plazas'
        self.confirmar_final = False
        await self.render(interaction)

    async def _elegir_meta(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MetaModal(self, interaction.data['values'][0]))

    async def _externo(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ExternoModal(self))

    async def _abrir_cerrar(self, interaction: discord.Interaction):
        abrir = not self.ev['inscripcion_abierta']
        await db.mge_set_inscripcion_abierta(self.evento_id, abrir)
        programar_refresco(interaction.client, self.evento_id)
        await self.render(interaction, '🔓 Inscripciones reabiertas' if abrir else '🔒 Inscripciones cerradas')

    async def _vaciar(self, interaction: discord.Interaction):
        n = await db.mge_vaciar_seleccion(self.evento_id)
        programar_refresco(interaction.client, self.evento_id)
        await self.render(interaction, f'🧹 {n} plazas vaciadas; todos vuelven a la lista de espera.')

    async def _finalizar(self, interaction: discord.Interaction):
        if not self.confirmar_final:
            self.confirmar_final = True
            await self.render(interaction, '⚠️ Al finalizar, el tablón se congela y pasa al historial. Pulsa otra vez para confirmar.')
            return
        await db.mge_set_inscripcion_abierta(self.evento_id, False)
        await db.mge_cerrar_evento(str(interaction.guild_id), self.evento_id)
        programar_refresco(interaction.client, self.evento_id)
        self.modo = 'plazas'
        await self.render(interaction, '🏁 MGE finalizado. Ya aparece en `/mge-historial`.')
        self.stop()

    async def _cerrar(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            cerrado = discord.ui.LayoutView()
            cerrado.add_item(discord.ui.TextDisplay('✅ Panel cerrado.'))
            await interaction.edit_original_response(view=cerrado)


async def enviar_mds(guild: discord.Guild, nombre_mge: str, seleccionados: list):
    """Avisa por MD a cada seleccionado con su plaza y su meta."""
    for s in seleccionados:
        if es_externo(s['user_id']):
            continue
        miembro = guild.get_member(int(s['user_id']))
        if not miembro:
            continue
        try:
            await miembro.send(
                f'🏆 **{nombre_mge}** · {ALIANZA_TAG}\n'
                f'Tienes la plaza {medalla(s["posicion"])} con meta 🎯 **{fmt_poder(s["poder"])}**. ¡A por ello! 🔥\n'
                f'_You got slot #{s["posicion"]} with a **{fmt_poder(s["poder"])}** target. Go for it!_'
            )
        except discord.HTTPException:
            pass


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
