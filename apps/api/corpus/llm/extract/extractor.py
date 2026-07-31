"""llm/extract — filings text -> typed qualitative facts. Output is data,
not prose (docs/07). Cached by content hash: a filing is extracted once, ever.

The verbatim-span check is the cheap, exact validator that catches most
extraction errors: if evidence_span does not appear in the source text, the
fact is hallucinated — discard and log.
"""

import json
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from corpus.llm.config import load_llm_config


class QualFactOut(BaseModel):
    fact_type: Literal[
        "CAPEX", "ORDER_WIN", "GUIDANCE", "LITIGATION", "MGMT_CHANGE",
        "CAPITAL_RAISE", "ACQUISITION", "RISK", "OTHER",
    ]
    direction: Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]
    magnitude_band: Literal["SMALL", "MATERIAL", "TRANSFORMATIVE"]
    horizon_relevance: list[Literal["SHORT", "MID", "LONG"]]
    summary: str = Field(max_length=220)
    evidence_span: str = Field(max_length=400)  # verbatim from source


class ExtractionResult(BaseModel):
    facts: list[QualFactOut]


class Extractor(Protocol):
    """Anything that turns filing text into an ExtractionResult. The live
    implementation calls Anthropic; tests inject deterministic fakes."""

    def __call__(self, filing_text: str) -> ExtractionResult: ...


EXTRACTION_PROMPT = """\
Extract material qualitative facts from this corporate filing. Emit ONLY
facts stated in the text. For each fact, evidence_span must be copied
VERBATIM from the source — an exact substring, character for character.
The summary must not contain numbers unless they are quoted inside the
evidence span. Emit an empty list when nothing is material.

FILING TEXT:
{filing_text}
"""


def anthropic_extractor() -> Extractor:
    """The live extractor. Lazy import: corpus.llm is the only package
    permitted to import anthropic, and only when actually called."""
    import anthropic

    cfg = load_llm_config().extraction
    client = anthropic.Anthropic()

    def extract(filing_text: str) -> ExtractionResult:
        response = client.messages.create(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            temperature=float(cfg.temperature),
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": ExtractionResult.model_json_schema(),
                }
            },
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(filing_text=filing_text),
                }
            ],
        )
        if response.stop_reason == "refusal":
            return ExtractionResult(facts=[])
        payload = "".join(b.text for b in response.content if b.type == "text")
        return ExtractionResult.model_validate(json.loads(payload))

    return extract


def validate_spans(
    result: ExtractionResult, source_text: str
) -> tuple[list[QualFactOut], list[QualFactOut]]:
    """(kept, discarded). A fact whose evidence_span is not a verbatim
    substring of the source is hallucinated."""
    kept, discarded = [], []
    for fact in result.facts:
        (kept if fact.evidence_span in source_text else discarded).append(fact)
    return kept, discarded
