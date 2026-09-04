"""Safety policy for bounded agent execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class SafetyError(RuntimeError):
    """Raised when a safety policy blocks execution."""


@dataclass(frozen=True)
class SafetyPolicy:
    """Runtime safety controls.

    Attributes:
        max_steps: Maximum Observe -> Decide -> Act iterations.
        timeout_seconds: Provider/tool timeout budget.
        max_prompt_chars: Maximum accepted goal size.
        allowed_tools: Tool names allowed for execution.
        cancellation_file: Optional file whose existence cancels a run.
    """

    max_steps: int = 6
    timeout_seconds: float = 30.0
    max_prompt_chars: int = 4000
    allowed_tools: frozenset[str] = frozenset(
        {
            "base32_encode",
            "base58",
            "base64",
            "base85",
            "caesar_cipher",
            "calculator",
            "checklist",
            "content_type_sniff",
            "crc32",
            "cron_next",
            "csv",
            "csv_diff",
            "csv_fillna",
            "csv_filter",
            "csv_groupby",
            "csv_join",
            "csv_melt",
            "csv_pivot",
            "csv_select_columns",
            "csv_sort",
            "csv_stack",
            "csv_to_json",
            "csv_transpose",
            "csv_tsv",
            "csv_unique",
            "csv_window",
            "datetime",
            "diff",
            "duration",
            "echo",
            "hash",
            "hex_encode",
            "hmac_sign",
            "html_attr_extract",
            "html_entities",
            "html_links_extract",
            "html_markdown",
            "html_strip",
            "html_table",
            "html_table_csv",
            "iban_check",
            "ics_parse",
            "ini_parse",
            "isbn13",
            "json_diff_paths",
            "json_flatten",
            "json_format",
            "json_merge_patch",
            "json_patch_apply",
            "json_path",
            "json_pointer",
            "json_query",
            "json_unflatten",
            "jsonl_parse",
            "jwt_decode",
            "jwt_encode",
            "levenshtein",
            "line_number",
            "luhn",
            "markdown_table",
            "markdown_toc",
            "metaphone",
            "mime_attachment_cid_map",
            "mime_attachment_ctypes",
            "mime_attachment_disposition",
            "mime_attachment_encoding",
            "mime_attachment_filenames_unique",
            "mime_attachment_names",
            "mime_attachment_sizes",
            "mime_multipart",
            "mime_multipart_flatten",
            "mime_part_headers",
            "morse",
            "nato_phonetic",
            "pluralize",
            "punycode",
            "readonly_file",
            "redact",
            "regex",
            "regex_replace",
            "roman_numeral",
            "rot13",
            "semver_compare",
            "slugify",
            "soundex",
            "spreadsheet_slice",
            "template_render",
            "text_case",
            "text_center_lines",
            "text_collapse_blank",
            "text_dedent",
            "text_indent",
            "text_justify_lines",
            "text_margin_lines",
            "text_outdent",
            "text_pad_lines",
            "text_slug_lines",
            "text_sort_lines",
            "text_squeeze_ws",
            "text_title_lines",
            "text_unique_lines",
            "text_wrap",
            "toml_format",
            "toml_json",
            "truncate",
            "tsv_format",
            "ulid",
            "unicode_normalize",
            "url_encode",
            "url_normalize",
            "url_parse",
            "uuid4",
            "uuid5",
            "uuid_nil",
            "xml_escape",
            "xml_parse",
            "yaml_format",
            "yaml_to_json",
            "zip_list",
        }
    )
    cancellation_file: Path | None = None

    def validate_goal(self, goal: str) -> None:
        """Validate a user goal before starting a run.

        Args:
            goal: User goal.

        Raises:
            SafetyError: If the goal is empty or too large.
        """

        if not goal.strip():
            raise SafetyError("goal must be non-empty")
        if len(goal) > self.max_prompt_chars:
            raise SafetyError(f"goal exceeds max_prompt_chars={self.max_prompt_chars}")

    def validate_step(self, step: int) -> None:
        """Validate the current loop step.

        Args:
            step: Zero-based loop step.

        Raises:
            SafetyError: If the run exceeds max_steps.
        """

        if step >= self.max_steps:
            raise SafetyError(f"run exceeded max_steps={self.max_steps}")

    def validate_tool(self, tool_name: str) -> None:
        """Validate a tool against the allowlist.

        Args:
            tool_name: Tool name.

        Raises:
            SafetyError: If the tool is not allowed.
        """

        if tool_name not in self.allowed_tools:
            raise SafetyError(f"tool is not allowed: {tool_name}")

    def is_cancelled(self) -> bool:
        """Return whether a cancellation request is present.

        Returns:
            True when the configured cancellation file exists.
        """

        return self.cancellation_file is not None and self.cancellation_file.exists()
