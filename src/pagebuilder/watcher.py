import logging
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


logger = logging.getLogger('pagebuilder')


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
        logger.info(f'page changed: {path}')
        try:
            page = self.builder.add_page(path)
            page.save()
        # NOTE: we have to except everything here
        # we have no idea what exceptions can the custom functions throw
        # for example an incomplete markup can throw an exception while parsing
        # or something along those lines
        except Exception as err:
            logger.error(err.args[0])

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        page = self.builder.pages.pop(path)
        page.save_path.unlink()
        logger.info(f'page deleted: {path}')


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
        logger.info(f'template changed: {path}')
        for page in self.builder.pages.values():
            if template.name in page.template_stack:
                page.save()

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        name = path.name.removesuffix(self.builder.ext)
        del self.builder.templates[name]
        logger.info(f'template deleted: {path}')


class AssetHandler(WatcherFileSystemEventHandler):
    def to_real_path(self, path: Path) -> Path:
        if not self.builder.assets_path:
            raise ValueError(
                'an AssetHandler was created '
                'and scheduled without assets_path'
            )
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
        logger.info(f'asset copied: {path}')

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        self.to_real_path(path).unlink()
        logger.info(f'asset deleted: {path}')
