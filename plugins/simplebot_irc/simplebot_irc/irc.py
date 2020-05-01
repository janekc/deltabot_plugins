import irc.bot
import irc.strings


class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, server, port, nick, db, dbot):
        irc.bot.SingleServerIRCBot.__init__(
            self, [(server, port)], nick, nick)
        self.dbot = dbot
        self.db = db

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        channels = self.db.get_channels()
        for channel in channels:
            c.join(channel)

    def on_pubmsg(self, c, e):
        sender = e.source.split('!')[0]
        msg = e.arguments[0]
        channel = e.target
        for gid in self.db.get_cchats(channel):
            self.dbot.get_chat(gid).send_text(
                '{}[irc]:\n{}'.format(sender, msg))

    def on_notopic(self, c, e):
        chan = self.channels[e.arguments[0]]
        chan.topic = '-'

    def on_currenttopic(self, c, e):
        chan = self.channels[e.arguments[0]]
        chan.topic = e.arguments[1]

    def join_channel(self, name):
        self.connection.join(name)

    def leave_channel(self, name):
        self.connection.part(name)

    def get_topic(self, channel):
        self.connection.topic(channel)
        chan = self.channels[channel]
        if not hasattr(chan, 'topic'):
            chan.topic = '-'
        return chan.topic

    def get_members(self, channel):
        return list(self.channels[channel].users())

    def send_message(self, target, text):
        self.connection.privmsg(target, text)
