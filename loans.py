import os

import discord
from discord import app_commands
from discord.utils import get

from util import database

PERSONAL = int(os.getenv("PERSONAL_SERVER"))
HSKUCW = int(os.getenv("HSKUCW"))


LETTER_CHANNEL = os.getenv("LETTER_CHANNEL")


loans = app_commands.Group(
    name="loans",
    description="Commands for loan management",
    guild_ids=[PERSONAL, HSKUCW],
)


@loans.command(
    name="submit_bid",
    description="submit an npc loan bid",
)
@app_commands.describe(
    interest="the interest reate (annual) that you are bidding",
    amount="the amount of the bid",
    term="the term of the bid, in turns",
)
async def submit_bid(
    interaction: discord.Interaction, interest: float, amount: int, term: int
):
    # request metadata
    trole_id = interaction.user.top_role.id
    u_role = get(interaction.guild.roles, name="Diplo Umpire")
    s_role = get(interaction.guild.roles, name="Spectator")
    if interaction.user.nick is None:
        usr = interaction.user.name
    else:
        usr = interaction.user.nick

    # see if bid has been submitted
    df = database.get_sql(
        f"select * from loans where role_id = {trole_id} and active is true"
    )

    # if bid has been submitted already, overwrite the bid
    if not df.empty:
        database.execute_sql(
            "update loans set interest = ?, term = ?, amount = ?, submitted = CURRENT_TIMESTAMP where role_id = ? and active is true",
            commit=True,
            params=[interest / 100, term, amount, trole_id],
        )
    # if empty create a new bid
    elif df.empty:
        database.execute_sql(
            "insert into loans (role_id, interest, amount, term, submitted, active) values (?, ?, ?, ?, CURRENT_TIMESTAMP, true)",
            commit=True,
            params=[
                trole_id,
                interest / 100,
                amount,
                term,
            ],
        )

    # send a record of the bid to the state letter thread
    # letter channel is the base channel that all the threads will be under.
    letter_channel_id = None
    # check to make sure that a letter channel exists
    for channel in interaction.guild.channels:
        if channel.name == LETTER_CHANNEL:
            letter_channel_id = channel.id

    if letter_channel_id is None:
        raise ValueError
    letter_channel = interaction.guild.get_channel(int(letter_channel_id))

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

    uth = database.get_user_inbox(str(interaction.user.top_role.id))
    if uth.shape[0] == 0:
        # make new thread
        thread_name = f"{udf['name']} State Letters"

        thread = await letter_channel.create_thread(
            name=thread_name,
            message=None,
            invitable=False,
        )
        await thread.send(
            f"{u_role.mention} {s_role.mention} {interaction.user.top_role.mention}"
        )

        # save thread
        database.create_user_inbox(str(udf["role_id"]), str(thread.id), thread.name)
        uth = {
            "role_id": str(interaction.user.top_role.id),
            "personal_inbox_id": str(thread.id),
            "personal_inbox_name": thread.name,
        }

    # send the notification
    thread = letter_channel.get_thread(int(uth["personal_inbox_id"].iloc[0]))
    message = f"""{usr} submitted ${amount} IMF bid at {interest}% for {term} turns"""
    await thread.send(message)

    await interaction.response.send_message(
        f"Bid Submitted! Good Luck!",
        ephemeral=True,
    )


@loans.command(
    name="view_bid",
    description="view your currently submitted bid, if admin, view all active bids in rank order",
)
async def view_bid(interaction: discord.Interaction):
    trole_id = interaction.user.top_role.id
    au_role = get(interaction.guild.roles, name="Assistant Umpire")
    u_role = get(interaction.guild.roles, name="Lead Umpire")

    is_umpire = False
    if interaction.user.top_role == au_role or interaction.user.top_role == u_role:
        is_umpire = True

    # get active bids for user
    if not is_umpire:
        df = database.get_sql(
            f"select * from loans where role_id = {trole_id} and active is true"
        )
    elif is_umpire:
        df = database.get_sql(
            f"""
                select
                    r.name as role_name,
                    interest,
                    amount,
                    term
                from loans l 
                join roles r on l.role_id = r.role_id 
                where active is true
            """
        )
    else:
        await interaction.response.send_message(
            f"You do not have a valid role.",
            ephemeral=True,
        )
        return

    if df.empty:
        await interaction.response.send_message(
            f"There are no active bids submitted.",
            ephemeral=True,
        )
    else:
        if not is_umpire:
            for i, row in df.iterrows():
                message = f"""
                    Your current bid is ${row['amount']} for {row['term']} turns at {row['interest'] * 100}%
                """
                break
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )
        elif is_umpire:
            master_message = ""
            for i, row in df.iterrows():
                message = f"""
                     {row['role_name']} ${row['amount']} for {row['term']} turns at {row['interest'] * 100}%
                """
                master_message += message
            await interaction.response.send_message(
                master_message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"You do not have a valid role.",
                ephemeral=True,
            )
            return


@loans.command(
    name="clear_bid",
    description="clear (delete) your currently submitted bid, if admin, delete all active bids in rank order",
)
async def clear_bid(interaction: discord.Interaction):
    trole_id = interaction.user.top_role.id
    au_role = get(interaction.guild.roles, name="Assistant Umpire")
    u_role = get(interaction.guild.roles, name="Lead Umpire")

    is_umpire = False
    if interaction.user.top_role == au_role or interaction.user.top_role == u_role:
        is_umpire = True

    if is_umpire:
        database.execute_sql(
            "update loans set active = false where active is true", commit=True
        )
    else:
        database.execute_sql(
            f"update loans set active = false where active is true and role_id = {trole_id}",
            commit=True,
        )

    await interaction.response.send_message(
        f"Cleared Loan Data",
        ephemeral=True,
    )
