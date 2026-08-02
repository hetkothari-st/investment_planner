"""The report contract validator — docs/07.

The mechanism that makes the LLM incapable of inventing a number. Not prompt
discipline (which fails silently): a deterministic validator. This module
lives outside corpus/llm on purpose — it imports nothing from it and can be
tested without any model in the room.
"""

import re
from dataclasses import dataclass

# A digit that is not inside a {{token}}. strip_tokens() removes tokens first,
# so the check reduces to "any numeral at all outside the whitelist below".
NUMERAL = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
TOKEN = re.compile(r"\{\{([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)\}\}")
CITATION = re.compile(r"\[F(\d+)\]")

# Explicit whitelist of numeral contexts, per docs/07: enumerated list markers
# at line start, and ordinal words handled by not being numerals at all.
LIST_MARKER = re.compile(r"^\s*\d+\.\s", re.MULTILINE)

REQUIRED_SECTIONS = (
    "## Position",
    "## Why now",
    "## What has to stay true",
    "## How this loses money",
    "## What we could not check",
)

FALSIFIER_BLOCK = re.compile(r"##\s*What has to stay true", re.IGNORECASE)

BANNED_PHRASES = (
    "will definitely", "guaranteed", "multibagger", "sure shot",
    "can't go wrong", "risk-free", "must buy", "screaming buy",
    "to the moon", "no downside", "poised to explode",
)

# Generic market-risk phrases that do not count as company-specific failure
# paths in "How this loses money".
GENERIC_RISK_ONLY = (
    "market falls", "market downturn", "market volatility", "global slowdown",
    "macro risk", "broad selloff", "market correction",
)


@dataclass(frozen=True)
class ContractViolation(Exception):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def strip_tokens(draft: str) -> str:
    return TOKEN.sub("", draft)


def _strip_whitelisted(text: str) -> str:
    return LIST_MARKER.sub("", text)


def validate(
    draft: str,
    whitelist: set[str],
    fact_ids: set[int],
) -> None:
    """Raise ContractViolation on the first breach; return None when clean.

    fact_ids: the [Fn] citation numbers of the facts the composer was given.
    docs/07's supports() check is implemented mechanically: every qualitative
    claim must carry an [Fn] citation to a provided fact, and 'Why now' must
    cite at least one fact and two tokens.
    """
    bare = _strip_whitelisted(strip_tokens(draft))
    m = NUMERAL.search(bare)
    if m:
        raise ContractViolation("BARE_NUMERAL", m.group())

    for tok in TOKEN.findall(draft):
        if tok not in whitelist:
            raise ContractViolation("UNKNOWN_TOKEN", tok)

    for section in REQUIRED_SECTIONS:
        if section not in draft:
            raise ContractViolation("MISSING_SECTION", section)

    if not FALSIFIER_BLOCK.search(draft):
        raise ContractViolation("NO_FALSIFIER", "no falsifier block")

    for cited in CITATION.findall(draft):
        if int(cited) not in fact_ids:
            raise ContractViolation("UNGROUNDED_CLAIM", f"[F{cited}] not in provided facts")

    why_now = _section(draft, "## Why now")
    if len(TOKEN.findall(why_now)) < 2:
        raise ContractViolation("WHY_NOW_UNGROUNDED", "needs >= 2 metric tokens")
    if fact_ids and not CITATION.search(why_now):
        raise ContractViolation("WHY_NOW_UNGROUNDED", "needs >= 1 [Fn] fact citation")

    lower = draft.lower()
    for banned in BANNED_PHRASES:
        if banned in lower:
            raise ContractViolation("BANNED_PHRASE", banned)

    loses = _section(draft, "## How this loses money").lower()
    specific = TOKEN.search(_section(draft, "## How this loses money")) or CITATION.search(
        _section(draft, "## How this loses money")
    )
    if not specific and any(g in loses for g in GENERIC_RISK_ONLY):
        raise ContractViolation(
            "GENERIC_PREMORTEM",
            "How this loses money cites only market-wide risk",
        )
    if not loses.strip():
        raise ContractViolation("GENERIC_PREMORTEM", "empty pre-mortem")


def _section(draft: str, heading: str) -> str:
    start = draft.find(heading)
    if start < 0:
        return ""
    end = draft.find("\n## ", start + len(heading))
    return draft[start + len(heading) : end if end > 0 else len(draft)]


def substitute_tokens(draft: str, values: dict[str, str]) -> str:
    """Replace {{field_id}} with rendered values. Every token must resolve —
    an unresolvable token at render time is a violation, not a dash."""

    def repl(m: re.Match) -> str:
        tok = m.group(1)
        if tok not in values:
            raise ContractViolation("UNRESOLVED_TOKEN", tok)
        return values[tok]

    return TOKEN.sub(repl, draft)
