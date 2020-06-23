import irc.bot
import irc.strings
# typing
from .database import DBManager
from deltabot import DeltaBot
# ======


class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, server: str, port: int, nick: str, db: DBManager,
                 dbot: DeltaBot):
        irc.bot.SingleServerIRCBot.__init__(
            self, [(server, port)], nick, nick)
        self.dbot = dbot
        self.db = db

    def on_nicknameinuse(self, c, e) -> None:
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e) -> None:
        channels = self.db.get_channels()
        for channel in channels:
            c.join(channel)

    def on_pubmsg(self, c, e) -> None:
        sender = e.source.split('!')[0]
        msg = e.arguments[0]
        channel = e.target
        for gid in self.db.get_cchats(channel):
            self.dbot.get_chat(gid).send_text(
                '{}[irc]:\n{}'.format(sender, msg))

    def on_notopic(self, c, e) -> None:
        chan = self.channels[e.arguments[0]]
        chan.topic = '-'

    def on_currenttopic(self, c, e) -> None:
        chan = self.channels[e.arguments[0]]
        chan.topic = e.arguments[1]

    def join_channel(self, name: str) -> None:
        self.connection.join(name)

    def leave_channel(self, name: str) -> None:
        self.connection.part(name)

    def get_topic(self, channel: str) -> str:
        self.connection.topic(channel)
        chan = self.channels[channel]
        if not hasattr(chan, 'topic'):
            chan.topic = '-'
        return chan.topic

    def get_members(self, channel: str) -> list:
        return list(self.channels[channel].users())

    def send_message(self, target: str, text: str) -> None:
        self.connection.privmsg(target, text)
