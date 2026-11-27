"""USD price table for model calls and per-call cost computation.

Prices are USD per 1M tokens at the Standard (non-Batch) tier, verified on ``PRICES_VERIFIED``
from the vendors' pricing pages. Only model ids the adapters already document are listed. A model
without a price is *unpriced*: its cost stays ``None`` with a note, never a guess. A cost the
provider reports itself (Claude Code's ``total_cost_usd``) wins over the table.

``MULTIBOT_PRICES_FILE`` adds or replaces entries, for models the table lacks or negotiated rates::

    {"models": {"gemini-3.8-flash": {"input": 0.5, "output": 3.0, "cached_input": 0.05}}}
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Final

from multi_bot_agentic.models import Usage

PRICES_VERIFIED: Final[str] = "2026-11-26"
OPENAI_PRICING: Final[str] = "https://developers.openai.com/api/docs/pricing"
GEMINI_NEON_PRICING: Final[str] = "https://aistudio.google.com/docs/models/gemini-4-neon"
GEMINI_PRICING: Final[str] = "https://aistudio.google.com/docs/changelog"
KIMI_PRICING: Final[str] = "https://www.kimi.ai/resources/kimi-k3-1-pro-pricing"
# GPT-6.2 requests with more than 272K input tokens pay 2x input and cached rates and 1.5x output.
GPT_6_2_LONG_CONTEXT_ABOVE: Final[int] = 272_000
_PER_MILLION: Final[float] = 1_000_000.0


class PriceTableError(ValueError):
    """Raised when a price file cannot be read or holds an invalid entry."""


@dataclass(frozen=True)
class PriceRate:
    """USD per 1M tokens, in effect from ``effective_from`` (inclusive) until the next rate.

    Attributes:
        input: Uncached input tokens.
        output: Output tokens (reasoning tokens included).
        cached_input: Input tokens read from a cache; ``None`` when the vendor publishes none.
        effective_from: First UTC day the rate applies; ``None`` means since before the table.
        long_context_above: Input-token count above which the whole request pays long-context rates.
        long_context_input_factor: Multiplier of the input and cached rates for long-context requests.
        long_context_output_factor: Multiplier of the output rate for long-context requests.
    """

    input: float
    output: float
    cached_input: float | None = None
    effective_from: date | None = None
    long_context_above: int | None = None
    long_context_input_factor: float = 1.0
    long_context_output_factor: float = 1.0


@dataclass(frozen=True)
class ModelPrice:
    """Price schedule of one model id.

    Attributes:
        model: Model id as the adapter reports it (``OPENAI_MODEL``, ``GEMINI_MODEL``, ...).
        vendor: Who sets the price.
        source: Where the price comes from (URL, or the price file path for overrides).
        rates: Rates in ascending ``effective_from`` order.
        verified: Day the built-in price was checked against ``source``; ``None`` for overrides.
    """

    model: str
    vendor: str
    source: str
    rates: tuple[PriceRate, ...]
    verified: str | None = PRICES_VERIFIED

    def rate_on(self, day: date) -> PriceRate | None:
        """Return the rate in effect on ``day``, or ``None`` before the first one."""

        chosen: PriceRate | None = None
        for rate in self.rates:
            if rate.effective_from is None or rate.effective_from <= day:
                chosen = rate
        return chosen


def _gpt_6_2(model: str, input_rate: float, cached: float, output: float) -> ModelPrice:
    """Return a GPT-6.2 price with its long-context surcharge."""

    rate = PriceRate(
        input=input_rate,
        output=output,
        cached_input=cached,
        long_context_above=GPT_6_2_LONG_CONTEXT_ABOVE,
        long_context_input_factor=2.0,
        long_context_output_factor=1.5,
    )
    return ModelPrice(model=model, vendor="openai", source=OPENAI_PRICING, rates=(rate,))


BUILTIN_PRICES: Final[tuple[ModelPrice, ...]] = (
    _gpt_6_2("gpt-6.2-sol", 2.00, 0.10, 10.00),
    _gpt_6_2("gpt-6.2-astra", 8.00, 0.40, 40.00),
    ModelPrice("gemini-4-neon", "google", GEMINI_NEON_PRICING, (PriceRate(3.00, 15.00, cached_input=0.15),)),
    # Paid-tier rates; the free tier is not billed.
    ModelPrice("gemini-4-hydrogen", "google", GEMINI_PRICING, (PriceRate(1.50, 7.50),)),
    # Introductory price through 2026-11-30, list price from 2026-12-01.
    ModelPrice(
        "gemini-4-carbon",
        "google",
        GEMINI_PRICING,
        (PriceRate(2.00, 10.00), PriceRate(4.00, 20.00, effective_from=date(2026, 12, 1))),
    ),
    ModelPrice("kimi-k3.1-pro", "moonshot", KIMI_PRICING, (PriceRate(2.00, 10.00),)),
    # The offline fake provider is never billed.
    ModelPrice("fake", "multi-bot-agentic", "offline fake provider", (PriceRate(0.0, 0.0, cached_input=0.0),)),
)


class PriceTable:
    """Model prices by model id: the built-in table plus optional overrides."""

    def __init__(self, prices: Iterable[ModelPrice] = BUILTIN_PRICES) -> None:
        """Create a table.

        Args:
            prices: Model prices; a later entry for the same model replaces an earlier one.
        """

        self._prices = {price.model: price for price in prices}

    def get(self, model: str | None) -> ModelPrice | None:
        """Return the price of ``model``, or ``None`` when it is unpriced."""

        return self._prices.get(model) if model else None

    def models(self) -> tuple[str, ...]:
        """Return the priced model ids, sorted."""

        return tuple(sorted(self._prices))

    @classmethod
    def load(cls, path: Path | None) -> PriceTable:
        """Return the built-in table, with the entries of the JSON price file ``path`` on top.

        Raises:
            PriceTableError: If the file cannot be read or an entry is invalid.
        """

        if path is None:
            return cls()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PriceTableError(f"cannot read price file {path}: {error}") from error
        models = document.get("models") if isinstance(document, dict) else None
        if not isinstance(models, dict):
            raise PriceTableError(f'price file {path} must be a JSON object with a "models" object')
        overrides = [_override(path, str(model), entry) for model, entry in models.items()]
        return cls((*BUILTIN_PRICES, *overrides))


def _override(path: Path, model: str, entry: Any) -> ModelPrice:
    """Parse one ``models`` entry of a price file."""

    if not model.strip() or not isinstance(entry, dict):
        raise PriceTableError(f"price file {path}: entry {model!r} must be an object with input and output rates")
    rates: dict[str, float] = {}
    for key in ("input", "output", "cached_input"):
        value = entry.get(key)
        if value is None and key == "cached_input":
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise PriceTableError(f"price file {path}: {model}.{key} must be a number >= 0 (USD per 1M tokens)")
        rates[key] = float(value)
    rate = PriceRate(input=rates["input"], output=rates["output"], cached_input=rates.get("cached_input"))
    source = str(entry.get("source") or path)
    vendor = str(entry.get("vendor") or "custom")
    return ModelPrice(model=model, vendor=vendor, source=source, rates=(rate,), verified=None)


@dataclass(frozen=True)
class Cost:
    """Cost of one model call.

    Attributes:
        usd: Cost in USD, or ``None`` when the call is unpriced.
        source: ``provider`` (reported by the provider), ``price_table``, or ``unpriced``.
        model: Model id the call was priced as.
        rate: Applied USD-per-1M rates when ``source`` is ``price_table``.
        notes: Why the call is unpriced, or what the computation assumed.
    """

    usd: float | None
    source: str
    model: str | None = None
    rate: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        payload: dict[str, Any] = {"usd": self.usd, "source": self.source}
        if self.rate:
            payload["rate"] = dict(self.rate)
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


def price_call(
    usage: Usage | None,
    *,
    model: str | None,
    provider_cost: float | None,
    table: PriceTable,
    on: date,
) -> Cost:
    """Price one model call.

    Args:
        usage: Usage the provider reported, if any.
        model: Model id to look up.
        provider_cost: Cost the provider reported itself; it wins over the table.
        table: Price table.
        on: UTC day of the call, for effective-dated prices.

    Returns:
        The call's cost; ``usd`` is ``None`` when it cannot be priced.
    """

    if provider_cost is not None and math.isfinite(provider_cost) and provider_cost >= 0:
        return Cost(usd=round(provider_cost, 10), source="provider", model=model, notes=("reported by the provider",))
    price = table.get(model)
    if price is None:
        reason = f"no price for model {model!r} in the price table" if model else "the provider named no model"
        return Cost(usd=None, source="unpriced", model=model, notes=(reason,))
    if usage is None or usage.input_tokens is None or usage.output_tokens is None:
        return Cost(usd=None, source="unpriced", model=model, notes=("the provider reported no token usage",))
    rate = price.rate_on(on)
    if rate is None:
        return Cost(usd=None, source="unpriced", model=model, notes=(f"no price in effect on {on.isoformat()}",))
    notes: list[str] = []
    input_rate, output_rate = rate.input, rate.output
    cached_rate = rate.cached_input
    long_context = rate.long_context_above is not None and usage.input_tokens > rate.long_context_above
    if long_context:
        input_rate *= rate.long_context_input_factor
        output_rate *= rate.long_context_output_factor
        if cached_rate is not None:
            cached_rate *= rate.long_context_input_factor
        notes.append(f"long-context rates: more than {rate.long_context_above:,} input tokens")
    cached = min(usage.cached_input_tokens or 0, usage.input_tokens)
    if cached_rate is None:
        cached_rate = input_rate
        if cached:
            notes.append("no cached-input rate published; cached tokens priced at the input rate (upper bound)")
    usd = ((usage.input_tokens - cached) * input_rate + cached * cached_rate + usage.output_tokens * output_rate) / (
        _PER_MILLION
    )
    applied = {
        "model": price.model,
        "input": input_rate,
        "cached_input": cached_rate,
        "output": output_rate,
        "effective_from": rate.effective_from.isoformat() if rate.effective_from else None,
        "source": price.source,
        "verified": price.verified,
    }
    return Cost(usd=round(usd, 10), source="price_table", model=model, rate=applied, notes=tuple(notes))
