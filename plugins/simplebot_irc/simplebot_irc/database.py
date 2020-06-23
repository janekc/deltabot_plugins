import sqlite3
# typing
from typing import Optional, Generator
# ======


class DBManager:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute(
                '''CREATE TABLE IF NOT EXISTS channels
                (id TEXT PRIMARY KEY)''')
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
                (channel TEXT PRIMARY KEY)''')

    def execute(self, statement: str, args=()) -> sqlite3.Cursor:
        return self.db.execute(statement, args)

    def commit(self, statement: str, args=()) -> sqlite3.Cursor:
        with self.db:
            return self.db.execute(statement, args)

    def close(self) -> None:
        self.db.close()

    # ==== channels =====

    def channel_exists(self, name: str) -> bool:
        name = name.lower()
        r = self.execute(
            'SELECT * FROM channels WHERE id=?', (name,)).fetchone()
        return r is not None

    def get_channel_by_gid(self, gid: int) -> Optional[str]:
        r = self.db.execute(
            'SELECT channel from cchats WHERE id=?', (gid,)).fetchone()
        return r and r[0]

    def get_channels(self) -> Generator:
        for r in self.db.execute('SELECT id FROM channels'):
            yield r[0]

    def add_channel(self, name: str) -> None:
        self.commit('INSERT INTO channels VALUES (?)', (name.lower(),))

    def remove_channel(self, name: str) -> None:
        self.commit('DELETE FROM channels WHERE id=?', (name.lower(),))

    # ===== cchats =======

    def get_cchats(self, channel: str) -> Generator:
        for r in self.db.execute('SELECT id FROM cchats WHERE channel=?',
                                 (channel.lower(),)):
            yield r[0]

    def add_cchat(self, gid: int, channel: str) -> None:
        self.commit('INSERT INTO cchats VALUES (?,?)', (gid, channel))

    def remove_cchat(self, gid: int) -> None:
        self.commit('DELETE FROM cchats WHERE id=?', (gid,))

    # ===== nicks =======

    def get_nick(self, addr: str) -> str:
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

    def set_nick(self, addr: str, nick: str) -> None:
        self.commit('REPLACE INTO nicks VALUES (?,?)', (addr, nick))

    def get_addr(self, nick: str) -> str:
        r = self.execute(
            'SELECT addr FROM nicks WHERE nick=?', (nick,)).fetchone()
        return r and r[0]

    # ===== whitelist =======

    def is_whitelisted(self, name: str) -> bool:
        rows = self.execute('SELECT channel FROM whitelist').fetchall()
        if not rows:
            return True
        for r in rows:
            if r[0] == name:
                return True
        return False

    def add_to_whitelist(self, name: str) -> None:
        self.commit(
            'INSERT INTO whitelist VALUES (?)', (name,))

    def remove_from_whitelist(self, name: str) -> None:
        self.commit(
            'DELETE FROM whitelist WHERE id=?', (name,))
