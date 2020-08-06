# -*- coding: utf-8 -*-
from typing import Optional
from random import randint


CELL = ['⬜', '🔴', '🟢', '🟡', '🔵', '🟣', '🟠', '🟤']
COLS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
ROWS = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭', '🇮']


class Board:
    def __init__(self, game: str = None) -> None:
        if game:
            lines = game.split('\n')
            self.score = int(lines.pop(0))
            self.old_score = int(lines.pop(0))
            self.game = Field(balls=lines.pop(0), board=lines.pop(0))
        else:
            self.score = 0
            self.old_score = 0
            self.game = Field()
            self.game.set_next_balls()

    def export(self) -> str:
        board = str(self.score) + '\n'
        board += str(self.old_score) + '\n'
        board += ''.join(str(b.color) for b in self.game.next_balls)
        board += '\n'
        for row in self.game.field:
            for ball in row:
                if ball is None:
                    board += '0'
                else:
                    board += str(ball.color)
        return board

    def __str__(self) -> str:
        text = '|'.join(COLS) + '\n'
        for i, row in enumerate(self.game.field):
            for d in row:
                text += CELL[0] if d is None else CELL[d.color]
                text += '|'
            text += '{}\n'.format(ROWS[i])

        return text

    def is_valid(self, oi: int, oj: int, ei: int, ej: int) -> bool:
        return self.game.try_move(oi, oj, ei, ej)

    def move(self, coords: str) -> None:
        orig_coord = sorted(coords[:2].lower())
        end_coord = sorted(coords[2:].lower())
        o_j = 'abcdefghi'.find(orig_coord[1])
        o_i = '123456789'.find(orig_coord[0])
        e_j = 'abcdefghi'.find(end_coord[1])
        e_i = '123456789'.find(end_coord[0])

        if not self.is_valid(o_i, o_j, e_i, e_j):
            raise ValueError('Invalid move')

        self.game.make_step(o_i, o_j, e_i, e_j)

        balls = self.game.find_full_lines(e_i, e_j)
        if balls is None:
            self.next()
        else:
            self.game.delete_full_lines(balls)
            for e in self.game.set_balls:
                array = self.game.find_full_lines(e[0], e[1])
                if array is not None:
                    self.game.delete_full_lines(array)
        self.score += self.game.score

    def next(self) -> None:
        try:
            self.game.set_next_balls()
        except FieldFullException:
            pass

    def result(self) -> int:
        if len(self.game.free_cells) <= self.game.number_of_next_ball:
            return 1
        return 0


class Ball:
    """Class implementing a ball object"""

    def __init__(self, color: int = 0) -> None:
        """Initialize a ball object"""
        self.color = color
        self.selected = False

    def __eq__(self, other) -> bool:
        """Define the equality of balls"""
        return self.color == other.color

    def set_color(self, color: int) -> None:
        """Set the color (number) of the ball"""
        self.color = color

    def set_random_color(self, number_of_colors: int) -> None:
        """Determine the color of the ball"""
        self.color = randint(1, number_of_colors)


