# -*- coding: utf-8 -*-
import os

from .db import DBManager
from deltabot.hookspec import deltabot_hookimpl
import simplebot_chess.game as chgame
# typing
from typing import Optional
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message
# ======


version = '1.0.0'
db: DBManager
dbot: DeltaBot


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global db, dbot
    dbot = bot
    db = get_db(bot)

    getdefault('theme', '0')

    bot.filters.register(name=__name__, func=filter_messages)

    dbot.commands.register('/chess_play', cmd_play)
    dbot.commands.register('/chess_surrender', cmd_surrender)
    dbot.commands.register('/chess_new', cmd_new)
    dbot.commands.register('/chess_repeat', cmd_repeat)


@deltabot_hookimpl
def deltabot_member_removed(chat: Chat, contact: Contact) -> None:
    game = db.get_game_by_gid(chat.id)
    if game:
        me = dbot.self_contact
        if contact.addr in (me.addr, game['p1'], game['p2']):
            db.delete_game(game['p1'], game['p2'])
            if contact != me:
                chat.remove_contact(me)


# ======== Filters ===============

def filter_messages(msg: Message) -> Optional[str]:
    """Process move coordinates in Chess game groups
    """
    game = db.get_game_by_gid(msg.chat.id)
    if game is None or game['game'] is None or ' ' in msg.text:
        return None

    b = chgame.Board(game['game'])
    player = msg.get_sender_contact().addr
    if b.turn == player:
        try:
            b.move(msg.text)
            db.set_game(game['p1'], game['p2'], b.export())
            return run_turn(msg.chat.id)
        except (ValueError, AssertionError):
            return '❌ Invalid move!'
    return None


# ======== Commands ===============

def cmd_play(cmd: IncomingCommand) -> Optional[str]:
    """Invite a friend to play Chess.

    Example: `/play friend@example.com`
    To move use Standard Algebraic Notation or Long Algebraic Notation
    (without hyphens), more info in Wikipedia.
    For example, to move pawn from e2 to e4, send a message: e4 or: e2e4,
    to move knight from g1 to f3, send a message: Nf3 or: g1f3
    """
    if not cmd.payload:
        return "Missing address"

    p1 = cmd.message.get_sender_contact().addr
    p2 = cmd.payload
    if p1 == p2:
        return "You can't play with yourself"

    g = db.get_game_by_players(p1, p2)

    if g is None:  # first time playing with p2
        chat = cmd.bot.create_group(
            '♞ {} 🆚 {} [Chess]'.format(p1, p2), [p1, p2])
        b = chgame.Board(p1=p1, p2=p2, theme=int(getdefault('theme')))
        db.add_game(p1, p2, chat.id, b.export())
        text = 'Hello {1},\nYou have been invited by {0} to play Chess'
        text += '\n\n{} White: {}\n{} Black: {}\n\n'
        text = text.format(b.theme['P'], p1, b.theme['p'], p2)
        chat.send_text(text + run_turn(chat.id))
    else:
        chat = cmd.bot.get_chat(g['gid'])
        chat.send_text('You already have a game group with {}'.format(p2))
    return None


def cmd_surrender(cmd: IncomingCommand) -> Optional[str]:
    """End the Chess game in the group it is sent.
    """
    game = db.get_game_by_gid(cmd.message.chat.id)
    loser = cmd.message.get_sender_contact().addr
    if game is None or loser not in (game['p1'], game['p2']):
        return 'This is not your game group'
    if game['game'] is None:
        return 'There is no game running'
    db.set_game(game['p1'], game['p2'], None)
    return '🏳️ Game Over.\n{} surrenders.'.format(loser)


def cmd_new(cmd: IncomingCommand) -> Optional[str]:
    """Start a new Chess game in the current game group.
    """
    p1 = cmd.message.get_sender_contact().addr
    game = db.get_game_by_gid(cmd.message.chat.id)
    if game is None or p1 not in (game['p1'], game['p2']):
        return 'This is not your game group'
    if game['game'] is None:
        p2 = game['p2'] if p1 == game['p1'] else game['p1']
        b = chgame.Board(p1=p1, p2=p2, theme=int(getdefault('theme')))
        db.set_game(p1, p2, b.export())
        text = 'Game started!\n{} White: {}\n{} Black: {}\n\n'.format(
            b.theme['P'], p1, b.theme['p'], p2)
        return text + run_turn(cmd.message.chat.id)
    return 'There is a game running already'


def cmd_repeat(cmd: IncomingCommand) -> str:
    """Send game board again.
    """
    return run_turn(cmd.message.chat.id)


# ======== Utilities ===============

def run_turn(gid: int) -> str:
    g = db.get_game_by_gid(gid)
    b = chgame.Board(g['game'], theme=int(getdefault('theme')))
    result = b.result()
    if result == '*':
        return "{} {} it's your turn...\n\n{}".format(
            b.theme['P'] if b.turn == b.white else b.theme['p'], b.turn, b)
    db.set_game(g['p1'], g['p2'], None)
    if result == '1/2-1/2':
        return '🤝 Game over.\nIt is a draw!\n\n{}'.format(b)
    if result == '1-0':
        winner = '{} {}'.format(b.theme['P'], b.white)
    else:
        winner = '{} {}'.format(b.theme['p'], b.black)
    return '🏆 Game over.\n{} Wins!!!\n\n{}'.format(winner, b)


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
