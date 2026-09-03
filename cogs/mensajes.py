import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, ALIANZA_NOMBRE, ALIANZA_TAG, ALIANZA_FULL, REINO

# ── Contenido de cada canal ────────────────────────────────────────────────────

async def msg_bienvenida(canal: discord.TextChannel, guild: discord.Guild):
    canal_miembros = next((c.id for c in guild.channels if 'miembros' in c.name), 0)
    embed = discord.Embed(
        title=f'🔥 ¡Bienvenido a {ALIANZA_FULL}! / Welcome to {ALIANZA_FULL}!',
        description=(
            f'Has llegado al servidor oficial de la alianza **{ALIANZA_NOMBRE}** '
            f'del **Reino {REINO}**.\n'
            f'_You have joined the official server of **{ALIANZA_NOMBRE}**, **Kingdom {REINO}**._\n\n'
            f'Para acceder al servidor completo debes **registrarte** con tu perfil de gobernador.\n'
            f'_To access the full server you must **register** your governor profile._\n\n'
            f'**¿Cómo empezar? / How to start?**\n'
            f'1. Ve al canal <#{canal_miembros}> y usa `/registrar`\n'
            f'   _Go to <#{canal_miembros}> and use `/registrar`_\n'
            f'2. Introduce tu nombre de gobernador, poder y tipo de tropa\n'
            f'   _Enter your governor name, power and troop type_\n'
            f'3. El bot te asignará tu rol y tendrás acceso completo\n'
            f'   _The bot will assign your role and you will have full access_'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Una vez registrado tendrás acceso a / Once registered you will have access to',
        value=(
            '🔥 Coordinación de guerra y KvK / War and KvK coordination\n'
            '🏹 Ark of Osiris y estrategia / Ark of Osiris and strategy\n'
            '📅 Eventos y encuestas de la alianza / Alliance events and polls\n'
            '🏰 Cola de títulos del reino / Kingdom title queue\n'
            '🔍 Guías de comandantes y equipamiento / Commander and equipment guides'
        ),
        inline=False,
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f'{ALIANZA_TAG} · Reino / Kingdom {REINO}')
    return await canal.send(embed=embed)


async def msg_reglas(canal: discord.TextChannel):
    embed = discord.Embed(
        title=f'📜 Reglas de {ALIANZA_NOMBRE} / Rules of {ALIANZA_NOMBRE}',
        description=f'*{ALIANZA_TAG} · Reino {REINO}*',
        color=0xFF4444,
    )
    embed.add_field(
        name='1. 🤝 Respeto / Respect',
        value=(
            'Trato respetuoso con todos los miembros. Cero toxicidad ni insultos.\n'
            '_Respectful treatment of all members. Zero toxicity or insults._'
        ),
        inline=False,
    )
    embed.add_field(
        name='2. ⚡ Actividad / Activity',
        value=(
            'Se espera participación en KvK y Ark of Osiris. Avisa si vas a estar inactivo.\n'
            '_Participation in KvK and Ark of Osiris is expected. Let us know if you will be inactive._'
        ),
        inline=False,
    )
    embed.add_field(
        name='3. 🚩 Coordinación / Coordination',
        value=(
            'Sigue las órdenes del liderazgo en eventos de guerra. La coordinación es clave para ganar.\n'
            '_Follow leadership orders in war events. Coordination is key to winning._'
        ),
        inline=False,
    )
    embed.add_field(
        name='4. 💰 Donaciones / Donations',
        value=(
            'Dona recursos a la alianza regularmente para mantener los edificios activos.\n'
            '_Donate resources to the alliance regularly to keep buildings active._'
        ),
        inline=False,
    )
    embed.add_field(
        name='5. 📡 Comunicación / Communication',
        value=(
            'Usa los canales correctos. Reporta actividad enemiga en el canal de scouting.\n'
            '_Use the correct channels. Report enemy activity in the scouting channel._'
        ),
        inline=False,
    )
    embed.add_field(
        name='6. 🤖 Uso del bot / Bot usage',
        value=(
            'Usa los comandos del bot en sus canales correspondientes para no saturar el chat general.\n'
            '_Use bot commands in their corresponding channels to keep general chat clean._'
        ),
        inline=False,
    )
    embed.set_footer(text='El incumplimiento reiterado puede resultar en expulsión. / Repeated violations may result in expulsion.')
    return await canal.send(embed=embed)


async def msg_comandos_bot(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🤖 Guía de Comandos del Bot / Bot Command Guide',
        description=f'Lista completa de comandos · _Full command list_ · *{ALIANZA_TAG} Reino {REINO}*',
        color=COLOR_BOT,
    )
    embed.add_field(
        name='👥 Canal de Miembros / Members Channel',
        value=(
            '`/registrar` — Regístrate / _Register your governor, power and troop_\n'
            '`/perfil [@usuario]` — Tu perfil o el de otro / _Your profile or another member\'s_\n'
            '`/miembros` — Lista por poder / _List all members by power_\n'
            '`/ausente [días] [motivo]` — Avisa inactividad / _Report inactivity_\n'
            '`/volver` — Cancela tu ausencia / _Cancel your absence_'
        ),
        inline=False,
    )
    embed.add_field(
        name='🏰 Cola de Títulos / Title Queue',
        value=(
            '`/pedir` — Pide un título / _Request a title (Duke, Architect, Scientist...)_\n'
            '`/cola` — Ver la cola / _See who is waiting_\n'
            '`/cancelar` — Sal de la cola / _Leave the queue_'
        ),
        inline=False,
    )
    embed.add_field(
        name='🔍 Canal de Comandantes / Commanders Channel',
        value=(
            '`/comandante [nombre]` — Info y equipo / _Info and equipment_\n'
            '`/comandantes-lista` — Lista por tropa y tier / _List by troop and tier_\n'
            '`/equipo [tropa] [rol] [fase]` — Equipamiento / _Equipment by troop and phase_\n'
            '`/mi-equipo` — Tu equipamiento / _Your equipment_'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚔️ Canal de KvK / KvK Channel',
        value=(
            '`/kvk-importar` — Importa Excel de heroscroll.com / _Import Excel from heroscroll.com_\n'
            '`/kvk-ranking` — Ranking de la temporada / _Season ranking_\n'
            '`/kvk-buscar [nombre]` — Stats de un gobernador / _Governor stats_'
        ),
        inline=False,
    )
    embed.add_field(
        name='📊 Canal de Encuestas / Polls Channel',
        value=(
            '`/encuesta` — Encuesta general / _General poll_\n'
            '`/fecha` — Votar fecha u hora / _Vote on a date or time_\n'
            '`/si-no` — Votación rápida Sí/No / _Quick Yes/No vote_'
        ),
        inline=False,
    )
    embed.add_field(
        name='📝 MGE Inscripciones / MGE Enrollment',
        value=(
            '`/mge-lista` — Ver MGEs activos / _See active MGEs_\n'
            '`/mge-inscribir` — Apuntarte / _Sign up for an MGE_\n'
            '`/mge-salir` — Cancelar inscripción / _Cancel enrollment_'
        ),
        inline=False,
    )
    embed.add_field(
        name='🌐 Traducción / Translation',
        value=(
            '`/traducir` — Traduce cualquier texto / _Translate any text_\n'
            '_También puedes reaccionar con una bandera a cualquier mensaje para traducirlo._\n'
            '_You can also react with a flag emoji to any message to translate it._'
        ),
        inline=False,
    )
    embed.set_footer(text='Los comandos solo funcionan en su canal correspondiente. / Commands only work in their corresponding channel.')
    return await canal.send(embed=embed)


async def msg_titulos(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🏰 Cola de Títulos del Reino / Kingdom Title Queue',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Los títulos otorgan **buffs temporales muy valiosos**. '
            'Pídelos **antes** de empezar a entrenar, construir o investigar.\n'
            '_Titles grant **very valuable temporary buffs**. '
            'Request them **before** you start training, building or researching._'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos / Commands',
        value=(
            '`/pedir` → Selecciona el título que necesitas / _Select the title you need_\n'
            '`/cola` → Ve quién está esperando / _See who is waiting and their position_\n'
            '`/cancelar` → Sal de la cola / _Leave the queue if you no longer need it_'
        ),
        inline=False,
    )
    embed.add_field(
        name='🎖️ Títulos disponibles / Available titles',
        value=(
            '⚔️ **Duke** — +10% velocidad de entrenamiento / _+10% troop training speed_\n'
            '🏗️ **Architect** — +10% velocidad de construcción / _+10% building speed_\n'
            '🔬 **Scientist** — +10% velocidad de investigación / _+10% research speed_\n'
            '⚕️ **Justice** — +10% velocidad de curación / _+10% healing speed_\n'
            '🛡️ **General** — Buffs de ataque y defensa / _Attack and defense buffs_'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚠️ Importante / Important',
        value=(
            'El título **no tiene efecto** si ya empezaste la acción.\n'
            '_The title **has no effect** if you already started the action._\n'
            'Pide primero el título → espera a tenerlo → luego empieza.\n'
            '_Request the title first → wait until you have it → then start._\n'
            'No acapares el título más tiempo del necesario.\n'
            '_Do not hold the title longer than necessary._'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_miembros(canal: discord.TextChannel):
    embed = discord.Embed(
        title='👥 Registro de Miembros / Member Registration',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Regístrate para que la alianza conozca tu perfil de gobernador. '
            'Al registrarte recibirás tu **rol de tropa** y acceso completo al servidor.\n'
            '_Register so the alliance knows your governor profile. '
            'Upon registration you will receive your **troop role** and full server access._'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos / Commands',
        value=(
            '`/registrar` → Vincula tu Discord con tu gobernador / _Link your Discord to your governor_\n'
            '`/perfil [@usuario]` → Tu perfil o el de otro / _Your profile or another member\'s_\n'
            '`/miembros` → Lista todos por poder / _List all members by power_\n'
            '`/mi-equipo` → Equipamiento según tu tropa / _Equipment for your troop type_\n'
            '`/ausente [días] [motivo]` → Avisa inactividad / _Report inactivity_\n'
            '`/volver` → Cancela tu ausencia / _Cancel your absence when you return_'
        ),
        inline=False,
    )
    embed.add_field(
        name='📝 Qué necesitas al registrarte / What you need to register',
        value=(
            '• Tu **nombre de gobernador** tal como aparece en el juego\n'
            '  _Your **governor name** exactly as it appears in the game_\n'
            '• Tu **poder actual** (ej: 150M, 50000K o 150000000)\n'
            '  _Your **current power** (e.g. 150M, 50000K or 150000000)_\n'
            '• Tu **tipo de tropa principal** / _Your **main troop type**_'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_comandantes(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🔍 Guías de Comandantes y Equipamiento / Commander & Equipment Guides',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Consulta el mejor equipamiento y builds para cualquier comandante.\n'
            '_Check the best equipment and builds for any commander in the game._'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos / Commands',
        value=(
            '`/comandante [nombre]` → Info completa + equipo endgame / _Full info + endgame equipment_\n'
            '`/comandantes-lista [tropa]` → Lista por tropa y tier / _List by troop type and tier_\n'
            '`/equipo [tropa] [rol] [fase]` → Equipo por tropa y fase / _Equipment by troop and phase_\n'
            '`/mi-equipo` → Tu equipo según tu registro / _Your equipment based on your registration_'
        ),
        inline=False,
    )
    embed.add_field(
        name='💡 Ejemplos / Examples',
        value=(
            '`/comandante guan` → Guan Yu\n'
            '`/comandante nevsky` → Alexander Nevsky\n'
            '`/equipo caballeria campo final` → Endgame cavalry set\n'
        ),
        inline=False,
    )
    embed.add_field(
        name='🗂️ Fases de juego / Game phases',
        value='🌱 Temprana / Early  →  ⚡ Media / Mid  →  🏆 Endgame (Season of Conquest)',
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_kvk(canal: discord.TextChannel):
    embed = discord.Embed(
        title='⚔️ KvK — Kingdom vs Kingdom',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Canal de estadísticas del KvK. Las stats se importan desde el Excel de '
            '[heroscroll.com](https://heroscroll.com/rok/kvk-dashboard).\n'
            '_KvK statistics channel. Stats are imported from the heroscroll.com Excel file._'
        ),
        color=0xFF4444,
    )
    embed.add_field(
        name='📋 Comandos / Commands',
        value=(
            '`/kvk-ranking` → Ranking de la temporada actual / _Current season ranking_\n'
            '`/kvk-buscar [nombre]` → Stats de un gobernador / _Governor stats_'
        ),
        inline=False,
    )
    embed.add_field(
        name='📊 ¿Cómo se actualizan las stats? / How are stats updated?',
        value=(
            'Al final de cada KvK, el liderazgo importa el Excel de heroscroll.com con `/kvk-importar`.\n'
            '_At the end of each KvK, leadership imports the heroscroll.com Excel file with `/kvk-importar`._'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_encuestas(canal: discord.TextChannel):
    embed = discord.Embed(
        title='📊 Encuestas y Votaciones / Polls and Voting',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Canal para las votaciones de la alianza. '
            'Vota pulsando los botones — puedes cambiar tu voto en cualquier momento.\n'
            '_Alliance voting channel. Vote by pressing the buttons — you can change your vote at any time._'
        ),
        color=0x5865F2,
    )
    embed.add_field(
        name='📋 Comandos (solo liderazgo/R4) / Commands (leadership/R4 only)',
        value=(
            '`/encuesta` → Encuesta general / _General poll_\n'
            '`/fecha` → Votar fecha u hora / _Vote on a date or time_\n'
            '`/si-no` → Votación rápida Sí / No / _Quick Yes / No vote_'
        ),
        inline=False,
    )
    embed.add_field(
        name='💡 Cómo funciona / How it works',
        value=(
            '• Pulsa un botón para votar / _Press a button to vote_\n'
            '• Puedes cambiar tu voto cuantas veces quieras / _You can change your vote as many times as you want_\n'
            '• El embed se actualiza en tiempo real / _The embed updates in real time_\n'
            '• El liderazgo puede cerrar la encuesta con `/cerrar-encuesta` / _Leadership can close the poll with `/cerrar-encuesta`_'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_ark(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🏹 Ark of Osiris',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            f'Canal de coordinación del **Ark of Osiris** de {ALIANZA_NOMBRE}.\n'
            f'_**Ark of Osiris** coordination channel for {ALIANZA_NOMBRE}._\n'
            'Los equipos A, B, C y D tienen sus propios canales de voz.\n'
            '_Teams A, B, C and D have their own voice channels._'
        ),
        color=0x9B59B6,
    )
    embed.add_field(
        name='🎙️ Canales de voz / Voice channels',
        value=(
            '🎙️ **ark-equipo-a** — Equipo A / Team A\n'
            '🎙️ **ark-equipo-b** — Equipo B / Team B\n'
            '🎙️ **ark-equipo-c** — Equipo C / Team C\n'
            '🎙️ **ark-equipo-d** — Equipo D / Team D'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚔️ Normas del Ark / Ark Rules',
        value=(
            '• Conéctate al canal de voz de tu equipo **antes de empezar** / _Connect to your team\'s voice channel **before it starts**_\n'
            '• Sigue las instrucciones del líder de equipo / _Follow your team leader\'s instructions_\n'
            '• Reporta posiciones enemigas en el chat / _Report enemy positions in chat_\n'
            '• No abandones el canal de voz durante el evento / _Do not leave the voice channel during the event_'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_kvk_anuncios(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🔥 KvK — Coordinación de Guerra / War Coordination',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            f'Canal principal de coordinación durante el **KvK** de {ALIANZA_NOMBRE}.\n'
            f'_Main coordination channel during **KvK** for {ALIANZA_NOMBRE}._\n'
            'Solo el liderazgo puede escribir aquí. Mantén silencio y atiende las órdenes.\n'
            '_Only leadership can write here. Stay silent and follow orders._'
        ),
        color=0xFF4444,
    )
    embed.add_field(
        name='🎙️ Canales de voz / Voice channels',
        value=(
            '🎙️ **kvk-coordinacion** — Liderazgo y coordinadores / _Leadership and coordinators_\n'
            '🎙️ **kvk-equipo-1** — Equipo de rally 1 / _Rally team 1_\n'
            '🎙️ **kvk-equipo-2** — Equipo de campo 2 / _Field team 2_\n'
            '🎙️ **kvk-equipo-3** — Equipo de defensa 3 / _Defense team 3_'
        ),
        inline=False,
    )
    embed.add_field(
        name='📋 Estadísticas KvK / KvK Stats',
        value=(
            'Ve al canal **⚔️│kvk-stats** para consultar el ranking y buscar gobernadores.\n'
            '_Go to **⚔️│kvk-stats** to check the ranking and search for governors._'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_mge_inscripciones(canal: discord.TextChannel):
    embed = discord.Embed(
        title='📝 MGE — Inscripciones / MGE Enrollment',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Aquí puedes ver los MGEs disponibles y apuntarte.\n'
            '_Here you can see available MGEs and sign up._\n'
            'El liderazgo revisará las inscripciones y asignará las plazas.\n'
            '_Leadership will review enrollments and assign slots._\n'
            'La lista final se publicará en **🏆│mge-resultados**.\n'
            '_The final list will be published in **🏆│mge-resultados**._'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos / Commands',
        value=(
            '`/mge-lista` → Ver los MGEs activos y sus metas / _See active MGEs and their targets_\n'
            '`/mge-inscribir` → Apuntarte a un MGE / _Sign up for an MGE_\n'
            '`/mge-salir` → Cancelar tu inscripción / _Cancel your enrollment_'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚙️ Cómo funciona / How it works',
        value=(
            '**1.** El liderazgo crea el MGE con su meta de poder / _Leadership creates the MGE with its power target_\n'
            '**2.** Te inscribes aquí con `/mge-inscribir` / _You sign up here with `/mge-inscribir`_\n'
            '**3.** El liderazgo asigna posiciones y metas individuales / _Leadership assigns positions and individual targets_\n'
            '**4.** La lista final se publica en 🏆│mge-resultados / _The final list is published in 🏆│mge-resultados_'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_mge_resultados(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🏆 MGE — Lista de Participantes / Participant List',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Aquí se publican las listas finales de participantes de cada MGE '
            'con sus **posiciones y metas individuales** asignadas por el liderazgo.\n'
            '_Here the final participant lists for each MGE are published '
            'with their **positions and individual targets** assigned by leadership._'
        ),
        color=0xFFD700,
    )
    embed.add_field(
        name='📋 Comandos / Commands',
        value=(
            '`/mge-seleccionados` → Ver los participantes elegidos del MGE activo\n'
            '_See the selected participants for the active MGE_'
        ),
        inline=False,
    )
    embed.add_field(
        name='ℹ️ Para inscribirte / To sign up',
        value=(
            'Ve al canal **📝│mge-inscripciones** y usa `/mge-inscribir`\n'
            '_Go to **📝│mge-inscripciones** and use `/mge-inscribir`_'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_reclutamiento(canal: discord.TextChannel):
    from cogs.reclutamiento import PanelReclutamientoView
    embed = discord.Embed(
        title=f'⚔️ Reclutamiento — {ALIANZA_FULL} / Recruitment',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            f'¿Quieres unirte a nuestra alianza? Pulsa el botón, rellena el formulario '
            f'y el liderazgo creará un canal privado para revisar tu candidatura.\n'
            f'_Want to join our alliance? Press the button, fill in the form '
            f'and leadership will create a private channel to review your application._'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Lo que buscamos / What we look for',
        value=(
            '• Jugadores activos en **KvK** y **Ark of Osiris** / _Active players in **KvK** and **Ark of Osiris**_\n'
            '• Disposición a seguir órdenes del liderazgo / _Willingness to follow leadership orders_\n'
            '• Comunicación y trabajo en equipo / _Communication and teamwork_'
        ),
        inline=False,
    )
    embed.add_field(
        name='📸 Necesitarás subir / You will need to upload',
        value=(
            '⚔️ Capturas de tus **marchas** (tipo, tier y cantidad) / _Screenshots of your **marches** (type, tier and count)_\n'
            '⚡ Capturas de tus **velocidades** (entrenamiento, construcción, investigación, curación) / _Your **speed** screenshots_\n'
            '💰 Captura de tus **recursos** / _Screenshot of your **resources**_'
        ),
        inline=False,
    )
    embed.set_footer(text=f'El proceso es confidencial / The process is confidential · {ALIANZA_TAG} · Reino {REINO}')
    return await canal.send(embed=embed, view=PanelReclutamientoView())


async def msg_scouting(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🗺️ Scouting y Alertas / Scouting and Alerts',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Reporta aquí actividad enemiga, posiciones importantes y objetivos a atacar o defender.\n'
            '_Report enemy activity, important positions and targets to attack or defend here._'
        ),
        color=0xE74C3C,
    )
    embed.add_field(
        name='📋 Formato de reporte / Report format',
        value=(
            'Usa este formato / _Use this format_:\n'
            '```\n'
            '📍 Coordenadas / Coordinates: (XXX, YYY)\n'
            '⚔️  Tipo / Type: Ciudad enemiga / Rally / Bárbaros\n'
            '💬 Info: descripción breve / brief description\n'
            '```'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


# ── Mapa canal → función ───────────────────────────────────────────────────────

MENSAJES_POR_CANAL = {
    'bienvenida':       msg_bienvenida,
    'reglas':           msg_reglas,
    'comandos-bot':     msg_comandos_bot,
    'cola-titulos':     msg_titulos,
    'miembros':         msg_miembros,
    'comandantes':      msg_comandantes,
    'kvk-stats':        msg_kvk,
    'kvk-bajas':        msg_kvk,
    'encuestas':        msg_encuestas,
    'encuestas-fechas': msg_encuestas,
    'ark-general':      msg_ark,
    'kvk-anuncios':     msg_kvk_anuncios,
    'scouting':         msg_scouting,
    'kvk-scouting':     msg_scouting,
    'reclutamiento':    msg_reclutamiento,
    'mge-inscripciones': msg_mge_inscripciones,
    'mge-resultados':   msg_mge_resultados,
}


class Mensajes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name='inicializar-mensajes',
        description='[ADMIN] Publica los mensajes informativos en todos los canales del servidor'
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def inicializar_mensajes(self, interaction: discord.Interaction):
        print('[inicializar-mensajes] Recibido')
        await interaction.response.defer(ephemeral=True)
        print('[inicializar-mensajes] Deferred OK')

        publicados = 0
        omitidos   = 0

        for canal in interaction.guild.text_channels:
            nombre_limpio = canal.name.split('│')[-1] if '│' in canal.name else canal.name

            fn = MENSAJES_POR_CANAL.get(nombre_limpio)
            if not fn:
                omitidos += 1
                continue

            hay_mensajes = [
                m async for m in canal.history(limit=10)
                if m.author == interaction.guild.me and m.type == discord.MessageType.default
            ]
            if hay_mensajes:
                omitidos += 1
                continue

            try:
                if nombre_limpio == 'bienvenida':
                    msg = await fn(canal, interaction.guild)
                else:
                    msg = await fn(canal)
                if msg:
                    try:
                        await msg.pin()
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                publicados += 1
            except Exception as e:
                print(f'[mensajes] Error en #{canal.name}: {type(e).__name__}: {e}')
                omitidos += 1

        await interaction.followup.send(
            f'✅ Mensajes publicados en **{publicados}** canales. ({omitidos} omitidos)',
            ephemeral=True,
        )

    @app_commands.command(
        name='actualizar-mensaje',
        description='[ADMIN] Publica el mensaje informativo en un canal concreto'
    )
    @app_commands.describe(canal='Canal donde publicar el mensaje')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def actualizar_mensaje(self, interaction: discord.Interaction, canal: discord.TextChannel):
        nombre_limpio = canal.name.split('│')[-1] if '│' in canal.name else canal.name
        fn = MENSAJES_POR_CANAL.get(nombre_limpio)

        if not fn:
            await interaction.response.send_message(
                f'❌ No hay mensaje configurado para **{canal.name}**.',
                ephemeral=True,
            )
            return

        try:
            if nombre_limpio == 'bienvenida':
                msg = await fn(canal, interaction.guild)
            else:
                msg = await fn(canal)
            if msg:
                try:
                    await msg.pin()
                except discord.Forbidden:
                    pass
            await interaction.response.send_message(f'✅ Mensaje publicado y fijado en {canal.mention}.', ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f'❌ Sin permisos para escribir en {canal.mention}.', ephemeral=True)

    @inicializar_mensajes.error
    @actualizar_mensaje.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Mensajes(bot))
