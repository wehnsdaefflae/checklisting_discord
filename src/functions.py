import json

from coinmarketcap import Market


def get_debug_data():
    with open("resources/debug_coins.json", mode="r") as debug_file:
        return json.load(debug_file)


def get_cmc_data():
    cmc = Market()
    return cmc.ticker(limit=0, convert="EUR")


def coin_list_to_dict(coin_list):
    d = dict()
    for coin in coin_list:
        coin["symbol"] = coin.get("symbol").lower()
        d[coin.get("id", "")] = coin
    return d
