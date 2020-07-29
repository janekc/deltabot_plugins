# -*- coding: utf-8 -*-
from enum import Enum
from threading import Thread
from typing import Generator
import time
import os
import tempfile

from .db import DBManager
from deltabot.hookspec import deltabot_hookimpl
from bs4 import BeautifulSoup
from pydub import AudioSegment
from html2text import html2text
import mastodon
import requests
# typing:
from deltabot import DeltaBot
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand
from deltachat import Chat, Contact, Message


class Visibility(str, Enum):
    DIRECT = 'direct'  # visible only to mentioned users
    PRIVATE = 'private'  # visible only to followers
    UNLISTED = 'unlisted'  # public but not appear on the public timeline
    PUBLIC = 'public'  # post will be public


version = '1.0.0'
MASTODON_LOGO = os.path.join(
    os.path.dirname(__file__), 'mastodon-logo.png')
v2emoji = {Visibility.DIRECT: '✉', Visibility.PRIVATE: '🔒',
           Visibility.UNLISTED: '🔓', Visibility.PUBLIC: '🌎'}
TOOT_SEP = '\n\n―――――――――――――――\n\n'
dbot: DeltaBot
db: DBManager


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global dbot
    dbot = bot

    getdefault('delay', '30')
    getdefault('max_users', '-1')
    getdefault('max_users_instance', '-1')

    bot.filters.register(name=__name__, func=filter_messages)

    dbot.commands.register('/masto_login', cmd_login)
    dbot.commands.register('/masto_logout', cmd_logout)
    dbot.commands.register('/masto_account', cmd_account)
    dbot.commands.register('/masto_dm', cmd_dm)
    dbot.commands.register('/masto_reply', cmd_reply)
    dbot.commands.register('/masto_star', cmd_star)
    dbot.commands.register('/masto_boost', cmd_boost)
    dbot.commands.register('/masto_context', cmd_context)
    dbot.commands.register('/masto_follow', cmd_follow)
    dbot.commands.register('/masto_unfollow', cmd_unfollow)
    dbot.commands.register('/masto_whois', cmd_whois)
    dbot.commands.register('/masto_local', cmd_local)
    dbot.commands.register('/masto_public', cmd_public)
    dbot.commands.register('/masto_tag', cmd_tag)


@deltabot_hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    global db
    db = get_db(bot)

    Thread(target=listen_to_mastodon, daemon=True).start()


@deltabot_hookimpl
def deltabot_member_removed(chat: Chat, contact: Contact) -> None:
    me = dbot.self_contact
    if me == contact or len(chat.get_contacts()) <= 1:
        acc = db.get_account(chat.id)
        if acc:
            if chat.id in (acc['toots'], acc['notif']):
                db.remove_account(acc['id'])
            else:
                db.remove_pchat(chat.id)


# ======== Filters ===============

def filter_messages(message: Message, replies: Replies) -> None:
    """Process messages sent to a Mastodon chat.
    """
    acc = db.get_account_by_home(message.chat.id)
    if acc:
        toot(get_session(acc), message.text, message.filename)
        return

    pchat = db.get_pchat(message.chat.id)
    if pchat:
        acc = db.get_account_by_id(pchat['account'])
        text = '@{} {}'.format(pchat['contact'], message.text)
        toot(get_session(acc), text, visibility=Visibility.DIRECT)


# ======== Commands ===============

