"""Deterministic pytest tests for src/jobs/parse.py.

These tests use the HTML fixtures already present in the html/ directory
to verify parsing invariants without any network calls.
"""

import os

import pytest

from jobs.parse import clean, parse_ooh_page

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(REPO_ROOT, "html")


def html_path(slug: str) -> str:
    return os.path.join(HTML_DIR, f"{slug}.html")


# ---------------------------------------------------------------------------
# clean() unit tests
# ---------------------------------------------------------------------------


class TestClean:
    def test_collapses_whitespace(self):
        assert clean("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert clean("  foo  ") == "foo"

    def test_newlines_become_spaces(self):
        assert clean("line1\nline2") == "line1 line2"

    def test_tabs_become_spaces(self):
        assert clean("a\tb") == "a b"

    def test_empty_string(self):
        assert clean("") == ""


# ---------------------------------------------------------------------------
# parse_ooh_page() integration tests (using real HTML fixtures)
# ---------------------------------------------------------------------------

# Pick a handful of fixtures that are guaranteed to be present in the repo.
FIXTURE_SLUGS = ["cashiers", "software-developers", "civil-engineers", "dentists"]


@pytest.mark.parametrize("slug", FIXTURE_SLUGS)
def test_parse_returns_nonempty_markdown(slug):
    path = html_path(slug)
    if not os.path.exists(path):
        pytest.skip(f"Fixture {path} not present")
    md = parse_ooh_page(path)
    assert isinstance(md, str)
    assert len(md) > 100


@pytest.mark.parametrize("slug", FIXTURE_SLUGS)
def test_parse_contains_h1_title(slug):
    """The Markdown output must start with a # heading (the occupation title)."""
    path = html_path(slug)
    if not os.path.exists(path):
        pytest.skip(f"Fixture {path} not present")
    md = parse_ooh_page(path)
    assert md.startswith("# "), f"Expected Markdown to start with '# ', got: {md[:50]!r}"


@pytest.mark.parametrize("slug", FIXTURE_SLUGS)
def test_parse_quick_facts_present(slug):
    """The output should contain a Quick Facts section from the BLS table."""
    path = html_path(slug)
    if not os.path.exists(path):
        pytest.skip(f"Fixture {path} not present")
    md = parse_ooh_page(path)
    assert "## Quick Facts" in md


@pytest.mark.parametrize("slug", FIXTURE_SLUGS)
def test_parse_no_raw_html_tags(slug):
    """Markdown output must not contain raw HTML angle-bracket tags."""
    path = html_path(slug)
    if not os.path.exists(path):
        pytest.skip(f"Fixture {path} not present")
    md = parse_ooh_page(path)
    import re

    # Allow markdown tables (pipes) but not HTML tags like <div>
    assert not re.search(r"<[a-zA-Z][^>]*>", md), "Markdown contains raw HTML tags"


def test_cashiers_title():
    """Spot-check that cashiers.html parses to the expected occupation title."""
    path = html_path("cashiers")
    if not os.path.exists(path):
        pytest.skip("cashiers.html not present")
    md = parse_ooh_page(path)
    assert md.startswith("# Cashiers")


def test_software_developers_title():
    path = html_path("software-developers")
    if not os.path.exists(path):
        pytest.skip("software-developers.html not present")
    md = parse_ooh_page(path)
    assert "Software" in md.split("\n")[0]


def test_civil_engineers_source_url():
    """The output should contain the canonical BLS source URL."""
    path = html_path("civil-engineers")
    if not os.path.exists(path):
        pytest.skip("civil-engineers.html not present")
    md = parse_ooh_page(path)
    assert "**Source:**" in md
    # Check for a well-formed BLS URL (not just a substring match)
    import re

    assert re.search(r"https?://www\.bls\.gov/", md)
