# -*- coding: utf-8 -*-
from threading import Thread
import asyncio
import os
import re

from .xmpp import XMPPBot
from .database import DBManager
from deltachat import account_hookimpl
from deltabot.hookspec import deltabot_hookimpl


version = '1.0.0'
nick_re = re.compile(r'[a-zA-Z0-9]{1,30}$')


# ======== Hooks ===============

class AccountListener:
    @account_hookimpl
    def ac_member_removed(self, chat, contact, message):
        channel = db.get_channel_by_gid(chat.id)
        if channel:
            me = dbot.self_contact()
            if me == contact or len(chat.get_contacts()) <= 1:
                db.remove_cchat(chat.id)
                if next(db.get_cchats(channel), None) is None:
                    db.remove_channel(channel)
                    xmpp_bridge.leave_channel(channel)


@deltabot_hookimpl
def deltabot_init(bot):
    global dbot
    dbot = bot

    bot.filters.register(name=__name__, func=filter_messages)

    register_cmd('/join', '/xmpp_join', cmd_join)
    register_cmd('/remove', '/xmpp_remove', cmd_remove)
    register_cmd('/members', '/xmpp_members', cmd_members)
    register_cmd('/nick', '/xmpp_nick', cmd_nick)

    bot.account.add_account_plugin(AccountListener())


@deltabot_hookimpl
def deltabot_start(bot):
    global db
    db = DBManager(os.path.join(get_dir(bot), 'sqlite.db'))

    jid = bot.get('jid', scope=__name__)
    password = bot.get('password', scope=__name__)
    nick = getdefault('nick', 'SimpleBot')

    assert jid is not None, 'Missing "{}/jid" setting'.format(__name__)
    assert password is not None, 'Missing "{}/password" setting'.format(__name__)

    Thread(target=listen_to_xmpp,
           args=(jid, password, nick, db, bot), daemon=True).start()


# ======== Filters ===============

def filter_messages(msg):
    """Process messages sent to XMPP channels.
    """
    chan = db.get_channel_by_gid(msg.chat.id)
    if not chan:
        return

    if not msg.text or msg.filename:
        return 'Unsupported message'

    nick = db.get_nick(msg.get_sender_contact().addr)
    text = '{}[dc]:\n{}'.format(nick, msg.text)

    xmpp_bridge.send_message(chan, text, mtype='groupchat')
    for g in get_cchats(chan):
        if g.id != msg.chat.id:
            g.send_text(text)


# ======== Commands ===============

def cmd_members(cmd):
    """Show list of XMPP channel members.
    """
    me = cmd.bot.self_contact()

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


def cmd_nick(cmd):
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


def cmd_join(cmd):
    """Join the given XMPP channel.
    """
    sender = cmd.message.get_sender_contact()
    if not cmd.payload:
        return
    if not db.is_whitelisted(cmd.payload):
        return "That channel isn't in the whitelist"

    if db.channel_exists(cmd.payload):
        chats = get_cchats(cmd.payload)
    else:
        xmpp_bridge.join_channel(cmd.payload)
        db.add_channel(cmd.payload)
        chats = []

    g = None
    gsize = int(getdefault('max_group_size', '20'))
    for group in chats:
        contacts = group.get_contacts()
        if sender in contacts:
            group.send_text('You are already a member of this channel')
            return
        if len(contacts) < gsize:
            g = group
            gsize = len(contacts)
    if g is None:
        g = dbot.create_group(cmd.payload, [sender])
        db.add_cchat(g.id, cmd.payload)
    else:
        g.add_contact(sender)

    nick = db.get_nick(sender.addr)
    g.send_text('** You joined {} as {}'.format(cmd.payload, nick))


def cmd_remove(cmd):
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
                    return
                s_nick = db.get_nick(sender.addr)
                nick = db.get_nick(c.addr)
                text = '** {} removed by {}'.format(nick, s_nick)
                for g in get_cchats(channel):
                    g.send_text(text)
                text = 'Removed from {} by {}'.format(channel, s_nick)
                dbot.get_chat(c).send_text(text)
                return


# ======== Utilities ===============

def listen_to_xmpp(jid, password, nick, db, bot):
    global xmpp_bridge
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    xmpp_bridge = XMPPBot(jid, password, nick, db, bot)
    while True:
        try:
            xmpp_bridge.connect()
            xmpp_bridge.process(forever=False)
        except Exception as ex:
            bot.logger.exception(ex)


def get_cchats(channel):
    for gid in db.get_cchats(channel):
        yield dbot.get_chat(gid)


def register_cmd(name, alt_name, func):
    try:
        dbot.commands.register(name=name, func=func)
    except ValueError:
        dbot.commands.register(name=alt_name, func=func)


def getdefault(key, value):
    val = dbot.get(key, scope=__name__)
    if val is None:
        dbot.set(key, value, scope=__name__)
        val = value
    return val


def get_dir(bot):
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return path
