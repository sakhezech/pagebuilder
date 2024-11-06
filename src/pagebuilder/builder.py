import functools
import http.server
import shutil
from os import PathLike
from pathlib import Path
from typing import Any, Self

import combustache
import yaml
from watchdog.observers import Observer

from .watcher import AssetHandler, PagesHandler, TemplateHandler

type StrPath = PathLike[str] | str


class PageBuilder:
    def __init__(
        self,
        pages_path: Path,
        templates_path: Path,
        assets_path: Path,
        dist_path: Path,
        data_start: str = '<!-- YAML:\n',
        data_end: str = '-->\n',
        ext: str = '.html',
    ) -> None:
        self.pages_path = pages_path
        self.templates_path = templates_path
        self.assets_path = assets_path
        self.dist_path = dist_path

        self.ext = ext
        self.data_start = data_start
        self.data_end = data_end

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
        shutil.copytree(self.assets_path, self.dist_path, dirs_exist_ok=True)

    def observe(self) -> None:
        self.build()

        self._observer = Observer()
        pages_handler = PagesHandler(self)
        template_handler = TemplateHandler(self)
        asset_handler = AssetHandler(self)

        self._observer.schedule(
            pages_handler,
            str(self.pages_path),
            recursive=True,
        )
        self._observer.schedule(
            template_handler,
            str(self.templates_path),
            recursive=True,
        )
        self._observer.schedule(
            asset_handler,
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
        self.template_stack = self.make_template_stack()
        self.save_path = self.get_save_path()

    def render(self) -> str:
        templates = self.builder.templates
        merged_data = self.data
        merged_data['slot'] = combustache.render(self.content, self.data)

        for template_name in self.template_stack:
            template = templates[template_name]
            merged_data = template.data | merged_data
            merged_data['slot'] = combustache.render(
                template.content, merged_data
            )
        return merged_data['slot']

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_path.write_text(self.render())

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
            data_end = raw_txt.find(builder.data_end)
            txt_start = data_end + len(builder.data_end)

            data_txt = raw_txt[data_start:data_end]
            data = yaml.load(data_txt, yaml.Loader)
            txt = raw_txt[txt_start:]
        else:
            data = {}
            txt = raw_txt

        return cls(txt, data, rel_path, builder)

    def make_template_stack(self) -> list[str]:
        dependencies: list[str] = []
        templates = self.builder.templates
        curr = self
        while curr.data.get('template', None):
            template_name = curr.data['template']
            dependencies.append(template_name)
            curr = templates[template_name]
        return dependencies

    def get_save_path(self) -> Path:
        dist_path = self.builder.dist_path
        if self.name == 'index':
            output_dir_path = dist_path / self.relative_path.parent
        else:
            output_dir_path = dist_path / self.relative_path.parent / self.name

        return output_dir_path / 'index.html'


def serve(addr: str, port: int, directory: StrPath) -> None:
    MyHandler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory),
    )
    with http.server.ThreadingHTTPServer((addr, port), MyHandler) as httpd:
        httpd.serve_forever()
