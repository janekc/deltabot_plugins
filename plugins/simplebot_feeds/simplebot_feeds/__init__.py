# -*- coding: utf-8 -*-
from threading import Thread
from time import sleep
from typing import Optional
import os

from .db import DBManager
from deltabot.hookspec import deltabot_hookimpl
import feedparser
import html2text
# typing:
from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact


version = '1.0.0'
feedparser.USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:60.0)'
feedparser.USER_AGENT += ' Gecko/20100101 Firefox/60.0'
html2text.config.WRAP_LINKS = False
dbot: DeltaBot
db: DBManager


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot, db
    dbot = bot
    db = get_db(bot)

    getdefault('delay', 60*5)
    getdefault('max_feed_count', -1)

    dbot.commands.register('/feed_sub', cmd_sub)
    dbot.commands.register('/feed_unsub', cmd_unsub)
    dbot.commands.register('/feed_list', cmd_list)


@deltabot_hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    Thread(target=check_feeds, daemon=True).start()


@deltabot_hookimpl
def deltabot_member_removed(chat: Chat, contact: Contact) -> None:
    me = dbot.self_contact
    if me == contact or len(chat.get_contacts()) <= 1:
        feeds = db.get_feeds(chat.id)
        if feeds:
            db.remove_fchat(chat.id)
            for feed in feeds:
                if not db.get_fchats(feed['url']):
                    db.remove_feed(feed['url'])


# ======== Commands ===============

def cmd_sub(command: IncomingCommand, replies: Replies) -> None:
    """Subscribe current chat to the given feed.
    """
    url = command.payload
    feed = db.get_feed(url)

    if not feed:
        max_fc = int(getdefault('max_feed_count'))
        if max_fc >= 0 and len(db.get_feeds()) >= max_fc:
            replies.add(text='Sorry, maximum number of feeds reached')
            return
        d = feedparser.parse(url)
        if d.get('bozo') == 1:
            replies.add(text='Invalid feed url: {}'.format(url))
            return
        db.add_feed(url, command.message.chat.id)
        modified = d.get('modified') or d.get('updated')
        db.update_feed(
            url, d.get('etag'), modified, get_latest_date(d.entries))
        title = d.feed.get('title') or '-'
        desc = d.feed.get('description') or '-'
        text = 'Title: {}\n\nURL: {}\n\nDescription: {}\n\n{}'.format(
            title, url, desc, format_entries(d.entries[-5:]))
        replies.add(text=text)
        return

    if command.message.chat.id in db.get_fchats(feed['url']):
        replies.add(text='Chat alredy subscribed to that feed.')
        return

    db.add_fchat(command.message.chat.id, feed['url'])
    d = feedparser.parse(feed['url'])
    title = d.feed.get('title') or '-'
    desc = d.feed.get('description') or '-'
    text = 'Title: {}\n\nURL: {}\n\nDescription: {}\n\n'.format(
        title, feed['url'], desc)

    if d.entries and feed['latest']:
        latest = tuple(map(int, feed['latest'].split()))
        text += format_entries(get_old_entries(d.entries, latest)[-5:])

    replies.add(text=text)


def cmd_unsub(command: IncomingCommand, replies: Replies) -> None:
    """Unsubscribe current chat from the given feed.
    """
    url = command.payload
    feed = db.get_feed(url)
    if not feed:
        replies.add(text='Unknow feed: {}'.format(url))
        return

    if command.message.chat.id not in db.get_fchats(feed['url']):
        replies.add(
            text='This chat is not subscribed to: {}'.format(feed['url']))
        return

    db.remove_fchat(command.message.chat.id, feed['url'])
    if not db.get_fchats(feed['url']):
        db.remove_feed(feed['url'])
    replies.add(text='Chat unsubscribed from: {}'.format(feed['url']))


def cmd_list(command: IncomingCommand, replies: Replies) -> None:
    """List feed subscriptions for the current chat.
    """
    feeds = db.get_feeds(command.message.chat.id)
    text = '\n\n'.join(f['url'] for f in feeds)
    replies.add(text=text or 'No feed subscriptions in this chat')


# ======== Utilities ===============

def check_feeds() -> None:
    while True:
        dbot.logger.debug('Checking feeds')
        for f in db.get_feeds():
            try:
                _check_feed(f)
            except Exception as err:
                dbot.logger.exception(err)
        sleep(int(getdefault('delay')))


def _check_feed(f) -> None:
    fchats = db.get_fchats(f['url'])

    if not fchats:
        db.remove_feed(f['url'])
        return

    dbot.logger.debug('Checking feed: %s', f['url'])
    d = feedparser.parse(
        f['url'], etag=f['etag'], modified=f['modified'])

    if d.get('bozo') == 1:
        return

    if d.entries and f['latest']:
        d.entries = get_new_entries(
            d.entries, tuple(map(int, f['latest'].split())))
    if not d.entries:
        return

    text = format_entries(d.entries[-50:])
    for gid in fchats:
        try:
            dbot.get_chat(gid).send_text(text)
        except ValueError:
            db.remove_fchat(gid)

    latest = get_latest_date(d.entries) or f['latest']
    modified = d.get('modified') or d.get('updated')
    db.update_feed(f['url'], d.get('etag'), modified, latest)


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
