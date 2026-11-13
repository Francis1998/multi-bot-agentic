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
"""

from __future__ import annotations

import re
from pathlib import Path

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
