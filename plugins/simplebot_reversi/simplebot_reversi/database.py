# -*- coding: utf-8 -*-
import sqlite3


class DBManager:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.commit('''CREATE TABLE IF NOT EXISTS games
                       (players TEXT,
                        gid INTEGER NOT NULL,
                        board TEXT,
                        black TEXT,
                        PRIMARY KEY(players))''')

    def execute(self, statement, args=()):
        return self.db.execute(statement, args)

    def commit(self, statement, args=()):
        with self.db:
            return self.db.execute(statement, args)

    def add_game(self, players, gid, board, black):
        self.commit('INSERT INTO games VALUES (?,?,?,?)',
                    (players, gid, board, black))

    def delete_game(self, players):
        self.commit('DELETE FROM games WHERE players=?', (players,))

    def set_game(self, players, board, black):
        self.commit('UPDATE games SET board=?, black=? WHERE players=?',
                    (board, black, players))

    def set_board(self, players, board):
        self.commit(
            'UPDATE games SET board=? WHERE players=?', (board, players))

    def get_game_by_gid(self, gid):
        return self.execute(
            'SELECT * FROM games WHERE gid=?', (gid,)).fetchone()

    def get_game_by_players(self, players):
        return self.db.execute(
            'SELECT * FROM games WHERE players=?', (players,)).fetchone()

    def close(self):
        self.db.close()
