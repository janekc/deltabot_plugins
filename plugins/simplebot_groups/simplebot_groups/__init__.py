# -*- coding: utf-8 -*-
import os
import random
import re
import string

from .db import DBManager, Status
from deltachat import account_hookimpl
from deltabot.hookspec import deltabot_hookimpl
# typing
from typing import Callable, Generator, Optional
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message
# ======


version = '1.0.0'
GROUP_URL = 'http://delta.chat/group/'
MGROUP_URL = 'http://delta.chat/mega-group/'
CHANNEL_URL = 'http://delta.chat/channel/'
nick_re = re.compile(r'[a-zA-Z0-9_]{1,30}$')
dbot: DeltaBot
db: DBManager


# ======== Hooks ===============

class AccountListener:
    def __init__(self, db: DBManager, bot: DeltaBot) -> None:
        self.db = db
        self.bot = bot

    @account_hookimpl
    def ac_member_added(self, chat: Chat, contact: Contact,
                        message: Message) -> None:
        if contact == self.bot.self_contact:
            if self.db.get_mgroup(chat.id) or self.db.get_channel(chat.id):
                return
            add_group(chat.id)

    @account_hookimpl
    def ac_member_removed(self, chat: Chat, contact: Contact,
                          message: Message) -> None:
        me = self.bot.self_contact

        g = self.db.get_group(chat.id)
        ccount = len(chat.get_contacts()) - 1
        if g:
            if me == contact or ccount <= 1:
                self.db.remove_group(chat.id)
            return

        mg = self.db.get_mgroup(chat.id)
        if mg:
            if me == contact or ccount <= 1:
                self.db.remove_mchat(chat.id)
                if not self.db.get_mchats(mg['id']):
                    self.db.remove_mgroup(mg['id'])
            return

        ch = self.db.get_channel(chat.id)
        if ch:
            if me == contact or ccount <= 1:
                if ch['admin'] == chat.id:
                    for cchat in get_cchats(ch['id']):
                        try:
                            cchat.remove_contact(me)
                        except ValueError:
                            pass
                    self.db.remove_channel(ch['id'])
                else:
                    self.db.remove_cchat(chat.id)


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot, db
    dbot = bot
    db = get_db(bot)

    getdefault('max_mgroup_size', '20')
    getdefault('max_group_size', '20')
    getdefault('max_topic_size', '500')
    getdefault('allow_groups', '1')
    allow_mgroups = getdefault('allow_mgroups', '1')
    allow_channels = getdefault('allow_channels', '1')

    # getdefault('max_file_size', '102400')  # 100KB

    bot.filters.register(name=__name__, func=filter_messages)

    if allow_mgroups == '1':
        register_cmd('/mega', '/group_mega', cmd_mega)
    register_cmd('/nick', '/group_nick', cmd_nick)
    register_cmd('/id', '/group_id', cmd_id)
    register_cmd('/list', '/group_list', cmd_list)
    register_cmd('/me', '/group_me', cmd_me)
    register_cmd('/members', '/group_members', cmd_members)
    register_cmd('/join', '/group_join', cmd_join)
    register_cmd('/topic', '/group_topic', cmd_topic)
    register_cmd('/remove', '/group_remove', cmd_remove)
    if allow_channels == '1':
        register_cmd('/channel', '/group_channel', cmd_channel)
    # register_cmd('/public', '/group_public', cmd_public)
    # register_cmd('/private', '/group_private', cmd_private)
    # register_cmd('/name', '/group_name', cmd_name)
    # register_cmd('/image', '/group_image', cmd_image)
    # register_cmd('/chanimage', '/group_chanimage', cmd_chanimage)

    bot.account.add_account_plugin(AccountListener(db, bot))


# ======== Filters ===============

