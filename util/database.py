import os
from multiprocessing.managers import Value
from typing import List

import discord
import duckdb
import pandas as pd
from duckdb.duckdb import ParserException
from datetime import datetime
import numpy as np

from psycopg2.extras import execute_values
import psycopg2 as pg
from dotenv import load_dotenv

# init database connection on load

load_dotenv()
CONN = duckdb.connect("hsku_local.duckdb")

TABLES = {
    "users_table": [
        "user_id varchar unique",
        "name varchar",
        "nick varchar",
    ],
    "threads_table": [
        "user_id varchar unique",
        "personal_inbox_id varchar",
        "personal_inbox_name varchar",
    ],
    "roles_table": ["role_id varchar unique", "name varchar"],
    "messages_table": [
        "sender_id varchar",
        "recipient_id varchar",
        "time int",
        "message varchar",
    ],
    "loans_table": [
        "role_id varchar",
        "interest decimal(3,2)",
        "amount int",
        "term int",
        "submitted datetime",
        "active bool",
    ],
    "active_roles_table": [
        "user_id varchar",
        "role_id varchar",
        "top_role bool",
        "gained datetime",
        "lost datetime",
        "active bool",
        "ur_hash varchar unique",
    ],
    "spy_tokens_table": [
        "role_id varchar",
        "spy_tokens int",
    ],
    "orders_queue_table": [
        "order_id int primary key",
        "user_id varchar",
        "role_id varchar",
        "order_type varchar",
        "order_scope varchar",
        "order_text varchar",
        "timestamp int",
        "turn int",
    ],
}

TABLES_ON = {
    "users_table": "user_id",
    "threads_table": "user_id",
    "roles_table": "role_id",
    "loans_table": "hash",
    "messages_table": "hash",
    "active_roles_table": "hash",
    "orders_queue": "order_id",
}

TABLE_CONVERT = {
    "users_table": "diplo_member",
    "threads_table": "diplo_thread",
    "roles_table": "diplo_role",
    "loans_table": "diplo_loan",
    "messages_table": "diplo_message",
    "active_roles_table": "diplo_playerrole",
}

HASHES = {
    "messages": ["sender_id", "recipient_id", "time"],
    "loans": ["role_id", "submitted"],
    "active_roles": ["user_id", "role_id", "gained"],
}


def connect_db():
    conn = pg.connect(
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS"),
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
    )
    return conn


"""
dbname: the database name
database: the database name (only as keyword argument)
user: user name used to authenticate
password: password used to authenticate
host: database host address (defaults to UNIX socket if not provided)
port: connection port number (defaults to 5432 if not provided)
"""


def execute_sql(sql: str, commit: bool = True, params: list = None):
    """
    Executes an SQL query on the connected database.

    Args:
        :sql The SQL query to execute.
        :commit Whether to commit the transaction after execution.
        :param params:

    Returns:
        None

    """
    try:
        if params is not None:
            CONN.execute(sql, params)
        else:
            CONN.execute(sql)
    except ParserException:
        print(sql)
        raise ParserException()
    if commit:
        CONN.commit()


def get_sql(sql, params: list = None) -> pd.DataFrame:
    """
    Executes an SQL query on the connected database.

    Args:
        sql: The SQL query to execute.

    Returns:
        A pandas DataFrame containing the results of the query.
    """
    try:
        if params is not None:
            df = CONN.sql(sql, params=params).df()
        else:
            df = CONN.sql(sql).df()
    except ParserException:
        print(sql)
        raise ParserException()
    return df


def create_table(table_name, tuple_of_fields: List[str]):
    execute_sql(
        f"create table if not exists {table_name} ({','.join(tuple_of_fields)})",
        commit=True,
    )


# function that determines if a user has accessed the bot before
def user_lookup(id: str) -> pd.DataFrame:
    sql = f"select user_id, name, nick from users where user_id = {str(id)}"
    df = get_sql(sql)
    return df


def role_lookup(id: str) -> pd.DataFrame:
    sql = f"select role_id, name from roles where role_id = {str(id)}"
    df = get_sql(sql)
    return df


def create_user(id, name, nick):
    sql = f"insert into users (user_id, name, nick) values (?, ?, ?)"
    execute_sql(
        sql,
        commit=True,
        params=[str(id), str(name), str(nick).replace(";", "").replace("'", "")],
    )


def create_role(id, name):
    sql = f"insert into roles (role_id, name) values ('{str(id)}', '{str(name)}')"
    execute_sql(sql, commit=True)


