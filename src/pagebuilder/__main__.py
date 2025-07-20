import argparse
from collections.abc import Sequence
from pathlib import Path

from . import PageBuilder
from .__version__ import __version__


def hostportify(string: str) -> tuple[str, int]:
    host, _, port_str = string.partition(':')
    port = int(port_str)
    return (host, port)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--version', action='version', version=__version__
    )

    parser.add_argument('pages_path', type=Path)
    parser.add_argument('templates_path', type=Path)
    parser.add_argument('assets_path', type=Path)
    parser.add_argument('dist_path', type=Path)

    parser.add_argument('--ext', default='.html')
    parser.add_argument('--data-start', default='---\n')
    parser.add_argument('--data-end', default='---\n')

    parser.add_argument('--serve', type=hostportify)
    parser.add_argument('--ws', type=hostportify)

    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)

    PageBuilder(
        args.pages_path,
        args.templates_path,
        args.assets_path,
        args.dist_path,
        args.serve,
        args.ws,
        args.ext,
        args.data_start,
        args.data_end,
    ).run(bool(args.serve))


if __name__ == '__main__':
    cli(None)
