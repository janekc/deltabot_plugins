# -*- coding: utf-8 -*-
from urllib.request import urlopen
from typing import TYPE_CHECKING
import io

from deltabot.hookspec import deltabot_hookimpl
import xkcd

if TYPE_CHECKING:
    from deltabot import DeltaBot
    from deltabot.bot import Replies
    from deltabot.commands import IncomingCommand


version = '1.0.0'


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.commands.register(name='/xkcd', func=cmd_xkcd)
    bot.commands.register(name='/xkcd_latest', func=cmd_latest)


# ======== Commands ===============

def cmd_xkcd(command: IncomingCommand, replies: Replies) -> None:
    """Show the comic with the given number or a ramdom comic if no number is provided.
    """
    if command.payload:
        comic = xkcd.getComic(int(command.payload))
    else:
        comic = xkcd.getRandomComic()
    replies.add(**get_reply(comic))


def cmd_latest(command: IncomingCommand, replies: Replies) -> None:
    """Get the latest comic released in xkcd.com.
    """
    replies.add(**get_reply(xkcd.getLatestComic()))


# ======== Utilities ===============

def get_reply(comic: xkcd.Comic) -> dict:
    image = urlopen(comic.imageLink).read()
    text = '#{} - {}\n\n{}'.format(
        comic.number, comic.title, comic.altText)
    return dict(text=text, filename=comic.imageName,
                bytefile=io.BytesIO(image))