def filter_messages(msg: Message) -> Optional[str]:
    """Process messages sent to groups, mega-groups and channels.
    """
    mg = db.get_mgroup(msg.chat.id)
    if mg:
        if not msg.text or msg.filename:
            return 'Unsupported message'

        nick = db.get_nick(msg.get_sender_contact().addr)
        text = '{}:\n{}'.format(nick, msg.text)

        for g in get_mchats(mg['id']):
            if g.id != msg.chat.id:
                g.send_text(text)
        return None

    ch = db.get_channel(msg.chat.id)
    if ch and ch['admin'] == msg.chat.id:
        if not msg.text or msg.filename:
            return 'Unsupported message'

        nick = db.get_nick(msg.get_sender_contact().addr)
        text = '{}:\n{}'.format(nick, msg.text)

        for g in get_cchats(ch['id']):
            g.send_text(text)
    elif ch:
        return 'Only channel operators can do that.'

    return None


# ======== Commands ===============

def cmd_mega(cmd: IncomingCommand) -> str:
    """Convert the group where it is sent in a mega-group.
    """
    if db.get_mgroup(cmd.message.chat.id):
        return 'This is already a mega-group'

    if db.get_channel(cmd.message.chat.id):
        return 'This is a channel'

    name = cmd.message.chat.get_name()
    if db.get_mgroup_by_name(name):
        return 'Failed, there is a mega-group with the same name'

    g = db.get_group(cmd.message.chat.id)
    if g:
        db.remove_group(g['id'])
        db.add_mgroup(g['pid'], name, g['topic'], g['status'])
    else:
        db.add_mgroup(generate_pid(), name, None, Status.PUBLIC)
    db.add_mchat(cmd.message.chat.id, db.get_mgroup_by_name(name)['id'])

    return 'This is now a mega-group'


def cmd_nick(cmd: IncomingCommand) -> str:
    """Set your nick or display your current nick if no new nick is given.
    """
    addr = cmd.message.get_sender_contact().addr
    if cmd.payload:
        new_nick = '_'.join(cmd.payload.split())
        if new_nick != addr and not nick_re.match(new_nick):
            text = '** Invalid nick, only letters, numbers and'
            text += ' underscore are allowed, also nick should be'
            text += ' less than 30 characters'
            return text
        if db.get_addr(new_nick):
            return '** Nick already taken'
        db.set_nick(addr, new_nick)
        return '** Nick: {}'.format(new_nick)
    return '** Nick: {}'.format(db.get_nick(addr))


def cmd_id(cmd: IncomingCommand) -> str:
    """Show the id of the group, mega-group or channel where it is sent.
    """
    if not cmd.message.chat.is_group():
        return 'This is not a group'

    mg = db.get_mgroup(cmd.message.chat.id)
    if mg:
        if mg['status'] == Status.PUBLIC:
            status = 'Mega-Group Status: Public'
            gid = '{}{}'.format(MGROUP_URL, mg['id'])
        else:
            status = 'Mega-Group Status: Private'
            gid = '{}{}-{}'.format(MGROUP_URL, mg['pid'], mg['id'])
        return '{}\nID: {}'.format(status, gid)

    ch = db.get_channel(cmd.message.chat.id)
    if ch:
        if ch['status'] == Status.PUBLIC:
            status = 'Channel Status: Public'
            gid = '{}{}'.format(CHANNEL_URL, ch['id'])
        else:
            status = 'Channel Status: Private'
            gid = '{}{}-{}'.format(CHANNEL_URL, ch['pid'], ch['id'])
        return '{}\nID: {}'.format(status, gid)

    g = db.get_group(cmd.message.chat.id)
    if not g:
        add_group(cmd.message.chat.id)
        g = db.get_group(cmd.message.chat.id)
        assert g is not None

    url = GROUP_URL
    if g['status'] == Status.PUBLIC:
        status = 'Group Status: Public'
        gid = '{}{}'.format(url, g['id'])
    else:
        status = 'Group Status: Private'
        gid = '{}{}-{}'.format(url, g['pid'], g['id'])
    return '{}\nID: {}'.format(status, gid)


