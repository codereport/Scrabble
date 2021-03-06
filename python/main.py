"""
Scrabble Game

Started from https://arcade.academy/examples/array_backed_grid.html#array-backed-grid
"""

import arcade
import random                # shuffle
import itertools      as it  # permutations
import more_itertools as mt  # flatten
import numpy          as np  # transpose

from result import Ok, Err
from enum   import Enum
from tqdm   import tqdm, trange

import multiprocessing
from joblib import Parallel, delayed

## Constants

ROW_COUNT    = 15
COLUMN_COUNT = 15
WIDTH        = 50  # Grid width
HEIGHT       = 50  # Grid height
MARGIN       = 5   # This sets the margin between each cell and on the edges of the screen.

BOTTOM_MARGIN = 100
RIGHT_MARGIN  = 400

SCREEN_WIDTH  = (WIDTH + MARGIN)  * COLUMN_COUNT + MARGIN + RIGHT_MARGIN
SCREEN_HEIGHT = (HEIGHT + MARGIN) * ROW_COUNT    + MARGIN + BOTTOM_MARGIN
SCREEN_TITLE  = "Scrabble"

#TODO convert to Enum
NO = 1
DL = 2
DW = 3
TL = 4
TW = 5

BOARD = [[TW, NO, NO, DL, NO, NO, NO, TW, NO, NO, NO, DL, NO, NO, TW],
         [NO, DW, NO, NO, NO, TL, NO, NO, NO, TL, NO, NO, NO, DW, NO],
         [NO, NO, DW, NO, NO, NO, DL, NO, DL, NO, NO, NO, DW, NO, NO],
         [DL, NO, NO, DW, NO, NO, NO, DL, NO, NO, NO, DW, NO, NO, DL],
         [NO, NO, NO, NO, DW, NO, NO, NO, NO, NO, DW, NO, NO, NO, NO],
         [NO, TL, NO, NO, NO, TL, NO, NO, NO, TL, NO, NO, NO, TL, NO],
         [NO, NO, DL, NO, NO, NO, DL, NO, DL, NO, NO, NO, NO, DL, NO],
         [TW, NO, NO, DL, NO, NO, NO, DW, NO, NO, NO, DL, NO, NO, TW],
         [NO, NO, DL, NO, NO, NO, DL, NO, DL, NO, NO, NO, NO, DL, NO],
         [NO, TL, NO, NO, NO, TL, NO, NO, NO, TL, NO, NO, NO, TL, NO],
         [NO, NO, NO, NO, DW, NO, NO, NO, NO, NO, DW, NO, NO, NO, NO],
         [DL, NO, NO, DW, NO, NO, NO, DL, NO, NO, NO, DW, NO, NO, DL],
         [NO, NO, DW, NO, NO, NO, DL, NO, DL, NO, NO, NO, DW, NO, NO],
         [NO, DW, NO, NO, NO, TL, NO, NO, NO, TL, NO, NO, NO, DW, NO],
         [TW, NO, NO, DL, NO, NO, NO, TW, NO, NO, NO, DL, NO, NO, TW]]

TILE_SCORE = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2,  'H': 4, 'I': 1, 'J': 8,
    'K': 5, 'L': 1, 'M': 3, 'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1, 'S': 1, 'T': 1,
    'U': 1, 'V': 4, 'W': 4, 'X': 8, 'Y': 4, 'Z': 10}

TILE_BAG = \
    ['A'] * 9 + ['B'] * 2 + ['C'] * 2 + ['D'] * 4 + ['E'] * 12 + ['F'] * 2 + ['G'] * 3 + \
    ['H'] * 2 + ['I'] * 9 + ['J'] * 1 + ['K'] * 1  + ['L'] * 4 + ['M'] * 2 + ['N'] * 6 + \
    ['O'] * 8 + ['P'] * 2 + ['Q'] * 1 + ['R'] * 6  + ['S'] * 4 + ['T'] * 6 + ['U'] * 4 + \
    ['V'] * 2 + ['W'] * 2 + ['X'] * 1 + ['Y'] * 2  + ['Z'] * 1

COLOR_NORMAL        = (200, 196, 172)
COLOR_TRIPLE_WORD   = (241, 108,  77)
COLOR_TRIPLE_LETTER = ( 58, 156, 184)
COLOR_DOUBLE_WORD   = (250, 187, 170)
COLOR_DOUBLE_LETTER = (189, 215, 214)


## Enumerators

class Direction(Enum):
    ACROSS = 1
    DOWN = 2