def cmd_login(command: IncomingCommand, replies: Replies) -> None:
    """Login on Mastodon. Example: /masto_login mastodon.social me@example.com myPassw0rd
    """
    api_url, email, passwd = command.payload.split(maxsplit=2)
    api_url = normalize_url(api_url)

    max = int(getdefault('max_users'))
    if max >= 0 and len(db.get_accounts()) >= max:
        replies.add(text='No more accounts allowed.')
        return
    max = int(getdefault('max_users_instance'))
    if max >= 0 and len(db.get_accounts(url=api_url)) >= max:
        replies.add(
            text='No more accounts allowed from {}'.format(api_url))
        return

    m = mastodon.Mastodon(api_base_url=api_url, ratelimit_method='throw')
    m.log_in(email, passwd)
    uname = m.me().acct.lower()

    old_user = db.get_account_by_user(uname, api_url)
    if old_user:
        replies.add(text='Account already in use')
        return

    n = m.notifications(limit=1)
    last_notif = n[0].id if n else None
    n = m.timeline_home(limit=1)
    last_home = n[0].id if n else None

    addr = command.message.get_sender_contact().addr
    url = rmprefix(api_url, 'https://')
    hgroup = command.bot.create_group(
        'Home ({}@{})'.format(uname, url), [addr])
    ngroup = command.bot.create_group(
        'Notifications ({}@{})'.format(uname, url), [addr])

    db.add_account(email, passwd, api_url, uname, addr, hgroup.id,
                   ngroup.id, last_home, last_notif)

    hgroup.set_profile_image(MASTODON_LOGO)
    ngroup.set_profile_image(MASTODON_LOGO)
    text = 'Messages sent here will be tooted to {}'.format(api_url)
    replies.add(text=text, chat=hgroup)
    text = 'Here you will receive notifications from {}'.format(api_url)
    replies.add(text=text, chat=ngroup)


def cmd_logout(command: IncomingCommand, replies: Replies) -> None:
    """Logout from Mastodon.
    """
    if command.payload:
        acc = db.get_account_by_id(int(command.payload))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
    else:
        acc = db.get_account(command.message.chat.id)

    if acc:
        db.remove_account(acc['id'])
        chat = command.bot.get_chat(command.message.get_sender_contact())
        replies.add(
            text='You have logged out from: '+acc['api_url'], chat=chat)
    else:
        replies.add(text='Unknow account')


def cmd_account(command: IncomingCommand, replies: Replies) -> None:
    """Show your Mastodon accounts.
    """
    accs = db.get_accounts(addr=command.message.get_sender_contact().addr)
    if not accs:
        replies.add(text='Empty list')
        return
    text = ''
    for acc in accs:
        url = rmprefix(acc['api_url'], 'https://')
        text += '{}@{}: /masto_logout_{}\n\n'.format(
            acc['accname'], url, acc['id'])
    replies.add(text=text)


def cmd_dm(command: IncomingCommand, replies: Replies) -> None:
    """Start a private chat with the given Mastodon user.
    """
    if len(command.args) == 2:
        acc = db.get_account_by_id(int(command.args[0]))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
        command.payload = command.args[1]
    else:
        acc = db.get_account(command.message.chat.id)
    if not command.payload:
        replies.add(text='Wrong Syntax')
        return
    if not acc:
        replies.add(text='You must send that command in you Mastodon chats')
        return

    command.payload = command.payload.lstrip('@').lower()

    pv = db.get_pchat_by_contact(acc['id'], command.payload)
    if pv:
        chat = command.bot.get_chat(pv['id'])
        replies.add(
            text='Chat already exists, send messages here', chat=chat)
    else:
        m = get_session(acc)
        contact = m.account_search(command.payload, limit=1)
        accnames = (command.payload, command.payload.split('@')[0])
        if contact and contact[0].acct.lower() in accnames:
            title = '🇲 {} ({})'.format(
                command.payload, rmprefix(acc['api_url'], 'https://'))
            g = command.bot.create_group(title, [acc['addr']])
            db.add_pchat(g.id, command.payload, acc['id'])

            r = requests.get(contact[0].avatar_static)
            with tempfile.NamedTemporaryFile(suffix='.jpg') as fp:
                fp.write(r.content)
                g.set_profile_image(fp.name)
            replies.add(
                text='Private chat with: ' + command.payload, chat=g)
        else:
            replies.add(text='Account not found: ' + command.payload)


def cmd_reply(command: IncomingCommand, replies: Replies) -> None:
    """Reply to a toot with the given id.
    """
    acc_id, toot_id, text = command.payload.split(maxsplit=2)
    addr = command.message.get_sender_contact().addr

    acc = db.get_account_by_id(acc_id)
    if not acc or acc['addr'] != addr:
        replies.add(text='Invalid toot or account id')
        return

    toot(acc, text=text, in_reply_to=toot_id)


def cmd_star(command: IncomingCommand, replies: Replies) -> None:
    """Mark as favourite the toot with the given id.
    """
    acc_id, toot_id = command.args
    addr = command.message.get_sender_contact().addr

    acc = db.get_account_by_id(acc_id)
    if not acc or acc['addr'] != addr:
        replies.add(text='Invalid toot or account id')
        return

    m = get_session(acc)
    m.status_favourite(toot_id)


