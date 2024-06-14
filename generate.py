import shutil
from pathlib import Path

import combustache

HTML = '.html'

src_path = Path('./src/')
dist_path = Path('./dist/')
assets_path = Path('./assets/')
data = dict()

shutil.rmtree(dist_path, ignore_errors=True)

paths = src_path.rglob(f'**/*{HTML}')
templates = combustache.load_templates(
    src_path, HTML, include_relative_path=True
)

for path in paths:
    if path.name.startswith('_'):
        continue

    if path.name.removesuffix(HTML) == 'index':
        output_dir_path = dist_path / (path.parent.relative_to(src_path))
    else:
        output_dir_path = (
            dist_path
            / path.parent.relative_to(src_path)
            / path.name.removesuffix(HTML)
        )
    output_dir_path.mkdir(parents=True, exist_ok=True)

    res = combustache.render(path.read_text(), data, templates)
    (output_dir_path / 'index.html').write_text(res)

shutil.copytree(assets_path, dist_path / assets_path)
