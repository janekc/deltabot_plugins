
import os
from typing import Optional

from .db import DBManager

from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand
from deltabot.hookspec import deltabot_hookimpl

from deltachat import Message

version = '1.0.0'
dbot: DeltaBot
db: DBManager


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot, db
    dbot = bot
    db = get_db(bot)

    bot.filters.register(name=__name__, func=filter_messages)

    bot.commands.register(name="/scoreSet", func=cmd_set, admin=True)
    bot.commands.register(name="/score", func=cmd_score)


# ======== Filters ===============

def filter_messages(message: Message, replies: Replies) -> Optional[bool]:
    """Detect messages like +1 or -1 to increase/decrease score.
    """
    if not message.quote or not message.text or message.text[0] not in '-+' or not message.text[1:].isdigit() or not dbot.is_admin(message.get_sender_contact().addr):
        return None

    _set_score(message.quote.get_sender_contact().addr, message.text, replies)
    return True


# ======== Commands ===============

def cmd_set(command: IncomingCommand, replies: Replies) -> None:
    """Set score for given address.

    Example: `/score foo@example.com +100`
    """
    _set_score(command.args[0], command.args[1], replies)


def cmd_score(command: IncomingCommand, replies: Replies) -> None:
    """Get score from given address or your current score if no address is given.

    Example: `/score`
    """
    addr = command.payload if command.payload else command.message.get_sender_contact().addr
    replies.add(text='{} has {} points.'.format(addr, db.get_score(addr)))


# ======== Utilities ===============

def get_db(bot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))


def _set_score(addr: str, score: str, replies: Replies) -> None:
    new_score = db.get_score(addr)
    if score[0] == '+':
        new_score += int(score[1:])
    elif score[0] == '-':
        new_score -= int(score[1:])
    else:
        replies.add(text='❌ Invalid operand, use + or -')
        return

    db.set_score(addr, new_score)
    replies.add(text='{} has {} points.'.format(addr, new_score))