def cmd_boost(command: IncomingCommand, replies: Replies) -> None:
    """Boost the toot with the given id.
    """
    acc_id, toot_id = command.args
    addr = command.message.get_sender_contact().addr

    acc = db.get_account_by_id(acc_id)
    if not acc or acc['addr'] != addr:
        replies.add(text='Invalid toot or account id')
        return

    m = get_session(acc)
    m.status_reblog(toot_id)


def cmd_context(command: IncomingCommand, replies: Replies) -> None:
    """Get the context of the toot with the given id.
    """
    acc_id, toot_id = command.args
    addr = command.message.get_sender_contact().addr

    acc = db.get_account_by_id(acc_id)
    if not acc or acc['addr'] != addr:
        replies.add(text='Invalid toot or account id')
        return

    m = get_session(acc)
    toots = m.status_context(toot_id)['ancestors']
    if toots:
        replies.add(text=TOOT_SEP.join(
            toots2text(toots[-3:], acc['id'])))
    else:
        replies.add(text='Nothing found')


def cmd_follow(command: IncomingCommand, replies: Replies) -> None:
    """Follow the user with the given id.
    """
    if len(command.args) == 2:
        acc = db.get_account_by_id(int(command.args[0]))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
        command.payload = command.args[1]
    else:
        acc = db.get_account(command.message.chat.id)
    if not command.payload:
        replies.add(text='Wrong Syntax')
        return
    if not acc:
        replies.add(
            text='You must send that command in you Mastodon chats')
        return

    m = get_session(acc)
    if command.payload.isdigit():
        user_id = command.payload
    else:
        user_id = get_user(m, command.payload)
        if user_id is None:
            replies.add(text='Invalid user')
            return
    m.account_follow(user_id)
    replies.add(text='User followed')


def cmd_unfollow(command: IncomingCommand, replies: Replies) -> None:
    """Unfollow the user with the given id.
    """
    if len(command.args) == 2:
        acc = db.get_account_by_id(int(command.args[0]))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
        command.payload = command.args[1]
    else:
        acc = db.get_account(command.message.chat.id)
    if not command.payload:
        replies.add(text='Wrong Syntax')
        return
    if not acc:
        replies.add(
            text='You must send that command in you Mastodon chats')
        return

    m = get_session(acc)
    if command.payload.isdigit():
        user_id = command.payload
    else:
        user_id = get_user(m, command.payload)
        if user_id is None:
            replies.add(text='Invalid user')
            return
    m.account_unfollow(user_id)
    replies.add(text='User unfollowed')


def cmd_whois(command: IncomingCommand, replies: Replies) -> None:
    """See the profile of the given user.
    """
    if len(command.args) == 2:
        acc = db.get_account_by_id(int(command.args[0]))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
        command.payload = command.args[1]
    else:
        acc = db.get_account(command.message.chat.id)
    if not command.payload:
        replies.add(text='Wrong Syntax')
        return
    if not acc:
        replies.add(
            text='You must send that command in you Mastodon chats')
        return

    m = get_session(acc)
    user = get_user(m, command.payload)
    if user is None:
        replies.add(text='Invalid user')
        return

    toots = m.account_statuses(user.id)
    text = '{} (@{}):\n\n'.format(user.display_name, user.acct)
    fields = ''
    for f in user.fields:
        fields += '{}: {}\n'.format(html2text(f.name), html2text(f.value))
    if fields:
        text += fields+'\n\n'
    text += html2text(user.note)
    text += '\n\nToots: {}\nFollowing: {}\nFollowers: {}\n\n'.format(
        user.statuses_count, user.following_count, user.followers_count)
    text += TOOT_SEP.join(toots2text(toots, acc['id']))
    replies.add(text=text)


def cmd_local(command: IncomingCommand, replies: Replies) -> None:
    """Get latest entries from the local timeline.
    """
    if command.payload:
        acc = db.get_account_by_id(int(command.payload))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
    else:
        acc = db.get_account(command.message.chat.id)
    if not acc:
        replies.add(
            text='You must send that command in you Mastodon chats')
        return

    m = get_session(acc)
    toots = m.timeline_local()
    if toots:
        replies.add(text=TOOT_SEP.join(toots2text(toots, acc['id'])))
    else:
        replies.add(text='Nothing found')


