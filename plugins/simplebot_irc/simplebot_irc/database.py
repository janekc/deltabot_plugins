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

    def del_user(self, addr):
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

    def get_channels(self):
        for r in self.db.execute('SELECT name FROM channels'):
            yield r[0]

    def get_nick(self, addr):
        r = self.execute(
            'SELECT nick from nicks WHERE addr=?', (addr,)).fetchone()
        if r:
            return r[0]
        else:
            i = 1
            while True:
                nick = 'User{}'.format(i)
                r = self.execute(
                    'SELECT nick FROM nicks WHERE nick=?',
                    (nick,)).fetchone()
                if not r:
                    self.commit(
                        'INSERT OR REPLACE INTO nicks VALUES (?,?)',
                        (addr, nick))
                    break
                i += 1
            return nick

    def execute(self, statement, args=()):
        return self.db.execute(statement, args)

    def commit(self, statement, args=()):
        with self.db:
            return self.db.execute(statement, args)

    def close(self):
        self.db.close()
