# -*- coding: utf-8 -*-
import os

from .db import DBManager
from .game import Board
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

    dbot.commands.register('/mines_play', cmd_play)
    dbot.commands.register('/mines_repeat', cmd_repeat)


@deltabot_hookimpl
def deltabot_member_removed(chat: Chat, contact: Contact) -> None:
    game = db.get_game_by_gid(chat.id)
    if game:
        me = dbot.self_contact
        if contact.addr in (me.addr, game['addr']):
            db.delete_game(game['addr'])
            if contact != me:
                chat.remove_contact(me)


# ======== Filters ===============

def filter_messages(message: Message, replies: Replies) -> None:
    """Process move coordinates in Minesweeper game groups.
    """
    if not message.text.isalnum() or len(message.text) != 2:
        return

    game = db.get_game_by_gid(message.chat.id)
    if game is None or game['board'] is None:
        return

    try:
        b = Board(game['board'])
        b.move(message.text)
        db.set_board(game['addr'], b.export())
        replies.add(text=run_turn(message.chat.id))
    except ValueError as err:
        dbot.logger.exception(err)
        replies.add(text='❌ Invalid move!')


# ======== Commands ===============

def cmd_play(command: IncomingCommand, replies: Replies) -> None:
    """Start a new Minesweeper game.

    Example: `/mines_play`
    """
    player = command.message.get_sender_contact()
    game = db.get_game_by_addr(player.addr)

    if game is None:  # make a new chat
        b = Board()
        chat = command.bot.create_group('💣 Minesweeper', [player.addr])
        db.add_game(player.addr, chat.id, b.export())
        text = 'Hello {}, in this group you can play Minesweeper.\n\n'.format(
            player.name)
        replies.add(text=text + run_turn(chat.id), chat=chat)
    else:
        db.set_board(game['addr'], Board().export())
        if command.message.chat.id == game['gid']:
            chat = command.message.chat
        else:
            chat = command.bot.get_chat(game['gid'])
        replies.add(
            text='Game started!\n\n' + run_turn(game['gid']), chat=chat)


def cmd_repeat(command: IncomingCommand, replies: Replies) -> None:
    """Send Minesweeper game board again.

    Example: `/mines_repeat`
    """
    game = db.get_game_by_addr(command.message.get_sender_contact().addr)
    if game:
        if command.message.chat.id == game['gid']:
            chat = command.message.chat
        else:
            chat = command.bot.get_chat(game['gid'])
        replies.add(text=run_turn(game['gid']), chat=chat)
    else:
        replies.add(
            text="No active game, send /mines_play to start playing.")


# ======== Utilities ===============

def run_turn(gid: int) -> str:
    g = db.get_game_by_gid(gid)
    assert g is not None
    if not g['board']:
        return "No active game, send /mines_play to start playing."
    b = Board(g['board'])
    result = b.result()
    if result == 1:
        text = '🏆 Game over. You Win!!!\n\n{}'
    elif result == -1:
        text = '☠️ Game over. You died.\n\n{}'
    else:
        return str(b)
    db.set_board(g['addr'], None)
    return text.format(b.reveal(result)) + '\n\nPlay again? /mines_play'


def get_db(bot: DeltaBot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))
