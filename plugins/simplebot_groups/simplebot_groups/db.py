from enum import IntEnum
from typing import Optional, List
import sqlite3


class Status(IntEnum):
    PRIVATE = 0
    PUBLIC = 1


class DBManager:
    def __init__(self, db_path: str) -> None:
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.execute(
            '''CREATE TABLE IF NOT EXISTS nicks
            (addr TEXT PRIMARY KEY,
            nick TEXT UNIQUE NOT NULL)''')
        self.execute(
            '''CREATE TABLE IF NOT EXISTS groups
            (id INTEGER PRIMARY KEY,
            pid TEXT NOT NULL,
            topic TEXT,
            status INTEGER)''')
        self.execute(
            '''CREATE TABLE IF NOT EXISTS mgroups
            (id INTEGER PRIMARY KEY,
            pid TEXT NOT NULL,
            name TEXT NOT NULL,
            topic TEXT,
            status INTEGER NOT NULL)''')
        self.execute(
            '''CREATE TABLE IF NOT EXISTS mg_images
            (mgroup INTEGER PRIMARY KEY REFERENCES mgroups(id),
            image BLOB NOT NULL,
            extension TEXT NOT NULL)''')
        self.execute(
            '''CREATE TABLE IF NOT EXISTS mchats
            (id INTEGER PRIMARY KEY,
            mgroup INTEGER NOT NULL REFERENCES mgroups(id))''')
        self.execute(
            '''CREATE TABLE IF NOT EXISTS channels
            (id INTEGER PRIMARY KEY,
            pid TEXT NOT NULL,
            name TEXT NOT NULL,
            topic TEXT,
            status INTEGER NOT NULL,
            admin INTEGER NOT NULL)''')
        self.execute(
            '''CREATE TABLE IF NOT EXISTS channel_images
            (channel INTEGER PRIMARY KEY REFERENCES channels(id),
            image BLOB NOT NULL,
            extension TEXT NOT NULL)''')
        self.execute(
            '''CREATE TABLE IF NOT EXISTS cchats
            (id INTEGER PRIMARY KEY,
            channel INTEGER NOT NULL REFERENCES channels(id))''')

    def execute(self, statement: str, args=()) -> sqlite3.Cursor:
        return self.db.execute(statement, args)

    def commit(self, statement: str, args=()) -> sqlite3.Cursor:
        with self.db:
            return self.db.execute(statement, args)

    def close(self) -> None:
        self.db.close()

    # ==== nicks =====

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

    def get_addr(self, nick: str) -> Optional[str]:
        r = self.execute(
            'SELECT addr FROM nicks WHERE nick=?', (nick,)).fetchone()
        return r and r[0]

    # ==== groups =====

    def add_group(self, gid: int, pid: str, topic: Optional[str],
                  status: Status) -> None:
        self.commit('INSERT INTO groups VALUES (?,?,?,?)',
                    (gid, pid, topic, status))

    def remove_group(self, gid: int) -> None:
        self.commit('DELETE FROM groups WHERE id=?', (gid,))

    def get_group(self, gid: int) -> Optional[sqlite3.Row]:
        return self.execute(
            'SELECT * FROM groups WHERE id=?', (gid,)).fetchone()

    def get_groups(self, status: Status) -> List[sqlite3.Row]:
        return self.execute(
            'SELECT * FROM groups WHERE status=?', (status,)).fetchall()

    def set_group_topic(self, gid: int, topic: str) -> None:
        self.commit(
            'UPDATE groups SET topic=? WHERE id=?', (topic, gid))

    # ==== mega groups =====

    def add_mgroup(self, pid: str, name: str, topic: Optional[str],
                   status: Status) -> int:
        return self.commit('INSERT INTO mgroups VALUES(?,?,?,?,?)',
                           (None, pid, name, topic, status)).lastrowid

    def remove_mgroup(self, mgid: int) -> None:
        self.commit('DELETE FROM mg_images WHERE mgroup=?', (mgid,))
        self.commit('DELETE FROM mchats WHERE mgroup=?', (mgid,))
        self.commit('DELETE FROM mgroups WHERE id=?', (mgid,))

    def get_mgroup_by_id(self, mgid: int) -> Optional[sqlite3.Row]:
        return self.execute(
            'SELECT * FROM mgroups WHERE id=?', (mgid,)).fetchone()

    def get_mgroup(self, gid: int) -> Optional[sqlite3.Row]:
        r = self.execute(
            'SELECT mgroup FROM mchats WHERE id=?', (gid,)).fetchone()
        return r and self.execute(
            'SELECT * FROM mgroups WHERE id=?', (r[0],)).fetchone()

    def get_mgroups(self, status: Status) -> List[sqlite3.Row]:
        return self.execute(
            'SELECT * FROM mgroups WHERE status=?', (status,)).fetchall()

    def set_mgroup_topic(self, mgid: int, topic: str) -> None:
        self.commit(
            'UPDATE mgroups SET topic=? WHERE id=?', (topic, mgid))

    def add_mchat(self, gid: int, mgid: int) -> None:
        self.commit('INSERT INTO mchats VALUES (?,?)', (gid, mgid))

    def remove_mchat(self, gid: int) -> None:
        self.commit('DELETE FROM mchats WHERE id=?', (gid,))

    def get_mchats(self, mgid: int) -> List[int]:
        rows = self.execute('SELECT id FROM mchats WHERE mgroup=?', (mgid,))
        return [r[0] for r in rows]

    # ==== channels =====

    def add_channel(self, pid: str, name: str, topic: Optional[str],
                    admin: int, status: Status) -> None:
        self.commit('INSERT INTO channels VALUES (?,?,?,?,?,?)',
                    (None, pid, name, topic, status, admin))

    def remove_channel(self, cgid: int) -> None:
        self.commit('DELETE FROM channel_images WHERE channel=?', (cgid,))
        self.commit('DELETE FROM cchats WHERE channel=?', (cgid,))
        self.commit('DELETE FROM channels WHERE id=?', (cgid,))

    def get_channel(self, gid: int) -> Optional[sqlite3.Row]:
        r = self.execute(
            'SELECT channel FROM cchats WHERE id=?', (gid,)).fetchone()
        if r:
            return self.execute(
                'SELECT * FROM channels WHERE id=?', (r[0],)).fetchone()
        return self.execute(
            'SELECT * FROM channels WHERE admin=?', (gid,)).fetchone()

    def get_channel_by_id(self, cgid: int) -> Optional[sqlite3.Row]:
        return self.execute(
            'SELECT * FROM channels WHERE id=?', (cgid,)).fetchone()

    def get_channel_by_name(self, name: str) -> Optional[sqlite3.Row]:
        return self.execute(
            'SELECT * FROM channels WHERE name=?', (name,)).fetchone()

    def get_channels(self, status: Status) -> List[sqlite3.Row]:
        return self.execute(
            'SELECT * FROM channels WHERE status=?', (status,)).fetchall()

    def set_channel_topic(self, cgid: int, topic: str) -> None:
        self.commit(
            'UPDATE channels SET topic=? WHERE id=?', (topic, cgid))

    def add_cchat(self, gid: int, cgid: int) -> None:
        self.commit('INSERT INTO cchats VALUES (?,?)', (gid, cgid))

    def remove_cchat(self, gid: int) -> None:
        self.commit('DELETE FROM cchats WHERE id=?', (gid,))

    def get_cchats(self, cgid: int) -> List[int]:
        rows = self.execute('SELECT id FROM cchats WHERE channel=?', (cgid,))
        return [r[0] for r in rows]
