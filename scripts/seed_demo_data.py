"""Seed demo data for MVP end-to-end verification.

Creates:
- 5 Baseline projects
- 10 Candidate projects (some filtered out)
- 2 Evaluations
- 2 Trials
- 1 Share
- Graph nodes/edges via graph_builder

Usage:
    python scripts/seed_demo_data.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session

from src.models import Evaluation, Project, Share, Trial
from src.repositories import (
    EvaluationRepository,
    ProjectRepository,
    ShareRepository,
    TrialRepository,
)
from src.services.classifier import classify_project
from src.services.graph_builder import (
    add_dependency,
    add_similar_to,
    build_project_graph,
    build_share_graph,
)
from src.services.project_filter import filter_project
from src.services.project_scorer import score_project


def _utc(days_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


# ── Project definitions ──────────────────────────────────────────────

BASELINE_PROJECTS: list[dict] = [
    {
        "github_url": "https://github.com/langchain-ai/langchain",
        "repo_full_name": "langchain-ai/langchain",
        "name": "LangChain",
        "description": "Build context-aware reasoning applications",
        "pool": "baseline",
        "source": "baseline",
        "stars": 95000,
        "forks": 15000,
        "language": "Python",
        "topics": ["llm", "agent", "rag", "nlp", "chains"],
        "tags": ["Agent", "RAG", "Workflow"],
        "license": "MIT",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(2),
    },
    {
        "github_url": "https://github.com/openai/openai-python",
        "repo_full_name": "openai/openai-python",
        "name": "OpenAI Python SDK",
        "description": "The official Python library for the OpenAI API",
        "pool": "baseline",
        "source": "baseline",
        "stars": 25000,
        "forks": 3500,
        "language": "Python",
        "topics": ["openai", "llm", "api"],
        "tags": ["Inference"],
        "license": "Apache-2.0",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(1),
    },
    {
        "github_url": "https://github.com/run-llama/llama_index",
        "repo_full_name": "run-llama/llama_index",
        "name": "LlamaIndex",
        "description": "LlamaIndex is a data framework for LLM-based applications",
        "pool": "baseline",
        "source": "baseline",
        "stars": 38000,
        "forks": 5200,
        "language": "Python",
        "topics": ["rag", "llm", "index", "retrieval"],
        "tags": ["RAG"],
        "license": "MIT",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(3),
    },
    {
        "github_url": "https://github.com/deepseek-ai/DeepSeek-V3",
        "repo_full_name": "deepseek-ai/DeepSeek-V3",
        "name": "DeepSeek-V3",
        "description": "DeepSeek-V3 inference engine and model weights",
        "pool": "baseline",
        "source": "baseline",
        "stars": 42000,
        "forks": 4800,
        "language": "Python",
        "topics": ["inference", "llm", "model", "deepseek"],
        "tags": ["Inference"],
        "license": "MIT",
        "has_quickstart": False,
        "last_pushed_at": lambda: _utc(7),
    },
    {
        "github_url": "https://github.com/modelcontextprotocol/servers",
        "repo_full_name": "modelcontextprotocol/servers",
        "name": "MCP Servers",
        "description": "Model Context Protocol reference server implementations",
        "pool": "baseline",
        "source": "baseline",
        "stars": 35000,
        "forks": 4100,
        "language": "Python",
        "topics": ["mcp", "tools", "agent", "protocol"],
        "tags": ["MCP", "Agent"],
        "license": "MIT",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(5),
    },
]

CANDIDATE_PROJECTS: list[dict] = [
    # --- Pass filter (stars >= 200, recently active) ---
    {
        "github_url": "https://github.com/crewAIInc/crewAI",
        "repo_full_name": "crewAIInc/crewAI",
        "name": "crewAI",
        "description": "Framework for orchestrating role-playing AI agents",
        "pool": "candidate",
        "source": "github_search",
        "stars": 22000,
        "forks": 3100,
        "language": "Python",
        "topics": ["agent", "multi-agent", "ai", "crew"],
        "tags": ["Agent"],
        "license": "MIT",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(4),
    },
    {
        "github_url": "https://github.com/microsoft/autogen",
        "repo_full_name": "microsoft/autogen",
        "name": "AutoGen",
        "description": "Enable next-gen LLM applications via multi-agent conversation",
        "pool": "candidate",
        "source": "github_search",
        "stars": 40000,
        "forks": 5800,
        "language": "Python",
        "topics": ["agent", "multi-agent", "llm", "conversation"],
        "tags": ["Agent", "Workflow"],
        "license": "MIT",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(6),
    },
    {
        "github_url": "https://github.com/sgl-project/sglang",
        "repo_full_name": "sgl-project/sglang",
        "name": "SGLang",
        "description": "SGLang is a structured generation language for LLMs",
        "pool": "candidate",
        "source": "github_search",
        "stars": 8000,
        "forks": 800,
        "language": "Python",
        "topics": ["inference", "llm", "structured-generation"],
        "tags": ["Inference"],
        "license": "Apache-2.0",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(2),
    },
    {
        "github_url": "https://github.com/unclecode/crawl4ai",
        "repo_full_name": "unclecode/crawl4ai",
        "name": "Crawl4AI",
        "description": "LLM-friendly web crawler and scraper for RAG pipelines",
        "pool": "candidate",
        "source": "github_search",
        "stars": 15000,
        "forks": 1100,
        "language": "Python",
        "topics": ["crawler", "rag", "web-scraping"],
        "tags": ["RAG"],
        "license": "Apache-2.0",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(8),
    },
    {
        "github_url": "https://github.com/anthropics/anthropic-cookbook",
        "repo_full_name": "anthropics/anthropic-cookbook",
        "name": "Anthropic Cookbook",
        "description": "Examples and guides for building with the Anthropic API",
        "pool": "candidate",
        "source": "github_search",
        "stars": 6000,
        "forks": 750,
        "language": "Python",
        "topics": ["claude", "llm", "examples"],
        "tags": ["Developer Tooling"],
        "license": "MIT",
        "has_quickstart": False,
        "last_pushed_at": lambda: _utc(10),
    },
    {
        "github_url": "https://github.com/brainblend-ai/promptfoo",
        "repo_full_name": "brainblend-ai/promptfoo",
        "name": "promptfoo",
        "description": "Test your LLM app, catch regressions, evaluate prompts",
        "pool": "candidate",
        "source": "github_search",
        "stars": 4500,
        "forks": 350,
        "language": "TypeScript",
        "topics": ["eval", "testing", "llm", "prompt"],
        "tags": ["Eval"],
        "license": "MIT",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(3),
    },
    {
        "github_url": "https://github.com/flowise-ai/flowise",
        "repo_full_name": "flowise-ai/flowise",
        "name": "Flowise",
        "description": "Drag & drop UI to build LLM-powered apps",
        "pool": "candidate",
        "source": "external",
        "stars": 32000,
        "forks": 16000,
        "language": "TypeScript",
        "topics": ["workflow", "llm", "no-code"],
        "tags": ["Workflow"],
        "license": "Apache-2.0",
        "has_quickstart": True,
        "last_pushed_at": lambda: _utc(12),
    },
    # --- Filtered out (low stars) ---
    {
        "github_url": "https://github.com/example/tiny-agent",
        "repo_full_name": "example/tiny-agent",
        "name": "TinyAgent",
        "description": "A minimal agent framework for learning",
        "pool": "candidate",
        "source": "github_search",
        "stars": 50,
        "forks": 5,
        "language": "Python",
        "topics": ["agent"],
        "tags": ["Agent"],
        "license": "MIT",
        "has_quickstart": False,
        "last_pushed_at": lambda: _utc(15),
    },
    # --- Filtered out (archived) ---
    {
        "github_url": "https://github.com/example/old-toolkit",
        "repo_full_name": "example/old-toolkit",
        "name": "OldToolkit",
        "description": "Archived AI dev toolkit",
        "pool": "candidate",
        "source": "manual",
        "stars": 500,
        "forks": 30,
        "language": "Python",
        "topics": ["toolkit"],
        "tags": ["Developer Tooling"],
        "license": "MIT",
        "has_quickstart": False,
        "is_archived": True,
        "last_pushed_at": lambda: _utc(120),
    },
    # --- Filtered out (inactive) ---
    {
        "github_url": "https://github.com/example/stale-inference",
        "repo_full_name": "example/stale-inference",
        "name": "StaleInference",
        "description": "An inference library no longer maintained",
        "pool": "candidate",
        "source": "github_search",
        "stars": 1200,
        "forks": 100,
        "language": "Python",
        "topics": ["inference"],
        "tags": ["Inference"],
        "license": "MIT",
        "has_quickstart": False,
        "last_pushed_at": lambda: _utc(200),
    },
]


def seed(session: Session) -> dict:
    """Seed all demo data and return summary statistics."""
    project_repo = ProjectRepository(session)
    eval_repo = EvaluationRepository(session)
    trial_repo = TrialRepository(session)
    share_repo = ShareRepository(session)

    created_projects: list[Project] = []

    # ── 1. Insert projects ───────────────────────────────────────────
    all_defs = BASELINE_PROJECTS + CANDIDATE_PROJECTS
    for pdef in all_defs:
        # Resolve lambda fields
        resolved = {}
        for k, v in pdef.items():
            resolved[k] = v() if callable(v) else v

        # Apply filter
        filter_result = filter_project(
            stars=resolved.get("stars", 0),
            last_pushed_at=resolved.get("last_pushed_at"),
            is_archived=resolved.get("is_archived", False),
            filter_status=resolved.get("filter_status", "needs_review"),
            filter_reason=resolved.get("filter_reason"),
        )
        resolved["filter_status"] = filter_result["filter_status"]
        resolved["filter_reason"] = filter_result["filter_reason"]

        # Classify tags if not set
        if not resolved.get("tags"):
            resolved["tags"] = classify_project(
                name=resolved.get("name", ""),
                description=resolved.get("description", ""),
                topics=resolved.get("topics", []),
            )

        project = project_repo.upsert(Project(**resolved))
        created_projects.append(project)

        # Build graph for each project
        build_project_graph(session, project)

    print(f"  Inserted {len(created_projects)} projects")

    # ── 2. Create evaluations for 2 projects ─────────────────────────
    # Evaluate crewAI (index 5)
    crewai = created_projects[5]
    score_crewai = score_project(
        name=crewai.name,
        description=crewai.description,
        topics=crewai.topics,
        stars=crewai.stars,
        forks=crewai.forks,
        license=crewai.license,
        has_quickstart=crewai.has_quickstart,
        tags=crewai.tags,
    )
    eval_repo.create(Evaluation(
        project_id=crewai.id,
        relevance_score=score_crewai["relevance_score"],
        trialability_score=score_crewai["trialability_score"],
        value_score=score_crewai["value_score"],
        recommendation_score=score_crewai["recommendation_score"],
        decision="try",
        decision_reason="Multi-agent framework, active community",
        evidence=score_crewai["evidence"],
        evaluated_by="demo_user",
    ))
    crewai = project_repo.get(crewai.id)  # refresh
    print(f"  Created evaluation for {crewai.name} (decision=try)")

    # Evaluate AutoGen (index 6)
    autogen = created_projects[6]
    score_autogen = score_project(
        name=autogen.name,
        description=autogen.description,
        topics=autogen.topics,
        stars=autogen.stars,
        forks=autogen.forks,
        license=autogen.license,
        has_quickstart=autogen.has_quickstart,
        tags=autogen.tags,
    )
    eval_repo.create(Evaluation(
        project_id=autogen.id,
        relevance_score=score_autogen["relevance_score"],
        trialability_score=score_autogen["trialability_score"],
        value_score=score_autogen["value_score"],
        recommendation_score=score_autogen["recommendation_score"],
        decision="watch",
        decision_reason="Interesting but complex, keep watching",
        evidence=score_autogen["evidence"],
        evaluated_by="demo_user",
    ))
    autogen = project_repo.get(autogen.id)
    print(f"  Created evaluation for {autogen.name} (decision=watch)")

    # ── 3. Create 2 trials ───────────────────────────────────────────
    # Trial 1: crewAI -> claimed -> running -> demo_done
    trial1 = trial_repo.create(Trial(
        project_id=crewai.id,
        owner="alice",
        status="demo_done",
        due_date=date.today() + timedelta(days=14),
        environment="Python 3.11 + conda",
        demo_url="https://demo.example.com/crewai",
        trial_notes="Tested multi-agent collaboration with 3 agents",
        result_summary="CrewAI provides intuitive agent orchestration, good for structured tasks",
        next_action="Prepare share for team meeting",
    ))
    print(f"  Created trial for {crewai.name} (status=demo_done)")

    # Trial 2: SGLang (index 7) -> claimed -> running
    sglang = created_projects[7]
    trial_repo.create(Trial(
        project_id=sglang.id,
        owner="bob",
        status="running",
        due_date=date.today() + timedelta(days=7),
        environment="Docker + A100 GPU",
        trial_notes="Benchmarking inference throughput vs vLLM",
    ))
    print(f"  Created trial for {sglang.name} (status=running)")

    # ── 4. Create 1 share from trial1 ────────────────────────────────
    share1 = share_repo.create(Share(
        trial_id=trial1.id,
        title="CrewAI Multi-Agent 试用分享",
        summary="CrewAI is an effective framework for orchestrating role-playing AI agents with clear abstractions.",
        key_findings="1. Agent definition via YAML config is intuitive\n2. Built-in memory and tool integration\n3. Supports sequential and hierarchical processes",
        reusable_patterns="Agent role template pattern; Tool callback pattern; Memory backends",
        applicable_scenarios="Structured multi-step tasks; Customer support automation; Data analysis pipelines",
        shared_by="alice",
    ))
    # Update trial status to shared
    trial1.status = "shared"
    trial_repo.update(trial1)

    # Build share graph (TeamAsset + produced edge)
    build_share_graph(session, share1)
    print(f"  Created share '{share1.title}'")

    # ── 5. Add extra graph relationships ──────────────────────────────
    # Dependency: LangChain depends on OpenAI SDK
    langchain = created_projects[0]
    add_dependency(session, langchain, "openai-python")
    print(f"  Added dependency: {langchain.name} -> openai-python")

    # Similar: crewAI similar to AutoGen
    add_similar_to(session, crewai, autogen, evidence="Both are multi-agent frameworks")
    print(f"  Added similar_to: {crewai.name} <-> {autogen.name}")

    # ── Summary ───────────────────────────────────────────────────────
    summary = {
        "projects": len(created_projects),
        "evaluations": 2,
        "trials": 2,
        "shares": 1,
    }
    return summary


def main() -> None:
    from sqlalchemy import create_engine as sa_create_engine
    from sqlmodel import SQLModel

    db_path = Path(__file__).resolve().parent.parent / "data" / "demo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing demo db
    if db_path.exists():
        db_path.unlink()

    engine = sa_create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    from sqlmodel import Session
    with Session(engine) as session:
        print("Seeding demo data...")
        summary = seed(session)
        print(f"\nDone! Summary: {summary}")
        print(f"Demo database: {db_path}")


if __name__ == "__main__":
    main()
