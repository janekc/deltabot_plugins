# -*- coding: utf-8 -*-
from threading import Thread, Event
import gettext
import os
import re

from simplebot import Plugin, PluginCommand, PluginFilter
from .irc import IRCBot
from .database import DBManager


nick_re = re.compile(r'[a-zA-Z0-9]{1,30}$')


class IRCBridge(Plugin):

    name = 'IRC Bridge'
    version = '0.1.0'

    @classmethod
    def activate(cls, bot):
        super().activate(bot)

        localedir = os.path.join(os.path.dirname(__file__), 'locale')
        lang = gettext.translation(
            'simplebot_irc', localedir=localedir,
            languages=[bot.locale], fallback=True)
        lang.install()

        save = False
        cls.cfg = cls.bot.get_config(__name__)
        if not cls.cfg.get('max_group_size'):
            cls.cfg['max_group_size'] = '20'
            save = True
        if not cls.cfg.get('nick'):
            cls.cfg['nick'] = 'SimpleBot'
            save = True
        if not cls.cfg.get('host'):
            cls.cfg['host'] = 'irc.freenode.net'
            save = True
        if not cls.cfg.get('port'):
            cls.cfg['port'] = '6667'
            save = True
        if save:
            cls.bot.save_config()

        cls.db = DBManager(os.path.join(
            cls.bot.get_dir(__name__), 'irc.db'))

        cls.bot.logger.debug('Starting IRC worker')
        cls.connected = Event()
        cls.worker = Thread(target=cls.listen_to_irc)
        cls.worker.start()
        cls.connected.wait()
        cls.bot.logger.debug('Connected to IRC')

        cls.description = _('IRC <--> Delta Chat bridge.')
        filters = [PluginFilter(cls.process_messages)]
        cls.bot.add_filters(filters)
        commands = [
            PluginCommand('/irc/join', ['<channel>'], _('join the given channel'), cls.join_cmd),
            PluginCommand('/irc/remove', ['[nick]'],
                          _('Remove the member with the given nick from the channel, if no nick is given remove yourself'), cls.remove_cmd),
            PluginCommand('/irc/nick', ['[nick]'],
                          _('Set your nick or display your current nick if no new nick is given'), cls.nick_cmd)]
        cls.bot.add_commands(commands)

    @classmethod
    def get_cchats(cls, cname):
        cname = cname.lower()
        me = cls.bot.get_contact()
        chats = []
        invalid_chats = []
        old_chats = cls.db.execute(
            'SELECT id FROM cchats WHERE channel=?', (cname,))
        for r in old_chats:
            chat = cls.bot.get_chat(r[0])
            if chat is None:
                cls.db.commit('DELETE FROM cchats WHERE id=?', (r[0],))
                continue
            contacts = chat.get_contacts()
            if me not in contacts or len(contacts) == 1:
                invalid_chats.append(chat)
            else:
                chats.append(chat)
        for chat in invalid_chats:
            cls.db.commit('DELETE FROM cchats WHERE id=?', (chat.id,))
            try:
                chat.remove_contact(me)
            except ValueError:
                pass
        if not chats:
            cls.db.commit('DELETE FROM channels WHERE name=?', (cname,))
        return chats

    @classmethod
    def listen_to_irc(cls):
        cls.irc = IRCBot(cls)
        cls.irc.start()

    @classmethod
    def irc2dc(cls, channel, sender, msg):
        for g in cls.get_cchats(channel):
            g.send_text('{}:\n{}'.format(sender, msg))

    @classmethod
    def process_messages(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)
        r = cls.db.execute(
            'SELECT channel from cchats WHERE id=?',
            (chat.id,)).fetchone()
        if not r:
            return

        ctx.processed = True
        sender = ctx.msg.get_sender_contact()
        nick = cls.db.get_nick(sender.addr)

        if sender not in chat.get_contacts():
            return

        if not ctx.text or ctx.msg.filename:
            chat.send_text(_('Unsupported message'))
            return

        text = '{}[dc]: {}'.format(nick, ctx.text)

        cls.irc.send_message(r[0], text)
        for g in cls.get_cchats(r[0]):
            if g.id != chat.id:
                g.send_text(text)

    @classmethod
    def nick_cmd(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)
        addr = ctx.msg.get_sender_contact().addr
        new_nick = ' '.join(ctx.text.split())
        if new_nick:
            if not nick_re.match(new_nick):
                text = _(
                    '** Invalid nick, only letters and numbers are allowed, and nick should be less than 30 characters')
            elif cls.db.execute('SELECT * FROM nicks WHERE nick=?', (new_nick,)).fetchone():
                text = _('** Nick already taken')
            else:
                text = _('** Nick: {}').format(new_nick)
                cls.db.commit(
                    'INSERT OR REPLACE INTO nicks VALUES (?,?)', (addr, new_nick))
        else:
            text = _('** Nick: {}').format(cls.db.get_nick(addr))
        chat.send_text(text)

    @classmethod
    def join_cmd(cls, ctx):
        sender = ctx.msg.get_sender_contact()
        if not ctx.text:
            return

        ctx.text = ctx.text.lower()
        ch = cls.db.execute(
            'SELECT * FROM channels WHERE name=?',
            (ctx.text,)).fetchone()
        if ch:
            chats = cls.get_cchats(ch['name'])
        else:
            cls.irc.join_channel(ctx.text)
            cls.db.commit(
                'INSERT INTO channels VALUES (?)', (ctx.text,))
            ch = {'name': ctx.text}
            chats = []

        g = None
        gsize = cls.cfg.getint('max_group_size')
        for group in chats:
            contacts = group.get_contacts()
            if sender in contacts:
                group.send_text(
                    _('You are already a member of this group'))
                return
            if len(contacts) < gsize:
                g = group
                gsize = len(contacts)
        if g is None:
            g = cls.bot.create_group(ch['name'], [sender])
            cls.db.commit('INSERT INTO cchats VALUES (?,?)',
                          (g.id, ch['name']))
        else:
            g.add_contact(sender)

        nick = cls.db.get_nick(sender.addr)
        text = _('** You joined {} as {}').format(ch['name'], nick)
        g.send_text(text)

    @classmethod
    def remove_cmd(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)

        r = cls.db.execute(
            'SELECT channel from cchats WHERE id=?',
            (chat.id,)).fetchone()
        if not r:
            chat.send_text(_('This is not an IRC channel'))
            return

        channel = r[0]
        sender = ctx.msg.get_sender_contact().addr
        if not ctx.text:
            ctx.text = sender
        if '@' not in ctx.text:
            r = cls.db.execute(
                'SELECT addr FROM nicks WHERE nick=?',
                (ctx.text,)).fetchone()
            if not r:
                chat.send_text(_('Unknow user: {}').format(ctx.text))
                return
            ctx.text = r[0]

        for g in cls.get_cchats(channel):
            for c in g.get_contacts():
                if c.addr == ctx.text:
                    g.remove_contact(c)
                    s_nick = cls.get_nick(sender)
                    nick = cls.get_nick(c.addr)
                    text = _('** {} removed by {}').format(nick, s_nick)
                    for g in cls.get_cchats(channel):
                        g.send_text(text)
                    text = _('Removed from {} by {}').format(
                        channel, s_nick)
                    cls.bot.get_chat(c).send_text(text)
                    return
