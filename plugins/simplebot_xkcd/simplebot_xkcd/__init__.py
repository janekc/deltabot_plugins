# -*- coding: utf-8 -*-
from urllib.request import urlopen
import tempfile

from deltabot.hookspec import deltabot_hookimpl
import xkcd
# typing
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
# ======


version = '1.0.0'


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.commands.register(name='/xkcd', func=cmd_xkcd)
    bot.commands.register(name='/xkcd_latest', func=cmd_latest)


# ======== Commands ===============

def cmd_xkcd(cmd: IncomingCommand) -> tuple:
    """Show the comic with the given number or a ramdom comic if no number is provided.
    """
    return get_message(xkcd.getComic(
        int(cmd.payload)) if cmd.payload else xkcd.getRandomComic())


def cmd_latest(cmd: IncomingCommand) -> tuple:
    """Get the latest comic released in xkcd.com.
    """
    return get_message(xkcd.getLatestComic())


# ======== Utilities ===============

def get_message(comic: xkcd.Comic) -> tuple:
    image = urlopen(comic.imageLink).read()
    fd, path = tempfile.mkstemp(prefix='xkcd-', suffix=comic.imageName)
    with open(fd, 'wb') as f:
        f.write(image)
    text = '#{} - {}\n\n{}'.format(
        comic.number, comic.title, comic.altText)
    return (text, path)
