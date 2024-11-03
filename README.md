# Pagebuilder

`pagebuilder` is a static site generator I made.

## How does it work?

You can check out the [site](/data) in this repo as an example.

`pagebuilder` uses `mustache` for rendering.

Pages and templates define data in the beginning of their files
between `<!-- YAML:\n` and `-->\n`.
(`template` and `slot` are special)

### Pages

Pages represent the contents of a page and are put into templates.
Templates are referenced by their name.

```html
<!-- YAML:
title: Page Title
theme: light
template: main_template
-->
<p>hello world</p>
```

### Templates

Contents of the page will be put into the `{{{slot}}}` tag.
Can be nested.

```html
<!-- YAML:
theme: dark
-->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{title}}</title>
    <link href="/css/style.css" rel="stylesheet" />
  </head>
  <body class="{{{theme}}}">
    <main>{{{slot}}}</main>
  </body>
</html>
```

Here `{{title}}` will be provided by the page
and `{{{theme}}}` will be overridden if provided.

### Assets

Assets are simply copied over unchanged.

## How to run?

### From code

```py
#!/usr/bin/env python3
from pathlib import Path

from pagebuilder import PageBuilderWatcher, serve

builder = PageBuilderWatcher(
    Path('./data/pages/'),
    Path('./data/templates/'),
    Path('./data/assets/'),
    Path('./.dist/'),
)
with builder:
    serve('localhost', 5000, builder.dist_path)
```

### From the CLI

```bash
# build
python -m pagebuilder ./data/pages/ ./data/templates ./data/assets ./dist
# watcher mode
python -m pagebuilder -a localhost:5000 ./data/pages/ ./data/templates ./data/assets ./dist
```

## Why not use `mustache`'s inheritance?

The syntax is quite clunky and it messes up HTML highlighting.
Also having data parsed opens the door to programmatic use.

Compare these examples.

```mustache
{{<main_template}}
{{$title}}My Title{{/title}}
{{$theme}}gruvbox{{/theme}}
{{$content}}
<div>
  List of fruits:
  <ul>
    <li>Bad Apple</li>
    <li>Fresh Apricot</li>
    <li>Sour Lemon</li>
    <li>Sweet Orange</li>
  </ul>
</div>
{{/content}}
{{/main_template}}
```

```html
<!-- YAML:
title: My Title
theme: gruvbox
template: main_template
-->
<div>
  List of fruits:
  <ul>
    <li>Bad Apple</li>
    <li>Fresh Apricot</li>
    <li>Sour Lemon</li>
    <li>Sweet Orange</li>
  </ul>
</div>
```

```html
<!-- YAML:
title: My Title
theme: gruvbox
template: main_template
fruits: [Bad Apple, Fresh Apricot, Sour Lemon, Sweet Orange]
-->
<div>
  List of fruits:
  <ul>
    {{#fruits}}
    <li>{{.}}</li>
    {{/fruits}}
  </ul>
</div>
```

## Plans

- Hook system
- Plugin system
- "Bring your own" rendering function
