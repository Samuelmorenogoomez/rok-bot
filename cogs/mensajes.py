import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT, ALIANZA_NOMBRE, ALIANZA_TAG, ALIANZA_FULL, REINO

# ── Contenido de cada canal ────────────────────────────────────────────────────

async def msg_bienvenida(canal: discord.TextChannel, guild: discord.Guild):
    canal_miembros = next((c.id for c in guild.channels if 'miembros' in c.name), 0)
    embed = discord.Embed(
        title=f'🔥 ¡Bienvenido a {ALIANZA_FULL}!',
        description=(
            f'Has llegado al servidor oficial de la alianza **{ALIANZA_NOMBRE}** '
            f'del **Reino {REINO}**.\n\n'
            f'Para acceder al servidor completo debes **registrarte** con tu perfil de gobernador.\n\n'
            f'**¿Cómo empezar?**\n'
            f'1. Ve al canal <#{canal_miembros}> y usa `/registrar`\n'
            f'2. Introduce tu nombre de gobernador, poder y tipo de tropa\n'
            f'3. El bot te asignará tu rol y tendrás acceso completo al servidor'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Una vez registrado tendrás acceso a',
        value=(
            '🔥 Coordinación de guerra y KvK\n'
            '🏹 Ark of Osiris y estrategia\n'
            '📅 Eventos y encuestas de la alianza\n'
            '🏰 Cola de títulos del reino\n'
            '🔍 Guías de comandantes y equipamiento'
        ),
        inline=False,
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f'{ALIANZA_TAG} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_reglas(canal: discord.TextChannel):
    embed = discord.Embed(
        title=f'📜 Reglas de {ALIANZA_NOMBRE}',
        description=f'*{ALIANZA_TAG} · Reino {REINO}*',
        color=0xFF4444,
    )
    embed.add_field(
        name='1. 🤝 Respeto',
        value='Trato respetuoso con todos los miembros. Cero toxicidad ni insultos.',
        inline=False,
    )
    embed.add_field(
        name='2. ⚡ Actividad',
        value='Se espera participación en KvK y Ark of Osiris. Avisa si vas a estar inactivo.',
        inline=False,
    )
    embed.add_field(
        name='3. 🚩 Coordinación',
        value='Sigue las órdenes del liderazgo en eventos de guerra. La coordinación es clave para ganar.',
        inline=False,
    )
    embed.add_field(
        name='4. 💰 Donaciones',
        value='Dona recursos a la alianza regularmente para mantener los edificios activos.',
        inline=False,
    )
    embed.add_field(
        name='5. 📡 Comunicación',
        value='Usa los canales correctos. Reporta actividad enemiga en el canal de scouting.',
        inline=False,
    )
    embed.add_field(
        name='6. 🤖 Uso del bot',
        value='Usa los comandos del bot en sus canales correspondientes para no saturar el chat general.',
        inline=False,
    )
    embed.set_footer(text='El incumplimiento reiterado puede resultar en expulsión de la alianza.')
    return await canal.send(embed=embed)


async def msg_comandos_bot(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🤖 Guía de Comandos del Bot',
        description=f'Lista completa de comandos disponibles · *{ALIANZA_TAG} Reino {REINO}*',
        color=COLOR_BOT,
    )
    embed.add_field(
        name='👥 Canal de Miembros',
        value=(
            '`/registrar` — Regístrate con tu gobernador, poder y tropa\n'
            '`/perfil [@usuario]` — Ve tu perfil o el de otro miembro\n'
            '`/miembros` — Lista todos los miembros por poder\n'
            '`/mi-equipo` — Equipamiento recomendado para tu tropa\n'
            '`/ausente [días] [motivo]` — Avisa que estarás inactivo\n'
            '`/volver` — Cancela tu ausencia'
        ),
        inline=False,
    )
    embed.add_field(
        name='🏰 Canal de Títulos',
        value=(
            '`/pedir` — Pide un título (Duke, Architect, Scientist...)\n'
            '`/cola` — Ve quién está esperando título\n'
            '`/cancelar` — Sal de la cola si ya no lo necesitas'
        ),
        inline=False,
    )
    embed.add_field(
        name='🔍 Canal de Comandantes',
        value=(
            '`/comandante [nombre]` — Info y equipo de cualquier comandante\n'
            '`/comandantes-lista` — Lista todos los comandantes por tropa y tier\n'
            '`/equipo [tropa] [rol] [fase]` — Equipamiento por tipo de tropa\n'
            '`/mi-equipo` — Tu equipamiento según tu tipo de tropa'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚔️ Canal de KvK',
        value=(
            '`/kvk-importar` — Importa el Excel de heroscroll.com\n'
            '`/kvk-ranking` — Ranking de la temporada actual\n'
            '`/kvk-buscar [nombre]` — Stats de un gobernador'
        ),
        inline=False,
    )
    embed.add_field(
        name='📊 Canal de Encuestas',
        value=(
            '`/encuesta [pregunta] [op1] [op2]...` — Encuesta con botones\n'
            '`/fecha [evento] [op1] [op2]...` — Votar fecha/hora de evento\n'
            '`/si-no [pregunta]` — Encuesta rápida Sí / No'
        ),
        inline=False,
    )
    embed.add_field(
        name='📝 Canal MGE Inscripciones',
        value=(
            '`/mge-lista` — Ver MGEs activos y sus metas\n'
            '`/mge-inscribir` — Apuntarte a un MGE\n'
            '`/mge-salir` — Cancelar tu inscripción'
        ),
        inline=False,
    )
    embed.add_field(
        name='🏆 Canal MGE Resultados',
        value='`/mge-seleccionados` — Ver los participantes elegidos y sus metas',
        inline=False,
    )
    embed.set_footer(text='Los comandos solo funcionan en su canal correspondiente.')
    return await canal.send(embed=embed)


async def msg_titulos(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🏰 Cola de Títulos del Reino',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Los títulos otorgan **buffs temporales muy valiosos**. '
            'Pídelos **antes** de empezar a entrenar, construir o investigar.'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos',
        value=(
            '`/pedir` → Selecciona el título que necesitas\n'
            '`/cola` → Ve quién está esperando y en qué posición\n'
            '`/cancelar` → Sal de la cola si ya no lo necesitas'
        ),
        inline=False,
    )
    embed.add_field(
        name='🎖️ Títulos disponibles',
        value=(
            '⚔️ **Duke** — +10% velocidad de entrenamiento de tropas\n'
            '🏗️ **Architect** — +10% velocidad de construcción\n'
            '🔬 **Scientist** — +10% velocidad de investigación\n'
            '⚕️ **Justice** — +10% velocidad de curación\n'
            '🛡️ **General** — Buffs de ataque y defensa'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚠️ Importante',
        value=(
            'El título **no tiene efecto** si ya empezaste la acción.\n'
            'Pide primero el título → espera a tenerlo → luego empieza.\n'
            'No acapares el título más tiempo del necesario.'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_miembros(canal: discord.TextChannel):
    embed = discord.Embed(
        title='👥 Registro de Miembros',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Regístrate para que la alianza conozca tu perfil de gobernador.\n'
            'Al registrarte recibirás automáticamente tu **rol de tropa** y acceso completo al servidor.'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos',
        value=(
            '`/registrar` → Vincula tu Discord con tu gobernador\n'
            '`/perfil [@usuario]` → Ve tu perfil o el de otro miembro\n'
            '`/miembros` → Lista todos los miembros por poder\n'
            '`/mi-equipo` → Equipamiento recomendado para tu tropa\n'
            '`/ausente [días] [motivo]` → Avisa que estarás inactivo\n'
            '`/volver` → Cancela tu ausencia cuando regreses'
        ),
        inline=False,
    )
    embed.add_field(
        name='📝 Qué necesitas al registrarte',
        value=(
            '• Tu **nombre de gobernador** tal como aparece en el juego\n'
            '• Tu **poder actual** (ej: 150M, 50000K o 150000000)\n'
            '• Tu **tipo de tropa principal**'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_comandantes(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🔍 Guías de Comandantes y Equipamiento',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Consulta el mejor equipamiento y builds para cualquier comandante del juego.'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos',
        value=(
            '`/comandante [nombre]` → Info completa + equipo endgame\n'
            '`/comandantes-lista [tropa]` → Lista por tipo de tropa y tier\n'
            '`/equipo [tropa] [rol] [fase]` → Equipo por tropa y fase\n'
            '`/mi-equipo` → Tu equipo según tu registro'
        ),
        inline=False,
    )
    embed.add_field(
        name='💡 Ejemplos de búsqueda',
        value=(
            '`/comandante guan` → Guan Yu\n'
            '`/comandante nevsky` → Alexander Nevsky\n'
            '`/comandante zhuge` → Zhuge Liang\n'
            '`/equipo caballeria campo final` → Set endgame caballería'
        ),
        inline=False,
    )
    embed.add_field(
        name='🗂️ Fases de juego',
        value='🌱 Temprana  →  ⚡ Media  →  🏆 Endgame (Season of Conquest)',
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
            '[heroscroll.com](https://heroscroll.com/rok/kvk-dashboard).'
        ),
        color=0xFF4444,
    )
    embed.add_field(
        name='📋 Comandos',
        value=(
            '`/kvk-ranking` → Ranking de la temporada actual\n'
            '`/kvk-buscar [nombre]` → Busca las stats de un gobernador'
        ),
        inline=False,
    )
    embed.add_field(
        name='📊 ¿Cómo se actualizan las stats?',
        value=(
            'Al final de cada KvK, el liderazgo importa el Excel de heroscroll.com con `/kvk-importar`.\n'
            'El ranking se actualiza automáticamente con los datos oficiales.'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_encuestas(canal: discord.TextChannel):
    embed = discord.Embed(
        title='📊 Encuestas y Votaciones',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Canal para las votaciones de la alianza. '
            'Vota pulsando los botones — puedes cambiar tu voto en cualquier momento.'
        ),
        color=0x5865F2,
    )
    embed.add_field(
        name='📋 Comandos (solo liderazgo/R4)',
        value=(
            '`/encuesta [pregunta] [op1] [op2]...` → Encuesta general\n'
            '`/fecha [evento] [op1] [op2]...` → Votar fecha u hora\n'
            '`/si-no [pregunta]` → Votación rápida Sí / No'
        ),
        inline=False,
    )
    embed.add_field(
        name='💡 Cómo funciona',
        value=(
            '• Pulsa un botón para votar\n'
            '• Puedes cambiar tu voto cuantas veces quieras\n'
            '• El embed se actualiza en tiempo real con el recuento y barras de progreso\n'
            '• El liderazgo puede cerrar la encuesta con `/cerrar-encuesta`'
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
            'Los equipos A, B, C y D tienen sus propios canales de voz.'
        ),
        color=0x9B59B6,
    )
    embed.add_field(
        name='🎙️ Canales de voz disponibles',
        value=(
            '🎙️ **ark-equipo-a** — Equipo A\n'
            '🎙️ **ark-equipo-b** — Equipo B\n'
            '🎙️ **ark-equipo-c** — Equipo C\n'
            '🎙️ **ark-equipo-d** — Equipo D'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚔️ Normas del Ark',
        value=(
            '• Conéctate al canal de voz de tu equipo **antes de empezar**\n'
            '• Sigue las instrucciones del líder de equipo en todo momento\n'
            '• Reporta posiciones enemigas y objetivos en el chat\n'
            '• No abandones el canal de voz durante el evento'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_kvk_anuncios(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🔥 KvK — Coordinación de Guerra',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            f'Canal principal de coordinación durante el **KvK** de {ALIANZA_NOMBRE}.\n'
            'Solo el liderazgo puede escribir aquí. Mantén silencio y atiende las órdenes.'
        ),
        color=0xFF4444,
    )
    embed.add_field(
        name='🎙️ Canales de voz',
        value=(
            '🎙️ **kvk-coordinacion** — Liderazgo y coordinadores\n'
            '🎙️ **kvk-equipo-1** — Equipo de rally 1\n'
            '🎙️ **kvk-equipo-2** — Equipo de campo 2\n'
            '🎙️ **kvk-equipo-3** — Equipo de defensa 3'
        ),
        inline=False,
    )
    embed.add_field(
        name='📋 Estadísticas KvK',
        value='Ve al canal **⚔️│kvk-stats** para consultar el ranking y buscar gobernadores.',
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_mge_inscripciones(canal: discord.TextChannel):
    embed = discord.Embed(
        title='📝 MGE — Inscripciones',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Aquí puedes ver los MGEs disponibles y apuntarte.\n'
            'El liderazgo revisará las inscripciones y asignará las plazas.\n'
            'La lista final de seleccionados se publicará en **🏆│mge-resultados**.'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Comandos',
        value=(
            '`/mge-lista` → Ver los MGEs activos y sus metas de poder\n'
            '`/mge-inscribir` → Apuntarte a un MGE\n'
            '`/mge-salir` → Cancelar tu inscripción'
        ),
        inline=False,
    )
    embed.add_field(
        name='⚙️ Cómo funciona',
        value=(
            '**1.** El liderazgo crea el MGE con su meta de poder\n'
            '**2.** Te inscribes aquí con `/mge-inscribir`\n'
            '**3.** El liderazgo asigna posiciones y metas individuales\n'
            '**4.** La lista final se publica en 🏆│mge-resultados con mención a todos'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_mge_resultados(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🏆 MGE — Lista de Participantes',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Aquí se publican las listas finales de participantes de cada MGE '
            'con sus **posiciones y metas individuales** asignadas por el liderazgo.'
        ),
        color=0xFFD700,
    )
    embed.add_field(
        name='📋 Comandos',
        value='`/mge-seleccionados` → Ver los participantes elegidos del MGE activo',
        inline=False,
    )
    embed.add_field(
        name='ℹ️ Para inscribirte',
        value='Ve al canal **📝│mge-inscripciones** y usa `/mge-inscribir`',
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_reclutamiento(canal: discord.TextChannel):
    embed = discord.Embed(
        title=f'⚔️ Reclutamiento — {ALIANZA_FULL}',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            f'¿Quieres unirte a nuestra alianza?\n'
            f'Pulsa el botón, rellena el formulario y el liderazgo creará un canal privado para revisar tu candidatura.'
        ),
        color=COLOR_BOT,
    )
    embed.add_field(
        name='📋 Lo que buscamos',
        value=(
            '• Jugadores activos en **KvK** y **Ark of Osiris**\n'
            '• Disposición a seguir órdenes del liderazgo\n'
            '• Comunicación y trabajo en equipo'
        ),
        inline=False,
    )
    embed.add_field(
        name='📸 Necesitarás subir',
        value=(
            '⚔️ Capturas de tus **marchas** (tipo, tier y cantidad)\n'
            '⚡ Capturas de tus **velocidades** (entrenamiento, construcción, investigación, curación)\n'
            '💰 Captura de tus **recursos**'
        ),
        inline=False,
    )
    embed.set_footer(text=f'El proceso es confidencial · {ALIANZA_TAG} · Reino {REINO}')
    return await canal.send(embed=embed)


async def msg_scouting(canal: discord.TextChannel):
    embed = discord.Embed(
        title='🗺️ Scouting y Alertas',
        description=(
            f'*{ALIANZA_TAG} · Reino {REINO}*\n\n'
            'Reporta aquí actividad enemiga, posiciones importantes y objetivos a atacar o defender.'
        ),
        color=0xE74C3C,
    )
    embed.add_field(
        name='📋 Formato de reporte',
        value=(
            'Usa este formato para que todos entiendan el aviso:\n'
            '```\n'
            '📍 Coordenadas: (XXX, YYY)\n'
            '⚔️  Tipo: Ciudad enemiga / Rally / Bárbaros\n'
            '💬 Info: descripción breve\n'
            '```'
        ),
        inline=False,
    )
    embed.set_footer(text=f'{ALIANZA_FULL} · Reino {REINO}')
    return await canal.send(embed=embed)


# ── Mapa canal → función ───────────────────────────────────────────────────────

MENSAJES_POR_CANAL = {
    'bienvenida':    msg_bienvenida,
    'reglas':        msg_reglas,
    'comandos-bot':  msg_comandos_bot,
    'cola-titulos':  msg_titulos,
    'miembros':      msg_miembros,
    'comandantes':   msg_comandantes,
    'kvk-stats':     msg_kvk,
    'kvk-bajas':     msg_kvk,
    'encuestas':     msg_encuestas,
    'encuestas-fechas': msg_encuestas,
    'ark-general':   msg_ark,
    'kvk-anuncios':  msg_kvk_anuncios,
    'scouting':      msg_scouting,
    'kvk-scouting':  msg_scouting,
    'reclutamiento':     msg_reclutamiento,
    'mge-inscripciones': msg_mge_inscripciones,
    'mge-resultados':    msg_mge_resultados,
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
