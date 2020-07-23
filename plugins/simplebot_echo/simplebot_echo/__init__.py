# -*- coding: utf-8 -*-
from deltabot.hookspec import deltabot_hookimpl
# typing:
from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand


version = '1.0.0'


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.commands.register(name="/echo", func=cmd_echo)


def cmd_echo(command: IncomingCommand, replies: Replies) -> None:
    """Echoes back received text.

    To use it you can simply send a message starting with
    the command '/echo'. Example: `/echo hello world`
    """
    replies.add(text=command.payload or 'echo')
