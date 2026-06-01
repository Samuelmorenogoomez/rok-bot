import json
import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT
from checks import solo_en_canal
from db import database as db

ESTILOS = [
    discord.ButtonStyle.primary,
    discord.ButtonStyle.success,
    discord.ButtonStyle.danger,
    discord.ButtonStyle.secondary,
]
NUMEROS  = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
COLORES  = {
    "general": 0x5865F2,
    "fecha":   0x57F287,
    "sino":    0xFEE75C,
}
ICONOS = {
    "general": "📊",
    "fecha":   "📅",
    "sino":    "❓",
}


def barra_progreso(pct: int, ancho: int = 18) -> str:
    llena = round(pct * ancho / 100)
    return "▰" * llena + "▱" * (ancho - llena)


def build_embed(pregunta: str, opciones: list[str], votos: list, tipo: str, creador: str) -> discord.Embed:
    total  = len(votos)
    conteo: dict[int, int] = {}
    for v in votos:
        conteo[v["opcion_idx"]] = conteo.get(v["opcion_idx"], 0) + 1

    ganador = max(conteo, key=conteo.get) if conteo else -1
    color   = COLORES.get(tipo, COLOR_BOT)
    icono   = ICONOS.get(tipo, "📊")

    embed = discord.Embed(
        title=f"{icono}  {pregunta}",
        color=color,
    )

    lineas = []
    for i, opcion in enumerate(opciones):
        count = conteo.get(i, 0)
        pct   = round((count / total * 100) if total > 0 else 0)
        corona = " 👑" if i == ganador and total > 0 else ""

        lineas.append(
            f"{NUMEROS[i]} **{opcion}**{corona}\n"
            f"`{barra_progreso(pct)}` **{pct}%**  ·  {count} voto{'s' if count != 1 else ''}"
        )

    embed.description = "\n\n".join(lineas)

    if total == 0:
        embed.set_footer(text=f"✏️ Creada por {creador}  ·  Sin votos aún  ·  Pulsa un botón para votar")
    else:
        embed.set_footer(text=f"✏️ {creador}  ·  {total} voto{'s' if total != 1 else ''}  ·  Puedes cambiar tu voto")

    return embed


class PollButton(discord.ui.Button):
    def __init__(self, encuesta_id: int, opcion_idx: int, label: str):
        super().__init__(
            style=ESTILOS[opcion_idx % 4],
            label=f"  {label[:75]}  ",
            emoji=NUMEROS[opcion_idx],
            custom_id=f"encuesta:{encuesta_id}:{opcion_idx}",
        )

    async def callback(self, interaction: discord.Interaction):
        parts       = self.custom_id.split(":")
        encuesta_id = int(parts[1])
        opcion_idx  = int(parts[2])

        encuesta = await db.get_encuesta(encuesta_id)
        if not encuesta or not encuesta["activa"]:
            await interaction.response.send_message("❌ Esta encuesta ya está cerrada.", ephemeral=True)
            return

        voto_previo = await db.get_user_vote(encuesta_id, str(interaction.user.id))
        await db.upsert_vote(encuesta_id, str(interaction.user.id), opcion_idx)

        opciones = json.loads(encuesta["opciones"])
        votos    = await db.get_votos(encuesta_id)

        nuevo_embed = build_embed(
            encuesta["pregunta"], opciones, votos,
            encuesta["tipo"], interaction.guild.get_member(int(encuesta["creador_id"])).display_name
            if interaction.guild.get_member(int(encuesta["creador_id"])) else "Admin"
        )

        await interaction.response.edit_message(embed=nuevo_embed, view=self.view)

        if voto_previo is None:
            msg = f"✅ Has votado **{opciones[opcion_idx]}**"
        elif voto_previo["opcion_idx"] == opcion_idx:
            msg = f"ℹ️ Ya habías votado **{opciones[opcion_idx]}**"
        else:
            msg = f"🔄 Voto cambiado a **{opciones[opcion_idx]}**"

        await interaction.followup.send(msg, ephemeral=True)


class PollView(discord.ui.View):
    def __init__(self, encuesta_id: int, opciones: list[str]):
        super().__init__(timeout=None)
        for i, opcion in enumerate(opciones):
            self.add_item(PollButton(encuesta_id, i, opcion))


