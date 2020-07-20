# -*- coding: utf-8 -*-
from typing import Generator
import os
import random
import re
import string

from .db import DBManager, Status
from deltabot.hookspec import deltabot_hookimpl
# typing:
from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message


version = '1.0.0'
GROUP_URL = 'http://delta.chat/group/'
MGROUP_URL = 'http://delta.chat/mega-group/'
CHANNEL_URL = 'http://delta.chat/channel/'
dbot: DeltaBot
db: DBManager


# ======== Hooks ===============

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
        dbot.commands.register('/group_mega', cmd_mega)
    dbot.commands.register('/group_id', cmd_id)
    dbot.commands.register('/group_list', cmd_list)
    dbot.commands.register('/group_me', cmd_me)
    dbot.commands.register('/group_members', cmd_members)
    dbot.commands.register('/group_join', cmd_join)
    dbot.commands.register('/group_topic', cmd_topic)
    dbot.commands.register('/group_remove', cmd_remove)
    if allow_channels == '1':
        dbot.commands.register('/group_chan', cmd_chan)
    # dbot.commands.register('/group_public', cmd_public)
    # dbot.commands.register('/group_private', cmd_private)
    # dbot.commands.register('/group_name', cmd_name)
    # dbot.commands.register('/group_image', cmd_image)
    # dbot.commands.register('/group_chanimage', cmd_chanimage)


@deltabot_hookimpl
def deltabot_member_added(chat: Chat, contact: Contact) -> None:
    if contact == dbot.self_contact:
        if db.get_mgroup(chat.id) or db.get_channel(chat.id):
            return
        add_group(chat.id)


@deltabot_hookimpl
def deltabot_member_removed(chat: Chat, contact: Contact) -> None:
    me = dbot.self_contact
    if me == contact or len(chat.get_contacts()) <= 1:
        g = db.get_group(chat.id)
        if g:
            db.remove_group(chat.id)
            return

        mg = db.get_mgroup(chat.id)
        if mg:
            db.remove_mchat(chat.id)
            if not db.get_mchats(mg['id']):
                db.remove_mgroup(mg['id'])
            return

        ch = db.get_channel(chat.id)
        if ch:
            if ch['admin'] == chat.id:
                for cchat in get_cchats(ch['id']):
                    try:
                        cchat.remove_contact(me)
                    except ValueError:
                        pass
                db.remove_channel(ch['id'])
            else:
                db.remove_cchat(chat.id)


# ======== Filters ===============

def filter_messages(message: Message, replies: Replies) -> None:
    """Process messages sent to groups, mega-groups and channels.
    """
    mg = db.get_mgroup(message.chat.id)
    if mg:
        if not message.text or message.filename:
            replies.add(text='Unsupported message')
            return

        name = get_name(message.get_sender_contact())
        text = '{}:\n{}'.format(name, message.text)

        for g in get_mchats(mg['id']):
            if g.id != message.chat.id:
                g.send_text(text)
        return

    ch = db.get_channel(message.chat.id)
    if ch and ch['admin'] == message.chat.id:
        if not message.text or message.filename:
            replies.add(text='Unsupported message')
            return

        name = get_name(message.get_sender_contact())
        text = '{}:\n{}'.format(name, message.text)

        for g in get_cchats(ch['id']):
            replies.add(text=text, chat=g)
    elif ch:
        replies.add(text='Only channel operators can do that.')


# ======== Commands ===============

def cmd_mega(command: IncomingCommand, replies: Replies) -> None:
    """Convert the group where it is sent in a mega-group.
    """
    if db.get_mgroup(command.message.chat.id):
        replies.add(text='This is already a mega-group')
        return

    if db.get_channel(command.message.chat.id):
        replies.add(text='This is a channel')
        return

    name = command.message.chat.get_name()
    if db.get_mgroup_by_name(name):
        replies.add(
            text='Failed, there is a mega-group with the same name')
        return

    g = db.get_group(command.message.chat.id)
    if g:
        db.remove_group(g['id'])
        db.add_mgroup(g['pid'], name, g['topic'], g['status'])
    else:
        db.add_mgroup(generate_pid(), name, None, Status.PUBLIC)
    db.add_mchat(command.message.chat.id, db.get_mgroup_by_name(name)['id'])

    replies.add(text='This is now a mega-group')