def cmd_list(cmd: IncomingCommand) -> Optional[str]:
    """Show the list of public groups, mega-groups and channels.
    """
    def get_list(header, groups):
        groups.sort(key=lambda g: g[-1])
        text = '{} ({}):\n\n'.format(header, len(groups))
        text += '―――――――――――――――\n\n'.join(
            '{0}:\n👤 {3}\nTopic: {1}\nID: {2}\n\n'.format(*g) for g in groups)
        return text

    groups: list = db.get_groups(Status.PUBLIC)
    for i, g in enumerate(groups):
        chat = cmd.bot.get_chat(g['id'])
        groups[i] = (chat.get_name(), g['topic'], '{}{}'.format(
            GROUP_URL, chat.id), len(chat.get_contacts()))
    if groups:
        cmd.message.chat.send_text(get_list('Groups', groups))

    mgroups = []
    for mg in db.get_mgroups(Status.PUBLIC):
        count = sum(
            map(lambda g: len(g.get_contacts())-1, get_mchats(mg['id'])))
        if count == 0:
            db.remove_mgroup(mg['id'])
            continue
        mgroups.append((mg['name'], mg['topic'],
                        '{}{}'.format(MGROUP_URL, mg['id']), count))
    if mgroups:
        cmd.message.chat.send_text(get_list('Mega-Groups', mgroups))

    channels = []
    for ch in db.get_channels(Status.PUBLIC):
        count = sum(
            map(lambda g: len(g.get_contacts())-1, get_cchats(ch['id'])))
        channels.append((ch['name'], ch['topic'],
                         '{}{}'.format(CHANNEL_URL, ch['id']), count))
    if channels:
        cmd.message.chat.send_text(get_list('Channels', channels))

    if not groups and not mgroups and not channels:
        return 'Empty List'
    return None


def cmd_me(cmd: IncomingCommand) -> str:
    """Show the list of groups, mega-groups and channels you are in.
    """
    sender = cmd.message.get_sender_contact()
    groups = []
    for group in db.get_groups(Status.PUBLIC) + db.get_groups(Status.PRIVATE):
        g = cmd.bot.get_chat(group['id'])
        if sender in g.get_contacts():
            groups.append((g.get_name(), '{}{}'.format(GROUP_URL, g.id)))

    for mg in db.get_mgroups(Status.PUBLIC) + db.get_mgroups(Status.PRIVATE):
        for g in get_mchats(mg['id']):
            if sender in g.get_contacts():
                groups.append(
                    (mg['name'], '{}{}'.format(MGROUP_URL, mg['id'])))
                break

    for ch in db.get_channels(Status.PUBLIC) + db.get_channels(Status.PRIVATE):
        for c in get_cchats(ch['id']):
            if sender in c.get_contacts():
                groups.append(
                    (ch['name'], '{}{}'.format(CHANNEL_URL, ch['id'])))
                break

    return ''.join(
        '{0}:\nID: {1}\n\n'.format(*g) for g in groups) or 'Empty list'


def cmd_members(cmd: IncomingCommand) -> str:
    """Show list of mega-group members.
    """
    me = cmd.bot.self_contact

    mg = db.get_mgroup(cmd.message.chat.id)
    if not mg:
        return 'This is not a mega-group'

    text = 'Members:\n'
    count = 0
    for g in get_mchats(mg['id']):
        for c in g.get_contacts():
            if c != me:
                text += '• {}\n'.format(db.get_nick(c.addr))
                count += 1
    return '{}\n\n👤 Total: {}'.format(text, count)