def get_user_inbox(id: str) -> pd.DataFrame:
    sql = f"select user_id, personal_inbox_id, personal_inbox_name from threads where user_id = {str(id)}"
    df = get_sql(sql)
    return df


def create_user_inbox(id, personal_inbox_id, personal_inbox_name):
    sql = f"insert into threads (user_id, personal_inbox_id, personal_inbox_name) values (?, ?, ?)"
    execute_sql(
        sql,
        commit=True,
        params=[str(id), str(personal_inbox_id), str(personal_inbox_name)],
    )


def get_orders(turn, order_id=None, user_id=None, role_id=None):
    sql2 = """
        select 
            oq.order_id,
            coalesce(u.nick, u.name) as username,
            r.name as role,
            order_type,
            order_scope,
            order_text,
            timestamp,
            turn
        from orders_queue oq
        join users u on oq.user_id = u.user_id
        join roles r on oq.role_id = r.role_id
        where 1=1
            and turn = ?
    """
    res = get_sql(
        sql2,
        params=[
            turn,
        ],
    )

    return res


def get_max_order_pk() -> int:
    sql = """
        select max(order_id) as mxid from orders_queue
    """
    res = get_sql(sql)
    if res.shape[0] == 0 or np.isnan(res.iloc[0]["mxid"]):
        return 0
    try:
        x = int(res.iloc[0]["mxid"])
    except ValueError as e:
        print(
            f"Cannot recover primary key from orders table",
            res.iloc[0]["mxid"],
            type(res.iloc[0]["mxid"]),
        )
        raise ValueError(e)
    return int(res.iloc[0]["mxid"])


def create_order(
    order_type, order_text, turn, user_id=None, role_id=None, order_scope=None
):
    sql = """
        insert into orders_queue (order_id, user_id, role_id, order_type, order_scope, order_text, timestamp, turn)
        values (?, ?, ?, ?, ?, ?, ?, ?)
    """
    execute_sql(
        sql,
        commit=True,
        params=[
            int(get_max_order_pk()) + 1,
            str(user_id),
            str(role_id),
            str(order_type),
            str(order_scope),
            str(order_text),
            int(datetime.now().timestamp()),
            int(turn),
        ],
    )


def update_user_inbox(id, personal_inbox_id, personal_inbox_name):
    sql = f"""
    update threads
    set personal_inbox_id = ?, personal_inbox_name = ?
    where user_id = '{str(id)}'
    """
    execute_sql(
        sql,
        commit=True,
        params=[str(personal_inbox_id), str(personal_inbox_name)],
    )


def create_message(send_id, recp_id, timestp, message):
    sql = f"""
    insert into messages (sender_id, recipient_id, time, message) 
    values (?, ?, ?, ?)
    """
    execute_sql(
        sql,
        commit=True,
        params=[
            str(send_id),
            str(recp_id),
            int(timestp),
            str(message.replace("'", "").replace(";", "")),
        ],
    )


def check_message_time(send_id, recp_id, chk_time, gap) -> int | None:
    sql = f"select coalesce(max(time), 1) as mx_tim from messages where sender_id = '{str(send_id)}' and recipient_id = '{str(recp_id)}' and time > {int(chk_time) - int(gap)}"
    df = get_sql(sql)
    mx_tim = df.iloc[0].to_dict()["mx_tim"]
    if mx_tim == 1:
        return None
    else:
        return mx_tim + gap


def sync_table(table: str, cols: list, on: str):
    conn = connect_db()
    if on != "hash":
        data = CONN.sql(f"select * from {table}").fetchall()
    else:
        hash_str = [f"{h}::varchar" for h in HASHES[table]]
        data = CONN.sql(
            f"select *, hash({' || '.join(hash_str)}) from {table}"
        ).fetchall()
    print("syncing", len(data))
    cur = conn.cursor()
    cur.execute("BEGIN")

    # create tmp table
    cur.execute(
        f"create table tmp_{table} as select * from {TABLE_CONVERT[table + '_table']} where 1=0"
    )
    # load data
    if on == "hash" and "hash" not in cols:
        cols.append("hash")

    tmp_cols = [col.split(" ")[0] for col in cols]
    sql = f"insert into tmp_{table} ({', '.join(tmp_cols)}) values %s"
    execute_values(cur, sql, data)

    # upsert
    up_cols = [f"{c} = EXCLUDED.{c}" for c in tmp_cols]
    sql = f"""
        INSERT INTO {TABLE_CONVERT[table + "_table"]} ({', '.join(tmp_cols)})
        SELECT {', '.join([f'tu.{col}' for col in tmp_cols])}
        FROM tmp_{table} tu
        ON CONFLICT ({on}) DO UPDATE SET
            {', '.join(up_cols)}
    """
    cur.execute(sql)
    # delete temp table
    cur.execute(f"drop table tmp_{table}")
    conn.commit()


