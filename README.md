### Maturin KS Bot

#### How to run
install pipenv: `pip install pipenv`

clone the repo: `git clone https://github.com/eric-oaktree/maturin.git`

install the required libraries: `pipenv install`

run the app: `pipenv run python maturin.py`

Servers are currently hardcoded, don't know if I will ever change that. If you want to use it on another server, change your `.env ` file to override the `PERSONAL` id.

The following options can be set in a `.env` file:

```
DISCORD_TOKEN=
PERSONAL_SERVER=
HSKUCW=
LETTER_CHANNEL=
PG_HOST=
PG_USER=
PG_PASS=
PG_PORT=
PG_DB=
PERSONAL_ID=
```

Discord token is the token for your application, as given by discord. You will also need to have the correct permissions set. I run under admin b/c I control the code... your trust may vary.

PERSONAL_SERVER is the admin server ID. It is setup to have admin commands for the bot, and exists so that the players do not see all the admin commands. This could be the same server I think if you want to simplify. Note that not all the commands check for admin, but the syncing commands won't break anything.

HSKUCW is the id of the game server.

LETTER_CHANNEL is the channel that you want letter threads to be added under.

The PG options are for syncing the bot database with another database. The bot database is an embedded duck db instance, but that means to look at the data while the bot is running it needs to be extracted.

PERSONAL_ID is your personal discord ID, and is used to permissions check some functions as an override.
