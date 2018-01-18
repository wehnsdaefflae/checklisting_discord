import platform

import discord
from discord.ext import commands


# https://github.com/Rapptz/discord.py/blob/async/examples/playlist.py


class CMCBot:
    def __init__(self, bot):
        self.bot = bot

        self.id_to_coin_dict = dict()
        self.symbol_to_ids = dict()
        self.user_notifications = set()

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
        # bot.loop.create_task(poll_loop())