def cmd_join(cmd: IncomingCommand) -> Optional[str]:
    """Join the given group or channel.
    """
    sender = cmd.message.get_sender_contact()
    pid = ''
    text = 'Added to {}\n(ID:{})\n\nTopic:\n{}'
    if cmd.payload.startswith(MGROUP_URL):
        data = rmprefix(cmd.payload, MGROUP_URL).split('-')
        if len(data) == 2:
            pid = data[0]
        gid = int(data[-1])
        mg = db.get_mgroup_by_id(gid)
        if mg and (mg['status'] == Status.PUBLIC or mg['pid'] == pid):
            g = None
            gsize = int(getdefault('max_mgroup_size'))
            for group in get_mchats(mg['id']):
                contacts = group.get_contacts()
                if sender in contacts:
                    group.send_text(
                        'You are already a member of this group')
                    return None
                if len(contacts) < gsize:
                    g = group
                    gsize = len(contacts)
            if g is None:
                g = cmd.bot.create_group(mg['name'], [sender])
                db.add_mchat(g.id, mg['id'])
            else:
                add_contact(g, sender)

            text = text.format(mg['name'], cmd.payload, mg['topic'])
            text += '\n\nYour Nick: {}'.format(db.get_nick(sender.addr))
            return text
    elif cmd.payload.startswith(GROUP_URL):
        data = rmprefix(cmd.payload, GROUP_URL).split('-')
        if len(data) == 2:
            pid = data[0]
            gid = int(data[-1])
        gr = db.get_group(gid)
        if gr and (gr['status'] == Status.PUBLIC or gr['pid'] == pid):
            g = cmd.bot.get_chat(gr['id'])
            contacts = g.get_contacts()
            if sender in contacts:
                g.send_text('You are already a member of this group')
                return None
            elif len(contacts) < int(getdefault('max_group_size')):
                add_contact(g, sender)
                return text.format(g.get_name(), cmd.payload, gr['topic'])
            else:
                return 'Group is full'
    elif cmd.payload.startswith(CHANNEL_URL):
        data = rmprefix(cmd.payload, CHANNEL_URL).split('-')
        if len(data) == 2:
            pid = data[0]
        gid = int(data[-1])
        ch = db.get_channel_by_id(gid)
        if ch and (ch['status'] == Status.PUBLIC or ch['pid'] == pid):
            g = cmd.bot.get_chat(ch['admin'])
            if sender in g.get_contacts():
                g.send_text('You are already a member of this channel')
                return None
            for g in get_cchats(ch['id']):
                if sender in g.get_contacts():
                    g.send_text('You are already a member of this channel')
                    return None
            g = cmd.bot.create_group(ch['name'], [sender])
            db.add_cchat(g.id, ch['id'])
            return text.format(ch['name'], cmd.payload, ch['topic'])

    return 'Invalid ID'


def cmd_topic(cmd: IncomingCommand) -> Optional[str]:
    """Show or change group/channel topic.
    """
    if not cmd.message.chat.is_group():
        return 'This is not a group'

    if cmd.payload:
        new_topic = ' '.join(cmd.payload.split())
        max_size = int(getdefault('max_topic_size'))
        if len(new_topic) > max_size:
            new_topic = new_topic[:max_size]+'...'

        text = '** {} changed topic to:\n{}'

        mg = db.get_mgroup(cmd.message.chat.id)
        if mg:
            nick = db.get_nick(cmd.message.get_sender_contact().addr)
            text = text.format(nick, new_topic)
            db.set_mgroup_topic(mg['id'], new_topic)
            for chat in get_mchats(mg['id']):
                chat.send_text(text)
            return None

        ch = db.get_channel(cmd.message.chat.id)
        if ch and ch['admin'] == cmd.message.chat.id:
            nick = db.get_nick(cmd.message.get_sender_contact().addr)
            text = text.format(nick, new_topic)
            db.set_channel_topic(ch['id'], new_topic)
            for chat in get_cchats(ch['id']):
                chat.send_text(text)
            return text
        if ch:
            return 'Only channel operators can do that.'

        g = db.get_group(cmd.message.chat.id)
        if not g:
            add_group(cmd.message.chat.id)
            g = db.get_group(cmd.message.chat.id)
            assert g is not None
        db.set_group_topic(g['id'], new_topic)
        return text.format(
            cmd.message.get_sender_contact().addr, new_topic)

    g = db.get_mgroup(cmd.message.chat.id) or db.get_channel(
        cmd.message.chat.id) or db.get_group(cmd.message.chat.id)
    if not g:
        add_group(cmd.message.chat.id)
        g = db.get_group(cmd.message.chat.id)
        assert g is not None
    return 'Topic:\n{}'.format(g['topic'])


