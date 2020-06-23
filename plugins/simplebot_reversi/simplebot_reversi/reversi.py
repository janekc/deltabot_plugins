# -*- coding: utf-8 -*-
from typing import Optional


BLACK = 'x'
WHITE = 'o'
COLS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣']
ROWS = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭']
DISKS = {BLACK: '🔴', WHITE: '🔵', ' ': '⬜', 'V': '⬛'}


class Board:
    def __init__(self, board=None):
        if board:
            lines = board.split('\n')
            self.turn = lines[0]
            self._board = [[e for e in ln] for ln in lines[1:]]
        else:
            self.turn = BLACK
            self._board = [[' ' for y in range(8)] for x in range(8)]
            self._board[3][3] = BLACK
            self._board[3][4] = WHITE
            self._board[4][3] = WHITE
            self._board[4][4] = BLACK

    def export(self) -> str:
        b = '\n'.join(''.join(ln) for ln in self._board)
        return '\n'.join((self.turn, b))

    def __str__(self) -> str:
        board = [[e for e in row] for row in self._board]
        for x, y in self.get_valid_moves(self.turn):
            board[x][y] = 'V'
        text = '|'.join(COLS) + '\n'
        for i, row in enumerate(board):
            for d in row:
                text += DISKS[d] + '|'
            text += ROWS[i] + '\n'
        return text

    def get_score(self) -> str:
        b, w = 0, 0
        for row in self._board:
            for d in row:
                if d == BLACK:
                    b += 1
                elif d == WHITE:
                    w += 1
        return '{} {} – {} {}'.format(DISKS[BLACK], b, w, DISKS[WHITE])

    def result(self) -> Optional[dict]:
        b, w = 0, 0
        for x in range(8):
            for y in range(8):
                if self.is_valid_move(self.turn, x, y):
                    return None
                elif self._board[x][y] == BLACK:
                    b += 1
                elif self._board[x][y] == WHITE:
                    w += 1
        return {BLACK: b, WHITE: w}

    def move(self, coord: str) -> None:
        sorted_coord = sorted(coord.lower())
        x = 'abcdefgh'.find(sorted_coord[1])
        assert x >= 0, 'Invalid move {}'.format(coord)
        y = int(sorted_coord[0]) - 1

        flipped = self.get_flipped(self.turn, x, y)
        if flipped:
            self._board[x][y] = self.turn
            for x, y in flipped:
                self._board[x][y] = self.turn
            self.turn = WHITE if self.turn == BLACK else BLACK
        else:
            raise ValueError('Invalid move ({}, {})'.format(x, y))

    def is_on_board(self, x: int, y: int) -> bool:
        return 0 <= x <= 7 and 0 <= y <= 7

    def get_valid_moves(self, disk: str) -> list:
        moves = []
        for x in range(8):
            for y in range(8):
                if self.is_valid_move(disk, x, y):
                    moves.append((x, y))
        return moves

    def is_valid_move(self, disk: str, x: int, y: int) -> bool:
        if not self.is_on_board(x, y) or self._board[x][y] != ' ':
            return False
        other_tile = WHITE if disk == BLACK else BLACK
        for xdir, ydir in ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)):
            newx, newy = x + xdir, y + ydir
            while self.is_on_board(newx, newy) and self._board[newx][newy] == other_tile:
                newx += xdir
                newy += ydir
            if self.is_on_board(newx, newy) and self._board[newx][newy] == disk and (newx-xdir, newy-ydir) != (x, y):
                return True
        return False

    def get_flipped(self, disk: str, x: int, y: int) -> list:
        if not self.is_on_board(x, y) or self._board[x][y] != ' ':
            return []

        other_tile = WHITE if disk == BLACK else BLACK
        flipped = []
        for xdir, ydir in ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)):
            newx, newy = x + xdir, y + ydir
            while self.is_on_board(newx, newy) and self._board[newx][newy] == other_tile:
                newx += xdir
                newy += ydir
            if not self.is_on_board(newx, newy) or self._board[newx][newy] != disk:
                continue
            while True:
                newx -= xdir
                newy -= ydir
                if newx == x and newy == y:
                    break
                flipped.append((newx, newy))
        return flipped
