# -*- coding: utf-8 -*-
from typing import Optional
import sqlite3


class DBManager:
    def __init__(self, db_path: str) -> None:
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute(
                '''CREATE TABLE IF NOT EXISTS games
                (addr TEXT PRIMARY KEY,
                gid INTEGER NOT NULL,
                board TEXT,
                score INTEGER NOT NULL)''')

    def add_game(self, addr: str, gid: int, board: str) -> None:
        args = (addr, gid, board, 0)
        q = 'INSERT INTO games VALUES ({})'.format(
            ','.join('?' for a in args))
        with self.db:
            self.db.execute(q, args)

    def delete_game(self, addr: str) -> None:
        with self.db:
            self.db.execute('DELETE FROM games WHERE addr=?', (addr,))

    def set_game(self, addr: str, board: str, score: int) -> None:
        q = 'UPDATE games SET board=?, score=? WHERE addr=?'
        with self.db:
            self.db.execute(q, (board, score, addr))

    def set_board(self, addr: str, board: Optional[str]) -> None:
        with self.db:
            self.db.execute(
                'UPDATE games SET board=? WHERE addr=?', (board, addr))

    def get_game_by_gid(self, gid: int) -> Optional[sqlite3.Row]:
        return self.db.execute(
            'SELECT * FROM games WHERE gid=?', (gid,)).fetchone()

    def get_game_by_addr(self, addr: str) -> Optional[sqlite3.Row]:
        return self.db.execute(
            'SELECT * FROM games WHERE addr=?', (addr,)).fetchone()
