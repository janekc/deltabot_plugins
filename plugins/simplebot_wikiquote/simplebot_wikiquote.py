# -*- coding: utf-8 -*-
from random import choice

from deltabot.hookspec import deltabot_hookimpl
import wikiquote as wq


version = '1.0.0'


@deltabot_hookimpl
def deltabot_init(bot):
    bot.commands.register(name="/quote", func=process_quote_cmd)


def process_quote_cmd(cmd):
    """Get Wikiquote quotes.

    Search in Wikiquote or get the quote of the day if no text is given.
    Example: `/quote Richard Stallman`
    """
    if cmd.payload:
        authors = wq.search(cmd.payload)
        if authors:
            if cmd.payload.lower() == authors[0].lower():
                author = authors[0]
            else:
                author = choice(authors)
            quote = '"{}"\n\n― {}'.format(
                choice(wq.quotes(author, max_quotes=200)), author)
        else:
            quote = 'No quote found for: {}'.format(cmd.payload)
    else:
        quote = '"{}"\n\n― {}'.format(*wq.quote_of_the_day())

    return quote
