from discord import app_commands, Interaction
from db import database as db


def solo_en_canal(tipo: str):
    """Restringe un comando al canal configurado para ese tipo."""
    async def predicate(interaction: Interaction) -> bool:
        config = await db.get_canal_config(str(interaction.guild_id), tipo)
        if not config:
            return True  # Sin restricción configurada → funciona en cualquier canal
        if config['canal_id'] == str(interaction.channel_id):
            return True
        canal = interaction.guild.get_channel(int(config['canal_id']))
        raise app_commands.CheckFailure(
            f'❌ Este comando solo funciona en {canal.mention if canal else "el canal configurado"}.\n'
            f'Usa `/config-canal` para cambiar la configuración.'
        )
    return app_commands.check(predicate)
