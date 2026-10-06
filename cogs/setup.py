import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, GUILD_NAME
from db import database as db

# Tupla: (nombre, color, mentionable, hoist, permissions)
# permissions=None → permisos por defecto heredados del servidor
ROLES = [
    ('🔧 Admin Discord',   0xFF2222, True,  True,  discord.Permissions(administrator=True)),
    ('👑 Liderazgo',       0xFFD700, True,  True,  None),
    ('⚔️ R4',              0xFF8C00, True,  True,  None),
    ('🛡️ R3',              0x4169E1, True,  True,  None),
    ('⚔️ Capitán KvK',     0xE74C3C, True,  True,  None),
    ('🏹 Organizador Ark', 0x9B59B6, True,  True,  None),
    ('🌿 Miembro',         0x2ECC71, True,  False, None),
    ('🔰 Nuevo',           0x95A5A6, True,  False, None),
    ('🗡️ Infantería',      0xC0392B, False, False, None),
    ('🐴 Caballería',      0x8E44AD, False, False, None),
    ('🏹 Arqueros',        0x27AE60, False, False, None),
    ('⚙️ Maquinaria',      0xE67E22, False, False, None),
    ('🔱 Mixto',           0x1ABC9C, False, False, None),
    ('⚔️ Guerra',          0xFF0000, True,  False, None),
    ('📢 Anuncios',        0x3498DB, False, False, None),
]

# Canales de stats: sus nombres cambian dinámicamente → los buscamos por clave en config_general
STATS_CLAVES = {
    '👥 Miembros: ...': 'stats_total',
    '💪 Poder: ...':    'stats_poder',
    '⚔️ KvK: ...':      'stats_kvk',
}

ESTRUCTURA = [
    {
        'categoria': '📊 ESTADÍSTICAS',
        'canales': [
            ('👥 Miembros: ...', 'voice', 'stats'),
            ('💪 Poder: ...',    'voice', 'stats'),
            ('⚔️ KvK: ...',      'voice', 'stats'),
        ],
    },
    {
        'categoria': '📋 INFORMACIÓN',
        'canales': [
            ('📢│anuncios',      'text', 'info'),
            ('🎉│bienvenida',    'text', 'info'),   # bienvenida + reglas + guía del bot
            ('⚔️│reclutamiento', 'text', 'info'),
        ],
    },
    {
        'categoria': '🏰 ALIANZA',
        'canales': [
            ('💬│chat-general',  'text',  'normal'),
            ('👥│miembros',      'text',  'registro'),
            ('📅│calendario',    'text',  'info'),
            ('📊│encuestas',     'text',  'normal'),
            ('📝│mge',           'text',  'info'),   # tablones e inscripción con botones + lista final
            ('🎙️│voz-general',   'voice', 'normal'),
        ],
    },
    {
        'categoria': '⚔️ KVK Y GUERRA',
        'canales': [
            ('📢│kvk-anuncios',  'text',  'info'),
            ('💬│kvk-chat',      'text',  'normal'),
            ('🗺️│scouting',      'text',  'normal'),
            ('📊│kvk-stats',     'text',  'normal'),
            ('🎙️│voz-guerra',    'voice', 'normal'),
            ('🎙️│equipo-1',      'voice', 'normal'),
            ('🎙️│equipo-2',      'voice', 'normal'),
        ],
    },
    {
        'categoria': '🏹 ARK OF OSIRIS',
        'canales': [
            ('💬│ark',           'text',  'normal'),
            ('🎙️│ark-voz',       'voice', 'normal'),
        ],
    },
    {
        'categoria': '👑 ADMINISTRACIÓN',
        'canales': [
            ('💬│chat-admin',    'text',  'admin'),
            ('🎙️│voz-admin',     'voice', 'admin'),
        ],
    },
]

# Canales antiguos que pasan a ser uno de la estructura nueva: se renombran y mueven
# (así conservan su historial, sus mensajes anclados y los IDs que tenga guardados el bot)
RENOMBRAR = {
    '📝│mge-inscripciones': '📝│mge',
    '💬│kvk-general':       '💬│kvk-chat',
    '⚔️│kvk-stats':         '📊│kvk-stats',
    '🎙️│kvk-equipo-1':      '🎙️│equipo-1',
    '🎙️│kvk-equipo-2':      '🎙️│equipo-2',
    '💬│ark-general':       '💬│ark',
    '🎙️│ark-equipo-a':      '🎙️│ark-voz',
    '📅│encuestas':         '📊│encuestas',
}

