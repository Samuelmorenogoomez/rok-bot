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
    '👥 Miembros: ...':    'stats_total',
    '🌿 Registrados: ...': 'stats_registrados',
    '💪 Poder: ...':       'stats_poder',
    '⚔️ KvK: ...':         'stats_kvk',
}

ESTRUCTURA = [
    {
        'categoria': '📊 ESTADÍSTICAS',
        'canales': [
            ('👥 Miembros: ...',    'voice', 'stats'),
            ('🌿 Registrados: ...',  'voice', 'stats'),
            ('💪 Poder: ...',       'voice', 'stats'),
            ('⚔️ KvK: ...',         'voice', 'stats'),
        ],
    },
    {
        'categoria': '📋 INFORMACIÓN',
        'canales': [
            ('📢│anuncios',         'text',  'info'),
            ('📜│reglas',           'text',  'info'),
            ('🤖│comandos-bot',     'text',  'info'),
            ('🎉│bienvenida',       'text',  'info'),
            ('⚔️│reclutamiento',   'text',  'info'),
        ],
    },
    {
        'categoria': '🏰 ALIANZA',
        'canales': [
            ('💬│chat-general',      'text',  'normal'),
            ('📣│avisos-alianza',    'text',  'info'),
            ('📊│estadisticas',      'text',  'info'),
            ('🎙️│voz-general',       'voice', 'normal'),
        ],
    },
    {
        'categoria': '⚔️ GUERRA',
        'canales': [
            ('🚨│alertas-guerra',    'text',  'normal'),
            ('🗺️│scouting',          'text',  'normal'),
            ('🚩│coordinacion',      'text',  'normal'),
            ('🎙️│voz-guerra',        'voice', 'normal'),
        ],
    },
    {
        'categoria': '⚔️ KVK',
        'canales': [
            ('📢│kvk-anuncios',      'text',  'info'),
            ('💬│kvk-general',       'text',  'normal'),
            ('🗺️│kvk-scouting',      'text',  'normal'),
            ('📋│kvk-bajas',         'text',  'normal'),
            ('🎙️│kvk-coordinacion',  'voice', 'normal'),
            ('🎙️│kvk-equipo-1',      'voice', 'normal'),
            ('🎙️│kvk-equipo-2',      'voice', 'normal'),
            ('🎙️│kvk-equipo-3',      'voice', 'normal'),
        ],
    },
    {
        'categoria': '🏹 ARK OF OSIRIS',
        'canales': [
            ('📢│ark-anuncios',      'text',  'info'),
            ('💬│ark-general',       'text',  'normal'),
            ('📋│ark-estrategia',    'text',  'normal'),
            ('🎙️│ark-equipo-a',      'voice', 'normal'),
            ('🎙️│ark-equipo-b',      'voice', 'normal'),
            ('🎙️│ark-equipo-c',      'voice', 'normal'),
            ('🎙️│ark-equipo-d',      'voice', 'normal'),
        ],
    },
    {
        'categoria': '📅 EVENTOS',
        'canales': [
            ('📅│calendario',        'text',  'info'),
            ('💬│eventos-general',   'text',  'normal'),
            ('📊│encuestas-fechas',  'text',  'normal'),
            ('🎙️│eventos-voz',       'voice', 'normal'),
        ],
    },
    {
        'categoria': '🤖 BOT',
        'canales': [
            ('🏰│cola-titulos',      'text',  'normal'),
            ('📅│encuestas',         'text',  'normal'),
            ('⚔️│kvk-stats',         'text',  'normal'),
            ('👥│miembros',          'text',  'registro'),
            ('🔍│comandantes',       'text',  'normal'),
            ('📝│mge-inscripciones', 'text',  'normal'),
            ('🏆│mge-resultados',    'text',  'info'),
        ],
    },
    {
        'categoria': '👑 ADMINISTRACIÓN',
        'canales': [
            ('🎛️│panel-control',     'text',  'admin'),
            ('📋│logs-bot',          'text',  'admin'),
            ('💬│chat-admin',        'text',  'admin'),
            ('🎙️│voz-admin',         'voice', 'admin'),
        ],
    },
]


