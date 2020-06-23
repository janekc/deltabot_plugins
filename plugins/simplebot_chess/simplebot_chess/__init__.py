# -*- coding: utf-8 -*-
import os

from .db import DBManager
from deltachat import account_hookimpl
from deltabot.hookspec import deltabot_hookimpl
import simplebot_chess.game as chgame
# typing
from typing import Optional, Callable
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message
# ======


version = '1.0.0'
db: DBManager = None
dbot: DeltaBot = None


# ======== Hooks ===============

class AccountListener:
    def __init__(self, db: DBManager, bot: DeltaBot) -> None:
        self.db = db
        self.bot = bot

    @account_hookimpl
    def ac_member_removed(self, chat: Chat, contact: Contact,
                          message: Message) -> None:
        game = self.db.get_game_by_gid(chat.id)
        if game:
            me = self.bot.self_contact
            if contact.addr in (me.addr, game['p1'], game['p2']):
                self.db.delete_game(game['p1'], game['p2'])
                try:
                    chat.remove_contact(me)
                except ValueError:
                    pass


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global db, dbot
    dbot = bot
    db = get_db(bot)

    bot.filters.register(name=__name__, func=filter_messages)

    register_cmd('/play', '/chess_play', cmd_play)
    register_cmd('/surrender', '/chess_surrender', cmd_surrender)
    register_cmd('/new', '/chess_new', cmd_new)

    bot.account.add_account_plugin(AccountListener(db, bot))


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
        game = chgame.Board(p1=p1, p2=p2).export()
        db.add_game(p1, p2, chat.id, game)
        text = 'Hello {1},\nYou have been invited by {0} to play Chess'
        text += '\n\n♔ White: {0}\n♚ Black: {1}\n\n'
        text = text.format(p1, p2)
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
        b = chgame.Board(p1=p1, p2=p2)
        db.set_game(p1, p2, b.export())
        text = 'Game started!\n♔ White: {}\n♚ Black: {}\n\n'.format(
            p1, p2)
        return text + run_turn(cmd.message.chat.id)
    return 'There is a game running already'


# ======== Utilities ===============

def run_turn(gid: int) -> str:
    g = db.get_game_by_gid(gid)
    b = chgame.Board(g['game'])
    result = b.result()
    if result == '*':
        return "{} {} it's your turn...\n\n{}".format(
            '♔' if b.turn == b.white else '♚', b.turn, b)
    db.set_game(g['p1'], g['p2'], None)
    if result == '1/2-1/2':
        return '🤝 Game over.\nIt is a draw!\n\n{}'.format(b)
    if result == '1-0':
        winner = '♔ {}'.format(b.white)
    else:
        winner = '♚ {}'.format(b.black)
    return '🏆 Game over.\n{} Wins!!!\n\n{}'.format(winner, b)


def get_db(bot: DeltaBot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))


def register_cmd(name: str, alt_name: str, func: Callable) -> None:
    try:
        dbot.commands.register(name=name, func=func)
    except ValueError:
        dbot.commands.register(name=alt_name, func=func)
