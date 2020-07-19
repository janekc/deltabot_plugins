# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
import os

from .db import DBManager
from deltabot.hookspec import deltabot_hookimpl

if TYPE_CHECKING:
    from deltabot import DeltaBot
    from deltabot.bot import Replies
    from deltabot.commands import IncomingCommand


version = '1.0.0'
dbot: DeltaBot
db: DBManager


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot, db
    dbot = bot
    db = get_db(bot)

    getdefault('max_bio_len', '500')

    dbot.commands.register('/friends_join', cmd_join)
    dbot.commands.register('/friends_leave', cmd_leave)
    dbot.commands.register('/friends_list', cmd_list)
    dbot.commands.register('/friends_me', cmd_me)


# ======== Commands ===============

def cmd_join(command: IncomingCommand, replies: Replies) -> None:
    """Add you to the list or update your bio.
    """
    if not command.payload:
        replies.add(text='You must provide a biography')
        return

    text = ' '.join(command.payload.split())
    max_len = int(getdefault('max_bio_len'))
    if len(text) > max_len:
        text = text[:max_len] + '...'

    addr = command.message.get_sender_contact().addr
    exists = db.get_bio(addr)
    db.update_bio(addr, text)
    if exists:
        replies.add(text='Bio updated')
    else:
        replies.add(text='Added to the list')


def cmd_leave(command: IncomingCommand, replies: Replies) -> None:
    """Remove you from the list.
    """
    addr = command.message.get_sender_contact().addr
    if db.get_bio(addr) is None:
        replies.add(text='You are not in the list yet')
    else:
        db.remove_user(addr)
        replies.add(text='You was removed from the list')


def cmd_list(command: IncomingCommand, replies: Replies) -> None:
    """Get the list of users and their biography.
    """
    users = ['{}:\n{}'.format(f['addr'], f['bio']) for f in db.get_users()]
    text = '\n\n―――――――――――――――\n\n'.join(users) or 'Empty List'
    replies.add(text=text)


def cmd_me(command: IncomingCommand, replies: Replies) -> None:
    """See your biography.
    """
    addr = command.message.get_sender_contact().addr
    bio = db.get_bio(addr)
    if bio is None:
        replies.add(text='You have not set a biography yet')
    else:
        replies.add(text='{}:\n{}'.format(addr, bio))


# ======== Utilities ===============

def getdefault(key: str, value: str = None) -> str:
    val = dbot.get(key, scope=__name__)
    if val is None and value is not None:
        dbot.set(key, value, scope=__name__)
        val = value
    return val


def get_db(bot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))
