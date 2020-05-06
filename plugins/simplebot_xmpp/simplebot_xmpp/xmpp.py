# -*- coding: utf-8 -*-
from slixmpp import ClientXMPP
# from slixmpp.exceptions import IqError, IqTimeout


class XMPPBot(ClientXMPP):
    def __init__(self, jid, password, nick, db, dbot):
        ClientXMPP.__init__(self, jid, password)
        self.nick = nick
        self.db = db
        self.dbot = dbot
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)

        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0054')  # vcard-temp
        self.register_plugin('xep_0363')  # HTTP File Upload
        self.register_plugin('xep_0128')  # Service Discovery Extensions
        # self.register_plugin('xep_0071')  # XHTML-IM

    def session_start(self, event):
        self.send_presence(
            pstatus='Open source DeltaChat <--> XMPP bridge')
        self.get_roster()

        for jid in self.db.get_channels():
            self.join_muc(jid)

    def message(self, msg):
        nick = msg['mucnick']
        if nick == self.nick:
            return

        if msg['type'] == 'groupchat':
            for gid in self.db.get_cchats(msg['mucroom']):
                self.dbot.get_chat(gid).send_text(
                    '{}[xmpp]:\n{}'.format(nick, msg['body']))

    def join_channel(self, jid):
        self['xep_0045'].join_muc(jid, self.nick)

    def leave_channel(self, jid):
        self['xep_0045'].leave_muc(jid, self.nick)

    def get_members(self, jid):
        for u in self['xep_0045'].get_roster(jid):
            if u:
                yield u
