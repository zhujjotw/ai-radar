"""Smoke test script for MVP end-to-end verification (T10).

Runs the complete MVP lifecycle:
  1. Initialize database
  2. Seed demo data
  3. Filter + classify + score
  4. Query project ego graph
  5. Export Markdown
  6. Reverse lookups

Usage:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, SQLModel, create_engine

from src.repositories import (
    ProjectRepository,
    ShareRepository,
    TrialRepository,
)
from src.services.classifier import classify_project
from src.services.graph_builder import (
    find_projects_by_capability,
    find_projects_by_dependency,
    find_projects_by_domain,
    get_project_ego_graph,
)
from src.services.markdown_export import (
    export_evaluation_markdown,
    export_share_markdown,
    export_trial_markdown,
)
from src.services.project_scorer import score_project


passed = 0
failed = 0


def check(description: str, assertion: bool, detail: str = "") -> None:
    global passed, failed
    if assertion:
        passed += 1
        print(f"  [PASS] {description}")
    else:
        failed += 1
        msg = f"  [FAIL] {description}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def run_smoke_test() -> None:
    # ── Step 1: Initialize in-memory database ──────────────────────────
    print("\n[Step 1] Initialize database")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        project_repo = ProjectRepository(session)
        trial_repo = TrialRepository(session)
        share_repo = ShareRepository(session)

        # ── Step 2: Seed demo data via seed_demo_data ─────────────────
        print("\n[Step 2] Seed demo data")
        from scripts.seed_demo_data import seed

        summary = seed(session)
        check("15 projects created", summary["projects"] == 15)
        check("2 evaluations created", summary["evaluations"] == 2)
        check("2 trials created", summary["trials"] == 2)
        check("1 share created", summary["shares"] == 1)

        # Verify baseline / candidate counts
        baseline = project_repo.list(pool="baseline")
        candidates = project_repo.list(pool="candidate")
        check("5 baseline projects", len(baseline) == 5)
        check("10 candidate projects", len(candidates) == 10)

        # ── Step 3: Filter + classify + score ─────────────────────────
        print("\n[Step 3] Filter + classify + score")
        # Verify some projects are filtered out
        filtered = project_repo.list(filter_status="filtered_out")
        check("At least 2 projects filtered out", len(filtered) >= 2)

        # Classify a project
        crewai = project_repo.get_by_repo_full_name("crewAIInc/crewAI")
        check("Found crewAI project", crewai is not None)
        tags = classify_project(
            name=crewai.name,
            description=crewai.description or "",
            topics=crewai.topics,
        )
        check("crewAI tagged as Agent", "Agent" in tags)

        # Score a project
        score_result = score_project(
            name=crewai.name,
            description=crewai.description or "",
            topics=crewai.topics,
            stars=crewai.stars,
            forks=crewai.forks,
            license=crewai.license,
            has_quickstart=crewai.has_quickstart,
            tags=crewai.tags,
        )
        check("Recommendation score >= 1", score_result["recommendation_score"] >= 1)
        check("Evidence is non-empty", len(score_result["evidence"]) > 0)

        # ── Step 4: Query ego graph ────────────────────────────────────
        print("\n[Step 4] Query ego graph")
        langchain = project_repo.get_by_repo_full_name("langchain-ai/langchain")
        check("Found LangChain project", langchain is not None)

        ego = get_project_ego_graph(session, langchain.id)
        check("Ego graph has nodes", len(ego["nodes"]) > 0)
        check("Ego graph has edges", len(ego["edges"]) > 0)

        node_types = {n["node_type"] for n in ego["nodes"]}
        check("Ego graph has Domain nodes", "Domain" in node_types)
        check("Ego graph has Project node", "Project" in node_types)

        relation_types = {e["relation_type"] for e in ego["edges"]}
        check("Ego graph has belongs_to edges", "belongs_to" in relation_types)

        # Check TeamAsset from share
        crewai_ego = get_project_ego_graph(session, crewai.id)
        crewai_node_types = {n["node_type"] for n in crewai_ego["nodes"]}
        check("crewAI ego has TeamAsset node", "TeamAsset" in crewai_node_types)

        crewai_edge_types = {e["relation_type"] for e in crewai_ego["edges"]}
        check("crewAI ego has produced edge", "produced" in crewai_edge_types)

        # ── Step 5: Export Markdown ────────────────────────────────────
        print("\n[Step 5] Export Markdown")
        md_eval = export_evaluation_markdown(session, crewai.id)
        check("Evaluation markdown contains crewAI", "crewAI" in md_eval)
        check("Evaluation markdown contains try", "try" in md_eval)

        shares = share_repo.list_all()
        check("1 share exists", len(shares) == 1)
        md_share = export_share_markdown(session, shares[0].id)
        check("Share markdown contains title", "CrewAI" in md_share)
        check("Share markdown contains findings section", "核心发现" in md_share)

        trials = trial_repo.list_by_status("shared")
        check("1 shared trial exists", len(trials) == 1)
        md_trial = export_trial_markdown(session, trials[0].id)
        check("Trial markdown contains 试用记录", "试用记录" in md_trial)

        # ── Step 6: Reverse lookups ───────────────────────────────────
        print("\n[Step 6] Reverse lookups")
        agent_projects = find_projects_by_domain(session, "Agent")
        agent_names = {p.name for p in agent_projects}
        check("Agent domain returns projects", len(agent_projects) > 0)
        check(
            "LangChain or crewAI in Agent domain",
            "LangChain" in agent_names or "crewAI" in agent_names,
        )

        dep_projects = find_projects_by_dependency(session, "openai-python")
        dep_names = {p.name for p in dep_projects}
        check("openai-python dependency returns LangChain", "LangChain" in dep_names)

        cap_projects = find_projects_by_capability(session, "multi-agent")
        cap_names = {p.name for p in cap_projects}
        check("multi-agent capability returns crewAI", "crewAI" in cap_names)

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"Smoke test: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_smoke_test()
