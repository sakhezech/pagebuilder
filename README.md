# Pagebuilder

`pagebuilder` is a static site generator I made.

## How does it work?

`pagebuilder` uses `mustache` for rendering by default.

Pages and templates define data in the frontmatter format.

`template` and `slot` keys are special.

### Pages

Pages represent the contents of a page and are put into templates.
Templates are referenced by their name.

```html
---
title: Page Title
theme: light
template: main_template
---

<p>hello world</p>
```

### Templates

Contents of the page will be put into the `{{{slot}}}` tag.
Can be nested.

```html
---
theme: dark
---

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

### From the CLI

You can run `pagebuilder` from the CLI in two ways:

by passing in the arguments like this:

```bash
# add --watch for watcher mode
python -m pagebuilder --args ./.dist/ ./pages/ ./templates/ ./assets/
```

or by "importing" a builder from a module

```bash
# add --watch for watcher mode
python -m pagebuilder -b hello_world:my_builder
```

```py
# filename: hello_world.py
from pagebuilder import PageBuilder

my_builder = PageBuilder(
    './pages/',
    './templates/',
    './assets/',
    dist_path='./.dist/',
)
```

### From code

```py
#!/usr/bin/env python3
from pagebuilder import PageBuilder, serve

builder = PageBuilder(
    './pages/',
    './templates/',
    './assets/',
    dist_path='./.dist/',
)
# builder.build() for build only
with builder:  # watcher mode
    serve('localhost', 5000, builder.dist_path)
```

## Plans

- Hook system
