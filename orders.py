import os
from datetime import datetime
from dotenv import load_dotenv

import discord
import pandas as pd
from discord import app_commands
from discord.utils import get

from util import database
from util.database import create_order, get_orders

load_dotenv()
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
    await interaction.response.defer(ephemeral=True)

    if len(order) > 1900:
        await send_order_too_long_message(interaction, order, order_as, order_type, turn)
        return

    trol = interaction.user.top_role

    create_order(
        turn=turn,
        order_type=order_type,
        order_text=order,
        role_id=trol.id,
        user_id=interaction.user.id,
        order_scope=order_as,
    )

    await send_order_confirmation_message(interaction, order_as, order_type, turn, order)


async def send_order_too_long_message(interaction, order, order_as, order_type, turn):
    msg = f"""
        Your subordinates fall asleep as your orders monologue reaches its third hour...
        Failed to issue {order_as} {order_type} order for turn {turn}
        {order[:1900]}...
    """
    await interaction.followup.send(
        msg,
        ephemeral=True,
    )


async def send_order_confirmation_message(interaction, order_as, order_type, turn, order):
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
    await interaction.response.defer(ephemeral=True)

    trol = interaction.user.top_role

    orders_df = get_orders(turn, user_id=interaction.user.id, role_id=trol.id)

    if orders_df.empty:
        await interaction.followup.send("No Orders Found", ephemeral=True)
        return

    message = format_orders_message(orders_df)
    await interaction.followup.send(message, ephemeral=True)


def format_orders_message(orders_df):
    message = []
    for i, order in orders_df.iterrows():
        line = f"{order['order_id']} | {order['user_id']} | {order['role_id']} | {order['order_type']} | {order['order_scope']} \n {order['order_text']} \n {order['timestamp']}"
        message.append(line)
    return "\n".join(message)


@orders.command(name="delete_order", description="delete and order. No recovery.")
@app_commands.describe(
    turn="The turn number of the order",
    order_id="The order id",
)
async def delete_order(interaction: discord.Interaction, order_id: int, turn: int):
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

    index, order = orders_df.iterrows()[0]

    if order["user_id"] == interaction.user.id:
        database.execute_sql(
            f"delete from orders_queue where id=?",
            params=[
                order["order_id"],
            ],
        )

        await interaction.followup.send(
            f"Updated order id {order['order_id']}", ephemeral=True
        )
        return

    else:
        await interaction.followup.send(
            f"You cannot delete someone else's orders", ephemeral=True
        )
        return
