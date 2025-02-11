import discord
import os
from util import database
from discord.utils import get

LETTER_CHANNEL = os.getenv("LETTER_CHANNEL")
DIPLO_UMPIRE_ROLE = os.getenv("DIPLO_UMPIRE_ROLE")
SPECTATOR_ROLE = os.getenv("SPECTATOR_ROLE")


def get_channel_obj(
    interaction: discord.Interaction, channel_name: str
) -> discord.TextChannel:
    # check to make sure that a letter channel exists
    for channel in interaction.guild.channels:
        if channel.name == channel_name:
            return interaction.guild.get_channel(int(channel.id))

    print("Could not find channel", channel_name)
    return None


ADMIN_ROLES = [
    "Lead Umpire",
    "Assistant Umpire",
]


async def get_or_create_user_thread(interaction: discord.Interaction):
    u_role = get(interaction.guild.roles, name=DIPLO_UMPIRE_ROLE)
    s_role = get(interaction.guild.roles, name=SPECTATOR_ROLE)

    udf = database.user_lookup(str(interaction.user.id))
    if udf.shape[0] == 0:
        # make new user
        database.create_user(
            interaction.user.id, interaction.user.name, interaction.user.nick
        )
        udf = database.user_lookup(str(interaction.user.id))

    udf = udf.iloc[0].to_dict()

    uth = database.get_user_inbox(str(interaction.user.id))
    if uth.shape[0] > 0:
        uth = uth.iloc[0].to_dict()
    else:
        uth = {"personal_inbox_id": 1}

    letter_channel = [
        c for c in interaction.guild.channels if c.name == LETTER_CHANNEL
    ][0]

    thread = letter_channel.get_thread(int(uth["personal_inbox_id"]))
    if thread is None:
        print(
            "Could not find thread for letter channel",
            letter_channel,
            int(uth["personal_inbox_id"]),
        )
        # make new thread
        if udf["nick"] == "None":
            thread_name = f"{udf['name']} Personal Letters"
        else:
            thread_name = f"{udf['nick']} Personal Letters"

        # if thread does not exist create thread

        thread = await letter_channel.create_thread(
            name=thread_name,
            message=None,
            invitable=False,
        )
        await thread.send(
            f"{u_role.mention} {s_role.mention} {interaction.user.mention}"
        )

        try:
            database.create_user_inbox(str(udf["user_id"]), str(thread.id), thread.name)
        except:
            database.update_user_inbox(str(udf["user_id"]), str(thread.id), thread.name)

    return thread
