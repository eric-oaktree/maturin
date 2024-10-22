import os
from datetime import datetime

import discord
import pandas as pd
from discord import app_commands
from discord.utils import get

from util import database
from util.database import create_order, get_orders

PERSONAL = int(os.getenv("PERSONAL_SERVER"))
HSKUCW = int(os.getenv("HSKUCW"))

orders = app_commands.Group(
    name="orders",
    description="Order Commands",
    guild_ids=[PERSONAL, HSKUCW],
)


@orders.command(name="issue_order", description="make an order in game")
@app_commands.describe(
    turn="The turn number you want the order to be in effect for",
    order_type="Movement, Millitary, Economic",
    order="the text of your order",
    order_as="user or role",
)
async def issue_order(
    interaction: discord.Interaction,
    turn: int,
    order_type: str,
    order: str,
    order_as: str = "User",
):
    # defer in case db is slow
    await interaction.response.defer(ephemeral=True)

    # check for length
    if len(order) > 1900:
        msg = f"""
                Your subordinates fall asleep as your orders monologue reaches its third hour...
                Failed to issue {order_as} {order_type} order for turn {turn}
                {order[:1900]}...
            """
        await interaction.followup.send(
            msg,
            ephemeral=True,
        )

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
    active="Leave blank or true if you want to just see active orders. Set to false if you want to see all orders",
)
async def view_orders(interaction: discord.Interaction, turn: int, active: bool = True):
    # defer in case db is slow
    await interaction.response.defer(ephemeral=True)

    # get top role
    trol = interaction.user.top_role

    # get orders
    orders_df = get_orders(
        turn, active=bool(active), user_id=interaction.user.id, role_id=trol.id
    )

    # return orders
    message = []
    for i, order in orders_df.iterrows():
        line = f"{order['order_id']} | {order['user_id']} | {order['role_id']} | {order['order_type']} | {order['order_scope']} \n {order['order_text']} \n {order['timestamp']}"
        message.append(line)

    message = "\n".join(message)

    await interaction.followup.send(message, ephemeral=True)


@orders.command(name="toggle_order", description="toggle the status of an order")
@app_commands.describe(
    turn="The turn number of the order",
    order_id="The order id",
)
async def toggle_order_status(
    interaction: discord.Interaction, order_id: int, turn: int
):
    await interaction.response.defer(ephemeral=True)

    orders_df = get_orders(
        turn=turn,
        order_id=order_id,
    )

    if orders_df.empty:
        await interaction.followup.send("Order not found", ephemeral=True)
        return

    if orders_df.shape[0] > 1:
        await interaction.followup.send("Too many orders found", ephemeral=True)
        return

    index, order = orders_df.itterrows()[0]

    if order["user_id"] == interaction.user.id:
        if order["active"] is False:
            new_status = True
        else:
            new_status = False
        database.execute_sql(
            f"update orders_queue set active=? where id=?",
            params=[new_status, order["order_id"]],
        )

        await interaction.followup.send(f"Updated order id {order['order_id']}")
