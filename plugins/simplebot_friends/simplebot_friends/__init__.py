# -*- coding: utf-8 -*-
from typing import Callable
import os

from .db import DBManager
from deltabot.hookspec import deltabot_hookimpl
# typing
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
# ======


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

    register_cmd('/join', '/friends_join', cmd_join)
    register_cmd('/leave', '/friends_leave', cmd_leave)
    register_cmd('/list', '/friends_list', cmd_list)
    register_cmd('/me', '/friends_me', cmd_me)


# ======== Commands ===============

def cmd_join(cmd: IncomingCommand) -> str:
    """Add you to the list or update your bio.
    """
    if not cmd.payload:
        return 'You must provide a biography'

    text = ' '.join(cmd.payload.split())
    max_len = int(getdefault('max_bio_len'))
    if len(text) > max_len:
        text = text[:max_len] + '...'

    addr = cmd.message.get_sender_contact().addr
    exists = db.get_bio(addr)
    db.update_bio(addr, text)
    if exists:
        return 'Bio updated'
    return 'Added to the list'


def cmd_leave(cmd: IncomingCommand) -> str:
    """Remove you from the list.
    """
    addr = cmd.message.get_sender_contact().addr
    if db.get_bio(addr) is None:
        return 'You are not in the list yet'
    db.remove_user(addr)
    return 'You was removed from the list'


def cmd_list(cmd: IncomingCommand) -> str:
    """Get the list of users and their biography.
    """
    users = ['{}:\n{}'.format(f['addr'], f['bio']) for f in db.get_users()]
    return '\n\n―――――――――――――――\n\n'.join(users) or 'Empty List'


def cmd_me(cmd: IncomingCommand) -> str:
    """See your biography.
    """
    addr = cmd.message.get_sender_contact().addr
    bio = db.get_bio(addr)
    if bio is None:
        return 'You have not set a biography yet'
    return '{}:\n{}'.format(addr, bio)


# ======== Utilities ===============

def register_cmd(name: str, alt_name: str, func: Callable) -> None:
    try:
        dbot.commands.register(name=name, func=func)
    except ValueError:
        dbot.commands.register(name=alt_name, func=func)


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
