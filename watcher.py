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

from generate import Generator

type StrPath = PathLike[str] | str


class PagesHandler(FileSystemEventHandler):
    def __init__(self, generator: Generator) -> None:
        super().__init__()
        self.generator = generator

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

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        self.on_created_or_modified(event)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        self.on_created_or_modified(event)


class TemplateHandler(FileSystemEventHandler):
    def __init__(self, generator: Generator) -> None:
        super().__init__()
        self.generator = generator

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
            if page.template_stack is None:
                raise ValueError
            if template.name in page.template_stack:
                self.generator.save_page(page)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        template = self.generator.add_template(path)
        self.generator.templates.pop(template.name)

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        self.on_created_or_modified(event)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        self.on_created_or_modified(event)


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
        generator = Generator(
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