def cmd_id(command: IncomingCommand, replies: Replies) -> None:
    """Show the id of the group, mega-group or channel where it is sent.
    """
    if not command.message.chat.is_group():
        replies.add(text='This is not a group')
        return

    mg = db.get_mgroup(command.message.chat.id)
    if mg:
        if mg['status'] == Status.PUBLIC:
            status = 'Mega-Group Status: Public'
            gid = '{}{}'.format(MGROUP_URL, mg['id'])
        else:
            status = 'Mega-Group Status: Private'
            gid = '{}{}-{}'.format(MGROUP_URL, mg['pid'], mg['id'])
        replies.add(text='{}\nID: {}'.format(status, gid))
        return

    ch = db.get_channel(command.message.chat.id)
    if ch:
        if ch['status'] == Status.PUBLIC:
            status = 'Channel Status: Public'
            gid = '{}{}'.format(CHANNEL_URL, ch['id'])
        else:
            status = 'Channel Status: Private'
            gid = '{}{}-{}'.format(CHANNEL_URL, ch['pid'], ch['id'])
        replies.add(text='{}\nID: {}'.format(status, gid))
        return

    g = db.get_group(command.message.chat.id)
    if not g:
        add_group(command.message.chat.id)
        g = db.get_group(command.message.chat.id)
        assert g is not None

    url = GROUP_URL
    if g['status'] == Status.PUBLIC:
        status = 'Group Status: Public'
        gid = '{}{}'.format(url, g['id'])
    else:
        status = 'Group Status: Private'
        gid = '{}{}-{}'.format(url, g['pid'], g['id'])
    replies.add(text='{}\nID: {}'.format(status, gid))


def cmd_list(command: IncomingCommand, replies: Replies) -> None:
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
        chat = command.bot.get_chat(g['id'])
        groups[i] = (chat.get_name(), g['topic'], '{}{}'.format(
            GROUP_URL, chat.id), len(chat.get_contacts()))
    if groups:
        replies.add(
            text=get_list('Groups', groups), chat=command.message.chat)

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
        replies.add(text=get_list('Mega-Groups', mgroups),
                    chat=command.message.chat)

    channels = []
    for ch in db.get_channels(Status.PUBLIC):
        count = sum(
            map(lambda g: len(g.get_contacts())-1, get_cchats(ch['id'])))
        channels.append((ch['name'], ch['topic'],
                         '{}{}'.format(CHANNEL_URL, ch['id']), count))
    if channels:
        replies.add(text=get_list('Channels', channels),
                    chat=command.message.chat)

    if not groups and not mgroups and not channels:
        replies.add(text='Empty List')


def cmd_me(command: IncomingCommand, replies: Replies) -> None:
    """Show the list of groups, mega-groups and channels you are in.
    """
    sender = command.message.get_sender_contact()
    groups = []
    for group in db.get_groups(Status.PUBLIC) + db.get_groups(Status.PRIVATE):
        g = command.bot.get_chat(group['id'])
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

    replies.add(text=''.join(
        '{0}:\nID: {1}\n\n'.format(*g) for g in groups) or 'Empty list')


def cmd_members(command: IncomingCommand, replies: Replies) -> None:
    """Show list of mega-group members.
    """
    me = command.bot.self_contact

    mg = db.get_mgroup(command.message.chat.id)
    if not mg:
        replies.add(text='This is not a mega-group')
        return

    text = 'Members:\n'
    count = 0
    for g in get_mchats(mg['id']):
        for c in g.get_contacts():
            if c != me:
                text += '• {}\n'.format(get_name(c))
                count += 1
    replies.add(text='{}\n\n👤 Total: {}'.format(text, count))


