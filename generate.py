import shutil
from pathlib import Path
from typing import Any, NamedTuple, Self

import combustache
import yaml

PAGES_PATH = Path('./pages/')
TEMPLATE_PATH = Path('./templates/')
DIST_PATH = Path('./dist/')
ASSETS_PATH = Path('./assets/')

EXT = '.html'
COMMENT_START = '<!-- YAML:\n'
COMMENT_END = '-->\n'


class Page(NamedTuple):
    content: str
    data: dict[str, Any]
    path: Path

    def render(self, templates: dict[str, Self]) -> str:
        template_stack = [self.content]
        merged_data = self.data
        curr = self

        while curr.data.get('template', None):
            template_name = curr.data['template']
            curr = templates[template_name]

            template_stack.append(curr.content)
            merged_data = curr.data | merged_data

        for txt in template_stack:
            rendered = combustache.render(txt, merged_data)
            merged_data['slot'] = rendered

        return merged_data['slot']

    def save(self, txt: str) -> None:
        path = self.path
        if path.name.removesuffix(EXT) == 'index':
            output_dir_path = DIST_PATH / (path.parent.relative_to(PAGES_PATH))
        else:
            output_dir_path = (
                DIST_PATH
                / path.parent.relative_to(PAGES_PATH)
                / path.name.removesuffix(EXT)
            )
        output_dir_path.mkdir(parents=True, exist_ok=True)

        (output_dir_path / 'index.html').write_text(txt)

    def render_and_save(self, templates: dict[str, Self]) -> None:
        self.save(self.render(templates))

    @classmethod
    def load(cls, path: Path) -> Self:
        raw_txt = path.read_text()

        if raw_txt.startswith(COMMENT_START):
            data_start = len(COMMENT_START)
            data_end = raw_txt.find(COMMENT_END)
            txt_start = data_end + len(COMMENT_END)

            data_txt = raw_txt[data_start:data_end]
            data = yaml.load(data_txt, yaml.Loader)
            txt = raw_txt[txt_start:]
        else:
            data = {}
            txt = raw_txt
        return cls(txt, data, path)


def load_pages(path: Path) -> dict[str, Page]:
    return {
        file.name.removesuffix(EXT): Page.load(file)
        for file in path.rglob(f'**/*{EXT}')
    }


if __name__ == '__main__':
    pages = load_pages(PAGES_PATH)
    templates = load_pages(TEMPLATE_PATH)

    shutil.rmtree(DIST_PATH, ignore_errors=True)
    for page in pages.values():
        page.render_and_save(templates)
    shutil.copytree(ASSETS_PATH, DIST_PATH / ASSETS_PATH)
