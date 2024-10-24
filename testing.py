import discord
from discord import app_commands
from discord.utils import get
import os
from dotenv import load_dotenv

load_dotenv()
PERSONAL = int(os.getenv("PERSONAL_SERVER"))

testing = app_commands.Group(
    name="testing", description="Testing Commands", guild_ids=[PERSONAL]
)


@testing.command(
    name="test_maturin",
    description="Test command that will parrot things back at you",
)
async def test_maturin(interaction, message: str = None):
    await interaction.response.send_message(f"Hello! I am a robot! You said {message}")


@testing.command(
    name="personal_letter",
    description="create a private thread with a user",
)
@app_commands.describe(user="the user you would like to send the letter to")
async def personal_letter(
    interaction: discord.Interaction, user: discord.Member | discord.Role
):
    channel = client.get_channel(interaction.channel.id)
    u_role = get(interaction.guild.roles, name="Diplo Umpire")
    s_role = get(interaction.guild.roles, name="Spectator")

    thread = await channel.create_thread(
        name=f"PL: {interaction.user.nick} - {user.nick}",
        message=None,
        invitable=False,
        slowmode_delay=21600,
    )
    await thread.send(
        f"Personal letter thread between <@{interaction.user.id}> and with {user.mention}. {u_role.mention} {s_role.mention}"
    )

    await interaction.response.send_message(
        f"Created - Personal Letters: {interaction.user.name} - {user.name}",
        ephemeral=True,
    )


@testing.command(
    name="diplomatic_communications",
    description="create a thread for diplomatic communications between states",
    # guild=discord.Object(id=PERSONAL),
)
@app_commands.describe(
    your_party="the country role of your party",
    other_party="the country role of the other party you want to talk to",
)
async def state_letter(
    interaction: discord.Interaction,
    your_party: discord.Role,
    other_party: discord.Role,
):
    channel = client.get_channel(interaction.channel.id)
    u_role = get(interaction.guild.roles, name="Diplo Umpire")
    s_role = get(interaction.guild.roles, name="Spectator")
    thread = await channel.create_thread(
        name=f"D: {your_party.name} - {other_party.name}",
        message=None,
        invitable=False,
        slowmode_delay=21600,
    )
    await thread.send(
        f"Diplomacy thread between {your_party.mention} and with {other_party.mention}. {u_role.mention} {s_role.mention}"
    )

    await interaction.response.send_message(
        f"Created that thread - Diplomacy: {your_party.name} - {other_party.name}",
        ephemeral=True,
    )
