"""Tower of Hanoi: a pygame game with an animated solver.

The rules and the solver are in :mod:`honoi.towers` and do not need pygame.
"""

from .towers import IllegalMove, Towers, classic_solution, solution_from

__version__ = '1.0.0'

__all__ = ['IllegalMove', 'Towers', 'classic_solution', 'solution_from']