class Encuestas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        encuestas = await db.get_all_active_encuestas()
        for enc in encuestas:
            opciones = json.loads(enc["opciones"])
            self.bot.add_view(PollView(enc["id"], opciones))

    def _hacer_view(self, encuesta_id: int, opciones: list[str]) -> PollView:
        view = PollView(encuesta_id, opciones)
        self.bot.add_view(view)
        return view

    async def _enviar_encuesta(
        self,
        interaction: discord.Interaction,
        tipo: str,
        pregunta: str,
        opciones: list[str],
        horas: int,
        rol: discord.Role | None,
    ):
        encuesta_id = await db.create_encuesta(
            guild_id    = str(interaction.guild_id),
            canal_id    = str(interaction.channel_id),
            tipo        = tipo,
            pregunta    = pregunta,
            opciones_json = json.dumps(opciones),
            horas       = horas,
            creador_id  = str(interaction.user.id),
        )

        view  = self._hacer_view(encuesta_id, opciones)
        embed = build_embed(pregunta, opciones, [], tipo, interaction.user.display_name)
        contenido = rol.mention if rol else ""

        await interaction.response.send_message(content=contenido, embed=embed, view=view)
        msg = await interaction.original_response()
        await db.update_encuesta_mensaje(encuesta_id, str(msg.id))

    # ── Comandos ──────────────────────────────────────────────────────────────

    @app_commands.command(name="encuesta", description="[ADMIN] Crea una encuesta con botones y hasta 4 opciones")
    @solo_en_canal('encuestas')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        pregunta="La pregunta de la encuesta",
        op1="Primera opción",
        op2="Segunda opción",
        op3="Tercera opción (opcional)",
        op4="Cuarta opción (opcional)",
        horas="Duración en horas (por defecto 24h)",
        rol="Rol al que mencionar (opcional)",
    )
    async def encuesta(
        self,
        interaction: discord.Interaction,
        pregunta: str,
        op1: str,
        op2: str,
        op3: str = None,
        op4: str = None,
        horas: int = 24,
        rol: discord.Role = None,
    ):
        opciones = [o for o in [op1, op2, op3, op4] if o]
        await self._enviar_encuesta(interaction, "general", pregunta, opciones, max(1, min(horas, 168)), rol)

    @app_commands.command(name="fecha", description="[ADMIN] Vota para elegir la mejor fecha u hora para un evento")
    @solo_en_canal('encuestas')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        evento="Nombre del evento (ej: Rally KvK, Ark of Osiris)",
        op1="Primera opción (ej: Viernes 21:00)",
        op2="Segunda opción",
        op3="Tercera opción (opcional)",
        op4="Cuarta opción (opcional)",
        horas="Duración en horas (por defecto 24h)",
        rol="Rol al que mencionar (opcional)",
    )
    async def fecha(
        self,
        interaction: discord.Interaction,
        evento: str,
        op1: str,
        op2: str,
        op3: str = None,
        op4: str = None,
        horas: int = 24,
        rol: discord.Role = None,
    ):
        opciones = [o for o in [op1, op2, op3, op4] if o]
        await self._enviar_encuesta(interaction, "fecha", f"📅 {evento}", opciones, max(1, min(horas, 168)), rol)

    @app_commands.command(name="si-no", description="[ADMIN] Encuesta rápida de Sí / No")
    @solo_en_canal('encuestas')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        pregunta="La pregunta",
        rol="Rol al que mencionar (opcional)",
    )
    async def si_no(self, interaction: discord.Interaction, pregunta: str, rol: discord.Role = None):
        await self._enviar_encuesta(interaction, "sino", pregunta, ["Sí ✅", "No ❌"], 24, rol)

    @app_commands.command(name="cerrar-encuesta", description="[ADMIN] Cierra una encuesta y muestra resultados finales")
    @app_commands.describe(mensaje_id="ID del mensaje de la encuesta")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cerrar_encuesta(self, interaction: discord.Interaction, mensaje_id: str):
        try:
            msg = await interaction.channel.fetch_message(int(mensaje_id))
        except Exception:
            await interaction.response.send_message("❌ No encontré ese mensaje.", ephemeral=True)
            return

        async with __import__('aiosqlite').connect(__import__('db.database', fromlist=['DB_PATH']).DB_PATH) as conn:
            conn.row_factory = __import__('aiosqlite').Row
            cursor = await conn.execute(
                'SELECT * FROM encuestas WHERE mensaje_id=? AND guild_id=?',
                (str(msg.id), str(interaction.guild_id))
            )
            enc = await cursor.fetchone()

        if not enc:
            await interaction.response.send_message("❌ No encontré esa encuesta en la base de datos.", ephemeral=True)
            return

        await db.close_encuesta(enc["id"])
        opciones = json.loads(enc["opciones"])
        votos    = await db.get_votos(enc["id"])

        embed = build_embed(enc["pregunta"], opciones, votos, enc["tipo"], "Admin")
        embed.title = "🔒  " + embed.title.lstrip("📊📅❓  ")
        embed.set_footer(text=f"Encuesta cerrada · {len(votos)} voto{'s' if len(votos) != 1 else ''} totales")

        view_cerrada = discord.ui.View()
        for i, opcion in enumerate(opciones):
            btn = discord.ui.Button(
                style=ESTILOS[i % 4],
                label=opcion[:80],
                emoji=NUMEROS[i],
                disabled=True,
            )
            view_cerrada.add_item(btn)

        await msg.edit(embed=embed, view=view_cerrada)
        await interaction.response.send_message("✅ Encuesta cerrada.", ephemeral=True)

    @encuesta.error
    @fecha.error
    @si_no.error
    @cerrar_encuesta.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Encuestas(bot))
