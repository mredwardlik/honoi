"""The pygame window: drawing, mouse and keyboard, animations and the auto solver."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from .towers import MAX_DISKS, MIN_DISKS, PEGS, IllegalMove, Move, Towers

TITLE = 'Tower of Hanoi'
MIN_SIZE = (640, 420)
FPS = 60

BACKGROUND = (21, 23, 32)
PANEL = (33, 36, 50)
TEXT = (232, 234, 242)
MUTED = (132, 138, 164)
PEG = (78, 84, 110)
PEG_HOVER = (120, 128, 165)
TARGET = (255, 196, 84)
ERROR = (235, 87, 87)
SUCCESS = (92, 207, 140)
HINT = (110, 170, 255)

MOVE_SECONDS = 0.32
SPEEDS = (0.5, 1, 2, 4, 8, 16, 32)
MESSAGE_SECONDS = 2.2

HELP = ('click or 1 2 3  move', 'space  solve', 'H  hint', 'U  undo', 'R  restart', '+ −  disks', 'esc  quit')


def disk_color(disk: int, disks: int) -> pygame.Color:
    """Warm colors for small disks, cold ones for large."""
    color = pygame.Color(0)
    hue = 20 + 250 * (disk - 1) / max(1, disks - 1)
    color.hsva = (hue % 360, 62, 96, 100)
    return color


def smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


@dataclass
class Layout:
    """Where everything is for a window size and a number of disks."""

    width: int
    height: int
    disks: int
    top: int = field(init=False)
    base_y: int = field(init=False)
    disk_height: float = field(init=False)
    max_disk: float = field(init=False)
    min_disk: float = field(init=False)
    peg_height: float = field(init=False)
    lift_y: float = field(init=False)

    def __post_init__(self):
        self.top = 84
        self.base_y = self.height - 96
        room = self.base_y - self.top - 40
        self.disk_height = max(8.0, min(34.0, room / (self.disks + 2.5)))
        self.max_disk = min(self.width / PEGS - 44, 320.0)
        self.min_disk = max(self.max_disk * 0.28, 34.0)
        self.peg_height = self.disk_height * (self.disks + 1) + 14
        self.lift_y = self.base_y - self.peg_height - self.disk_height - 14

    def peg_x(self, peg: int) -> float:
        return self.width * (peg + 0.5) / PEGS

    def peg_at(self, x: float) -> int:
        return max(0, min(PEGS - 1, int(x * PEGS / self.width)))

    def disk_width(self, disk: int) -> float:
        if self.disks == 1:
            return self.max_disk
        return self.min_disk + (self.max_disk - self.min_disk) * (disk - 1) / (self.disks - 1)

    def slot(self, peg: int, level: int) -> tuple[float, float]:
        """Center of a disk at ``level`` (0 is the bottom) on ``peg``."""
        return self.peg_x(peg), self.base_y - (level + 0.5) * self.disk_height

    def lifted(self, x: float) -> tuple[float, float]:
        return x, self.lift_y + self.disk_height / 2


@dataclass
class Flight:
    """A disk on its way: up, across and down along a polyline."""

    disk: int
    points: list[tuple[float, float]]
    duration: float
    time: float = 0.0

    @property
    def done(self) -> bool:
        return self.time >= self.duration

    def position(self) -> tuple[float, float]:
        lengths = [math.dist(a, b) for a, b in zip(self.points, self.points[1:])]
        total = sum(lengths) or 1
        left = smooth(min(1.0, self.time / self.duration)) * total
        for (a, b), length in zip(zip(self.points, self.points[1:]), lengths):
            if left <= length and length:
                k = left / length
                return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
            left -= length
        return self.points[-1]


@dataclass
class Confetti:
    x: float
    y: float
    vx: float
    vy: float
    color: pygame.Color
    size: float
    spin: float
    angle: float = 0.0


class Game:
    """One window, one puzzle. ``update`` and ``draw`` are separate, so tests can drive it."""

    def __init__(self, disks: int = 4, size: tuple[int, int] = (960, 600), solve: bool = False):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self.running = True
        self.speed = 1
        self.mouse = (-1, -1)
        self.new_game(disks)
        if solve:
            self.toggle_solver()

    # ------------------------------------------------------------ state

    def new_game(self, disks: int) -> None:
        self.towers = Towers(max(MIN_DISKS, min(MAX_DISKS, disks)))
        self.held: int | None = None
        self.dragging = False
        self.drag_x = 0.0
        self.flight: Flight | None = None
        self.flight_target: tuple[int, int] | None = None
        self.solving = False
        self.plan: list[Move] = []
        self.used_solver = False
        self.elapsed = 0.0
        self.won = False
        self.message: tuple[str, tuple[int, int, int], float] | None = None
        self.flash: tuple[int, float] | None = None
        self.hint: tuple[Move, float] | None = None
        self.confetti: list[Confetti] = []

    @property
    def layout(self) -> Layout:
        return Layout(*self.surface.get_size(), self.towers.disks)

    @property
    def busy(self) -> bool:
        return self.flight is not None

    def say(self, text: str, color=TEXT, seconds: float = MESSAGE_SECONDS) -> None:
        self.message = (text, color, seconds)

    # ------------------------------------------------------------ moves

    def fly(self, source: int, target: int, start: tuple[float, float] | None = None) -> None:
        """Animate the disk that has just moved from ``source`` to ``target``."""
        layout = self.layout
        disk = self.towers.pegs[target][-1]
        level = len(self.towers.pegs[target]) - 1
        if start is None:
            start = layout.slot(source, len(self.towers.pegs[source]))
        end = layout.slot(target, level)
        lift = layout.lifted(0)[1]
        points = [start]
        if start[1] > lift:
            points.append((start[0], lift))
        points += [(end[0], lift), end]
        speed = SPEEDS[self.speed] if self.solving else 1.5
        self.flight = Flight(disk, points, MOVE_SECONDS / speed)
        self.flight_target = (target, level)

    def pick(self, peg: int) -> None:
        if self.towers.top(peg) is None:
            self.say('This peg is empty.', MUTED)
            return
        self.held = peg
        self.drag_x = self.layout.peg_x(peg)

    def drop(self, target: int) -> None:
        source, self.held = self.held, None
        if source is None:
            return
        start = self.layout.lifted(self.drag_x if self.dragging else self.layout.peg_x(source))
        if source == target:
            return
        try:
            self.towers.move(source, target)
        except IllegalMove as error:
            self.say(str(error), ERROR)
            self.flash = (target, 0.5)
            return
        self.fly(source, target, start)

    def press_peg(self, peg: int) -> None:
        """A click or a 1 2 3 key: pick a disk up or put it down."""
        if self.won:
            return
        self.stop_solver()
        if self.busy:
            return
        if self.held is None:
            self.pick(peg)
        else:
            self.drop(peg)

    def undo(self) -> None:
        self.stop_solver()
        if self.busy or self.won:
            return
        self.held = None
        move = self.towers.undo()
        if move is None:
            self.say('Nothing to undo.', MUTED)
            return
        source, target = move
        self.fly(target, source)

    def show_hint(self) -> None:
        if self.won or self.busy:
            return
        self.held = None
        move = self.towers.hint()
        if move:
            self.hint = (move, 1.8)
            self.say(f'Move the top disk from peg {move[0] + 1} to peg {move[1] + 1}.', HINT)

    def toggle_solver(self) -> None:
        if self.solving:
            self.stop_solver()
            self.say('Solver paused.', MUTED)
            return
        if self.won:
            return
        self.held = None
        self.solving = True
        self.used_solver = True
        self.plan = []
        self.say(f'Solving: {len(self.towers.solution())} moves left. ← → change the speed.', TARGET)

    def stop_solver(self) -> None:
        self.solving = False
        self.plan = []

    def change_disks(self, delta: int) -> None:
        disks = self.towers.disks + delta
        if MIN_DISKS <= disks <= MAX_DISKS:
            self.new_game(disks)
            self.say(f'{disks} disks: at least {self.towers.minimum} moves.')

    # ------------------------------------------------------------ events

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            size = (max(MIN_SIZE[0], event.w), max(MIN_SIZE[1], event.h))
            self.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
            if self.flight:
                self._land()  # the path was computed for the old size
        elif event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
            if self.dragging:
                self.drag_x = event.pos[0]
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse = event.pos
            peg = self.layout.peg_at(event.pos[0])
            was_held = self.held is not None
            self.press_peg(peg)
            if not was_held and self.held is not None:
                self.dragging = True
                self.drag_x = event.pos[0]
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                peg = self.layout.peg_at(event.pos[0])
                if peg != self.held:
                    self.drop(peg)
                self.dragging = False
        elif event.type == pygame.KEYDOWN:
            self.key(event.key, event.mod)

    def key(self, key: int, mod: int = 0) -> None:
        pegs = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2,
                pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2}
        if key in pegs:
            self.dragging = False
            self.press_peg(pegs[key])
        elif key == pygame.K_SPACE:
            self.toggle_solver()
        elif key in (pygame.K_u, pygame.K_BACKSPACE) or (key == pygame.K_z and mod & pygame.KMOD_CTRL):
            self.undo()
        elif key == pygame.K_h:
            self.show_hint()
        elif key == pygame.K_r:
            self.new_game(self.towers.disks)
        elif key == pygame.K_n and self.won:
            self.change_disks(1 if self.towers.disks < MAX_DISKS else 0)
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.change_disks(1)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.change_disks(-1)
        elif key in (pygame.K_RIGHT, pygame.K_LEFT):
            step = 1 if key == pygame.K_RIGHT else -1
            self.speed = max(0, min(len(SPEEDS) - 1, self.speed + step))
            self.say(f'Solver speed ×{SPEEDS[self.speed]:g}', MUTED, 1.2)
        elif key == pygame.K_ESCAPE:
            if self.held is not None:
                self.held = None
                self.dragging = False
            else:
                self.running = False

    # ------------------------------------------------------------ time

    def _land(self) -> None:
        """Finish the current flight."""
        self.flight = None
        self.flight_target = None
        if self.towers.solved and not self.won:
            self.win()

    def win(self) -> None:
        self.won = True
        self.stop_solver()
        layout = self.layout
        for _ in range(120):
            self.confetti.append(Confetti(
                x=random.uniform(0, layout.width), y=random.uniform(-layout.height * 0.6, -10),
                vx=random.uniform(-40, 40), vy=random.uniform(80, 220),
                color=disk_color(random.randint(1, 8), 8), size=random.uniform(4, 9),
                spin=random.uniform(-6, 6)))

    def update(self, dt: float) -> None:
        if self.towers.moves and not self.won and not self.used_solver:
            self.elapsed += dt
        if self.flight:
            self.flight.time += dt
            if self.flight.done:
                self._land()
        if self.solving and not self.busy and not self.won:
            if not self.plan:
                self.plan = self.towers.solution()
            if self.plan:
                source, target = self.plan.pop(0)
                self.towers.move(source, target)
                self.fly(source, target)
        if self.message:
            text, color, left = self.message
            self.message = (text, color, left - dt) if left > dt else None
        if self.flash:
            self.flash = (self.flash[0], self.flash[1] - dt) if self.flash[1] > dt else None
        if self.hint:
            self.hint = (self.hint[0], self.hint[1] - dt) if self.hint[1] > dt else None
        height = self.surface.get_height()
        for piece in self.confetti:
            piece.x += piece.vx * dt
            piece.y += piece.vy * dt
            piece.angle += piece.spin * dt
        self.confetti = [piece for piece in self.confetti if piece.y < height + 20]

    # ------------------------------------------------------------ drawing

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self.fonts:
            font = pygame.font.SysFont('segoeui,helveticaneue,helvetica,arial,dejavusans', size, bold=bold)
            self.fonts[key] = font
        return self.fonts[key]

    def text(self, text: str, size: int, color, position, anchor: str = 'topleft', bold: bool = False) -> pygame.Rect:
        image = self.font(size, bold).render(text, True, color)
        rect = image.get_rect(**{anchor: position})
        self.surface.blit(image, rect)
        return rect

    def draw_disk(self, disk: int, center: tuple[float, float], layout: Layout, glow: bool = False) -> None:
        width, height = layout.disk_width(disk), layout.disk_height - 3
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (round(center[0]), round(center[1]))
        color = disk_color(disk, self.towers.disks)
        if glow:
            halo = rect.inflate(8, 8)
            pygame.draw.rect(self.surface, TARGET, halo, border_radius=int(height / 2) + 4, width=2)
        pygame.draw.rect(self.surface, color.lerp((0, 0, 0), 0.35), rect.move(0, 2), border_radius=int(height / 2))
        pygame.draw.rect(self.surface, color, rect, border_radius=int(height / 2))
        shine = pygame.Rect(rect.x + 6, rect.y + 3, max(0, rect.width - 12), max(2, height // 4))
        pygame.draw.rect(self.surface, color.lerp((255, 255, 255), 0.35), shine, border_radius=int(height / 4))
        if height >= 16:
            self.text(str(disk), int(height * 0.62), color.lerp((0, 0, 0), 0.55), rect.center, 'center', bold=True)

    def draw(self) -> None:
        layout = self.layout
        surface = self.surface
        surface.fill(BACKGROUND)

        # header
        self.text(TITLE, 30, TEXT, (24, 18), bold=True)
        towers = self.towers
        stats = [f'Disks {towers.disks}', f'Moves {towers.moves} / {towers.minimum}']
        if not self.used_solver:
            minutes, seconds = divmod(int(self.elapsed), 60)
            stats.append(f'Time {minutes}:{seconds:02d}')
        self.text('    '.join(stats), 20, MUTED, (layout.width - 24, 28), 'topright')

        # pegs and base
        pointing = self.mouse[0] >= 0 and pygame.mouse.get_focused()
        hover = layout.peg_at(self.mouse[0]) if pointing and not (self.won or self.solving) else None
        base = pygame.Rect(16, layout.base_y, layout.width - 32, 12)
        pygame.draw.rect(surface, PEG, base, border_radius=6)
        hint_move = self.hint[0] if self.hint else None
        for peg in range(PEGS):
            x = layout.peg_x(peg)
            color = PEG_HOVER if peg == hover else PEG
            if self.flash and self.flash[0] == peg:
                color = ERROR
            elif hint_move and peg in hint_move:
                color = HINT
            pole = pygame.Rect(0, 0, 12, layout.peg_height)
            pole.midbottom = (round(x), layout.base_y + 2)
            pygame.draw.rect(surface, color, pole, border_radius=6)
            goal = peg == towers.target
            self.text(f'{peg + 1} · goal' if goal else str(peg + 1), 18, TARGET if goal else MUTED,
                      (x, layout.base_y + 22), 'midtop')

        # disks at rest
        for peg, stack in enumerate(towers.pegs):
            for level, disk in enumerate(stack):
                if self.flight_target == (peg, level):
                    continue
                if self.held == peg and level == len(stack) - 1:
                    continue
                self.draw_disk(disk, layout.slot(peg, level), layout)

        # the disk in the hand and the flying one
        if self.held is not None:
            x = self.drag_x if self.dragging else layout.peg_x(self.held)
            self.draw_disk(towers.pegs[self.held][-1], layout.lifted(x), layout, glow=True)
        if self.flight:
            self.draw_disk(self.flight.disk, self.flight.position(), layout)

        # bottom line: a message or the help
        if self.message:
            text, color, _ = self.message
            self.text(text, 19, color, (layout.width / 2, layout.height - 22), 'center')
        else:
            line = '     '.join(HELP)
            size = 16 if layout.width >= 900 else 14
            self.text(line, size, MUTED, (layout.width / 2, layout.height - 22), 'center')

        if self.won:
            self.draw_victory(layout)
        for piece in self.confetti:
            rect = pygame.Rect(0, 0, piece.size, piece.size * (0.5 + 0.5 * abs(math.sin(piece.angle))))
            rect.center = (round(piece.x), round(piece.y))
            pygame.draw.rect(surface, piece.color, rect)

    def draw_victory(self, layout: Layout) -> None:
        towers = self.towers
        # over the two empty pegs, so the finished tower stays in sight
        others = [peg for peg in range(PEGS) if peg != towers.target]
        center_x = sum(layout.peg_x(peg) for peg in others) / len(others)
        panel = pygame.Rect(0, 0, min(500, layout.width * 2 / 3 - 40), 168)
        panel.center = (center_x, (layout.top + layout.base_y) / 2)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (*PANEL, 235), shade.get_rect(), border_radius=16)
        self.surface.blit(shade, panel)
        pygame.draw.rect(self.surface, SUCCESS, panel, width=2, border_radius=16)
        if self.used_solver:
            title, line = 'Solved by the computer', f'{towers.moves} moves'
        elif towers.moves == towers.minimum:
            title, line = 'Perfect!', f'{towers.moves} moves — the minimum possible'
        else:
            title, line = 'Solved!', f'{towers.moves} moves, the minimum is {towers.minimum}'
        self.text(title, 34, SUCCESS, (panel.centerx, panel.y + 22), 'midtop', bold=True)
        self.text(line, 21, TEXT, (panel.centerx, panel.y + 74), 'midtop')
        keys = 'N  next level     R  play again' if towers.disks < MAX_DISKS else 'R  play again'
        self.text(keys, 18, MUTED, (panel.centerx, panel.y + 120), 'midtop')

    # ------------------------------------------------------------ loop

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                self.handle(event)
            self.update(min(dt, 0.1))
            self.draw()
            pygame.display.flip()
        pygame.quit()
