import json

import asyncio
import logging
import platform

import time

import os

import shutil

import discord
from discord.ext import commands

from src.functions import get_cmc_data, coin_list_to_dict, get_debug_data

DEBUG = False
INTERVAL = 3 if DEBUG else 300
COIN_INFO_PATH = "resources/last_coin_info.json"

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

log_formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

file_handler = logging.FileHandler("{}.log".format(time.strftime("%Y-%m-%d_%H-%M-%S")))
file_handler.setFormatter(log_formatter)
LOGGER.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
LOGGER.addHandler(console_handler)

id_to_coin_dict = dict()
symbol_to_ids = dict()
user_notifications = set()

URL = "https://github.com/wehnsdaefflae/checklisting_discord"
DESCRIPTION = """CMC Listing Notification Bot, type ?help"""
bot = commands.Bot(command_prefix="?", description=DESCRIPTION)


def get_symbols(user_id):
    json_path = "users/{:s}/symbols.json".format(user_id)
    if not os.path.isfile(json_path):
        LOGGER.error("User <{}> not found! Defaulting to empty set.".format(user_id))
        return set()
    with open(json_path, mode="r") as json_file:
        try:
            symbols = set(json.load(json_file))
        except ValueError as ve:
            format_str = "Error while parsing JSON in <{}>! Defaulting to empty set.\n{:s}"
            LOGGER.error(format_str.format(json_path, ve))
            symbols = set()
        except FileNotFoundError as fnf:
            LOGGER.error("File <{}> not found! Defaulting to empty set.\n{:s}".format(json_path, fnf))
            symbols = set()
    return symbols


@bot.event
async def on_ready():
    members = set(bot.get_all_members())
    print('Logged in as ' + bot.user.name + ' (ID:' + bot.user.id + ') | Connected to ' + str(
        len(bot.servers)) + ' servers | Connected to {:d} users'.format(len(members)))
    print("\n".join([x.name for x in members]))
    print('--------')
    print('Current Discord.py Version: {} | Current Python Version: {}'.format(discord.__version__,
                                                                               platform.python_version()))
    print('--------')
    print('Use this link to invite {}:'.format(bot.user.name))
    print('https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions=8'.format(bot.user.id))
    bot.loop.create_task(poll_loop())


async def notification(user_id, coin):
    retrieved_author = await bot.get_user_info(user_id)
    embed = await get_coin_embed(coin)
    await bot.send_message(retrieved_author, embed=embed)


async def poll_loop():
    while True:
        LOGGER.info("Waiting {:d} seconds.".format(INTERVAL))
        await asyncio.sleep(INTERVAL)

        LOGGER.info("Getting data...")
        try:
            # get data and put in coin id dict
            coins = get_debug_data() if DEBUG else get_cmc_data()
            for each_coin in coins:
                each_coin["symbol"] = each_coin.get("symbol", "").lower()
            LOGGER.info("Received {:d} coins.".format(len(coins)))
            new_id_to_coin_dict = coin_list_to_dict(coins)

            # update symbol to coin ids map
            symbol_to_ids.clear()
            for each_id, each_coin in new_id_to_coin_dict.items():
                symbol = each_coin.get("symbol", "")
                ids = symbol_to_ids.get(symbol)
                if ids is None:
                    ids = {each_id}
                    symbol_to_ids[symbol] = ids
                else:
                    ids.add(each_id)

            # determine new coin ids
            delta_ids = set(new_id_to_coin_dict.keys()) - set(id_to_coin_dict.keys())

            # check user watch lists for new coin ids
            remove_user = set()
            for each_uid in user_notifications:
                if not os.path.isdir("users/" + each_uid):
                    LOGGER.error("Data for user <{:s}> not found! Removing user from notification list...")
                    remove_user.add(each_uid)
                    continue

                symbols = get_symbols(each_uid)
                for each_id in delta_ids:
                    coin = new_id_to_coin_dict[each_id]
                    each_symbol = coin.get("symbol")
                    if each_symbol in symbols:
                        await notification(each_uid, coin)

            for each_user in remove_user:
                user_notifications.remove(each_user)

            # update last coin info
            id_to_coin_dict.clear()
            id_to_coin_dict.update(new_id_to_coin_dict)

            # persist last coin info
            LOGGER.info("Saving listed coins to <{}>.".format(COIN_INFO_PATH))
            with open(COIN_INFO_PATH, mode="w") as listed_file:
                json.dump(id_to_coin_dict, listed_file, indent=2)

        except Exception as e:
            LOGGER.error("Caught error:\n{}\nSkipping cycle...".format(e))


@bot.command(pass_context=True)
async def add(context, symbol: str=""):
    """
    Adds a new coin symbol to the watch list.
    """
    author = context.message.author
    author_id = author.id

    if len(symbol) < 1:
        await bot.send_message(author, content="Argument missing! Usage: ?add <smb>")

    else:
        symbol_lower = symbol.lower()

        user_dir = "users/{:s}/".format(author_id)
        file_path = user_dir + "symbols.json"
        symbols = get_symbols(author_id)
        if symbol_lower in symbols:
            await bot.send_message(author, content="Symbol <{:s}> already in watch list.".format(symbol_lower))

        else:
            if not os.path.isdir(user_dir):
                os.makedirs(user_dir, exist_ok=True)
            symbols.add(symbol_lower)
            with open(file_path, mode="w") as symbol_file:
                json.dump(sorted(symbols), symbol_file)
            await bot.send_message(author, content="Added <{:s}> to watch list.".format(symbol_lower))


