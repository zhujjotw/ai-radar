"""Tests for T3 filtering modules: classifier, project_filter, project_scorer."""

from datetime import datetime, timedelta, timezone

from src.services.classifier import classify_project, classify_project_dict
from src.services.project_filter import filter_project, filter_project_dict
from src.services.project_scorer import score_project, score_project_dict


# ── Classifier Tests ──────────────────────────────────────────────


class TestClassifier:
    """Tests for classifier.py direction tagging."""

    def test_agent_tag_from_name(self):
        tags = classify_project(name="awesome-agent-framework")
        assert "Agent" in tags

    def test_rag_tag_from_description(self):
        tags = classify_project(description="A retrieval-augmented-generation system")
        assert "RAG" in tags

    def test_eval_tag_from_topics(self):
        tags = classify_project(topics=["evaluation", "benchmark"])
        assert "Eval" in tags

    def test_inference_tag_from_name(self):
        tags = classify_project(name="vllm-inference-engine")
        assert "Inference" in tags

    def test_workflow_tag_from_description(self):
        tags = classify_project(description="Workflow orchestration for LLM pipelines")
        assert "Workflow" in tags

    def test_developer_tooling_tag_from_topics(self):
        tags = classify_project(topics=["copilot", "code-assistant"])
        assert "Developer Tooling" in tags

    def test_mcp_tag_from_description(self):
        tags = classify_project(description="Model Context Protocol server implementation")
        assert "MCP" in tags

    def test_multiple_tags(self):
        tags = classify_project(
            name="agent-framework",
            description="RAG-powered agent with evaluation",
            topics=["mcp"],
        )
        assert "Agent" in tags
        assert "RAG" in tags
        assert "Eval" in tags
        assert "MCP" in tags

    def test_no_tags_for_irrelevant_project(self):
        tags = classify_project(
            name="random-tool",
            description="A random utility with no AI keywords",
        )
        assert tags == []

    def test_classify_from_dict(self):
        project_dict = {
            "name": "langchain",
            "description": "Building LLM agent applications",
            "topics": ["agent", "llm"],
            "readme_summary": "",
        }
        tags = classify_project_dict(project_dict)
        assert "Agent" in tags

    def test_empty_input_returns_empty(self):
        tags = classify_project()
        assert tags == []

    def test_tags_are_sorted_and_deduplicated(self):
        tags = classify_project(
            name="agent-agent-agent",
            description="agent agent",
            topics=["agent"],
        )
        # Should not have duplicates
        assert tags.count("Agent") == 1


# ── Project Filter Tests ─────────────────────────────────────────


class TestProjectFilter:
    """Tests for project_filter.py hard filtering."""

    def test_needs_review_for_good_project(self):
        result = filter_project(stars=500, is_archived=False)
        assert result["filter_status"] == "needs_review"
        assert result["filter_reason"] is None

    def test_filtered_out_low_stars(self):
        result = filter_project(stars=50, is_archived=False)
        assert result["filter_status"] == "filtered_out"
        assert "Stars 50 below threshold" in result["filter_reason"]

    def test_filtered_out_archived(self):
        result = filter_project(stars=5000, is_archived=True)
        assert result["filter_status"] == "filtered_out"
        assert "archived" in result["filter_reason"].lower()

    def test_filtered_out_inactive(self):
        old_date = datetime.now(timezone.utc) - timedelta(days=120)
        result = filter_project(stars=500, last_pushed_at=old_date, is_archived=False)
        assert result["filter_status"] == "filtered_out"
        assert "Inactive" in result["filter_reason"]

    def test_active_project_passes(self):
        recent_date = datetime.now(timezone.utc) - timedelta(days=10)
        result = filter_project(stars=500, last_pushed_at=recent_date, is_archived=False)
        assert result["filter_status"] == "needs_review"

    def test_manual_override_preserved(self):
        result = filter_project(
            stars=5,
            filter_status="override",
            filter_reason="Team uses this internally",
        )
        assert result["filter_status"] == "override"
        assert result["filter_reason"] == "Team uses this internally"

    def test_override_survives_archived(self):
        """Even if archived, override status should be preserved."""
        result = filter_project(
            stars=5,
            is_archived=True,
            filter_status="override",
            filter_reason="Critical internal dependency",
        )
        assert result["filter_status"] == "override"

    def test_filter_from_dict(self):
        project_dict = {
            "stars": 10,
            "is_archived": False,
            "filter_status": "needs_review",
        }
        result = filter_project_dict(project_dict)
        assert result["filter_status"] == "filtered_out"

    def test_exactly_at_star_threshold_passes(self):
        """Project at exactly the threshold should pass."""
        result = filter_project(stars=200, is_archived=False)
        assert result["filter_status"] == "needs_review"

    def test_naive_datetime_handled(self):
        """Naive datetime (no tzinfo) should be treated as UTC."""
        old_date = datetime.utcnow() - timedelta(days=120)
        result = filter_project(stars=500, last_pushed_at=old_date, is_archived=False)
        assert result["filter_status"] == "filtered_out"

    def test_no_last_pushed_at_passes(self):
        """If last_pushed_at is None, inactivity check is skipped."""
        result = filter_project(stars=500, last_pushed_at=None, is_archived=False)
        assert result["filter_status"] == "needs_review"


