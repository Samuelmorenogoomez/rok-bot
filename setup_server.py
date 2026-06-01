"""
Script de configuración del servidor — Hermandad del Fuego | K2318
Ejecutar una vez para crear toda la estructura. Seguro de re-ejecutar.

Uso:
    python setup_server.py
"""

import asyncio
import os
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN    = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', '0'))

GUILD_NAME = '🔥 Hermandad del Fuego | K2318'

# (nombre, color, mentionable, hoist, permissions)
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


async def setup():
    if not TOKEN:
        print('❌ No encontré DISCORD_TOKEN en el .env')
        return
    if not GUILD_ID:
        print('❌ No encontré GUILD_ID en el .env')
        return

    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f'\n✅ Conectado como {client.user}')
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f'❌ No encontré el servidor {GUILD_ID}')
            await client.close()
            return

        print(f'   Servidor: {guild.name}\n')
        everyone = guild.default_role

        # ── Renombrar servidor ─────────────────────────────────────────────────
        if guild.name != GUILD_NAME:
            await guild.edit(name=GUILD_NAME)
            print(f'✅ Servidor renombrado → {GUILD_NAME}\n')

        # ── Roles ──────────────────────────────────────────────────────────────
        print('📋 Roles...')
        roles_map = {r.name: r for r in guild.roles}

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
                print(f'   ✅ {nombre}')
                await asyncio.sleep(0.5)
            else:
                print(f'   ⏭️  {nombre} (ya existe)')

        liderazgo = roles_map.get('👑 Liderazgo')
        r4        = roles_map.get('⚔️ R4')
        r3        = roles_map.get('🛡️ R3')
        miembro   = roles_map.get('🌿 Miembro')
        nuevo     = roles_map.get('🔰 Nuevo')

        # ── Función de permisos ────────────────────────────────────────────────
        def ow(tipo: str) -> dict:
            base = {everyone: discord.PermissionOverwrite(view_channel=False)}

            if tipo == 'stats':
                for rol in guild.roles:
                    base[rol] = discord.PermissionOverwrite(view_channel=True, connect=False)
                base[everyone] = discord.PermissionOverwrite(view_channel=True, connect=False)

            elif tipo == 'info':
                for rol in [nuevo, miembro, r3]:
                    if rol:
                        base[rol] = discord.PermissionOverwrite(
                            view_channel=True, send_messages=False, read_message_history=True,
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
                pass  # solo liderazgo y r4 abajo

            for rol in [liderazgo, r4]:
                if rol:
                    base[rol] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True,
                        manage_messages=True, connect=True, speak=True,
                    )

            return base

        # ── Categorías y canales ───────────────────────────────────────────────
        cats_map    = {c.name: c for c in guild.categories}
        canales_map = {c.name: c for c in guild.channels}

        for bloque in ESTRUCTURA:
            nombre_cat = bloque['categoria']
            print(f'\n📁 {nombre_cat}')

            if nombre_cat not in cats_map:
                cat = await guild.create_category(
                    nombre_cat,
                    overwrites={everyone: discord.PermissionOverwrite(view_channel=False)},
                )
                cats_map[nombre_cat] = cat
                print(f'   ✅ Categoría creada')
            else:
                cat = cats_map[nombre_cat]
                await cat.edit(overwrites={everyone: discord.PermissionOverwrite(view_channel=False)})
                print(f'   🔄 Categoría actualizada')

            await asyncio.sleep(0.3)

            for nombre_canal, tipo_canal, tipo_perms in bloque['canales']:
                permisos = ow(tipo_perms)
                if nombre_canal not in canales_map:
                    if tipo_canal == 'text':
                        await guild.create_text_channel(nombre_canal, category=cat, overwrites=permisos)
                    else:
                        await guild.create_voice_channel(nombre_canal, category=cat, overwrites=permisos)
                    print(f'   ✅ #{nombre_canal}')
                else:
                    await canales_map[nombre_canal].edit(overwrites=permisos)
                    print(f'   🔄 #{nombre_canal}')
                await asyncio.sleep(0.5)

        print('\n' + '─' * 50)
        print('✅ Servidor configurado correctamente.')
        print('\nPróximos pasos:')
        print('  1. Asígna el rol 🔧 Admin Discord a tu usuario en Discord')
        print('  2. Arranca el bot:  python bot.py')
        print('  3. En Discord ejecuta:')
        print('       /panel-titulos  #🏰│cola-titulos')
        print('       /stats-setup    [categoría 📊 ESTADÍSTICAS]')
        print('       /inicializar-mensajes')
        print('       /config-bienvenida  #🎉│bienvenida')
        print('       /canal-eventos      #📅│calendario')
        print('       /kvk-canal-recap    #📢│kvk-anuncios')
        print('─' * 50)

        await client.close()

    await client.start(TOKEN)


if __name__ == '__main__':
    asyncio.run(setup())
