# podpack-pages

One distribution, three [podpack](https://github.com/holdenweb/podpack) apps,
each serving a set of a site's content from that app's own host data
directory. A site installs any of them by naming it in `[site] apps`:

| Import name (in `apps`) | App name (keys everything else) | Asks to mount at | Kind | Host tree it serves |
| --- | --- | --- | --- | --- |
| `podpack_pages` | `pages` | `/pages` | unified Markdown/HTML space | `<data root>/pages/{md-pages,html-pages}/` |
| `podpack_pages.pybooks` | `pybooks` | `/pybooks` | the same kind, a second time | `<data root>/pybooks/html-pages/` ← orpy's `build.py --fragments` tree |
| `podpack_pages.blog` | `blog` | `/blog` | a sitescraper export, served from its manifest | `<data root>/blog/export/` ← sitescraper's `build/` |

Three spellings, per podpack convention: the distribution is `podpack-pages`;
the *import* names above go in a site's `apps` list; the *app* names are the
blueprints' names and key `[apps.<name>]`, `[site.mounts]`, the directories on
disk, the log files and the template namespaces. `/_status` reports the
mapping under `installed_from` for anyone unsure which is which.

Each app is an ordinary podpack app in its own right -- own data directory,
own config section, own mount override, own nav entry, own log file, own
`/_status` entry -- because podpack installs a dotted subpackage exactly as it
installs a top-level one. `pages` contributes no nav entry; `pybooks` and
`blog` contribute "Python" and "Blog", which resolve to their roots wherever
the site mounts them.

## The pages kind: `pages` and `pybooks`

Content lives in the app's host data directory, in two trees:

```
<data root>/<name>/md-pages/       Markdown, searched first
<data root>/<name>/html-pages/     HTML, searched second; assets live beside pages
```

`/<mount>/<name>` searches the Markdown tree (`md-pages/<name>.md`) first and
the HTML tree (`html-pages/<name>.html`) second, so a page's address never
says which format it is stored in, and a Markdown page shadows an HTML one of
the same name.

| Route | What it does |
| --- | --- |
| `/<mount>/<name>` | serve the page, Markdown space first |
| `/<mount>/<dir>/` | serve the directory's `index` page |
| `/<mount>/` | serve the top-level `index` page |
| `/<mount>/asset/<path>` | serve an asset (image, stylesheet) belonging to a page, cached an hour |

A name that is a directory in either tree serves the directory's `index`
page, resolved like any other name. The canonical address is the slash form;
the bare form redirects to it (308) so that relative references inside an
index page resolve within its directory. Mounted at the site root, this puts
the top-level `index` page at `/` (podpack ADR-0024).

**Markdown** renders with the `mdx_math` and `codehilite` extensions. A
leading `# Heading` becomes the page's title and leaves the body.

**HTML** is served as a page body inside the site's chrome. Relative `src`
and `href` references are rewritten server-side through the app's own asset
route, so they follow the app wherever the site mounts it; absolute ones
(`/...`, `http(s)://`, `#`, `mailto:`, `data:`) pass through untouched. A page
whose first line is `<!-- title: The Title -->` is titled by it, and the
comment leaves the body -- the Markdown rule's twin, so a generator can title
every page it emits without knowing the chrome.

A page that declares no title gets `[apps.<name>] default_title`, or
"Untitled". A page named `asset/...` would be shadowed by the asset route;
don't create one.

### `pybooks`: the Python course books

`pybooks` *is* the pages app installed a second time under another name
(`src/podpack_pages/pybooks/__init__.py` is two imports and one `PagesApp(...)`
construction). Its `html-pages/`
tree is where the orpy repository's `build.py --fragments` output is copied,
verbatim: `index.html`, `python1/`..`python4/` with their `images/`, and
`common/course.css|js`. Those fragments were shaped to this app's behaviour
-- relative image srcs (rewritten here), absolute suffix-less links between
pages and absolute css/js links (passed through) -- so nothing here is orpy-
specific. Two things follow from the links being absolute:

- orpy must be built with `courses.yaml pages_prefix` equal to this app's
  mount (`/pybooks` unless the site moves it); a tree built for another
  prefix serves its pages and 404s on every link between them. This app
  does not rewrite absolute links and will not detect the mismatch.
- The whole tree is copied each time, mirroring: a course removed upstream
  should disappear here too.

Until a tree is copied in, `/pybooks/` serves a seeded placeholder page that
says so. It is `html-pages/index.html`, the path orpy's own landing page
overwrites -- and deliberately not a Markdown page, which would shadow the
real landing for ever after.

## The blog kind: `blog`

The sitescraper repository captures a Blogger blog into MongoDB and exports
it (`python -m blogscraper export`) as a tree of content-only fragments with a
manifest. That tree is copied verbatim into this app's data directory:

```
<data root>/blog/export/manifest.json          what is a post, with titles, dates, categories
<data root>/blog/export/posts/YYYY/MM/slug.html one fragment per post; the .html is kept on purpose
<data root>/blog/export/images/<hash>.<ext>     harvested images
```

The manifest is the contract (sitescraper ADR-0007). A request under the
mount whose path the manifest lists is a **post**: the fragment's
placeholders are filled in and it is wrapped in the site's chrome, titled
from the manifest. Anything else that exists in the tree -- images, the
manifest itself, a stray file -- is served exactly as stored, cached an hour.
Nothing else is served; nothing is cached; the manifest is read on every
request, so a freshly copied export is live the moment it lands.

| Route | What it does |
| --- | --- |
| `/<mount>/` | every post, newest first, grouped by year, titled `[apps.blog] index_title` |
| `/<mount>/posts/YYYY/MM/slug.html` | a post listed in the manifest, decorated |
| `/<mount>/<anything else on disk>` | served as stored |

Fragments are written before their site root is known: every URL into the
tree is spelled `${{{ROOT}}}` (content) or `${{{IMAGE_ROOT}}}` (images), and
publishing substitutes the mounted roots through Jinja with all of its
delimiters moved to those distinctive sentinels, so `${HOME}`, `{{ x }}` and
`{% for %}` in a post's code samples pass through untouched (sitescraper
ADR-0009 and ADR-0010). `ROOT` is this app's mount, read per request, so
`[site.mounts] blog = "/elsewhere"` moves every link inside every post with
no regeneration. `IMAGE_ROOT` is `[apps.blog] image_root` if the site sets
one, else `ROOT`. The eight-line publish step is restated in
`src/podpack_pages/blog/publish.py` rather than imported, because
`blogscraper` carries MongoDB, BeautifulSoup and requests; the delimiter
strings there must match sitescraper's `blogscraper/publish.py`,
`tests/test_publish.py` pins them on both sides, and a manifest whose `root_placeholder` disagrees is refused.

