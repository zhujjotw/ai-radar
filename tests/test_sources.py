"""Tests for T2 source modules: baseline, github_search, manual_entry."""

import sys
from unittest.mock import patch

import pytest

# Ensure project root is importable
sys.path.insert(0, ".")

from src.models import Project
from src.sources.baseline_sources import BASELINE_PROJECTS, get_baseline_projects
from src.sources.manual_entry import create_project_from_url


class TestBaselineSources:
    """Tests for baseline_sources module."""

    def test_baseline_has_minimum_projects(self):
        assert len(BASELINE_PROJECTS) >= 20

    def test_get_baseline_returns_project_instances(self):
        projects = get_baseline_projects()
        assert len(projects) >= 20
        for p in projects:
            assert isinstance(p, Project)
            assert p.pool == "baseline"
            assert p.source == "baseline"

    def test_each_baseline_has_required_fields(self):
        for p in get_baseline_projects():
            assert p.github_url, f"Missing github_url for {p.repo_full_name}"
            assert p.repo_full_name, "Missing repo_full_name"
            assert p.name, f"Missing name for {p.repo_full_name}"
            assert "github.com" in p.github_url

    def test_no_duplicate_repo_full_names(self):
        names = [p.repo_full_name for p in get_baseline_projects()]
        assert len(names) == len(set(names)), "Duplicate repo_full_name in baseline"

    def test_all_have_tags(self):
        for p in get_baseline_projects():
            assert p.tags, f"Missing tags for {p.repo_full_name}"

    def test_covers_all_keyword_categories(self):
        """Verify baseline covers each category in keywords.yaml."""
        from src.config import load_yaml_config

        keywords = load_yaml_config("keywords.yaml")
        expected_categories = set(keywords.keys())
        found_tags: set[str] = set()
        for p in get_baseline_projects():
            found_tags.update(p.tags)
        missing = expected_categories - found_tags
        assert not missing, f"Baseline missing projects for categories: {missing}"


class TestManualEntry:
    """Tests for manual_entry module."""

    def test_invalid_url_raises_valueerror(self):
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            create_project_from_url("https://not-github.com/foo/bar")

    def test_malformed_url_raises_valueerror(self):
        with pytest.raises(ValueError):
            create_project_from_url("not-a-url")

    @patch("src.sources.manual_entry._fetch_repo_data")
    def test_create_project_from_url(self, mock_fetch):
        mock_fetch.return_value = {
            "html_url": "https://github.com/test/project",
            "full_name": "test/project",
            "name": "project",
            "description": "A test project",
            "stargazers_count": 500,
            "forks_count": 50,
            "open_issues_count": 10,
            "language": "Python",
            "topics": ["ai", "ml"],
            "license": {"spdx_id": "MIT"},
            "pushed_at": "2026-01-01T00:00:00Z",
        }
        project = create_project_from_url("https://github.com/test/project")
        assert project.repo_full_name == "test/project"
        assert project.name == "project"
        assert project.source == "manual"
        assert project.pool == "candidate"
        assert project.stars == 500

    @patch("src.sources.manual_entry._fetch_repo_data")
    def test_override_reason_sets_filter_status(self, mock_fetch):
        mock_fetch.return_value = {
            "html_url": "https://github.com/test/low-star",
            "full_name": "test/low-star",
            "name": "low-star",
            "stargazers_count": 5,
        }
        project = create_project_from_url(
            "https://github.com/test/low-star",
            override_reason="Team uses this internally",
        )
        assert project.filter_status == "override"
        assert project.filter_reason == "Team uses this internally"


class TestGitHubSearch:
    """Tests for github_search module (with mocked API)."""

    def test_build_search_query(self):
        from src.sources.github_search import _build_search_query

        query = _build_search_query(["agent", "rag"], min_stars=200)
        assert "agent" in query
        assert "rag" in query
        assert "stars:>=200" in query

    def test_parse_repo_full_name(self):
        from src.sources.github_search import _parse_repo_full_name

        assert _parse_repo_full_name("https://github.com/owner/repo") == "owner/repo"
        assert _parse_repo_full_name("https://github.com/org/project/") == "org/project"

    def test_parse_repo_full_name_invalid(self):
        from src.sources.github_search import _parse_repo_full_name

        with pytest.raises(ValueError):
            _parse_repo_full_name("https://example.com/owner/repo")

    def test_github_item_to_project(self):
        from src.sources.github_search import _github_item_to_project

        item = {
            "full_name": "test/repo",
            "html_url": "https://github.com/test/repo",
            "name": "repo",
            "description": "Test desc",
            "stargazers_count": 1000,
            "forks_count": 100,
            "open_issues_count": 20,
            "language": "Python",
            "topics": ["ai"],
            "license": {"spdx_id": "Apache-2.0"},
            "pushed_at": "2026-01-01T00:00:00Z",
        }
        project = _github_item_to_project(item)
        assert project.repo_full_name == "test/repo"
        assert project.stars == 1000
        assert project.pool == "candidate"
        assert project.source == "github_search"
