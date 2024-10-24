import functools
import http.server
from os import PathLike
from pathlib import Path

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from generate import Generator, Page, make_template_stack

type StrPath = PathLike[str] | str


class WatcherGenerator(Generator):
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


class WatcherFileSystemEventHandler(FileSystemEventHandler):
    def __init__(self, generator: WatcherGenerator) -> None:
        super().__init__()
        self.generator = generator

    def on_created_or_modified(
        self,
        event: FileCreatedEvent
        | FileModifiedEvent
        | DirCreatedEvent
        | DirModifiedEvent,
    ) -> None:
        pass

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
        page = self.generator.add_page(path)
        self.generator.save_page(page)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        page = self.generator.pages.pop(path)
        page.get_save_path(self.generator.dist_path).unlink()
        del self.generator.template_stacks_of_pages[page]


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
        template = self.generator.add_template(path)
        for page in self.generator.pages.values():
            if template.name in self.generator.template_stacks_of_pages[page]:
                self.generator.save_page(page)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        template = self.generator.add_template(path)
        self.generator.templates.pop(template.name)


def serve(addr: str, port: int, directory: StrPath) -> None:
    MyHandler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory),
    )
    with http.server.ThreadingHTTPServer((addr, port), MyHandler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    observer = Observer()
    try:
        generator = WatcherGenerator(
            Path('./pages/'),
            Path('./templates/'),
            Path('./assets/'),
            Path('./dist/'),
        )
        generator.generate()

        pages_handler = PagesHandler(generator)
        template_handler = TemplateHandler(generator)

        observer.schedule(
            pages_handler,
            str(generator.pages_path),
            recursive=True,
        )
        observer.schedule(
            template_handler,
            str(generator.templates_path),
            recursive=True,
        )
        observer.start()

        serve('localhost', 5000, 'dist')
    finally:
        observer.stop()
        observer.join()