CATEGORIA_ARCHIVO = '🗄️ ARCHIVO'


def build_overwrites(tipo: str, roles_map: dict, everyone) -> dict:
    liderazgo = roles_map.get('👑 Liderazgo')
    r4        = roles_map.get('⚔️ R4')
    r3        = roles_map.get('🛡️ R3')
    miembro   = roles_map.get('🌿 Miembro')
    nuevo     = roles_map.get('🔰 Nuevo')

    base = {everyone: discord.PermissionOverwrite(view_channel=False)}

    if tipo == 'stats':
        # Visibles para todos, pero nadie puede entrar: solo muestran el dato
        base[everyone] = discord.PermissionOverwrite(view_channel=True, connect=False)

    elif tipo == 'info':
        for rol in [nuevo, miembro, r3]:
            if rol:
                base[rol] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=False, read_message_history=True
                )

    elif tipo == 'registro':
        for rol in [nuevo, miembro, r3]:
            if rol:
                base[rol] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    read_message_history=True, use_application_commands=True,
                )

    elif tipo == 'normal':
        for rol in [miembro, r3]:
            if rol:
                base[rol] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    read_message_history=True, add_reactions=True,
                    connect=True, speak=True, use_application_commands=True,
                )

    elif tipo == 'admin':
        pass  # solo liderazgo y r4 que se añaden abajo

    for rol in [liderazgo, r4]:
        if rol:
            base[rol] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_messages=True, connect=True, speak=True,
            )

    return base


def es_rol_sobrante(rol: discord.Role, guild: discord.Guild) -> bool:
    nombres_validos = {nombre for nombre, *_ in ROLES}
    return (not rol.is_default() and not rol.managed and rol.name not in nombres_validos
            and rol < guild.me.top_role)


# ── Limpieza con confirmación ─────────────────────────────────────────────────

