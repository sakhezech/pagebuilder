import shutil
from pathlib import Path
from typing import Any, Self

import combustache
import yaml


class Generator:
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
        page = Page.load(
            page_path,
            self.pages_path,
            self.data_start,
            self.data_end,
            self.ext,
        )
        page.template_stack = make_template_stack(page, self.templates)

        self.pages[page_path] = page
        return page

    def add_template(self, template_path: Path) -> 'Page':
        template = Page.load(
            template_path,
            self.templates_path,
            self.data_start,
            self.data_end,
            self.ext,
        )
        self.templates[template.name] = template
        return template

    def save_page(self, page: 'Page') -> None:
        page.save(self.templates, self.dist_path)

    def save_all(self) -> None:
        for page in self.pages.values():
            self.save_page(page)

    def generate(self) -> None:
        shutil.rmtree(self.dist_path, ignore_errors=True)
        self.save_all()
        shutil.copytree(self.assets_path, self.dist_path / self.assets_path)


class Page:
    def __init__(
        self,
        content: str,
        data: dict[str, Any],
        path: Path,
        name: str,
    ) -> None:
        self.content = content
        self.data = data
        self.path = path
        self.name = name
        self.template_stack: list[str] | None = None

    def render(self, templates: dict[str, Self]) -> str:
        merged_data = self.data
        merged_data['slot'] = combustache.render(self.content, self.data)

        if self.template_stack is None:
            self.template_stack = make_template_stack(self, templates)
        for template_name in self.template_stack:
            template = templates[template_name]
            merged_data = template.data | merged_data
            merged_data['slot'] = combustache.render(
                template.content, merged_data
            )
        return merged_data['slot']

    def save(self, templates: dict[str, Self], dist_path: Path) -> None:
        if self.name == 'index':
            output_dir_path = dist_path / self.path.parent
        else:
            output_dir_path = dist_path / self.path.parent / self.name

        output_dir_path.mkdir(parents=True, exist_ok=True)
        (output_dir_path / 'index.html').write_text(self.render(templates))

    @classmethod
    def load(
        cls,
        path: Path,
        relative_to: Path,
        data_comment_start: str,
        data_comment_end: str,
        EXT: str,
    ) -> Self:
        rel_path = path.relative_to(relative_to)
        raw_txt = path.read_text()
        name = path.name.removesuffix(EXT)

        if raw_txt.startswith(data_comment_start):
            data_start = len(data_comment_start)
            data_end = raw_txt.find(data_comment_end)
            txt_start = data_end + len(data_comment_end)

            data_txt = raw_txt[data_start:data_end]
            data = yaml.load(data_txt, yaml.Loader)
            txt = raw_txt[txt_start:]
        else:
            data = {}
            txt = raw_txt

        return cls(txt, data, rel_path, name)


def make_template_stack(page: 'Page', templates: dict[str, Any]) -> list[str]:
    dependencies: list[str] = []
    curr = page
    while curr.data.get('template', None):
        template_name = curr.data['template']
        dependencies.append(template_name)
        curr = templates[template_name]
    return dependencies


if __name__ == '__main__':
    PAGES_PATH = Path('./pages/')
    TEMPLATE_PATH = Path('./templates/')
    DIST_PATH = Path('./dist/')
    ASSETS_PATH = Path('./assets/')

    gen = Generator(
        PAGES_PATH,
        TEMPLATE_PATH,
        ASSETS_PATH,
        DIST_PATH,
    )
    gen.generate()