## Free functions

def letter_multiplier(row, col):
    if BOARD[row][col] == DL: return 2
    if BOARD[row][col] == TL: return 3
    return 1


def word_multiplier(row, col):
    if BOARD[row][col] == DW: return 2
    if BOARD[row][col] == TW: return 3
    return 1


def tile_color(row, col):
    if BOARD[row][col] == DL: return COLOR_DOUBLE_LETTER
    if BOARD[row][col] == DW: return COLOR_DOUBLE_WORD
    if BOARD[row][col] == TL: return COLOR_TRIPLE_LETTER
    if BOARD[row][col] == TW: return COLOR_TRIPLE_WORD
    return COLOR_NORMAL

def prefix_tiles(board, dir, row, col):
    row_delta = 1 if dir == Direction.DOWN else 0
    col_delta = 0 if dir == Direction.DOWN else 1
    prev_row, prev_col, tiles, score = row, col, '', 0
    while prev_row - row_delta >= 0 and prev_col - col_delta >= 0:
        prev_row -= row_delta
        prev_col -= col_delta
        if board[prev_row][prev_col] != '.':
            tiles += board[prev_row][prev_col]
            score += TILE_SCORE.get(board[prev_row][prev_col])
        else:
            break
    return (tiles[::-1], score)

def suffix_tiles(board, dir, row, col):
    row_delta = 1 if dir == Direction.DOWN else 0
    col_delta = 0 if dir == Direction.DOWN else 1
    next_row, next_col, tiles, score = row, col, '', 0
    while next_row + row_delta < 15 and next_col + col_delta < 15:
        next_row += row_delta
        next_col += col_delta
        if board[next_row][next_col] != '.':
            tiles += board[next_row][next_col]
            score += TILE_SCORE.get(board[next_row][next_col])
        else:
            break
    return (tiles, score)

def is_first_turn(board):
    return all('.' == c for c in mt.flatten(board))

def word_score(board, dictionary, dir, letters, row, col, first_call):
    row = 14 - row
    if board[row][col] != '.':
        return Err('cannot start word on existing tile')
    if dir == Direction.ACROSS:
        if len([1 for c in board[row][col:] if c == '.']) < len(letters):
            return Err('outside of board')
    else:
        if len([1 for c in np.transpose(board)[col][row:] if c == '.']) < len(letters):
            return Err('outside of board')

    word_played, score = prefix_tiles(board, dir, row, col)
    word_mult      = 1
    row_delta      = 1 if dir == Direction.DOWN else 0
    col_delta      = 0 if dir == Direction.DOWN else 1
    crosses        = True if len(word_played) else False
    valid_start    = False

    perpandicular_words = []

    for letter in letters:
        while board[row][col] != '.':
            word_played = word_played + board[row][col]
            score += TILE_SCORE.get(board[row][col])
            row += row_delta
            col += col_delta
            crosses = True
        word_played = word_played + letter
        score += TILE_SCORE.get(letter) * letter_multiplier(row, col)
        word_mult *= word_multiplier(row, col)
        if dir == Direction.ACROSS:
            if (row + 1 <= 14 and board[row+1][col] != '.') or \
               (row - 1 >= 0  and board[row-1][col] != '.'):
                perpandicular_words.append((letter, (row, col)))
        else:
            if (col + 1 <= 14 and board[row][col+1] != '.') or \
               (col - 1 >= 0  and board[row][col-1] != '.'):
                perpandicular_words.append((letter, (row, col)))
        if row * col == 49:
            valid_start = True
        row += row_delta
        col += col_delta

    suffix, suffix_score = suffix_tiles(board, dir, row - row_delta, col - col_delta)
    word_played += suffix

    score += suffix_score

    score *= word_mult
    score += 50 if len(letters) == 7 else 0

    if first_call:
        opposite_dir = Direction.ACROSS if dir == Direction.DOWN else Direction.DOWN
        for word, (r, c) in perpandicular_words:
            res = word_score(board, dictionary, opposite_dir, word, 14-r, c, False)
            if res.is_ok():
                score += res.value[0]
            else:
                return res

    if not crosses and not len(suffix) and not len(perpandicular_words) and first_call:
        if is_first_turn(board):
            if not valid_start:
                return Err('first move must be through center tile')
        else:
            return Err('does not overlap with any other word')

    if word_played not in dictionary and not (len(word_played) == 1 and len(perpandicular_words)):
        return Err(word_played + ' not in dictionary')

    return Ok((score, word_played))