def cmd_public(command: IncomingCommand, replies: Replies) -> None:
    """Get latest entries from the public timeline.
    """
    if command.payload:
        acc = db.get_account_by_id(int(command.payload))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
    else:
        acc = db.get_account(command.message.chat.id)
    if not acc:
        replies.add(
            text='You must send that command in you Mastodon chats')
        return

    m = get_session(acc)
    toots = m.timeline_public()
    if toots:
        replies.add(text=TOOT_SEP.join(toots2text(toots, acc['id'])))
    else:
        replies.add(text='Nothing found')


def cmd_tag(command: IncomingCommand, replies: Replies) -> None:
    """Get latest entries with the given tag.
    """
    if len(command.args) == 2:
        acc = db.get_account_by_id(int(command.args[0]))
        if acc and acc['addr'] != command.message.get_sender_contact().addr:
            replies.add(text='That is not your account')
            return
        command.payload = command.args[1]
    else:
        acc = db.get_account(command.message.chat.id)
    command.payload = command.payload.lstrip('#')
    if not command.payload:
        replies.add(text='Wrong Syntax')
        return
    if not acc:
        replies.add(
            text='You must send that command in you Mastodon chats')
        return

    m = get_session(acc)
    toots = m.timeline_hashtag(command.payload)
    if toots:
        replies.add(text=TOOT_SEP.join(toots2text(toots, acc['id'])))
    else:
        replies.add(text='Nothing found')


# ======== Utilities ===============

def get_session(acc) -> mastodon.Mastodon:
    m = mastodon.Mastodon(api_base_url=acc['api_url'],
                          ratelimit_method='throw')
    m.log_in(acc['email'], acc['password'])
    return m


def get_user(m, user_id):
    user = None
    if user_id.isdigit():
        user = m.account(user_id)
    else:
        user_id = user_id.lstrip('@').lower()
        ids = (user_id, user_id.split('@')[0])
        for a in m.account_search(user_id):
            if a.acct.lower() in ids:
                user = a
                break
    return user


def toots2text(toots: list, acc_id: int,
               notifications: bool = False) -> Generator:
    for t in reversed(toots):
        if notifications:
            if t.type == 'reblog':
                text = '🔁 {} (@{}) boosted your toot:\n\n'.format(
                    t.account.display_name, t.account.acct)
            elif t.type == 'favourite':
                text = '⭐ {} (@{}) favorited your toot:\n\n'.format(
                    t.account.display_name, t.account.acct)
            elif t.type == 'follow':
                yield '👤 {} (@{}) followed you.'.format(
                    t.account.display_name, t.account.acct)
                continue
            elif t.type != 'mention':
                continue
            is_mention = t.type == 'mention'
            t = t.status
        elif t.reblog:
            a = t.reblog.account
            text = '{} (@{}):\n🔁 {} (@{})\n\n'.format(
                a.display_name, a.acct, t.account.display_name, t.account.acct)
        else:
            text = '{} (@{}):\n\n'.format(
                t.account.display_name, t.account.acct)

        media_urls = '\n'.join(
            media.url for media in t.media_attachments)
        if media_urls:
            text += media_urls + '\n\n'

        soup = BeautifulSoup(
            t.content, 'html.parser')
        if t.mentions:
            accts = {e.url: '@' + e.acct
                     for e in t.mentions}
            for a in soup('a', class_='u-url'):
                name = accts.get(a['href'])
                if name:
                    a.string = name
        for br in soup('br'):
            br.replace_with('\n')
        for p in soup('p'):
            p.replace_with(p.get_text()+'\n\n')
        text += soup.get_text()

        text += '\n\nStatus: {}\n'.format(v2emoji[t.visibility])
        if not notifications or is_mention:
            text += '↩️ /masto_reply_{}_{}\n'.format(acc_id, t.id)
            text += '⭐ /masto_star_{}_{}\n'.format(acc_id, t.id)
            if t.visibility == Visibility.PUBLIC:
                text += '🔄 /masto_boost_{}_{}\n'.format(acc_id, t.id)
            text += '⏫ /masto_context_{}_{}\n'.format(acc_id, t.id)

        yield text


