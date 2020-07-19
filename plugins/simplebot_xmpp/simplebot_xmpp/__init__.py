# -*- coding: utf-8 -*-
from threading import Thread, Event
import asyncio
import os
import re

from .xmpp import XMPPBot
from .database import DBManager
from deltabot.hookspec import deltabot_hookimpl
# typing
from typing import Optional, Generator
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message
# ======


version = '1.0.0'
nick_re = re.compile(r'[a-zA-Z0-9]{1,30}$')
dbot: DeltaBot = None
db: DBManager
xmpp_bridge: XMPPBot


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot, db
    dbot = bot
    db = get_db(bot)

    getdefault('nick', 'DC-Bridge')
    getdefault('max_group_size', '20')

    bot.filters.register(name=__name__, func=filter_messages)

    dbot.commands.register('/xmpp_join', cmd_join)
    dbot.commands.register('/xmpp_remove', cmd_remove)
    dbot.commands.register('/xmpp_members', cmd_members)
    dbot.commands.register('/xmpp_nick', cmd_nick)


@deltabot_hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    jid = bot.get('jid', scope=__name__)
    password = bot.get('password', scope=__name__)
    nick = getdefault('nick')

    assert jid is not None, 'Missing "{}/jid" setting'.format(__name__)
    assert password is not None, 'Missing "{}/password" setting'.format(
        __name__)

    bridge_init = Event()
    Thread(target=listen_to_xmpp,
           args=(jid, password, nick, bridge_init), daemon=True).start()
    bridge_init.wait()


@deltabot_hookimpl
def deltabot_member_removed(self, chat: Chat, contact: Contact) -> None:
    me = dbot.self_contact
    if me == contact or len(chat.get_contacts()) <= 1:
        channel = db.get_channel_by_gid(chat.id)
        if channel:
            db.remove_cchat(chat.id)
            if next(db.get_cchats(channel), None) is None:
                db.remove_channel(channel)
                xmpp_bridge.leave_channel(channel)


# ======== Filters ===============

def filter_messages(msg: Message) -> Optional[str]:
    """Process messages sent to XMPP channels.
    """
    chan = db.get_channel_by_gid(msg.chat.id)
    if not chan:
        return None

    if not msg.text or msg.filename:
        return 'Unsupported message'

    nick = db.get_nick(msg.get_sender_contact().addr)
    text = '{}[dc]:\n{}'.format(nick, msg.text)

    dbot.logger.debug('Sending message to XMPP: %r', text)
    xmpp_bridge.send_message(chan, text, mtype='groupchat')
    for g in get_cchats(chan):
        if g.id != msg.chat.id:
            g.send_text(text)

    return None


# ======== Commands ===============

def cmd_members(cmd: IncomingCommand) -> str:
    """Show list of XMPP channel members.
    """
    me = cmd.bot.self_contact

    chan = db.get_channel_by_gid(cmd.message.chat.id)
    if not chan:
        return 'This is not an XMPP channel'

    members = 'Members:\n'
    for g in get_cchats(chan):
        for c in g.get_contacts():
            if c != me:
                members += '• {}[dc]\n'.format(db.get_nick(c.addr))

    for m in xmpp_bridge.get_members(chan):
        if m != xmpp_bridge.nick:
            members += '• {}[xmpp]\n'.format(m)

    return members


def cmd_nick(cmd: IncomingCommand) -> str:
    """Set your XMPP nick or display your current nick if no new nick is given.
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
    """Join the given XMPP channel.
    """
    sender = cmd.message.get_sender_contact()
    if not cmd.payload:
        return None
    if not db.is_whitelisted(cmd.payload):
        return "That channel isn't in the whitelist"

    chats = get_cchats(cmd.payload)
    if not db.channel_exists(cmd.payload):
        xmpp_bridge.join_channel(cmd.payload)
        db.add_channel(cmd.payload)

    g = None
    gsize = int(getdefault('max_group_size'))
    for group in chats:
        contacts = group.get_contacts()
        if sender in contacts:
            group.send_text('You are already a member of this channel')
            return None
        if len(contacts) < gsize:
            g = group
            gsize = len(contacts)
    if g is None:
        g = dbot.create_group(cmd.payload, [sender])
        db.add_cchat(g.id, cmd.payload)
    else:
        add_contact(g, sender)

    nick = db.get_nick(sender.addr)
    g.send_text('** You joined {} as {}'.format(cmd.payload, nick))
    return None


def cmd_remove(cmd: IncomingCommand) -> Optional[str]:
    """Remove the DC member with the given nick from the XMPP channel, if no nick is given remove yourself.
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

def listen_to_xmpp(jid: str, password: str, nick: str,
                   bridge_initialized: Event) -> None:
    global xmpp_bridge
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    xmpp_bridge = XMPPBot(jid, password, nick, db, dbot)
    bridge_initialized.set()
    while True:
        try:
            dbot.logger.info('Starting XMPP bridge')
            xmpp_bridge.connect()
            xmpp_bridge.process(forever=False)
        except Exception as ex:
            dbot.logger.exception(ex)


def get_cchats(channel: str) -> Generator:
    for gid in db.get_cchats(channel):
        yield dbot.get_chat(gid)


def getdefault(key: str, value: str = None) -> str:
    val = dbot.get(key, scope=__name__)
    if val is None and value is not None:
        dbot.set(key, value, scope=__name__)
        val = value
    return val


def get_db(bot: DeltaBot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))


def add_contact(chat: Chat, contact: Contact) -> None:
    img_path = chat.get_profile_image()
    if img_path and not os.path.exists(img_path):
        chat.remove_profile_image()
    chat.add_contact(contact)
