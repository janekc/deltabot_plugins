import sqlite3


class DBManager:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute(
                '''CREATE TABLE IF NOT EXISTS channels
                (name TEXT PRIMARY KEY)''')
            self.db.execute(
                '''CREATE TABLE IF NOT EXISTS cchats
                (id INTEGER PRIMARY KEY,
                channel TEXT NOT NULL)''')
            self.db.execute(
                '''CREATE TABLE IF NOT EXISTS nicks
                (addr TEXT PRIMARY KEY,
                nick TEXT NOT NULL)''')
            self.db.execute(
                '''CREATE TABLE IF NOT EXISTS whitelist
                (addr TEXT PRIMARY KEY)''')

    def add_user(self, addr):
        self.commit(
            'INSERT INTO whitelist VALUES (?)', (addr,))

    def remove_user(self, addr):
        self.commit(
            'DELETE FROM whitelist WHERE addr=?', (addr,))

    def is_whitelisted(self, addr):
        rows = self.execute('SELECT addr FROM whitelist').fetchall()
        if not rows:
            return True
        for r in rows:
            if r[0] == addr:
                return True
        return False

    def channel_exists(self, name):
        name = name.lower()
        r = self.execute(
            'SELECT name FROM channels WHERE name=?', (name,)).fetchone()
        return r is not None

    def add_channel(self, name):
        self.commit('INSERT INTO channels VALUES (?)', (name.lower(),))

    def remove_channel(self, name):
        self.commit('DELETE FROM channels WHERE name=?', (name.lower(),))

    def get_channel_by_gid(self, gid):
        r = self.db.execute(
            'SELECT channel from cchats WHERE id=?', (gid,)).fetchone()
        return r and r[0]

    def get_channels(self):
        for r in self.db.execute('SELECT name FROM channels'):
            yield r[0]

    def get_cchats(self, channel):
        for r in self.db.execute('SELECT id FROM cchats WHERE channel=?',
                                 (channel.lower(),)).fetchall():
            yield r[0]

    def add_cchat(self, gid, channel):
        self.commit('INSERT INTO cchats VALUES (?,?)', (gid, channel))

    def remove_cchat(self, gid):
        self.commit('DELETE FROM cchats WHERE id=?', (gid,))

    def get_addr(self, nick):
        r = self.execute(
            'SELECT addr FROM nicks WHERE nick=?', (nick,)).fetchone()
        return r and r[0]

    def get_nick(self, addr):
        r = self.execute(
            'SELECT nick from nicks WHERE addr=?', (addr,)).fetchone()
        if r:
            return r[0]
        else:
            i = 1
            while True:
                nick = 'User{}'.format(i)
                if not self.get_addr(nick):
                    self.set_nick(addr, nick)
                    break
                i += 1
            return nick

    def set_nick(self, addr, nick):
        self.commit('REPLACE INTO nicks VALUES (?,?)', (addr, nick))

    def execute(self, statement, args=()):
        return self.db.execute(statement, args)

    def commit(self, statement, args=()):
        with self.db:
            return self.db.execute(statement, args)

    def close(self):
        self.db.close()
