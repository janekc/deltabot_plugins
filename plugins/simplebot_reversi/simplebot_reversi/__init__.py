# -*- coding: utf-8 -*-
import os

from .database import DBManager
from deltachat import account_hookimpl
from deltabot.hookspec import deltabot_hookimpl
import simplebot_reversi.reversi as reversi
# typing
from typing import Optional, Callable
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message
# ===


version = '1.0.0'
db: DBManager = None
dbot: DeltaBot = None


# ======== Hooks ===============

class AccountListener:
    def __init__(self, db: DBManager, bot: DeltaBot) -> None:
        self.db = db
        self.bot = bot

    @account_hookimpl
    def ac_member_removed(self, chat: Chat, contact: Contact, message: Message) -> None:
        game = self.db.get_game_by_gid(chat.id)
        if game:
            me = self.bot.self_contact
            p1, p2 = game['p1'], game['p2']
            if contact.addr in (me.addr, p1, p2):
                self.db.delete_game(p1, p2)
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

    register_cmd('/play', '/reversi_play', cmd_play)
    register_cmd('/surrender', '/reversi_surrender', cmd_surrender)
    register_cmd('/new', '/reversi_new', cmd_new)

    bot.account.add_account_plugin(AccountListener(db, bot))


# ======== Filters ===============

def filter_messages(msg: Message) -> Optional[str]:
    """Process move coordinates in Reversi game groups
    """
    game = db.get_game_by_gid(msg.chat.id)
    if game is None or game['board'] is None or len(msg.text) != 2:
        return None

    b = reversi.Board(game['board'])
    player = msg.get_sender_contact().addr
    player = reversi.BLACK if game['black'] == player else reversi.WHITE
    if b.turn == player:
        try:
            b.move(msg.text)
            db.set_board(game['p1'], game['p2'], b.export())
            return run_turn(msg.chat.id)
        except (ValueError, AssertionError):
            return '❌ Invalid move!'

    return None


# ======== Commands ===============

def cmd_play(cmd: IncomingCommand) -> Optional[str]:
    """Invite a friend to play Reversi.

    Example: `/play friend@example.com`
    """
    if not cmd.payload:
        return "Missing address"

    p1 = cmd.message.get_sender_contact().addr
    p2 = cmd.payload
    if p1 == p2:
        return "You can't play with yourself"

    g = db.get_game_by_players(p1, p2)

    if g is None:  # first time playing with p2
        b = reversi.DISKS[reversi.BLACK]
        w = reversi.DISKS[reversi.WHITE]
        chat = cmd.bot.create_group(
            '{} {} 🆚 {} [Reversi]'.format(b, p1, p2), [p1, p2])
        db.add_game(p1, p2, chat.id, reversi.Board().export(), p1)
        text = 'Hello {1},\nYou have been invited by {0} to play Reversi'
        text += '\n\n{2}: {0}\n{3}: {1}\n\n'
        text = text.format(p1, p2, b, w)
        chat.send_text(text + run_turn(chat.id))
    else:
        chat = cmd.bot.get_chat(g['gid'])
        chat.send_text('You already have a game group with {}'.format(p2))

    return None


def cmd_surrender(cmd: IncomingCommand) -> Optional[str]:
    """End the Reversi game in the group it is sent.
    """
    game = db.get_game_by_gid(cmd.message.chat.id)
    loser = cmd.message.get_sender_contact().addr
    # this is not your game group
    if game is None or loser not in (game['p1'], game['p2']):
        return 'This is not your game group'
    if game['board'] is None:
        return 'There is no game running'
    db.set_board(game['p1'], game['p2'], None)
    return '🏳️ Game Over.\n{} surrenders.'.format(loser)


def cmd_new(cmd: IncomingCommand) -> Optional[str]:
    """Start a new Reversi game in the current game group.
    """
    sender = cmd.message.get_sender_contact().addr
    game = db.get_game_by_gid(cmd.message.chat.id)
    # this is not your game group
    if game is None or sender not in (game['p1'], game['p2']):
        return 'This is not your game group'
    if game['board'] is None:
        board = reversi.Board()
        db.set_game(game['p1'], game['p2'], board.export(), sender)
        b = reversi.DISKS[reversi.BLACK]
        w = reversi.DISKS[reversi.WHITE]
        p2 = game['p2'] if sender == game['p1'] else game['p1']
        text = 'Game started!\n{}: {}\n{}: {}\n\n'.format(
            b, sender, w, p2)
        return text + run_turn(cmd.message.chat.id)
    return 'There is a game running already'


# ======== Utilities ===============

def run_turn(gid: int) -> str:
    g = db.get_game_by_gid(gid)
    b = reversi.Board(g['board'])
    result = b.result()
    if result is None:
        if b.turn == reversi.BLACK:
            disk = reversi.DISKS[reversi.BLACK]
            turn = '{} {}'.format(disk, g['black'])
        else:
            disk = reversi.DISKS[reversi.WHITE]
            p2 = g['p2'] if g['black'] == g['p1'] else g['p1']
            turn = '{} {}'.format(disk, p2)
        return "{} it's your turn...\n\n{}\n\n{}".format(
            turn, b, b.get_score())
    else:
        db.set_board(g['p1'], g['p2'], None)
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
                p2 = g['p2'] if g['black'] == g['p1'] else g['p1']
                winner = '{} {}'.format(disk, p2)
            return '🏆 Game over.\n{} Wins!!!\n\n{}\n\n{}'.format(
                winner, b, b.get_score())


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
