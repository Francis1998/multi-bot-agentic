"""Observe -> Decide -> Act runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.lifecycle import InvalidTransitionError, RunStateMachine
from multi_bot_agentic.llm.base import LLMAdapter
from multi_bot_agentic.models import (
    Decision,
    EventType,
    ModelRequest,
    Observation,
    RunState,
    ToolInvocation,
)
from multi_bot_agentic.safety import SafetyError, SafetyPolicy
from multi_bot_agentic.tools.base import ToolAdapter


@dataclass(frozen=True)
class RunResult:
    """Final run result."""

    run_id: str
    state: RunState
    answer: str
    steps: int


class AgentRunner:
    """Runs an auditable Observe -> Decide -> Act loop."""

    def __init__(
        self,
        provider: LLMAdapter,
        event_log: SQLiteEventLog,
        tools: dict[str, ToolAdapter],
        safety_policy: SafetyPolicy,
    ) -> None:
        """Initialize the runner.

        Args:
            provider: LLM provider adapter.
            event_log: Durable event log.
            tools: Registered tool adapters by name.
            safety_policy: Runtime safety controls.
        """

        self.provider = provider
        self.event_log = event_log
        self.tools = tools
        self.safety_policy = safety_policy
        self.decision_engine = DeterministicDecisionEngine(provider_name=provider.provider_name)

    def run(self, goal: str, run_id: str | None = None) -> RunResult:
        """Execute one bounded agent run.

        Args:
            goal: User goal.
            run_id: Optional run identifier.

        Returns:
            Final run result.
        """

        self.safety_policy.validate_goal(goal)
        selected_run_id = run_id or str(uuid4())
        state_machine = RunStateMachine()
        observations: tuple[Observation, ...] = (Observation(source="user", content=goal),)
        self.event_log.append(
            selected_run_id,
            state_machine.state,
            EventType.RUN_CREATED,
            {"goal": goal, "provider": self.provider.provider_name},
        )

        try:
            for step in range(self.safety_policy.max_steps):
                self.safety_policy.validate_step(step)
                if self.safety_policy.is_cancelled():
                    return self._cancel(selected_run_id, state_machine, step, "cancellation requested")

                self._transition(selected_run_id, state_machine, RunState.OBSERVING)
                for observation in observations:
                    self.event_log.append(
                        selected_run_id,
                        state_machine.state,
                        EventType.OBSERVATION,
                        observation.to_dict(),
                    )

                self._transition(selected_run_id, state_machine, RunState.DECIDING)
                decision = self.decision_engine.decide(observations, step, self.safety_policy)
                self.event_log.append(
                    selected_run_id,
                    state_machine.state,
                    EventType.DECISION,
                    decision.to_dict(),
                )

                if decision.action == "finish":
                    return self._succeed(selected_run_id, state_machine, step + 1, decision)
                if decision.action == "cancel":
                    return self._cancel(
                        selected_run_id,
                        state_machine,
                        step + 1,
                        str(decision.payload.get("reason", "cancelled")),
                    )
                if decision.action == "fail":
                    return self._fail(
                        selected_run_id,
                        state_machine,
                        step + 1,
                        str(decision.payload.get("reason", "failed")),
                    )

                self._transition(selected_run_id, state_machine, RunState.ACTING)
                new_observation = self._act(selected_run_id, state_machine.state, goal, observations, decision)
                observations = (*observations, new_observation)

        except (InvalidTransitionError, SafetyError, OSError, RuntimeError, ValueError) as error:
            return self._fail(selected_run_id, state_machine, self.safety_policy.max_steps, str(error))

        return self._fail(selected_run_id, state_machine, self.safety_policy.max_steps, "step budget exhausted")

    def _act(
        self,
        run_id: str,
        state: RunState,
        goal: str,
        observations: tuple[Observation, ...],
        decision: Decision,
    ) -> Observation:
        """Execute a provider or tool action.

        Args:
            run_id: Run identifier.
            state: Current state.
            goal: User goal.
            observations: Current observations.
            decision: Selected decision.

        Returns:
            New observation produced by the action.
        """

        self.event_log.append(run_id, state, EventType.ACTION_REQUESTED, decision.to_dict())
        if decision.action == "call_llm":
            output = self.provider.complete(
                ModelRequest(goal=goal, observations=observations),
                timeout_seconds=self.safety_policy.timeout_seconds,
            )
            observation = output.to_observation()
            self.event_log.append(
                run_id,
                state,
                EventType.ACTION_RESULT,
                {"kind": "llm", "output": output.text, "metadata": output.raw},
            )
            return observation

        if decision.action == "call_tool":
            if decision.target is None:
                raise ValueError("tool decision requires a target")
            self.safety_policy.validate_tool(decision.target)
            tool = self.tools.get(decision.target)
            if tool is None:
                raise ValueError(f"tool is not registered: {decision.target}")
            result = tool.execute(ToolInvocation(tool_name=decision.target, arguments=decision.payload))
            self.event_log.append(
                run_id,
                state,
                EventType.ACTION_RESULT,
                {
                    "kind": "tool",
                    "tool": result.tool_name,
                    "ok": result.ok,
                    "content": result.content,
                    "metadata": result.metadata,
                },
            )
            return result.to_observation()

        raise ValueError(f"unsupported action for _act: {decision.action}")

    def _transition(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        next_state: RunState,
    ) -> None:
        """Transition and persist state-machine movement.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            next_state: Desired state.
        """

        previous_state, current_state = state_machine.transition_to(next_state)
        self.event_log.append(
            run_id,
            current_state,
            EventType.STATE_TRANSITION,
            {"from": previous_state.value, "to": current_state.value},
        )

    def _succeed(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        steps: int,
        decision: Decision,
    ) -> RunResult:
        """Mark a run as succeeded.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            steps: Step count.
            decision: Finish decision.

        Returns:
            Successful run result.
        """

        self._transition(run_id, state_machine, RunState.SUCCEEDED)
        answer = str(decision.payload.get("answer", ""))
        self.event_log.append(
            run_id,
            state_machine.state,
            EventType.RUN_COMPLETED,
            {"answer": answer, "steps": steps},
        )
        return RunResult(run_id=run_id, state=state_machine.state, answer=answer, steps=steps)

    def _cancel(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        steps: int,
        reason: str,
    ) -> RunResult:
        """Mark a run as cancelled.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            steps: Step count.
            reason: Cancellation reason.

        Returns:
            Cancelled run result.
        """

        self._transition(run_id, state_machine, RunState.CANCELLED)
        self.event_log.append(
            run_id,
            state_machine.state,
            EventType.RUN_CANCELLED,
            {"reason": reason, "steps": steps},
        )
        return RunResult(run_id=run_id, state=state_machine.state, answer=reason, steps=steps)

    def _fail(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        steps: int,
        reason: str,
    ) -> RunResult:
        """Mark a run as failed.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            steps: Step count.
            reason: Failure reason.

        Returns:
            Failed run result.
        """

        if not state_machine.is_terminal():
            self._transition(run_id, state_machine, RunState.FAILED)
        self.event_log.append(
            run_id,
            state_machine.state,
            EventType.RUN_FAILED,
            {"reason": reason, "steps": steps},
        )
        return RunResult(run_id=run_id, state=state_machine.state, answer=reason, steps=steps)


def build_default_tools(root: Path) -> dict[str, ToolAdapter]:
    """Build default allowlisted tools.

    Args:
        root: Root directory for read-only file access.

    Returns:
        Tool registry.
    """

    from multi_bot_agentic.tools.base32_encode import Base32EncodeTool
    from multi_bot_agentic.tools.base58 import Base58Tool
    from multi_bot_agentic.tools.base64_codec import Base64Tool
    from multi_bot_agentic.tools.base85 import Base85Tool
    from multi_bot_agentic.tools.calculator import CalculatorTool
    from multi_bot_agentic.tools.checklist import ChecklistTool
    from multi_bot_agentic.tools.content_type_sniff import ContentTypeSniffTool
    from multi_bot_agentic.tools.crc32 import Crc32Tool
    from multi_bot_agentic.tools.cron_next import CronNextTool
    from multi_bot_agentic.tools.csv_diff import CsvDiffTool
    from multi_bot_agentic.tools.csv_fillna import CsvFillnaTool
    from multi_bot_agentic.tools.csv_filter import CsvFilterTool
    from multi_bot_agentic.tools.csv_groupby import CsvGroupbyTool
    from multi_bot_agentic.tools.csv_join import CsvJoinTool
    from multi_bot_agentic.tools.csv_melt import CsvMeltTool
    from multi_bot_agentic.tools.csv_parse import CsvParseTool
    from multi_bot_agentic.tools.csv_pivot import CsvPivotTool
    from multi_bot_agentic.tools.csv_select_columns import CsvSelectColumnsTool
    from multi_bot_agentic.tools.csv_sort import CsvSortTool
    from multi_bot_agentic.tools.csv_stack import CsvStackTool
    from multi_bot_agentic.tools.csv_to_json import CsvToJsonTool
    from multi_bot_agentic.tools.csv_transpose import CsvTransposeTool
    from multi_bot_agentic.tools.csv_tsv import CsvTsvTool
    from multi_bot_agentic.tools.csv_unique import CsvUniqueTool
    from multi_bot_agentic.tools.csv_window import CsvWindowTool
    from multi_bot_agentic.tools.datetime_normalize import DateTimeTool
    from multi_bot_agentic.tools.diff_text import DiffTool
    from multi_bot_agentic.tools.duration_parse import DurationTool
    from multi_bot_agentic.tools.echo import EchoTool
    from multi_bot_agentic.tools.filesystem_readonly import ReadOnlyFileTool
    from multi_bot_agentic.tools.hashing import HashTool
    from multi_bot_agentic.tools.hex_encode import HexEncodeTool
    from multi_bot_agentic.tools.hmac_sign import HmacSignTool
    from multi_bot_agentic.tools.html_attr_extract import HtmlAttrExtractTool
    from multi_bot_agentic.tools.html_entities import HtmlEntitiesTool
    from multi_bot_agentic.tools.html_links_extract import HtmlLinksExtractTool
    from multi_bot_agentic.tools.html_markdown import HtmlMarkdownTool
    from multi_bot_agentic.tools.html_strip import HtmlStripTool
    from multi_bot_agentic.tools.html_table import HtmlTableTool
    from multi_bot_agentic.tools.html_table_csv import HtmlTableCsvTool
    from multi_bot_agentic.tools.ics_parse import IcsParseTool
    from multi_bot_agentic.tools.ini_parse import IniParseTool
    from multi_bot_agentic.tools.json_diff_paths import JsonDiffPathsTool
    from multi_bot_agentic.tools.json_flatten import JsonFlattenTool
    from multi_bot_agentic.tools.json_format import JsonFormatTool
    from multi_bot_agentic.tools.json_merge_patch import JsonMergePatchTool
    from multi_bot_agentic.tools.json_patch_apply import JsonPatchApplyTool
    from multi_bot_agentic.tools.json_path import JsonPathTool
    from multi_bot_agentic.tools.json_pointer import JsonPointerTool
    from multi_bot_agentic.tools.json_query import JsonQueryTool
    from multi_bot_agentic.tools.json_unflatten import JsonUnflattenTool
    from multi_bot_agentic.tools.jsonl_parse import JsonlParseTool
    from multi_bot_agentic.tools.jwt_decode import JwtDecodeTool
    from multi_bot_agentic.tools.jwt_encode import JwtEncodeTool
    from multi_bot_agentic.tools.levenshtein import LevenshteinTool
    from multi_bot_agentic.tools.line_number import LineNumberTool
    from multi_bot_agentic.tools.markdown_table import MarkdownTableTool
    from multi_bot_agentic.tools.markdown_toc import MarkdownTocTool
    from multi_bot_agentic.tools.metaphone import MetaphoneTool
    from multi_bot_agentic.tools.mime_attachment_cid_map import MimeAttachmentCidMapTool
    from multi_bot_agentic.tools.mime_attachment_ctypes import MimeAttachmentCtypesTool
    from multi_bot_agentic.tools.mime_attachment_disposition import MimeAttachmentDispositionTool
    from multi_bot_agentic.tools.mime_attachment_encoding import MimeAttachmentEncodingTool
    from multi_bot_agentic.tools.mime_attachment_filenames_unique import MimeAttachmentFilenamesUniqueTool
    from multi_bot_agentic.tools.mime_attachment_names import MimeAttachmentNamesTool
    from multi_bot_agentic.tools.mime_attachment_sizes import MimeAttachmentSizesTool
    from multi_bot_agentic.tools.mime_multipart import MimeMultipartTool
    from multi_bot_agentic.tools.mime_multipart_flatten import MimeMultipartFlattenTool
    from multi_bot_agentic.tools.mime_part_headers import MimePartHeadersTool
    from multi_bot_agentic.tools.pluralize import PluralizeTool
    from multi_bot_agentic.tools.punycode import PunycodeTool
    from multi_bot_agentic.tools.redaction import RedactionTool
    from multi_bot_agentic.tools.regex_extract import RegexExtractTool
    from multi_bot_agentic.tools.regex_replace import RegexReplaceTool
    from multi_bot_agentic.tools.rot13 import Rot13Tool
    from multi_bot_agentic.tools.semver_compare import SemverCompareTool
    from multi_bot_agentic.tools.slugify import SlugifyTool
    from multi_bot_agentic.tools.soundex import SoundexTool
    from multi_bot_agentic.tools.spreadsheet_slice import SpreadsheetSliceTool
    from multi_bot_agentic.tools.template_render import TemplateRenderTool
    from multi_bot_agentic.tools.text_case import TextCaseTool
    from multi_bot_agentic.tools.text_center_lines import TextCenterLinesTool
    from multi_bot_agentic.tools.text_collapse_blank import TextCollapseBlankTool
    from multi_bot_agentic.tools.text_dedent import TextDedentTool
    from multi_bot_agentic.tools.text_indent import TextIndentTool
    from multi_bot_agentic.tools.text_justify_lines import TextJustifyLinesTool
    from multi_bot_agentic.tools.text_margin_lines import TextMarginLinesTool
    from multi_bot_agentic.tools.text_outdent import TextOutdentTool
    from multi_bot_agentic.tools.text_pad_lines import TextPadLinesTool
    from multi_bot_agentic.tools.text_slug_lines import TextSlugLinesTool
    from multi_bot_agentic.tools.text_sort_lines import TextSortLinesTool
    from multi_bot_agentic.tools.text_squeeze_ws import TextSqueezeWsTool
    from multi_bot_agentic.tools.text_title_lines import TextTitleLinesTool
    from multi_bot_agentic.tools.text_truncate import TextTruncateTool
    from multi_bot_agentic.tools.text_unique_lines import TextUniqueLinesTool
    from multi_bot_agentic.tools.text_wrap import TextWrapTool
    from multi_bot_agentic.tools.toml_format import TomlFormatTool
    from multi_bot_agentic.tools.toml_json import TomlJsonTool
    from multi_bot_agentic.tools.tsv_format import TsvFormatTool
    from multi_bot_agentic.tools.unicode_normalize import UnicodeNormalizeTool
    from multi_bot_agentic.tools.url_encode import UrlEncodeTool
    from multi_bot_agentic.tools.url_normalize import UrlNormalizeTool
    from multi_bot_agentic.tools.url_parse import UrlParseTool
    from multi_bot_agentic.tools.uuid4 import Uuid4Tool
    from multi_bot_agentic.tools.uuid5 import Uuid5Tool
    from multi_bot_agentic.tools.uuid_nil import UuidNilTool
    from multi_bot_agentic.tools.xml_escape import XmlEscapeTool
    from multi_bot_agentic.tools.xml_parse import XmlParseTool
    from multi_bot_agentic.tools.yaml_format import YamlFormatTool
    from multi_bot_agentic.tools.yaml_to_json import YamlToJsonTool
    from multi_bot_agentic.tools.zip_list import ZipListTool

    return {
        "base32_encode": Base32EncodeTool(),
        "base58": Base58Tool(),
        "base64": Base64Tool(),
        "base85": Base85Tool(),
        "calculator": CalculatorTool(),
        "checklist": ChecklistTool(),
        "content_type_sniff": ContentTypeSniffTool(),
        "crc32": Crc32Tool(),
        "cron_next": CronNextTool(),
        "csv": CsvParseTool(),
        "csv_diff": CsvDiffTool(),
        "csv_fillna": CsvFillnaTool(),
        "csv_filter": CsvFilterTool(),
        "csv_groupby": CsvGroupbyTool(),
        "csv_join": CsvJoinTool(),
        "csv_melt": CsvMeltTool(),
        "csv_pivot": CsvPivotTool(),
        "csv_select_columns": CsvSelectColumnsTool(),
        "csv_sort": CsvSortTool(),
        "csv_stack": CsvStackTool(),
        "csv_to_json": CsvToJsonTool(),
        "csv_transpose": CsvTransposeTool(),
        "csv_tsv": CsvTsvTool(),
        "csv_unique": CsvUniqueTool(),
        "csv_window": CsvWindowTool(),
        "datetime": DateTimeTool(),
        "diff": DiffTool(),
        "duration": DurationTool(),
        "echo": EchoTool(),
        "hash": HashTool(),
        "hex_encode": HexEncodeTool(),
        "hmac_sign": HmacSignTool(),
        "html_attr_extract": HtmlAttrExtractTool(),
        "html_entities": HtmlEntitiesTool(),
        "html_links_extract": HtmlLinksExtractTool(),
        "html_markdown": HtmlMarkdownTool(),
        "html_strip": HtmlStripTool(),
        "html_table": HtmlTableTool(),
        "html_table_csv": HtmlTableCsvTool(),
        "ics_parse": IcsParseTool(),
        "ini_parse": IniParseTool(),
        "json_diff_paths": JsonDiffPathsTool(),
        "json_flatten": JsonFlattenTool(),
        "json_format": JsonFormatTool(),
        "json_merge_patch": JsonMergePatchTool(),
        "json_patch_apply": JsonPatchApplyTool(),
        "json_path": JsonPathTool(),
        "json_pointer": JsonPointerTool(),
        "json_query": JsonQueryTool(),
        "json_unflatten": JsonUnflattenTool(),
        "jsonl_parse": JsonlParseTool(),
        "jwt_decode": JwtDecodeTool(),
        "jwt_encode": JwtEncodeTool(),
        "levenshtein": LevenshteinTool(),
        "line_number": LineNumberTool(),
        "markdown_table": MarkdownTableTool(),
        "markdown_toc": MarkdownTocTool(),
        "metaphone": MetaphoneTool(),
        "mime_attachment_cid_map": MimeAttachmentCidMapTool(),
        "mime_attachment_ctypes": MimeAttachmentCtypesTool(),
        "mime_attachment_disposition": MimeAttachmentDispositionTool(),
        "mime_attachment_encoding": MimeAttachmentEncodingTool(),
        "mime_attachment_filenames_unique": MimeAttachmentFilenamesUniqueTool(),
        "mime_attachment_names": MimeAttachmentNamesTool(),
        "mime_attachment_sizes": MimeAttachmentSizesTool(),
        "mime_multipart": MimeMultipartTool(),
        "mime_multipart_flatten": MimeMultipartFlattenTool(),
        "mime_part_headers": MimePartHeadersTool(),
        "pluralize": PluralizeTool(),
        "punycode": PunycodeTool(),
        "readonly_file": ReadOnlyFileTool(root=root),
        "redact": RedactionTool(),
        "regex": RegexExtractTool(),
        "regex_replace": RegexReplaceTool(),
        "rot13": Rot13Tool(),
        "semver_compare": SemverCompareTool(),
        "slugify": SlugifyTool(),
        "soundex": SoundexTool(),
        "spreadsheet_slice": SpreadsheetSliceTool(),
        "template_render": TemplateRenderTool(),
        "text_case": TextCaseTool(),
        "text_center_lines": TextCenterLinesTool(),
        "text_collapse_blank": TextCollapseBlankTool(),
        "text_dedent": TextDedentTool(),
        "text_indent": TextIndentTool(),
        "text_justify_lines": TextJustifyLinesTool(),
        "text_margin_lines": TextMarginLinesTool(),
        "text_outdent": TextOutdentTool(),
        "text_pad_lines": TextPadLinesTool(),
        "text_slug_lines": TextSlugLinesTool(),
        "text_sort_lines": TextSortLinesTool(),
        "text_squeeze_ws": TextSqueezeWsTool(),
        "text_title_lines": TextTitleLinesTool(),
        "text_unique_lines": TextUniqueLinesTool(),
        "text_wrap": TextWrapTool(),
        "toml_format": TomlFormatTool(),
        "toml_json": TomlJsonTool(),
        "truncate": TextTruncateTool(),
        "tsv_format": TsvFormatTool(),
        "unicode_normalize": UnicodeNormalizeTool(),
        "url_encode": UrlEncodeTool(),
        "url_normalize": UrlNormalizeTool(),
        "url_parse": UrlParseTool(),
        "uuid4": Uuid4Tool(),
        "uuid5": Uuid5Tool(),
        "uuid_nil": UuidNilTool(),
        "xml_escape": XmlEscapeTool(),
        "xml_parse": XmlParseTool(),
        "yaml_format": YamlFormatTool(),
        "yaml_to_json": YamlToJsonTool(),
        "zip_list": ZipListTool(),
    }
