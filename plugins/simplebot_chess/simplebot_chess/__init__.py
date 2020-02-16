# -*- coding: utf-8 -*-
import gettext
import io
import os
import sqlite3

from simplebot import Plugin, PluginCommand, PluginFilter
import chess
import chess.pgn


def _(text):
    return text


ranks = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣']
files = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭']
pieces = {
    'r': '♜',
    'n': '♞',
    'b': '♝',
    'q': '♛',
    'k': '♚',
    'p': '♟',
    'R': '♖',
    'N': '♘',
    'B': '♗',
    'Q': '♕',
    'K': '♔',
    'P': '♙',
}


def format(board):
    text = '⬜|{}|⬜\n'.format('|'.join(files))
    for i, line in enumerate(str(board).splitlines()):
        text += '{}|'.format(ranks[7-i])
        line = line.split()
        for j, cell in enumerate(line, start=1):
            if cell == '.':
                text += '⬛' if (i+j) % 2 == 0 else '⬜'
            else:
                text += pieces[cell]
            text += '|'
        text += '{}\n'.format(ranks[7-i])
    text += '⬜|{}|⬜\n'.format('|'.join(files))
    return text


class Chess(Plugin):

    name = 'Chess'
    version = '0.1.0'

    @classmethod
    def activate(cls, bot):
        super().activate(bot)

        cls.db = DBManager(os.path.join(
            cls.bot.get_dir(__name__), 'chess.db'))

        localedir = os.path.join(os.path.dirname(__file__), 'locale')
        lang = gettext.translation('simplebot_chess', localedir=localedir,
                                   languages=[bot.locale], fallback=True)
        lang.install()

        cls.description = _('Chess game to play with friends!')
        cls.long_description = _(
            'To move use Standard Algebraic Notation <https://en.wikipedia.org/wiki/Algebraic_notation_(chess)> or Long Algebraic Notation (without hyphens) <https://en.wikipedia.org/wiki/Universal_Chess_Interface>\nFor example, to move pawn from e2 to e4, send a message: e4, or a message: e2e4, to move knight from g1 to f3, send a message: Nf3, or a message: g1f3')
        cls.filters = [PluginFilter(cls.process_messages)]
        cls.bot.add_filters(cls.filters)
        cls.commands = [
            PluginCommand('/chess/play', ['<email>'],
                          _('Invite a friend to play.'), cls.play_cmd),
            PluginCommand('/chess/surrender', [],
                          _('End the game in the group it is sent.'), cls.surrender_cmd),
            PluginCommand(
                '/chess/new', [], _('Start a new game in the current game group.'), cls.new_cmd),
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
        game = chess.pgn.read_game(io.StringIO(r['game']))
        b = game.board()
        for move in game.mainline_moves():
            b.push(move)
        result = b.result()
        if result == '*':
            if b.turn == chess.WHITE:
                turn = '♔ {}'.format(game.headers['White'])
            else:
                turn = '♚ {}'.format(game.headers['Black'])
            chat.send_text(
                _('{} is your turn...\n\n{}').format(turn, format(b)))
        else:
            if result == '1/2-1/2':
                chat.send_text(
                    _('Game over.\nIt is a draw!\n\n{}').format(format(b)))
            else:
                if result == '1-0':
                    winner = '♔ {}'.format(game.headers['White'])
                else:
                    winner = '♚ {}'.format(game.headers['Black'])
                chat.send_text(_('🏆 Game over.\n{} Wins!!!\n\n{}').format(
                    winner, format(b)))
            cls.db.commit('UPDATE games SET game=? WHERE players=?',
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
                chat = cls.bot.create_group(
                    '♞ {} Vs {} [{}]'.format(p1, p2, cls.name), [p1, p2])
                game = chess.pgn.Game()
                game.headers['White'] = p1
                game.headers['Black'] = p2
                cls.db.insert((players, chat.id, str(game)))
                chat.send_text(
                    _('Hello {1},\nYou have been invited by {0} to play {2}\n\n♔ White: {0}\n♚ Black: {1}').format(p1, p2, cls.name))
                cls.run_turn(chat)
            else:
                chat = cls.bot.get_chat(r['gid'])
                chat.send_text(
                    _('You already has a game group with {}, to start a new game just send:\n/chess/new').format(p2))

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
        elif game['game'] is None:
            chat.send_text(
                _('There are no game running. To start a new game use /chess/new'))
        else:
            cls.db.commit('UPDATE games SET game=? WHERE players=?',
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
        elif r['game'] is None:
            game = chess.pgn.Game()
            game.headers['White'] = sender
            game.headers['Black'] = r['players'].replace(sender, '').strip(',')
            cls.db.commit('UPDATE games SET game=? WHERE players=?',
                          (str(game), r['players']))
            chat.send_text(_('Game started!\n♔ White: {}\n♚ Black: {}').format(
                sender, game.headers['Black']))
            cls.run_turn(chat)
        else:
            chat.send_text(
                _('There are a game running already, to start a new one first end this game'))

    @classmethod
    def process_messages(cls, ctx):
        chat = cls.bot.get_chat(ctx.msg)
        r = cls.db.execute(
            'SELECT * FROM games WHERE gid=?', (chat.id,)).fetchone()
        if r is None:
            return
        p1, p2 = map(cls.bot.get_contact, r['players'].split(','))
        me = cls.bot.get_contact()
        contacts = chat.get_contacts()
        if me not in contacts or p1 not in contacts or p2 not in contacts:
            cls.db.commit('DELETE FROM games WHERE players=?', (r['players'],))
            chat.remove_contact(me)
            return
        if ' ' in ctx.text:
            return

        ctx.processed = True
        game = chess.pgn.read_game(io.StringIO(r['game']))
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)
        if board.turn == chess.WHITE:
            turn = game.headers['White']
        else:
            turn = game.headers['Black']
        player = ctx.msg.get_sender_contact().addr
        if player == turn:
            try:
                try:
                    board.push_san(ctx.text)
                except ValueError:
                    board.push_uci(ctx.text)
                game.end().add_variation(chess.Move.from_uci(ctx.text))
                cls.db.commit('UPDATE games SET game=? WHERE players=?',
                              (str(game), r['players']))
                cls.run_turn(chat)
            except (ValueError, AssertionError):
                chat.send_text(_('Invalid move!'))


class DBManager:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.commit('''CREATE TABLE IF NOT EXISTS games
                       (players TEXT,
                        gid INTEGER NOT NULL,
                        game TEXT,
                        PRIMARY KEY(players))''')

    def execute(self, statement, args=()):
        return self.db.execute(statement, args)

    def commit(self, statement, args=()):
        with self.db:
            return self.db.execute(statement, args)

    def insert(self, row):
        self.commit('INSERT INTO games VALUES (?,?,?)', row)

    def close(self):
        self.db.close()
