# -*- coding: utf-8 -*-
from deltabot.hookspec import deltabot_hookimpl
from translators.google import LANGUAGES
import translators as ts
# typing
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
# ======


version = '1.0.0'
LANGUAGES = '\n'.join(
    ['* {}: {}'.format(v, k)
     for k, v in sorted(LANGUAGES.items(), key=lambda e: e[1])])


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.commands.register(name="/tr", func=cmd_tr)


def cmd_tr(cmd: IncomingCommand) -> str:
    """Translate text.

    You need to pass origin and destination language. If you send the
    command along you will get the list of supported languages and their
    code.
    Example: `/tr en es hello world`
    """
    if cmd.payload:
        l1, l2, text = cmd.payload.split(maxsplit=2)
        return ts.google(text=text, from_language=l1, to_language=l2,
                         host='https://translate.google.com')
    else:
        return LANGUAGES
