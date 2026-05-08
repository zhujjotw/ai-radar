"""Built-in baseline project list for initial database seeding.

Each entry maps to a well-known AI open-source project that the team should
track.  The data is intentionally *static* — live metadata (stars, forks, …)
will be refreshed by ``refresh_projects.py`` or the GitHub search module.
"""

from __future__ import annotations

from src.models import Project

# fmt: off
BASELINE_PROJECTS: list[dict] = [
    # ── Agent ──────────────────────────────────────────────────────────────
    {
        "github_url": "https://github.com/langchain-ai/langchain",
        "repo_full_name": "langchain-ai/langchain",
        "name": "LangChain",
        "description": "Build context-aware reasoning applications",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Agent", "Workflow"],
    },
    {
        "github_url": "https://github.com/langchain-ai/langgraph",
        "repo_full_name": "langchain-ai/langgraph",
        "name": "LangGraph",
        "description": "Build resilient agents as graphs",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Agent"],
    },
    {
        "github_url": "https://github.com/crewAIInc/crewAI",
        "repo_full_name": "crewAIInc/crewAI",
        "name": "CrewAI",
        "description": "Framework for orchestrating role-playing autonomous AI agents",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Agent"],
    },
    {
        "github_url": "https://github.com/microsoft/autogen",
        "repo_full_name": "microsoft/autogen",
        "name": "AutoGen",
        "description": "Enable next-gen LLM applications via multi-agent conversation",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Agent"],
    },
    {
        "github_url": "https://github.com/openai/openai-agents-python",
        "repo_full_name": "openai/openai-agents-python",
        "name": "OpenAI Agents SDK",
        "description": "A lightweight, multi-agent framework built by OpenAI",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Agent"],
    },
    # ── RAG ────────────────────────────────────────────────────────────────
    {
        "github_url": "https://github.com/run-llama/llama_index",
        "repo_full_name": "run-llama/llama_index",
        "name": "LlamaIndex",
        "description": "LlamaIndex is a data framework for LLM-based applications",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["RAG"],
    },
    {
        "github_url": "https://github.com/chroma-core/chroma",
        "repo_full_name": "chroma-core/chroma",
        "name": "Chroma",
        "description": "The AI-native open-source embedding database",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["RAG"],
    },
    # ── Eval ───────────────────────────────────────────────────────────────
    {
        "github_url": "https://github.com/confident-ai/deepeval",
        "repo_full_name": "confident-ai/deepeval",
        "name": "DeepEval",
        "description": "The open-source LLM evaluation framework",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Eval"],
    },
    {
        "github_url": "https://github.com/explodinggradients/ragas",
        "repo_full_name": "explodinggradients/ragas",
        "name": "Ragas",
        "description": "Evaluation framework for RAG pipelines",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Eval", "RAG"],
    },
    # ── Inference ──────────────────────────────────────────────────────────
    {
        "github_url": "https://github.com/vllm-project/vllm",
        "repo_full_name": "vllm-project/vllm",
        "name": "vLLM",
        "description": "High-throughput and memory-efficient inference and serving engine for LLMs",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Inference"],
    },
    {
        "github_url": "https://github.com/ollama/ollama",
        "repo_full_name": "ollama/ollama",
        "name": "Ollama",
        "description": "Get up and running with Llama 3, Mistral, and other large language models",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Inference"],
    },
    {
        "github_url": "https://github.com/ggerganov/llama.cpp",
        "repo_full_name": "ggerganov/llama.cpp",
        "name": "llama.cpp",
        "description": "LLM inference in C/C++",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Inference"],
    },
    # ── Workflow ───────────────────────────────────────────────────────────
    {
        "github_url": "https://github.com/n8n-io/n8n",
        "repo_full_name": "n8n-io/n8n",
        "name": "n8n",
        "description": "Fair-code licensed workflow automation platform",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Workflow"],
    },
    {
        "github_url": "https://github.com/langgenius/dify",
        "repo_full_name": "langgenius/dify",
        "name": "Dify",
        "description": "Open-source LLM app development platform — workflow, RAG, agent",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Workflow", "RAG", "Agent"],
    },
    # ── Developer Tooling ──────────────────────────────────────────────────
    {
        "github_url": "https://github.com/continuedev/continue",
        "repo_full_name": "continuedev/continue",
        "name": "Continue",
        "description": "The leading open-source AI code assistant",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Developer Tooling"],
    },
    {
        "github_url": "https://github.com/codestoryai/aide",
        "repo_full_name": "codestoryai/aide",
        "name": "Aide",
        "description": "The open-source AI-powered IDE",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Developer Tooling"],
    },
    # ── MCP ────────────────────────────────────────────────────────────────
    {
        "github_url": "https://github.com/modelcontextprotocol/servers",
        "repo_full_name": "modelcontextprotocol/servers",
        "name": "MCP Servers",
        "description": "Model Context Protocol reference server implementations",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["MCP"],
    },
    {
        "github_url": "https://github.com/modelcontextprotocol/python-sdk",
        "repo_full_name": "modelcontextprotocol/python-sdk",
        "name": "MCP Python SDK",
        "description": "The official Python SDK for Model Context Protocol",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["MCP"],
    },
    # ── Cross-domain / General ─────────────────────────────────────────────
    {
        "github_url": "https://github.com/huggingface/transformers",
        "repo_full_name": "huggingface/transformers",
        "name": "Transformers",
        "description": "State-of-the-art ML library for PyTorch, TensorFlow, JAX",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Inference", "Eval"],
    },
    {
        "github_url": "https://github.com/huggingface/text-generation-inference",
        "repo_full_name": "huggingface/text-generation-inference",
        "name": "TGI",
        "description": "Large Language Model Text Generation Inference",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Inference"],
    },
    {
        "github_url": "https://github.com/open-webui/open-webui",
        "repo_full_name": "open-webui/open-webui",
        "name": "Open WebUI",
        "description": "User-friendly AI frontend supporting Ollama and OpenAI-compatible APIs",
        "pool": "baseline",
        "source": "baseline",
        "tags": ["Inference", "Developer Tooling"],
    },
]
# fmt: on


def get_baseline_projects() -> list[Project]:
    """Return baseline projects as unsaved ``Project`` model instances.

    The caller is responsible for persisting these via ``ProjectRepository``.
    """
    return [Project(**data) for data in BASELINE_PROJECTS]
