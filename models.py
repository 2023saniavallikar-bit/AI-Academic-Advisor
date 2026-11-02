"""Which chat models the advisor may use, and what they cost.

Simple idea
-----------
* ``MODEL_SPECS`` is the allow-list of models we know about. Each entry says
  how to call the model and what Google charges for it.
* The browser may only pick a model that is in the allow-list AND enabled for
  this deployment. The server checks this, so nobody can send any random name.
* Token counts always come from the API response. The *price* comes from this
  file, so a cost shown to the user is always labelled "estimated".

Prices are US dollars per 1 million tokens, copied by hand from Google's
official pricing page (see PRICING_SOURCE) on PRICING_CHECKED_ON. Prices change,
so re-check that page before relying on them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os

PRICING_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
PRICING_CHECKED_ON = "2026-10-31"
DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash-lite"


@dataclass(frozen=True)
class PriceRule:
    """One price. A model can have several (by date, or by prompt size)."""

    input_per_million: float
    output_per_million: float  # includes "thinking" tokens, as Google bills them
    valid_from: date | None = None  # first day this price applies (inclusive)
    valid_until: date | None = None  # last day this price applies (inclusive)
    max_input_tokens: int | None = None  # rule only for prompts up to this size

    def applies(self, on_date: date, input_tokens: int) -> bool:
        if self.valid_from and on_date < self.valid_from:
            return False
        if self.valid_until and on_date > self.valid_until:
            return False
        if self.max_input_tokens is not None and input_tokens > self.max_input_tokens:
            return False
        return True


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    prices: tuple[PriceRule, ...] = ()
    # None means "do not send a temperature": Google's Gemini 3 guide tells
    # developers to drop the sampling settings for these models.
    temperature: float | None = 0
    note: str = ""
    # False = known, priced, but NOT shown in the dropdown unless ENABLED_MODELS
    # names it. Used for models Google appears to have retired.
    offered: bool = True


# Prices re-read from Google's pricing page on 2026-10-31. The 2.5 models are
# still priced there, but a Google forum thread (10 July 2026) reports that
# gemini-2.5-flash / 2.5-flash-lite return "no longer available" (HTTP 404), and
# the live advisor failed on gemini-2.5-flash. So they are kept for pricing old
# chats but not offered by default.
_RETIRED_NOTE = "Reported as no longer available from Google (404) since July 2026."

MODEL_SPECS: dict[str, ModelSpec] = {
    spec.id: spec
    for spec in (
        ModelSpec(
            id="gemini-3.5-flash-lite",
            label="Gemini 3.5 Flash-Lite",
            prices=(PriceRule(0.30, 2.50),),
            note="Fast and low cost (the current default).",
        ),
        ModelSpec(
            id="gemini-3.6-flash",
            label="Gemini 3.6 Flash",
            prices=(
                PriceRule(0.75, 3.75, valid_until=date(2026, 12, 31)),
                PriceRule(1.50, 7.50, valid_from=date(2027, 1, 1)),
            ),
            temperature=None,
            note="Previous-generation Flash. Price rises on 1 Jan 2027.",
        ),
        ModelSpec(
            id="gemini-3.8-flash",
            label="Gemini 3.8 Flash",
            prices=(
                PriceRule(0.75, 3.75, valid_until=date(2026, 12, 31)),
                PriceRule(1.50, 7.50, valid_from=date(2027, 1, 1)),
            ),
            temperature=None,
            note="Newest Flash model. Price rises on 1 Jan 2027.",
        ),
        ModelSpec(
            id="gemini-2.5-flash",
            label="Gemini 2.5 Flash",
            prices=(PriceRule(0.30, 2.50),),
            note=_RETIRED_NOTE,
            offered=False,
        ),
        ModelSpec(
            id="gemini-2.5-flash-lite",
            label="Gemini 2.5 Flash-Lite",
            prices=(PriceRule(0.10, 0.40),),
            note=_RETIRED_NOTE,
            offered=False,
        ),
        ModelSpec(
            id="gemini-2.5-pro",
            label="Gemini 2.5 Pro",
            prices=(
                PriceRule(1.25, 10.00, max_input_tokens=200_000),
                PriceRule(2.50, 15.00),
            ),
            note="Not checked live; hidden until confirmed available.",
            offered=False,
        ),
    )
}


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def default_model_id() -> str:
    """The model used when the browser does not choose one."""
    return os.getenv("CHAT_MODEL", DEFAULT_FALLBACK_MODEL)


def enabled_model_ids() -> list[str]:
    """Models the dropdown offers.

    * ``ENABLED_MODELS`` (comma separated) sets the list when present. It may
      name any model in ``MODEL_SPECS``, including ones hidden by default.
    * Otherwise every model marked ``offered`` is listed.
    * The configured default model is always included, even when it is not in
      ``MODEL_SPECS`` (it then simply has no price, so cost shows "unavailable").
    """
    configured = _csv_env("ENABLED_MODELS")
    ids = (
        [m for m in configured if m in MODEL_SPECS]
        if configured
        else [m for m, spec in MODEL_SPECS.items() if spec.offered]
    )
    default = default_model_id()
    if default not in ids:
        ids.insert(0, default)
    return ids


def get_spec(model_id: str) -> ModelSpec:
    spec = MODEL_SPECS.get(model_id)
    if spec is not None:
        return spec
    # A model set only through CHAT_MODEL: callable, but we have no price for it.
    return ModelSpec(id=model_id, label=model_id, prices=(), temperature=0,
                     note="Custom model. No price on file.")


def model_options() -> list[dict]:
    """What the dropdown needs: id, label, note."""
    return [
        {"id": mid, "label": get_spec(mid).label, "note": get_spec(mid).note}
        for mid in enabled_model_ids()
    ]


def resolve_model(requested: str | None) -> str:
    """Return a safe model id, or raise ValueError for one we do not allow."""
    if requested is None or requested == "":
        return default_model_id()
    if requested not in enabled_model_ids():
        raise ValueError("That model is not available.")
    return requested


def estimate_cost(
    spec: ModelSpec,
    input_tokens: int | None,
    output_tokens: int | None,
    on_date: date | None = None,
) -> dict | None:
    """Estimated cost in USD, or None when we cannot say.

    We return None (never a guess) when the API gave no token counts or we have
    no price for this model on this date.
    """
    if input_tokens is None or output_tokens is None:
        return None
    on_date = on_date or date.today()
    rule = next((r for r in spec.prices if r.applies(on_date, input_tokens)), None)
    if rule is None:
        return None
    amount = (
        input_tokens * rule.input_per_million + output_tokens * rule.output_per_million
    ) / 1_000_000
    return {
        "amount_usd": round(amount, 8),
        "currency": "USD",
        "estimated": True,
        "basis": (
            f"${rule.input_per_million:g} per 1M input tokens and "
            f"${rule.output_per_million:g} per 1M output tokens "
            f"(Google pricing page, checked {PRICING_CHECKED_ON}). "
            "Cached-prompt discounts are not applied."
        ),
    }


def extract_usage(message) -> dict | None:
    """Read token counts exactly as the API reported them (never estimate)."""
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return None
    try:
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    except AttributeError:
        return None
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    total = usage.get("total_tokens")
    out_details = usage.get("output_token_details") or {}
    in_details = usage.get("input_token_details") or {}
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,  # already includes thinking tokens
        "total_tokens": total if isinstance(total, int) else input_tokens + output_tokens,
        "reasoning_tokens": out_details.get("reasoning") or None,
        "cached_input_tokens": in_details.get("cache_read") or None,
        "source": "api",
    }
