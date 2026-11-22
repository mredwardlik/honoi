"""Command line entry point: ``honoi [--disks N] [--solve]``."""

from __future__ import annotations

import argparse
from typing import Sequence

from . import __version__
from .towers import MAX_DISKS, MIN_DISKS


def window_size(text: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in text.lower().split('x'))
    except ValueError:
        raise argparse.ArgumentTypeError('use WIDTHxHEIGHT, for example 1280x720') from None
    if width < 640 or height < 420:
        raise argparse.ArgumentTypeError('the window must be at least 640x420')
    return width, height


def disks(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError('must be a number') from None
    if not MIN_DISKS <= value <= MAX_DISKS:
        raise argparse.ArgumentTypeError(f'must be from {MIN_DISKS} to {MAX_DISKS}')
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='honoi',
        description='Tower of Hanoi: move the tower to the goal peg, one disk at a time, '
                    'never a larger disk on a smaller one.',
    )
    parser.add_argument('-d', '--disks', type=disks, default=4, metavar='N',
                        help=f'number of disks, {MIN_DISKS}-{MAX_DISKS} (default: 4)')
    parser.add_argument('-s', '--solve', action='store_true', help='start with the solver running')
    parser.add_argument('--size', type=window_size, default=(960, 600), metavar='WxH',
                        help='window size (default: 960x600)')
    parser.add_argument('-V', '--version', action='version', version=f'%(prog)s {__version__}')
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .game import Game  # pygame prints a banner on import: only when the game starts

    Game(args.disks, args.size, args.solve).run()
    return 0
