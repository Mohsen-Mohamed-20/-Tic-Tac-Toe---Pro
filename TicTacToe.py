import math
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import pygame


# -----------------------------
# Global configuration
# -----------------------------
WIDTH, HEIGHT = 1120, 720
FPS = 60

BOARD_SIZE = 510
BOARD_LEFT = 42
BOARD_TOP = 136
CELL = BOARD_SIZE // 3

PANEL_LEFT = BOARD_LEFT + BOARD_SIZE + 34
PANEL_TOP = 84
PANEL_WIDTH = WIDTH - PANEL_LEFT - 42
PANEL_HEIGHT = HEIGHT - PANEL_TOP - 38

BG = (7, 9, 18)
PANEL = (16, 21, 39)
PANEL_2 = (21, 28, 50)
GRID = (68, 79, 124)
TEXT = (226, 232, 255)
MUTED = (132, 143, 178)
SUBTLE = (42, 50, 82)
CYAN = (0, 225, 255)
PINK = (255, 57, 123)
LIME = (115, 255, 165)
AMBER = (255, 198, 86)
VIOLET = (150, 93, 255)
WHITE = (255, 255, 255)

WIN_LINES = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)

MODES = {
    "human_ai": "Human vs AI",
    "human_human": "Human vs Human",
    "ai_ai": "AI vs AI Demo",
    "minimax_random": "Minimax AI vs Random AI",
}

DIFFICULTIES = ("Easy", "Medium", "Hard", "Expert")
DEPTH_LIMITS = {"easy": 2, "medium": 4, "hard": 6, "expert": 9}
RANDOM_RATES = {"easy": 0.7, "medium": 0.45, "hard": 0.12, "expert": 0.0}

ARABIC_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)

# Arabic presentation forms: isolated, initial, medial, final.
ARABIC_FORMS = {
    key: tuple(forms)
    for item in """
    ء=ﺀﺀﺀﺀ آ=ﺁﺁﺂﺂ أ=ﺃﺃﺄﺄ ؤ=ﺅﺅﺆﺆ إ=ﺇﺇﺈﺈ ئ=ﺉﺋﺌﺊ ا=ﺍﺍﺎﺎ ب=ﺏﺑﺒﺐ ة=ﺓﺓﺔﺔ
    ت=ﺕﺗﺘﺖ ث=ﺙﺛﺜﺚ ج=ﺝﺟﺠﺞ ح=ﺡﺣﺤﺢ خ=ﺥﺧﺨﺦ د=ﺩﺩﺪﺪ ذ=ﺫﺫﺬﺬ ر=ﺭﺭﺮﺮ ز=ﺯﺯﺰﺰ
    س=ﺱﺳﺴﺲ ش=ﺵﺷﺸﺶ ص=ﺹﺻﺼﺺ ض=ﺽﺿﻀﺾ ط=ﻁﻃﻄﻂ ظ=ﻅﻇﻈﻆ ع=ﻉﻋﻌﻊ غ=ﻍﻏﻐﻎ
    ف=ﻑﻓﻔﻒ ق=ﻕﻗﻘﻖ ك=ﻙﻛﻜﻚ ل=ﻝﻟﻠﻞ م=ﻡﻣﻤﻢ ن=ﻥﻧﻨﻦ ه=ﻩﻫﻬﻪ و=ﻭﻭﻮﻮ
    ى=ﻯﻯﻰﻰ ي=ﻱﻳﻴﻲ لا=ﻻﻻﻼﻼ لآ=ﻵﻵﻶﻶ لأ=ﻷﻷﻸﻸ لإ=ﻹﻹﻺﻺ
    """.split()
    for key, forms in [item.split("=")]
}
RIGHT_JOIN_ONLY = set("اأإآدذرزوةؤى")
TASHKEEL = set("ًٌٍَُِّْٰ")


def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out_cubic(t):
    return 1 - pow(1 - clamp(t, 0, 1), 3)


def board_winner(board):
    for line in WIN_LINES:
        a, b, c = line
        if board[a] and board[a] == board[b] == board[c]:
            return board[a], line
    if all(board):
        return "Draw", None
    return None, None


def opponent(mark):
    return "O" if mark == "X" else "X"


def cell_center(index):
    row, col = divmod(index, 3)
    return (
        BOARD_LEFT + col * CELL + CELL // 2,
        BOARD_TOP + row * CELL + CELL // 2,
    )


def has_arabic(text):
    for char in str(text):
        code = ord(char)
        if any(start <= code <= end for start, end in ARABIC_RANGES):
            return True
    return False


def is_arabic_char(char):
    code = ord(char)
    return any(start <= code <= end for start, end in ARABIC_RANGES)


def can_connect_after(char):
    return char in ARABIC_FORMS and char not in RIGHT_JOIN_ONLY and char not in TASHKEEL


def can_connect_before(char):
    return char in ARABIC_FORMS and char not in TASHKEEL


