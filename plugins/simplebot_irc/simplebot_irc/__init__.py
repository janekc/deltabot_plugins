# -*- coding: utf-8 -*-
from threading import Thread
from time import sleep
import re
import os

from .irc import IRCBot
from .database import DBManager
from deltachat import account_hookimpl
from deltabot.hookspec import deltabot_hookimpl
# typing
from typing import Callable, Generator, Optional
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message
# ======


version = '1.0.0'
nick_re = re.compile(r'[a-zA-Z0-9]{1,30}$')
dbot: DeltaBot = None
db: DBManager
irc_bridge: IRCBot


# ======== Hooks ===============

class AccountListener:
    def __init__(self, db: DBManager, bot: DeltaBot,
                 irc_bridge: IRCBot) -> None:
        self.db = db
        self.bot = bot
        self.irc_bridge = irc_bridge

    @account_hookimpl
    def ac_member_removed(self, chat: Chat, contact: Contact,
                          message: Message) -> None:
        channel = self.db.get_channel_by_gid(chat.id)
        if channel:
            me = self.bot.self_contact
            if me == contact or len(chat.get_contacts()) <= 1:
                self.db.remove_cchat(chat.id)
                if next(self.db.get_cchats(channel), None) is None:
                    self.db.remove_channel(channel)
                    self.irc_bridge.leave_channel(channel)


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot
    dbot = bot

    bot.filters.register(name=__name__, func=filter_messages)

    register_cmd('/join', '/irc_join', cmd_join)
    register_cmd('/remove', '/irc_remove', cmd_remove)
    register_cmd('/topic', '/irc_topic', cmd_topic)
    register_cmd('/members', '/irc_members', cmd_members)
    register_cmd('/nick', '/irc_nick', cmd_nick)


@deltabot_hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    global db, irc_bridge

    db = get_db(bot)

    nick = getdefault('nick', 'SimpleBot')
    host = getdefault('host', 'irc.freenode.net')
    port = int(getdefault('port', '6667'))
    irc_bridge = IRCBot(host, port, nick, db, bot)
    Thread(target=run_irc, daemon=True).start()

    bot.account.add_account_plugin(AccountListener(db, bot, irc_bridge))


# ======== Filters ===============

def filter_messages(msg: Message) -> Optional[str]:
    """Process messages sent to an IRC channel.
    """
    chan = db.get_channel_by_gid(msg.chat.id)
    if not chan:
        return None

    if not msg.text or msg.filename:
        return 'Unsupported message'

    nick = db.get_nick(msg.get_sender_contact().addr)
    text = '{}[dc]: {}'.format(nick, msg.text)

    irc_bridge.send_message(chan, text)
    for g in get_cchats(chan):
        if g.id != msg.chat.id:
            g.send_text(text)

    return None


# ======== Commands ===============

def cmd_topic(cmd: IncomingCommand) -> str:
    """Show IRC channel topic.
    """
    chan = db.get_channel_by_gid(cmd.message.chat.id)
    if not chan:
        return 'This is not an IRC channel'
    return 'Topic:\n{}'.format(irc_bridge.get_topic(chan))


def cmd_members(cmd: IncomingCommand) -> str:
    """Show list of IRC channel members.
    """
    me = cmd.bot.self_contact

    chan = db.get_channel_by_gid(cmd.message.chat.id)
    if not chan:
        return 'This is not an IRC channel'

    members = 'Members:\n'
    for g in get_cchats(chan):
        for c in g.get_contacts():
            if c != me:
                members += '• {}[dc]\n'.format(db.get_nick(c.addr))

    for m in irc_bridge.get_members(chan):
        members += '• {}[irc]\n'.format(m)

    return members


def cmd_nick(cmd: IncomingCommand) -> str:
    """Set your IRC nick or display your current nick if no new nick is given.
    """
    addr = cmd.message.get_sender_contact().addr
    new_nick = ' '.join(cmd.payload.split())
    if new_nick:
        if not nick_re.match(new_nick):
            return '** Invalid nick, only letters and numbers are allowed, and nick should be less than 30 characters'
        if db.get_addr(new_nick):
            return '** Nick already taken'
        db.set_nick(addr, new_nick)
        return '** Nick: {}'.format(new_nick)
    return '** Nick: {}'.format(db.get_nick(addr))


def cmd_join(cmd: IncomingCommand) -> Optional[str]:
    """Join the given IRC channel.
    """
    sender = cmd.message.get_sender_contact()
    if not cmd.payload:
        return None
    if not db.is_whitelisted(cmd.payload):
        return "That channel isn't in the whitelist"

    chats = get_cchats(cmd.payload)
    if not db.channel_exists(cmd.payload):
        irc_bridge.join_channel(cmd.payload)
        db.add_channel(cmd.payload)

    g = None
    gsize = int(getdefault('max_group_size', '20'))
    for group in chats:
        contacts = group.get_contacts()
        if sender in contacts:
            group.send_text('You are already a member of this group')
            return None
        if len(contacts) < gsize:
            g = group
            gsize = len(contacts)
    if g is None:
        g = dbot.create_group(cmd.payload, [sender])
        db.add_cchat(g.id, cmd.payload)
    else:
        g.add_contact(sender)

    nick = db.get_nick(sender.addr)
    text = '** You joined {} as {}'.format(cmd.payload, nick)
    g.send_text(text)
    return None


def cmd_remove(cmd: IncomingCommand) -> Optional[str]:
    """Remove the member with the given nick from the IRC channel, if no nick is given remove yourself.
    """
    sender = cmd.message.get_sender_contact()

    text = cmd.payload
    channel = db.get_channel_by_gid(cmd.message.chat.id)
    if not channel:
        args = cmd.payload.split(maxsplit=1)
        channel = args[0]
        text = args[1] if len(args) == 2 else ''
        for g in get_cchats(channel):
            if sender in g.get_contacts():
                break
        else:
            return 'You are not a member of that channel'

    if not text:
        text = sender.addr
    if '@' not in text:
        t = db.get_addr(text)
        if not t:
            return 'Unknow user: {}'.format(text)
        text = t

    for g in get_cchats(channel):
        for c in g.get_contacts():
            if c.addr == text:
                g.remove_contact(c)
                if c == sender:
                    return None
                s_nick = db.get_nick(sender.addr)
                nick = db.get_nick(c.addr)
                text = '** {} removed by {}'.format(nick, s_nick)
                for g in get_cchats(channel):
                    g.send_text(text)
                text = 'Removed from {} by {}'.format(channel, s_nick)
                dbot.get_chat(c).send_text(text)
                return None

    return None


# ======== Utilities ===============

def run_irc() -> None:
    while True:
        try:
            irc_bridge.start()
        except Exception as ex:
            dbot.logger.exception('Error on IRC bridge: ', ex)
            sleep(5)


def register_cmd(name: str, alt_name: str, func: Callable) -> None:
    try:
        dbot.commands.register(name=name, func=func)
    except ValueError:
        dbot.commands.register(name=alt_name, func=func)


def getdefault(key: str, value: str) -> str:
    val = dbot.get(key, scope=__name__)
    if val is None:
        dbot.set(key, value, scope=__name__)
        val = value
    return val


def get_cchats(channel: str) -> Generator:
    for gid in db.get_cchats(channel):
        yield dbot.get_chat(gid)


def get_db(bot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))
