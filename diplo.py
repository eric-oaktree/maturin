import os
from datetime import datetime

import discord
import pandas as pd
from discord import app_commands
from discord.utils import get

from util import database, tools

PERSONAL = int(os.getenv("PERSONAL_SERVER"))
HSKUCW = int(os.getenv("HSKUCW"))

if os.getenv("PG_HOST") is None:
    DB = False
else:
    DB = True

LETTER_CHANNEL = os.getenv("LETTER_CHANNEL")


diplo = app_commands.Group(
    name="diplo",
    description="Diplomacy Commands",
    guild_ids=[PERSONAL, HSKUCW],
)


@diplo.command(
    name="send_letter",
    description="send a letter to another player or state inbox",
)
@app_commands.describe(
    recipient="the person or state you are sending the letter too",
    message="the content of your letter",
)
async def send_letter(
    interaction: discord.Interaction,
    recipient: discord.Role | discord.Member,
    message: str,
):
    # TODO - these roles should also be configurable
    u_role = get(interaction.guild.roles, name="Diplo Umpire")
    s_role = get(interaction.guild.roles, name="Spectator")
    d_role = get(interaction.guild.roles, name="Diplomat")
    b_role = get(interaction.guild.roles, name="Banker")
    n_role = get(interaction.guild.roles, name="Newspaper Writer")
    c_role = get(interaction.guild.roles, name="Captured")
    now_stamp = int(datetime.now().timestamp())

    # max_letter_size = 1900
    # if len(message) > max_letter_size:
    #     await interaction.response.send_message(
    #         f"Sorry, your postal system can only handle messages less than {max_letter_size} at this time. {message}",
    #         ephemeral=True,
    #     )
    #     return

    # defering to give time to process - ephemeral true here to make sure all the feedback is hidden
    await interaction.response.defer(ephemeral=True)

    # letter channel is the base channel that all the threads will be under.
    letter_channel = tools.get_channel_obj(interaction, LETTER_CHANNEL)

    # checks the message timelimits. #TODO - make these conifgurable
    if isinstance(recipient, discord.Role):
        gp = 14400
        chk = database.check_message_time(
            interaction.user.top_role.id, recipient.id, now_stamp, gp
        )
        if recipient == n_role:
            chk = None
    elif isinstance(recipient, discord.Member):
        if d_role in interaction.user.roles or b_role in interaction.user.roles:
            gp = 3600
        else:
            gp = 72000
        chk = database.check_message_time(
            interaction.user.id, recipient.id, now_stamp, gp
        )
    else:
        chk = None

    # check if the sender is captured
    if c_role in interaction.user.roles:
        await interaction.followup.send(
            f"You cannot send letters while captured. \n ```{message}```",
            ephemeral=True,
        )

    # bounce back the message if the time limit has not passes
    if chk is not None:
        if isinstance(recipient, discord.Role):
            nm = recipient.name
        elif recipient.nick is None:
            nm = recipient.name
        else:
            nm = recipient.nick

        if len(message) < 1900:
            await interaction.followup.send(
                f"Oh no! The mailman for {nm} has left already! They will be back in <t:{chk}:R> \n ```{message}```",
                ephemeral=True,
            )
        else:
            chann = await interaction.user.create_dm()
            for i in range(0, len(message), 1900):
                if i == 0:
                    adj_message = f"Failed to send: \n ```{message[i : i + 1900]}```"
                else:
                    adj_message = (
                        f"Continuing failed to send: \n ```{message[i : i + 1900]}```"
                    )
                await chann.send(adj_message)
            await interaction.followup.send(
                f"Oh no! The mailman for {nm} has left already! They will be back in <t:{chk}:R> \n Wow, what a wordsmith. We've sent the message you tried to send to your DMs.",
                ephemeral=True,
            )
        return

    # TODO this needs to be absracted when im not in a rush, for now, icky if statement
    ### PLAYERS WORKFLOW
    if isinstance(recipient, discord.Member):
        # check for sender data
        udf = database.user_lookup(str(interaction.user.id))
        if udf.shape[0] == 0:
            # make new user
            database.create_user(
                interaction.user.id, interaction.user.name, interaction.user.nick
            )
            udf = database.user_lookup(str(interaction.user.id))
        elif udf.shape[0] > 1:
            raise ValueError("unique constraint broken")

        udf = udf.iloc[0].to_dict()

        # look for thread
        uth = database.get_user_inbox(str(interaction.user.id))
        if uth.shape[0] > 0:
            uth = uth.iloc[0].to_dict()
        else:
            uth = {"personal_inbox_id": 1}

        thread = letter_channel.get_thread(int(uth["personal_inbox_id"]))
        if thread is None:
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
                database.create_user_inbox(
                    str(udf["user_id"]), str(thread.id), thread.name
                )
            except:
                database.update_user_inbox(
                    str(udf["user_id"]), str(thread.id), thread.name
                )
            uth = {
                "user_id": str(interaction.user.id),
                "personal_inbox_id": str(thread.id),
                "personal_inbox_name": thread.name,
            }

        # resolve recipient name
        if recipient.nick is None:
            recp_name = recipient.name
        else:
            recp_name = recipient.nick

        # send letter to sender thread
        for i in range(0, len(message), 1900):
            if i == 0:
                adj_message = (
                    f"Sent letter to **{recp_name}**: \n```{message[i : i + 1900]}```"
                )
            else:
                adj_message = f"Continuing letter to **{recp_name}**: \n```{message[i : i + 1900]}```"
            await thread.send(adj_message)

        # make sure recipient has thread
        rdf = database.user_lookup(str(recipient.id))
        if rdf.shape[0] == 0:
            # make new user
            database.create_user(recipient.id, recipient.name, recipient.nick)
            rdf = database.user_lookup(str(recipient.id))
        elif rdf.shape[0] > 1:
            raise ValueError("unqiue constraint broken")

        rdf = rdf.iloc[0].to_dict()
        # look for thread
        rth = database.get_user_inbox(str(recipient.id))
        if rth.shape[0] > 0:
            rth = rth.iloc[0].to_dict()
        else:
            rth = {"personal_inbox_id": 1}

        thread = letter_channel.get_thread(int(rth["personal_inbox_id"]))
        if thread is None:
            # make new thread
            # build the recipient letter thread name
            if isinstance(recipient, discord.Member):
                thread_name = f"{recp_name} Personal Letters"
            elif isinstance(recipient, discord.Role):
                thread_name = f"{recp_name} Letters"

            # if thread does not exist create thread

            thread = await letter_channel.create_thread(
                name=thread_name,
                message=None,
                invitable=False,
            )
            await thread.send(f"{u_role.mention} {s_role.mention} {recipient.mention}")

            # save thread
            try:
                database.create_user_inbox(
                    str(rdf["user_id"]), str(thread.id), thread.name
                )
            except:
                database.update_user_inbox(
                    str(rdf["user_id"]), str(thread.id), thread.name
                )
            rth = {
                "user_id": str(rdf["user_id"]),
                "personal_inbox_id": str(thread.id),
                "personal_inbox_name": thread.name,
            }

        # resolve sender name
        if interaction.user.nick is None:
            sender_name = interaction.user.name
        else:
            sender_name = interaction.user.nick

        if c_role not in recipient.roles:
            # send letter to recipient thread
            for i in range(0, len(message), 1900):
                if i == 0:
                    adj_message = f"Letter from **{sender_name}**: \n```{message[i : i + 1900]}```"
                else:
                    adj_message = f"Continuing letter from **{sender_name}**: \n```{message[i : i + 1900]}```"
                await thread.send(adj_message)

        # save message to message table
        if c_role in recipient.roles:
            message = message + " <CAPTURED_REC>"

        database.create_message(udf["user_id"], rdf["user_id"], now_stamp, message)

        await interaction.followup.send(
            f"Sent letter to **{recp_name}**, next in <t:{now_stamp + gp}:R>",
            ephemeral=True,
        )

        if DB:
            database.sync_messages()

    ### ROLES WORKFLOW
    elif isinstance(recipient, discord.Role):
        # check for sender data
        udf = database.role_lookup(str(interaction.user.top_role.id))
        if udf.shape[0] == 0:
            # make new user
            database.create_role(
                interaction.user.top_role.id,
                interaction.user.top_role.name,
            )
            udf = database.role_lookup(str(interaction.user.top_role.id))
        elif udf.shape[0] > 1:
            raise ValueError("unique constraint broken")

        udf = udf.iloc[0].to_dict()

        # look for thread
        uth = database.get_user_inbox(str(interaction.user.top_role.id))
        if uth.shape[0] == 0:
            # make new thread
            thread_name = f"{udf['name']} State Letters"

            ## if it's being sent to a newspaper writer, don't do it
            if recipient != n_role:

                thread = await letter_channel.create_thread(
                    name=thread_name,
                    message=None,
                    invitable=False,
                )
                await thread.send(
                    f"{u_role.mention} {s_role.mention} {interaction.user.top_role.mention}"
                )

                # save thread
                database.create_user_inbox(
                    str(udf["role_id"]), str(thread.id), thread.name
                )
                uth = {
                    "role_id": str(interaction.user.top_role.id),
                    "personal_inbox_id": str(thread.id),
                    "personal_inbox_name": thread.name,
                }

        if isinstance(uth, pd.DataFrame):
            uth = uth.iloc[0].to_dict()

        # resolve recipient name
        recp_name = recipient.name

        if interaction.user.nick is None:
            s_n = interaction.user.name
        else:
            s_n = interaction.user.nick

        ## if it's being sent to a newspaper writer, don't do it
        if recipient != n_role:

            # send letter to sender thread
            thread = letter_channel.get_thread(int(uth["personal_inbox_id"]))
            for i in range(0, len(message), 1900):
                if i == 0:
                    adj_message = f"**{s_n.title()}** sent state letter to **{recp_name}**: \n```{message[i : i + 1900]}```"
                else:
                    adj_message = f"continuing statue letter from **{s_n.title()}** to **{recp_name}**: \n```{message[i : i + 1900]}```"
                await thread.send(adj_message)

        # make sure recipient has thread
        rdf = database.role_lookup(str(recipient.id))
        if rdf.shape[0] == 0:
            # make new user
            database.create_role(recipient.id, recipient.name)
            rdf = database.role_lookup(str(recipient.id))
        elif rdf.shape[0] > 1:
            raise ValueError("unqiue constraint broken")

        rdf = rdf.iloc[0].to_dict()
        # look for thread
        rth = database.get_user_inbox(str(recipient.id))
        if rth.shape[0] == 0:
            # make new thread
            # build the recipient letter thread name
            thread_name = f"{recp_name} State Letters"

            # if thread does not exist create thread

            thread = await letter_channel.create_thread(
                name=thread_name,
                message=None,
                invitable=False,
            )
            await thread.send(f"{u_role.mention} {s_role.mention} {recipient.mention}")

            # save thread
            database.create_user_inbox(str(rdf["role_id"]), str(thread.id), thread.name)
            rth = {
                "role_id": str(rdf["role_id"]),
                "personal_inbox_id": str(thread.id),
                "personal_inbox_name": thread.name,
            }

        if isinstance(rth, pd.DataFrame):
            rth = rth.iloc[0].to_dict()

        # resolve sender name
        sender_name = interaction.user.top_role.name

        # send letter to recipient thread
        thread = letter_channel.get_thread(int(rth["personal_inbox_id"]))

        if thread is None:
            interaction.followup.send(
                f"That receipient does not exist? Ask for help. \n {message}",
                ephemeral=True,
            )
            print(recipient.name)
            return

        for i in range(0, len(message), 1900):
            if i == 0:
                adj_message = (
                    f"Letter from **{sender_name}**: \n```{message[i : i + 1900]}```"
                )
            else:
                adj_message = f"continuing letter from **{sender_name}**: \n```{message[i : i + 1900]}```"
            await thread.send(adj_message)

        # save message to message table
        database.create_message(udf["role_id"], rdf["role_id"], now_stamp, message)
        await database.get_active_roles(
            interaction.guild,
            user=interaction.user,
        )

        await interaction.followup.send(
            f"Sent letter to **{recp_name}**, next in <t:{now_stamp + gp}:R>",
            ephemeral=True,
        )

        if DB:
            database.sync_messages()
