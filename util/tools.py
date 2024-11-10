import discord


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