class Field:
    """Game Field"""

    def __init__(self, amount_cells: int = 9, player: str = "Player",
                 balls: str = None, board: str = None) -> None:
        """Initialize game field"""
        self.height = amount_cells
        self.width = amount_cells
        self.player = player
        self._set_number_of_ball_per_line()
        self._set_number_of_next_ball()
        self._set_number_of_color()
        self._init_field(board)

        if balls is not None:
            self.next_balls = []
            for e in balls:
                ball = Ball()
                ball.set_color(int(e))
                self.next_balls.append(ball)
        else:
            self.next_balls = []
            self.make_next_balls()

        self.set_balls: list = []
        self.score = 0

    def _init_field(self, board: Optional[str]) -> None:
        """Initialize field"""
        if board is not None:
            self.field: list = []
            self.free_cells = []
            for i in range(self.height):
                self.field.append([])
                for j in range(self.width):
                    if board[i * self.height + j] == '0':
                        self.field[i].append(None)
                        self.free_cells.append((j, i))
                    else:
                        ball = Ball()
                        ball.set_color(int(board[i*self.height + j]))
                        self.field[i].append(ball)
        else:
            self.field = []
            self.free_cells = []
            for rows in range(self.height):
                self.field.append([])
                for columns in range(self.width):
                    self.field[rows].append(None)
                    self.free_cells.append((columns, rows))

    def _set_number_of_color(self) -> None:
        """Set number of color"""
        self.number_of_color = self.height // 2 + 3

    def _set_number_of_ball_per_line(self) -> None:
        """Set number of a ball per line"""
        self.balls_in_line = self.height // 3 + 2

    def _set_number_of_next_ball(self) -> None:
        """Set the number of a ball put on the field"""
        self.number_of_next_ball = self.height // 4 + 1

    def make_next_balls(self) -> None:
        """Set the following balls"""
        self.next_balls.clear()
        for index in range(self.number_of_next_ball):
            ball = Ball()
            ball.set_random_color(self.number_of_color)
            self.next_balls.append(ball)

    def clear_field(self) -> None:
        """Clear the game field"""
        self.free_cells.clear()
        for rows in range(self.height):
            for columns in range(self.width):
                self.field[rows][columns] = None
                self.free_cells.append((rows, columns))

    def refresh_field(self) -> None:
        """Return the field to its initial state"""
        self.clear_field()
        self.score = 0
        self.make_next_balls()
        self.set_next_balls()

    def get_ball(self, x: int, y: int) -> Optional[Ball]:
        """Get a ball by coordinates"""
        return self.field[y][x]

    def get_color_of_ball(self, x: int, y: int) -> Optional[int]:
        """Get the color of the ball be coordinates"""
        if self.field[y][x] is not None:
            return self.field[y][x].color
        return None

    def set_ball(self, x: int, y: int, ball: Ball) -> None:
        """Set the ball by coordinates"""
        self.field[y][x] = ball
        self.free_cells.remove((x, y))

    def delete_ball(self, x: int, y: int) -> None:
        """Delete a ball by coordinates"""
        self.field[y][x] = None
        self.free_cells.append((x, y))

    def set_next_balls(self) -> None:
        """install the next balls on field"""
        if len(self.free_cells) <= self.number_of_next_ball:
            raise FieldFullException()
        self.set_balls.clear()
        for ball in self.next_balls:
            coordinates = self.free_cells[randint(0, len(self.free_cells)) - 1]
            self.set_ball(coordinates[0], coordinates[1], ball)
            self.set_balls.append((coordinates[0], coordinates[1]))
        self.make_next_balls()

    def try_move(self, start_x: int, start_y: int, end_x: int,
                 end_y: int) -> bool:
        """Try move ball in needed coordinate"""
        if self.get_ball(end_x, end_y) is not None or self.get_ball(start_x, start_y) is None:
            return False
        queue = []
        visited_cells = []
        queue.append((start_x, start_y))
        while len(queue) != 0:
            coordinates = queue.pop(0)
            if coordinates[0] < 0 or coordinates[0] >= self.height \
                    or coordinates[1] < 0 or coordinates[1] >= self.width:
                continue
            if (coordinates != (start_x, start_y) and self.get_ball(coordinates[0], coordinates[1]) is not None) \
                    or (coordinates[0], coordinates[1]) in visited_cells:
                continue
            if coordinates[0] == end_x and coordinates[1] == end_y:
                return True
            visited_cells.append((coordinates[0], coordinates[1]))
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if dx != 0 and dy != 0:
                        continue
                    else:
                        queue.append((coordinates[0] + dx, coordinates[1] + dy))
        return False

    def make_step(self, start_x: int, start_y: int, end_x: int,
                  end_y: int) -> None:
        """Make step"""
        ball = Ball(self.get_ball(start_x, start_y).color)
        self.set_ball(end_x, end_y, ball)
        self.delete_ball(start_x, start_y)

    def find_full_lines(self, x: int, y: int) -> Optional[list]:
        """Find all full lines starting by coordinates of ball"""
        if self.get_ball(x, y) is None:
            return None
        current_color = self.get_color_of_ball(x, y)
        ball_for_delete = []
        minus_dx = x
        plus_dx = x + 1
        while minus_dx >= 0 and self.get_color_of_ball(minus_dx, y) == current_color:
            ball_for_delete.append((minus_dx, y))
            minus_dx -= 1
        while plus_dx < self.width and self.get_color_of_ball(plus_dx, y) == current_color:
            ball_for_delete.append((plus_dx, y))
            plus_dx += 1
        if len(ball_for_delete) >= self.balls_in_line:
            return ball_for_delete
        else:
            ball_for_delete.clear()
        minus_dy = y
        plus_dy = y + 1
        while minus_dy >= 0 and self.get_color_of_ball(x, minus_dy) == current_color:
            ball_for_delete.append((x, minus_dy))
            minus_dy -= 1
        while plus_dy < self.height and self.get_color_of_ball(x, plus_dy) == current_color:
            ball_for_delete.append((x, plus_dy))
            plus_dy += 1
        if len(ball_for_delete) >= self.balls_in_line:
            return ball_for_delete
        else:
            ball_for_delete.clear()
        minus_dx = x
        minus_dy = y
        plus_dx = x + 1
        plus_dy = y + 1
        while minus_dx >= 0 and minus_dy >= 0 and self.get_color_of_ball(minus_dx, minus_dy) == current_color:
            ball_for_delete.append((minus_dx, minus_dy))
            minus_dx -= 1
            minus_dy -= 1
        while plus_dx < self.width and plus_dy < self.height and self.get_color_of_ball(plus_dx, plus_dy) == current_color:
            ball_for_delete.append((plus_dx, plus_dy))
            plus_dx += 1
            plus_dy += 1
        if len(ball_for_delete) >= self.balls_in_line:
            return ball_for_delete
        else:
            ball_for_delete.clear()
        minus_dx = x
        plus_dy = y
        while minus_dx >= 0 and plus_dy < self.height and self.get_color_of_ball(minus_dx, plus_dy) == current_color:
            ball_for_delete.append((minus_dx, plus_dy))
            minus_dx -= 1
            plus_dy += 1
        plus_dx = x + 1
        minus_dy = y - 1
        while plus_dx < self.width and minus_dy >= 0 and self.get_color_of_ball(plus_dx, minus_dy) == current_color:
            ball_for_delete.append((plus_dx, minus_dy))
            plus_dx += 1
            minus_dy -= 1
        if len(ball_for_delete) >= self.balls_in_line:
            return ball_for_delete
        return None

    def delete_full_lines(self, array_of_balls_coord: Optional[list]) -> None:
        """Delete full lines"""
        if array_of_balls_coord is not None:
            self.scoring(len(array_of_balls_coord))
            for coordinate in array_of_balls_coord:
                self.delete_ball(coordinate[0], coordinate[1])

    def scoring(self, length_of_remote_line: int) -> None:
        """Scoring by length of remote line"""
        multiplier = length_of_remote_line % self.balls_in_line + 1
        self.score += 10 * length_of_remote_line * multiplier


class FieldFullException(Exception):
    """Field full and no places to set next balls"""
    pass
