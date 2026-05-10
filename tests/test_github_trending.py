"""Tests for GitHub Trending scraper."""

from __future__ import annotations

import pytest

from src.sources.github_trending import _parse_trending_html, _item_to_project


# Sample HTML snippet mimicking GitHub Trending page structure
_SAMPLE_ARTICLE = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/test-org/test-repo" class="Link">
      <span class="text-normal">test-org /</span>
      test-repo
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">
    A test repository for AI experiments
  </p>
  <div class="f6 color-fg-muted mt-2">
    <span itemprop="programmingLanguage">Python</span>
    <a href="/test-org/test-repo/stargazers" class="Link Link--muted">
      12,345
    </a>
    <a href="/test-org/test-repo/forks" class="Link Link--muted">
      1,234
    </a>
    <span class="float-sm-right">
      567 stars today
    </span>
  </div>
</article>
"""

_SAMPLE_HTML = f"""
<html><body>
{_SAMPLE_ARTICLE}
{_SAMPLE_ARTICLE.replace("test-org/test-repo", "another-org/another-repo")}
</body></html>
"""


class TestParseTrendingHtml:
    """Test HTML parsing logic."""

    def test_parse_returns_list(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert isinstance(repos, list)

    def test_parse_finds_repos(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert len(repos) == 2

    def test_parse_extracts_full_name(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert repos[0]["full_name"] == "test-org/test-repo"
        assert repos[1]["full_name"] == "another-org/another-repo"

    def test_parse_extracts_description(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert repos[0]["description"] == "A test repository for AI experiments"

    def test_parse_extracts_language(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert repos[0]["language"] == "Python"

    def test_parse_extracts_stars(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert repos[0]["stars"] == 12345

    def test_parse_extracts_forks(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert repos[0]["forks"] == 1234

    def test_parse_extracts_trending_stars(self) -> None:
        repos = _parse_trending_html(_SAMPLE_HTML)
        assert repos[0]["trending_stars"] == 567
        assert repos[0]["trending_period"] == "today"

    def test_parse_empty_html(self) -> None:
        repos = _parse_trending_html("<html><body></body></html>")
        assert repos == []

    def test_parse_no_description(self) -> None:
        html = """
        <article class="Box-row">
          <h2 class="h3 lh-condensed">
            <a href="/org/repo">org / repo</a>
          </h2>
          <div class="f6 color-fg-muted mt-2">
            <a href="/org/repo/stargazers">100</a>
          </div>
        </article>
        """
        repos = _parse_trending_html(html)
        assert len(repos) == 1
        assert repos[0]["description"] is None


class TestItemToProject:
    """Test conversion from parsed item to Project model."""

    def _make_item(self, **overrides) -> dict:
        defaults = {
            "full_name": "test-org/test-repo",
            "description": "A test repo",
            "language": "Python",
            "stars": 1000,
            "forks": 100,
            "trending_stars": 50,
            "trending_period": "today",
        }
        defaults.update(overrides)
        return defaults

    def test_project_has_correct_source(self) -> None:
        item = self._make_item()
        project = _item_to_project(item)
        assert project.source == "github_trending"

    def test_project_has_correct_pool(self) -> None:
        item = self._make_item()
        project = _item_to_project(item)
        assert project.pool == "candidate"

    def test_project_has_github_url(self) -> None:
        item = self._make_item()
        project = _item_to_project(item)
        assert project.github_url == "https://github.com/test-org/test-repo"

    def test_project_has_discovered_reason(self) -> None:
        item = self._make_item(trending_stars=100, trending_period="weekly")
        project = _item_to_project(item)
        assert "100 stars weekly" in project.discovered_reason

    def test_project_preserves_metadata(self) -> None:
        item = self._make_item(stars=5000, forks=500, language="Rust")
        project = _item_to_project(item)
        assert project.stars == 5000
        assert project.forks == 500
        assert project.language == "Rust"
