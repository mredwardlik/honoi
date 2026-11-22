import os

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame  # noqa: E402
import pytest  # noqa: E402

from honoi import solution_from  # noqa: E402
from honoi.cli import build_parser  # noqa: E402
from honoi.game import Game, Layout  # noqa: E402


@pytest.fixture
def game():
    game = Game(3, (960, 600))
    yield game
    pygame.quit()


def settle(game, seconds=1.0):
    for _ in range(int(seconds * 60)):
        game.update(1 / 60)
        game.draw()


def click(game, peg, release=True):
    x = int(game.layout.peg_x(peg))
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, 300)))
    if release:
        game.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(x, 300)))


def test_keys_move_disks(game):
    game.key(pygame.K_1)
    assert game.held == 0
    game.key(pygame.K_3)
    assert game.towers.pegs == [[3, 2], [], [1]]
    settle(game)
    assert game.flight is None


def test_click_click(game):
    click(game, 0)
    assert game.held == 0
    click(game, 1)
    assert game.towers.pegs[1] == [1]


def test_drag_and_drop(game):
    click(game, 0, release=False)
    target = (int(game.layout.peg_x(2)), 300)
    game.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=target, rel=(0, 0), buttons=(1, 0, 0)))
    assert game.drag_x == target[0]
    game.draw()
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=target))
    assert game.towers.pegs[2] == [1]


def test_illegal_move_is_refused(game):
    game.key(pygame.K_1)
    game.key(pygame.K_2)
    settle(game)
    game.key(pygame.K_1)
    game.key(pygame.K_2)
    assert game.towers.pegs == [[3, 2], [1], []]
    assert game.held is None
    assert "can't go" in game.message[0]
    game.draw()


def test_empty_peg(game):
    game.key(pygame.K_2)
    assert game.held is None
    assert 'empty' in game.message[0]


def test_input_ignored_while_flying(game):
    game.key(pygame.K_1)
    game.key(pygame.K_3)
    game.key(pygame.K_1)
    assert game.held is None
    settle(game)


def test_undo(game):
    game.key(pygame.K_1)
    game.key(pygame.K_3)
    settle(game)
    game.key(pygame.K_u)
    assert game.towers.pegs[0] == [3, 2, 1]
    settle(game)


def test_player_wins(game):
    for source, target in game.towers.solution():
        game.key(pygame.K_1 + source)
        game.key(pygame.K_1 + target)
        settle(game, 0.4)
    assert game.won and not game.used_solver
    assert game.towers.moves == 7
    game.key(pygame.K_n)
    assert game.towers.disks == 4 and not game.won


def test_solver_from_the_middle(game):
    game.key(pygame.K_1)
    game.key(pygame.K_2)
    settle(game)
    left = len(solution_from(game.towers.pegs))
    game.key(pygame.K_SPACE)
    assert game.solving
    settle(game, 10)
    assert game.won and game.used_solver
    assert game.towers.moves == 1 + left


def test_solver_pause_and_speed(game):
    game.key(pygame.K_RIGHT)
    game.key(pygame.K_RIGHT)
    assert game.speed == 3
    game.key(pygame.K_SPACE)
    settle(game, 0.2)
    game.key(pygame.K_SPACE)
    assert not game.solving
    moves = game.towers.moves
    settle(game, 1)
    assert game.towers.moves == moves


def test_hint(game):
    game.key(pygame.K_h)
    assert game.hint[0] == (0, 2)
    game.draw()


def test_disks_and_restart(game):
    game.key(pygame.K_PLUS)
    assert game.towers.disks == 4
    game.key(pygame.K_MINUS)
    game.key(pygame.K_MINUS)
    assert game.towers.disks == 2
    game.key(pygame.K_1)
    game.key(pygame.K_2)
    game.key(pygame.K_r)
    assert game.towers.moves == 0


def test_resize_and_quit(game):
    game.handle(pygame.event.Event(pygame.VIDEORESIZE, w=300, h=200, size=(300, 200)))
    assert game.surface.get_size() == (640, 420)
    game.draw()
    game.key(pygame.K_ESCAPE)
    assert not game.running


@pytest.mark.parametrize('disks', [1, 10])
def test_layout_fits(disks):
    for size in [(640, 420), (960, 600), (1920, 1080)]:
        layout = Layout(*size, disks)
        assert layout.lift_y > layout.top
        assert layout.disk_width(disks) <= size[0] / 3
        assert layout.disk_width(1) >= 30


def test_cli_arguments():
    parser = build_parser()
    args = parser.parse_args(['-d', '7', '--size', '1280x720', '--solve'])
    assert (args.disks, args.size, args.solve) == (7, (1280, 720), True)
    for wrong in (['-d', '0'], ['-d', '11'], ['--size', '100x100'], ['--size', 'big']):
        with pytest.raises(SystemExit):
            parser.parse_args(wrong)
