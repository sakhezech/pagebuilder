import functools
import http.server
import shutil
from os import PathLike
from pathlib import Path
from typing import Self

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from .builder import Page, PageBuilder, make_template_stack

type StrPath = PathLike[str] | str


class PageBuilderWatcher(PageBuilder):
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
        super().__init__(
            pages_path,
            templates_path,
            assets_path,
            dist_path,
            data_start,
            data_end,
            ext,
        )

        self.pages: dict[Path, Page] = {}
        self.template_stacks_of_pages: dict[Page, list[str]] = {}
        for page_path in self.pages_path.rglob(f'**/*{self.ext}'):
            self.add_page(page_path)

    def add_page(self, page_path: Path) -> 'Page':
        page = Page.load(
            page_path,
            self.pages_path,
            self.data_start,
            self.data_end,
            self.ext,
        )
        self.template_stacks_of_pages[page] = make_template_stack(
            page,
            self.templates,
        )

        self.pages[page_path] = page
        return page

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


class WatcherFileSystemEventHandler(FileSystemEventHandler):
    def __init__(self, generator: PageBuilderWatcher) -> None:
        super().__init__()
        self.builder = generator

    def on_created_or_modified(
        self,
        event: FileCreatedEvent
        | FileModifiedEvent
        | DirCreatedEvent
        | DirModifiedEvent,
    ) -> None:
        pass

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        if not event.is_directory:
            self.on_deleted(
                FileDeletedEvent(event.src_path, is_synthetic=True)
            )
            self.on_created_or_modified(
                FileCreatedEvent(event.dest_path, is_synthetic=True)
            )
        else:
            self.on_deleted(DirDeletedEvent(event.src_path, is_synthetic=True))
            self.on_created_or_modified(
                DirCreatedEvent(event.dest_path, is_synthetic=True)
            )

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        self.on_created_or_modified(event)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        self.on_created_or_modified(event)


class PagesHandler(WatcherFileSystemEventHandler):
    def on_created_or_modified(
        self,
        event: FileCreatedEvent
        | FileModifiedEvent
        | DirCreatedEvent
        | DirModifiedEvent,
    ) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        page = self.builder.add_page(path)
        self.builder.save_page(page)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        page = self.builder.pages.pop(path)
        page.get_save_path(self.builder.dist_path).unlink()
        del self.builder.template_stacks_of_pages[page]


class TemplateHandler(WatcherFileSystemEventHandler):
    def on_created_or_modified(
        self,
        event: FileCreatedEvent
        | FileModifiedEvent
        | DirCreatedEvent
        | DirModifiedEvent,
    ) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        template = self.builder.add_template(path)
        for page in self.builder.pages.values():
            if template.name in self.builder.template_stacks_of_pages[page]:
                self.builder.save_page(page)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        template = self.builder.add_template(path)
        self.builder.templates.pop(template.name)


class AssetHandler(WatcherFileSystemEventHandler):
    def to_real_path(self, path: Path) -> Path:
        return self.builder.dist_path / path.relative_to(
            self.builder.assets_path
        )

    def on_created_or_modified(
        self,
        event: FileCreatedEvent
        | FileModifiedEvent
        | DirCreatedEvent
        | DirModifiedEvent,
    ) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        real_path = self.to_real_path(path)
        real_path.parent.mkdir(exist_ok=True)
        shutil.copy2(path, real_path)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        self.to_real_path(path).unlink()


def serve(addr: str, port: int, directory: StrPath) -> None:
    MyHandler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory),
    )
    with http.server.ThreadingHTTPServer((addr, port), MyHandler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    builder = PageBuilderWatcher(
        Path('./pages/'),
        Path('./templates/'),
        Path('./assets/'),
        Path('./dist/'),
    )
    with builder:
        serve('localhost', 5000, builder.dist_path)
