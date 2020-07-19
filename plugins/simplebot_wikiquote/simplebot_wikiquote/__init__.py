# -*- coding: utf-8 -*-
from random import choice

from deltabot.hookspec import deltabot_hookimpl
import wikiquote as wq
# typing:
from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand


version = '1.0.0'


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    bot.commands.register(name="/quote", func=cmd_quote)


def cmd_quote(command: IncomingCommand, replies: Replies) -> None:
    """Get Wikiquote quotes.

    Search in Wikiquote or get the quote of the day if no text is given.
    Example: `/quote Richard Stallman`
    """
    if command.payload:
        authors = wq.search(command.payload)
        if authors:
            if command.payload.lower() == authors[0].lower():
                author = authors[0]
            else:
                author = choice(authors)
            quote = '"{}"\n\n― {}'.format(
                choice(wq.quotes(author, max_quotes=200)), author)
        else:
            quote = 'No quote found for: {}'.format(command.payload)
    else:
        quote = '"{}"\n\n― {}'.format(*wq.quote_of_the_day())

    replies.add(text=quote)
