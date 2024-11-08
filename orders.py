import os
from datetime import datetime

import discord
import pandas as pd
from discord import app_commands
from discord.utils import get

from util import database, tools
from util.database import create_order, get_orders
from typing import Literal
from discord.utils import get

PERSONAL = int(os.getenv("PERSONAL_SERVER"))
HSKUCW = int(os.getenv("HSKUCW"))

ECON_CHANNEL = str(os.getenv("ECON_CHANNEL"))
MOVE_CHANNEL = str(os.getenv("MOVE_CHANNEL"))
MIL_CHANNEL = str(os.getenv("MIL_CHANNEL"))


orders = app_commands.Group(
    name="orders",
    description="Order Commands",
    guild_ids=[PERSONAL, HSKUCW],
)


@orders.command(name="issue_order", description="make an order in game")
@app_commands.describe(
    turn="The turn number you want the order to be in effect for",
    order_type="Movement, Military, Economic",
    order="the text of your order",
    order_as="user or role",
)
async def issue_order(
    interaction: discord.Interaction,
    turn: int,
    order_type: Literal["Move", "Military", "Econ"],
    order: str,
    order_as: Literal["User", "Role"] = "User",
):
    # defer in case db is slow
    await interaction.response.defer(ephemeral=True)

    # check for length
    if len(order) > 1900:
        msg = f"""
                Your subordinates fall asleep as your monologue reaches its third hour...
                Failed to issue {order_as} {order_type} order for turn {turn}.
                {order[:1900]}...
            """
        await interaction.followup.send(
            msg,
            ephemeral=True,
        )

    # autoset invalid type scope combinations
    if order_type == "Move" and order_as == "Role":
        order_as = "User"

    if order_type == "Econ" and order_as == "User":
        order_as = "Role"

    # get top role
    trol = interaction.user.top_role

    # create order
    create_order(
        turn=turn,
        order_type=order_type,
        order_text=order,
        role_id=trol.id,
        user_id=interaction.user.id,
        order_scope=order_as,
    )

    # return confirmation message
    msg = f"""
        Issued {order_as} {order_type} order for turn {turn}
        {order}
    """
    await interaction.followup.send(
        msg,
        ephemeral=True,
    )


@orders.command(name="view_orders", description="view orders")
@app_commands.describe(
    turn="The turn number you want the order to be in effect for",
)
async def view_orders(interaction: discord.Interaction, turn: int):
    # defer in case db is slow
    await interaction.response.defer(ephemeral=True)

    # get top role
    trol = interaction.user.top_role

    # get orders
    orders_df = get_orders(turn)
    # print(orders_df.head())

    if orders_df.empty:
        await interaction.followup.send("No Orders Found", ephemeral=True)
        return

    # filter DF for orders that they are allowed to see
    orders_df = orders_df.loc[
        (orders_df["user_id"] == str(interaction.user.id))
        | (
            (orders_df["role_id"] == str(trol.id))
            & (orders_df["order_scope"] == "Role")
        )
    ]

    # return orders
    message = []
    for i, order in orders_df.iterrows():
        line = construct_line(order)
        message.append(line)

    message = "\n".join(message)

    await interaction.followup.send(message, ephemeral=True)


def construct_line(order):
    line = f"{order.get('order_id')} | {order.get('username')} | {order.get('role')} | {order.get('order_type')} | {order.get('order_scope')} | {order.get('order_text')} | <t:{order.get('timestamp')}:f> | {order.get('status')}"
    return line


@orders.command(name="delete_order", description="delete and order. No recovery.")
@app_commands.describe(
    turn="The turn number of the order",
    order_id="The order id",
)
async def delete_order(interaction: discord.Interaction, order_id: int, turn: int):
    await interaction.response.defer(ephemeral=True)

    orders_df = get_orders(
        turn=int(turn),
    )

    orders_df = orders_df.loc[orders_df["user_id"] == str(interaction.user.id)]
    orders_df = orders_df.loc[orders_df["order_id"] == order_id]

    if orders_df.empty:
        await interaction.followup.send("Order not found", ephemeral=True)
        return

    if orders_df.shape[0] > 1:
        # print(orders_df.head())
        await interaction.followup.send("Too many orders found", ephemeral=True)
        return

    order = orders_df.iloc[0]

    if order["user_id"] == str(interaction.user.id):
        database.execute_sql(
            f"delete from orders_queue where order_id=? and user_id=? and turn = ?",
            params=[int(order["order_id"]), str(interaction.user.id), int(turn)],
            commit=True,
        )

        await interaction.followup.send(
            f"Deleted order id {order['order_id']}", ephemeral=True
        )
        return

    else:
        await interaction.followup.send(
            f"You cannot delete someone else's orders", ephemeral=True
        )
        return


@orders.command(
    name="print_orders",
    description="Admin Only - Puts the orders in the orders channel",
)
@app_commands.describe(
    turn="The turn number of the order",
)
async def print_orders(interaction: discord.Interaction, turn: int):
    await interaction.response.defer(ephemeral=True)

    channels = {
        "Econ": tools.get_channel_obj(interaction, ECON_CHANNEL),
        "Military": tools.get_channel_obj(interaction, MIL_CHANNEL),
        "Move": tools.get_channel_obj(interaction, MOVE_CHANNEL),
    }

    # check that the user has the admin role
    admin_role_objs = [get(interaction.guild.roles, name=i) for i in ADMIN_ROLES]
    trol = interaction.user.top_role
    if trol not in admin_role_objs:
        await interaction.followup.send(f"You are not an Admin...", ephemeral=True)
        return

    # grab all orders for turn
    orders_df = get_orders(turn)

    # post a turn message to the econ, orders, moves channels
    for channel in channels.values():
        await channel.send(f"## Turn {turn}")

    # iterate through roles and post to a channel
    roles = list(orders_df["role_id"].unique())
    for role in roles:
        # filter df
        tmp_df = orders_df[orders_df["role_id"] == role]
        rname = list(tmp_df["role"].unique())[0]

        for channel in channels.values():
            await channel.send(f"### {rname}")

        for i, record in tmp_df.iterrows():
            msg = construct_line(record)
            await channels[record["order_type"]].send(msg)

    await interaction.followup.send(f"Orders Printed", ephemeral=True)
    return


async def handle_reaction(
    payload: discord.RawReactionActionEvent,
    letter_channel: discord.TextChannel,
    guild: discord.Guild,
):

    # check for message content

    react_channel = guild.get_channel(payload.channel_id)
    message = await react_channel.fetch_message(payload.message_id)
    if payload.emoji.name == "✅":
        # grab order id
        order_id = message.content.split("|")[0].strip()
        # grab order from db
        odf = database.get_order_by_id(int(order_id))
        # make order complete entry in order status table
        database.execute_sql(
            "insert into order_status (order_id, user_id, status, time) values (?, ?, ?, ?)",
            params=[
                order_id,
                payload.user_id,
                "Complete",
                int(datetime.now().timestamp()),
            ],
        )
        # send complete event
        if odf.iloc[0]["order_scope"] == "Role":
            t_id = odf.iloc[0]["role_id"]
        else:
            t_id = odf.iloc[0]["user_id"]

        inbox_df = database.get_user_inbox(t_id)
        if inbox_df.empty:
            print("No thread for that id", t_id)
            return None

        thread = letter_channel.get_thread(int(inbox_df["personal_inbox_id"].iloc[0]))
        await thread.send(
            f"Order Number {order_id}, turn {odf.iloc[0]['turn']} is complete. \n {odf.iloc[0]['order_text']}"
        )