def cmd_remove(cmd: IncomingCommand) -> Optional[str]:
    """Remove the member with the given address or nick from the group with the given id. If no address is provided, removes yourself from group or channel.
    """
    sender = cmd.message.get_sender_contact()
    me = cmd.bot.self_contact

    if not cmd.payload:
        cmd.message.chat.remove_contact(sender)
        return None

    if not cmd.message.chat.is_group():
        args = cmd.payload.split(maxsplit=1)
        url = args[0]
        cmd.payload = args[1] if len(args) == 2 else ''
        if url.startswith(MGROUP_URL):
            mg = db.get_mgroup_by_id(
                int(rmprefix(url, MGROUP_URL).split('-')[-1]))
            if not mg:
                return 'Invalid ID'
            for g in get_mchats(mg['id']):
                if sender in g.get_contacts():
                    if not cmd.payload:
                        g.remove_contact(sender)
                        return 'Removed from "{}"'.format(mg['name'])
                    break
            else:
                return 'You are not a member of that group'
        elif url.startswith(CHANNEL_URL):
            ch = db.get_channel_by_id(
                int(rmprefix(url, CHANNEL_URL).split('-')[-1]))
            if not ch:
                return 'Invalid ID'
            for g in get_cchats(ch['id'], include_admin=True):
                if sender in g.get_contacts():
                    g.remove_contact(sender)
                    return 'Removed from "{}"'.format(ch['name'])
            else:
                return 'You are not a member of that channel'
        elif url.startswith(GROUP_URL):
            g = db.get_group(int(rmprefix(url, GROUP_URL).split('-')[-1]))
            if not g:
                return 'Invalid ID'
            if sender not in g.get_contacts():
                return 'You are not a member of that group'
            if cmd.payload:
                if cmd.payload == cmd.bot.self_contact.addr:
                    return 'You can not remove me from the group'
                g.remove_contact(cmd.payload)
                chat = cmd.bot.get_chat(cmd.payload)
                chat.send_text('Removed from {} by {}'.format(
                    g.get_name(), sender.addr))
                return '** {} removed'.format(cmd.payload)
            g.remove_contact(sender)
            return 'Removed from "{}"'.format(g.get_name())
    else:
        mg = db.get_mgroup(cmd.message.chat.id)

    if mg:
        addr = cmd.payload
        if '@' not in addr:
            addr = db.get_addr(addr)
        if not addr:
            return 'Unknow user: {}'.format(cmd.payload)
        if addr == me.addr:
            return 'You can not remove me from the group'
        for g in get_mchats(mg['id']):
            for c in g.get_contacts():
                if c.addr == addr:
                    g.remove_contact(c)
                    nick = db.get_nick(sender.addr)
                    cmd.bot.get_chat(c).send_text(
                        'Removed from {} by {}'.format(mg['name'], nick))
                    return '** {} removed'.format(cmd.payload)
        return 'User "{}" is not member of the group'.format(cmd.payload)

    # if it is a group
    for c in cmd.message.chat.get_contacts():
        if c.addr == cmd.payload:
            cmd.message.chat.remove_contact(c)
            return None
    return 'User "{}" is not member of this group'.format(cmd.payload)


def cmd_channel(cmd: IncomingCommand) -> Optional[str]:
    """Create a new channel with the given name.
    """
    if not cmd.payload:
        return 'You must provide a channel name'
    if db.get_channel_by_name(cmd.payload):
        return 'There is already a channel with that name'
    g = cmd.bot.create_group(cmd.payload, [cmd.message.get_sender_contact()])
    db.add_channel(generate_pid(), cmd.payload, None, g.id, Status.PUBLIC)
    g.send_text('Channel created')
    return None


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


def rmprefix(text: str, prefix: str) -> str:
    return text[text.startswith(prefix) and len(prefix):]


def generate_pid(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for i in range(length))


def get_mchats(mgid: int) -> Generator:
    for gid in db.get_mchats(mgid):
        yield dbot.get_chat(gid)


def get_cchats(cgid: int, include_admin: bool = False) -> Generator:
    for gid in db.get_cchats(cgid):
        yield dbot.get_chat(gid)
    if include_admin:
        ch = db.get_channel(cgid)
        if ch:
            yield ch['admin']


def add_group(gid: int) -> None:
    if getdefault('allow_groups') == '1':
        db.add_group(gid, generate_pid(), None, Status.PUBLIC)
    else:
        dbot.get_chat(gid).remove_contact(dbot.self_contact)


def add_contact(chat: Chat, contact: Contact) -> None:
    img_path = chat.get_profile_image()
    if img_path and not os.path.exists(img_path):
        chat.remove_profile_image()
    chat.add_contact(contact)