def shape_arabic_run(text):
    """Convert Arabic letters to contextual forms, then reverse for Pygame LTR rendering."""
    result = []
    chars = list(text)
    i = 0
    while i < len(chars):
        char = chars[i]
        next_char = chars[i + 1] if i + 1 < len(chars) else ""

        # Lam-alef ligatures make common Arabic names look natural.
        if char == "ل" and next_char in ("ا", "أ", "إ", "آ"):
            ligature_key = char + next_char
            prev_char = chars[i - 1] if i > 0 else ""
            joins_prev = can_connect_after(prev_char) and can_connect_before(char)
            forms = ARABIC_FORMS[ligature_key]
            result.append(forms[2] if joins_prev else forms[0])
            i += 2
            continue

        forms = ARABIC_FORMS.get(char)
        if not forms:
            result.append(char)
            i += 1
            continue

        prev_char = chars[i - 1] if i > 0 else ""
        next_char = chars[i + 1] if i + 1 < len(chars) else ""
        joins_prev = can_connect_after(prev_char) and can_connect_before(char)
        joins_next = can_connect_after(char) and can_connect_before(next_char)

        if joins_prev and joins_next:
            shaped = forms[2]  # medial
        elif joins_next:
            shaped = forms[1]  # initial
        elif joins_prev:
            shaped = forms[3]  # final
        else:
            shaped = forms[0]  # isolated

        result.append(shaped)
        i += 1

    return "".join(reversed(result))


def display_text(text):
    """Shape Arabic runs for display while leaving English/numbers unchanged."""
    text = str(text)
    if not has_arabic(text):
        return text

    output = []
    run = []
    for char in text:
        if is_arabic_char(char) or char in TASHKEEL:
            run.append(char)
        else:
            if run:
                output.append(shape_arabic_run("".join(run)))
                run = []
            output.append(char)
    if run:
        output.append(shape_arabic_run("".join(run)))
    return "".join(output)


def make_font(size, bold=False):
    """Prefer Windows fonts that include Arabic glyphs, then fall back safely."""
    for name in ("Segoe UI", "Tahoma", "Arial", "Noto Sans Arabic", "Consolas"):
        font = pygame.font.SysFont(name, size, bold=bold)
        if font:
            return font
    return pygame.font.Font(None, size)


def fit_text(font, text, max_width):
    """Trim long text by rendered width so Arabic and Latin names fit nicely."""
    text = str(text)
    if font.size(display_text(text))[0] <= max_width:
        return text
    ellipsis = "..."
    while text and font.size(display_text(text + ellipsis))[0] > max_width:
        text = text[:-1]
    return text + ellipsis if text else ellipsis


