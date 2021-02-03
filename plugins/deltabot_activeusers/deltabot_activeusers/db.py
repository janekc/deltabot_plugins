import os
import sqlite3


class DBManager:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._execute('''CREATE TABLE IF NOT EXISTS users
                        (username TEXT PRIMARY KEY,
                         date TEXT)''')

    def _execute(self, statement, args=()):
        with self.db:
            return self.db.execute(statement, args)

    def store(self, key, value):
        old_val = self.geta(key)
        if value is not None:
            self._execute('REPLACE INTO users VALUES (?,?)', (key, value))
        else:
            self._execute('DELETE FROM users WHERE username=?', (key, ))
        return old_val

    def geta(self, key):
        row = self._execute(
            'SELECT * FROM users WHERE username=?',
            (key,),
        ).fetchone()
        return row['date'] if row else None

    def deltabot_list_users(self):
        rows = self._execute('SELECT * FROM users').fetchall()
        return [(row['username'], row["date"]) for row in rows]

    def deltabot_shutdown(self, bot):
        self.db.close()
    