def cmd_join(command: IncomingCommand, replies: Replies) -> None:
    """Join the given group or channel.
    """
    sender = command.message.get_sender_contact()
    pid = ''
    text = 'Added to {}\n(ID:{})\n\nTopic:\n{}'
    if command.payload.startswith(MGROUP_URL):
        data = rmprefix(command.payload, MGROUP_URL).split('-')
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
                    replies.add(
                        text='You are already a member of this group',
                        chat=group)
                    return None
                if len(contacts) < gsize:
                    g = group
                    gsize = len(contacts)
            if g is None:
                g = command.bot.create_group(mg['name'], [sender])
                db.add_mchat(g.id, mg['id'])
            else:
                add_contact(g, sender)

            text = text.format(mg['name'], command.payload, mg['topic'])
            replies.add(text=text)
            return
    elif command.payload.startswith(GROUP_URL):
        data = rmprefix(command.payload, GROUP_URL).split('-')
        if len(data) == 2:
            pid = data[0]
        gid = int(data[-1])
        gr = db.get_group(gid)
        if gr and (gr['status'] == Status.PUBLIC or gr['pid'] == pid):
            g = command.bot.get_chat(gr['id'])
            contacts = g.get_contacts()
            if sender in contacts:
                replies.add(
                    text='You are already a member of this group', chat=g)
            elif len(contacts) < int(getdefault('max_group_size')):
                add_contact(g, sender)
                replies.add(text=text.format(
                    g.get_name(), command.payload, gr['topic']))
            else:
                replies.add(text='Group is full')
            return
    elif command.payload.startswith(CHANNEL_URL):
        data = rmprefix(command.payload, CHANNEL_URL).split('-')
        if len(data) == 2:
            pid = data[0]
        gid = int(data[-1])
        ch = db.get_channel_by_id(gid)
        if ch and (ch['status'] == Status.PUBLIC or ch['pid'] == pid):
            g = command.bot.get_chat(ch['admin'])
            if sender in g.get_contacts():
                replies.add(
                    text='You are already a member of this channel',
                    chat=g)
                return
            for g in get_cchats(ch['id']):
                if sender in g.get_contacts():
                    replies.add(
                        text='You are already a member of this channel',
                        chat=g)
                    return
            g = command.bot.create_group(ch['name'], [sender])
            db.add_cchat(g.id, ch['id'])
            replies.add(text=text.format(
                ch['name'], command.payload, ch['topic']), chat=g)
            return

    replies.add(text='Invalid ID')


def cmd_topic(command: IncomingCommand, replies: Replies) -> None:
    """Show or change group/channel topic.
    """
    if not command.message.chat.is_group():
        replies.add(text='This is not a group')
        return

    if command.payload:
        new_topic = ' '.join(command.payload.split())
        max_size = int(getdefault('max_topic_size'))
        if len(new_topic) > max_size:
            new_topic = new_topic[:max_size]+'...'

        text = '** {} changed topic to:\n{}'

        mg = db.get_mgroup(command.message.chat.id)
        if mg:
            name = get_name(command.message.get_sender_contact())
            text = text.format(name, new_topic)
            db.set_mgroup_topic(mg['id'], new_topic)
            for chat in get_mchats(mg['id']):
                replies.add(text=text, chat=chat)
            return

        ch = db.get_channel(command.message.chat.id)
        if ch and ch['admin'] == command.message.chat.id:
            name = get_name(command.message.get_sender_contact())
            text = text.format(name, new_topic)
            db.set_channel_topic(ch['id'], new_topic)
            for chat in get_cchats(ch['id']):
                replies.add(text=text, chat=chat)
            replies.add(text=text)
            return
        if ch:
            replies.add(text='Only channel operators can do that.')
            return

        g = db.get_group(command.message.chat.id)
        if not g:
            add_group(command.message.chat.id)
            g = db.get_group(command.message.chat.id)
            assert g is not None
        db.set_group_topic(g['id'], new_topic)
        replies.add(text=text.format(
            command.message.get_sender_contact().addr, new_topic))
        return

    g = db.get_mgroup(command.message.chat.id) or db.get_channel(
        command.message.chat.id) or db.get_group(command.message.chat.id)
    if not g:
        add_group(command.message.chat.id)
        g = db.get_group(command.message.chat.id)
        assert g is not None
    replies.add(text='Topic:\n{}'.format(g['topic']))