def min_play_length(board, row, col, dir):
    if is_first_turn(board):
        return 1
    if dir == Direction.DOWN:
        if row - 1 >= 0 and board[row - 1][col] != '.':
            return 1
        for i in range(7):
            if row + i <= 14:
                if (col - 1     >= 0  and board[row + i][col - 1] != '.') or \
                   (col + 1     <= 14 and board[row + i][col + 1] != '.') or \
                   (row + 1 + i <= 14 and board[row + i + 1][col] != '.'):
                    return i + 1
    else:
        if col - 1 >= 0 and board[row][col - 1] != '.':
            return 1
        for i in range(7):
            if col + i <= 14:
                if (row - 1     >= 0  and board[row - 1][col + i] != '.') or \
                   (row + 1     <= 14 and board[row + 1][col + i] != '.') or \
                   (col + 1 + i <= 14 and board[row][col + i + 1] != '.'):
                    return i + 1
    return 10

def word_scores_for_row(board, dictionary, row, words):
    plays = []
    if is_first_turn(board) and row != 7: return plays
    for col in range(COLUMN_COUNT):
        if board[14-row][col] == '.':
            if not is_first_turn(board):
                m = min_play_length(board, 14-row, col, Direction.DOWN)
                for word in words:
                    if len(word) >= m:
                        score = word_score(board, dictionary, Direction.DOWN, word, row, col, True)
                        if score.is_ok(): plays.append(score.unwrap())
            m = min_play_length(board, 14-row, col, Direction.ACROSS)
            for word in words:
                if len(word) >= m:
                    score = word_score(board, dictionary, Direction.ACROSS, word, row, col, True)
                    if score.is_ok(): plays.append(score.unwrap())
    return plays

