# -*- coding: utf-8 -*-
import gettext
import os
import sqlite3

from simplebot import Plugin, PluginCommand, PluginFilter
import simplebot_reversi.reversi as reversi


def _(text):
    return text


class Reversi(Plugin):

    name = 'Reversi'
    version = '0.1.0'

    @classmethod
    def activate(cls, bot):
        super().activate(bot)

        cls.db = DBManager(os.path.join(
            cls.bot.get_dir(__name__), 'reversi.db'))

        localedir = os.path.join(os.path.dirname(__file__), 'locale')
        lang = gettext.translation('simplebot_reversi', localedir=localedir,
                                   languages=[bot.locale], fallback=True)
        lang.install()

        cls.description = _('Reversi game to play with friends!')
        cls.long_description = _(
            'To move use a1, b3, etc.\nTo learn about Reversi and the game rules read: `https://en.wikipedia.org/wiki/Reversi')
        cls.filters = [PluginFilter(cls.process_messages)]
        cls.bot.add_filters(cls.filters)
        cls.commands = [
            PluginCommand('/reversi/play', ['<email>'],
                          _('Invite a friend to play.'), cls.play_cmd),
            PluginCommand('/reversi/surrender', [],
                          _('End the game in the group it is sent.'), cls.surrender_cmd),
            PluginCommand(
                '/reversi/new', [], _('Start a new game in the current game group.'), cls.new_cmd),
        ]
        cls.bot.add_commands(cls.commands)

    @classmethod
    def deactivate(cls):
        super().deactivate()
        cls.db.close()

    @classmethod
    def run_turn(cls, chat):
        r = cls.db.execute(
            'SELECT * FROM games WHERE gid=?', (chat.id,)).fetchone()
        b = reversi.Board(r['board'])
        result = b.result()
        if result is None:
            if b.turn == reversi.BLACK:
                disk = reversi.DISKS[reversi.BLACK]
                turn = '{} {}'.format(disk, r['black'])
            else:
                disk = reversi.DISKS[reversi.WHITE]
                p2 = r['players'].replace(r['black'], '').strip(',')
                turn = '{} {}'.format(disk, p2)
            text = _('{} is your turn...\n\n{}\n\n{}').format(
                turn, b, b.get_score())
            chat.send_text(text)
        else:
            black, white = result[reversi.BLACK], result[reversi.WHITE]
            if black == white:
                text = _('🤝 Game over.\nIt is a draw!\n\n{}\n\n{}').format(
                    b, b.get_score())
                chat.send_text(text)
            else:
                if black > white:
                    disk = reversi.DISKS[reversi.BLACK]
                    winner = '{} {}'.format(disk, r['black'])
                else:
                    disk = reversi.DISKS[reversi.WHITE]
                    p2 = r['players'].replace(r['black'], '').strip(',')
                    winner = '{} {}'.format(disk, p2)
                text = _('🏆 Game over.\n{} Wins!!!\n\n{}\n\n{}').format(
                    winner, b, b.get_score())
                chat.send_text(text)
            cls.db.commit('UPDATE games SET board=? WHERE players=?',
                          (None, r['players']))

    @classmethod
    def play_cmd(cls, ctx):
        if ctx.text:
            p1 = ctx.msg.get_sender_contact().addr
            p2 = ctx.text
            if p1 == p2:
                chat = cls.bot.get_chat(ctx.msg)
                chat.send_text(_("You can't play with yourself"))
                return
            players = ','.join(sorted([p1, p2]))
            r = cls.db.execute(
                'SELECT * FROM games WHERE players=?', (players,)).fetchone()
            if r is None:  # first time playing with p2
                disk = reversi.DISKS[reversi.BLACK]
                chat = cls.bot.create_group(
                    '{} {} 🆚 {} [{}]'.format(disk, p1, p2, cls.name), [p1, p2])
                b = reversi.Board()
                cls.db.insert((players, chat.id, b.export(), p1))
                b = reversi.DISKS[reversi.BLACK]
                w = reversi.DISKS[reversi.WHITE]
                chat.send_text(
                    _('Hello {1},\nYou have been invited by {0} to play {2}\n\n{3}: {0}\n{4}: {1}').format(p1, p2, cls.name, b, w))
                cls.run_turn(chat)
            else:
                chat = cls.bot.get_chat(r['gid'])
                chat.send_text(
                    _('You already has a game group with {}, to start a new game just send:\n/reversi/new').format(p2))

    @classmethod
    def surrender_cmd(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)
        loser = ctx.msg.get_sender_contact().addr
        game = cls.db.execute(
            'SELECT * FROM games WHERE gid=?', (chat.id,)).fetchone()
        # this is not your game group
        if game is None or loser not in game['players'].split(','):
            chat.send_text(
                _('This is not your game group, please send that command in the game group you want to surrender'))
        elif game['board'] is None:
            chat.send_text(
                _('There are no game running. To start a new game use /reversi/new'))
        else:
            cls.db.commit('UPDATE games SET board=? WHERE players=?',
                          (None, game['players']))
            chat.send_text(_('🏳️ Game Over.\n{} Surrenders.').format(loser))

    @classmethod
    def new_cmd(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)
        sender = ctx.msg.get_sender_contact().addr
        r = cls.db.execute(
            'SELECT * FROM games WHERE gid=?', (chat.id,)).fetchone()
        # this is not your game group
        if r is None or sender not in r['players'].split(','):
            chat.send_text(
                _('This is not your game group, please send that command in the game group you want to start a new game'))
        elif r['board'] is None:
            b = reversi.Board()
            cls.db.commit('UPDATE games SET board=?, black=? WHERE players=?',
                          (b.export(), sender, r['players']))
            b = reversi.DISKS[reversi.BLACK]
            w = reversi.DISKS[reversi.WHITE]
            p2 = r['players'].replace(sender, '').strip(',')
            chat.send_text(_('Game started!\n{}: {}\n{}: {}').format(
                b, sender, w, p2))
            cls.run_turn(chat)
        else:
            chat.send_text(
                _('There are a game running already, to start a new one first end this game'))

    @classmethod
    def process_messages(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)
        r = cls.db.execute(
            'SELECT * FROM games WHERE gid=?', (chat.id,)).fetchone()
        if None in (r, r['board']):
            return
        p1, p2 = map(cls.bot.get_contact, r['players'].split(','))
        me = cls.bot.get_contact()
        contacts = chat.get_contacts()
        if me not in contacts or p1 not in contacts or p2 not in contacts:
            cls.db.commit('DELETE FROM games WHERE players=?', (r['players'],))
            chat.remove_contact(me)
            return
        if len(ctx.text) != 2:
            return

        ctx.processed = True
        b = reversi.Board(r['board'])
        player = ctx.msg.get_sender_contact().addr
        player = reversi.BLACK if r['black'] == player else reversi.WHITE
        if b.turn == player:
            try:
                b.move(ctx.text)
                cls.db.commit('UPDATE games SET board=? WHERE players=?',
                              (b.export(), r['players']))
                cls.run_turn(chat)
            except (ValueError, AssertionError) as ex:
                cls.bot.logger.exception(ex)
                chat.send_text(_('❌ Invalid move!'))


class DBManager:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.commit('''CREATE TABLE IF NOT EXISTS games
                       (players TEXT,
                        gid INTEGER NOT NULL,
                        board TEXT,
                        black TEXT,
                        PRIMARY KEY(players))''')

    def execute(self, statement, args=()):
        return self.db.execute(statement, args)

    def commit(self, statement, args=()):
        with self.db:
            return self.db.execute(statement, args)

    def insert(self, row):
        self.commit('INSERT INTO games VALUES (?,?,?,?)', row)

    def close(self):
        self.db.close()