def sync_all_tables():
    for table in ("users", "roles", "threads", "loans", "active_roles"):
        print("syncing", table)
        sync_table(
            table,
            TABLES[table + "_table"],
            TABLES_ON[table + "_table"],
        )


def sync_messages():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("select max(time) from diplo_message")
    mx = cur.fetchone()[0]
    if mx is None:
        mx = 0
    data = CONN.sql(
        f"select *, hash(sender_id || recipient_id || time::varchar) from messages where time > {mx} "
    ).fetchall()
    print("syncing", len(data), "messages")
    cur.execute("BEGIN")
    # create tmp table
    cur.execute(f"create table tmp_message as select * from diplo_message where 1=0")
    # load data
    execute_values(
        cur,
        "insert into tmp_message (sender_id, recipient_id, time, message, hash) values %s",
        data,
    )
    # upsert
    sql = f"""
        INSERT INTO diplo_message (sender_id, recipient_id, time, message, hash)
        SELECT sender_id, recipient_id, time, message, hash
        FROM tmp_message
        ON CONFLICT (hash) DO NOTHING
    """
    cur.execute(sql)
    # delete temp table
    cur.execute(f"drop table tmp_message")
    conn.commit()


async def get_active_roles(guild: discord.Guild, user: discord.Member = None):
    if user is None:
        # get list of users
        df = CONN.sql("select distinct user_id from users").df()
        ulst = list(df["user_id"])
    elif user is not None:
        # get user
        ulst = [
            user.id,
        ]
    else:
        print("No Params, Skipping Role Pull")
        return None

    print("syncing roles for", len(ulst), "users")
    # look for the user on the server
    for uid in ulst:
        try:
            mem = await guild.fetch_member(int(uid))
        except discord.errors.NotFound:
            continue
        trole = mem.top_role
        # check if the role exists
        if (
            CONN.sql(
                "select count(role_id) from roles where role_id = ?",
                params=[trole.id],
            ).fetchone()[0]
            == 0
        ):
            create_role(trole.id, trole.name)
        hash = CONN.sql("select hash(? || ?)", params=(uid, trole.id)).fetchone()[0]
        isql = """
            insert into active_roles
            (user_id, role_id, top_role, gained, lost, active, ur_hash)
            VALUES 
            (?, ?, true, current_date, null, true, ?)
            on conflict (ur_hash) do update set
            top_role = true,
            active = true,
            lost = null
        """
        execute_sql(isql, params=[str(uid), str(trole.id), str(hash)])
        usql = """
            update active_roles set 
            active = false,
            top_role = false,
            lost = current_date
            where user_id = ? and role_id != ?
        """
        execute_sql(usql, params=[str(uid), str(trole.id)])
        for role in mem.roles:
            if (
                CONN.sql(
                    "select count(role_id) from roles where role_id = ?",
                    params=[role.id],
                ).fetchone()[0]
                == 0
            ):
                create_role(role.id, role.name)
            nhash = CONN.sql("select hash(? || ?)", params=[uid, role.id]).fetchone()[0]
            rsql = """
                insert into active_roles 
                (user_id, role_id, top_role, gained, lost, active, ur_hash)
                VALUES (?, ?, false, current_date, null, true, ?)
                on conflict (ur_hash) do update set
                active = true,
                lost = null
            """
            execute_sql(rsql, params=[str(uid), str(role.id), str(nhash)])
        CONN.commit()
    CONN.commit()


def initialize():
    # function for running all the create table statements
    for table, name in (
        (TABLES["users_table"], "users"),
        (TABLES["threads_table"], "threads"),
        (TABLES["roles_table"], "roles"),
        (TABLES["messages_table"], "messages"),
        (TABLES["loans_table"], "loans"),
        (TABLES["active_roles_table"], "active_roles"),
        (TABLES["orders_queue_table"], "orders_queue"),
        (TABLES["spy_tokens_table"], "spy_tokens"),
    ):
        create_table(name, table)


if __name__ == "__main__":
    initialize()