A manifest that is missing, unparseable, or lists a path that steps outside
the tree makes the **whole blog answer 503**, with one ERROR line in
`blog.log` naming the file and the remedy, and `/healthz` reporting the app
unhealthy (not fatal: the rest of the site serves). Partly serving a tree
nobody can trust was the alternative. A post the manifest lists but the tree
lacks is a 404 with a WARNING naming the file: a copy that did not complete.

Until an export is copied in, the app serves a seeded one-post sample that
says so, and whose one link is a placeholder -- so a fresh install proves the
whole chain. Copy the real export *mirroring* and the sample is gone; merge
it and the sample lingers unlisted, served as stored if anyone types its URL.

Comments, feeds, archive and category pages are not built; the manifest
carries what any of them would need.

## Installing on a site

```toml
[site]
apps = ["mysite", "podpack_pages", "podpack_pages.pybooks", "podpack_pages.blog"]
# nav order is this order: Python, Blog

[apps.pages]
default_title = "Just another note"     # a page that declares no title

[apps.pybooks]
default_title = "Python courses"

[apps.blog]
index_title = "Blog"                    # title of the index page
default_title = "Untitled post"         # a post whose manifest title is empty
# image_root = "https://img.example"    # only if images are served from elsewhere
```

Every key is optional and has a shipped default. Mounts are not config of
these apps: `[site.mounts] pybooks = "/courses"` is the site's table (podpack
ADR-0006), and routes, nav entries, rewritten asset URLs and substituted
roots all follow it. A mis-keyed section (`[apps.podpack_pages.blog]`, the
import name) is podpack's one silent failure: the defaults apply and nothing
says so. `/_status` reports each app's effective content counts and, for the
blog, which manifest is live.

