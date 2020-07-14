# -*- coding: utf-8 -*-
from urllib.parse import quote_plus
import tempfile

from deltabot.hookspec import deltabot_hookimpl
import bs4
import requests
# typing
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
# ======


version = '1.0.0'
HEADERS = {
    'user-agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0'}


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.commands.register(name='/avatar', func=cmd_avatar)
    bot.commands.register(name='/avatar_bird', func=cmd_bird)


# ======== Commands ===============


def cmd_avatar(cmd: IncomingCommand) -> tuple:
    """Generate a cat avatar based on the given text, if no text is given a random avatar is generated.
    """
    return get_message(cmd.payload, '2016_cat-generator')


def cmd_bird(cmd: IncomingCommand) -> tuple:
    """Generate a bird avatar based on the given text, if no text is given a random avatar is generated.
    """
    return get_message(cmd.payload, '2019_bird-generator')


# ======== Utilities ===============

def get_message(text: str, generator: str) -> tuple:
    url = 'https://www.peppercarrot.com/extras/html/{}/'.format(generator)
    if not text:
        with requests.get(url, headers=HEADERS) as r:
            r.raise_for_status()
            soup = bs4.BeautifulSoup(r.text, 'html.parser')
        text = soup.find('img', class_='avatar')[
            'src'].rsplit('=', maxsplit=1)[-1]

    url += 'avatar.php?seed=' + quote_plus(text)
    with requests.get(url, headers=HEADERS) as r:
        r.raise_for_status()
        fd, path = tempfile.mkstemp(prefix='catvatar-', suffix='.png')
        with open(fd, 'wb') as f:
            f.write(r.content)
    return (text, path)
