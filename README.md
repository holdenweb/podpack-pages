# podpack-pages

A podpack app serving a site's prose content — Markdown and HTML files — from
a **single name space**. `/pages/<name>` searches the Markdown tree
(`md-pages/<name>.md`) first and the HTML tree (`html-pages/<name>.html`)
second, so a page's address never says which format it is stored in, and a
Markdown page shadows an HTML one of the same name.

Three spellings, per podpack convention: the distribution is `podpack-pages`,
the import name (for a site's `apps` list) is `podpack_pages`, and the app
answers to `pages` — its blueprint's name, which keys `[apps.pages]`,
`[site.mounts]` and its directories on disk.

## Content location

Content lives in the app's host data directory:

```
<data root>/pages/md-pages/       Markdown, searched first
<data root>/pages/html-pages/     HTML, searched second; assets live beside pages
```

The package ships a starter `data/` tree which podpack seeds to the host on
first install, so editing a page on the host changes the site with no rebuild.

## Routes

| Route | What it does |
| --- | --- |
| `/pages/<name>` | serve the page, Markdown space first |
| `/pages/asset/<path>` | serve an asset (image, stylesheet) belonging to a page |

Relative `src`/`href` references inside HTML pages are rewritten server-side
through `url_for("pages.asset", ...)`, so they follow the app wherever the
site mounts it. A page named `asset/...` would be shadowed by the asset route;
don't create one.

## Markdown rendering

Extensions `mdx_math` and `codehilite` are enabled. A leading `# Heading`
becomes the page's title and is removed from the body; a page without one
gets `[apps.pages] default_title`, or "Untitled".

## Configuration

```toml
[apps.pages]
default_title = "Just another note"     # title for Markdown pages with no heading
```

Both settings are optional; the app ships defaults.

## Requirements of the site's chrome

The Markdown template fills `{% block scripts %}` with MathJax. A site chrome
that does not define that block silently drops it — mathematics then renders
as raw TeX.