@bot.command(pass_context=True)
async def remove(context, symbol: str=""):
    """
    Removes a symbol from the watch list.
    """
    author = context.message.author
    author_id = author.id

    if len(symbol) < 1:
        await bot.send_message(author, content="Argument missing! Usage: ?remove <smb>")

    else:
        symbol_lower = symbol.lower()

        user_dir = "users/{:s}/".format(author_id)
        file_path = user_dir + "symbols.json"

        symbols = get_symbols(author_id)
        if symbol_lower in symbols:
            await bot.send_message(author, content="Removing <{:s}> from watch list...".format(symbol_lower))
            if len(symbols) < 2:
                shutil.rmtree(user_dir)
                await bot.send_message(author, content="No symbol left. User folder deleted.".format(symbol_lower))

            else:
                symbols.remove(symbol_lower)
                with open(file_path, mode="w") as symbols_file:
                    json.dump(sorted(symbols), symbols_file)

        else:
            await bot.say("Symbol <{:s}> not in watch list.".format(symbol_lower))


async def get_coin_embed(coin):
    symbol = coin.get("symbol")
    each_id = coin.get("id")
    embed_title = "{:s} ({:s})".format(symbol.upper(), each_id)
    embed_url = "https://coinmarketcap.com/currencies/{:s}/".format(each_id)
    embed = discord.Embed(title=embed_title, url=embed_url)
    embed.set_author(name=DESCRIPTION, url=URL)

    try:
        usd = float(coin.get("price_usd"))
    except ValueError:
        usd = -1.

    try:
        eur = float(coin.get("price_eur"))
    except ValueError:
        eur = -1.

    embed_price = "${:6.2f} or {:6.2f} €".format(usd, eur)
    embed.add_field(name="price", value=embed_price, inline=True)

    try:
        hourly_change = float(coin.get("percent_change_1h"))
    except ValueError:
        hourly_change = 0.

    embed_h_change = "{:+5.2f}%".format(hourly_change)
    embed.add_field(name="hourly change", value=embed_h_change, inline=True)

    try:
        daily_change = float(coin.get("percent_change_24h"))
    except ValueError:
        daily_change = 0.

    embed_d_change = "{:+5.2f}%".format(daily_change)
    embed.add_field(name="daily change", value=embed_d_change, inline=True)
    return embed


@bot.command(pass_context=True)
async def check(context, symbol: str=""):
    """
    Checks whether a symbol token is listed.
    """
    author = context.message.author

    if len(symbol) < 1:
        await bot.send_message(author, content="Argument missing! Usage: ?check <smb>")

    else:
        symbol_lower = symbol.lower()
        ids = symbol_to_ids.get(symbol_lower)
        if ids is None:
            await bot.send_message(author, content="No coin with the symbol <{}> is listed.".format(symbol_lower))
        else:
            for each_id in ids:
                coin = id_to_coin_dict.get(each_id)
                if coin is not None:
                    embed = await get_coin_embed(coin)
                    await bot.send_message(author, embed=embed)


async def send_listings(author):
    author_id = author.id
    symbols = get_symbols(author_id)

    if len(symbols) < 1:
        await bot.send_message(author, content="Watchlist empty! Add symbols with ?add <smb>")

    else:
        for each_symbol in sorted(symbols):
            ids = symbol_to_ids.get(each_symbol)
            if ids is not None:
                for each_id in sorted(ids):
                    coin = id_to_coin_dict.get(each_id)
                    embed = await get_coin_embed(coin)
                    await bot.send_message(author, embed=embed)
        await bot.send_message(author,
                               content="Watch list:\n{:s}".format(", ".join(x.upper() for x in sorted(symbols))))

    if author_id in user_notifications:
        await bot.send_message(author, content="Notification service for {:s} running.".format(author.name))
    else:
        await bot.send_message(author, content="Notification service {:s} disabled.".format(author.name))


@bot.command(pass_context=True)
async def listings(context):
    """
    Shows all listings on the watch list.
    """
    author = context.message.author
    await send_listings(author)


@bot.command(pass_context=True)
async def start(context):
    """
    Starts the listing notification service.
    """
    author = context.message.author
    author_id = author.id
    user_notifications.add(author_id)
    await send_listings(author)


@bot.command(pass_context=True)
async def stop(context):
    """
    Stops the listing notification service.
    """
    author = context.message.author
    author_id = author.id

    try:
        user_notifications.remove(author_id)
        await bot.send_message(author, content="Notification service for {:s} stopped.".format(author.name))
    except KeyError:
        await bot.send_message(author, content="Notification was not running for {:s}.".format(author.name))


with open("resources/discord-bot-token.txt", mode="r") as token_file:
    token = token_file.readline().strip()
bot.run(token)
