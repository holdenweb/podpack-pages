"""The publish step of sitescraper's export contract, restated here.

A blogscraper fragment is written before its site root is known: every URL
into the tree is spelled with a placeholder -- `${{{ROOT}}}` for content and
`${{{IMAGE_ROOT}}}` for images -- and publishing substitutes the mounted
roots through Jinja. All of Jinja's delimiters are moved to distinctive
sentinels, so shell, template and code samples in post bodies pass through
untouched (sitescraper ADR-0009; the image placeholder is ADR-0010).

The reference is `make_publish_env` / `render_fragment` in sitescraper's
`blogscraper/export.py`. It is copied rather than imported because that
package carries MongoDB, BeautifulSoup and requests for the sake of eight
lines. The strings below must therefore match that file: `tests/test_publish.py`
pins them, and the blog refuses a manifest whose `root_placeholder` disagrees.
"""

from __future__ import annotations

import jinja2

VARIABLE_START, VARIABLE_END = "${{{", "}}}"
BLOCK_START, BLOCK_END = "${{%", "%}}}"
COMMENT_START, COMMENT_END = "${{#", "#}}}"

ROOT_PLACEHOLDER = f"{VARIABLE_START}ROOT{VARIABLE_END}"
IMAGE_ROOT_PLACEHOLDER = f"{VARIABLE_START}IMAGE_ROOT{VARIABLE_END}"

# Built once, since it holds only delimiter settings. Fragments are compiled
# per request with from_string, so an edited file shows on the next request.
_ENV = jinja2.Environment(
    variable_start_string=VARIABLE_START,
    variable_end_string=VARIABLE_END,
    block_start_string=BLOCK_START,
    block_end_string=BLOCK_END,
    comment_start_string=COMMENT_START,
    comment_end_string=COMMENT_END,
    undefined=jinja2.StrictUndefined,
    autoescape=False,  # a fragment is HTML we serve deliberately
    keep_trailing_newline=True,
)


def render_fragment(
    html: str, root: str, image_root: str | None = None, *, source: str = ""
) -> str:
    """Substitute the mounted roots into a fragment.

    `image_root` defaults to `root`, so a self-contained tree needs no
    configuration (ADR-0010). A placeholder the contract does not define, or a
    broken sentinel, raises RuntimeError naming `source`: loud, as the
    contract asks -- the export's own collision scan should have caught it
    first, and nothing here can guess what was meant.
    """
    try:
        return _ENV.from_string(html).render(
            ROOT=root, IMAGE_ROOT=root if image_root is None else image_root
        )
    except jinja2.TemplateError as exc:
        raise RuntimeError(f"{source or 'fragment'}: {exc}") from exc
