import itertools
import random

import pytest

from honoi import IllegalMove, Towers, classic_solution, solution_from


@pytest.mark.parametrize('disks', range(1, 11))
def test_classic_solution_is_minimal_and_legal(disks):
    towers = Towers(disks)
    moves = classic_solution(disks)
    assert len(moves) == 2 ** disks - 1 == towers.minimum
    for move in moves:
        towers.move(*move)
    assert towers.solved
    assert towers.pegs == [[], [], list(range(disks, 0, -1))]


def test_solution_from_start_equals_classic():
    assert Towers(6).solution() == classic_solution(6)


def all_positions(disks):
    """Every legal position: each disk on any peg, stacks sorted."""
    for pegs_of in itertools.product(range(3), repeat=disks):
        pegs = [[], [], []]
        for disk in range(disks, 0, -1):
            pegs[pegs_of[disk - 1]].append(disk)
        yield pegs


def shortest_distances(disks, target=2):
    """Breadth-first search from the goal: the true shortest distance to every position."""
    def key(pegs):
        return tuple(map(tuple, pegs))

    goal = [[], [], []]
    goal[target] = list(range(disks, 0, -1))
    distance = {key(goal): 0}
    queue = [goal]
    for pegs in queue:
        for a, b in itertools.permutations(range(3), 2):
            if pegs[a] and (not pegs[b] or pegs[b][-1] > pegs[a][-1]):
                nxt = [list(p) for p in pegs]
                nxt[b].append(nxt[a].pop())
                if key(nxt) not in distance:
                    distance[key(nxt)] = distance[key(pegs)] + 1
                    queue.append(nxt)
    return distance


@pytest.mark.parametrize('disks', [1, 2, 3, 4, 5])
def test_solution_from_any_position_is_optimal(disks):
    distance = shortest_distances(disks)
    assert len(distance) == 3 ** disks
    for pegs in all_positions(disks):
        moves = solution_from(pegs)
        assert len(moves) == distance[tuple(map(tuple, pegs))]
        towers = Towers(disks)
        towers.pegs = [list(p) for p in pegs]
        for move in moves:
            towers.move(*move)
        assert towers.solved


def test_other_target():
    towers = Towers(3, target=1)
    for move in towers.solution():
        towers.move(*move)
    assert towers.pegs[1] == [3, 2, 1]


def test_rules():
    towers = Towers(3)
    with pytest.raises(IllegalMove, match='empty'):
        towers.move(1, 2)
    towers.move(0, 1)
    with pytest.raises(IllegalMove, match='smaller'):
        towers.move(0, 1)
    with pytest.raises(IllegalMove):
        towers.move(0, 5)
    assert not towers.can_move(0, 1)
    assert towers.can_move(1, 2)
    assert towers.moves == 1


def test_same_peg_is_not_a_move():
    towers = Towers(3)
    assert towers.move(0, 0) == 1
    assert towers.moves == 0


def test_undo():
    towers = Towers(3)
    assert towers.undo() is None
    towers.move(0, 2)
    towers.move(0, 1)
    assert towers.undo() == (0, 1)
    assert towers.pegs == [[3, 2], [], [1]]
    assert towers.moves == 1


def test_hint_after_random_play():
    rng = random.Random(1)
    towers = Towers(5)
    for _ in range(40):
        legal = [(a, b) for a in range(3) for b in range(3) if towers.can_move(a, b)]
        towers.move(*rng.choice(legal))
    played = towers.moves
    while not towers.solved:
        towers.move(*towers.hint())
    assert towers.hint() is None
    assert towers.moves - played <= towers.minimum


@pytest.mark.parametrize('disks, target', [(0, 2), (11, 2), (3, 0), (3, 3), (2.5, 2)])
def test_invalid(disks, target):
    with pytest.raises(ValueError):
        Towers(disks, target)
