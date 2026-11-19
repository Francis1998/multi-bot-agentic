"""Guard user-facing prose against retired model-stack boilerplate.

Guides, catalogs, and docstrings used to say a tool or advisor "works with
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2" long after the adapters
moved to GPT-6.1 Sol, Claude Opus 5.5, Gemini 4 Argon / 3.8 Flash, and Kimi
K3.1 Pro. Tool guides legitimately use old model names as *sample data* (CSV
rows, YAML lists, sorted lines), so this guard only flags retired names that
appear inside a model list, e.g. ``GPT-5.5 / Claude ...`` or ``..., or Kimi K2``.

Superseded models count as retired too: Claude Fable 5.2 replaced Fable 5.1, and
the Kimi K2 series closed to new users on 2026-10-31 (verified 2026-11-12). Model
IDs are matched with or without backticks, e.g. ``claude-haiku-5-5, claude-fable-5-1``.

Docs that state a provider's default model (the README and Configuration model-stack
tables, the Quickstart, ``.env.example``, and "``<model>`` by default" sentences) must
name the model the adapter really uses, so a default change cannot skip one of them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from multi_bot_agentic.config import build_llm_adapter
from multi_bot_agentic.llm.gemini import GeminiAdapter
from multi_bot_agentic.llm.openai import OpenAIAdapter

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]

_RETIRED = (
    r"(?:GPT-5\.\d|GPT-4o|Claude\s+(?:Sonnet|Opus)\s+4\.\d|Sonnet\s+4\.6"
    r"|Fable\s+5\.1\b|claude-fable-5-1\b"
    r"|Kimi\s+K2(?:\.\d+)?\b|kimi-k2[\w.-]*|Gemini\s+2\.5)"
)
_FAMILY = r"(?:GPT|Claude|Sonnet|Opus|Fable|Gemini|Kimi|gpt-|claude-|gemini-|kimi-)"
_JOIN = r"[*`]*\s*(?:/|,)\s*(?:or\s+|and\s+)?[*`]*\s*"
RETIRED_IN_MODEL_LIST = re.compile(rf"{_RETIRED}{_JOIN}{_FAMILY}|{_FAMILY}[\w.\- ]{{0,24}}?{_JOIN}{_RETIRED}")

EXEMPT = {Path("CHANGELOG.md"), Path("docs/PULL_SHARK_LOG.md")}

_MODEL_ID = r"(?:gpt|gemini|kimi)-[\w.-]*\w"
STATED_DEFAULT = re.compile(
    rf"`({_MODEL_ID})` by default|default model: `?({_MODEL_ID})|`({_MODEL_ID})` \((?:OpenAI|Gemini|Kimi)\)"
    rf"|^[A-Z]+_MODEL=({_MODEL_ID})$"
)
DEFAULT_COLUMNS = {"Default", "Default here"}


def _prose_files() -> list[Path]:
    """Return the user-facing docs, the env template, and non-test sources to scan."""
    files = [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md"), ROOT / ".env.example"]
    files += [*ROOT.glob("src/**/*.py"), *ROOT.glob("scripts/**/*.py")]
    return sorted(p for p in files if p.relative_to(ROOT) not in EXEMPT)


def test_scan_covers_guides_and_sources() -> None:
    """The guard must actually see the guides, catalogs, env template, and package sources."""
    rels = {p.relative_to(ROOT).as_posix() for p in _prose_files()}

    assert "README.md" in rels
    assert "docs/TOOLS.md" in rels
    assert ".env.example" in rels
    assert "src/multi_bot_agentic/runner.py" in rels
    assert sum(r.startswith("docs/guides/") for r in rels) > 100


def test_sample_data_is_not_flagged() -> None:
    """Old names used as tool sample data stay legal; model lists do not."""
    assert not RETIRED_IN_MODEL_LIST.search("model,score\\nGPT-5.5,95\\nClaude Sonnet 4.6,94")
    assert not RETIRED_IN_MODEL_LIST.search("  - Claude Sonnet 4.6")
    assert RETIRED_IN_MODEL_LIST.search("Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x")
    assert RETIRED_IN_MODEL_LIST.search("feeds GPT-6 Astra, Gemini 4 Argon, or Kimi K2.")


def test_superseded_models_are_flagged_in_id_lists() -> None:
    """Fable 5.1 and the closed Kimi K2 series are flagged in lists; naming what was superseded stays legal."""
    assert RETIRED_IN_MODEL_LIST.search("`claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-fable-5-1` |")
    assert RETIRED_IN_MODEL_LIST.search("# claude-haiku-5-5, claude-fable-5-1)")
    assert RETIRED_IN_MODEL_LIST.search("Claude Fable 5.1 / Claude Opus 5.5")
    assert RETIRED_IN_MODEL_LIST.search("`kimi-k3.1-pro`, `kimi-k2.6`")
    assert RETIRED_IN_MODEL_LIST.search("GPT-6 Astra / Kimi K2.7 Code")
    assert not RETIRED_IN_MODEL_LIST.search("`claude-fable-5-2` supersedes `claude-fable-5-1`.")
    assert not RETIRED_IN_MODEL_LIST.search("`claude-opus-5-5`, `claude-fable-5-2`, `claude-sonnet-5-5`")


def test_no_retired_model_lists_in_prose() -> None:
    """Docs and docstrings name the current model stack in model lists."""
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:120]}"
        for path in _prose_files()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if RETIRED_IN_MODEL_LIST.search(line)
    ]

    assert offenders == [], "retired model names in model lists:\n" + "\n".join(offenders[:40])


def _cells(row: str) -> list[str]:
    """Split a markdown table row into stripped cells."""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _stated_defaults(path: Path) -> list[str]:
    """Return the model IDs that ``path`` presents as a provider's default, in prose or a ``Default`` column."""
    stated: list[str] = []
    column: int | None = None
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stated += [model for groups in STATED_DEFAULT.findall(line) for model in groups if model]
        is_row = line.startswith("|")
        if is_row and not in_table:
            column = next((index for index, cell in enumerate(_cells(line)) if cell in DEFAULT_COLUMNS), None)
        elif is_row and column is not None:
            cell = re.fullmatch(rf"`({_MODEL_ID})`", _cells(line)[column])
            if cell:
                stated.append(cell.group(1))
        in_table = is_row
    return stated


