import functools
import http.server
import logging
import shutil
from collections.abc import Callable
from os import PathLike
from pathlib import Path
from typing import Any, Self

import combustache
import yaml
from watchdog.observers import Observer

from .watcher import AssetHandler, PagesHandler, TemplateHandler

type StrPath = PathLike[str] | str

logger = logging.getLogger('pagebuilder')


class PageBuilder:
    def __init__(
        self,
        pages_path: StrPath,
        templates_path: StrPath,
        assets_path: StrPath | None,
        dist_path: StrPath,
        *,
        ext: str = '.html',
        data_start: str = '---\n',
        data_end: str = '---\n',
        shared_data: dict[str, Any] | None = None,
        render_func: Callable[[str, dict[str, Any]], str] | None = None,
    ) -> None:
        self.pages_path = Path(pages_path)
        self.templates_path = Path(templates_path)
        self.assets_path = Path(assets_path) if assets_path else None
        self.dist_path = Path(dist_path)

        self.ext = ext
        self.data_start = data_start
        self.data_end = data_end
        self.shared_data = shared_data or {}
        self.render_func = render_func or combustache.render

        self.templates: dict[str, Page] = {}
        for template_path in self.templates_path.rglob(f'**/*{self.ext}'):
            self.add_template(template_path)

        self.pages: dict[Path, Page] = {}
        for page_path in self.pages_path.rglob(f'**/*{self.ext}'):
            self.add_page(page_path)

    def add_page(self, page_path: Path) -> 'Page':
        page = Page.load(page_path, self.pages_path, self)
        self.pages[page_path] = page
        return page

    def add_template(self, template_path: Path) -> 'Page':
        template = Page.load(template_path, self.templates_path, self)
        self.templates[template.name] = template
        return template

    def build(self) -> None:
        shutil.rmtree(self.dist_path, ignore_errors=True)
        for page in self.pages.values():
            page.save()
        if self.assets_path:
            shutil.copytree(
                self.assets_path, self.dist_path, dirs_exist_ok=True
            )

    def observe(self) -> None:
        self.build()

        self._observer = Observer()

        self._observer.schedule(
            PagesHandler(self),
            str(self.pages_path),
            recursive=True,
        )
        self._observer.schedule(
            TemplateHandler(self),
            str(self.templates_path),
            recursive=True,
        )
        if self.assets_path:
            self._observer.schedule(
                AssetHandler(self),
                str(self.assets_path),
                recursive=True,
            )

        self._observer.start()

    def stop_observing(self) -> None:
        self._observer.stop()
        self._observer.join()

    def __enter__(self) -> Self:
        self.observe()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop_observing()


class Page:
    def __init__(
        self,
        content: str,
        data: dict[str, Any],
        path: Path,
        builder: PageBuilder,
    ) -> None:
        self.content = content
        self.data = data
        self.builder = builder
        self.relative_path = path
        self.name = self.relative_path.name.removesuffix(self.builder.ext)
        self.template_stack: list[str] = []

        curr = self
        while True:
            template_name = curr.data.get('template', None)
            if not template_name:
                break
            if template_name not in self.builder.templates:
                raise KeyError(f"template doesn't exist: {template_name}")
            self.template_stack.append(template_name)
            curr = self.builder.templates[template_name]

        output_dir_path = self.builder.dist_path / self.relative_path.parent
        if self.name != 'index':
            output_dir_path /= self.name
        self.save_path = output_dir_path / 'index.html'

    def render(self) -> str:
        # NOTE: we merge the builder shared data here so we can freely
        # modify it whenever we please by hooks or any other means
        data = self.builder.shared_data | self.data
        for template_name in self.template_stack:
            if template_name not in self.builder.templates:
                raise KeyError(f"template doesn't exist: {template_name}")
            template = self.builder.templates[template_name]
            data = template.data | data

        data['slot'] = self.builder.render_func(self.content, data)
        for template_name in self.template_stack:
            template = self.builder.templates[template_name]
            data['slot'] = self.builder.render_func(template.content, data)
        return data['slot']

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_path.write_text(self.render())
        logger.info(f'page saved: {self.save_path}')

    @classmethod
    def load(
        cls,
        path: Path,
        relative_to: Path,
        builder: PageBuilder,
    ) -> Self:
        rel_path = path.relative_to(relative_to)
        raw_txt = path.read_text()

        if raw_txt.startswith(builder.data_start):
            data_start = len(builder.data_start)
            data_end = raw_txt.find(builder.data_end, data_start)
            txt_start = data_end + len(builder.data_end)

            data_txt = raw_txt[data_start:data_end]
            data = yaml.load(data_txt, yaml.Loader)
            if not isinstance(data, dict):
                logger.debug(
                    f'page data is not a dictionary; skipping: {path}; {data}'
                )
                data = {}
            txt = raw_txt[txt_start:]
        else:
            data = {}
            txt = raw_txt

        return cls(txt, data, rel_path, builder)


http_logger = logging.getLogger('pagebuilder.http')


class LoggingHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        message = (format % args).translate(self._control_char_table)  # pyright: ignore[reportAttributeAccessIssue]
        http_logger.debug(message)


def serve(addr: str, port: int, directory: StrPath) -> None:
    MyHandler = functools.partial(
        LoggingHTTPRequestHandler, directory=str(directory)
    )
    with http.server.ThreadingHTTPServer((addr, port), MyHandler) as httpd:
        httpd.serve_forever()
