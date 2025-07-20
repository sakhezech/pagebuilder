import dataclasses
import shutil
from pathlib import Path
from typing import Any

import combustache
import coreca
import coreca.lifespans
import yaml


class Hello:
    def __init__(self, string: str, ds: str, de: str) -> None:
        if string.startswith(ds):
            ds_i = len(ds)
            de_i = string.find(de, ds_i)
            if de_i == -1:
                raise ValueError('frontmatter not closed')
            ts_i = de_i + len(de)

            data = yaml.load(string[ds_i:de_i], yaml.Loader)
            text = string[ts_i:]
        else:
            data = {}
            text = string

        self.data = data or {}
        self.text = text

    def update_deps(self, templates: dict[str, 'Template']) -> None:
        self.deps = []
        curr = self
        while curr:
            template_name = curr.data.get('template', None)
            if not template_name:
                break
            curr = templates.get(template_name, None)
            if not curr:
                break
            self.deps.append(template_name)


class Page(Hello):
    def __init__(
        self, path: Path, pages_path: Path, dist_path: Path, ds: str, de: str
    ) -> None:
        super().__init__(path.read_text(), ds, de)
        if path.name == 'index.html':
            self.out_path = dist_path / path.relative_to(pages_path)
        else:
            self.out_path = (
                dist_path
                / path.relative_to(pages_path).with_suffix('')
                / 'index.html'
            )

    def render(self, data: dict, templates: dict[str, 'Template']) -> str:
        data = self.data | data  # NOTE: idk
        data['slot'] = combustache.render(self.text, data)
        for template_name in self.deps:
            template = templates[template_name]
            data = template.data | data
            data['slot'] = combustache.render(template.text, data)
        return data['slot']

    def save(self, data: dict, templates: dict[str, 'Template']) -> None:
        text = self.render(data, templates)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.out_path.write_text(text)


class Template(Hello):
    def __init__(self, path: Path, ext: str, ds: str, de: str) -> None:
        super().__init__(path.read_text(), ds, de)
        self.name = path.name.removesuffix(ext)


@dataclasses.dataclass
class State:
    pages_path: Path
    templates_path: Path
    assets_path: Path
    dist_path: Path

    ext: str
    data_start: str
    data_end: str

    shared_data: dict[str, Any]

    pages: dict[Path, Page] = dataclasses.field(default_factory=dict)
    templates: dict[str, Template] = dataclasses.field(default_factory=dict)


class PageBuilder(coreca.Core):
    def __init__(
        self,
        pages_path: Path,
        templates_path: Path,
        assets_path: Path,
        dist_path: Path,
        serve_host_port: tuple[str, int] | None = None,
        websocket_host_port: tuple[str, int] | None = None,
        ext: str = '.html',
        data_start: str = '---\n',
        data_end: str = '---\n',
        shared_data: dict[str, Any] | None = None,
    ) -> None:
        if shared_data is None:
            shared_data = {}
        state = State(
            pages_path,
            templates_path,
            assets_path,
            dist_path,
            ext,
            data_start,
            data_end,
            shared_data,
        )
        if websocket_host_port:
            ws_host, ws_port = websocket_host_port
            state.shared_data['_ws_script'] = f"""
                <script>
                  const socket = new WebSocket("ws://{ws_host}:{ws_port}");

                  socket.addEventListener("message", (event) => {{
                    if (event.data === "refresh") {{
                      window.location.reload();
                    }}
                  }});
                </script>
                """

        super().__init__(
            processors=[
                coreca.Processor('templates', [templates_path / f'*{ext}']),
                coreca.Processor('pages', [pages_path / f'**/*{ext}']),
                coreca.Processor('assets', [assets_path / '**/*']),
            ],
            signal_handlers=[
                tempaltes_handler,
                pages_handler,
                assets_handler,
            ],
            lifespans=[],
            state=state,
        )
        self.lifespans: list[coreca.Lifespan] = []
        if serve_host_port:
            self.lifespans.extend(
                [
                    coreca.Lifespan(coreca.lifespans.observe),
                    coreca.Lifespan(
                        coreca.lifespans.serve, dist_path, serve_host_port
                    ),
                ]
            )
        if websocket_host_port:
            self.lifespans.append(
                coreca.Lifespan(
                    coreca.lifespans.websocket,
                    websocket_host_port,
                    lambda _, __: 'refresh',
                ),
            )


def pages_handler(core: coreca.Core[State], signal: coreca.Signal) -> None:
    if signal.source == 'templates':
        # HACK: this is recalcing the name too
        name = signal.path.name.removesuffix(core.state.ext)
        for _, page in core.state.pages.items():
            if name in page.deps:
                page.update_deps(core.state.templates)
                page.save(core.state.shared_data, core.state.templates)
        return

    if signal.source != 'pages':
        return

    if signal.type == 'update':
        page = Page(
            signal.path,
            core.state.pages_path,
            core.state.dist_path,
            core.state.data_start,
            core.state.data_end,
        )
        page.update_deps(core.state.templates)
        core.state.pages[signal.path] = page
        page.save(core.state.shared_data, core.state.templates)

    elif signal.type == 'delete':
        page = core.state.pages.pop(signal.path, None)
        if page:
            page.out_path.unlink(missing_ok=True)


def tempaltes_handler(core: coreca.Core[State], signal: coreca.Signal) -> None:
    if signal.source != 'templates':
        return

    if signal.type == 'update':
        template = Template(
            signal.path,
            core.state.ext,
            core.state.data_start,
            core.state.data_end,
        )
        core.state.templates[template.name] = template
    elif signal.type == 'delete':
        # HACK: we are remaking the name here
        # we should store templates in a dict[Path, Template]
        # instead of dict[str, Template] (str -> name)
        # or we can have 2 dicts one for accessing by path and other for work
        name = signal.path.name.removesuffix(core.state.ext)
        core.state.templates.pop(name, None)


def assets_handler(core: coreca.Core[State], signal: coreca.Signal) -> None:
    if signal.source != 'assets':
        return
    out_path = core.state.dist_path / signal.path.relative_to(
        core.state.assets_path
    )
    if signal.type == 'update':
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(signal.path, out_path)
    elif signal.type == 'delete':
        out_path.unlink(missing_ok=True)
