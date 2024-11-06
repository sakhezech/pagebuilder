import shutil
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING

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

type StrPath = PathLike[str] | str

if TYPE_CHECKING:
    from .builder import PageBuilder


class WatcherFileSystemEventHandler(FileSystemEventHandler):
    def __init__(self, generator: 'PageBuilder') -> None:
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
        real_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, real_path)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        self.to_real_path(path).unlink()
