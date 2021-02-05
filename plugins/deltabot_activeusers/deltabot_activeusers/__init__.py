# -*- coding: utf-8 -*-
from deltabot.hookspec import deltabot_hookimpl
from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand
from .db import DBManager
from deltachat import Chat, Contact, Message
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import socket
import re
import os
import segno



version = '1.0.0'
db: DBManager
dbot: DeltaBot


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global db, dbot
    dbot = bot
    db = get_db(bot)

    bot.commands.register(name="/info", func=cmd_info)
    bot.commands.register(name="/refresh", func=cmd_refresh)
    bot.commands.register(name="/show", func=cmd_show)


@deltabot_hookimpl
def deltabot_start(bot: DeltaBot, chat = Chat) -> None:
    groups = []
    groups = db.get_groups()
    if groups:
        for g in groups:
            if g['topic'] == 'Admin group' and g['id'] == int(dbot.get('admgrpid')):
                dbot.logger.info("found Admin group")
            else:
                dbot.logger.warn("no admin group found. removing groups. gid:" + str(g['id']))
                db.remove_group(g['id'])         
    else:
        dbot.logger.warn("no groups found. Creating an admin group")
        chat = dbot.account.create_group_chat("Admin group", contacts=[], verified=True)
        db.upsert_group(chat.id, chat.get_name())
        dbot.set("admgrpid",chat.id)
        qr = segno.make(chat.get_join_qr())
        print("\nPlease scan this qr code to join a verified group chat with the bot:\n\n")
        qr.terminal()


# ======== Commands ===============

def cmd_info(command: IncomingCommand, replies: Replies) -> None:
    """Shows info
    """
    if check_priv(command.message, dbot):
        replies.add(text='💻 Userbot active on: {} '.format(socket.gethostname()))
        replies.add(text='Available commands:\n/info - show this info \n/refresh - scan logs \n/show <all|active|inactive> <hours default=24>\nshow active or inactive users in the last n hours')


def cmd_refresh(command: IncomingCommand, replies: Replies) -> None:
    """Reads logfile and creates a summary
    """
    if check_priv(command.message, dbot):
        writetodatabase(parse("/var/log/mail.log"))
        replies.add(text='✅ scanned for new logins: {}'.format(str(datetime.now())))


def cmd_show(command: IncomingCommand, message: Message, replies: Replies) -> None:
    """Shows last login dates for every user seen
    Show active or inactive users in the last n hours

    Todo: use cmd handling
    """
    if check_priv(command.message, dbot):
        usercount = 0
        textlist = "❌ Wrong syntax!\n/show <all|active|inactive> <hours default=24>"
        text = command.payload
        args = command.payload.split(maxsplit=1)
        subcommand = args[0]
        parameter = args[1] if len(args) == 2 else ''
        startdate = datetime.now(timezone(timedelta(hours=1))) - timedelta(hours=24)
        if parameter:
            try:
                parameter = int(parameter)
            except ValueError as e:
                replies.add(text="❌ Wrong Syntax!\nParameter must be a number\n/show <all|active|inactive> <hours default=24>")
                return
            startdate = datetime.now(timezone(timedelta(hours=1))) - timedelta(hours=parameter)
        if subcommand == "all":
            textlist = ""
            for user, timestamp in db.deltabot_list_users():
                usercount = usercount + 1
                textlist = textlist + "{0:25} {1} \n".format(user, timestamp[:-13])
            textlist = textlist + "\n\nUsers: {}".format(usercount)
        if subcommand == "active":
            textlist = "Showing users who have been seen since {}\n\n".format(startdate)
            textlist = textlist + comparedatetime(1, startdate)
        if subcommand == "inactive":
            textlist = "Showing users who have NOT been seen since {}\n\n".format(startdate)
            textlist = textlist + comparedatetime(0, startdate)
        replies.add(text=textlist)
        

# ======== Utilities ===============

def writetodatabase(dict_obj):
    for user, timestamp in dict_obj.items():
        timestamp = datetime.fromisoformat(timestamp)
        db.store_mailusers(user, timestamp)


def get_db(bot: DeltaBot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))


def parse(file):
    lastseen = {}
    with open(file, "r") as logfile:
        for line in logfile:
            matchLogin = re.search(r'Login: user=<([a-zA-Z0-9_.+-]+@testrun.org)', line)
            if matchLogin:
                matchDate = re.match(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.\d\d\d\d\d\d\+\d\d:00', line)
                if matchDate:
                    lastseen.update({matchLogin.group()[13:]: matchDate.group()})
    return lastseen


def comparedatetime(sign, startdate):
    """write to file
    """
    textlist = ""
    usercount = 0
    for user, timestamp in db.list_mailusers():
        if sign == 1 and startdate < datetime.fromisoformat(timestamp):
            usercount = usercount + 1
            textlist = textlist + "{0:25} {1} \n".format(user, timestamp[:-13])
        if sign == 0 and startdate > datetime.fromisoformat(timestamp):
                usercount = usercount + 1
                textlist = textlist + "{0:25} {1} \n".format(user, timestamp[:-13])
    textlist = textlist + "\n\n Users: {}".format(usercount)
    return textlist


def check_priv(message: Message, bot: DeltaBot) -> None:
    groups = db.get_groups()
    if message.chat.is_group():
        for g in groups:
            if g['id'] == message.chat.id:
                dbot.logger.info("recieved message in registered group")
                if message.chat.is_protected():
                    return True
    dbot.logger.error("recieved message from not registered group or 1on1.")
    dbot.logger.error("Sender: {} Chat: {}".format(message.get_sender_contact().addr, message.chat.get_name()))
    return False
