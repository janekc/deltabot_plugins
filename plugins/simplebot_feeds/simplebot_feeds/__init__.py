# -*- coding: utf-8 -*-
from threading import Thread
from time import sleep
import os

from .db import DBManager
from deltachat import account_hookimpl
from deltabot.hookspec import deltabot_hookimpl
import feedparser
import html2text
# typing
from typing import Callable, Optional
from deltabot import DeltaBot
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message
# ======


version = '1.0.0'
feedparser.USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:60.0)'
feedparser.USER_AGENT += ' Gecko/20100101 Firefox/60.0'
html2text.config.WRAP_LINKS = False
dbot: DeltaBot
db: DBManager


# ======== Hooks ===============

class AccountListener:
    def __init__(self, db: DBManager, bot: DeltaBot) -> None:
        self.db = db
        self.bot = bot

    @account_hookimpl
    def ac_member_removed(self, chat: Chat, contact: Contact,
                          message: Message) -> None:
        feeds = self.db.get_feeds(chat.id)
        if feeds:
            me = self.bot.self_contact
            ccount = len(chat.get_contacts()) - 1
            if me == contact or ccount <= 1:
                self.db.remove_fchat(chat.id)
                for feed in feeds:
                    if not self.db.get_fchats(feed['url']):
                        self.db.remove_feed(feed['url'])


@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot, db
    dbot = bot
    db = get_db(bot)

    getdefault('delay', 60*5)

    bot.account.add_account_plugin(AccountListener(db, bot))

    register_cmd('/sub', '/feed_sub', cmd_sub)
    register_cmd('/unsub', '/feed_unsub', cmd_unsub)
    register_cmd('/list', '/feed_list', cmd_list)


@deltabot_hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    Thread(target=check_feeds, daemon=True).start()


# ======== Commands ===============

def cmd_sub(cmd: IncomingCommand) -> str:
    """Subscribe current chat to the given feed.
    """
    url = cmd.payload
    feed = db.get_feed(url)

    if not feed:
        d = feedparser.parse(url)
        if d.get('bozo') == 1:
            return 'Invalid feed url: {}'.format(url)
        db.add_feed(url, cmd.message.chat.id)
        title = d.feed.get('title') or '-'
        desc = d.feed.get('description') or '-'
        return 'Title: {}\n\nURL: {}\n\nDescription: {}'.format(
            title, url, desc)

    if cmd.message.chat.id in db.get_fchats(feed['url']):
        return 'Chat alredy subscribed to that feed.'

    db.add_fchat(cmd.message.chat.id, feed['url'])
    d = feedparser.parse(feed['url'])
    title = d.feed.get('title') or '-'
    desc = d.feed.get('description') or '-'
    text = 'Title: {}\n\nURL: {}\n\nDescription: {}\n\n'.format(
        title, feed['url'], desc)

    if d.entries and feed['latest']:
        latest = tuple(map(int, feed['latest'].split()))
        text += format_entries(get_old_entries(d, latest)[-5:])

    return text


def cmd_unsub(cmd: IncomingCommand) -> str:
    """Unsubscribe current chat from the given feed.
    """
    url = cmd.payload
    feed = db.get_feed(url)
    if not feed:
        return 'Unknow feed: {}'.format(url)

    if cmd.message.chat.id not in db.get_fchats(feed['url']):
        return 'This chat is not subscribed to: {}'.format(feed['url'])

    db.remove_fchat(cmd.message.chat.id, feed['url'])
    if not db.get_fchats(feed['url']):
        db.remove_feed(feed['url'])
    return 'Chat unsubscribed from: {}'.format(feed['url'])


def cmd_list(cmd: IncomingCommand) -> str:
    """List feed subscriptions for the current chat.
    """
    feeds = db.get_feeds(cmd.message.chat.id)
    text = '\n\n'.join(f['url'] for f in feeds)
    return text or 'No feed subscriptions in this chat'


# ======== Utilities ===============

def check_feeds() -> None:
    while True:
        dbot.logger.debug('Checking feeds')
        for f in db.get_feeds():
            fchats = db.get_fchats(f['url'])

            if not fchats:
                db.remove_feed(f['url'])
                continue

            d = feedparser.parse(
                f['url'], etag=f['etag'], modified=f['modified'])

            if d.get('bozo') == 1:
                db.remove_feed(f['url'])
                text = 'Feed failed and was removed: {}'.format(f['url'])
                for gid in fchats:
                    dbot.get_chat(gid).send_text(text)
                continue

            if d.entries and f['latest']:
                d.entries = get_new_entries(
                    d.entries, tuple(map(int, f['latest'].split())))
            if not d.entries:
                continue

            text = format_entries(d.entries[-50:])
            for gid in fchats:
                try:
                    dbot.get_chat(gid).send_text(text)
                except ValueError:
                    db.remove_fchat(gid)

            latest = get_latest_date(d.entries) or f['latest']
            modified = d.get('modified') or d.get('updated')
            db.update_feed(f['url'], d.get('etag'), modified, latest)
        sleep(int(getdefault('delay')))


def format_entries(entries: list) -> str:
    entries_text = []
    for e in entries:
        t = '{}:\n({})\n\n'.format(
            e.get('title') or 'NO TITLE', e.get('link') or '-')
        pub_date = e.get('published')
        if pub_date:
            t += '**{}**\n\n'.format(pub_date)
        desc = e.get('description')
        if desc:
            t += '{}\n'.format(html2text.html2text(desc))
        else:
            t += '\n\n'
        entries_text.append(t)
    return '―――――――――――――――\n\n'.join(entries_text)


def get_new_entries(entries: list, date: tuple) -> list:
    new_entries = []
    for e in entries:
        d = e.get('published_parsed') or e.get('updated_parsed')
        if d is not None and d > date:
            new_entries.append(e)
    return new_entries


def get_old_entries(entries: list, date: tuple) -> list:
    old_entries = []
    for e in entries:
        d = e.get('published_parsed') or e.get('updated_parsed')
        if d is not None and d <= date:
            old_entries.append(e)
    return old_entries


def get_latest_date(entries: list) -> Optional[str]:
    dates = []
    for e in entries:
        d = e.get('published_parsed') or e.get('updated_parsed')
        if d:
            dates.append(d)
    return ' '.join(map(str, max(dates))) if dates else None


def register_cmd(name: str, alt_name: str, func: Callable) -> None:
    try:
        dbot.commands.register(name=name, func=func)
    except ValueError:
        dbot.commands.register(name=alt_name, func=func)


def getdefault(key: str, value=None) -> str:
    val = dbot.get(key, scope=__name__)
    if val is None and value is not None:
        dbot.set(key, value, scope=__name__)
        val = value
    return val


def get_db(bot) -> DBManager:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    return DBManager(os.path.join(path, 'sqlite.db'))
