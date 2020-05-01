# -*- coding: utf-8 -*-
from threading import Thread
from time import sleep
import re
import os

from .irc import IRCBot
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
                remove_cchat(chat.id, channel)


@deltabot_hookimpl
def deltabot_init(bot):
    global db, cfg, dbot, irc_bridge
    dbot = bot

    db = DBManager(os.path.join(get_dir(), 'sqlite.db'))

    nick = getdefault('nick', 'SimpleBot')
    host = getdefault('host', 'irc.freenode.net')
    port = int(getdefault('port', '6667'))
    irc_bridge = IRCBot(host, port, nick, db, bot)
    Thread(target=run_irc, daemon=True).start()

    bot.filters.register(name=__name__, func=process_messages)

    register_cmd('/join', '/irc_join', process_join_cmd)
    register_cmd('/remove', '/irc_remove', process_remove_cmd)
    register_cmd('/topic', '/irc_topic', process_topic_cmd)
    register_cmd('/members', '/irc_members', process_members_cmd)
    register_cmd('/nick', '/irc_nick', process_nick_cmd)

    bot.account.add_account_plugin(AccountListener())


# ======== Filters ===============


def process_messages(msg):
    chan = db.get_channel_by_gid(msg.chat.id)
    if not chan:
        return

    if not msg.text or msg.filename:
        return 'Unsupported message'

    nick = db.get_nick(msg.get_sender_contact().addr)
    text = '{}[dc]: {}'.format(nick, msg.text)

    irc_bridge.send_message(chan, text)
    for g in get_cchats(chan):
        if g.id != msg.chat.id:
            g.send_text(text)


# ======== Commands ===============


def process_topic_cmd(cmd):
    """Show channel topic.
    """
    chan = db.get_channel_by_gid(cmd.message.chat.id)
    if not chan:
        return 'This is not an IRC channel'
    return 'Topic:\n{}'.format(irc_bridge.get_topic(chan))


def process_members_cmd(cmd):
    """Show list of channel members.
    """
    me = cmd.bot.self_contact()

    chan = db.get_channel_by_gid(cmd.message.chat.id)
    if not chan:
        return 'This is not an IRC channel'

    members = ''
    for g in get_cchats(chan):
        for c in g.get_contacts():
            if c != me:
                members += '• {}[dc]\n'.format(db.get_nick(c.addr))

    for m in irc_bridge.get_members(chan):
        members += '• {}[irc]\n'.format(m)

    return 'Members:\n{}'.format(members)


def process_nick_cmd(cmd):
    """Set your nick or display your current nick if no new nick is given.
    """
    addr = cmd.message.get_sender_contact().addr
    new_nick = ' '.join(cmd.payload.split())
    if new_nick:
        if not nick_re.match(new_nick):
            return '** Invalid nick, only letters and numbers are allowed, and nick should be less than 30 characters'
        addr = db.get_addr(new_nick)
        if addr:
            return '** Nick already taken'
        db.set_nick(addr, new_nick)
        return '** Nick: {}'.format(new_nick)
    return '** Nick: {}'.format(db.get_nick(addr))


def process_join_cmd(cmd):
    """Join the given channel.
    """
    sender = cmd.message.get_sender_contact()
    if not cmd.payload or not db.is_whitelisted(sender.addr):
        return

    if db.channel_exists(cmd.payload):
        chats = get_cchats(cmd.payload)
    else:
        irc_bridge.join_channel(cmd.payload)
        db.add_channel(cmd.payload)
        chats = []

    g = None
    gsize = int(getdefault('max_group_size', '20'))
    for group in chats:
        contacts = group.get_contacts()
        if sender in contacts:
            group.send_text('You are already a member of this group')
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
    text = '** You joined {} as {}'.format(cmd.payload, nick)
    g.send_text(text)


def process_remove_cmd(cmd):
    """Remove the member with the given nick from the channel, if no nick is given remove yourself.
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

def run_irc():
    while True:
        try:
            irc_bridge.start()
        except Exception as ex:
            dbot.logger.exception('Error on IRC bridge: ', ex)
            sleep(5)


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


def remove_cchat(chat_id, channel):
    db.remove_cchat(chat_id)
    if next(db.get_cchats(channel), None) is None:
        db.remove_channel(channel)
        irc_bridge.leave_channel(channel)


def get_cchats(channel):
    for gid in db.get_cchats(channel):
        yield dbot.get_chat(gid)


def get_dir():
    path = os.path.join(os.path.dirname(dbot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return path
