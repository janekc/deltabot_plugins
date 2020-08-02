# -*- coding: utf-8 -*-
import os

from .database import DBManager
from .reversi import Board, BLACK, WHITE
from deltabot.hookspec import deltabot_hookimpl
# typing:
from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message


version = '1.0.0'
db: DBManager
dbot: DeltaBot


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global db, dbot
    dbot = bot
    db = get_db(bot)

    bot.filters.register(name=__name__, func=filter_messages)

    dbot.commands.register('/reversi_play', cmd_play)
    dbot.commands.register('/reversi_surrender', cmd_surrender)
    dbot.commands.register('/reversi_new', cmd_new)
    dbot.commands.register('/reversi_repeat', cmd_repeat)


@deltabot_hookimpl
def deltabot_member_removed(chat: Chat, contact: Contact) -> None:
    game = db.get_game_by_gid(chat.id)
    if game:
        me = dbot.self_contact
        p1, p2 = game['p1'], game['p2']
        if contact.addr in (me.addr, p1, p2):
            db.delete_game(p1, p2)
            if contact != me:
                chat.remove_contact(me)


# ======== Filters ===============

def filter_messages(message: Message, replies: Replies) -> None:
    """Process move coordinates in Reversi game groups
    """
    if len(message.text) != 2 or not message.text.isalnum():
        return
    game = db.get_game_by_gid(message.chat.id)
    if game is None or game['board'] is None:
        return

    b = Board(game['board'])
    player = message.get_sender_contact().addr
    player = BLACK if game['black'] == player else WHITE
    if b.turn == player:
        try:
            b.move(message.text)
            db.set_board(game['p1'], game['p2'], b.export())
            replies.add(text=run_turn(message.chat.id))
        except (ValueError, AssertionError):
            replies.add(text='❌ Invalid move!')


# ======== Commands ===============

def cmd_play(command: IncomingCommand, replies: Replies) -> None:
    """Invite a friend to play Reversi.

    Example: `/reversi_play friend@example.com`
    """
    if not command.payload:
        replies.add(text="Missing address")
        return

    if command.payload == command.bot.self_contact.addr:
        replies.add(text="Sorry, I don't want to play")
        return

    p1 = command.message.get_sender_contact().addr
    p2 = command.payload
    if p1 == p2:
        replies.add(text="You can't play with yourself")
        return

    g = db.get_game_by_players(p1, p2)

    if g is None:  # first time playing with p2
        b = Board()
        chat = command.bot.create_group(
            '🔴 {} 🆚 {} [Reversi]'.format(p1, p2), [p1, p2])
        db.add_game(p1, p2, chat.id, b.export(), p1)
        text = 'Hello {1},\nYou have been invited by {0} to play Reversi'
        text += '\n\n{2}: {0}\n{3}: {1}\n\n'
        text = text.format(p1, p2, b.get_disk(BLACK), b.get_disk(WHITE))
        replies.add(text=text + run_turn(chat.id), chat=chat)
    else:
        text = 'You already have a game group with {}'.format(p2)
        replies.add(text=text, chat=command.bot.get_chat(g['gid']))


def cmd_surrender(command: IncomingCommand, replies: Replies) -> None:
    """End the Reversi game in the group it is sent.
    """
    game = db.get_game_by_gid(command.message.chat.id)
    loser = command.message.get_sender_contact().addr
    # this is not your game group
    if game is None or loser not in (game['p1'], game['p2']):
        replies.add(text='This is not your game group')
    elif game['board'] is None:
        replies.add(text='There is no game running')
    else:
        db.set_board(game['p1'], game['p2'], None)
        replies.add(text='🏳️ Game Over.\n{} surrenders.'.format(loser))


def cmd_new(command: IncomingCommand, replies: Replies) -> None:
    """Start a new Reversi game in the current game group.
    """
    sender = command.message.get_sender_contact().addr
    game = db.get_game_by_gid(command.message.chat.id)
    # this is not your game group
    if game is None or sender not in (game['p1'], game['p2']):
        replies.add(text='This is not your game group')
    elif game['board'] is None:
        b = Board()
        db.set_game(game['p1'], game['p2'], b.export(), sender)
        p2 = game['p2'] if sender == game['p1'] else game['p1']
        text = 'Game started!\n{}: {}\n{}: {}\n\n'.format(
            b.get_disk(BLACK), sender, b.get_disk(WHITE), p2)
        replies.add(text=text + run_turn(command.message.chat.id))
    else:
        replies.add(text='There is a game running already')


def cmd_repeat(command: IncomingCommand, replies: Replies) -> None:
    """Send game board again.
    """
    replies.add(text=run_turn(command.message.chat.id))


# ======== Utilities ===============

def run_turn(gid: int) -> str:
    g = db.get_game_by_gid(gid)
    if not g:
        return 'This is not your game group'
    if not g['board']:
        return 'There is no game running'
    b = Board(g['board'])
    result = b.result()
    if result['status'] in (0, 1):
        if result['status'] == 1:
            b.turn = BLACK if b.turn == WHITE else WHITE
            db.set_board(g['p1'], g['p2'], b.export())
        if b.turn == BLACK:
            disk = b.get_disk(BLACK)
            turn = '{} {}'.format(disk, g['black'])
        else:
            disk = b.get_disk(WHITE)
            p2 = g['p2'] if g['black'] == g['p1'] else g['p1']
            turn = '{} {}'.format(disk, p2)
        return "{} it's your turn...\n\n{}\n\n{}".format(
            turn, b, b.get_score())
    else:
        db.set_board(g['p1'], g['p2'], None)
        black, white = result[BLACK], result[WHITE]
        if black == white:
            return '🤝 Game over.\nIt is a draw!\n\n{}\n\n{}'.format(
                b, b.get_score())
        else:
            if black > white:
                disk = b.get_disk(BLACK)
                winner = '{} {}'.format(disk, g['black'])
            else:
                disk = b.get_disk(WHITE)
                p2 = g['p2'] if g['black'] == g['p1'] else g['p1']
                winner = '{} {}'.format(disk, p2)
            return '🏆 Game over.\n{} Wins!!!\n\n{}\n\n{}'.format(
                winner, b, b.get_score())


def get_db(bot: DeltaBot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))
