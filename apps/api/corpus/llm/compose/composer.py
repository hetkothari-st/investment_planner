"""llm/compose — structured facts + token whitelist -> report narrative.

The composer never sees raw filing text (it would paraphrase numbers out of
it and bypass the token system). It sees extracted facts and a whitelist of
metric tokens, and must reference numbers as {{field_id}} only. The output
must pass corpus/research/contract.validate — enforcement is downstream and
mechanical, not in the prompt.
"""

from typing import Protocol

from corpus.llm.config import load_llm_config
from corpus.llm.extract.extractor import QualFactOut


class Composer(Protocol):
    def __call__(
        self,
        symbol: str,
        horizon: str,
        whitelist: dict[str, str],  # field_id -> human label + unit
        facts: list[QualFactOut],
        violation_feedback: str | None,
    ) -> str: ...


COMPOSITION_PROMPT = """\
Write the narrative sections of an equity research note for {symbol}
({horizon} horizon).

RULES — mechanical, validated after you write:
- You may reference measured values ONLY via tokens, exactly as listed below.
- Do not write any numeral yourself. If a figure you need is not listed,
  omit the claim entirely.
- Every qualitative claim must cite one of the numbered facts as [Fn].
- Structure: exactly these markdown sections, in order:
  ## Position
  ## Why now            (2-4 sentences; >= 2 tokens and >= 1 [Fn] citation)
  ## What has to stay true
  ## How this loses money   (three failure paths SPECIFIC to this company;
                             generic market risk alone is a violation)
  ## What we could not check
- Plain, direct register. No exclamation marks, no encouragement, no
  superlatives about returns.

AVAILABLE TOKENS
{tokens}

FACTS (cite as [Fn])
{facts}
{feedback}
"""


def anthropic_composer() -> Composer:
    """The live composer. Lazy anthropic import, per the architectural fence."""
    import anthropic

    cfg = load_llm_config().composition
    client = anthropic.Anthropic()

    def compose(
        symbol: str,
        horizon: str,
        whitelist: dict[str, str],
        facts: list[QualFactOut],
        violation_feedback: str | None,
    ) -> str:
        tokens = "\n".join(
            f"  {{{{{fid}}}}}    {label}" for fid, label in sorted(whitelist.items())
        )
        fact_lines = "\n".join(
            f"  [F{i}] {f.fact_type} {f.direction}: {f.summary}"
            for i, f in enumerate(facts, start=1)
        ) or "  (no extracted facts available)"
        feedback = (
            f"\nYOUR PREVIOUS DRAFT WAS REJECTED: {violation_feedback}. Fix it."
            if violation_feedback
            else ""
        )
        response = client.messages.create(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            temperature=float(cfg.temperature),
            messages=[
                {
                    "role": "user",
                    "content": COMPOSITION_PROMPT.format(
                        symbol=symbol, horizon=horizon, tokens=tokens,
                        facts=fact_lines, feedback=feedback,
                    ),
                }
            ],
        )
        if response.stop_reason == "refusal":
            return ""
        return "".join(b.text for b in response.content if b.type == "text")

    return compose