Copying content onto a host is the site's business; podpack promises only
that each app's directory is `<data root>/<name>/`. A site running podpack's
substrate typically has a refresh script that takes the app and tree by name
(holdenweb.com's `ops/refresh-content.sh`):

```
APP=pybooks TREE=html-pages ops/refresh-content.sh <the orpy tree> --mirror
APP=blog    TREE=export     ops/refresh-content.sh <the sitescraper build/> --mirror
```

No restart either time.

## Adding a content set

Every content set on a site is its own podpack app, and one distribution may
ship several (podpack ADR-0038, "A distribution can ship more than one app"):
the registry keys everything off the blueprint's name, so the apps here are
enabled, mounted and configured independently, exactly as apps from separate
distributions are. Adding a content set is therefore adding an app, never
extending an existing one.

### The common case: another pages-kind app

If the new content is a tree of Markdown and HTML pages -- hand-written, or
generated the way orpy generates the course books -- it is the pages kind,
and the whole app is a subpackage exposing a `PagesApp` under a new name.
`src/podpack_pages/pybooks/__init__.py` is the template:

```python
# src/podpack_pages/<name>/__init__.py
from podpack import Section

from ..views import PagesApp, make_blueprint

site_app = PagesApp(
    blueprint=make_blueprint("<name>"),
    url_prefix="/<name>",
    nav=(Section("<Label>", "<name>.page"),),   # or nav=() to stay out of the nav
)
```

Everything else follows from the name: the data directory
`<data root>/<name>/`, the config section `[apps.<name>]`, the log file, the
template namespace `templates/<name>/` and the `/_status` entry. Nothing in
`views.py`, `content.py` or `chrome.py` changes. Three rules:

- **The name is the blueprint's, typed once.** It must not collide with any
  app a site might install beside it -- `pages`, `pybooks`, `blog`, the site's
  own -- because podpack refuses to boot two apps of one name.
- **Ship a placeholder**, `src/podpack_pages/<name>/data/html-pages/index.html`,
  saying what the app is and where its real tree goes. podpack seeds it into
  the app's empty directory on first install (ADR-0008), so a fresh site
  serves `/<name>/` with a 200 and the mount, the nav entry and `/_status`
  can all be checked before any content is copied. Make it HTML, at
  `html-pages/index.html`: that is the path a real tree's own landing page
  overwrites, whereas a Markdown placeholder would shadow that landing page
  for ever. Seeding happens once, so a later change to the placeholder never
  reaches a host that already has the directory.
- **The nav label is a fixed string.** A `Section` is frozen at import time
  and podpack gives a site no lever to relabel it (ADR-0022).

Add a test file on the pattern of `tests/test_pybooks.py`: the app names
itself after its blueprint, installs by its import name, seeds its own
placeholder and not another app's, reads its own `[apps.<name>]`, contributes
a nav entry that resolves to its root, and follows a `[site.mounts]` remount.

The same construction works from a distribution of its own: a package that
depends on `podpack-pages` builds its `site_app` from
`podpack_pages.views.PagesApp` and `make_blueprint` exactly as above and
ships its own `data/`. Verified by installing such a package beside the
three apps here.

### When to build a new kind instead

Reuse `PagesApp` when the content is pages: files addressed by name, one per
URL, that the site's chrome can wrap as they are. Build a new kind -- a
`views.py` of its own and, if it has anything to report, a `SiteApp`
subclass -- when the content has a contract of its own: addresses that are
not file names, a manifest or index that decides what is served and how,
titles that come from somewhere other than the file, placeholders to fill at
serve time, or a health question an operator would ask ("is the manifest
readable?"). `src/podpack_pages/blog/` is the worked example: `views.py`
routes, `manifest.py` reads the export's index, `publish.py` restates the
producer's contract, and `BlogApp` answers `/healthz` and `/_status`. What a
kind shares with the others is the toolbox, not the views:
`chrome.blueprint()` and `chrome.render()` for templates,
`content.check_relative()` and `content.find_asset()` for reading a tree
safely. A new kind's default templates go under `templates/podpack_pages/`
beside the others, named for the kind.

### What the site then does

1. Add the import name, `podpack_pages.<name>`, to `[site] apps`, in the
   position its nav entry should take: nav order is installation order.
2. Optionally set `[apps.<name>]` keys (every one has a default) and, if the
   app asks to mount somewhere the site does not want it,
   `[site.mounts] <name> = "/elsewhere"`.
3. Release and re-pin. A site depends on this distribution by version or
   commit, so a new app reaches it only through a new release here and a
   re-lock there.
4. Copy the content into `<data root>/<name>/html-pages/`, or whatever tree
   the kind reads. On a site running podpack's substrate that is the site's
   refresh script with the app and tree named; holdenweb.com wraps its
   `ops/refresh-content.sh` and `ops/push-content.sh` in one `just` recipe
   that takes them as arguments:

```
just content staging <source-dir> <name> html-pages --mirror
```

No restart, for any kind: every app here reads the disk on each request.

## Templates

Every page extends the site's `base.html` and fills `{% block content %}`,
passing `title`; the Markdown page also fills `{% block scripts %}` with
MathJax, which a chrome that does not define that block silently drops.

Shipped defaults live under `templates/podpack_pages/` -- the name of the
package the blueprint was built for, which no app's name can collide with --
and are looked up after the app's own name, so a site restyles:

- one app, by shipping `templates/pybooks/html.html` or
  `templates/blog/blog-post.html` (podpack ADR-0005 shadowing);
- every app of a kind, by shipping `templates/podpack_pages/<page>`.

The pages: `markdown.html`, `html.html`, `blog-index.html`, `blog-post.html`.
An existing site override at `templates/pages/*.html` keeps working.

`chrome.py` is not tied to this package. A distribution of its own that
depends on podpack-pages builds its blueprints with
`chrome.blueprint(name, "its_package")` and calls `chrome.render()` exactly as
the apps here do; its defaults then come from its own `templates/its_package/`.

## Logs

Each app logs to `<log root>/<name>/<name>.log`. Because `pybooks` and `blog`
are subpackages of `podpack_pages`, Python's logger propagation also delivers
their records to `pages.log` when `pages` is installed; each record names its
logger, and the app's own file is the one to read first.

## When something is wrong

| Symptom | Cause | Where it says so |
| --- | --- | --- |
| `/pybooks/` shows the placeholder page | the orpy tree was never copied, or landed under another app | `/_status` → `apps.pybooks.reported` counts |
| course pages render, links between them 404 | orpy built with the wrong `pages_prefix` | view source: the hrefs name the prefix they were built for |
| course images 404 | `images/` not copied beside the pages | the rewritten URL maps 1:1 onto `html-pages/<course>/images/` |
| every `/blog` URL is 503 | manifest missing, malformed, foreign placeholder, or a bad entry | `blog.log` ERROR names the file and the remedy; `/healthz` |
| a post shows raw, no chrome, `${{{ROOT}}}` visible | its path is not in the manifest (a merge without mirroring) | compare `curl /blog/manifest.json` with the URL |
| one post 404s though the index links it | the copy did not complete | `blog.log` WARNING names the missing file |
| every heading reads "Untitled" | `[apps.<name>]` keyed on the import name | `/_status` → `installed_from` |
| "Python" appears twice in the nav | the site still contributes its own entry | the site's `views.py` |

## Requirements

Python ≥ 3.12; podpack ≥ 0.8 (the `status()`/`healthz()` hooks). podpack is
deliberately absent from `dependencies` and lives in the dev group; see
`pyproject.toml`.