def toot(masto: mastodon.Mastodon, text: str = None, filename: str = None,
         visibility: str = None, in_reply_to: str = None) -> None:
    if filename:
        if filename.endswith('.aac'):
            aac_file = AudioSegment.from_file(filename, 'aac')
            filename = filename[:-4] + '.mp3'
            aac_file.export(filename, format='mp3')
        media = [masto.media_post(filename).id]
        if in_reply_to:
            masto.status_reply(masto.status(in_reply_to), text,
                               media_ids=media, visibility=visibility)
        else:
            masto.status_post(
                text, media_ids=media, visibility=visibility)
    elif text:
        if in_reply_to:
            masto.status_reply(
                masto.status(in_reply_to), text, visibility=visibility)
        else:
            masto.status_post(text, visibility=visibility)


def normalize_url(url: str) -> str:
    if url.startswith('http://'):
        url = 'https://' + url[4:]
    elif not url.startswith('https://'):
        url = 'https://' + url
    return url.rstrip('/')


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


def rmprefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]


def _check_notifications(acc, m: mastodon.Mastodon) -> None:
    max_id = None
    dmsgs = []
    mentions = []
    while True:
        ment = m.notifications(
            max_id=max_id, since_id=acc['last_notif'])
        if not ment:
            break
        if max_id is None:
            db.set_last_notif(acc['id'], ment[0].id)
        max_id = ment[-1]
        for mention in ment:
            if mention.type == 'mention' and mention.status.visibility == Visibility.DIRECT and len(mention.status.mentions) == 1:
                dmsgs.append(mention.status)
            mentions.append(mention)
    for dm in reversed(dmsgs):
        acct = dm.account.acct
        text = '{} (@{}):\n\n'.format(
            dm.account.display_name, acct)

        media_urls = '\n'.join(
            media.url for media in dm.media_attachments)
        if media_urls:
            text += media_urls + '\n\n'

        soup = BeautifulSoup(dm.content, 'html.parser')
        accts = {e.url: '@'+e.acct
                 for e in dm.mentions}
        for a in soup('a', class_='u-url'):
            name = accts.get(a['href'])
            if name:
                a.string = name
        for br in soup('br'):
            br.replace_with('\n')
        for p in soup('p'):
            p.replace_with(p.get_text()+'\n\n')
        text += soup.get_text()
        text += '\n\n⭐ /masto_star_{}_{}\n'.format(
            acc['id'], dm.id)

        pv = db.get_pchat_by_contact(acc['id'], acct)
        if pv:
            g = dbot.get_chat(pv['id'])
            if g is None:
                db.remove_pchat(pv['id'])
            else:
                g.send_text(text)
        else:
            url = rmprefix(acc['api_url'], 'https://')
            g = dbot.create_group(
                '🇲 {} ({})'.format(acct, url), [acc['addr']])
            db.add_pchat(g.id, acct, acc['id'])

            r = requests.get(dm.account.avatar_static)
            with tempfile.NamedTemporaryFile(suffix='.jpg') as fp:
                fp.write(r.content)
                g.set_profile_image(fp.name)

            g.send_text(text)

    if mentions:
        dbot.get_chat(acc['notif']).send_text(TOOT_SEP.join(
            toots2text(mentions, acc['id'], True)))


def _check_home(acc, m: mastodon.Mastodon) -> None:
    max_id = None
    toots: list = []
    while True:
        ts = m.timeline_home(max_id=max_id, since_id=acc['last_home'])
        if not toots:
            break
        if max_id is None:
            db.set_last_home(acc['id'], ts[0].id)
        max_id = ts[-1]
        toots.extend(ts)
    if toots:
        dbot.get_chat(acc['home']).send_text(TOOT_SEP.join(
            toots2text(toots, acc['id'])))


def listen_to_mastodon() -> None:
    while True:
        dbot.logger.info('Checking Mastodon')
        for acc in db.get_accounts():
            try:
                m = get_session(acc)
                _check_notifications(acc, m)
                _check_home(acc, m)
            except mastodon.MastodonUnauthorizedError:
                db.remove_account(acc['id'])
                dbot.get_chat(acc['addr']).send_text(
                    'You have logged out from: ' + acc['api_url'])
            except Exception as ex:
                dbot.logger.exception(ex)
            time.sleep(0.5)
        time.sleep(int(getdefault('delay')))