def cmd_remove(command: IncomingCommand, replies: Replies) -> None:
    """Remove the member with the given address from the group it is sent. If no address is provided, removes yourself from group or channel.
    """
    sender = command.message.get_sender_contact()
    me = command.bot.self_contact

    if not command.payload:
        command.message.chat.remove_contact(sender)
        return

    if not command.message.chat.is_group():
        args = command.payload.split(maxsplit=1)
        url = args[0]
        command.payload = args[1] if len(args) == 2 else ''
        if url.startswith(MGROUP_URL):
            mg = db.get_mgroup_by_id(
                int(rmprefix(url, MGROUP_URL).split('-')[-1]))
            if not mg:
                replies.add(text='Invalid ID')
                return
            for g in get_mchats(mg['id']):
                if sender in g.get_contacts():
                    if not command.payload:
                        g.remove_contact(sender)
                        replies.add(
                            text='Removed from "{}"'.format(mg['name']))
                        return
                    break
            else:
                replies.add(text='You are not a member of that group')
                return
        elif url.startswith(CHANNEL_URL):
            ch = db.get_channel_by_id(
                int(rmprefix(url, CHANNEL_URL).split('-')[-1]))
            if not ch:
                replies.add(text='Invalid ID')
                return
            for g in get_cchats(ch['id'], include_admin=True):
                if sender in g.get_contacts():
                    g.remove_contact(sender)
                    replies.add(
                        text='Removed from "{}"'.format(ch['name']))
                    return
            else:
                replies.add(text='You are not a member of that channel')
                return
        elif url.startswith(GROUP_URL):
            g = db.get_group(int(rmprefix(url, GROUP_URL).split('-')[-1]))
            if not g:
                replies.add(text='Invalid ID')
                return
            if sender not in g.get_contacts():
                replies.add(text='You are not a member of that group')
                return
            if command.payload:
                if command.payload == command.bot.self_contact.addr:
                    replies.add(
                        text='You can not remove me from the group')
                    return
                g.remove_contact(command.payload)
                chat = command.bot.get_chat(command.payload)
                replies.add(text='Removed from {} by {}'.format(
                    g.get_name(), sender.addr), chat=chat)
                replies.add(text='** {} removed'.format(command.payload))
                return
            g.remove_contact(sender)
            replies.add(text='Removed from "{}"'.format(g.get_name()))
            return
    else:
        mg = db.get_mgroup(command.message.chat.id)

    if mg:
        addr = command.payload
        if '@' not in addr:
            addr = db.get_addr(addr)
        if not addr:
            replies.add(text='Unknow user: {}'.format(command.payload))
            return
        if addr == me.addr:
            replies.add(text='You can not remove me from the group')
            return
        for g in get_mchats(mg['id']):
            for c in g.get_contacts():
                if c.addr == addr:
                    g.remove_contact(c)
                    text = 'Removed from {} by {}'.format(
                        mg['name'], get_name(sender))
                    replies.add(text=text, chat=command.bot.get_chat(c))
                    replies.add(
                        text='** {} removed'.format(command.payload))
                    return
        replies.add(text='User "{}" is not member of the group'.format(
            command.payload))

    # if it is a group
    for c in command.message.chat.get_contacts():
        if c.addr == command.payload:
            command.message.chat.remove_contact(c)
            return
    replies.add(text='User "{}" is not member of this group'.format(
        command.payload))


def cmd_chan(command: IncomingCommand, replies: Replies) -> None:
    """Create a new channel with the given name.
    """
    if not command.payload:
        replies.add(text='You must provide a channel name')
        return
    if db.get_channel_by_name(command.payload):
        replies.add(text='There is already a channel with that name')
        return
    g = command.bot.create_group(
        command.payload, [command.message.get_sender_contact()])
    db.add_channel(generate_pid(), command.payload, None, g.id, Status.PUBLIC)
    replies.add(text='Channel created', chat=g)


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


def get_name(c: Contact) -> str:
    if c.name == c.addr:
        return c.addr
    return '{}({})'.format(c.name, c.addr)
