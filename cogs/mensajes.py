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
            f'1. Ve al canal <#{canal_miembros}> y pulsa 📝 **Registrarme**\n'
            f'   _Go to <#{canal_miembros}> and press 📝 **Register**_\n'
            f'2. Rellena el formulario: nombre de gobernador, poder y tropa\n'
            f'   _Fill in the form: governor name, power and troop_\n'
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
            '📅 Eventos, encuestas y MGE de la alianza / Alliance events, polls and MGE'
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
            '📝 Botón **Registrarme** en el canal de miembros / _**Register** button in the members channel_\n'
            '`/perfil [@usuario]` — Tu perfil o el de otro / _Your profile or another member\'s_\n'
            '`/miembros` — Lista por poder / _List all members by power_\n'
            '😴 Botones **Ausencia** y **He vuelto** en el canal de miembros / _**Absence** and **I\'m back** buttons_'
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
            'Pulsa ✋ en el tablón del MGE para apuntarte / _Press ✋ on the MGE board to sign up_\n'
            '`/mge-historial` — Historial de MGEs / _MGE history_'
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


async def msg_miembros(canal: discord.TextChannel):
    from cogs.miembros import PanelMiembrosView
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
        name='🔘 Botones / Buttons',
        value=(
            '📝 **Registrarme / Actualizar** → formulario con tus datos / _form with your details_\n'
            '👤 **Mi perfil** → ver tu ficha / _see your profile_\n'
            '😴 **Ausencia** → avisa de que estarás inactivo / _report inactivity_\n'
            '✅ **He vuelto** → cancela tu ausencia / _cancel your absence_\n\n'
            '`/perfil @usuario` · `/miembros`'
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
    return await canal.send(embed=embed, view=PanelMiembrosView())



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
            'Durante el evento, todos al canal de voz **🎙️│ark-voz**.\n'
            '_During the event, everyone joins the **🎙️│ark-voz** voice channel._'
        ),
        color=0x9B59B6,
    )
    embed.add_field(
        name='⚔️ Normas del Ark / Ark Rules',
        value=(
            '• Conéctate a **🎙️│ark-voz** **antes de empezar** / _Join **🎙️│ark-voz** **before it starts**_\n'
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
            '🎙️ **voz-guerra** — Coordinación general / _General coordination_\n'
            '🎙️ **equipo-1** — Equipo 1 / _Team 1_\n'
            '🎙️ **equipo-2** — Equipo 2 / _Team 2_\n'
            '💬 **kvk-chat** — Chat de KvK y guerra / _KvK and war chat_'
        ),
        inline=False,
    )
    embed.add_field(
        name='📋 Estadísticas KvK / KvK Stats',
        value=(
            'Ve al canal **📊│kvk-stats** para consultar el ranking y buscar gobernadores.\n'
            '_Go to **📊│kvk-stats** to check the ranking and search for governors._'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_mge(canal: discord.TextChannel):
    embed = discord.Embed(
        title='📝 MGE',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Cada MGE tiene aquí su **tablón**: te apuntas con un botón y ves la lista en directo.\n'
            '_Each MGE has its **board** here: sign up with one button and see the list live._\n\n'
            '⚠️ Tienes que estar **registrado** en 👥│miembros para apuntarte.\n'
            '_You must be **registered** in 👥│miembros to sign up._'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='🔘 Botones del tablón / Board buttons',
        value=(
            '✋ **Apuntarme** → eliges tus cabezas doradas y listo / _pick your golden heads and done_\n'
            '🗿 **Mis cabezas** → cambiar cuántas tienes / _change how many you have_\n'
            '🚪 **Salir** → borrarte del MGE / _leave the MGE_'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚙️ Cómo funciona / How it works',
        value=(
            '**1.** El liderazgo crea el MGE con su meta de poder / _Leadership creates the MGE with its power target_\n'
            '**2.** Te apuntas con ✋ en su tablón / _You sign up with ✋ on its board_\n'
            '**3.** El liderazgo asigna plazas y metas / _Leadership assigns slots and targets_\n'
            '**4.** La lista final se publica aquí y te llega por MD / _The final list is posted here and sent to you by DM_\n\n'
            '`/mge-historial` → historial de MGEs / _MGE history_'
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
    'bienvenida':    [msg_bienvenida, msg_reglas, msg_comandos_bot],
    'miembros':      [msg_miembros],
    'kvk-stats':     [msg_kvk],
    'encuestas':     [msg_encuestas],
    'ark':           [msg_ark],
    'kvk-anuncios':  [msg_kvk_anuncios],
    'scouting':      [msg_scouting],
    'reclutamiento': [msg_reclutamiento],
    'mge':           [msg_mge],
}


def nombre_limpio(canal: discord.abc.GuildChannel) -> str:
    return canal.name.split('│')[-1]


async def publicar_mensajes(canal: discord.TextChannel) -> int:
    """Publica y ancla los mensajes fijos del canal, quitando antes los que el bot tuviera anclados."""
    funciones = MENSAJES_POR_CANAL.get(nombre_limpio(canal), [])
    if not funciones:
        return 0
    for viejo in [m async for m in canal.pins()]:
        if viejo.author == canal.guild.me:
            try:
                await viejo.delete()
            except discord.HTTPException:
                pass
    for fn in funciones:
        msg = await (fn(canal, canal.guild) if fn is msg_bienvenida else fn(canal))
        try:
            await msg.pin()
        except discord.HTTPException:
            pass
    return len(funciones)


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
            if nombre_limpio(canal) not in MENSAJES_POR_CANAL:
                continue
            # Si el bot ya tiene un mensaje anclado ahí, no se toca (para rehacerlo: /actualizar-mensaje)
            if any([m.author == interaction.guild.me async for m in canal.pins()]):
                omitidos += 1
                continue
            try:
                await publicar_mensajes(canal)
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
        description='[ADMIN] Rehace el mensaje fijo de un canal (sustituye al anclado anterior)'
    )
    @app_commands.describe(canal='Canal donde publicar el mensaje')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def actualizar_mensaje(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if nombre_limpio(canal) not in MENSAJES_POR_CANAL:
            await interaction.response.send_message(
                f'❌ No hay mensaje configurado para **{canal.name}**.', ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await publicar_mensajes(canal)
        except discord.Forbidden:
            await interaction.followup.send(f'❌ Sin permisos para escribir en {canal.mention}.', ephemeral=True)
            return
        await interaction.followup.send(
            f'✅ Mensaje publicado y anclado en {canal.mention} (el anterior del bot se ha quitado).', ephemeral=True
        )

    @inicializar_mensajes.error
    @actualizar_mensaje.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('❌ No tienes permisos.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Mensajes(bot))