def draw_text(surface, font, text, color, pos, anchor="topleft"):
    img = font.render(display_text(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(img, rect)
    return rect


def draw_glow_rect(surface, rect, color, radius=12, width=2, glow=16, fill=None):
    glow_surface = pygame.Surface((rect.width + glow * 2, rect.height + glow * 2), pygame.SRCALPHA)
    glow_rect = pygame.Rect(glow, glow, rect.width, rect.height)
    for i in range(glow, 0, -4):
        alpha = int(22 * (i / glow))
        pygame.draw.rect(
            glow_surface,
            (*color, alpha),
            glow_rect.inflate(i * 2, i * 2),
            border_radius=radius + i,
        )
    surface.blit(glow_surface, (rect.x - glow, rect.y - glow))
    if fill is not None:
        pygame.draw.rect(surface, fill, rect, border_radius=radius)
    pygame.draw.rect(surface, color, rect, width, border_radius=radius)


def draw_gradient_background(surface, tick):
    surface.fill(BG)
    for y in range(0, HEIGHT, 3):
        mix = y / HEIGHT
        color = (
            int(lerp(7, 18, mix)),
            int(lerp(9, 18, mix)),
            int(lerp(18, 36, mix)),
        )
        pygame.draw.line(surface, color, (0, y), (WIDTH, y + 2))

    grid_color = (22, 31, 58)
    offset = int((tick * 0.015) % 36)
    for x in range(-offset, WIDTH, 36):
        pygame.draw.line(surface, grid_color, (x, 0), (x + 80, HEIGHT), 1)
    for y in range(offset, HEIGHT, 36):
        pygame.draw.line(surface, grid_color, (0, y), (WIDTH, y), 1)


@dataclass
class AIResult:
    move: Optional[int] = None
    scores: dict = field(default_factory=dict)
    nodes: int = 0
    pruned: int = 0
    thinking_ms: int = 0
    best_move_index: Optional[int] = None
    evaluated_order: list = field(default_factory=list)


class SoundManager:
    def __init__(self):
        self.sounds = {}
        try:
            pygame.mixer.init()
            self.load_optional_sounds()
        except pygame.error:
            pass

    def load_optional_sounds(self):
        base = os.path.dirname(os.path.abspath(__file__))
        for key, candidates in {
            "click": ("click.wav", "click.mp3", "assets/click.wav"),
            "win": ("win.wav", "win.mp3", "assets/win.wav"),
            "draw": ("draw.wav", "draw.mp3", "assets/draw.wav"),
            "thinking": ("thinking.wav", "thinking.mp3", "assets/thinking.wav"),
        }.items():
            for candidate in candidates:
                path = os.path.join(base, candidate)
                if not os.path.exists(path):
                    continue
                try:
                    self.sounds[key] = pygame.mixer.Sound(path)
                except pygame.error:
                    pass
                break

    def play(self, name):
        try:
            self.sounds[name].play()
        except (KeyError, pygame.error):
            pass


class Button:
    """Reusable neon button with hover and click feedback."""

    def __init__(self, rect, text, font, color=CYAN, subtext=None, small_font=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.subtext = subtext
        self.font = font
        self.small_font = small_font or font
        self.color = color
        self.hovered = False
        self.selected = False
        self.enabled = True

    def handle_event(self, event, sound_manager=None):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if sound_manager:
                    sound_manager.play("click")
                return True
        return False

    def draw(self, surface):
        mouse = pygame.mouse.get_pos()
        self.hovered = self.rect.collidepoint(mouse) and self.enabled
        active = self.hovered or self.selected
        color = self.color if self.enabled else SUBTLE
        fill = PANEL_2 if active else PANEL
        if self.selected:
            fill = tuple(min(255, c + 18) for c in PANEL_2)

        if active:
            draw_glow_rect(surface, self.rect, color, radius=10, width=2, glow=18, fill=fill)
        else:
            pygame.draw.rect(surface, fill, self.rect, border_radius=10)
            pygame.draw.rect(surface, SUBTLE, self.rect, 1, border_radius=10)

        label_color = WHITE if self.enabled else MUTED
        draw_text(surface, self.font, self.text, label_color, (self.rect.centerx, self.rect.centery - (8 if self.subtext else 0)), "center")
        if self.subtext:
            draw_text(surface, self.small_font, self.subtext, color if self.enabled else MUTED, (self.rect.centerx, self.rect.centery + 20), "center")


class AnimationManager:
    """Tracks symbol placement and win-line animation timing."""

    def __init__(self):
        self.symbol_started = {}
        self.win_started = None

    def mark_cell(self, index):
        self.symbol_started[index] = pygame.time.get_ticks()

    def start_win(self):
        self.win_started = pygame.time.get_ticks()

    def reset(self):
        self.symbol_started.clear()
        self.win_started = None

    def symbol_progress(self, index):
        start = self.symbol_started.get(index)
        if start is None:
            return 1
        return ease_out_cubic((pygame.time.get_ticks() - start) / 330)

    def win_progress(self):
        if self.win_started is None:
            return 0
        return ease_out_cubic((pygame.time.get_ticks() - self.win_started) / 620)


class AIPlayer:
    """Minimax player with alpha-beta pruning plus intentionally weaker levels."""

    def __init__(self, mark, difficulty="Expert", style="minimax"):
        self.mark = mark
        self.difficulty = difficulty
        self.style = style
        self.nodes = 0
        self.pruned = 0
        self.evaluated_order = []

    def choose_move(self, board):
        start = time.perf_counter()
        self.nodes = 0
        self.pruned = 0
        self.evaluated_order = []
        empty = [i for i, value in enumerate(board) if value is None]
        if not empty:
            return AIResult()

        if self.style == "random":
            move = random.choice(empty)
            return self.make_result(move, {i: 0 for i in empty}, start)

        difficulty = self.difficulty.lower()
        random_rate = RANDOM_RATES.get(difficulty, 0.0)
        depth_limit = DEPTH_LIMITS.get(difficulty, 9)
        scores = self.evaluate_all_moves(board[:], depth_limit)

        # Easy/Medium/Hard sometimes choose a human-like mistake. Expert never does.
        if random_rate and random.random() < random_rate:
            move = random.choice(empty)
            return self.make_result(move, scores, start)

        best_score = max(scores.values())
        best_moves = [i for i, score in scores.items() if score == best_score]
        return self.make_result(self.tiebreak(best_moves, board), scores, start)

    def make_result(self, move, scores, start):
        return AIResult(
            move=move,
            scores=scores,
            nodes=self.nodes,
            pruned=self.pruned,
            thinking_ms=int((time.perf_counter() - start) * 1000),
            best_move_index=move,
            evaluated_order=self.evaluated_order[:],
        )

    def evaluate_all_moves(self, board, depth_limit):
        scores = {}
        for move in self.ordered_moves(board):
            if board[move] is None:
                board[move] = self.mark
                score = self.minimax(board, 1, False, -math.inf, math.inf, depth_limit)
                board[move] = None
                scores[move] = score
                self.evaluated_order.append(move)
        return scores

    def ordered_moves(self, board):
        order = [4, 0, 2, 6, 8, 1, 3, 5, 7]
        return [i for i in order if board[i] is None]

    def tiebreak(self, moves, board):
        preference = [4, 0, 2, 6, 8, 1, 3, 5, 7]
        for move in preference:
            if move in moves:
                return move
        return moves[0]

    def minimax(self, board, depth, maximizing, alpha, beta, depth_limit):
        self.nodes += 1
        winner, _ = board_winner(board)
        if winner:
            return self.score_terminal(winner, depth)
        if depth >= depth_limit:
            return self.heuristic(board)

        player = self.mark if maximizing else opponent(self.mark)
        if maximizing:
            best = -math.inf
            for move in self.ordered_moves(board):
                board[move] = player
                best = max(best, self.minimax(board, depth + 1, False, alpha, beta, depth_limit))
                board[move] = None
                alpha = max(alpha, best)
                if beta <= alpha:
                    self.pruned += 1
                    break
            return best

        best = math.inf
        for move in self.ordered_moves(board):
            board[move] = player
            best = min(best, self.minimax(board, depth + 1, True, alpha, beta, depth_limit))
            board[move] = None
            beta = min(beta, best)
            if beta <= alpha:
                self.pruned += 1
                break
        return best

    def score_terminal(self, winner, depth):
        if winner == self.mark:
            return 100 - depth
        if winner == "Draw":
            return 0
        return depth - 100

    def heuristic(self, board):
        score = 0
        enemy = opponent(self.mark)
        weights = {1: 2, 2: 12, 3: 100}
        for line in WIN_LINES:
            values = [board[i] for i in line]
            mine = values.count(self.mark)
            theirs = values.count(enemy)
            if mine and not theirs:
                score += weights[mine]
            elif theirs and not mine:
                score -= weights[theirs]
        if board[4] == self.mark:
            score += 5
        elif board[4] == enemy:
            score -= 5
        return score


class MenuScreen:
    """Main menu with neon/dark controls for mode and difficulty."""

    def __init__(self, screen, fonts, sound_manager):
        self.screen = screen
        self.fonts = fonts
        self.sound_manager = sound_manager
        self.mode = "human_ai"
        self.difficulty = "Expert"
        self.buttons = {}
        self.build_buttons()

    def build_buttons(self):
        mode_specs = [
            ("human_ai", "Human vs AI", "Classic challenge", CYAN),
            ("human_human", "Human vs Human", "Two players", PINK),
            ("ai_ai", "AI vs AI Demo", "Watch minimax think", LIME),
            ("minimax_random", "Minimax vs Random", "Strategy lab", AMBER),
        ]
        start_x = 164
        start_y = 222
        w, h = 380, 78
        for n, (key, label, sub, color) in enumerate(mode_specs):
            col = n % 2
            row = n // 2
            self.buttons[key] = Button(
                (start_x + col * 410, start_y + row * 100, w, h),
                label,
                self.fonts["button"],
                color,
                sub,
                self.fonts["tiny"],
            )

        diff_y = 456
        diff_w = 180
        for n, diff in enumerate(DIFFICULTIES):
            color = [LIME, AMBER, PINK, VIOLET][n]
            self.buttons[f"diff_{diff}"] = Button(
                (150 + n * 205, diff_y, diff_w, 62),
                diff,
                self.fonts["button"],
                color,
            )

        self.buttons["start"] = Button((WIDTH // 2 - 150, 586, 300, 66), "Start Game", self.fonts["title"], CYAN)

    def handle_event(self, event):
        for key, button in self.buttons.items():
            if button.handle_event(event, self.sound_manager):
                if key in MODES:
                    self.mode = key
                elif key.startswith("diff_"):
                    self.difficulty = key.replace("diff_", "")
                elif key == "start":
                    return "start"
        return None

    def draw(self):
        tick = pygame.time.get_ticks()
        draw_gradient_background(self.screen, tick)
        draw_text(self.screen, self.fonts["mega"], "TIC TAC TOE", TEXT, (WIDTH // 2, 72), "center")
        draw_text(self.screen, self.fonts["subtitle"], "NEON AI ARENA", CYAN, (WIDTH // 2, 124), "center")
        draw_text(self.screen, self.fonts["small"], "Choose a mode and difficulty", MUTED, (WIDTH // 2, 162), "center")

        for key, button in self.buttons.items():
            button.selected = key == self.mode or key == f"diff_{self.difficulty}"
            if key.startswith("diff_"):
                button.enabled = self.mode in ("human_ai", "ai_ai", "minimax_random")
            button.draw(self.screen)

        draw_text(
            self.screen,
            self.fonts["tiny"],
            "Expert uses full-depth minimax with alpha-beta pruning and perfect tie-breaking.",
            MUTED,
            (WIDTH // 2, 676),
            "center",
        )


class NameEntryScreen:
    """Collects player names before starting Human vs Human mode."""

    def __init__(self, screen, fonts, sound_manager):
        self.screen = screen
        self.fonts = fonts
        self.sound_manager = sound_manager
        self.values = {"X": "", "O": ""}
        self.active = "X"
        self.fields = {
            "X": pygame.Rect(WIDTH // 2 - 230, 270, 460, 58),
            "O": pygame.Rect(WIDTH // 2 - 230, 372, 460, 58),
        }
        self.buttons = {
            "start": Button((WIDTH // 2 - 150, 506, 300, 62), "Start Match", fonts["title"], CYAN),
            "back": Button((WIDTH // 2 - 100, 588, 200, 46), "Back", fonts["button"], PINK),
        }

    def handle_event(self, event):
        if self.buttons["start"].handle_event(event, self.sound_manager):
            return "start"
        if self.buttons["back"].handle_event(event, self.sound_manager):
            return "back"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for mark, rect in self.fields.items():
                if rect.collidepoint(event.pos):
                    self.active = mark
                    self.sound_manager.play("click")

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self.active = opponent(self.active)
            elif event.key == pygame.K_RETURN:
                if self.active == "X":
                    self.active = "O"
                else:
                    return "start"
            elif event.key == pygame.K_BACKSPACE:
                self.values[self.active] = self.values[self.active][:-1]
            elif event.unicode and event.unicode.isprintable():
                # Arabic names are accepted through pygame's Unicode text events.
                if len(self.values[self.active]) < 18:
                    self.values[self.active] += event.unicode
        return None

    def player_names(self):
        return {
            "X": self.values["X"].strip() or "Player 1",
            "O": self.values["O"].strip() or "Player 2",
        }

    def draw(self):
        tick = pygame.time.get_ticks()
        draw_gradient_background(self.screen, tick)
        draw_text(self.screen, self.fonts["mega"], "PLAYER NAMES", TEXT, (WIDTH // 2, 86), "center")
        draw_text(self.screen, self.fonts["small"], "Human vs Human setup", CYAN, (WIDTH // 2, 138), "center")

        self.draw_field("X", "First player name", CYAN)
        self.draw_field("O", "Second player name", PINK)

        for button in self.buttons.values():
            button.draw(self.screen)

        draw_text(
            self.screen,
            self.fonts["tiny"],
            "Press Enter to continue, Tab to switch fields.",
            MUTED,
            (WIDTH // 2, 662),
            "center",
        )

    def draw_field(self, mark, label, color):
        rect = self.fields[mark]
        active = self.active == mark
        draw_text(self.screen, self.fonts["button"], f"{label} ({mark})", color, (rect.x, rect.y - 30), "topleft")
        draw_glow_rect(
            self.screen,
            rect,
            color if active else SUBTLE,
            radius=10,
            width=2 if active else 1,
            glow=18 if active else 8,
            fill=PANEL_2 if active else PANEL,
        )
        value = self.values[mark] or ("Player 1" if mark == "X" else "Player 2")
        fitted_value = fit_text(self.fonts["subtitle"], value, rect.width - 38)
        text_color = TEXT if self.values[mark] else MUTED
        if has_arabic(value):
            draw_text(self.screen, self.fonts["subtitle"], fitted_value, text_color, (rect.right - 18, rect.centery), "midright")
        else:
            draw_text(self.screen, self.fonts["subtitle"], fitted_value, text_color, (rect.x + 18, rect.centery), "midleft")
        if active and (pygame.time.get_ticks() // 430) % 2 == 0:
            text_width = self.fonts["subtitle"].size(display_text(fitted_value))[0]
            if has_arabic(value):
                x = max(rect.x + 20, rect.right - 20 - text_width)
            else:
                x = min(rect.right - 20, rect.x + 20 + text_width)
            pygame.draw.line(self.screen, color, (x, rect.y + 15), (x, rect.bottom - 15), 2)


class TicTacToeGame:
    """Owns gameplay state, rendering, AI turns, scoreboard, and end screen."""

    def __init__(self, screen, fonts, sound_manager, mode, difficulty, player_names=None):
        self.screen = screen
        self.fonts = fonts
        self.sound_manager = sound_manager
        self.mode = mode
        self.difficulty = difficulty
        self.player_names = player_names or self.default_player_names()
        self.animations = AnimationManager()
        self.scores = {"X": 0, "O": 0, "Draw": 0}
        self.buttons = {
            "restart": Button((PANEL_LEFT, 24, 142, 42), "Restart", fonts["button"], AMBER),
            "menu": Button((PANEL_LEFT + 154, 24, 166, 42), "Back to Menu", fonts["button"], PINK),
            "play_again": Button((BOARD_LEFT + 116, BOARD_TOP + 278, 132, 48), "Play Again", fonts["button"], CYAN),
            "end_menu": Button((BOARD_LEFT + 266, BOARD_TOP + 278, 132, 48), "Menu", fonts["button"], PINK),
        }
        self.reset_round(reset_scores=False)

    def default_player_names(self):
        if self.mode == "human_ai":
            ai_name = "Baby" if self.difficulty == "Easy" else "AI"
            return {"X": "Human", "O": ai_name}
        if self.mode == "minimax_random":
            return {"X": "Minimax AI", "O": "Random AI"}
        if self.mode == "ai_ai":
            return {"X": "AI X", "O": "AI O"}
        return {"X": "Player 1", "O": "Player 2"}

    def player_label(self, mark):
        return self.player_names.get(mark, mark)

    def score_label(self, mark):
        return f"{self.player_label(mark)} [{mark}]"

    def reset_round(self, reset_scores=False):
        if reset_scores:
            self.scores = {"X": 0, "O": 0, "Draw": 0}
        self.board = [None] * 9
        self.current = "X"
        self.winner = None
        self.win_line = None
        self.game_over = False
        self.ai_waiting = False
        self.ai_started_at = 0
        self.ai_delay_ms = 620
        self.ai_stats = AIResult()
        self.last_ai_move = None
        self.preview_scores = {}
        self.preview_order = []
        self.animations.reset()
        self.prepare_ai_preview()
        self.maybe_start_ai_turn()

    def mode_label(self):
        return MODES[self.mode]

    def is_ai_turn(self):
        if self.game_over:
            return False
        if self.mode == "human_ai":
            return self.current == "O"
        if self.mode in ("ai_ai", "minimax_random"):
            return True
        return False

    def ai_for_current_turn(self):
        if self.mode == "minimax_random" and self.current == "O":
            return AIPlayer("O", self.difficulty, "random")
        return AIPlayer(self.current, self.difficulty, "minimax")

    def prepare_ai_preview(self):
        self.preview_scores = {}
        self.preview_order = []
        if self.game_over:
            return
        if self.mode in ("human_ai", "ai_ai", "minimax_random"):
            ai = self.ai_for_current_turn()
            depth = DEPTH_LIMITS.get(self.difficulty.lower(), 9)
            self.preview_scores = ai.evaluate_all_moves(self.board[:], depth)
            self.preview_order = ai.evaluated_order[:]

    def maybe_start_ai_turn(self):
        if self.is_ai_turn() and not self.ai_waiting:
            self.ai_waiting = True
            self.ai_started_at = pygame.time.get_ticks()
            self.sound_manager.play("thinking")

    def update(self):
        if self.game_over:
            return

        self.maybe_start_ai_turn()
        if not self.ai_waiting:
            return

        now = pygame.time.get_ticks()
        delay = self.ai_delay_ms if self.mode == "human_ai" else 760
        if now - self.ai_started_at < delay:
            return

        ai = self.ai_for_current_turn()
        result = ai.choose_move(self.board[:])
        self.ai_stats = result
        self.preview_scores = result.scores
        self.preview_order = result.evaluated_order
        self.last_ai_move = result.move
        self.ai_waiting = False
        if result.move is not None:
            self.make_move(result.move)

    def handle_event(self, event):
        if self.buttons["restart"].handle_event(event, self.sound_manager):
            self.restart_round()
            return None
        if self.buttons["menu"].handle_event(event, self.sound_manager):
            return "menu"

        if self.game_over:
            if self.buttons["play_again"].handle_event(event, self.sound_manager):
                self.restart_round()
            if self.buttons["end_menu"].handle_event(event, self.sound_manager):
                return "menu"
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.restart_round()
            if event.key == pygame.K_m:
                return "menu"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.ai_waiting or self.is_ai_turn():
                return None
            index = self.index_from_pos(event.pos)
            if index is not None:
                self.make_move(index)
        return None

    def restart_round(self):
        self.reset_round(reset_scores=False)

    def index_from_pos(self, pos):
        x, y = pos
        if BOARD_LEFT <= x < BOARD_LEFT + BOARD_SIZE and BOARD_TOP <= y < BOARD_TOP + BOARD_SIZE:
            col = (x - BOARD_LEFT) // CELL
            row = (y - BOARD_TOP) // CELL
            return int(row * 3 + col)
        return None

    def make_move(self, index):
        if index not in range(9):
            return
        if self.board[index] is not None or self.game_over:
            return
        self.board[index] = self.current
        self.animations.mark_cell(index)
        self.sound_manager.play("click")

        winner, line = board_winner(self.board)
        if winner:
            self.game_over = True
            self.winner = winner
            self.win_line = line
            self.scores[winner] += 1
            if winner == "Draw":
                self.sound_manager.play("draw")
            else:
                self.sound_manager.play("win")
                self.animations.start_win()
            return

        self.current = opponent(self.current)
        self.prepare_ai_preview()
        self.maybe_start_ai_turn()

    def draw(self):
        tick = pygame.time.get_ticks()
        draw_gradient_background(self.screen, tick)
        self.draw_top_bar()
        self.draw_board()
        self.draw_panel()
        if self.game_over:
            self.draw_end_overlay()

    def draw_top_bar(self):
        draw_text(self.screen, self.fonts["title"], "Tic Tac Toe AI", TEXT, (42, 42), "midleft")
        draw_text(self.screen, self.fonts["small"], self.mode_label(), CYAN, (42, 74), "midleft")
        match_text = f"X: {self.player_label('X')}    O: {self.player_label('O')}"
        match_text = fit_text(self.fonts["tiny"], match_text, 470)
        draw_text(self.screen, self.fonts["tiny"], match_text, MUTED, (42, 98), "midleft")
        self.buttons["restart"].draw(self.screen)
        self.buttons["menu"].draw(self.screen)

    def draw_board(self):
        board_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_SIZE, BOARD_SIZE)
        draw_glow_rect(self.screen, board_rect, CYAN, radius=16, width=2, glow=20, fill=PANEL)

        # AI thinking and selected move highlights.
        self.draw_cell_highlights()

        for i in range(1, 3):
            x = BOARD_LEFT + i * CELL
            y = BOARD_TOP + i * CELL
            pygame.draw.line(self.screen, GRID, (x, BOARD_TOP + 16), (x, BOARD_TOP + BOARD_SIZE - 16), 4)
            pygame.draw.line(self.screen, GRID, (BOARD_LEFT + 16, y), (BOARD_LEFT + BOARD_SIZE - 16, y), 4)

        for index, mark in enumerate(self.board):
            if mark:
                self.draw_mark(index, mark)

        if self.win_line:
            self.draw_win_line()

    def draw_cell_highlights(self):
        now = pygame.time.get_ticks()
        for index, score in self.preview_scores.items():
            if self.board[index] is not None:
                continue
            row, col = divmod(index, 3)
            rect = pygame.Rect(BOARD_LEFT + col * CELL + 8, BOARD_TOP + row * CELL + 8, CELL - 16, CELL - 16)
            alpha = 32
            if self.ai_waiting and index in self.preview_order:
                position = self.preview_order.index(index)
                pulse = (math.sin(now * 0.01 + position) + 1) * 0.5
                alpha = int(28 + 48 * pulse)
            color = CYAN if score >= 0 else PINK
            if self.ai_stats.best_move_index == index or self.last_ai_move == index:
                color = AMBER
                alpha = 88
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(overlay, (*color, alpha), overlay.get_rect(), border_radius=12)
            self.screen.blit(overlay, rect.topleft)

    def draw_mark(self, index, mark):
        cx, cy = cell_center(index)
        progress = self.animations.symbol_progress(index)
        color = CYAN if mark == "X" else PINK
        if self.win_line and index in self.win_line:
            color = AMBER
        size = int(56 * progress)
        width = 9

        if mark == "X":
            pygame.draw.line(self.screen, color, (cx - size, cy - size), (cx + size, cy + size), width)
            pygame.draw.line(self.screen, color, (cx + size, cy - size), (cx - size, cy + size), width)
        else:
            pygame.draw.circle(self.screen, color, (cx, cy), size, width)

    def draw_win_line(self):
        if not self.win_line:
            return
        start = cell_center(self.win_line[0])
        end = cell_center(self.win_line[-1])
        progress = self.animations.win_progress()
        current = (
            int(lerp(start[0], end[0], progress)),
            int(lerp(start[1], end[1], progress)),
        )
        pygame.draw.line(self.screen, AMBER, start, current, 12)
        pygame.draw.line(self.screen, WHITE, start, current, 3)

    def draw_panel(self):
        panel_rect = pygame.Rect(PANEL_LEFT, PANEL_TOP, PANEL_WIDTH, PANEL_HEIGHT)
        pygame.draw.rect(self.screen, PANEL, panel_rect, border_radius=14)
        pygame.draw.rect(self.screen, SUBTLE, panel_rect, 1, border_radius=14)

        x = PANEL_LEFT + 22
        y = PANEL_TOP + 22
        draw_text(self.screen, self.fonts["subtitle"], "Scoreboard", TEXT, (x, y), "topleft")
        y += 44
        total = max(1, self.scores["X"] + self.scores["O"] + self.scores["Draw"])
        rows = [
            (self.score_label("X"), self.scores["X"], CYAN),
            (self.score_label("O"), self.scores["O"], PINK),
            ("Draw", self.scores["Draw"], MUTED),
        ]
        for label, value, color in rows:
            rate = int((value / total) * 100)
            self.draw_stat_row(x, y, label, value, f"{rate}% win rate" if label != "Draw" else f"{rate}% draw rate", color)
            y += 54

        y += 8
        current_label = f"{self.player_label(self.current)} ({self.current})"
        self.draw_info_card(x, y, "Current turn", current_label, CYAN if self.current == "X" else PINK)
        y += 70
        self.draw_info_card(x, y, "Game mode", self.mode_label(), TEXT)
        y += 70
        self.draw_info_card(x, y, "Difficulty", self.difficulty, VIOLET)
        y += 82

        draw_text(self.screen, self.fonts["subtitle"], "AI stats", TEXT, (x, y), "topleft")
        y += 40
        thinking = "thinking..." if self.ai_waiting else "ready"
        stats = [
            ("State", thinking),
            ("Nodes explored", self.ai_stats.nodes),
            ("Pruned branches", self.ai_stats.pruned),
            ("Thinking time", f"{self.ai_stats.thinking_ms} ms"),
            ("Best move index", "-" if self.ai_stats.best_move_index is None else self.ai_stats.best_move_index),
        ]
        for label, value in stats:
            draw_text(self.screen, self.fonts["small"], label, MUTED, (x, y), "topleft")
            draw_text(self.screen, self.fonts["small"], value, TEXT, (PANEL_LEFT + PANEL_WIDTH - 24, y), "topright")
            y += 28

    def draw_stat_row(self, x, y, label, value, note, color):
        max_label = fit_text(self.fonts["button"], label, PANEL_WIDTH - 116)
        draw_text(self.screen, self.fonts["button"], max_label, color, (x, y), "topleft")
        draw_text(self.screen, self.fonts["title"], value, TEXT, (PANEL_LEFT + PANEL_WIDTH - 24, y - 3), "topright")
        draw_text(self.screen, self.fonts["tiny"], note, MUTED, (x, y + 28), "topleft")

    def draw_info_card(self, x, y, label, value, color):
        rect = pygame.Rect(x, y, PANEL_WIDTH - 44, 54)
        pygame.draw.rect(self.screen, PANEL_2, rect, border_radius=8)
        pygame.draw.rect(self.screen, SUBTLE, rect, 1, border_radius=8)
        draw_text(self.screen, self.fonts["tiny"], label, MUTED, (rect.x + 14, rect.y + 9), "topleft")
        fitted_value = fit_text(self.fonts["button"], value, rect.width - 28)
        if has_arabic(value):
            draw_text(self.screen, self.fonts["button"], fitted_value, color, (rect.right - 14, rect.y + 29), "topright")
        else:
            draw_text(self.screen, self.fonts["button"], fitted_value, color, (rect.x + 14, rect.y + 29), "topleft")

    def draw_end_overlay(self):
        overlay = pygame.Surface((BOARD_SIZE, BOARD_SIZE), pygame.SRCALPHA)
        overlay.fill((5, 8, 18, 214))
        self.screen.blit(overlay, (BOARD_LEFT, BOARD_TOP))

        card = pygame.Rect(BOARD_LEFT + 58, BOARD_TOP + 106, BOARD_SIZE - 116, 258)
        draw_glow_rect(self.screen, card, AMBER if self.winner != "Draw" else CYAN, radius=16, width=2, glow=22, fill=(12, 17, 32))

        if self.winner == "Draw":
            headline = "DRAW"
            sub = "No winner this round"
            color = CYAN
        else:
            headline = f"{self.player_label(self.winner)} WINS"
            headline = fit_text(self.fonts["mega"], headline, card.width - 44)
            sub = "Perfect line secured"
            color = AMBER

        draw_text(self.screen, self.fonts["mega"], headline, color, (card.centerx, card.y + 70), "center")
        draw_text(self.screen, self.fonts["small"], sub, MUTED, (card.centerx, card.y + 126), "center")
        self.buttons["play_again"].draw(self.screen)
        self.buttons["end_menu"].draw(self.screen)


class App:
    """Application controller for menu and game screen transitions."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tic Tac Toe AI - Neon Pro")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = {
            "mega": make_font(46, bold=True),
            "title": make_font(28, bold=True),
            "subtitle": make_font(22, bold=True),
            "button": make_font(18, bold=True),
            "small": make_font(16),
            "tiny": make_font(13),
        }
        self.sound_manager = SoundManager()
        self.menu = MenuScreen(self.screen, self.fonts, self.sound_manager)
        self.name_entry = NameEntryScreen(self.screen, self.fonts, self.sound_manager)
        self.game = None
        self.state = "menu"

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if self.state == "menu":
                    action = self.menu.handle_event(event)
                    if action == "start":
                        if self.menu.mode == "human_human":
                            self.name_entry = NameEntryScreen(self.screen, self.fonts, self.sound_manager)
                            self.state = "names"
                        else:
                            self.start_game()
                elif self.state == "names":
                    action = self.name_entry.handle_event(event)
                    if action == "start":
                        self.start_game(self.name_entry.player_names())
                    elif action == "back":
                        self.state = "menu"
                elif self.state == "game":
                    action = self.game.handle_event(event)
                    if action == "menu":
                        self.state = "menu"

            if self.state == "menu":
                self.menu.draw()
            elif self.state == "names":
                self.name_entry.draw()
            else:
                self.game.update()
                self.game.draw()

            pygame.display.flip()
            self.clock.tick(FPS)

    def start_game(self, player_names=None):
        self.game = TicTacToeGame(
            self.screen,
            self.fonts,
            self.sound_manager,
            self.menu.mode,
            self.menu.difficulty,
            player_names,
        )
        self.state = "game"


def main():
    App().run()


if __name__ == "__main__":
    main()
