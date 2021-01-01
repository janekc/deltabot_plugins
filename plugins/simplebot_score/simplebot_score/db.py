
import sqlite3


class DBManager:
    def __init__(self, db_path: str) -> None:
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute(
                '''CREATE TABLE IF NOT EXISTS scores
                (addr TEXT PRIMARY KEY,
                score INTEGER NOT NULL DEFAULT 0)''')

    def get_score(self, addr: str) -> int:
        row = self.db.execute(
            'SELECT score FROM scores WHERE addr=?', (addr,)).fetchone()
        return row[0] if row else 0

    def set_score(self, addr: str, score: int) -> None:
        with self.db:
            self.db.execute(
                'REPLACE INTO score VALUES (?,?)', (addr, score))
