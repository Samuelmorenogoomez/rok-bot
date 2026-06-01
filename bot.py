import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from db.database import init_db

load_dotenv()

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

COGS = [
    'cogs.titulos',
    'cogs.eventos',
    'cogs.miembros',
    'cogs.kvk',
    'cogs.comandantes',
    'cogs.encuestas',
    'cogs.admin',
    'cogs.bienvenida',
    'cogs.mensajes',
    'cogs.stats',
    'cogs.mge',
    'cogs.reclutamiento',
]


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    import traceback
    if isinstance(error, discord.app_commands.CheckFailure):
        msg = str(error) if str(error) else '❌ No puedes usar este comando aquí.'
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass
    else:
        print(f'[ERROR] /{interaction.command.name if interaction.command else "?"}: {type(error).__name__}: {error}')
        traceback.print_exc()
        try:
            await interaction.response.send_message(f'❌ Error interno: `{error}`', ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send(f'❌ Error interno: `{error}`', ephemeral=True)
            except Exception:
                pass


@bot.event
async def on_ready():
    guild_id = os.getenv('GUILD_ID')
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        # Copiar comandos globales al servidor y sincronizar solo ahí
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        # Limpiar comandos globales de Discord para evitar duplicados
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print(f'✅ Comandos sincronizados al servidor {guild_id}')
    else:
        await bot.tree.sync()
    print(f'✅ Bot conectado como {bot.user}')
    print(f'   Servidores: {len(bot.guilds)}')
    print(f'   Cogs cargados: {", ".join(COGS)}')


async def main():
    async with bot:
        await init_db()
        for cog in COGS:
            await bot.load_extension(cog)
        await bot.start(os.getenv('DISCORD_TOKEN'))


if __name__ == '__main__':
    asyncio.run(main())
