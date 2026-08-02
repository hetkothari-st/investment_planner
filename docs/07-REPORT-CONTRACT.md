# 07 — Report Contract

The mechanism that makes the LLM incapable of inventing a number.
Not prompt discipline. Prompt discipline fails silently. This is a validator.

## The core trick: the model can only emit tokens, never digits

The composer receives a **token whitelist** and must reference numbers as
`{{field_id}}`. The renderer substitutes real values afterwards.

Prompt fragment:

```
You may reference these measured values only, using the exact token form shown.
Do not write any numeral yourself. If you need a figure that is not listed,
omit the claim entirely.

AVAILABLE TOKENS
  {{fin.roce_median_5y}}       ROCE median, 5 years, percent
  {{val.pe_pctl_5y}}           P/E percentile vs own 5-year history, percent
  {{gov.pledge_pct}}           Promoter pledge, percent
  ...
```

Model writes:

> Capital efficiency has held up: median ROCE over five years is {{fin.roce_median_5y}},
> and the stock trades at the {{val.pe_pctl_5y}} percentile of its own five-year range.

Renderer substitutes → `19.4%` and `31st`. The model never touched a digit.

## Validation gate

```python
NUMERAL = re.compile(r"(?<!\{)\b\d[\d,]*(?:\.\d+)?\b(?!\})")
TOKEN   = re.compile(r"\{\{([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)\}\}")

def validate(draft: str, whitelist: set[str], facts: list[QualFact]) -> None:
    if NUMERAL.search(strip_tokens(draft)):
        raise ContractViolation("BARE_NUMERAL", NUMERAL.search(...).group())

    for tok in TOKEN.findall(draft):
        if tok not in whitelist:
            raise ContractViolation("UNKNOWN_TOKEN", tok)

    for section in REQUIRED_SECTIONS:
        if section not in draft:
            raise ContractViolation("MISSING_SECTION", section)

    if not FALSIFIER_BLOCK.search(draft):
        raise ContractViolation("NO_FALSIFIER")

    for claim in extract_qualitative_claims(draft):
        if not any(fact.supports(claim) for fact in facts):
            raise ContractViolation("UNGROUNDED_CLAIM", claim)

    for banned in BANNED_PHRASES:
        if banned in draft.lower():
            raise ContractViolation("BANNED_PHRASE", banned)
```

Allowed exceptions to `BARE_NUMERAL`: ordinals in prose ("first quarter"), years inside
a `{{...}}`-free quoted `evidence_span`, and enumerated list markers. Whitelist these
explicitly; don't loosen the regex.

### Banned phrases (non-exhaustive, extend as you see them)

```
"will definitely"   "guaranteed"      "multibagger"     "sure shot"
"can't go wrong"    "risk-free"       "must buy"        "screaming buy"
"to the moon"       "no downside"     "poised to explode"
```

### On violation
Write to `cascade_gap` with stage, isin, horizon, reason, raw output. Retry once with the
violation appended to the prompt. On second failure, render the report **without the
narrative section** — the deterministic metrics and band still display. A report with
no prose is fine. A report with invented prose is not.

## Report structure (enforced sections, exact order)

```markdown
## Position
{one sentence: what this is and for which horizon}

## Why now
{2–4 sentences. Must cite ≥2 tokens and ≥1 qual_fact evidence span.}

## What the numbers say
{table — rendered by the app from metric_values, NOT written by the model}

## Scenario band
{table — computed, not written. Includes n_analogues and the honest bear case.}

## What has to stay true
{the falsifiers, in plain language, each bound to a field_id}

## How this loses money
{MANDATORY pre-mortem. The three most likely failure paths.
 Must be specific to this company. Generic market risk is a contract violation.}

## What we could not check
{coverage gaps, stale sources, missing fundamentals. Named, not hidden.}

## Sizing
{computed. suggested_size_inr, resulting portfolio heat, days-to-exit at that size.}
```

**"How this loses money" is mandatory and validated for specificity.** If it mentions
only market-wide risk with no company-specific mechanism, reject it. This section is
the single best defence against the model's tendency toward advocacy.

## The extraction stage (separate model call, separate schema)

`llm/extract/` never writes prose. It emits typed facts:

```python
class QualFactOut(BaseModel):
    fact_type: Literal["CAPEX","ORDER_WIN","GUIDANCE","LITIGATION","MGMT_CHANGE",
                       "CAPITAL_RAISE","ACQUISITION","RISK","OTHER"]
    direction: Literal["POSITIVE","NEGATIVE","NEUTRAL"]
    magnitude_band: Literal["SMALL","MATERIAL","TRANSFORMATIVE"]
    horizon_relevance: list[Literal["SHORT","MID","LONG"]]
    summary: str = Field(max_length=220)
    evidence_span: str = Field(max_length=400)   # verbatim from source
```

Validation: `evidence_span` must appear **verbatim** in the source filing text.
If it doesn't, the fact is hallucinated — discard it and log. This is a cheap, exact
check and it catches the majority of extraction errors.

Cache extraction by `filings.content_hash`. A filing is extracted exactly once, ever.

## Model roles

| Stage | Model | Temperature | Why |
|---|---|---|---|
| Extraction | `claude-sonnet-4-6` | 0 | High volume, structured output, cheap |
| Composition | Opus-class | 0.3 | Low volume, quality matters, still constrained |
| Falsifier phrasing | `claude-sonnet-4-6` | 0 | Template-filling only |

## Provenance in the UI

Every block in a rendered report carries a small engraved label (see design system):

- `MEASURED` — from `metric_values`, cyan label
- `COMPUTED` — derived (bands, sizing, hurdle), cyan label
- `INFERRED` — LLM narrative grounded in cited facts, amber label
- `SOURCE` — verbatim filing excerpt, neutral label

The user must always be able to tell at a glance which parts of a report are arithmetic
and which parts are argument. This is the visual expression of the whole architecture,
and it's why the design system reserves a dedicated label slot on every panel.

## Anti-patterns

Do not:
- Let the composer see the raw filing text. It sees extracted facts only. Otherwise it
  will paraphrase numbers out of the filing and bypass the token system.
- Use function calling to let the model "look up" a metric mid-generation. Whitelist upfront.
- Retry more than once. Two failures means the prompt or the data is wrong; fix that instead.
- Show a report where `meta.coverage < 0.60`. Refuse and say why.