class MyGame(arcade.Window):
    """Main application class"""

    def __init__(self, width, height, title):
        """Set up the application"""

        super().__init__(width, height, title)

        # Create a 2 dimensional array. A two dimensional array is simply a list of lists.
        self.grid = [['.'] * 15 for i in range(15)]

        arcade.set_background_color(arcade.color.BLACK)

        # Cursor for typings
        self.cursor   = 0  # 0 = off, 1 = across, 2 = down
        self.cursor_x = 0
        self.cursor_y = 0

        # Setup game
        random.shuffle(TILE_BAG)
        self.tile_bag_index = 14

        self.your_tiles      = TILE_BAG[0: 7]
        self.oppenents_tiles = TILE_BAG[7: 14]

        self.DICTIONARY = set()
        with open('dictionary.txt') as f:
            for line in f:
                self.DICTIONARY.add(line.strip())

        self.letters_typed = {}

    def on_draw(self):
        """Render the screen"""

        arcade.start_render()

        played_tile_color = arcade.color.DARK_PASTEL_GREEN if self.is_playable() else arcade.color.SAE

        # Draw the grid
        for row in range(ROW_COUNT):
            render_row = 14 - row
            for column in range(COLUMN_COUNT):
                color = tile_color(row, column) if self.grid[render_row][column] == '.' else arcade.color.AMETHYST
                if (row, column) in self.letters_typed:
                    color = played_tile_color

                x = (MARGIN + WIDTH)  * column + MARGIN + WIDTH  // 2
                y = (MARGIN + HEIGHT) * row    + MARGIN + HEIGHT // 2 + BOTTOM_MARGIN
                arcade.draw_rectangle_filled(x, y, WIDTH, HEIGHT, color)

                if self.grid[render_row][column] != '.':
                    arcade.draw_text(self.grid[render_row][column], x-15, y-25, arcade.color.WHITE, 40, bold=True)
                elif (row, column) in self.letters_typed:
                    arcade.draw_text(self.letters_typed.get((row, column)), x-15, y-25, arcade.color.WHITE, 40, bold=True)

        # Draw cursor
        if self.cursor and len(self.letters_typed) == 0:
            color = arcade.color.WHITE if self.cursor == 1 else arcade.color.BLACK
            x = (MARGIN + WIDTH)  * self.cursor_x + MARGIN + WIDTH  // 2
            y = (MARGIN + HEIGHT) * self.cursor_y + MARGIN + HEIGHT // 2 + BOTTOM_MARGIN
            arcade.draw_rectangle_filled(x, y, WIDTH, HEIGHT, color)

        # Draw tile rack
        tiles_left = list(self.letters_typed.values())
        for i, tile in enumerate(self.your_tiles):
            if tile in tiles_left:
                color = played_tile_color
                tiles_left.remove(tile)
            else:
                color = arcade.color.AMETHYST
            x = (4 + i) * (MARGIN + WIDTH) + MARGIN + WIDTH // 2
            y = 50

            # Draw the box - TODO refactor this into draw_tile
            arcade.draw_rectangle_filled(x, y, WIDTH, HEIGHT, color)
            arcade.draw_text(tile, x-15, y-25, arcade.color.WHITE, 40, bold=True)

    def on_mouse_press(self, x, y, button, modifiers):
        """Called when the user presses a mouse button"""

        # Change the x/y screen coordinates to grid coordinates
        column = int(x // (WIDTH + MARGIN))
        row    = int((y - BOTTOM_MARGIN) // (HEIGHT + MARGIN))

        self.cursor_x = column
        self.cursor_y = row
        self.cursor   = (self.cursor + 1) % 3

        print(f"Click coordinates: ({x}, {y}). Grid coordinates: ({row}, {column})")

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key"""

        if str(chr(key)).isalpha():
            letter = chr(key - 32)
            if letter in self.your_tiles:
                self.letters_typed[(self.cursor_y, self.cursor_x)] = letter
                if self.cursor == 1: self.cursor_x += 1
                if self.cursor == 2: self.cursor_y -= 1
                while self.cursor_y >  0  and \
                      self.cursor_x <= 14 and \
                      self.grid[14-self.cursor_y][self.cursor_x] != '.':
                    if self.cursor == 1: self.cursor_x += 1
                    if self.cursor == 2: self.cursor_y -= 1

        if key == arcade.key.ESCAPE:
            self.letters_typed.clear()
            self.cursor = 0

        if key == arcade.key.BACKSPACE:
            if len(self.letters_typed):
                self.letters_typed.popitem()
                if self.cursor == 1: self.cursor_x -= 1
                if self.cursor == 2: self.cursor_y += 1
                while self.grid[14-self.cursor_y][self.cursor_x] != '.':
                    if self.cursor == 1: self.cursor_x -= 1
                    if self.cursor == 2: self.cursor_y += 1

        if key == arcade.key.SPACE:
            random.shuffle(self.your_tiles)

        if key == arcade.key.ENTER:
            if self.is_playable():
                words = {''.join(p) for i in range(7, 1, -1) for p in it.permutations(self.your_tiles, i)}
                scores = Parallel(n_jobs=12, verbose=20)\
                    (delayed(word_scores_for_row)\
                        (self.grid, self.DICTIONARY, row, words) for row in range(15))
                for play in sorted(mt.flatten(scores)):
                    print(play)

                for (row, col), letter in self.letters_typed.items():
                    self.your_tiles.remove(letter)
                    self.grid[14-row][col] = letter
                tiles_needed         = 7 - len(self.your_tiles)
                self.your_tiles     += TILE_BAG[self.tile_bag_index:self.tile_bag_index + tiles_needed]
                self.tile_bag_index += tiles_needed
                self.letters_typed.clear()
                self.cursor = 0

    def is_playable(self):
        if len(self.letters_typed):
            start_row, start_col = next(iter(self.letters_typed))
            score = word_score(self.grid,
                               self.DICTIONARY,
                               Direction.ACROSS if self.cursor == 1 else Direction.DOWN,
                               ''.join(self.letters_typed.values()),
                               start_row, # super hacky
                               start_col,
                               True)
            # if score.is_ok():
            print(score.value)
            return score.is_ok()
        else:
            return False


# class WordPermutations():

#     def __init__(self, letters):
#         self.len1 = {''.join(p) p in it.permutations(self.your_tiles, 1)}
#         self.len2 = {''.join(p) p in it.permutations(self.your_tiles, 2)}
#         self.len3 = {''.join(p) p in it.permutations(self.your_tiles, 3)}
#         self.len4 = {''.join(p) p in it.permutations(self.your_tiles, 4)}
#         self.len5 = {''.join(p) p in it.permutations(self.your_tiles, 5)}
#         self.len6 = {''.join(p) p in it.permutations(self.your_tiles, 6)}
#         self.len7 = {''.join(p) p in it.permutations(self.your_tiles, 7)}

#         self.lo = 1
#         self.hi = 7

#     def set_range(self, lo, hi):
#         self.lo, self.hi = lo, hi

#     def __iter__(self):
#         self.i = iter(len1)
#         return next(i)


def main():

    MyGame(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    arcade.run()


if __name__ == "__main__":
    main()
