"""The report contract validator — the cage, tested without any model."""

import pytest

from corpus.research.contract import (
    ContractViolation,
    substitute_tokens,
    validate,
)

WHITELIST = {"fin.roce_median_5y", "val.pe_pctl_5y", "gov.pledge_pct"}


def good_draft() -> str:
    return """\
## Position
A capital-efficiency thesis for the MID horizon.

## Why now
Median ROCE over five years is {{fin.roce_median_5y}} while the stock trades
at the {{val.pe_pctl_5y}} percentile of its own history. Management guided
capacity expansion at the concall [F1].

## What has to stay true
- TTM EBITDA margin stays above the falsifier threshold.
- Promoter pledge {{gov.pledge_pct}} does not rise materially.

## How this loses money
The capacity expansion [F1] slips and absorbs cash while margins compress.
The pledge {{gov.pledge_pct}} is collateral: a funding squeeze forces supply.
A large customer renegotiates terms, breaking the working-capital cycle.

## What we could not check
Estimate revisions are unavailable; no consensus source is wired.
"""


def test_valid_draft_passes():
    validate(good_draft(), WHITELIST, {1})


def test_bare_numeral_rejected():
    draft = good_draft().replace("five years", "5 years")
    with pytest.raises(ContractViolation, match="BARE_NUMERAL"):
        validate(draft, WHITELIST, {1})


def test_numeral_inside_token_is_fine_but_unknown_token_rejected():
    draft = good_draft().replace("{{val.pe_pctl_5y}}", "{{val.made_up_9y}}")
    with pytest.raises(ContractViolation, match="UNKNOWN_TOKEN"):
        validate(draft, WHITELIST, {1})


def test_list_markers_are_whitelisted():
    draft = good_draft().replace(
        "## What we could not check\n",
        "## What we could not check\n1. Estimate revisions\n2. Promoter interviews\n",
    )
    validate(draft, WHITELIST, {1})


def test_missing_section_rejected():
    draft = good_draft().replace("## How this loses money", "## Risks")
    with pytest.raises(ContractViolation, match="MISSING_SECTION"):
        validate(draft, WHITELIST, {1})


def test_banned_phrase_rejected():
    draft = good_draft() + "\nThis is a guaranteed compounding story."
    with pytest.raises(ContractViolation, match="BANNED_PHRASE"):
        validate(draft, WHITELIST, {1})


def test_ungrounded_citation_rejected():
    draft = good_draft().replace("[F1]", "[F7]")
    with pytest.raises(ContractViolation, match="UNGROUNDED_CLAIM"):
        validate(draft, WHITELIST, {1})


def test_why_now_needs_tokens_and_citation():
    draft = good_draft().replace("{{fin.roce_median_5y}}", "strong")
    with pytest.raises(ContractViolation, match="WHY_NOW_UNGROUNDED"):
        validate(draft, WHITELIST, {1})


def test_generic_premortem_rejected():
    draft = good_draft().replace(
        """The capacity expansion [F1] slips and absorbs cash while margins compress.
The pledge {{gov.pledge_pct}} is collateral: a funding squeeze forces supply.
A large customer renegotiates terms, breaking the working-capital cycle.""",
        "A market downturn hurts all stocks. Market volatility is a risk.",
    )
    with pytest.raises(ContractViolation, match="GENERIC_PREMORTEM"):
        validate(draft, WHITELIST, {1})


def test_substitution_resolves_every_token():
    out = substitute_tokens(
        "ROCE is {{fin.roce_median_5y}}.", {"fin.roce_median_5y": "19.4%"}
    )
    assert out == "ROCE is 19.4%."
    with pytest.raises(ContractViolation, match="UNRESOLVED_TOKEN"):
        substitute_tokens("P/E {{val.pe_pctl_5y}}", {})
