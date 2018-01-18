import json

import asyncio
import logging
import pprint
import re

import time

import os

import shutil

from coinmarketcap import Market
from discord.ext import commands

with open("resources/discord.json", mode="r") as file:
    discord_data = json.load(file)

TOKEN = discord_data.get("Bot Token")

description = """CMC Listing Notification Bot"""
bot = commands.Bot(command_prefix="/", description=description)

DEBUG = False
INTERVAL = 3 if DEBUG else 300
LISTED_PATH = "resources/listed_coins.json"

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

log_formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

file_handler = logging.FileHandler("{}.log".format(time.strftime("%Y-%m-%d_%H-%M-%S")))
file_handler.setFormatter(log_formatter)
LOGGER.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
LOGGER.addHandler(console_handler)


def get_debug_prices():
    with open("resources/debug_coins.json", mode="r") as debug_file:
        return json.load(debug_file)


def get_cmc_prices():
    cmc = Market()
    return cmc.ticker(limit=0, convert="EUR")


def coin_list_to_dict(coin_list):
    return {coin.get("id", "<no symbol>"): coin for coin in coin_list}


def get_symbols(user_id):
    json_path = "users/{:s}/symbols.json".format(user_id)
    if not os.path.isfile(json_path):
        return set()
    with open(json_path, mode="r") as json_file:
        try:
            symbols = json.load(json_file)
        except ValueError as ve:
            format_str = "Error while parsing JSON in <{}>! Defaulting to empty list.\n{:s}"
            LOGGER.error(format_str.format(json_path, ve))
            symbols = set()
        except FileNotFoundError as fnf:
            LOGGER.error("File <{}> not found! Defaulting to empty list.\n{:s}".format(json_path, fnf))
            symbols = set()
    return {x.lower() for x in symbols}


id_to_coin_dict = dict()
smb_to_ids = dict()
user_notifications = dict()


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    bot.loop.create_task(my_background_task())


async def my_background_task():
    while True:
        LOGGER.info("Waiting {:d} seconds.".format(INTERVAL))
        await asyncio.sleep(INTERVAL)

        LOGGER.info("Getting coinmarketcap data.")
        try:
            coins = get_debug_prices() if DEBUG else get_cmc_prices()
            for each_coin in coins:
                each_coin["symbol"] = each_coin.get("symbol", "").lower()
            LOGGER.info("Received {:d} coins.".format(len(coins)))

            new_id_to_coin_dict = coin_list_to_dict(coins)

            global id_to_coin_dict, smb_to_ids
            delta_ids = set(new_id_to_coin_dict.keys()) - set(id_to_coin_dict.keys())
            smb_to_ids.clear()
            for each_id, each_coin in new_id_to_coin_dict.items():
                symbol = each_coin["symbol"]
                ids = smb_to_ids.get(symbol)
                if ids is None:
                    ids = {each_id}
                    smb_to_ids[symbol] = ids
                else:
                    ids.add(each_id)

            global user_notifications
            uids = [x for x in os.listdir("users/") if os.path.isdir("users/" + x) and re.search(r'[0-9]+', x)]
            for each_uid in uids:
                if user_notifications.get(each_uid, False):
                    symbols = get_symbols(each_uid)
                    for each_id in delta_ids:
                        coin = new_id_to_coin_dict[each_id]
                        each_symbol = coin.get("symbol")
                        if each_symbol in symbols:
                            retrieved_author = await bot.get_user_info(each_uid)
                            coin_id = coin["id"]
                            await bot.send_message(retrieved_author, content="Symbol {:s} has been added as {:s}.".format(each_symbol, coin_id))

            id_to_coin_dict.clear()
            id_to_coin_dict.update(new_id_to_coin_dict)

            LOGGER.info("Saving listed coins to <{}>.".format(LISTED_PATH))
            with open(LISTED_PATH, mode="w") as listed_file:
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
        await bot.send_message(author, content="Argument missing! Usage: /add <smb>")

    else:
        # retrieved_author = await bot.get_user_info(author_id)
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
        await bot.send_message(author, content="Argument missing! Usage: /remove <smb>")

    else:
        symbol_lower = symbol.lower()

        user_dir = "users/{:s}/".format(author_id)
        file_path = user_dir + "symbols.json"

        symbols = get_symbols(author_id)
        if symbol_lower in symbols:
            await bot.send_message(author, content="Removed <{:s}> from watch list.".format(symbol_lower))
            if len(symbols) < 2:
                shutil.rmtree(user_dir)
                await bot.send_message(author, content="No symbol left. User folder deleted.".format(symbol_lower))

            else:
                symbols.remove(symbol_lower)
                with open(file_path, mode="w") as symbols_file:
                    json.dump(sorted(symbols), symbols_file)

        else:
            await bot.say("Symbol <{:s}> not in watch list.".format(symbol_lower))


@bot.command(pass_context=True)
async def check(context, symbol: str=""):
    """
    Checks whether a symbol token is listed.
    """
    author = context.message.author

    if len(symbol) < 1:
        await bot.send_message(author, content="Argument missing! Usage: /check <smb>")

    else:
        symbol_lower = symbol.lower()
        global id_to_coin_dict, smb_to_ids
        ids = smb_to_ids.get(symbol_lower)
        if ids is None:
            await bot.send_message(author, content="No coin with the symbol <{}> is listed.".format(symbol_lower))
        else:
            for each_id in ids:
                coin = id_to_coin_dict.get(each_id)
                if coin is not None:
                    await bot.send_message(author, content=pprint.pformat(coin))


@bot.command(pass_context=True)
async def listings(context):
    """
    Shows all listings on the watch list.
    """
    author = context.message.author
    author_id = author.id

    symbols = get_symbols(author_id)

    if len(symbols) < 1:
        await bot.send_message(author, content="Watchlist empty! Add symbols with /add <smb>")
    else:
        global id_to_coin_dict, smb_to_ids
        lines = []
        for each_symbol in sorted(symbols):
            ids = smb_to_ids.get(each_symbol)
            if ids is None:
                lines.append("No coin with the symbol <{}> is listed.".format(each_symbol))
            else:
                for each_id in sorted(ids):
                    coin = id_to_coin_dict.get(each_id)
                    if coin is not None:
                        lines.append("{:s} (:s)".format(each_id, each_symbol))
        await bot.send_message(author, content="\n".join(lines))


@bot.command(pass_context=True)
async def start(context):
    """
    Starts the listing notification service.
    """
    author = context.message.author
    author_id = author.id

    global user_notifications
    user_notifications[author_id] = True
    await bot.send_message(author, content="Notification service running for {:s} (uID: {:s}).".format(author.name, author_id))


@bot.command(pass_context=True)
async def stop(context):
    """
    Stops the listing notification service.
    """
    author = context.message.author
    author_id = author.id

    global user_notifications
    user_notifications[author_id] = False
    await bot.send_message(author, content="Notification service stopped for {:s} (uID: {:s}).".format(author.name, author_id))

bot.run(TOKEN)
