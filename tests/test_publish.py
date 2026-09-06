"""The consumer side of sitescraper's publish contract, held to its reference.

The first two tests are sitescraper's own (`tests/test_export.py`), verbatim,
so the two implementations are held to one contract from both sides.
"""

import pytest

from podpack_pages.blog import publish
from podpack_pages.blog.publish import render_fragment


def test_only_the_distinctive_sentinels_substitute() -> None:
    body = (
        "root=${{{ROOT}}} "
        "shell=${HOME} "
        "var={{ x }} "
        "block={% for i in xs %}{{ i }}{% endfor %} "
        "comment={# note #}"
    )
    assert render_fragment(body, "/blog") == (
        "root=/blog "
        "shell=${HOME} "
        "var={{ x }} "
        "block={% for i in xs %}{{ i }}{% endfor %} "
        "comment={# note #}"
    )


def test_image_root_defaults_to_root_but_can_diverge() -> None:
    frag = "page ${{{ROOT}}}/posts/x.html img ${{{IMAGE_ROOT}}}/images/y.png"
    assert render_fragment(frag, "/blog") == "page /blog/posts/x.html img /blog/images/y.png"
    out = render_fragment(frag, "/blog", image_root="https://img.holdenweb.com")
    assert out == "page /blog/posts/x.html img https://img.holdenweb.com/images/y.png"


def test_a_stray_placeholder_raises_naming_the_source() -> None:
    with pytest.raises(RuntimeError, match=r"posts/2020/01/bad\.html.*NOPE"):
        render_fragment("x ${{{NOPE}}} y", "/blog", source="posts/2020/01/bad.html")


def test_the_delimiter_constants_match_the_reference() -> None:
    """sitescraper ADR-0009's strings. A failure here means one side changed
    the contract; the other must follow before any post can be served."""
    assert (publish.VARIABLE_START, publish.VARIABLE_END) == ("${{{", "}}}")
    assert (publish.BLOCK_START, publish.BLOCK_END) == ("${{%", "%}}}")
    assert (publish.COMMENT_START, publish.COMMENT_END) == ("${{#", "#}}}")
    assert publish.ROOT_PLACEHOLDER == "${{{ROOT}}}"
    assert publish.IMAGE_ROOT_PLACEHOLDER == "${{{IMAGE_ROOT}}}"


def test_a_fragments_trailing_newline_survives() -> None:
    assert render_fragment("<p>x</p>\n", "/b") == "<p>x</p>\n"