def test_stated_defaults_match_the_adapters(monkeypatch: MonkeyPatch) -> None:
    """Every documented provider default is the model ``build_llm_adapter`` really uses.

    A default change, such as ``gpt-6.1-sol`` to ``gpt-6.2-sol`` on 2026-11-19, has to update the README and
    Configuration tables, the Quickstart, ``.env.example``, and the "``<model>`` by default" sentences together.
    """
    defaults: dict[str, str] = {}
    for provider in ("openai", "gemini", "kimi"):
        monkeypatch.setenv(f"{provider.upper()}_API_KEY", "dummy-key")
        monkeypatch.delenv(f"{provider.upper()}_MODEL", raising=False)
        adapter = build_llm_adapter(provider)
        assert isinstance(adapter, (OpenAIAdapter, GeminiAdapter))
        defaults[adapter.model.split("-")[0]] = adapter.model

    stated = [(path.relative_to(ROOT).as_posix(), model) for path in _prose_files() for model in _stated_defaults(path)]
    stale = [f"{doc}: {model}" for doc, model in stated if model != defaults[model.split("-")[0]]]
    covered = {(doc, model.split("-")[0]) for doc, model in stated}

    assert stale == [], f"docs state defaults other than {sorted(defaults.values())}"
    for doc in ("README.md", "docs/CONFIGURATION.md", "docs/QUICKSTART.md", ".env.example"):
        assert {(doc, family) for family in defaults} <= covered, f"{doc} no longer states every provider default"