# ── Project Scorer Tests ─────────────────────────────────────────


class TestProjectScorer:
    """Tests for project_scorer.py scoring logic."""

    def test_scores_are_integers_in_range(self):
        result = score_project(
            name="test-project",
            description="An agent framework",
            stars=1000,
            forks=100,
            license="MIT",
            has_quickstart=True,
        )
        for key in ("relevance_score", "trialability_score", "value_score", "recommendation_score"):
            score = result[key]
            assert isinstance(score, int), f"{key} should be int, got {type(score)}"
            assert 1 <= score <= 10, f"{key}={score} not in [1, 10]"

    def test_high_star_project_scores_higher(self):
        high = score_project(stars=50000, forks=5000)
        low = score_project(stars=50, forks=1)
        assert high["value_score"] > low["value_score"]

    def test_tags_included_in_result(self):
        result = score_project(
            name="agent-framework",
            description="Multi-agent orchestration",
        )
        assert "Agent" in result["tags"]

    def test_preexisting_tags_preserved(self):
        """If tags are passed in, they should be used as-is."""
        result = score_project(tags=["Custom"])
        assert result["tags"] == ["Custom"]

    def test_evidence_is_string(self):
        result = score_project(stars=100, forks=10, license="MIT")
        assert isinstance(result["evidence"], str)
        assert len(result["evidence"]) > 0

    def test_licensed_project_higher_trialability(self):
        with_license = score_project(license="MIT")
        without = score_project(license=None)
        assert with_license["trialability_score"] >= without["trialability_score"]

    def test_quickstart_boosts_trialability(self):
        with_qs = score_project(has_quickstart=True)
        without_qs = score_project(has_quickstart=False)
        assert with_qs["trialability_score"] > without_qs["trialability_score"]

    def test_score_from_dict(self):
        project_dict = {
            "name": "rag-engine",
            "description": "Retrieval augmented generation",
            "stars": 3000,
            "forks": 300,
            "license": "Apache-2.0",
            "has_quickstart": True,
            "topics": ["rag", "vector-search"],
        }
        result = score_project_dict(project_dict)
        assert "RAG" in result["tags"]
        assert result["relevance_score"] >= 5
        assert result["trialability_score"] >= 5

    def test_relevance_boost_for_high_signal_keywords(self):
        result = score_project(
            name="llm-agent",
            description="An agent framework for LLM applications",
        )
        assert result["relevance_score"] >= 5

    def test_zero_stars_low_value(self):
        result = score_project(stars=0, forks=0)
        assert result["value_score"] <= 3

    def test_recommendation_is_weighted_average(self):
        """Recommendation should be roughly 0.4*relevance + 0.3*trial + 0.3*value."""
        result = score_project(
            name="test",
            description="agent framework",
            stars=1000,
            forks=100,
            license="MIT",
            has_quickstart=True,
        )
        expected = round(
            result["relevance_score"] * 0.4
            + result["trialability_score"] * 0.3
            + result["value_score"] * 0.3
        )
        assert result["recommendation_score"] == expected