def build_overwrites(tipo: str, roles_map: dict, everyone) -> dict:
    liderazgo = roles_map.get('👑 Liderazgo')
    r4        = roles_map.get('⚔️ R4')
    r3        = roles_map.get('🛡️ R3')
    miembro   = roles_map.get('🌿 Miembro')
    nuevo     = roles_map.get('🔰 Nuevo')

    base = {everyone: discord.PermissionOverwrite(view_channel=False)}

    if tipo == 'stats':
        for rol in roles_map.values():
            base[rol] = discord.PermissionOverwrite(view_channel=True, connect=False)
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


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name='setup-servidor',
        description='[ADMIN] Crea y actualiza todos los canales y roles del servidor'
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_servidor(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild    = interaction.guild
        everyone = guild.default_role

        roles_creados    = 0
        canales_creados  = 0
        actualizados     = 0
        roles_borrados   = 0
        canales_borrados = 0

        # ── Roles ─────────────────────────────────────────────────────────────
        roles_map = {r.name: r for r in guild.roles}
        nombres_roles_validos = {nombre for nombre, *_ in ROLES}

        for nombre, color, mentionable, hoist, perms in ROLES:
            if nombre not in roles_map:
                kwargs = dict(
                    name=nombre,
                    color=discord.Color(color),
                    mentionable=mentionable,
                    hoist=hoist,
                )
                if perms:
                    kwargs['permissions'] = perms
                r = await guild.create_role(**kwargs)
                roles_map[nombre] = r
                roles_creados += 1
                await asyncio.sleep(0.5)

        # Borrar roles que no son parte de la estructura
        # rol.managed = roles gestionados por integraciones (bots), no se pueden borrar
        for rol in list(guild.roles):
            if rol.name == '@everyone' or rol.managed:
                continue
            if rol.name not in nombres_roles_validos:
                try:
                    await rol.delete(reason='setup-servidor: limpieza')
                    roles_borrados += 1
                    await asyncio.sleep(0.3)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # ── Categorías y canales ───────────────────────────────────────────────
        cats_map    = {c.name: c for c in guild.categories}
        canales_map = {c.name: c for c in guild.channels}
        valid_channel_ids  = set()
        valid_category_ids = set()

        for bloque in ESTRUCTURA:
            nombre_cat = bloque['categoria']

            if nombre_cat not in cats_map:
                cat = await guild.create_category(
                    nombre_cat,
                    overwrites={everyone: discord.PermissionOverwrite(view_channel=False)},
                )
                cats_map[nombre_cat] = cat
            else:
                cat = cats_map[nombre_cat]
                await cat.edit(overwrites={everyone: discord.PermissionOverwrite(view_channel=False)})

            valid_category_ids.add(cat.id)
            await asyncio.sleep(0.3)

            for nombre_canal, tipo_canal, tipo_perms in bloque['canales']:
                ow = build_overwrites(tipo_perms, roles_map, everyone)

                # Canales de stats: su nombre cambia dinámicamente → buscar por ID guardado en BD
                clave_stat = STATS_CLAVES.get(nombre_canal)
                if clave_stat:
                    canal_id_guardado = await db.get_config(str(guild.id), clave_stat)
                    if canal_id_guardado:
                        c = guild.get_channel(int(canal_id_guardado))
                        if c:
                            await c.edit(overwrites=ow)
                            valid_channel_ids.add(c.id)
                            actualizados += 1
                            await asyncio.sleep(0.5)
                            continue

                # Búsqueda por nombre o creación
                if nombre_canal not in canales_map:
                    if tipo_canal == 'text':
                        c = await guild.create_text_channel(nombre_canal, category=cat, overwrites=ow)
                    else:
                        c = await guild.create_voice_channel(nombre_canal, category=cat, overwrites=ow)
                    canales_creados += 1
                else:
                    c = canales_map[nombre_canal]
                    await c.edit(overwrites=ow)
                    actualizados += 1

                valid_channel_ids.add(c.id)
                await asyncio.sleep(0.5)

        # ── Limpieza: borrar lo que no pertenece a la estructura ───────────────
        # Primero canales normales, luego categorías
        for canal in list(guild.channels):
            if isinstance(canal, discord.CategoryChannel):
                continue
            if canal.id not in valid_channel_ids:
                try:
                    await canal.delete(reason='setup-servidor: limpieza')
                    canales_borrados += 1
                    await asyncio.sleep(0.3)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        for canal in list(guild.channels):
            if not isinstance(canal, discord.CategoryChannel):
                continue
            if canal.id not in valid_category_ids:
                try:
                    await canal.delete(reason='setup-servidor: limpieza')
                    canales_borrados += 1
                    await asyncio.sleep(0.3)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        await guild.edit(name=GUILD_NAME, reason='setup-servidor: nombre de alianza')

        embed = discord.Embed(title='✅ Servidor configurado', color=COLOR_BOT)
        embed.add_field(name='Roles creados',          value=str(roles_creados),    inline=True)
        embed.add_field(name='Canales creados',         value=str(canales_creados),  inline=True)
        embed.add_field(name='Permisos actualizados',   value=str(actualizados),     inline=True)
        embed.add_field(name='🗑️ Roles eliminados',    value=str(roles_borrados),   inline=True)
        embed.add_field(name='🗑️ Canales eliminados',  value=str(canales_borrados), inline=True)
        embed.set_footer(text='Asigna el rol 👑 Liderazgo a tu usuario para tener acceso completo.')
        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup_servidor.error
    async def setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ Necesitas ser Administrador.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
