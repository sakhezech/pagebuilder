import importlib
import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Iterable, Sequence
from pathlib import Path

from .__version__ import __version__
from .builder import PageBuilder, serve


def make_cli_parser() -> ArgumentParser:
    parser = ArgumentParser()

    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=__version__,
    )

    verbose_group = parser.add_mutually_exclusive_group()

    verbose_group.add_argument(
        '--logging',
        metavar='LEVEL',
        default='INFO',
        dest='logging',
        choices=logging.getLevelNamesMapping().keys(),
        help='logging level (defaults to INFO)',
    )

    verbose_group.add_argument(
        '--quiet',
        const='NOTSET',
        action='store_const',
        dest='logging',
        help='disable logging',
    )

    parser.add_argument(
        '-w',
        '--watch',
        metavar='ADDR',
        nargs='?',
        const='localhost:5000',
        default=None,
        help="watcher mode (serves by default on 'localhost:5000')",
    )

    parser.add_argument(
        '--serve-dir',
        type=Path,
        default=None,
        help="""
        directory to serve from
        (use if impossible to imply from where to serve)
        """,
    )

    return parser


def make_pagebuilder_cli_parser() -> ArgumentParser:
    parser = make_cli_parser()
    parser.prog = 'pagebuilder'
    parser.description = 'a static site generator i built'

    builder_select_group = parser.add_mutually_exclusive_group(required=True)

    builder_select_group.add_argument(
        '--args',
        metavar='ARG',
        nargs='*',
        help="""
        list of arguments for a builder in order 
        (pages_path,
        templates_path,
        assets_path (pass 'none' of no assets),
        dist_path,
        extension (defaults to '.html'),
        data_start (defaults to '---\\n'),
        data_end (defaults to '---\\n'))
        """,
    )

    builder_select_group.add_argument(
        '-b',
        '--builder',
        action='append',
        help="""
        builder instance or iteralbe of builders to run,
        in the format '<module>:<instance_or_iterable>'
        (can be used multiple times)
        """,
    )
    return parser


def setup_logging(args: Namespace) -> None:
    # TODO: temporary logging config, change later
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    logging.getLogger('pagebuilder').setLevel(args.logging)


def get_builders_from_args(args: Namespace) -> list[PageBuilder]:
    builders: list[PageBuilder] = []
    if args.builder:
        for builder_path in args.builder:
            import_path, _, builder_name = builder_path.partition(':')
            module = importlib.import_module(import_path)
            builder = getattr(module, builder_name, None)
            if isinstance(builder, PageBuilder):
                builders.append(builder)
            elif isinstance(builder, Iterable):
                for b in builder:
                    if not isinstance(b, PageBuilder):
                        raise ValueError(f'not a builder: {b}')
                builders.extend(builder)
            else:
                raise ValueError(
                    f'not a builder or an iterable of builders: {builder}'
                )
    else:
        if not 4 <= len(args.args) <= 7:
            raise ValueError(
                'number of arguments should be between '
                f'4 and 7: {len(args.args)}'
            )
        kwargs = dict(
            zip(
                (
                    'pages_path',
                    'templates_path',
                    'assets_path',
                    'dist_path',
                    'ext',
                    'data_start',
                    'data_end',
                ),
                args.args,
            )
        )
        if 'assets_path' in kwargs and kwargs['assets_path'].lower() == 'none':
            kwargs['assets_path'] = None

        builder = PageBuilder(**kwargs)
        builders.append(builder)

    return builders


def run_builders(builders: list[PageBuilder], args: Namespace) -> None:
    # if the builders dist_paths are nested
    # and a builder with a lower dist_path is processed later
    # it will delete what builders above did
    builders.sort(key=lambda b: b.dist_path)

    if args.watch:
        if not args.serve_dir:
            if len(builders) == 1:
                args.serve_dir = builders[0].dist_path
            else:
                raise ValueError(
                    'with 2 or more builders and no --serve-dir '
                    'impossible to imply from where to serve'
                )

        addr, _, port = args.watch.partition(':')
        try:
            for builder in builders:
                builder.observe()
            serve(addr, int(port), args.serve_dir)
        finally:
            for builder in builders:
                builder.stop_observing()
    else:
        for builder in builders:
            builder.build()


def pagebuilder_cli(argv: Sequence[str] | None = None) -> None:
    args = make_pagebuilder_cli_parser().parse_args(argv)
    setup_logging(args)
    builders = get_builders_from_args(args)
    run_builders(builders, args)


if __name__ == '__main__':
    pagebuilder_cli()
