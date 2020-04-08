import time

import irc.bot
import irc.strings


class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, bridge):
        cfg = bridge.cfg
        nick = cfg.get('nick')
        server = cfg.get('host')
        port = cfg.getint('port')
        irc.bot.SingleServerIRCBot.__init__(
            self, [(server, port)], nick, nick)
        self.bridge = bridge

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        self.conn = c
        channels = self.bridge.db.get_channels()
        for channel in channels:
            c.join(channel)
            time.sleep(1)
        self.bridge.connected.set()

    def on_pubmsg(self, c, e):
        sender = e.source.split('!')[0]
        msg = e.arguments[0]
        channel = e.target
        self.bridge.irc2dc(channel, sender, msg)

    def join_channel(self, name):
        self.conn.join(name)

    def send_message(self, target, text):
        self.conn.privmsg(target, text)
