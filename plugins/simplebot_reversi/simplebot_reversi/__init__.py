# -*- coding: utf-8 -*-
import os

from deltabot.hookspec import deltabot_hookimpl
from simplebot_reversi.database import DBManager
import simplebot_reversi.reversi as reversi


version = '1.0.0'


@deltabot_hookimpl
def deltabot_init(bot):
    global db
    plugin_dir = bot.get_dir(__name__)
    db = DBManager(os.path.join(plugin_dir, 'reversi.db'))

    bot.filters.register(name='reversi', func=process_messages)

    bot.commands.register(name='/reversi/play', func=process_play_cmd)
    bot.commands.register(
        name='/reversi/surrender', func=process_surrender_cmd)
    bot.commands.register(name='/reversi/new', func=process_new_cmd)


def process_messages(bot, msg):
    """Process move coordinates in Reversi game groups
    """
    game = db.get_game_by_gid(msg.chat.id)
    if game is None:
        return
    p1, p2 = map(bot.get_contact, game['players'].split(','))
    me = bot.self_contact()
    contacts = msg.chat.get_contacts()
    if me not in contacts or p1 not in contacts or p2 not in contacts:
        db.delete_game(game['players'])
        try:
            msg.chat.remove_contact(me)
        except ValueError:
            pass
        return
    if game['board'] is None or len(msg.text) != 2:
        return

    b = reversi.Board(game['board'])
    player = msg.get_sender_contact().addr
    player = reversi.BLACK if game['black'] == player else reversi.WHITE
    if b.turn == player:
        try:
            b.move(msg.text)
            db.set_board(game['players'], b.export())
            return run_turn(msg.chat.id)
        except (ValueError, AssertionError):
            return '❌ Invalid move!'


def process_play_cmd(cmd):
    """Invite a friend to play.

    Example: `/reversi/play friend@example.com`
    """
    if not cmd.payload:
        return "Missing address"

    p1 = cmd.message.get_sender_contact().addr
    p2 = cmd.payload
    if p1 == p2:
        return "You can't play with yourself"

    players = ','.join(sorted([p1, p2]))
    g = db.get_game_by_players(players)

    # fix bug caused by previous version
    if g is not None:
        chat = cmd.bot.get_chat(g['gid'])
        me = cmd.bot.self_contact()
        contacts = cmd.message.chat.get_contacts()
        c1, c2 = cmd.bot.get_contact(p1), cmd.bot.get_contact(p2)
        if me not in contacts or c1 not in contacts or c2 not in contacts:
            db.delete_game(g['players'])
        g = None

    if g is None:  # first time playing with p2
        b = reversi.DISKS[reversi.BLACK]
        w = reversi.DISKS[reversi.WHITE]
        chat = cmd.bot.create_group(
            '{} {} 🆚 {} [{}]'.format(b, p1, p2, 'Reversi'), [p1, p2])
        db.add_game(players, chat.id, reversi.Board().export(), p1)
        text = 'Hello {1},\nYou have been invited by {0} to play Reversi'
        text += '\n\n{2}: {0}\n{3}: {1}\n\n'
        text = text.format(p1, p2, b, w)
        chat.send_text(text + run_turn(chat.id))
    else:
        chat = cmd.bot.get_chat(g['gid'])
        chat.send_text('You already have a game group with {}'.format(p2))


def process_surrender_cmd(cmd):
    """End the game in the group it is sent.
    """
    game = db.get_game_by_gid(cmd.message.chat.id)
    loser = cmd.message.get_sender_contact().addr
    # this is not your game group
    if game is None or loser not in game['players'].split(','):
        return 'This is not your game group'
    elif game['board'] is None:
        return 'There are no game running'
    else:
        db.set_board(None, game['players'])
        return '🏳️ Game Over.\n{} surrenders.'.format(loser)


def process_new_cmd(cmd):
    """Start a new game in the current game group.
    """
    sender = cmd.message.get_sender_contact().addr
    game = db.get_game_by_gid(cmd.message.chat.id)
    # this is not your game group
    if game is None or sender not in game['players'].split(','):
        return 'This is not your game group'
    elif game['board'] is None:
        b = reversi.Board()
        db.set_game(game['players'], b.export(), sender)
        b = reversi.DISKS[reversi.BLACK]
        w = reversi.DISKS[reversi.WHITE]
        p2 = game['players'].replace(sender, '').strip(',')
        text = 'Game started!\n{}: {}\n{}: {}\n\n'.format(
            b, sender, w, p2)
        return text + run_turn(cmd.message.chat.id)
    else:
        return 'There are a game running already'


def run_turn(gid):
    g = db.get_game_by_gid(gid)
    b = reversi.Board(g['board'])
    result = b.result()
    if result is None:
        if b.turn == reversi.BLACK:
            disk = reversi.DISKS[reversi.BLACK]
            turn = '{} {}'.format(disk, g['black'])
        else:
            disk = reversi.DISKS[reversi.WHITE]
            p2 = g['players'].replace(g['black'], '').strip(',')
            turn = '{} {}'.format(disk, p2)
        return "{} it's your turn...\n\n{}\n\n{}".format(
            turn, b, b.get_score())
    else:
        db.set_board(None, g['players'])
        black, white = result[reversi.BLACK], result[reversi.WHITE]
        if black == white:
            return '🤝 Game over.\nIt is a draw!\n\n{}\n\n{}'.format(
                b, b.get_score())
        else:
            if black > white:
                disk = reversi.DISKS[reversi.BLACK]
                winner = '{} {}'.format(disk, g['black'])
            else:
                disk = reversi.DISKS[reversi.WHITE]
                p2 = g['players'].replace(g['black'], '').strip(',')
                winner = '{} {}'.format(disk, p2)
            return '🏆 Game over.\n{} Wins!!!\n\n{}\n\n{}'.format(
                winner, b, b.get_score())
