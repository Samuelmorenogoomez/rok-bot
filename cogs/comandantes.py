import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_BOT
from checks import solo_en_canal
from data.rok_data import (
    COMANDANTES, TIER_EMOJI, ROL_EMOJI, TROPA_EMOJI, FASE_LABEL,
    buscar_comandante, get_equipo, get_accesorios,
)

_image_cache: dict[str, str | None] = {}


async def fetch_commander_image(wiki_name: str) -> str | None:
    if wiki_name in _image_cache:
        return _image_cache[wiki_name]
    try:
        url = "https://riseofkingdoms.fandom.com/api.php"
        params = {
            "action": "query",
            "titles": f"Commanders/{wiki_name}",
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": "300",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    _image_cache[wiki_name] = None
                    return None
                data = await resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    img = page.get("thumbnail", {}).get("source")
                    _image_cache[wiki_name] = img
                    return img
    except Exception:
        pass
    _image_cache[wiki_name] = None
    return None


def build_gear_lines(equipo: dict) -> str:
    return "\n".join(f"{slot} **{pieza}**" for slot, pieza in equipo.items() if slot != "nota")


class Comandantes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='comandante', description='Info completa y equipo recomendado para cualquier comandante')
    @solo_en_canal('comandantes')
    @app_commands.describe(nombre='Nombre del comandante (parcial también funciona: "guan", "salad", "nevsky"...)')
    async def comandante(self, interaction: discord.Interaction, nombre: str):
        await interaction.response.defer()

        key, cmd = buscar_comandante(nombre)
        if not cmd:
            await interaction.followup.send(
                f'❌ No encontré a **{nombre}**. Prueba con nombre parcial (ej: "guan", "nevsky", "zhuge").',
                ephemeral=True
            )
            return

        tropa      = cmd["tropa"]
        rol        = cmd["roles"][0]
        acc_style  = cmd.get("acc_style", "habilidad")
        accs       = get_accesorios(acc_style)
        equipo     = get_equipo(tropa, rol, "final")
        imagen     = await fetch_commander_image(cmd["wiki"])

        embed = discord.Embed(
            title=f'{TIER_EMOJI[cmd["tier"]]} {cmd["nombre"]} — Tier {cmd["tier"]}',
            description=cmd["descripcion"],
            color=COLOR_BOT
        )

        if imagen:
            embed.set_thumbnail(url=imagen)

        embed.add_field(name="Tropa",       value=TROPA_EMOJI.get(tropa, tropa), inline=True)
        embed.add_field(name="Roles",       value=" · ".join(ROL_EMOJI[r] for r in cmd["roles"]), inline=True)
        embed.add_field(name="Pareja top",  value=f'**{cmd["pareja"]}**', inline=True)
        embed.add_field(name="Pareja alt",  value=cmd["pareja_alt"], inline=True)
        embed.add_field(name="Fortaleza",   value=cmd["fortaleza"], inline=False)

        if equipo:
            gear_lines = build_gear_lines(equipo)
            gear_lines += f'\n{accs["💍 Acc 1"]} _(acc 1)_\n{accs["💍 Acc 2"]} _(acc 2)_'
            nota = equipo.get("nota", "")
            if accs.get("nota_acc"):
                nota += f"\n_{accs['nota_acc']}_"
            embed.add_field(
                name=f'🏆 Equipo endgame · {ROL_EMOJI[rol]}',
                value=gear_lines,
                inline=False
            )
            if nota.strip():
                embed.add_field(name="💡 Consejo", value=nota.strip(), inline=False)

        embed.set_footer(text="Usa /equipo para ver otras fases y roles · /mi-equipo para tu build personal")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='equipo', description='Equipamiento recomendado por tipo de tropa, rol y fase')
    @solo_en_canal('comandantes')
    @app_commands.choices(
        tropa=[
            app_commands.Choice(name="🗡️ Infantería",  value="infanteria"),
            app_commands.Choice(name="🐴 Caballería",  value="caballeria"),
            app_commands.Choice(name="🏹 Arqueros",    value="arqueros"),
            app_commands.Choice(name="⚙️ Maquinaria", value="maquinaria"),
            app_commands.Choice(name="🔱 Universal",   value="universal"),
        ],
        rol=[
            app_commands.Choice(name="⚔️ Campo abierto", value="campo"),
            app_commands.Choice(name="🚩 Rally",          value="rally"),
            app_commands.Choice(name="🏰 Guarnición",     value="guarnicion"),
            app_commands.Choice(name="🌾 Recolección",    value="recolectar"),
        ],
        fase=[
            app_commands.Choice(name="🏆 Endgame",       value="final"),
            app_commands.Choice(name="⚡ Fase media",    value="medio"),
            app_commands.Choice(name="🌱 Fase temprana", value="temprano"),
        ],
    )
    async def equipo(self, interaction: discord.Interaction, tropa: str, rol: str, fase: str = "final"):
        equipo = get_equipo(tropa, rol, fase)
        if not equipo:
            await interaction.response.send_message(
                "❌ No hay datos para esa combinación. Prueba otra fase o rol.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f'Equipo — {TROPA_EMOJI.get(tropa, tropa)}',
            description=f'{ROL_EMOJI[rol]} · {FASE_LABEL[fase]}',
            color=COLOR_BOT
        )
        embed.add_field(name="Piezas", value=build_gear_lines(equipo), inline=False)
        nota = equipo.get("nota", "")
        if nota:
            embed.add_field(name="💡 Consejo", value=nota, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='mi-equipo', description='Muestra tu equipo recomendado según tu perfil')
    @solo_en_canal('comandantes')
    async def mi_equipo(self, interaction: discord.Interaction):
        from db import database as db
        miembro = await db.get_member(str(interaction.guild_id), str(interaction.user.id))
        if not miembro:
            await interaction.response.send_message(
                "❌ No tienes perfil. Usa `/registrar` primero.", ephemeral=True
            )
            return

        tropa = miembro["tropa"]
        if tropa == "mixto":
            await interaction.response.send_message(
                "⚠️ Tipo de tropa en **Mixto**. Usa `/equipo` y elige tu tropa principal.", ephemeral=True
            )
            return

        equipo = get_equipo(tropa, "campo", "final")
        if not equipo:
            await interaction.response.send_message(
                f"❌ No hay datos para {tropa} todavía.", ephemeral=True
            )
            return

        acc_style = "habilidad"
        accs = get_accesorios(acc_style)
        TROPAS_NOMBRE = {"infanteria": "🗡️ Infantería", "caballeria": "🐴 Caballería", "arqueros": "🏹 Arqueros", "maquinaria": "⚙️ Maquinaria"}

        embed = discord.Embed(
            title=f'Equipo de {interaction.user.display_name}',
            description=f'{TROPAS_NOMBRE.get(tropa, tropa)} · ⚔️ Campo · 🏆 Endgame',
            color=COLOR_BOT
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        gear = build_gear_lines(equipo) + f'\n{accs["💍 Acc 1"]} _(acc 1)_\n{accs["💍 Acc 2"]} _(acc 2)_'
        embed.add_field(name="Piezas", value=gear, inline=False)
        nota = equipo.get("nota", "")
        if nota:
            embed.add_field(name="💡 Consejo", value=nota, inline=False)
        embed.set_footer(text="Usa /equipo para ver otras fases y roles")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='comandantes-lista', description='Lista todos los comandantes disponibles')
    @solo_en_canal('comandantes')
    @app_commands.choices(tropa=[
        app_commands.Choice(name="🗡️ Infantería",  value="infanteria"),
        app_commands.Choice(name="🐴 Caballería",  value="caballeria"),
        app_commands.Choice(name="🏹 Arqueros",    value="arqueros"),
        app_commands.Choice(name="⚙️ Maquinaria", value="maquinaria"),
        app_commands.Choice(name="🔱 Universal",   value="universal"),
        app_commands.Choice(name="📋 Todos",       value="todos"),
    ])
    async def comandantes_lista(self, interaction: discord.Interaction, tropa: str = "todos"):
        ORDEN_TIER = {"S+": 0, "S": 1, "A": 2, "B": 3, "C": 4, "F": 5}
        filtrados = [
            cmd for cmd in COMANDANTES.values()
            if tropa == "todos" or cmd["tropa"] == tropa
        ]
        filtrados.sort(key=lambda c: (ORDEN_TIER.get(c["tier"], 9), c["nombre"]))

        por_tropa: dict[str, list] = {}
        for cmd in filtrados:
            t = TROPA_EMOJI.get(cmd["tropa"], cmd["tropa"])
            por_tropa.setdefault(t, []).append(cmd)

        embed = discord.Embed(
            title="📋 Comandantes disponibles",
            description="Usa `/comandante [nombre]` para ver info y equipo completo.",
            color=COLOR_BOT
        )

        for grupo, cmds in por_tropa.items():
            lineas = [f'{TIER_EMOJI[c["tier"]]} **{c["nombre"]}** — {" · ".join(ROL_EMOJI[r] for r in c["roles"])}' for c in cmds]
            text = "\n".join(lineas)
            embed.add_field(name=grupo, value=text[:1000], inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Comandantes(bot))
