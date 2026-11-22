"""The puzzle itself: pegs, legal moves, undo and the optimal solution from any position.

Disks are numbered by size: 1 is the smallest. Every peg is a list from the
bottom disk to the top one.

>>> towers = Towers(3)
>>> towers.pegs
[[3, 2, 1], [], []]
>>> towers.move(0, 2)
1
>>> towers.move(0, 2)
Traceback (most recent call last):
...
honoi.towers.IllegalMove: Disk 2 can't go on the smaller disk 1.
>>> len(towers.solution()), towers.minimum
(6, 7)
"""

from __future__ import annotations

from typing import Sequence

PEGS = 3
MIN_DISKS = 1
MAX_DISKS = 10

Move = tuple[int, int]


class IllegalMove(ValueError):
    """A move that breaks the rules: from an empty peg or onto a smaller disk."""


def classic_solution(disks: int, source: int = 0, target: int = 2) -> list[Move]:
    """The ``2ⁿ − 1`` moves that carry a tower of ``disks`` from ``source`` to ``target``.

    >>> classic_solution(2)
    [(0, 1), (0, 2), (1, 2)]
    """
    if disks <= 0:
        return []
    spare = PEGS - source - target
    return (classic_solution(disks - 1, source, spare) + [(source, target)]
            + classic_solution(disks - 1, spare, target))


def solution_from(pegs: Sequence[Sequence[int]], target: int = 2) -> list[Move]:
    """The shortest sequence of moves from any legal position to the whole tower on ``target``.

    The largest disk that is not on the target has to get there. Before that,
    all smaller disks go to the third peg. This gives the optimal answer from
    every position, not only from the start.

    >>> solution_from([[3], [2, 1], []])
    [(0, 2), (1, 0), (1, 2), (0, 2)]
    """
    where = {disk: peg for peg, stack in enumerate(pegs) for disk in stack}
    moves: list[Move] = []

    def place(disk: int, to: int) -> None:
        if disk == 0:
            return
        if where[disk] == to:
            place(disk - 1, to)
            return
        other = PEGS - where[disk] - to
        place(disk - 1, other)
        moves.append((where[disk], to))
        where[disk] = to
        place(disk - 1, to)

    place(len(where), target)
    return moves


class Towers:
    """Three pegs with ``disks`` disks, all of them on the first peg at the start."""

    def __init__(self, disks: int = 4, target: int = 2):
        if not isinstance(disks, int) or not MIN_DISKS <= disks <= MAX_DISKS:
            raise ValueError(f'The number of disks must be from {MIN_DISKS} to {MAX_DISKS}.')
        if target not in range(1, PEGS):
            raise ValueError('The target peg must be 1 or 2.')
        self.disks = disks
        self.target = target
        self.pegs: list[list[int]] = [list(range(disks, 0, -1)), [], []]
        self.history: list[Move] = []

    @property
    def moves(self) -> int:
        return len(self.history)

    @property
    def minimum(self) -> int:
        """Moves needed from the start: ``2ⁿ − 1``."""
        return 2 ** self.disks - 1

    @property
    def solved(self) -> bool:
        return len(self.pegs[self.target]) == self.disks

    def top(self, peg: int) -> int | None:
        stack = self.pegs[peg]
        return stack[-1] if stack else None

    def check(self, source: int, target: int) -> None:
        """Raise :class:`IllegalMove` if the top disk of ``source`` can't go to ``target``."""
        if source not in range(PEGS) or target not in range(PEGS):
            raise IllegalMove('There are only three pegs.')
        disk = self.top(source)
        if disk is None:
            raise IllegalMove('This peg is empty.')
        below = self.top(target)
        if below is not None and below < disk and source != target:
            raise IllegalMove(f"Disk {disk} can't go on the smaller disk {below}.")

    def can_move(self, source: int, target: int) -> bool:
        try:
            self.check(source, target)
        except IllegalMove:
            return False
        return source != target

    def move(self, source: int, target: int) -> int:
        """Move the top disk and return it. Moving a disk back onto its own peg is not a move."""
        self.check(source, target)
        if source == target:
            return self.top(source)
        disk = self.pegs[source].pop()
        self.pegs[target].append(disk)
        self.history.append((source, target))
        return disk

    def undo(self) -> Move | None:
        """Take the last move back and return it, ``None`` at the start."""
        if not self.history:
            return None
        source, target = self.history.pop()
        self.pegs[source].append(self.pegs[target].pop())
        return source, target

    def solution(self) -> list[Move]:
        """The shortest way to finish from the current position."""
        return solution_from(self.pegs, self.target)

    def hint(self) -> Move | None:
        """The next move of the shortest solution."""
        moves = self.solution()
        return moves[0] if moves else None