class LimpiezaView(discord.ui.View):
    """Lo que sobra tras /setup-servidor: se puede ocultar, borrar o dejar como está."""

    def __init__(self, canales: list[int], categorias: list[int], roles: list[int]):
        super().__init__(timeout=600)
        self.canales    = canales
        self.categorias = categorias
        self.roles      = roles
        self.confirmar  = None  # 'canales' o 'roles' cuando falta el segundo clic
        self._pintar()

    def _pintar(self):
        self.clear_items()
        if self.canales:
            self._boton(f'Ocultar {len(self.canales)} canales', '🙈', discord.ButtonStyle.primary, self._ocultar)
            self._boton('¿Seguro? Se pierde el historial' if self.confirmar == 'canales'
                        else f'Borrar {len(self.canales)} canales', '🗑️', discord.ButtonStyle.danger, self._borrar_canales)
        if self.roles:
            self._boton('¿Seguro? Pulsa otra vez' if self.confirmar == 'roles'
                        else f'Borrar {len(self.roles)} roles', '🗑️', discord.ButtonStyle.danger, self._borrar_roles)
        self._boton('Dejar así', '✋', discord.ButtonStyle.secondary, self._dejar)

    def _boton(self, label, emoji, style, callback):
        boton = discord.ui.Button(label=label, emoji=emoji, style=style)
        boton.callback = callback
        self.add_item(boton)

    async def _actualizar(self, interaction: discord.Interaction, texto: str):
        self._pintar()
        if not self.canales and not self.roles:
            self.stop()
            await interaction.edit_original_response(content=texto, view=None)
        else:
            await interaction.edit_original_response(content=texto, view=self)

    async def _borrar_categorias_vacias(self, guild: discord.Guild):
        for cat_id in self.categorias:
            cat = guild.get_channel(cat_id)
            if cat and not cat.channels:
                try:
                    await cat.delete(reason='setup-servidor: categoría vacía')
                except discord.HTTPException:
                    pass

    async def _ocultar(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content='🙈 Ocultando…', view=None)
        guild     = interaction.guild
        roles_map = {r.name: r for r in guild.roles}
        archivo   = discord.utils.get(guild.categories, name=CATEGORIA_ARCHIVO)
        if not archivo:
            ow = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
            for nombre in ('👑 Liderazgo', '⚔️ R4'):
                if roles_map.get(nombre):
                    ow[roles_map[nombre]] = discord.PermissionOverwrite(view_channel=True)
            archivo = await guild.create_category(CATEGORIA_ARCHIVO, overwrites=ow, position=len(guild.categories))
        movidos = 0
        for canal_id in self.canales:
            canal = guild.get_channel(canal_id)
            if not canal:
                continue
            try:
                await canal.edit(category=archivo, sync_permissions=True, reason='setup-servidor: archivado')
                movidos += 1
                await asyncio.sleep(0.4)
            except discord.HTTPException:
                pass
        await self._borrar_categorias_vacias(guild)
        self.canales, self.confirmar = [], None
        await self._actualizar(interaction, f'🙈 {movidos} canales movidos a **{CATEGORIA_ARCHIVO}** '
                                            '(solo los ve el liderazgo). Cuando nadie los eche de menos, '
                                            'vuelve a usar `/setup-servidor` para borrarlos.')

    async def _borrar_canales(self, interaction: discord.Interaction):
        if self.confirmar != 'canales':
            self.confirmar = 'canales'
            self._pintar()
            await interaction.response.edit_message(view=self)
            return
        await interaction.response.edit_message(content='🗑️ Borrando…', view=None)
        guild   = interaction.guild
        borrados = 0
        for canal_id in self.canales:
            canal = guild.get_channel(canal_id)
            if not canal:
                continue
            try:
                await canal.delete(reason='setup-servidor: limpieza')
                borrados += 1
                await asyncio.sleep(0.3)
            except discord.HTTPException:
                pass
        await self._borrar_categorias_vacias(guild)
        archivo = discord.utils.get(guild.categories, name=CATEGORIA_ARCHIVO)
        if archivo and not archivo.channels:
            await archivo.delete(reason='setup-servidor: archivo vacío')
        self.canales, self.confirmar = [], None
        await self._actualizar(interaction, f'🗑️ {borrados} canales borrados.')

    async def _borrar_roles(self, interaction: discord.Interaction):
        if self.confirmar != 'roles':
            self.confirmar = 'roles'
            self._pintar()
            await interaction.response.edit_message(view=self)
            return
        await interaction.response.edit_message(content='🗑️ Borrando roles…', view=None)
        borrados = 0
        for rol_id in self.roles:
            rol = interaction.guild.get_role(rol_id)
            if not rol:
                continue
            try:
                await rol.delete(reason='setup-servidor: limpieza')
                borrados += 1
                await asyncio.sleep(0.3)
            except discord.HTTPException:
                pass
        self.roles, self.confirmar = [], None
        await self._actualizar(interaction, f'🗑️ {borrados} roles borrados.')

    async def _dejar(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(content='✋ No se ha tocado nada de lo que sobra.', view=None)


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name='setup-servidor',
        description='[ADMIN] Crea y ordena canales y roles; lo que sobre te pregunta antes de tocarlo'
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_servidor(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild    = interaction.guild
        everyone = guild.default_role

        roles_creados    = 0
        canales_creados  = 0
        renombrados      = 0
        actualizados     = 0

        # ── Roles ─────────────────────────────────────────────────────────────
        roles_map = {r.name: r for r in guild.roles}
        for nombre, color, mentionable, hoist, perms in ROLES:
            if nombre not in roles_map:
                kwargs = dict(name=nombre, color=discord.Color(color), mentionable=mentionable, hoist=hoist)
                if perms:
                    kwargs['permissions'] = perms
                roles_map[nombre] = await guild.create_role(**kwargs)
                roles_creados += 1
                await asyncio.sleep(0.5)

        # ── Categorías y canales ───────────────────────────────────────────────
        cats_map    = {c.name: c for c in guild.categories}
        canales_map = {c.name: c for c in guild.channels if not isinstance(c, discord.CategoryChannel)}
        antiguo_de  = {nuevo: viejo for viejo, nuevo in RENOMBRAR.items()}
        valid_channel_ids  = set()
        valid_category_ids = set()

        for bloque in ESTRUCTURA:
            nombre_cat = bloque['categoria']
            if nombre_cat not in cats_map:
                cats_map[nombre_cat] = await guild.create_category(
                    nombre_cat, overwrites={everyone: discord.PermissionOverwrite(view_channel=False)},
                )
            else:
                await cats_map[nombre_cat].edit(overwrites={everyone: discord.PermissionOverwrite(view_channel=False)})
            cat = cats_map[nombre_cat]
            valid_category_ids.add(cat.id)
            await asyncio.sleep(0.3)

            for nombre_canal, tipo_canal, tipo_perms in bloque['canales']:
                ow = build_overwrites(tipo_perms, roles_map, everyone)

                # Canales de stats: su nombre cambia → se buscan por el ID guardado en BD
                clave_stat = STATS_CLAVES.get(nombre_canal)
                if clave_stat:
                    canal_id = await db.get_config(str(guild.id), clave_stat)
                    c = guild.get_channel(int(canal_id)) if canal_id else None
                    if c:
                        await c.edit(category=cat, overwrites=ow)
                        actualizados += 1
                    else:
                        c = await guild.create_voice_channel(nombre_canal, category=cat, overwrites=ow)
                        await db.set_config(str(guild.id), clave_stat, str(c.id))
                        canales_creados += 1
                    valid_channel_ids.add(c.id)
                    await asyncio.sleep(0.5)
                    continue

                c = canales_map.get(nombre_canal)
                viejo = antiguo_de.get(nombre_canal)
                if not c and viejo and viejo in canales_map:
                    c = canales_map[viejo]
                    await c.edit(name=nombre_canal, category=cat, overwrites=ow, reason='setup-servidor: fusión')
                    renombrados += 1
                elif not c:
                    if tipo_canal == 'text':
                        c = await guild.create_text_channel(nombre_canal, category=cat, overwrites=ow)
                    else:
                        c = await guild.create_voice_channel(nombre_canal, category=cat, overwrites=ow)
                    canales_creados += 1
                else:
                    await c.edit(category=cat, overwrites=ow)
                    actualizados += 1
                valid_channel_ids.add(c.id)
                await asyncio.sleep(0.5)

        if guild.name != GUILD_NAME:
            await guild.edit(name=GUILD_NAME, reason='setup-servidor: nombre de alianza')

        # ── Lo que sobra: se pregunta antes de tocarlo ────────────────────────
        sobrantes = [c for c in guild.channels
                     if not isinstance(c, discord.CategoryChannel) and c.id not in valid_channel_ids]
        cats_sobrantes = [c.id for c in guild.categories
                          if c.id not in valid_category_ids and c.name != CATEGORIA_ARCHIVO]
        roles_sobrantes = [r for r in guild.roles if es_rol_sobrante(r, guild)]

        embed = discord.Embed(title='✅ Servidor configurado', color=COLOR_BOT)
        embed.add_field(name='Roles creados',        value=str(roles_creados),   inline=True)
        embed.add_field(name='Canales creados',      value=str(canales_creados), inline=True)
        embed.add_field(name='Renombrados/fusionados', value=str(renombrados),   inline=True)
        embed.add_field(name='Permisos actualizados', value=str(actualizados),   inline=True)
        if sobrantes:
            lista = ', '.join(f'`{c.name}`' for c in sobrantes)
            embed.add_field(name=f'📦 Canales que ya no están en la estructura ({len(sobrantes)})',
                            value=lista[:1020], inline=False)
        if roles_sobrantes:
            lista = ', '.join(f'`{r.name}`' for r in roles_sobrantes)
            embed.add_field(name=f'🏷️ Roles que no están en la lista ({len(roles_sobrantes)})',
                            value=lista[:1020], inline=False)
        embed.set_footer(text='Asigna el rol 👑 Liderazgo a tu usuario para tener acceso completo.')

        if sobrantes or roles_sobrantes:
            vista = LimpiezaView([c.id for c in sobrantes], cats_sobrantes, [r.id for r in roles_sobrantes])
            await interaction.followup.send(
                content='¿Qué hago con lo que sobra? **Ocultar** lo mueve a 🗄️ ARCHIVO (solo lo ve el liderazgo '
                        'y se puede recuperar). **Borrar** no se puede deshacer.',
                embed=embed, view=vista, ephemeral=True,
            )
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @setup_servidor.error
    async def setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ Necesitas ser Administrador.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
