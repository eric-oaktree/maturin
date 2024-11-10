import os

import discord
from discord import app_commands
from dotenv import load_dotenv

import orders as ord

# from testing import testing
from diplo import diplo, LETTER_CHANNEL
from loans import loans
from orders import orders
from util import database
from util.tools import ADMIN_ROLES

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PERSONAL = int(os.getenv("PERSONAL_SERVER"))
HSKUCW = int(os.getenv("HSKUCW"))

BOT_ID = int(os.getenv("BOT_ID"))


intents = discord.Intents.default()
intents.members = True
intents.reactions = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

database.initialize()


@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=PERSONAL))
    print(f"We have logged in as {client.user}")


admin = app_commands.Group(
    name="admin",
    description="Admin Commands",
    guild_ids=[PERSONAL],
)


@admin.command(
    name="sync_maturin",
    description="will sync commands with servers",
)
async def sync_maturin(interaction, server: str):
    await tree.sync(guild=discord.Object(id=int(server)))
    await interaction.response.send_message(
        f"Commands Synced with {server} Successfully!"
    )


@admin.command(name="sync_database")
async def sync_database(interaction, sync_roles: bool):
    if str(interaction.user.id) == str(os.getenv("PERSONAL_ID")):
        await interaction.response.defer(ephemeral=True)
        if sync_roles:
            await database.get_active_roles(guild=client.get_guild(int(HSKUCW)))
        database.sync_all_tables()
        database.sync_messages()
        await database.sync_orders()
        await interaction.followup.send("Database synced successfully.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Permission Denied", ephemeral=True)


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # check that the message is from the bot
    if payload.message_author_id != BOT_ID:
        return

    guild = client.get_guild(payload.guild_id)
    letter_channel_obj = [c for c in guild.channels if c.name == LETTER_CHANNEL][0]

    # check guild
    if int(payload.guild_id) != int(HSKUCW):
        return

    # check for apropriate roles
    user = guild.get_member(payload.user_id)
    if user.top_role.name not in ADMIN_ROLES:
        return

    await ord.handle_reaction(payload, letter_channel_obj, guild)


tree.add_command(diplo)
# tree.add_command(testing)
tree.add_command(admin)
tree.add_command(loans)
tree.add_command(orders)

client.run(TOKEN)
